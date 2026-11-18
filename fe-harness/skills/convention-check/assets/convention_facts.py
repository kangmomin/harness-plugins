#!/usr/bin/env python3
"""convention-check의 결정적 사전 검사 — LLM 없이 판정할 수 있는 컨벤션 사실만 계산한다.

계약: workflow_scope.py가 만든 scope JSON(--scope FILE, 또는 - = stdin)을 입력으로 받는다.
      범위를 다시 계산하지 않는다. 결과는 stdout JSON 1건이며 판정 근거(path·line·detail)를 포함한다.
종료: 0 = 검사 완료(위반이 있어도 0) / 2 = BLOCKED:CONVENTION_FACTS (입력·git 오류 — 호출자는 LLM 절차로 폴백).
의존: 표준 라이브러리만. POSIX 전용 모듈을 쓰지 않는다. 텍스트는 UTF-8로 명시해 읽는다.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

CHECKS = ('new-dependency', 'sql-in-literal', 'component-path', 'hooks-coverage')
PATTERNS = ('feature-based', 'atomic', 'flat')
DEP_SECTIONS = ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies')
# 이 스크립트가 파싱하지 않는 매니페스트 — 호출자(LLM)가 이 목록만 확인한다.
OTHER_MANIFESTS = {'go.work', 'pyproject.toml', 'Pipfile', 'setup.py', 'setup.cfg', 'Cargo.toml',
                   'build.gradle', 'build.gradle.kts', 'pom.xml', 'Gemfile', 'composer.json'}
SKIP_DIRS = {'node_modules', 'vendor'}
# 대문자 IN만 본다: 소문자 `in (1)`은 주석·문장과 구분되지 않는다. `IN (?)`·`IN (:name)`은
# sqlx.In·GORM 같은 슬라이스 확장 관용구일 수 있어 판정하지 않는다 (LLM 몫).
SQL_IN_SINGLE = re.compile(r"\b(?:NOT\s+)?IN\s*\(\s*('(?:[^']|'')*'|-?\d+(?:\.\d+)?|\$\d+)\s*\)")
SQL_SKIP_SUFFIXES = {'.md', '.mdx', '.txt', '.rst', '.lock', '.sum', '.svg', '.json'}
COMPONENT_SUFFIXES = {'.tsx', '.jsx', '.vue'}
COMPONENT_SKIP_PARTS = {'__tests__', '__mocks__', 'test', 'tests', 'e2e', 'stories', '.storybook', 'app', 'pages'}
COMPONENT_SKIP_MARKS = ('.test.', '.spec.', '.stories.', '.story.')
ATOMIC_LEVELS = {'atoms', 'molecules', 'organisms', 'templates'}
SCRIPT_SUFFIXES = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue'}


class FactsError(ValueError):
    pass


def git(root, *args, check=True):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30)
    if check and result.returncode:
        raise FactsError('git ' + args[0] + ' failed: ' + result.stderr.decode('utf-8', errors='replace').strip())
    return result


def base_text(root, start, path):
    """START 시점 내용. 그때 없던 파일이면 None."""
    listed = git(root, 'ls-tree', '--name-only', start, '--', path).stdout
    if not listed.strip():
        return None
    return git(root, 'show', start + ':' + path).stdout.decode('utf-8', errors='replace')


def current_text(root, path):
    target = Path(root) / path
    if not target.is_file() or target.is_symlink():
        return None
    return target.read_bytes().decode('utf-8', errors='replace')


def line_of(text, needle):
    for number, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return number
    return None


def finding(tag, severity, path, line, detail):
    return dict(tag=tag, severity=severity, path=path, line=line, detail=detail)


def skipped_dir(path):
    return any(part in SKIP_DIRS for part in PurePosixPath(path).parts[:-1])


def go_requires(text):
    """go.mod require 지시자 → {module: indirect 여부}. 단일행·블록 모두 지원."""
    modules, in_block = {}, False
    for raw in text.splitlines():
        line = raw.strip()
        if in_block:
            if line.startswith(')'):
                in_block = False
                continue
            body = line
        elif re.match(r'^require\s*\($', line):
            in_block = True
            continue
        elif line.startswith('require '):
            body = line[len('require '):].strip()
        else:
            continue
        code, _, comment = body.partition('//')
        parts = code.split()
        if len(parts) >= 2:
            modules[parts[0].strip('"')] = 'indirect' in comment
    return modules


def package_deps(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('package.json root is not an object')
    deps = {}
    for section in DEP_SECTIONS:
        values = data.get(section) or {}
        if not isinstance(values, dict):
            raise ValueError(section + ' is not an object')
        for name in values:
            deps.setdefault(name, section)
    return deps


def new_dependencies(root, start, paths):
    findings, unchecked = [], []
    for path in paths:
        name = PurePosixPath(path).name
        if skipped_dir(path):
            continue
        is_requirements = name.startswith('requirements') and name.endswith('.txt')
        if name in OTHER_MANIFESTS or is_requirements:
            unchecked.append(dict(path=path, reason='unsupported manifest'))
            continue
        if name not in ('go.mod', 'package.json'):
            continue
        current = current_text(root, path)
        if current is None:
            continue
        before = base_text(root, start, path) or ''
        if name == 'go.mod':
            old, new = go_requires(before), go_requires(current)
            for module, indirect in sorted(new.items()):
                if indirect:
                    # 간접 의존은 직접 의존을 추가한 결과다. 직접 의존만 의도 확인 대상이다.
                    continue
                if module not in old:
                    detail = module + ' — 새 직접 의존'
                elif old[module]:
                    detail = module + ' — indirect에서 직접 의존으로 승격'
                else:
                    continue
                findings.append(finding('NEW_DEPENDENCY', 'ERROR', path, line_of(current, module), detail))
        else:
            try:
                old = package_deps(before) if before.strip() else {}
                new = package_deps(current)
            except ValueError as exc:
                unchecked.append(dict(path=path, reason='parse error: ' + str(exc)))
                continue
            for package, section in sorted(new.items()):
                if package not in old:
                    findings.append(finding('NEW_DEPENDENCY', 'ERROR', path, line_of(current, '"' + package + '"'),
                                            package + ' — ' + section + '에 새로 추가'))
    return findings, unchecked


def unquote(name):
    if not name.startswith('"'):
        return name
    # git은 비ASCII 경로를 C 문자열(8진 이스케이프)로 인용한다.
    raw = name[1:-1].encode('latin-1', errors='backslashreplace').decode('unicode_escape')
    return raw.encode('latin-1', errors='replace').decode('utf-8', errors='replace')


def added_lines(patch):
    """통합 diff → [(path, line, text)]. 현재(+) 쪽 줄 번호를 쓴다."""
    found, path, number, in_hunk = [], None, 0, False
    for line in patch.split('\n'):
        if line.startswith('diff --git '):
            path, in_hunk = None, False
        elif not in_hunk and line.startswith('+++ '):
            target = unquote(line[4:].rstrip('\r'))
            path = None if target == '/dev/null' else target[2:] if target.startswith('b/') else target
        elif line.startswith('@@'):
            hunk = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if hunk:
                number, in_hunk = int(hunk[1]), True
        elif in_hunk and line.startswith('+'):
            if path:
                found.append((path, number, line[1:].rstrip('\r')))
            number += 1
        elif in_hunk and line.startswith(' '):
            number += 1
    return found


def read_patch(data, key):
    if isinstance(data.get(key), str):
        return data[key]
    file_key = key + '_file'
    if file_key not in data:
        return ''
    payload = Path(data[file_key]).read_bytes()
    expected = data.get(key + '_sha256')
    if expected and hashlib.sha256(payload).hexdigest() != expected:
        raise FactsError(file_key + ' sha256 mismatch')
    return payload.decode('utf-8', errors='surrogateescape')


def sql_in_literals(root, data):
    lines = added_lines(read_patch(data, 'patch')) + added_lines(read_patch(data, 'index_patch'))
    for path in data.get('owned_untracked', []):
        text = current_text(root, path)
        if text is not None:
            lines += [(path, number, line) for number, line in enumerate(text.splitlines(), 1)]
    findings, seen = [], set()
    for path, number, text in lines:
        if PurePosixPath(path).suffix.lower() in SQL_SKIP_SUFFIXES or skipped_dir(path):
            continue
        for match in SQL_IN_SINGLE.finditer(text):
            key = (path, text.strip(), match.group(0))
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding('SQL_PATTERN', 'ERROR', path, number,
                                    '`' + match.group(0) + '` — 단일 값 IN. `= ` 비교로 바꾼다'))
    return findings


def is_component(path):
    pure = PurePosixPath(path)
    if pure.suffix not in COMPONENT_SUFFIXES or skipped_dir(path):
        return False
    if any(mark in pure.name for mark in COMPONENT_SKIP_MARKS):
        return False
    if any(part in COMPONENT_SKIP_PARTS for part in pure.parts[:-1]):
        return False
    stem = pure.name.split('.')[0]
    name = pure.parent.name if stem == 'index' else stem
    return bool(name) and name[0].isupper()


def component_location_ok(parts, pattern):
    dirs = parts[:-1]
    in_components = 'components' in dirs
    if pattern == 'flat':
        return in_components
    if pattern == 'atomic':
        return any(dirs[i] == 'components' and i + 1 < len(dirs) and dirs[i + 1] in ATOMIC_LEVELS
                   for i in range(len(dirs)))
    # feature-based: features/{도메인}/components/ 또는 features 밖의 공용 components/
    for i, part in enumerate(dirs):
        if part == 'features':
            return i + 2 < len(dirs) and dirs[i + 2] == 'components'
    return in_components


EXPECTED = {
    'feature-based': 'features/{도메인}/components/{ComponentName}/ (공용은 components/)',
    'atomic': 'components/{atoms|molecules|organisms|templates}/{ComponentName}/',
    'flat': 'components/{ComponentName}/',
}


def component_paths(root, start, data, pattern):
    findings = []
    for path in data.get('read', []):
        if not is_component(path) or base_text(root, start, path) is not None:
            continue  # 새로 추가된 컴포넌트 파일만 본다
        if not component_location_ok(PurePosixPath(path).parts, pattern):
            findings.append(finding('COMPONENT_PATH', 'WARN', path, None,
                                    'componentPattern=' + pattern + ' 기대 위치: ' + EXPECTED[pattern] + ' — 파일을 옮기지 말고 보고만'))
    return findings


def declares_react_hooks(root, directory):
    text = current_text(root, (directory / 'package.json').as_posix()) if directory.parts else current_text(root, 'package.json')
    if text is None:
        return False
    try:
        return 'eslint-plugin-react-hooks' in package_deps(text)
    except ValueError:
        return False


def hooks_coverage(root, data):
    """변경된 스크립트 파일마다 조상 package.json 중 하나가 react-hooks ESLint 플러그인을 선언하면 True."""
    sources = [p for p in data.get('read', []) if PurePosixPath(p).suffix in SCRIPT_SUFFIXES and not skipped_dir(p)]
    targets = [PurePosixPath(p).parent for p in sources] or [PurePosixPath('')]
    for directory in targets:
        chain = [directory, *directory.parents] if directory.parts else [directory]
        if not any(declares_react_hooks(root, d) for d in chain):
            return False
    return True


def load_scope(source):
    raw = sys.stdin.buffer.read() if source == '-' else Path(source).read_bytes()
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise FactsError('scope JSON schema_version 1 required')
    if not isinstance(data.get('root'), str) or not isinstance(data.get('start_sha'), str):
        raise FactsError('scope root/start_sha required')
    for key in ('paths', 'read'):
        if not isinstance(data.get(key), list) or not all(isinstance(p, str) for p in data[key]):
            raise FactsError('scope ' + key + ' must be a string array')
    if not Path(data['root']).is_dir():
        raise FactsError('scope root does not exist: ' + data['root'])
    return data


def run(data, checks, pattern):
    root, start = data['root'], data['start_sha']
    git(root, 'cat-file', '-e', start + '^{commit}')
    result = dict(schema_version=1, root=root, start_sha=start, checks=list(checks),
                  findings=[], unchecked_manifests=[], skipped_checks=[], lint_coverage=dict(react_hooks=None))
    if 'new-dependency' in checks:
        found, unchecked = new_dependencies(root, start, data['paths'])
        result['findings'] += found
        result['unchecked_manifests'] = unchecked
    if 'sql-in-literal' in checks:
        result['findings'] += sql_in_literals(root, data)
    if 'component-path' in checks:
        if pattern in PATTERNS:
            result['findings'] += component_paths(root, start, data, pattern)
        else:
            result['skipped_checks'].append(dict(check='component-path', reason='componentPattern 미설정 또는 미지원: ' + str(pattern)))
    if 'hooks-coverage' in checks:
        result['lint_coverage']['react_hooks'] = hooks_coverage(root, data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', required=True, help='workflow_scope.py JSON 경로, - 이면 stdin')
    parser.add_argument('--checks', required=True, help='쉼표 구분: ' + ','.join(CHECKS))
    parser.add_argument('--component-pattern', help='fe profile componentPattern: ' + '|'.join(PATTERNS))
    args = parser.parse_args()
    try:
        checks = [c.strip() for c in args.checks.split(',') if c.strip()]
        unknown = [c for c in checks if c not in CHECKS]
        if not checks or unknown:
            raise FactsError('unknown or empty checks: ' + ', '.join(unknown))
        output = run(load_scope(args.scope), checks, args.component_pattern)
        sys.stdout.buffer.write((json.dumps(output, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        sys.stderr.buffer.write(('BLOCKED:CONVENTION_FACTS — ' + str(exc) + '\n').encode('utf-8'))
        return 2


if __name__ == '__main__':
    sys.exit(main())
