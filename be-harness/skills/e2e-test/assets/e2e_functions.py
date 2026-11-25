#!/usr/bin/env python3
"""e2e 공통 스크립트(function) 목록·실행·저장 helper.

list --cwd C --harness be|fe
run  --cwd C --harness H --name N [--timeout S] -- args...
add  --cwd C --src F --name N --description D --harness be[,fe] --usage U
JSON 출력. 0 성공 / 1 실패 / 2 입력 오류.

구조: <function root>/_shared/ + <function root>/<project>/, 각 폴더 manifest.json(version 1).
function root·project 규칙은 start-workflow/assets/harness_store.py를 따른다. 실행은 shell 없이 인터프리터로만.
be-harness 정본, fe 동일 사본(check_contracts.py parity).
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time

_STORE_SPEC = importlib.util.spec_from_file_location(
    'harness_store', Path(__file__).resolve().parents[2] / 'start-workflow' / 'assets' / 'harness_store.py')
store = importlib.util.module_from_spec(_STORE_SPEC)
_STORE_SPEC.loader.exec_module(store)
ConfigError = store.ConfigError

SHARED = '_shared'
MANIFEST = 'manifest.json'
NAME = re.compile(r'^[a-z0-9][a-z0-9._-]{0,63}$')
EXTENSIONS = ('.sh', '.py', '.js')
HARNESSES = ('be', 'fe')
TEXT_LIMIT = 200
SOURCE_LIMIT = 1024 * 1024
LOCK_WAIT = 5.0
DEFAULT_TIMEOUT = 300.0


def _text_ok(value):
    return isinstance(value, str) and len(value) <= TEXT_LIMIT and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('중복 키: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def _regular(path):
    """symlink 아닌 일반 파일의 lstat, 없으면 None."""
    info = store.lstat_or_none(path)
    if info is not None and not stat.S_ISREG(info.st_mode):
        raise ValueError('일반 파일이 아님(symlink 포함): %s' % Path(path).name)
    return info


def _valid_manifest(data):
    return isinstance(data, dict) and type(data.get('version')) is int and data['version'] == 1 \
        and isinstance(data.get('scripts'), list)


def _entry_problem(folder, entry):
    if not isinstance(entry, dict):
        return '항목이 객체가 아님'
    name = entry.get('name')
    if not isinstance(name, str) or not NAME.match(name):
        return 'name 형식 오류'
    path = entry.get('path')
    if not isinstance(path, str) or not path or path != os.path.basename(path) or '/' in path or '\\' in path or path in ('.', '..'):
        return '%s: path는 폴더 안 파일 이름이어야 함' % name
    if os.path.splitext(path)[1].lower() not in EXTENSIONS:
        return '%s: 허용 확장자는 .sh·.py·.js' % name
    harness = entry.get('harness')
    if not isinstance(harness, list) or not harness or any(h not in HARNESSES for h in harness):
        return '%s: harness는 be·fe만' % name
    for key in ('description', 'usage'):
        if not _text_ok(entry.get(key)):
            return '%s: %s는 200자 이하 문자열(제어문자 없음)' % (name, key)
    target = folder / path
    try:
        info = _regular(target)
    except ValueError as exc:
        return '%s: %s' % (name, exc)
    if info is None:
        return '%s: 스크립트 파일 없음' % name
    if not store.inside(os.path.realpath(target), os.path.realpath(folder)):
        return '%s: 스크립트가 폴더 밖을 가리킴' % name
    if store.is_loose(info):
        return '%s: 다른 사용자가 쓸 수 있는 스크립트' % name
    return None


def _folder_entries(folder, label, warnings):
    """한 폴더의 유효 항목. 없음은 조용히, 신뢰·형식 실패는 경고 후 생략."""
    info = store.lstat_or_none(folder)
    if info is None:
        return []
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        warnings.append('%s: symlink이거나 폴더가 아니라 생략' % label)
        return []
    if store.is_loose(info):
        warnings.append('%s: 다른 사용자가 쓸 수 있는 폴더라 생략' % label)
        return []
    if store.is_plugin_source(folder):
        warnings.append('%s: 플러그인 소스 폴더라 생략' % label)
        return []
    manifest = folder / MANIFEST
    try:
        manifest_info = _regular(manifest)
        if manifest_info is None:
            return []
        if store.is_loose(manifest_info):
            raise ValueError('다른 사용자가 쓸 수 있는 manifest')
        data = _read_json(manifest)
    except (OSError, ValueError) as exc:
        warnings.append('%s/%s 생략: %s' % (label, MANIFEST, exc))
        return []
    if not _valid_manifest(data):
        warnings.append('%s/%s 생략: version 1과 scripts 배열이 필요함' % (label, MANIFEST))
        return []
    entries, seen = [], {}
    for entry in data['scripts']:
        problem = _entry_problem(folder, entry)
        if problem:
            warnings.append('%s 항목 생략: %s' % (label, problem))
            continue
        seen[entry['name']] = seen.get(entry['name'], 0) + 1
        entries.append(entry)
    for name in [n for n, count in seen.items() if count > 1]:
        warnings.append('%s: 같은 name %s가 여러 번 있어 제외' % (label, name))
    return [e for e in entries if seen[e['name']] == 1]


def _collect(cwd, env=None, home=None):
    ctx = store.Context(cwd, env, home)
    warnings = ctx.warnings
    root = ctx.function_root
    if not root.exists():
        return {}, warnings
    if ctx.tree.contains(root):
        warnings.append('function root가 현재 저장소 working tree 안이라 쓰지 않음')
        return {}, warnings
    folders = [(SHARED, root / SHARED)]
    try:
        project = ctx.project()[0]
        folders.append((project, root / project))
    except ConfigError as exc:
        warnings.append('project를 정하지 못해 _shared만 씀: %s' % exc)
    found = {}
    for label, folder in folders:
        for entry in _folder_entries(folder, label, warnings):
            found.setdefault(entry['name'], []).append((label, folder, entry))
    result = {}
    for name, items in found.items():
        if len(items) > 1:
            warnings.append('name 충돌로 제외: %s (%s)' % (name, ', '.join(label for label, _, _ in items)))
            continue
        result[name] = items[0]
    return result, warnings


def list_scripts(cwd, harness, env=None, home=None):
    if harness not in HARNESSES:
        raise ConfigError('--harness는 be 또는 fe')
    found, warnings = _collect(cwd, env, home)
    scripts = []
    for name in sorted(found):
        label, folder, entry = found[name]
        if harness in entry['harness']:
            scripts.append({'name': name, 'path': str((folder / entry['path']).resolve()),
                            'description': entry['description'], 'usage': entry['usage'],
                            'source': 'shared' if label == SHARED else 'project'})
    return {'scripts': scripts, 'warnings': warnings}


def _find_bash():
    if os.name != 'nt':
        return shutil.which('bash')
    # Why: Windows System32의 bash.exe는 WSL 진입점이라 Git Bash와 경로·환경이 다르다.
    system = os.path.normcase(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32'))
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        if folder and os.path.normcase(os.path.abspath(folder)) != system:
            found = shutil.which('bash', path=folder)
            if found:
                return found
    return None


def _interpreter(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.py':
        return sys.executable
    found = _find_bash() if ext == '.sh' else shutil.which('node') if ext == '.js' else None
    if not found:
        raise ConfigError('실행기를 찾을 수 없음: %s' % ext)
    return found


def _kill_tree(proc):
    if os.name == 'nt':
        taskkill = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'taskkill.exe')
        subprocess.run([taskkill, '/T', '/F', '/PID', str(proc.pid)], capture_output=True, timeout=30)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def run_script(cwd, harness, name, args=(), timeout=None, env=None, home=None):
    listed = list_scripts(cwd, harness, env, home)
    match = [item for item in listed['scripts'] if item['name'] == name]
    if not match:
        raise ConfigError('실행할 수 있는 function이 없음: %s' % name)
    path = match[0]['path']
    command = [_interpreter(path), path, *[str(a) for a in args]]
    options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen(command, cwd=str(Path(cwd).resolve()), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, **options)
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout or DEFAULT_TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = b'', b''
    return {'exitCode': proc.returncode, 'stdout': (out or b'').decode('utf-8', 'replace'),
            'stderr': (err or b'').decode('utf-8', 'replace'), 'timedOut': timed_out,
            'warnings': listed['warnings']}


def _harness_list(value):
    items = [part.strip() for part in str(value).split(',') if part.strip()]
    if not items or any(item not in HARNESSES for item in items):
        raise ConfigError('--harness는 be, fe, be,fe 중 하나')
    return list(dict.fromkeys(items))


def _load_manifest(manifest):
    if _regular(manifest) is None:
        return None
    data = _read_json(manifest)
    if not _valid_manifest(data):
        raise ConfigError('기존 manifest가 version 1 형식이 아니라 수정하지 않음')
    return data


class _Lock:
    def __init__(self, folder):
        self.path = folder / '.manifest.lock'

    def __enter__(self):
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise ConfigError('manifest 잠금을 얻지 못함: %s' % self.path) from None
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            os.unlink(self.path)
        except OSError:
            pass


def _write_manifest(folder, data):
    temp = folder / ('.manifest-%s.tmp' % secrets.token_hex(8))
    store.create_exclusive(temp, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    try:
        for attempt in range(2):
            try:
                os.replace(temp, folder / MANIFEST)
                return
            except PermissionError:
                # Why: Windows는 다른 프로세스가 대상 파일을 열고 있으면 replace를 잠시 거부한다.
                if attempt:
                    raise
                time.sleep(0.2)
    finally:
        if temp.exists():
            os.unlink(temp)


def add_script(cwd, src, name, description, harness, usage, env=None, home=None):
    if not isinstance(name, str) or not NAME.match(name):
        raise ConfigError('--name 형식: ^[a-z0-9][a-z0-9._-]{0,63}$')
    if not _text_ok(description) or not _text_ok(usage):
        raise ConfigError('--description·--usage는 200자 이하, 제어문자 없음')
    harness = _harness_list(harness)
    src = Path(os.path.abspath(src))
    if src.suffix.lower() not in EXTENSIONS:
        raise ConfigError('--src 확장자는 .sh·.py·.js')
    try:
        info = _regular(src)
    except ValueError as exc:
        raise ConfigError(str(exc)) from None
    if info is None:
        raise ConfigError('--src 파일이 없음')
    if info.st_size > SOURCE_LIMIT:
        raise ConfigError('--src가 1 MiB를 넘음')
    body = src.read_bytes()
    ctx = store.Context(cwd, env, home)
    project = ctx.project()[0]
    root = ctx.function_root
    if ctx.tree.contains(root):
        raise ConfigError('function root가 현재 저장소 working tree 안이라 저장하지 않음')
    store.ensure_base(root)
    folder = store.ensure_dir(root / project, ctx.warnings, strict=True)
    store.reject_plugin_source(folder)
    manifest = folder / MANIFEST
    if os.path.lexists(folder / src.name):
        raise ConfigError('같은 이름의 파일이 이미 있음: %s' % src.name)
    target = store.publish(folder, src.name, body, numbered=False, mode=0o700)
    try:
        with _Lock(folder):
            data = _load_manifest(manifest) or {'version': 1, 'scripts': []}
            if any(isinstance(e, dict) and e.get('name') == name for e in data['scripts']):
                raise ConfigError('같은 name이 이미 있음: %s' % name)
            data['scripts'].append({'name': name, 'path': src.name, 'description': description,
                                    'harness': harness, 'usage': usage})
            _write_manifest(folder, data)
    except BaseException:
        os.unlink(target)
        raise
    return {'name': name, 'path': str(target.resolve()), 'manifest': str(manifest.resolve()),
            'warnings': ctx.warnings}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({'error': message}, ensure_ascii=False))
        sys.exit(2)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = []
    if '--' in argv:
        index = argv.index('--')
        argv, rest = argv[:index], argv[index + 1:]
    parser = _Parser(description=__doc__)
    parser.add_argument('action', choices=('list', 'run', 'add'))
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--harness', required=True)
    parser.add_argument('--name')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--src')
    parser.add_argument('--description')
    parser.add_argument('--usage')
    args = parser.parse_args(argv)
    if rest and args.action != 'run':
        parser.error('`--` 뒤 인자는 run에만 씀')
    try:
        cwd = Path(args.cwd).resolve()
        if not cwd.is_dir():
            raise ConfigError('--cwd는 있는 폴더여야 함')
        if args.action == 'list':
            result = list_scripts(cwd, args.harness)
        elif args.action == 'run':
            if not args.name:
                parser.error('run은 --name이 필요함')
            result = run_script(cwd, args.harness, args.name, rest, args.timeout)
        else:
            missing = [flag for flag, value in (('--src', args.src), ('--name', args.name),
                                                ('--description', args.description), ('--usage', args.usage)) if value is None]
            if missing:
                parser.error('add에 필요한 인자 없음: ' + ', '.join(missing))
            result = add_script(cwd, args.src, args.name, args.description, args.harness, args.usage)
    except (ConfigError, OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
