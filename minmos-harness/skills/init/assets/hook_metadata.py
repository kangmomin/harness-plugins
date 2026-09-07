"""Metadata boundary copied from work-log io_worker.Metadata; keep class byte parity."""
import ctypes
import errno
import os
import stat
import sys


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

