#!/usr/bin/env python3
"""Descriptor-anchored POSIX transactions. NDJSON: request/read/content/prepared/commit/done.

flock is advisory: every writer must use this protocol. Lock files are never
unlinked, and an existing document's old AND replacement inodes stay locked.
"""
import ctypes
import errno
import json
import os
import stat
import sys
import time
import uuid
from contextlib import ExitStack


def send(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def receive():
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError('transaction aborted: caller disconnected')
    value = json.loads(line)
    if value.get('abort'):
        raise RuntimeError('transaction aborted by caller')
    return value


def identity(st):
    return st.st_dev, st.st_ino


def probe():
    if sys.version_info < (3, 9) or sys.platform not in ('linux', 'darwin'):
        raise RuntimeError('safe write/sync requires Python >=3.9 on Linux or macOS')
    for fn in (os.open, os.mkdir, os.stat, os.unlink, os.rename, os.link):
        if fn not in os.supports_dir_fd:
            raise RuntimeError('required descriptor-relative filesystem API unavailable')
    import fcntl
    return fcntl


class Anchor:
    """Pin every parent from /; all mutations and cleanup use its final fd."""
    def __init__(self, root, rel, create, stack):
        self.root = root
        self.real_root = os.path.realpath(root)
        target = os.path.realpath(os.path.join(self.real_root, rel))
        self.rel = os.path.relpath(target, self.real_root)
        if os.path.isabs(rel) or self.rel == '.' or self.rel.split(os.sep)[0] == '..':
            raise RuntimeError('vault 밖의 경로입니다')
        self.chain = []
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, fd)
        for name in os.path.dirname(target).split(os.sep)[1:]:
            try:
                next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                self.check()
                try:
                    os.mkdir(name, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, next_fd)
            self.chain.append((fd, name, identity(os.fstat(next_fd))))
            fd = next_fd
        self.fd, self.name = fd, os.path.basename(target)
        self.check()

    def check(self):
        if os.path.realpath(self.root) != self.real_root:
            raise RuntimeError('directory changed during transaction')
        for parent, name, expected in self.chain:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or identity(current) != expected:
                raise RuntimeError('directory changed during transaction')

    def current(self):
        try:
            return os.stat(self.name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return None


class Metadata:
    """Preserve observable fd metadata; unsupported/unpreservable values fail closed."""
    def __init__(self):
        self.lib = None
        if sys.platform == 'darwin':
            self.lib = ctypes.CDLL(None, use_errno=True)
            signatures = {
                'acl_get_fd_np': ([ctypes.c_int, ctypes.c_int], ctypes.c_void_p),
                'acl_set_fd_np': ([ctypes.c_int, ctypes.c_void_p, ctypes.c_int], ctypes.c_int),
                'acl_init': ([ctypes.c_int], ctypes.c_void_p),
                'acl_free': ([ctypes.c_void_p], ctypes.c_int),
                'acl_size': ([ctypes.c_void_p], ctypes.c_ssize_t),
                'acl_copy_ext': ([ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t], ctypes.c_ssize_t),
                'flistxattr': ([ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int], ctypes.c_ssize_t),
                'fgetxattr': ([ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int], ctypes.c_ssize_t),
                'fsetxattr': ([ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int], ctypes.c_int),
                'fremovexattr': ([ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
            }
            for name, (args, result) in signatures.items():
                fn = getattr(self.lib, name)
                fn.argtypes, fn.restype = args, result

    def call(self, name, *args):
        result = getattr(self.lib, name)(*args)
        if result is None or result == -1:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number))
        return result

    def acl(self, fd):
        acl = self.get_acl(fd)
        try:
            return self.acl_bytes(acl)
        finally:
            self.call('acl_free', acl)

    def get_acl(self, fd):
        ctypes.set_errno(0)
        acl = self.lib.acl_get_fd_np(fd, 0x100)
        if acl:
            return acl
        number = ctypes.get_errno()
        if number == errno.ENOENT:
            return self.call('acl_init', 0)  # macOS ordinary files may have no explicit ACL.
        raise OSError(number, os.strerror(number))

    def acl_bytes(self, acl):
        size = self.call('acl_size', acl)
        buf = ctypes.create_string_buffer(size)
        self.call('acl_copy_ext', buf, acl, size)
        return buf.raw

    def attrs(self, fd):
        if self.lib is None:
            return {name: os.getxattr(fd, name) for name in os.listxattr(fd)}
        size = self.call('flistxattr', fd, None, 0, 0)
        buf = ctypes.create_string_buffer(size)
        size = self.call('flistxattr', fd, buf, size, 0)
        attrs = {}
        for name in buf.raw[:size].split(b'\0'):
            if not name:
                continue
            size = self.call('fgetxattr', fd, name, None, 0, 0, 0)
            value = ctypes.create_string_buffer(size)
            size = self.call('fgetxattr', fd, name, value, size, 0, 0)
            attrs[name] = value.raw[:size]
        return attrs

    def set_attrs(self, fd, expected):
        actual = self.attrs(fd)
        for name in actual.keys() - expected.keys():
            if self.lib:
                self.call('fremovexattr', fd, name, 0)
            else:
                os.removexattr(fd, name)
        for name, value in expected.items():
            if actual.get(name) == value:
                continue
            if self.lib:
                self.call('fsetxattr', fd, name, value, len(value), 0, 0)
            else:
                os.setxattr(fd, name, value)

    def private(self, fd):
        # Remove inherited ACLs before any document bytes enter the temp file.
        if self.lib:
            acl = self.call('acl_init', 0)
            try:
                self.call('acl_set_fd_np', fd, acl, 0x100)
                if self.acl(fd) != self.acl_bytes(acl):
                    raise RuntimeError('temporary ACL privacy verification failed')
            finally:
                self.call('acl_free', acl)
        else:
            attrs = self.attrs(fd)
            attrs.pop('system.posix_acl_access', None)
            self.set_attrs(fd, attrs)
        os.fchmod(fd, 0o600)

    def copy(self, source, target):
        st = os.fstat(source)
        expected = self.attrs(source)
        actual = os.fstat(target)
        if (st.st_uid, st.st_gid) != (actual.st_uid, actual.st_gid):
            os.fchown(target, st.st_uid, st.st_gid)
        self.set_attrs(target, expected)
        os.fchmod(target, stat.S_IMODE(st.st_mode))
        if self.lib:
            acl = self.get_acl(source)
            try:
                self.call('acl_set_fd_np', target, acl, 0x100)
            finally:
                self.call('acl_free', acl)
            if self.acl(source) != self.acl(target):
                raise RuntimeError('ACL preservation verification failed')
        actual = os.fstat(target)
        if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (actual.st_uid, actual.st_gid, stat.S_IMODE(actual.st_mode)) or expected != self.attrs(target):
            raise RuntimeError('metadata preservation verification failed')


def transact(request, locks):
    cleanup_warnings = []
    with ExitStack() as stack:
        index = request['operation'] == 'index'
        mode = 'overwrite' if index else request.get('mode', 'create')
        anchor = Anchor(request['root'], request['relPath'], index or mode == 'create', stack)
        if not index and (not anchor.rel.lower().endswith('.md') or
                          any(part in request['excludes'] for part in anchor.rel.split(os.sep))):
            raise RuntimeError('excluded path or non-Markdown document')
        if index:
            os.fchmod(anchor.fd, 0o700)
        deadline = time.monotonic() + 5

        def acquire(fd, label):
            while True:
                anchor.check()
                try:
                    locks.flock(fd, locks.LOCK_EX | locks.LOCK_NB)
                    return
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(label + ' 잠금 대기 시간 초과')
                    time.sleep(0.05)

        def opened(name, flags, permissions=0o600, register=True):
            fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, permissions, dir_fd=anchor.fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise RuntimeError('target must be a regular file')
            if register:
                stack.callback(os.close, fd)
            return fd

        lock_fd = None
        if index:
            lock_fd = opened('index.lock', os.O_RDWR | os.O_CREAT)
            if os.fstat(lock_fd).st_nlink != 1:
                raise RuntimeError('index lock must not have hard-link aliases')
            acquire(lock_fd, '인덱스')
            old = os.read(lock_fd, 4096).strip()
            if old.isdigit():
                try:
                    os.kill(int(old), 0)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    raise RuntimeError('legacy index owner may be alive; stop old MCP servers before upgrade')
                else:
                    raise RuntimeError('legacy index owner alive; stop old MCP servers before upgrade')
            os.fchmod(lock_fd, 0o600)
            os.ftruncate(lock_fd, 0)
            os.lseek(lock_fd, 0, os.SEEK_SET)
            os.write(lock_fd, json.dumps({'pid': os.getpid(), 'protocol': 1}).encode())
            if 'vaultRoot' in request:
                marker = opened('vault-path.txt', os.O_WRONLY | os.O_CREAT)
                if os.fstat(marker).st_nlink != 1:
                    raise RuntimeError('cache marker must not have hard-link aliases')
                os.fchmod(marker, 0o600)
                os.ftruncate(marker, 0)
                os.write(marker, (request['vaultRoot'] + '\n').encode('utf-8'))
        else:
            legacy = '.' + anchor.name + '.write-lock'
            while True:
                anchor.check()
                try:
                    os.stat(legacy, dir_fd=anchor.fd, follow_symlinks=False)
                except FileNotFoundError:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('문서 쓰기 잠금 대기 시간 초과: legacy lock (소유자 정보 없음). Stop old MCP servers before upgrade.')
                time.sleep(0.05)

        source = None
        while True:
            if time.monotonic() >= deadline:
                raise RuntimeError('문서 쓰기 잠금 대기 시간 초과')
            anchor.check()
            try:
                fd = opened(anchor.name, os.O_RDONLY, register=False)
            except FileNotFoundError:
                if mode != 'create' and not index:
                    raise RuntimeError('대상 파일이 없습니다: ' + anchor.rel)
                break
            try:
                acquire(fd, '문서 쓰기')
                current = anchor.current()
                if current and identity(current) == identity(os.fstat(fd)):
                    source = fd
                    stack.callback(os.close, fd)
                    break
            finally:
                if source is None:
                    os.close(fd)
        if source is not None and mode == 'create':
            raise RuntimeError('파일이 이미 있습니다: ' + anchor.rel)
        snapshot = os.fstat(source) if source is not None else None
        existing = None
        if source is not None:
            with os.fdopen(os.dup(source), 'r', encoding='utf-8', errors='replace' if index else 'strict', newline='') as reader:
                existing = reader.read()
        send({'type': 'read', 'existing': existing, 'rel': anchor.rel})
        content = receive()['content'].encode('utf-8')
        anchor.check()
        metadata = Metadata()
        temp = '.' + anchor.name + '.' + uuid.uuid4().hex + '.tmp'
        tmp_fd = opened(temp, os.O_RDWR | os.O_CREAT | os.O_EXCL)
        temp_id = identity(os.fstat(tmp_fd))

        def cleanup():
            try:
                if identity(os.stat(temp, dir_fd=anchor.fd, follow_symlinks=False)) == temp_id:
                    os.unlink(temp, dir_fd=anchor.fd)
            except FileNotFoundError:
                pass
            except OSError as error:
                cleanup_warnings.append(str(error))

        stack.callback(cleanup)
        acquire(tmp_fd, 'temporary document')
        metadata.private(tmp_fd)
        with os.fdopen(os.dup(tmp_fd), 'wb') as writer:
            writer.write(content)
            writer.flush()
        # Keep the temporary copy private until the commit command is received.
        send({'type': 'prepared', 'temp': temp})
        if receive().get('commit') is not True:
            raise RuntimeError('commit command required')
        anchor.check()
        current = anchor.current()
        if source is None:
            if current is not None:
                raise RuntimeError('target appeared during transaction')
        elif current is None or (identity(current), current.st_mtime_ns, current.st_size) != (identity(snapshot), snapshot.st_mtime_ns, snapshot.st_size):
            raise RuntimeError('target changed during transaction')
        if lock_fd is not None and identity(os.stat('index.lock', dir_fd=anchor.fd, follow_symlinks=False)) != identity(os.fstat(lock_fd)):
            raise RuntimeError('index lock replaced during transaction')
        if identity(os.stat(temp, dir_fd=anchor.fd, follow_symlinks=False)) != temp_id:
            raise RuntimeError('temporary file replaced during transaction')
        if not index and source is not None:
            metadata.copy(source, tmp_fd)
        # New documents and cache files deliberately default to private 0600.
        os.fsync(tmp_fd)
        anchor.check()
        if identity(os.stat(temp, dir_fd=anchor.fd, follow_symlinks=False)) != temp_id:
            raise RuntimeError('temporary file replaced before publication')
        if mode == 'create':
            os.link(temp, anchor.name, src_dir_fd=anchor.fd, dst_dir_fd=anchor.fd, follow_symlinks=False)
        else:
            os.replace(temp, anchor.name, src_dir_fd=anchor.fd, dst_dir_fd=anchor.fd)
        try:
            anchor.check()
            if identity(anchor.current()) != temp_id:
                raise RuntimeError('published inode differs from the prepared document')
            for offset in range(0, len(content), 65536):
                if os.pread(tmp_fd, 65536, offset) != content[offset:offset + 65536]:
                    raise RuntimeError('published content changed during transaction')
            if os.fstat(tmp_fd).st_size != len(content):
                raise RuntimeError('published size changed during transaction')
        except Exception as error:
            error.write_state = 'unknown'
            raise
        try:
            os.fsync(anchor.fd)
        except OSError as error:
            # Publication already happened; report durability separately.
            durability = str(error)
        else:
            durability = 'synced'
    return {'type': 'done', 'committed': True, 'durability': durability, 'cleanupWarnings': cleanup_warnings}


def main():
    try:
        locks = probe()
        if sys.argv[1:] == ['--probe']:
            Metadata()
            send({'available': True, 'platform': sys.platform, 'python': sys.version.split()[0]})
        else:
            send(transact(receive(), locks))
    except Exception as error:
        send({'type': 'error', 'message': str(error), 'code': getattr(error, 'errno', None), 'writeState': getattr(error, 'write_state', 'not_written')})
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
