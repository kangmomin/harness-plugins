import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


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
        owner = self.root / "locks/localhost-8080.lock/owner"
        before = owner.read_bytes(), owner.stat().st_mtime_ns
        self.assertEqual(self.command("beat", "run-b").returncode, 1)
        self.assertEqual(self.command("release", "run-b").returncode, 1)
        self.assertEqual((owner.read_bytes(), owner.stat().st_mtime_ns), before)
        self.assertFalse(list((self.root / "locks").glob("*.reap.*")))

    def test_stale_lock_takeover_rejects_previous_owner(self):
        self.command("acquire", "run-a")
        owner = self.root / "locks/localhost-8080.lock/owner"
        os.utime(owner, (time.time() - 30, time.time() - 30))
        self.assertEqual(self.command("acquire", "run-b", "--ttl", "1", "--timeout", "0").returncode, 0)
        self.assertEqual(self.command("release", "run-a").returncode, 1)
        self.assertIn("token=run-b", owner.read_text())

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


if __name__ == "__main__":
    unittest.main()
