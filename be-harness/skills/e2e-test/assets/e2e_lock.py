#!/usr/bin/env python3
"""Cross-call E2E leases on overlapping socket resources; flock guards metadata.

Lease heartbeat spans separate tool processes. All participants must use this
protocol and common lock root. Vault configuration never chooses that root.
"""
import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from urllib.parse import urlsplit


def resource(raw):
    parsed = urlsplit(raw if '://' in raw else 'tcp://' + raw)
    port = parsed.port if parsed.port is not None else {'http': 80, 'https': 443}.get(parsed.scheme)
    if not parsed.hostname or not port or not 1 <= port <= 65535:
        raise ValueError('socket key requires a host and valid port (HTTP/HTTPS defaults allowed)')
    host = parsed.hostname.rstrip('.').lower()
    if host == 'localhost':
        addresses = {'127.0.0.1', '::1'}
    else:
        try:
            addresses = {str(ipaddress.ip_address(host))}
        except ValueError:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    normalized = set()
    for address in addresses:
        ip = ipaddress.ip_address(address)
        normalized.add(str(ip.ipv4_mapped) if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else str(ip))
    if '::' in normalized:
        normalized.add('0.0.0.0')  # IPv6 wildcard may bind both families.
    ns = Path('/proc/self/ns/net')
    namespace = str(ns.stat().st_ino) if ns.exists() else socket.gethostname()
    return {'namespace': namespace, 'transport': 'tcp', 'port': port, 'addresses': sorted(normalized)}


def overlaps(left, right):
    if any(left[k] != right[k] for k in ('namespace', 'transport', 'port')):
        return False
    for a in left['addresses']:
        for b in right['addresses']:
            if a == b or ipaddress.ip_address(a).version == ipaddress.ip_address(b).version and ('0.0.0.0' in (a, b) or '::' in (a, b)):
                return True
    return False


def key_for(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]


def read_owner(directory):
    with (directory / 'owner').open(encoding='utf-8') as stream:
        owner = json.load(stream)
    if not isinstance(owner, dict) or not isinstance(owner.get('resource'), dict) or not owner.get('token'):
        raise ValueError('invalid lease owner: ' + str(directory))
    return owner


def lock_root():
    root = Path(os.environ.get('HARNESS_E2E_LOCK_DIR', '/tmp/harness-e2e-locks'))
    if not root.is_absolute():
        raise ValueError('HARNESS_E2E_LOCK_DIR must be absolute and shared by all participants')
    return root


def execute(args):
    root = lock_root()
    if args.action != 'status' and not re.fullmatch(r'[A-Za-z0-9._-]+', args.token or ''):
        raise ValueError('실행별 --token 이 필요합니다')
    root.mkdir(parents=True, exist_ok=True)
    requested = None
    if args.key:
        if args.key.startswith('resource:'):
            key = args.key.removeprefix('resource:')
            if not re.fullmatch(r'[0-9a-f]{24}', key):
                raise ValueError('invalid resource key')
        else:
            requested = resource(args.key)
            key = key_for(requested)
    else:
        key = None
    if args.action != 'status' and key is None:
        raise ValueError('key required')
    deadline = time.monotonic() + args.timeout
    guard_fd = os.open(root / '.metadata.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(guard_fd, 'a+b') as guard:
        while True:
            guard_deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= guard_deadline:
                        raise ValueError('lock metadata owner is still busy')
                    time.sleep(0.05)
            try:
                lock = root / (key + '.lock') if key else None
                if args.action == 'status':
                    print('lock_root=' + str(root))
                    for item in sorted(root.glob('*.lock')):
                        if item.is_dir() and (key is None or item == lock):
                            print(json.dumps({'key': 'resource:' + item.stem, **read_owner(item)}, ensure_ascii=False))
                    return 0
                owner = read_owner(lock) if lock.exists() else None
                if args.action in ('beat', 'release'):
                    if owner is None:
                        print('NOT_HELD key=resource:' + key)
                        return 0 if args.action == 'release' else 1
                    if owner['token'] != args.token:
                        print('RELEASE_DENIED' if args.action == 'release' else 'BEAT_SKIP')
                        return 1
                    if args.action == 'beat':
                        os.utime(lock / 'owner', None)
                    else:
                        (lock / 'owner').unlink()
                        lock.rmdir()
                    print(('BEAT' if args.action == 'beat' else 'RELEASED') + ' key=resource:' + key)
                    return 0
                if requested is None:
                    if owner is None:
                        raise ValueError('expired resource handle; acquire the verified bind endpoint again')
                    requested = owner['resource']
                conflicts = []
                for item in root.glob('*.lock'):
                    if not item.is_dir():
                        continue
                    other = read_owner(item)
                    if not overlaps(requested, other['resource']):
                        continue
                    if other['token'] == args.token:
                        if item == lock:
                            os.utime(item / 'owner', None)
                            print('ALREADY_HELD key=resource:' + key + ' lock=' + str(item))
                            return 0
                        continue
                    age = time.time() - (item / 'owner').stat().st_mtime
                    if age > args.ttl:
                        (item / 'owner').unlink()
                        item.rmdir()
                    else:
                        conflicts.append(other)
                if not conflicts:
                    lock.mkdir()
                    try:
                        with (lock / 'owner').open('x', encoding='utf-8') as stream:
                            json.dump({'token': args.token, 'pid': os.getpid(), 'host': socket.gethostname(),
                                       'started': time.time(), 'label': args.label, 'resource': requested}, stream)
                    except Exception:
                        (lock / 'owner').unlink(missing_ok=True)
                        lock.rmdir()
                        raise
                    print('ACQUIRED key=resource:' + key + ' lock=' + str(lock))
                    return 0
                if time.monotonic() >= deadline:
                    print('TIMEOUT key=resource:' + key + ' holder_label=' + conflicts[0]['label'])
                    return 2
            finally:
                fcntl.flock(guard, fcntl.LOCK_UN)
            time.sleep(max(0.05, args.poll))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['acquire', 'beat', 'release', 'status'])
    parser.add_argument('key', nargs='?')
    parser.add_argument('--token')
    parser.add_argument('--timeout', type=int, default=540)
    parser.add_argument('--ttl', type=int, default=900)
    parser.add_argument('--poll', type=float, default=5)
    parser.add_argument('--label', default='')
    args = parser.parse_args()
    try:
        if args.timeout < 0 or args.ttl < 1 or args.poll < 0:
            raise ValueError('invalid timeout/ttl/poll')
        return execute(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('ERROR ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
