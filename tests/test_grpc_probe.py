"""The real gRPC probe must fail when the server drops its validation error."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent / 'fixtures/grpcurl'


class GrpcProbeTests(unittest.TestCase):
    def test_missing_server_invalid_argument_fails_actual_probe(self):
        if not shutil.which('grpcurl') or not shutil.which('go'):
            if os.environ.get('HARNESS_REQUIRE_GRPC') == '1':
                self.fail('Required grpcurl/Go fixture unavailable')
            self.skipTest('installed grpcurl/Go required')
        with tempfile.TemporaryDirectory(prefix='harness-grpc-negative-') as directory:
            root = Path(directory)
            for name in ('verify.py', 'server.go', 'fixture.proto', 'go.mod', 'go.sum'):
                shutil.copyfile(HERE / name, root / name)
            source = (root / 'server.go').read_text()
            self.assertIn('if request.Value == "bad"', source)
            (root / 'server.go').write_text(source.replace('if request.Value == "bad"', 'if false'))
            result = subprocess.run([sys.executable, '-B', str(root / 'verify.py')], capture_output=True, text=True, timeout=100)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('server-validation', result.stderr)
            self.assertIn('expected InvalidArgument', result.stderr)
