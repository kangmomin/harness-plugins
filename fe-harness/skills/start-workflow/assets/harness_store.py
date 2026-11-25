#!/usr/bin/env python3
"""harness-plugin 공통 폴더 경로 규칙과 문서 저장 helper.

resolve    --cwd C [--ensure]
report-dir --cwd C --domain be|fe
save-doc   --cwd C --name F [--prefer P]   (본문 stdin)
find-docs  --cwd C --contains S
JSON 출력. 0 성공 / 1 실패 / 2 입력 오류.

경로 규칙: base = $HARNESS_PLUGIN_HOME → ~/.harness-plugin, doc root = $WORK_LOG_ROOT → <base>/work-log/docs,
function root = $HARNESS_FUNCTION_DIR → <base>/function. env는 trim 후 절대경로일 때만 쓴다.
be-harness 정본, fe·common·minmos는 동일 사본(check_contracts.py parity).
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata


class ConfigError(ValueError):
    """경로·설정·git 오류를 한 종류로 묶는다."""


# Why: profile.py에서 복사한 파서 코드가 같은 예외 이름을 쓰게 한다.
ProfileError = ConfigError

WIN_ABS = re.compile(r'^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/?.])')
WIN_ROOT_RELATIVE = re.compile(r'^(?:[A-Za-z]:|[\\/])')
RESERVED = re.compile(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$', re.I)
EXCLUDED_NAMES = {'node_modules', '.harness-runs', '_shared'}
NOT_A_REPO = re.compile(r'not a git repository \(or any')
DOC_EXTENSIONS = ('.md', '.html')
RUNS_DIR = '.harness-runs'
MAX_SUFFIX = 99


def is_abs_strict(value, platform=None):
    """실행 플랫폼 기준 절대경로 판정. Windows는 드라이브·UNC만, POSIX는 `/`만."""
    if platform is None:
        platform = 'win' if os.name == 'nt' else 'posix'
    if not isinstance(value, str):
        return False
    value = value.strip()
    if platform == 'win':
        return bool(WIN_ABS.match(value))
    return value.startswith('/')


def slug(name):
    text = unicodedata.normalize('NFC', str(name))
    text = ''.join(c if c.isalnum() or c in '._-' else '-' for c in text)
    text = text.lstrip('.')[:64].rstrip('. ')
    if text in ('', '.', '..'):
        raise ConfigError('프로젝트 이름을 만들 수 없음: 빈 이름')
    if RESERVED.match(text) or text.lower() in EXCLUDED_NAMES:
        text += '-project'
    return text


def remote_project_name(url):
    """remote URL의 마지막 경로 조각(끝 `.git` 제거). URL 원본은 어디에도 출력하지 않는다."""
    parts = [part for part in re.split(r'[/\\:]', (url or '').strip()) if part]
    if not parts:
        return None
    name = parts[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name or None


def _env(env):
    return dict(os.environ) if env is None else dict(env)


def _home(home):
    return Path(home) if home is not None else Path.home()


def _env_path(env, name, warnings):
    raw = env.get(name)
    if raw is None or not raw.strip():
        return None
    if not is_abs_strict(raw):
        warnings.append('%s 무시: 절대경로가 아님' % name)
        return None
    return Path(raw.strip()).resolve()


def _git(cwd, args, env):
    executable = shutil.which('git', path=env.get('PATH', os.defpath))
    if not executable:
        raise ConfigError('git 실행 파일을 찾을 수 없음')
    git_env = {k: v for k, v in env.items() if not k.upper().startswith('GIT_')}
    git_env.update(LC_ALL='C', LANGUAGE='C')
    try:
        return subprocess.run([executable, '-C', str(cwd), *args], env=git_env, capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError('git 실행 실패: %s' % exc.__class__.__name__) from None


def project_name(cwd, env=None):
    """(이름, 출처) — origin URL → git common-dir → git 아님이면 폴더 이름."""
    env = _env(env)
    origin = _git(cwd, ['config', '--get', 'remote.origin.url'], env)
    if origin.returncode == 0 and origin.stdout.strip():
        name = remote_project_name(origin.stdout.decode('utf-8', 'replace'))
        if name:
            try:
                return slug(name), 'origin'
            except ConfigError:
                pass
    common = _git(cwd, ['rev-parse', '--path-format=absolute', '--git-common-dir'], env)
    if common.returncode == 0 and common.stdout.strip():
        path = Path(common.stdout.decode('utf-8', 'surrogateescape').rstrip('\r\n'))
        name = path.parent.name if path.name == '.git' else path.name
        if name.endswith('.git'):
            name = name[:-4]
        return slug(name), 'common-dir'
    error = common.stderr.decode('utf-8', 'replace')
    if common.returncode == 128 and NOT_A_REPO.search(error):
        return slug(Path(cwd).resolve().name), 'dir'
    if 'dubious ownership' in error:
        raise ConfigError('git이 저장소 소유자를 신뢰하지 않음 — `git config --global --add safe.directory <저장소 경로>` 후 다시 실행')
    first = error.strip().splitlines()[0] if error.strip() else 'exit %d' % common.returncode
    raise ConfigError('git 저장소 정보를 읽지 못함: %s' % first)


def is_plugin_source(path):
    """work-log config.js isPluginSource와 같은 4조건."""
    path = Path(path)
    return ((path / '.claude-plugin').exists() or (path / '.codex-plugin').exists()
            or (path / 'mcp' / 'server.js').exists()
            or ((path / 'skills').exists() and (path / '.mcp.json').exists()))


def _inside(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


class _Tree:
    """현재 저장소 working tree 위치. 조회 실패는 경고 생략으로만 다룬다."""

    def __init__(self, cwd, env):
        self.cwd, self.env, self._top, self._done = cwd, env, None, False

    def top(self):
        if not self._done:
            self._done = True
            try:
                result = _git(self.cwd, ['rev-parse', '--show-toplevel'], self.env)
                if result.returncode == 0 and result.stdout.strip():
                    self._top = Path(result.stdout.decode('utf-8', 'surrogateescape').rstrip('\r\n')).resolve()
            except ConfigError:
                self._top = None
        return self._top

    def contains(self, path):
        top = self.top()
        return top is not None and _inside(path, top)


def _loose(info):
    if os.name == 'nt':
        return False
    return info.st_uid != os.getuid() or bool(info.st_mode & 0o022)


def _ensure_dir(path, warnings, strict=False, create=True):
    """helper가 쓰는 폴더 1단계를 만들거나(0700) 검사한다. symlink·폴더 아님은 거부."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise ConfigError('폴더를 확인할 수 없음: %s (%s)' % (path, exc.strerror)) from None
    if info is None:
        if not create:
            raise ConfigError('폴더가 없음: %s' % path)
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            return _ensure_dir(path, warnings, strict, create=False)
        except OSError as exc:
            raise ConfigError('폴더를 만들 수 없음: %s (%s)' % (path, exc.strerror)) from None
        if os.name != 'nt':
            os.chmod(path, 0o700)
        return path
    if stat.S_ISLNK(info.st_mode):
        raise ConfigError('symlink 폴더는 쓰지 않음: %s' % path)
    if not stat.S_ISDIR(info.st_mode):
        raise ConfigError('폴더가 아님: %s' % path)
    if _loose(info):
        if strict:
            raise ConfigError('다른 사용자가 쓸 수 있는 폴더는 쓰지 않음: %s' % path)
        warnings.append('다른 사용자가 쓸 수 있는 폴더: %s' % path)
    return path


