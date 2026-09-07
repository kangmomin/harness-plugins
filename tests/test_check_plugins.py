"""The structural checker must leave pre-existing files untouched."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CheckPluginsTest(unittest.TestCase):
    def test_preserves_unowned_bytecode_and_cleans_own_cache(self):
        with tempfile.TemporaryDirectory(prefix=".check-fixture-", dir=ROOT) as fixture:
            root = Path(fixture)
            existing = root / "__pycache__" / "keep.txt"
            existing.parent.mkdir()
            existing.write_bytes(b"unrelated user data")
            scratch = root / "scratch"
            scratch.mkdir()
            result = subprocess.run(
                ["bash", "scripts/check-plugins.sh"], cwd=ROOT,
                env={**os.environ, "TMPDIR": str(scratch)},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(existing.read_bytes(), b"unrelated user data")
            self.assertEqual(list(scratch.iterdir()), [])
