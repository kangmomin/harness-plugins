import importlib.util
import base64
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('writer_guard', ROOT / 'be-harness/skills/start-workflow/assets/writer_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class WriterGuardTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Linux process identity probe')
    def test_lost_handle_while_process_alive_never_allows_second_writer(self):
        proc = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
        try:
            receipt = dict(run_id='run1', call_id='write1', job_id='job1', owner_id='host/session1',
                           process=guard.process_identity(proc.pid), handle=None)
            result = guard.check_stop(dict(receipt=receipt))
            self.assertEqual(result['status'], 'BLOCKED:WRITER_LIVE')
            evidence = dict(run_id='run1', call_id='write1', job_id='job1', owner_id='host/session1',
                            status='stopped', writers_stopped=True, source='host:job-status')
            self.assertFalse(guard.check_stop(dict(receipt=receipt, evidence=evidence))['may_start_writer'])
            proc.stdin.close()
            proc.wait(timeout=5)
            self.assertFalse(guard.check_stop(dict(receipt=receipt))['may_start_writer'])
            self.assertTrue(guard.check_stop(dict(receipt=receipt, evidence=evidence))['may_start_writer'])
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()

    def test_exact_host_job_stop_evidence_required_and_wrong_owner_rejected(self):
        receipt = dict(run_id='run1', call_id='write1', job_id='job1', owner_id='host/session1')
        evidence = dict(receipt, status='completed', writers_stopped=True, source='host:task-status')
        self.assertTrue(guard.check_stop(dict(receipt=receipt, evidence=evidence))['may_start_writer'])
        for key, bad in [('owner_id', 'host/session2'), ('job_id', 'job2'), ('status', 'timeout'),
                         ('writers_stopped', False), ('source', '')]:
            self.assertFalse(guard.check_stop(dict(receipt=receipt, evidence=dict(evidence, **{key: bad})))['may_start_writer'])
        self.assertFalse(guard.check_stop(dict(receipt=dict(receipt, job_id='')))['may_start_writer'])

    def test_isolated_slice_violation_is_detected_without_reverting_other_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'main'
            root.mkdir()
            def git(cwd, *args):
                return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git(root, 'init', '-b', 'main')
            git(root, 'config', 'user.name', 'Fixture')
            git(root, 'config', 'user.email', 'fixture@example.invalid')
            (root / 'be.py').write_text('BE baseline\n')
            (root / 'fe.js').write_text('FE baseline\n')
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'baseline')
            start = git(root, 'rev-parse', 'HEAD')
            a, b = Path(tmp) / 'writer a', Path(tmp) / 'writer b'
            git(root, 'worktree', 'add', '--detach', str(a), start)
            git(root, 'worktree', 'add', '--detach', str(b), start)
            (a / 'be.py').write_text('BE implementation\n')
            (a / 'fe.js').write_text('accidental cross-slice edit\n')
            (b / 'fe.js').write_text('other writer latest\n')
            data = dict(cwd=str(a), parent_cwd=str(root), start_sha=start, allow_files=['be.py'])
            got = guard.scope(data)
            self.assertEqual(got['outside_paths'], ['fe.js'])
            self.assertFalse(got['allowed_patch'])
            self.assertEqual((b / 'fe.js').read_text(), 'other writer latest\n')
            self.assertEqual((root / 'fe.js').read_text(), 'FE baseline\n')
            (a / 'fe.js').write_text('FE baseline\n')  # explicit fixture repair in A only
            self.assertTrue(guard.scope(data)['allowed_patch'])
            (a / 'out of scope.txt').write_text('new outside file\n')
            self.assertEqual(guard.scope(data)['outside_paths'], ['out of scope.txt'])
            self.assertEqual(guard.scope(dict(data, cwd=str(root)))['status'], 'BLOCKED:UNISOLATED_WRITER')

    def test_new_files_transfer_bytes_modes_and_symlink_metadata_and_nested_checkout_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'main'
            root.mkdir()
            def git(cwd, *args):
                return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git(root, 'init', '-b', 'main')
            git(root, 'config', 'user.name', 'Fixture')
            git(root, 'config', 'user.email', 'fixture@example.invalid')
            git(root, 'commit', '--allow-empty', '-m', 'baseline')
            start = git(root, 'rev-parse', 'HEAD')
            worker = Path(tmp) / 'worker'
            git(root, 'worktree', 'add', '--detach', str(worker), start)
            (worker / 'new.py').write_bytes(b'#!/usr/bin/env python3\nprint("new")\n')
            (worker / 'new.py').chmod(0o750)
            (worker / 'alias').symlink_to('new.py')
            data = dict(cwd=str(worker), parent_cwd=str(root), start_sha=start, allow_files=['new.py', 'alias'])
            got = guard.scope(data)
            self.assertTrue(got['allowed_patch'])
            files = {f['path']: f for f in got['new_files']}
            self.assertEqual(files['new.py']['mode'], 0o750)
            self.assertEqual(base64.b64decode(files['new.py']['bytes_base64']), (worker / 'new.py').read_bytes())
            self.assertEqual(files['alias'], dict(path='alias', kind='symlink', target='new.py'))
            # Orchestrator consumes explicit new-file payload even when git patch is empty.
            self.assertEqual(got['scope']['patch'], '')
            with (root / 'new.py').open('xb') as output:
                output.write(base64.b64decode(files['new.py']['bytes_base64']))
            (root / 'new.py').chmod(files['new.py']['mode'])
            self.assertEqual((root / 'new.py').read_bytes(), (worker / 'new.py').read_bytes())
            nested = root / 'workers/nested'
            git(root, 'worktree', 'add', '--detach', str(nested), start)
            self.assertEqual(guard.scope(dict(data, cwd=str(nested)))['status'], 'BLOCKED:UNISOLATED_WRITER')


if __name__ == '__main__':
    unittest.main()