def _ensure_chain(top, parts, warnings, strict=False):
    """이미 있는 top 아래로 parts를 1단계씩 만든다(각 단계 symlink 거부)."""
    current = Path(top)
    for part in parts:
        current = _ensure_dir(current / part, warnings, strict)
    return current


def _ensure_base(base):
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ConfigError('base 폴더를 만들 수 없음: %s (%s)' % (base, exc.strerror)) from None
    if not base.is_dir():
        raise ConfigError('base가 폴더가 아님: %s' % base)


def _reject_plugin_source(path):
    if is_plugin_source(path):
        raise ConfigError('플러그인 소스 폴더에는 쓰지 않음: %s' % path)


class _Context:
    """한 호출의 경로 계산. project·git은 필요할 때만 계산한다."""

    def __init__(self, cwd, env=None, home=None):
        self.cwd = Path(cwd).resolve()
        self.env = _env(env)
        self.home = _home(home)
        self.warnings = []
        base = _env_path(self.env, 'HARNESS_PLUGIN_HOME', self.warnings)
        self.base = base or (self.home / '.harness-plugin').resolve()
        root = _env_path(self.env, 'WORK_LOG_ROOT', self.warnings)
        self.doc_root_source = 'env:WORK_LOG_ROOT' if root else 'default'
        self.doc_root = root or self.base / 'work-log' / 'docs'
        function_root = _env_path(self.env, 'HARNESS_FUNCTION_DIR', self.warnings)
        self.function_root_source = 'env:HARNESS_FUNCTION_DIR' if function_root else 'default'
        self.function_root = function_root or self.base / 'function'
        self.tree = _Tree(self.cwd, self.env)
        self._project = None

    def project(self):
        if self._project is None:
            self._project = project_name(self.cwd, self.env)
        return self._project

    def check_doc_root(self):
        if self.doc_root_source == 'default':
            return
        if not self.doc_root.is_dir():
            raise ConfigError('WORK_LOG_ROOT 폴더가 없음: %s' % self.doc_root)
        _reject_plugin_source(self.doc_root)

    def ensure_doc_root(self):
        """doc root를 쓸 준비. 기본 위치면 base부터 만든다. 다른 위치로 대체하지 않는다."""
        self.check_doc_root()
        if self.doc_root_source == 'default':
            _ensure_base(self.base)
            _ensure_chain(self.base, ('work-log', 'docs'), self.warnings)
        return self.doc_root

    def ensure_doc_dir(self):
        name = self.project()[0]
        doc_root = self.ensure_doc_root()
        doc_dir = _ensure_dir(doc_root / name, self.warnings)
        if not _inside(doc_dir, doc_root):
            raise ConfigError('문서 폴더가 doc root 밖을 가리킴: %s' % doc_dir)
        _reject_plugin_source(doc_dir)
        if self.tree.contains(doc_dir):
            self.warnings.append('문서 폴더가 현재 저장소 working tree 안에 있음: %s' % doc_dir.resolve())
        return doc_dir


