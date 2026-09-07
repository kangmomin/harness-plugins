#!/usr/bin/env python3
"""Optional real integration probe. Uses installed grpcurl + cached Go modules only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    grpcurl = shutil.which('grpcurl')
    if not grpcurl:
        raise RuntimeError('installed grpcurl required; this probe never downloads it')
    env = {**os.environ, 'GOPROXY': 'off', 'GOSUMDB': 'off'}
    module = Path(subprocess.check_output(['go', 'env', 'GOMODCACHE'], text=True).strip()) / 'google.golang.org/grpc@v1.71.0'
    if not module.exists():
        raise RuntimeError('cached grpc@v1.71.0 required for offline probe')
    with tempfile.TemporaryDirectory(prefix='harness-grpc-probe-') as directory:
        root = Path(directory)
        shutil.copyfile(HERE / 'go.mod', root / 'go.mod')
        shutil.copyfile(HERE / 'go.sum', root / 'go.sum')
        shutil.copy(HERE / 'server.go', root / 'main.go')
        binary = root / 'probe-server'
        subprocess.run(['go', 'build', '-mod=readonly', '-o', str(binary), '.'], cwd=root, env=env, check=True, timeout=90)
        arrivals = root / 'arrivals.log'
        server = subprocess.Popen([str(binary), str(arrivals)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            address = server.stdout.readline().strip()
            if not address.startswith('127.0.0.1:'):
                raise RuntimeError('server did not start on loopback')
            observations = []
            cases = [('valid', {'value': 'ok'}, True), ('unknown-field', {'unknown': 'x'}, False),
                     ('oneof-conflict', {'name': 'x', 'id': 1}, True), ('server-validation', {'value': 'bad'}, True),
                     ('deadline', {'value': 'wait'}, True)]
            for name, payload, expected_contact in cases:
                before = len(arrivals.read_text().splitlines())
                command = [grpcurl, '-plaintext', '-import-path', str(HERE), '-proto', 'fixture.proto',
                           '-max-time', '0.1' if name == 'deadline' else '3', '-d', json.dumps(payload), address, 'fixture.Audit/Read']
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                after = len(arrivals.read_text().splitlines())
                contact = after > before
                assert contact == expected_contact, (name, result.stderr, before, after)
                assert after - before == int(expected_contact), (name, 'unexpected duplicate handler arrivals')
                if name in ('valid', 'oneof-conflict'):
                    expected = {'value': 'ok'} if name == 'valid' else {}
                    assert result.returncode == 0 and not result.stderr and json.loads(result.stdout) == expected, (name, 'invalid success response', result)
                elif name == 'unknown-field':
                    assert result.returncode == 1 and not result.stdout and 'no known field named unknown' in result.stderr, (name, 'expected client parser rejection', result)
                else:
                    code, status = (67, 'InvalidArgument') if name == 'server-validation' else (68, 'DeadlineExceeded')
                    assert result.returncode == code and not result.stdout and 'Code: ' + status in result.stderr, (name, 'expected ' + status, result)
                observations.append({'case_id': name, 'server_contact': contact, 'handler_arrivals': after - before,
                                     'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
            print(json.dumps({'grpcurl_module': 'v1.9.3', 'grpc_module': 'v1.71.0', 'transport': 'loopback',
                              'offline': True, 'observations': observations}, ensure_ascii=False, indent=2))
        finally:
            server.terminate()
            server.communicate(timeout=5)


if __name__ == '__main__':
    main()
