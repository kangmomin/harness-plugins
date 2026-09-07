#!/usr/bin/env python3
"""Read-only writer stop-evidence and isolated Git scope checks.

Host evidence is an orchestrator attestation, not a cryptographic sandbox.
The process probe uses Linux boot ID/start ticks to distinguish PID reuse.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import stat
import sys

sys.dont_write_bytecode = True


def process_identity(pid):
    if type(pid) is not int or pid < 1:
        raise ValueError('positive PID required')
    if sys.platform != 'linux':
        return dict(status='UNKNOWN', pid=pid, reason='use host job-status evidence on this platform')
    try:
        # comm may contain spaces and parentheses; the closing ')' ends field2.
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return dict(status='PRESENT', pid=pid, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    start_ticks=fields[19], process_state=fields[0])
    except FileNotFoundError:
        return dict(status='ABSENT', pid=pid)
    except (OSError, IndexError):
        return dict(status='UNKNOWN', pid=pid, reason='process identity unavailable')


def check_stop(data):
    receipt, evidence = data.get('receipt'), data.get('evidence')
    if not isinstance(receipt, dict):
        raise ValueError('receipt required')
    keys = ('run_id', 'call_id', 'job_id', 'owner_id')
    if any(not isinstance(receipt.get(k), str) or not receipt[k] for k in keys):
        return dict(status='BLOCKED:WRITER_IDENTITY', may_start_writer=False)
    probe = None
    identity = receipt.get('process')
    if identity is not None:
        if not isinstance(identity, dict) or any(not identity.get(k) for k in ('pid', 'boot_id', 'start_ticks')):
            return dict(status='BLOCKED:WRITER_IDENTITY', may_start_writer=False)
        probe = process_identity(identity['pid'])
        same = probe.get('boot_id') == identity['boot_id'] and probe.get('start_ticks') == identity['start_ticks']
        # Even a zombie/terminated parent is not proof that its child writers stopped.
        if probe['status'] == 'PRESENT' and same and probe['process_state'] not in ('Z', 'X'):
            return dict(status='BLOCKED:WRITER_LIVE', may_start_writer=False, process=probe)
        if probe['status'] == 'UNKNOWN':
            return dict(status='BLOCKED:WRITER_UNKNOWN', may_start_writer=False, process=probe)
    valid = (isinstance(evidence, dict) and all(evidence.get(k) == receipt[k] for k in keys)
             and evidence.get('status') in ('completed', 'failed', 'stopped')
             and evidence.get('writers_stopped') is True
             and isinstance(evidence.get('source'), str) and bool(evidence['source'].strip()))
    return dict(status='STOP_CONFIRMED' if valid else 'BLOCKED:WRITER_UNKNOWN',
                may_start_writer=valid, process=probe)


def scope(data):
    cwd, parent = Path(data['cwd']).resolve(), Path(data['parent_cwd']).resolve()
    if cwd == parent or parent in cwd.parents:
        return dict(status='BLOCKED:UNISOLATED_WRITER', allowed_patch=False)
    allow = data.get('allow_files')
    if not isinstance(allow, list) or any(not isinstance(p, str) or not p or Path(p).is_absolute()
                                         or '..' in Path(p).parts or '.git' in Path(p).parts
                                         or str(Path(p)) != p for p in allow):
        raise ValueError('allow_files must be exact normalized root-relative file paths')
    spec = importlib.util.spec_from_file_location('writer_workflow_scope', Path(__file__).with_name('workflow_scope.py'))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    raw = subprocess.run(['git', '-C', str(cwd), 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True, check=True).stdout
    visible_new = [x.decode(errors='surrogateescape') for x in raw.split(b'\0') if x]
    result = helper.scope(str(cwd), data['start_sha'], visible_new)
    # Working-directory isolation requires the Git root itself to differ too.
    if Path(result['root']).resolve() == parent:
        return dict(status='BLOCKED:UNISOLATED_WRITER', allowed_patch=False)
    outside = sorted(set(result['paths']) - set(allow))
    head_moved = result['head'] != result['start_sha']
    new_files = []
    if not (outside or head_moved):
        for name in result['owned_untracked']:
            path = Path(result['root']) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                new_files.append(dict(path=name, kind='symlink', target=os.readlink(path)))
            elif stat.S_ISREG(info.st_mode):
                payload = path.read_bytes()
                new_files.append(dict(path=name, kind='file', mode=stat.S_IMODE(info.st_mode),
                                      sha256=hashlib.sha256(payload).hexdigest(),
                                      bytes_base64=base64.b64encode(payload).decode('ascii')))
            else:
                raise ValueError('unsupported new file kind: ' + name)
    return dict(status='BLOCKED:SLICE_SCOPE' if outside or head_moved else 'PASS',
                allowed_patch=not (outside or head_moved), outside_paths=outside, head_moved=head_moved,
                scope=result, new_files=new_files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['process', 'check-stop', 'scope'])
    parser.add_argument('input', help='PID for process, JSON path or - otherwise')
    args = parser.parse_args()
    try:
        if args.action == 'process':
            result = process_identity(int(args.input))
        else:
            data = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text())
            if not isinstance(data, dict):
                raise ValueError('input must be an object')
            result = check_stop(data) if args.action == 'check-stop' else scope(data)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if result['status'].startswith('BLOCKED:') else 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print('BLOCKED:WRITER_GUARD: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
