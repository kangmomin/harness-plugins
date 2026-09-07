import os
import json
import importlib.util
import socket
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class LockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="harness-lock-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {**os.environ, "HARNESS_E2E_LOCK_DIR": str(self.root / "locks"), "TMPDIR": str(self.root)}
        self.script = ROOT / "be-harness/skills/e2e-test/assets/e2e-lock.sh"

    def command(self, action, token=None, *options):
        args = ["bash", str(self.script), action, "http://localhost:8080"]
        if token is not None:
            args += ["--token", token]
        return subprocess.run([*args, *options], env=self.env, capture_output=True, text=True, timeout=10)

    def test_different_runs_exclude_each_other_and_same_run_can_resume(self):
        self.assertEqual(self.command("acquire", "run-a", "--timeout", "0").returncode, 0)
        other = self.command("acquire", "run-b", "--timeout", "0")
        self.assertEqual(other.returncode, 2, other.stdout + other.stderr)
        self.assertIn("ALREADY_HELD", self.command("acquire", "run-a").stdout)
        self.assertEqual(self.command("beat", "run-a").returncode, 0)
        self.assertEqual(self.command("release", "run-a").returncode, 0)
        self.assertEqual(self.command("acquire", "run-b", "--timeout", "0").returncode, 0)

    def test_wrong_owner_cannot_touch_or_release_lock(self):
        self.command("acquire", "run-a")
        owner = next((self.root / "locks").glob("*.lock/owner"))
        before = owner.read_bytes(), owner.stat().st_mtime_ns
        self.assertEqual(self.command("beat", "run-b").returncode, 1)
        self.assertEqual(self.command("release", "run-b").returncode, 1)
        self.assertEqual((owner.read_bytes(), owner.stat().st_mtime_ns), before)
        self.assertFalse(list((self.root / "locks").glob("*.reap.*")))

    def test_stale_lock_takeover_rejects_previous_owner(self):
        self.command("acquire", "run-a")
        owner = next((self.root / "locks").glob("*.lock/owner"))
        os.utime(owner, (time.time() - 30, time.time() - 30))
        self.assertEqual(self.command("acquire", "run-b", "--ttl", "1", "--timeout", "0").returncode, 0)
        self.assertEqual(self.command("release", "run-a").returncode, 1)
        self.assertEqual(json.loads(owner.read_text())["token"], "run-b")

    def test_concurrent_acquires_have_one_winner(self):
        args = ["bash", str(self.script), "acquire", "localhost:8080", "--timeout", "0"]
        children = [subprocess.Popen([*args, "--token", token], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for token in ("run-a", "run-b")]
        for child in children:
            self.addCleanup(lambda p=child: p.kill() if p.poll() is None else None)
        for child in children:
            child.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in children), [0, 2])

    def test_missing_token_fails_without_creating_lock(self):
        self.assertEqual(self.command("acquire", None, "--timeout", "0").returncode, 1)
        self.assertFalse((self.root / "locks").exists())

    def endpoint(self, endpoint, token, action='acquire', env=None):
        return subprocess.run(['bash', str(self.script), action, endpoint, '--token', token, '--timeout', '0'],
                              env=env or self.env, capture_output=True, text=True, timeout=10)

    def test_loopback_aliases_share_real_socket_lock(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen()
            port = server.getsockname()[1]
            with socket.create_connection(('localhost', port)):
                pass
            self.assertEqual(self.endpoint('http://localhost:%d/api' % port, 'owner').returncode, 0)
            for host in ('127.0.0.1', '[::ffff:127.0.0.1]', 'LOCALHOST.'):
                result = self.endpoint('http://%s:%d' % (host, port), 'other')
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)

    def test_wildcard_overlap_and_independent_addresses(self):
        with socket.socket() as a, socket.socket() as b:
            a.bind(('127.0.0.1', 0))
            port = a.getsockname()[1]
            try:
                b.bind(('127.0.0.2', port))
            except OSError:
                self.skipTest('second loopback address unavailable on this host')
            self.assertEqual(self.endpoint('127.0.0.1:%d' % port, 'a').returncode, 0)
            self.assertEqual(self.endpoint('127.0.0.2:%d' % port, 'b').returncode, 0)
            self.assertEqual(self.endpoint('0.0.0.0:%d' % port, 'wildcard').returncode, 2)
            self.assertEqual(self.endpoint('[::]:%d' % port, 'wildcard-v6').returncode, 2)
            self.assertEqual(self.endpoint('127.0.0.1:%d' % (port + 1 if port < 65535 else port - 1), 'independent-port').returncode, 0)

    def test_default_port_and_opaque_handle(self):
        result = self.endpoint('https://localhost/path', 'a')
        self.assertEqual(result.returncode, 0, result.stderr)
        handle = result.stdout.split('key=', 1)[1].split()[0]
        self.assertEqual(self.endpoint('127.0.0.1:443', 'b').returncode, 2)
        self.assertEqual(self.endpoint(handle, 'a', action='beat').returncode, 0)
        self.assertEqual(self.endpoint(handle, 'a', action='release').returncode, 0)
        self.assertEqual(self.endpoint('127.0.0.1:443', 'b').returncode, 0)

    def test_work_log_scope_does_not_change_lock_root(self):
        first = {**self.env, 'WORK_LOG_ROOT': str(self.root / 'vault-a')}
        second = {**self.env, 'WORK_LOG_ROOT': str(self.root / 'vault-b')}
        self.assertEqual(self.endpoint('localhost:9080', 'a', env=first).returncode, 0)
        self.assertEqual(self.endpoint('127.0.0.1:9080', 'b', env=second).returncode, 2)

    def test_namespace_is_part_of_resource_identity(self):
        spec = importlib.util.spec_from_file_location('e2e_lock', self.script.with_name('e2e_lock.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resource = module.resource('127.0.0.1:8000')
        if Path('/proc/self/ns/net').exists():
            self.assertEqual(resource['namespace'], str(Path('/proc/self/ns/net').stat().st_ino))
        self.assertFalse(module.overlaps(resource, {**resource, 'namespace': 'another-namespace'}))
        for vault in ('vault-a', 'vault-b'):
            with patch.dict(os.environ, {'WORK_LOG_ROOT': str(self.root / vault)}, clear=True):
                self.assertEqual(module.lock_root(), Path('/tmp/harness-e2e-locks'))


if __name__ == "__main__":
    unittest.main()
