"""Test-only IPC barriers around real publication syscalls, never used by MCP."""
import json
import os
import runpy
import sys

phase, worker = sys.argv[1:]
sys.argv = [worker]
original = os.replace if phase == 'before-replace' else os.link


def boundary(*args, **kwargs):
    if phase == 'after-link':
        result = original(*args, **kwargs)
    print(json.dumps({'type': 'boundary', 'source': args[0]}), flush=True)
    if not sys.stdin.readline():
        raise RuntimeError('test controller disconnected')
    return original(*args, **kwargs) if phase == 'before-replace' else result


if phase == 'before-replace':
    os.replace = boundary
else:
    # Keep probe membership correct while replacing only the callable boundary.
    os.link = boundary
    os.supports_dir_fd.add(boundary)
runpy.run_path(worker, run_name='__main__')