def resolve(cwd, env=None, home=None, ensure=False):
    ctx = _Context(cwd, env, home)
    ctx.check_doc_root()
    name, source = ctx.project()
    doc_dir = ctx.ensure_doc_dir() if ensure else ctx.doc_root / name
    return {
        'base': str(ctx.base), 'docRoot': str(Path(ctx.doc_root).resolve()), 'docRootSource': ctx.doc_root_source,
        'project': name, 'projectSource': source, 'docDir': str(Path(doc_dir).resolve()),
        'functionRoot': str(Path(ctx.function_root).resolve()), 'functionRootSource': ctx.function_root_source,
        'feedbackRoot': str(ctx.base / 'feedback-submissions' / name), 'warnings': ctx.warnings,
    }


# ---- profile reportDir 파서: profile.py의 DELIM·ROOT·scalar·lex·Document·validate(string)를 그대로 복사 ----
ROOT = re.compile(r"^([A-Za-z0-9_-]+):(?=\s|$)")
DELIM = re.compile(r"^---[ \t]*$")


def scalar(value):
    if not value or value.lower() in ("null", "~"):
        return None
    if value.startswith('"'):
        try:
            result = json.loads(value)
        except ValueError as exc:
            raise ProfileError("UNSUPPORTED_LAYOUT: double-quoted scalar (JSON escapes only)") from exc
        if not isinstance(result, str):
            raise ProfileError("UNSUPPORTED_LAYOUT: scalar")
        return result
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ProfileError("UNSUPPORTED_LAYOUT: single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"[-+]?(?:\d[\d_]*(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", value):
        return float(value.replace("_", ""))
    if value[0] in "|>&*!%@`[{" or re.search(r":(?:\s|$)", value) or re.match(r"[-?:](?:\s|$)", value):
        raise ProfileError("UNSUPPORTED_LAYOUT: scalar")
    # YAML 1.1 booleans/dates/hex differ between consumers. Require quoting them.
    if value.lower() in ("yes", "no", "on", "off", ".nan", ".inf", "-.inf", "+.inf") or re.match(r"[-+]?0[xob]|\d{4}-\d\d-\d\d", value, re.I):
        raise ProfileError("UNSUPPORTED_LAYOUT: ambiguous YAML scalar; quote it")
    return value


def lex(line, prefix):
    """Return unchanged prefix/separator, scalar lexeme, suffix/comment, EOL."""
    eol = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    text = line[:-len(eol)] if eol else line
    rest = text[len(prefix):]
    quote, comment, i, node_start, depth = None, len(rest), 0, True, 0
    while i < len(rest):
        c = rest[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                if quote == "'" and i + 1 < len(rest) and rest[i + 1] == "'":
                    i += 1
                else:
                    quote = None
        elif c in "\"'" and node_start:
            quote = c
            node_start = False
        elif c == "#" and (i == 0 or rest[i - 1].isspace()):
            comment = i
            break
        elif c in "[{" and node_start:
            depth += 1
            node_start = True
        elif depth and c in "]}":
            depth -= 1
            node_start = False
        elif depth and (c == "," or c == ":" and i + 1 < len(rest) and rest[i + 1].isspace()):
            node_start = True
        elif not c.isspace():
            node_start = False
        i += 1
    content = rest[:comment]
    left = len(content) - len(content.lstrip(" \t"))
    value = content.strip(" \t")
    if value:
        return prefix + content[:left], value, content[left + len(value):] + rest[comment:], eol
    return prefix, "", rest, eol


def validate(key, value):
    """profile.py validate()의 string 분기."""
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ProfileError("INVALID_VALUE: " + key)


class Document:
    def __init__(self, data):
        self.lines = re.findall(r"[^\n]*\n|[^\n]+$", data.decode("utf-8"))
        if not self.lines or not self.lines[0].endswith("\n") or not DELIM.fullmatch(self.lines[0].rstrip("\r\n")):
            raise ProfileError("INVALID_PROFILE: opening delimiter")
        self.end = next((i for i in range(1, len(self.lines)) if DELIM.fullmatch(self.lines[i].rstrip("\r\n"))), None)
        if self.end is None:
            raise ProfileError("INVALID_PROFILE: closing delimiter")
        self.roots, self.placeholders = {}, {}
        for i in range(1, self.end):
            line = self.lines[i]
            root = ROOT.match(line)
            if root:
                if root[1] in self.roots:
                    raise ProfileError("DUPLICATE_KEY: " + root[1])
                self.roots[root[1]] = i
            elif line.startswith("# ") and ROOT.match(line[2:]):
                self.placeholders.setdefault(ROOT.match(line[2:])[1], i)
            elif line.strip() and not line.lstrip().startswith("#") and not self.roots:
                raise ProfileError("UNSUPPORTED_LAYOUT: orphan child line " + str(i + 1))
            elif line.strip() and not line.startswith((" ", "\t", "#")):
                raise ProfileError("UNSUPPORTED_LAYOUT: root line " + str(i + 1))

    def block(self, key):
        placeholder = key not in self.roots
        i = self.placeholders.get(key) if placeholder else self.roots[key]
        if i is None:
            return None
        line = self.lines[i][2:] if placeholder else self.lines[i]
        parts = lex(line, key + ":")
        children, gap = [], False
        if not placeholder:
            stop = min([v for v in self.roots.values() if v > i] + [self.end])
            for j in range(i + 1, stop):
                child = self.lines[j]
                if not child.strip() or child.lstrip().startswith("#"):
                    gap = True
                elif child.startswith((" ", "\t")):
                    if gap or child.startswith("\t"):
                        raise ProfileError("UNSUPPORTED_LAYOUT: separated children: " + key)
                    children.append(j)
                else:
                    raise ProfileError("UNSUPPORTED_LAYOUT: " + key)
        return i, parts, children, placeholder

    def value(self, key):
        """profile.py Document.value()의 scalar 경로."""
        block = self.block(key)
        if block is None:
            return None
        _, parts, children, _ = block
        raw = parts[1]
        if children:
            raise ProfileError("UNSUPPORTED_LAYOUT: scalar children " + key)
        return scalar(raw)
# ---- 복사 끝 ----


def profile_report_dir(cwd, domain):
    """`.claude/{domain}-harness.local.md` frontmatter의 root 키 reportDir. 파일·키 없음 = ''."""
    if domain not in ('be', 'fe'):
        raise ConfigError('domain은 be 또는 fe')
    path = Path(cwd) / '.claude' / (domain + '-harness.local.md')
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        if path.is_symlink():
            raise ConfigError('%s: reportDir 읽기 실패 — 끊긴 symlink' % path) from None
        return ''
    except OSError as exc:
        raise ConfigError('%s: reportDir 읽기 실패 — %s' % (path, exc.strerror or exc.__class__.__name__)) from None
    try:
        doc = Document(data)
        if 'reportDir' not in doc.roots:
            return ''
        value = doc.value('reportDir')
        validate('reportDir', value)
    except ValueError as exc:
        raise ConfigError('%s: reportDir 읽기 실패 — %s' % (path, exc)) from None
    return value


def _report_path(value, cwd, home):
    """profile reportDir 값을 절대경로로. ~ 확장 → 절대 → (Windows 드라이브·루트 상대 거부) → cwd 기준."""
    text = value.strip()
    if text == '~' or text.startswith('~/') or (os.name == 'nt' and text.startswith('~\\')):
        path = Path(home) / text[2:]
    elif is_abs_strict(text):
        path = Path(text)
    elif os.name == 'nt' and WIN_ROOT_RELATIVE.match(text):
        raise ConfigError('reportDir에 드라이브·루트 상대 경로는 쓸 수 없음: %s' % text)
    else:
        path = Path(cwd) / text
    return Path(os.path.abspath(path))


def report_location(cwd, value):
    """기록 없는 옛 run의 REPORT_DIR — 만들지 않고 계산만 한다."""
    if value:
        return str(_report_path(value, Path(cwd).resolve(), Path.home()).resolve())
    return str((Path(cwd).resolve() / '.claude' / 'harness-reports').resolve())


def _mkdtemp(prefix, parent=None):
    try:
        return Path(tempfile.mkdtemp(prefix=prefix, dir=None if parent is None else str(parent))).resolve()
    except OSError as exc:
        raise ConfigError('run 폴더를 만들 수 없음: %s' % (exc.strerror or exc)) from None


def run_location(cwd, value, env=None, home=None, prefix='harness-run-'):
    """REPORT_DIR·RUN_DIR을 정하고 만든다. value가 비면 doc root 기본 위치, 아니면 그 값 + 시스템 temp."""
    ctx = _Context(cwd, env, home)
    if value:
        report = _report_path(value, ctx.cwd, ctx.home)
        _reject_plugin_source(report)
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigError('REPORT_DIR 상위 폴더를 만들 수 없음: %s (%s)' % (report.parent, exc.strerror)) from None
        _ensure_dir(report, ctx.warnings)
        run_dir, source = _mkdtemp(prefix), 'profile'
    else:
        name = ctx.project()[0]
        doc_root = ctx.ensure_doc_root()
        report = _ensure_dir(doc_root / name, ctx.warnings)
        _reject_plugin_source(report)
        runs = doc_root / RUNS_DIR / name
        if ctx.tree.contains(runs):
            ctx.warnings.append('RUN_DIR 기본 위치가 working tree 안이라 시스템 temp를 씀: %s' % runs.resolve())
            run_dir = _mkdtemp(prefix)
        else:
            parent = _ensure_chain(doc_root, (RUNS_DIR, name), ctx.warnings)
            _reject_plugin_source(doc_root / RUNS_DIR)
            _reject_plugin_source(parent)
            run_dir = _mkdtemp(prefix, parent)
        source = 'default'
    if ctx.tree.contains(report):
        ctx.warnings.append('REPORT_DIR이 현재 저장소 working tree 안에 있음: %s' % report.resolve())
    return {'reportDir': str(report.resolve()), 'runDir': str(run_dir), 'source': source, 'warnings': ctx.warnings}


def report_dir(cwd, domain, env=None, home=None):
    return run_location(cwd, profile_report_dir(cwd, domain), env, home, prefix='harness-e2e-')


def feedback_dir(cwd, plugin, env=None, home=None):
    """`<base>/feedback-submissions/<project>/<plugin>` — 0700, symlink·느슨한 권한·플러그인 소스 거부."""
    if not isinstance(plugin, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', plugin):
        raise ConfigError('plugin 이름이 한 경로 조각이 아님')
    ctx = _Context(cwd, env, home)
    name = ctx.project()[0]
    _ensure_base(ctx.base)
    folder = _ensure_chain(ctx.base, ('feedback-submissions', name, plugin), ctx.warnings, strict=True)
    _reject_plugin_source(folder)
    return folder


def _check_name(name):
    if not isinstance(name, str) or not name or name != os.path.basename(name) or '/' in name or '\\' in name:
        raise ConfigError('--name은 폴더 없는 파일 이름이어야 함')
    if any(ord(c) < 32 or ord(c) == 127 for c in name) or name != name.rstrip('. '):
        raise ConfigError('--name에 제어문자 또는 끝 점·공백이 있음')
    if os.path.splitext(name)[1].lower() not in DOC_EXTENSIONS:
        raise ConfigError('--name 확장자는 .md 또는 .html')
    if len(name.encode('utf-8')) > 200:
        raise ConfigError('--name이 200바이트를 넘음')
    if RESERVED.match(name):
        raise ConfigError('--name이 예약 이름임')
    if re.search(r'-(?:workflow|e2e)-report', name, re.I):
        raise ConfigError('리포트 이름은 save-doc으로 저장하지 않음')


def _lstat(path):
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ConfigError('경로를 확인할 수 없음: %s (%s)' % (path, exc.strerror)) from None


def _write_all(fd, data):
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _create_exclusive(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), mode)
    try:
        _write_all(fd, data)
    except BaseException:
        os.unlink(path)
        raise
    return path


def publish(folder, name, data, numbered=True, mode=0o600):
    """덮어쓰지 않고 게시한다. 임시 파일 → os.link, link 불가면 O_EXCL 직접 쓰기. 같은 이름이면 -2..-99."""
    folder = Path(folder)
    stem, ext = os.path.splitext(name)
    names = [name] + (['%s-%d%s' % (stem, i, ext) for i in range(2, MAX_SUFFIX + 1)] if numbered else [])
    temp = folder / ('.hs-%s.tmp' % secrets.token_hex(8))
    try:
        _create_exclusive(temp, data, mode)
    except OSError as exc:
        raise ConfigError('임시 파일을 만들 수 없음: %s (%s)' % (folder, exc.strerror)) from None
    linkable = True
    try:
        for candidate in names:
            target = folder / candidate
            if linkable:
                try:
                    os.link(temp, target)
                    return target
                except FileExistsError:
                    continue
                except OSError:
                    linkable = False
            try:
                return _create_exclusive(target, data, mode)
            except FileExistsError:
                continue
            except OSError as exc:
                raise ConfigError('파일을 쓸 수 없음: %s (%s)' % (target, exc.strerror)) from None
        if numbered:
            raise ConfigError('같은 이름의 파일이 너무 많음: %s' % name)
        raise ConfigError('파일이 이미 있음: %s' % (folder / name))
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _prefer_target(cwd, prefer):
    """--prefer: `.md`로 끝나면 그 파일(있으면 오류), 아니면 있는 폴더. symlink·플러그인 소스 거부."""
    path = Path(prefer)
    path = Path(os.path.abspath(path if is_abs_strict(str(prefer)) else Path(cwd) / path))
    if path.name.lower().endswith('.md'):
        folder, name = path.parent, path.name
    else:
        folder, name = path, None
    info = _lstat(folder)
    if info is None:
        raise ConfigError('--prefer 폴더가 없음: %s' % folder)
    if stat.S_ISLNK(info.st_mode):
        raise ConfigError('--prefer에 symlink 폴더는 쓰지 않음: %s' % folder)
    if not stat.S_ISDIR(info.st_mode):
        raise ConfigError('--prefer가 폴더가 아님: %s' % folder)
    _reject_plugin_source(folder)
    if name is not None:
        if any(ord(c) < 32 for c in name):
            raise ConfigError('--prefer 파일 이름에 제어문자가 있음')
        if _lstat(path) is not None:
            raise ConfigError('--prefer 파일이 이미 있음: %s' % path)
    return folder, name


def save_doc(cwd, name, body, prefer=None, env=None, home=None):
    data = body.encode('utf-8') if isinstance(body, str) else bytes(body)
    if not data.strip():
        raise ConfigError('본문이 비어 있음')
    ctx = _Context(cwd, env, home)
    if prefer:
        folder, fixed = _prefer_target(ctx.cwd, prefer)
        if fixed is None:
            _check_name(name)
            path = publish(folder, name, data)
        else:
            path = publish(folder, fixed, data, numbered=False)
    else:
        _check_name(name)
        ctx.check_doc_root()
        folder = ctx.ensure_doc_dir()
        path = publish(folder, name, data)
    return {'path': str(Path(path).resolve()), 'needsSync': True, 'warnings': ctx.warnings}


def find_docs(cwd, contains, env=None, home=None):
    ctx = _Context(cwd, env, home)
    ctx.check_doc_root()
    doc_dir = ctx.doc_root / ctx.project()[0]
    needle = unicodedata.normalize('NFC', contains or '')
    info = _lstat(doc_dir)
    files = []
    if info is not None and stat.S_ISDIR(info.st_mode):
        for entry in sorted(os.scandir(doc_dir), key=lambda e: e.name):
            if entry.is_file(follow_symlinks=False) and needle in unicodedata.normalize('NFC', entry.name):
                files.append(str(Path(entry.path).resolve()))
    return {'docDir': str(Path(doc_dir).resolve()), 'files': files, 'warnings': ctx.warnings}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({'error': message}, ensure_ascii=False))
        sys.exit(2)


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument('action', choices=('resolve', 'report-dir', 'save-doc', 'find-docs'))
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--ensure', action='store_true')
    parser.add_argument('--domain', choices=('be', 'fe'))
    parser.add_argument('--name')
    parser.add_argument('--prefer')
    parser.add_argument('--contains')
    args = parser.parse_args(argv)
    try:
        cwd = Path(args.cwd).resolve()
        if not cwd.is_dir():
            raise ConfigError('--cwd는 있는 폴더여야 함: %s' % cwd)
        if args.action == 'resolve':
            result = resolve(cwd, ensure=args.ensure)
        elif args.action == 'report-dir':
            if not args.domain:
                parser.error('report-dir는 --domain이 필요함')
            result = report_dir(cwd, args.domain)
        elif args.action == 'save-doc':
            if not args.name:
                parser.error('save-doc는 --name이 필요함')
            result = save_doc(cwd, args.name, sys.stdin.buffer.read(), prefer=args.prefer)
        else:
            if args.contains is None:
                parser.error('find-docs는 --contains가 필요함')
            result = find_docs(cwd, args.contains)
    except (ConfigError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
