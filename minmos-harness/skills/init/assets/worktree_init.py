#!/usr/bin/env python3
"""Install a preserving SessionStart hook; copy only approved ignored worktree files.

Linux/macOS Python3.9+. No global settings writes unless install is explicitly run.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import uuid
sys.dont_write_bytecode = True
from hook_metadata import Metadata

FILES = ('.mcp.json', '.env', 'secret/.env', 'secret/gcp-sa-key.json')
BUNDLE_FILES = ('worktree_init.py', 'hook_metadata.py')


class Blocked(ValueError):
    pass


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Blocked('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def load_json(data):
    result = json.loads(data, object_pairs_hook=strict_object)
    if not isinstance(result, dict):
        raise Blocked('JSON_OBJECT_REQUIRED')
    return result


def stamp(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode, st.st_uid, st.st_gid)


class Anchor:
    def __init__(self, path, stack, create=False):
        self.path = Path(os.path.abspath(path))
        self.chain = []
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, fd)
        for part in self.path.parent.parts[1:]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                self.check()
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, child)
            st = os.fstat(child)
            self.chain.append((fd, part, (st.st_dev, st.st_ino)))
            fd = child
        self.fd, self.name = fd, self.path.name
        self.check()

    def check(self):
        for fd, name, expected in self.chain:
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != expected:
                raise Blocked('DIRECTORY_CHANGED')

    def current(self):
        try:
            return os.stat(self.name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return None


def read_at(anchor):
    with os.fdopen(os.open(anchor.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=anchor.fd), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Blocked('REGULAR_FILE_REQUIRED')
        content = stream.read()
        if stamp(os.fstat(stream.fileno())) != stamp(before):
            raise Blocked('SOURCE_CHANGED')
        anchor.check()
        current = anchor.current()
        if current is None or stamp(current) != stamp(before):
            raise Blocked('SOURCE_CHANGED')
        return content, before


def publish(anchor, content, expected=None, before_publish=None):
    """Exclusive first publish; hash/inode checked atomic replace for existing settings."""
    metadata = Metadata()
    name = '.minmos-' + uuid.uuid4().hex + '.tmp'
    temp_fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=anchor.fd)
    temp_identity = (os.fstat(temp_fd).st_dev, os.fstat(temp_fd).st_ino)
    published_ok = False
    verified = False
    warnings = []
    try:
        metadata.private(temp_fd)
        if expected is not None:
            source_fd = os.open(anchor.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=anchor.fd)
            try:
                if stamp(os.fstat(source_fd)) != stamp(expected):
                    raise Blocked('SETTINGS_CHANGED')
                metadata.copy(source_fd, temp_fd)
            finally:
                os.close(source_fd)
        with os.fdopen(os.dup(temp_fd), 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if before_publish:
            before_publish()
        anchor.check()
        temp_stat = os.stat(name, dir_fd=anchor.fd, follow_symlinks=False)
        if (not stat.S_ISREG(temp_stat.st_mode) or (temp_stat.st_dev, temp_stat.st_ino) != temp_identity
                or temp_stat.st_size != len(content) or os.pread(temp_fd, len(content) + 1, 0) != content):
            raise Blocked('TEMP_CHANGED')
        current = anchor.current()
        if expected is None:
            if current is not None:
                raise Blocked('DESTINATION_CREATED')
            os.link(name, anchor.name, src_dir_fd=anchor.fd, dst_dir_fd=anchor.fd, follow_symlinks=False)
        else:
            if current is None or stamp(current) != stamp(expected):
                raise Blocked('SETTINGS_CHANGED')
            os.replace(name, anchor.name, src_dir_fd=anchor.fd, dst_dir_fd=anchor.fd)
        published_ok = True
        try:
            os.fsync(anchor.fd)
            anchor.check()
            published = anchor.current()
            if published is None or (published.st_dev, published.st_ino) != temp_identity or read_at(anchor)[0] != content:
                raise Blocked('PUBLISHED_FILE_CHANGED')
            verified = True
        except (OSError, ValueError, RuntimeError) as exc:
            raise Blocked('UNKNOWN:PUBLISH: ' + str(exc)) from exc
    finally:
        try:
            os.close(temp_fd)
            try:
                current = os.stat(name, dir_fd=anchor.fd, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == temp_identity:
                    os.unlink(name, dir_fd=anchor.fd)
            except FileNotFoundError:
                pass
        except OSError as exc:
            if published_ok and verified:
                warnings.append(dict(path=str(anchor.path.parent / name), reason='TEMP_CLEANUP_FAILED'))
            elif published_ok:
                raise Blocked('UNKNOWN:PUBLISH_CLEANUP: ' + type(exc).__name__) from exc
            else:
                raise
    return warnings


def bundle_hash(contents):
    return hashlib.sha256(b''.join(name.encode() + b'\0' + contents[name] for name in BUNDLE_FILES)).hexdigest()


def ensure_bundle(hook_dir):
    contents = {name: (Path(__file__).parent / name).read_bytes() for name in BUNDLE_FILES}
    folder = hook_dir / ('minmos-worktree-init-' + bundle_hash(contents))
    created_files = []
    warnings = []
    with ExitStack() as stack:
        parent = Anchor(folder, stack, create=True)
        current = parent.current()
        created = current is None
        if created:
            os.mkdir(parent.name, 0o700, dir_fd=parent.fd)
        expected = parent.current()
        if not stat.S_ISDIR(expected.st_mode) or stat.S_IMODE(expected.st_mode) != 0o700 or expected.st_uid != os.geteuid():
            raise Blocked('HOOK_BUNDLE_OWNERSHIP')
        try:
            for name, content in contents.items():
                anchor = Anchor(folder / name, stack)
                if anchor.current() is None:
                    if not created:
                        raise Blocked('HOOK_BUNDLE_INCOMPLETE')
                    warnings.extend(publish(anchor, content))
                    created_files.append((anchor, stamp(anchor.current())))
                existing, _ = read_at(anchor)
                if existing != content:
                    raise Blocked('HOOK_BUNDLE_CONFLICT')
        except BaseException as exc:
            if created and 'UNKNOWN:PUBLISH' not in str(exc):
                for anchor, owned in created_files:
                    anchor.check()
                    current = anchor.current()
                    if current is not None and stamp(current) == owned:
                        os.unlink(anchor.name, dir_fd=anchor.fd)
                parent.check()
                current = parent.current()
                if current and (current.st_dev, current.st_ino) == (expected.st_dev, expected.st_ino):
                    os.rmdir(parent.name, dir_fd=parent.fd)
            raise
    return folder, created, warnings


def owned_command(command, hook_dir):
    try:
        args = shlex.split(command)
        if len(args) != 3 or args[0] != 'python3' or args[2] != 'hook':
            return False
        script = Path(args[1])
        if script.name != 'worktree_init.py' or script.parent.parent != hook_dir or not script.parent.name.startswith('minmos-worktree-init-'):
            return False
        content = {name: (script.parent / name).read_bytes() for name in BUNDLE_FILES}
        return script.parent.name == 'minmos-worktree-init-' + bundle_hash(content)
    except (OSError, ValueError):
        return False


def inspect_install(settings):
    settings = Path(os.path.abspath(settings))
    if not settings.exists():
        return dict(status='MISSING', reason='SETTINGS_MISSING')
    with ExitStack() as stack:
        anchor = Anchor(settings, stack)
        doc = load_json(read_at(anchor)[0])
    commands = [h.get('command', '') for e in doc.get('hooks', {}).get('SessionStart', []) for h in e['hooks']]
    if any('worktree-init.sh' in command for command in commands):
        return dict(status='BLOCKED', reason='LEGACY_HOOK_MIGRATION_REQUIRED')
    verified = [command for command in commands if owned_command(command, settings.parent / 'hooks')]
    return dict(status='INSTALLED' if verified else 'MISSING', commands=verified)


def install(settings, before_publish=None):
    import fcntl
    settings = Path(os.path.abspath(settings))
    with ExitStack() as stack:
        anchor = Anchor(settings, stack, create=True)
        lock_fd = os.open('.minmos-worktree-init.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=anchor.fd)
        stack.callback(os.close, lock_fd)
        st = os.fstat(lock_fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
            raise Blocked('INSTALL_LOCK')
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        anchor.check()
        previous = anchor.current()
        original = b'{}' if previous is None else read_at(anchor)[0]
        doc = load_json(original)
        hooks = doc.setdefault('hooks', {})
        if not isinstance(hooks, dict) or not isinstance(hooks.get('SessionStart', []), list):
            raise Blocked('HOOK_SETTINGS_SHAPE')
        entries = hooks.setdefault('SessionStart', [])
        hook_dir = settings.parent / 'hooks'
        for entry in entries:
            for h in entry['hooks']:
                if 'worktree-init.sh' in h.get('command', ''):
                    raise Blocked('LEGACY_HOOK_MIGRATION_REQUIRED')
        folder, bundle_created, warnings = ensure_bundle(hook_dir)
        command = shlex.join(['python3', str(folder / 'worktree_init.py'), 'hook'])
        found = False
        for entry in entries:
            for h in entry['hooks']:
                old = h.get('command', '')
                if old == command:
                    found = True
                elif owned_command(old, hook_dir):
                    h['command'] = command
                    found = True
        if not found:
            entries.append(dict(matcher='', hooks=[dict(type='command', command=command)]))
        if previous is not None and doc == load_json(original):
            return dict(status='UNCHANGED', settings=str(settings), command=command, cleanup_warnings=warnings)
        content = (json.dumps(doc, ensure_ascii=False, indent=2) + '\n').encode()
        try:
            warnings.extend(publish(anchor, content, previous, before_publish))
        except BaseException as exc:
            # Keep a bundle if publication is unknown or a changed settings still references it.
            current = anchor.current()
            uncertain = 'UNKNOWN:PUBLISH' in str(exc)
            try:
                published = current is not None and command.encode() in read_at(anchor)[0]
            except (OSError, ValueError, RuntimeError):
                published = True
            if bundle_created and not published and not uncertain:
                for name in BUNDLE_FILES:
                    child = Anchor(folder / name, stack)
                    if read_at(child)[0] == (Path(__file__).parent / name).read_bytes():
                        child.check()
                        os.unlink(child.name, dir_fd=child.fd)
                folder.rmdir()
            raise
        return dict(status='INSTALLED', settings=str(settings), command=command, cleanup_warnings=warnings)


def git(root, *args, allow_missing=False):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode and not (allow_missing and result.returncode == 1):
        raise Blocked('GIT_' + args[0])
    return result


def ignored_untracked(root, name):
    if git(root, 'ls-files', '-z', '--', name).stdout:
        raise Blocked('TRACKED_COPY_PATH: ' + name)
    if git(root, 'check-ignore', '--quiet', '--', name, allow_missing=True).returncode != 0:
        raise Blocked('COPY_PATH_NOT_IGNORED: ' + name)


def copy_worktree(cwd):
    root = Path(os.fsdecode(git(cwd, 'rev-parse', '--show-toplevel').stdout.removesuffix(b'\n')))
    listing = git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split(b'\0')
    first = next((field[len(b'worktree '):] for field in listing if field.startswith(b'worktree ')), None)
    if first is None:
        raise Blocked('MAIN_WORKTREE_MISSING')
    main = Path(os.fsdecode(first))
    if root == main:
        return dict(status='MAIN_WORKTREE', copied=[], skipped=[])
    if git(main, 'rev-parse', '--is-bare-repository').stdout.strip() == b'true':
        raise Blocked('MAIN_IS_BARE')
    planned, skipped = [], []
    with ExitStack() as stack:
        for name in FILES:
            destination = root / name
            if os.path.lexists(destination):
                skipped.append(dict(path=name, reason='EXISTS'))
                continue
            if not os.path.lexists(main / name):
                skipped.append(dict(path=name, reason='SOURCE_MISSING'))
                continue
            ignored_untracked(main, name)
            ignored_untracked(root, name)
            source = Anchor(main / name, stack)
            content, expected = read_at(source)
            planned.append((name, source, content, expected))
        copied, warnings = [], []
        for name, source, content, expected in planned:
            source.check()
            if stamp(source.current()) != stamp(expected):
                raise Blocked('SOURCE_CHANGED')
            ignored_untracked(root, name)
            destination = Anchor(root / name, stack, create=True)
            warnings.extend(publish(destination, content))
            copied.append(name)
        return dict(status='COPIED' if copied else 'NO_COPY', copied=copied, skipped=skipped, cleanup_warnings=warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('hook')
    init = sub.add_parser('install')
    init.add_argument('--settings', type=Path, required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--settings', type=Path, required=True)
    args = parser.parse_args()
    try:
        if sys.platform not in ('linux', 'darwin'):
            raise Blocked('POSIX_HOST_REQUIRED')
        if args.action == 'inspect':
            result = inspect_install(args.settings)
        elif args.action == 'install':
            result = install(args.settings)
        else:
            payload = load_json(sys.stdin.read())
            if not isinstance(payload.get('cwd'), str) or not payload['cwd']:
                raise Blocked('HOOK_CWD_MISSING')
            result = copy_worktree(payload['cwd'])
        print(json.dumps(result, ensure_ascii=True), file=sys.stderr)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print('BLOCKED:WORKTREE_INIT: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
