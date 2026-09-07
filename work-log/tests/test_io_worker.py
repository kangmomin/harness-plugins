"""Real process/descriptor tests; no mocks of the atomic filesystem boundary."""
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest

WORKER = Path(__file__).resolve().parents[1] / 'mcp/lib/io_worker.py'


class IOTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='work-log-io-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'vault'
        self.root.mkdir()

    def worker(self, rel='doc.md', operation='write', mode='overwrite', umask=0o022, boundary=None, user=None):
        argv = [sys.executable, '-I', '-B', '-X', 'utf8']
        argv += [str(Path(__file__).parent / 'helpers/io-boundary-worker.py'), boundary, str(WORKER)] if boundary else [str(WORKER)]
        child = subprocess.Popen(argv,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, umask=umask, user=user)

        def cleanup():
            if child.poll() is None:
                child.kill()
            child.communicate()
        self.addCleanup(cleanup)
        self.send(child, dict(operation=operation, root=str(self.root), relPath=rel, mode=mode, excludes=['.git']))
        return child

    def send(self, child, value):
        child.stdin.write(json.dumps(value) + '\n')
        child.stdin.flush()

    def read(self, child, timeout=8):
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout), 'worker did not respond')
        line = child.stdout.readline()
        self.assertTrue(line, child.stderr.read() if child.poll() is not None else 'unexpected EOF')
        return json.loads(line)

    def commit(self, child, content):
        self.send(child, {'content': content})
        prepared = self.read(child)
        self.assertEqual(prepared['type'], 'prepared', prepared)
        self.send(child, {'commit': True})
        result = self.read(child)
        child.wait(timeout=5)
        return result

    def test_path_swap_after_lock_and_after_temp(self):
        for stage in ('read', 'prepared'):
            with self.subTest(stage=stage):
                sub = self.root / stage
                sub.mkdir()
                (sub / 'doc.md').write_text('ORIGINAL')
                outside = self.base / ('outside-' + stage)
                outside.mkdir()
                (outside / 'doc.md').write_text('OUTSIDE')
                child = self.worker(stage + '/doc.md')
                self.assertEqual(self.read(child)['type'], 'read')
                if stage == 'prepared':
                    self.send(child, {'content': 'CHANGED'})
                    message = self.read(child)
                    self.assertEqual(message['type'], 'prepared')
                    (outside / message['temp']).write_text('EXTERNAL TEMP SENTINEL')
                moved = self.root / (stage + '-moved')
                sub.rename(moved)
                sub.symlink_to(outside, target_is_directory=True)
                self.send(child, {'content': 'CHANGED'} if stage == 'read' else {'commit': True})
                self.assertEqual(self.read(child)['type'], 'error')
                child.wait(timeout=5)
                self.assertEqual((outside / 'doc.md').read_text(), 'OUTSIDE')
                self.assertEqual((moved / 'doc.md').read_text(), 'ORIGINAL')
                self.assertEqual(sorted(p.name for p in moved.iterdir()), ['doc.md'])
                if stage == 'prepared':
                    self.assertEqual((outside / message['temp']).read_text(), 'EXTERNAL TEMP SENTINEL')

    def test_path_swap_while_waiting_for_document_lock(self):
        sub = self.root / 'sub'
        sub.mkdir()
        (sub / 'doc.md').write_text('ORIGINAL')
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'doc.md').write_text('OUTSIDE')
        with (sub / 'doc.md').open('r') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            child = self.worker('sub/doc.md')
            time.sleep(0.15)
            sub.rename(self.root / 'moved')
            sub.symlink_to(outside, target_is_directory=True)
            self.assertEqual(self.read(child)['type'], 'error')
        child.wait(timeout=5)
        self.assertEqual((outside / 'doc.md').read_text(), 'OUTSIDE')

    def test_mode_owner_xattr_preservation_and_private_temp(self):
        doc = self.root / 'doc.md'
        for permissions in (0o600, 0o640):
            for mask in (0o002, 0o022, 0o077):
                with self.subTest(permissions=permissions, umask=mask):
                    doc.write_text('ORIGINAL')
                    doc.chmod(permissions)
                    if sys.platform == 'linux':
                        os.setxattr(doc, 'user.work-log-test', b'private value')
                    before = doc.stat()
                    child = self.worker(umask=mask)
                    self.assertEqual(self.read(child)['existing'], 'ORIGINAL')
                    self.send(child, {'content': 'REPLACED'})
                    message = self.read(child)
                    self.assertEqual(message['type'], 'prepared', message)
                    self.assertEqual(stat.S_IMODE((self.root / message['temp']).stat().st_mode), 0o600)
                    self.send(child, {'commit': True})
                    self.assertEqual(self.read(child)['type'], 'done')
                    child.wait(timeout=5)
                    after = doc.stat()
                    self.assertEqual((stat.S_IMODE(after.st_mode), after.st_uid, after.st_gid),
                                     (permissions, before.st_uid, before.st_gid))
                    if sys.platform == 'linux':
                        self.assertEqual(os.getxattr(doc, 'user.work-log-test'), b'private value')

    def test_eof_abort_cleans_temp_and_releases_lock(self):
        doc = self.root / 'doc.md'
        doc.write_text('ORIGINAL')
        child = self.worker()
        self.read(child)
        self.send(child, {'content': 'ABORTED'})
        self.assertEqual(self.read(child)['type'], 'prepared')
        child.stdin.close()
        child.stdin = None
        self.assertEqual(self.read(child)['type'], 'error')
        child.wait(timeout=5)
        self.assertEqual([p.name for p in self.root.iterdir()], ['doc.md'])
        self.assertEqual(doc.read_text(), 'ORIGINAL')
        next_child = self.worker()
        self.read(next_child)
        self.assertEqual(self.commit(next_child, 'NEXT')['type'], 'done')

    @unittest.skipUnless(sys.platform == 'linux', 'Linux POSIX ACL encoding')
    def test_default_acl_is_not_added_to_replacement(self):
        doc = self.root / 'doc.md'
        doc.write_text('ORIGINAL')
        doc.chmod(0o640)
        acl = struct.pack('<I', 2) + b''.join(struct.pack('<HHI', *entry) for entry in [
            (1, 7, 0xffffffff), (2, 4, 12345), (4, 0, 0xffffffff),
            (16, 4, 0xffffffff), (32, 0, 0xffffffff)])
        os.setxattr(self.root, 'system.posix_acl_default', acl)
        child = self.worker()
        self.read(child)
        self.send(child, {'content': 'CHANGED'})
        prepared = self.read(child)
        self.assertEqual(prepared['type'], 'prepared', prepared)
        self.assertNotIn('system.posix_acl_access', os.listxattr(self.root / prepared['temp']))
        self.send(child, {'commit': True})
        self.assertEqual(self.read(child)['type'], 'done')
        child.wait(timeout=5)
        self.assertNotIn('system.posix_acl_access', os.listxattr(doc))
        self.assertEqual(stat.S_IMODE(doc.stat().st_mode), 0o640)

    def test_index_lock_replacement_cannot_be_committed_or_removed(self):
        (self.root / 'index.json').write_text('OLD')
        child = self.worker('index.json', operation='index')
        self.read(child)
        self.send(child, {'content': 'STALE'})
        self.assertEqual(self.read(child)['type'], 'prepared')
        lock = self.root / 'index.lock'
        lock.rename(self.root / 'old-lock')
        lock.write_text('NEW OWNER SENTINEL')
        self.send(child, {'commit': True})
        self.assertEqual(self.read(child)['type'], 'error')
        child.wait(timeout=5)
        self.assertEqual(lock.read_text(), 'NEW OWNER SENTINEL')
        self.assertEqual((self.root / 'index.json').read_text(), 'OLD')

    def test_replaced_temp_is_neither_published_nor_deleted(self):
        doc = self.root / 'doc.md'
        doc.write_text('ORIGINAL')
        child = self.worker()
        self.read(child)
        self.send(child, {'content': 'CHANGED'})
        message = self.read(child)
        temp = self.root / message['temp']
        temp.rename(self.root / 'owned-temp-moved')
        temp.write_text('REPLACEMENT SENTINEL')
        self.send(child, {'commit': True})
        self.assertEqual(self.read(child)['type'], 'error')
        child.wait(timeout=5)
        self.assertEqual(temp.read_text(), 'REPLACEMENT SENTINEL')
        self.assertEqual(doc.read_text(), 'ORIGINAL')

    def test_source_name_race_at_syscall_is_unknown_never_false_success(self):
        doc = self.root / 'doc.md'
        doc.write_text('ORIGINAL')
        child = self.worker(boundary='before-replace')
        self.read(child)
        self.send(child, {'content': 'INTENDED'})
        prepared = self.read(child)
        self.assertEqual(prepared['type'], 'prepared')
        self.send(child, {'commit': True})
        self.assertEqual(self.read(child)['type'], 'boundary')
        temp = self.root / prepared['temp']
        temp.rename(self.root / 'moved-owned-temp')
        temp.write_text('UNCOOPERATIVE REPLACEMENT')
        self.send(child, {'continue': True})
        result = self.read(child)
        self.assertEqual(result['type'], 'error')
        self.assertEqual(result['writeState'], 'unknown')
        child.wait(timeout=5)

    def test_cleanup_failure_after_create_keeps_one_written_response(self):
        user = None
        if os.geteuid() == 0:
            user = 65534
            os.chown(self.base, user, -1)
            os.chown(self.root, user, -1)
        child = self.worker(mode='create', boundary='after-link', user=user)
        self.assertEqual(self.read(child)['type'], 'read')
        self.send(child, {'content': 'SAVED'})
        self.assertEqual(self.read(child)['type'], 'prepared')
        self.send(child, {'commit': True})
        self.assertEqual(self.read(child)['type'], 'boundary')
        self.root.chmod(0o500)
        try:
            self.send(child, {'continue': True})
            result = self.read(child)
            self.assertEqual(result['type'], 'done', result)
            self.assertTrue(result['committed'])
            self.assertTrue(result['cleanupWarnings'])
            self.assertEqual(child.wait(timeout=5), 0)
            self.assertEqual(child.stdout.read(), '')
            self.assertEqual((self.root / 'doc.md').read_text(), 'SAVED')
        finally:
            self.root.chmod(0o700)

    def test_stopped_index_owner_is_not_evicted_by_age_and_death_releases(self):
        doc = self.root / 'index.json'
        doc.write_text('OLD')
        owner = self.worker('index.json', operation='index')
        self.assertEqual(self.read(owner)['existing'], 'OLD')
        os.kill(owner.pid, signal.SIGSTOP)
        lock = self.root / 'index.lock'
        lock_inode = lock.stat().st_ino
        old = time.time() - 600
        os.utime(lock, (old, old))
        waiter = self.worker('index.json', operation='index')
        result = self.read(waiter)
        self.assertEqual(result['type'], 'error', result)
        self.assertIn('잠금', result['message'])
        waiter.wait(timeout=5)
        self.assertEqual(lock.stat().st_ino, lock_inode)
        owner.kill()
        owner.wait(timeout=5)
        next_child = self.worker('index.json', operation='index')
        self.assertEqual(self.read(next_child)['existing'], 'OLD')
        self.assertEqual(self.commit(next_child, 'NEW')['type'], 'done')
        self.assertEqual(doc.read_text(), 'NEW')
        self.assertEqual(lock.stat().st_ino, lock_inode)


if __name__ == '__main__':
    unittest.main()
