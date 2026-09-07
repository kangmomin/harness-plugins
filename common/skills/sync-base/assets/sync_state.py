#!/usr/bin/env python3
"""Read-only merge preflight, candidate refresh and conflict-section extraction."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def git(cwd, *args, optional=False):
    proc = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True)
    if proc.returncode:
        if optional and proc.returncode == 1:
            return b''
        raise ValueError(proc.stderr.decode(errors='replace').strip() or 'Git lookup failed')
    return proc.stdout


def state(cwd):
    root = Path(git(cwd, 'rev-parse', '--show-toplevel').decode().strip())
    operations = []
    paths = {}
    for name in ('rebase-merge', 'rebase-apply'):
        path = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', name).decode().strip())
        paths[name] = str(path)
        if path.exists():
            operations.append(name)
    refs = {name: git(root, 'rev-parse', '-q', '--verify', name, optional=True).decode().strip()
            for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD')}
    operations += [name for name in ('CHERRY_PICK_HEAD', 'REVERT_HEAD') if refs[name]]
    return dict(root=str(root), status='BLOCKED:OTHER_OP_IN_PROGRESS' if operations else 'MERGING' if refs['MERGE_HEAD'] else 'IDLE',
                operations=operations, git_paths=paths, refs=refs,
                dirty=bool(git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')))


def targets(cwd, configured=None, before_merge=None):
    root = Path(git(cwd, 'rev-parse', '--show-toplevel').decode().strip())
    paths = set(x.decode(errors='surrogateescape') for x in git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0') if x)
    existing = {p for p in paths if not {'node_modules', 'vendor', '.git'} & set(Path(p).parts)
                and (root / p).is_file() and not (root / p).is_symlink()}
    versions = sorted(existing & {'VERSION', 'VERSION.txt'})
    defaults = {'docs/swagger.json', 'openapi.json', 'swagger.json', 'docs/swagger.yaml', 'docs/swagger.yml',
                'openapi.yaml', 'openapi.yml', 'docs/docs.go'}
    if configured is not None:
        if not isinstance(configured, list) or any(not isinstance(p, str) or not p or Path(p).is_absolute() or '..' in Path(p).parts for p in configured):
            raise ValueError('swaggerVersionFiles must be normalized root-relative paths')
        wanted = set(configured)
    else:
        wanted = defaults | {p for p in existing if p.endswith('.go') and re.search(rb'(?m)^\s*//\s*@version\s+\S+', (root / p).read_bytes())}
    swag = {'docs/docs.go', 'docs/swagger.json', 'docs/swagger.yaml'}
    if wanted & swag:
        wanted |= swag
    # Missing configured names are visible for rename/delete reconciliation, never recreated.
    conflicts = sorted(set(x.decode(errors='surrogateescape') for x in git(root, 'diff', '--name-only', '-z', '--diff-filter=U').split(b'\0') if x))
    renames = {}
    if before_merge is not None:
        baseline = git(root, 'rev-parse', '--verify', before_merge + '^{commit}').decode().strip()
        tokens = git(root, 'diff', '--name-status', '-z', '--find-renames', baseline, '--').split(b'\0')
        i = 0
        while i < len(tokens) and tokens[i]:
            status = tokens[i].decode()
            old = tokens[i + 1].decode(errors='surrogateescape')
            if status[0] in ('R', 'C'):
                new = tokens[i + 2].decode(errors='surrogateescape')
                if status[0] == 'R':
                    renames[old] = new
                i += 3
            else:
                i += 2
    return dict(root=str(root), versions=versions, version_status='AMBIGUOUS' if len(versions) > 1 else 'FOUND' if versions else 'ABSENT',
                swagger=sorted(existing & wanted), missing=sorted(wanted - existing) if configured is not None else [], conflicts=conflicts, renames=renames)


def hunks(text):
    result, block, side = [], None, None
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        match = re.match(r'^(<+|\|+|=+|>+)(?:\s.*)?(?:\r?\n)?$', line)
        if match:
            marker = match[1]
            char = marker[0]
            if char == '<' and block is None:
                block = dict(start_line=number, marker_size=len(marker), ours=[], ancestor=[], theirs=[])
                side = 'ours'
            elif block is None or len(marker) != block['marker_size']:
                raise ValueError('unmatched conflict marker at line ' + str(number))
            elif char == '|' and side == 'ours':
                side = 'ancestor'
            elif char == '=' and side in ('ours', 'ancestor'):
                side = 'theirs'
            elif char == '>' and side == 'theirs':
                block['end_line'] = number
                result.append(block)
                block, side = None, None
            else:
                raise ValueError('invalid conflict marker order at line ' + str(number))
        elif block is not None:
            block[side].append(line)
    if block is not None:
        raise ValueError('unterminated conflict block')
    return result


def owned_stash(cwd, token, before_stash):
    if not re.fullmatch(r'sync-base:[a-f0-9]{32}', token):
        raise ValueError('stash token must contain an execution-owned UUID hex')
    before = git(cwd, 'rev-parse', '--verify', before_stash + '^{commit}').decode().strip()
    records = git(cwd, 'reflog', 'show', '--format=%H%x00%gs%x00', 'refs/stash').split(b'\0')
    candidates = set()
    for i in range(0, len(records) - 1, 2):
        oid, subject = records[i].strip().decode(), records[i + 1].decode()
        if subject.endswith(': ' + token):
            parents = git(cwd, 'show', '-s', '--format=%P', oid).decode().split()
            message = git(cwd, 'show', '-s', '--format=%s', oid).decode().strip()
            if len(parents) not in (2, 3) or parents[0] != before or not message.endswith(': ' + token):
                raise ValueError('stash identity/parent mismatch')
            candidates.add(oid)
    if len(candidates) != 1:
        raise ValueError('owned stash was not uniquely identified; preserve receipt and do not apply top stash')
    return dict(status='IDENTIFIED', oid=candidates.pop(), token=token, before_stash=before)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['state', 'targets', 'hunks', 'stash'])
    parser.add_argument('--cwd', default='.')
    parser.add_argument('--file')
    parser.add_argument('--configured', help='JSON array of configured swaggerVersionFiles')
    parser.add_argument('--before-merge', help='Saved pre-merge HEAD, preserved on resume')
    parser.add_argument('--token')
    parser.add_argument('--before-stash')
    args = parser.parse_args()
    try:
        if args.action == 'stash':
            if not args.token or not args.before_stash:
                raise ValueError('--token and --before-stash required')
            result = owned_stash(args.cwd, args.token, args.before_stash)
        elif args.action == 'hunks':
            if not args.file:
                raise ValueError('--file required')
            with open(args.file, newline='') as stream:
                result = dict(hunks=hunks(stream.read()))
        else:
            result = state(args.cwd) if args.action == 'state' else targets(args.cwd, json.loads(args.configured) if args.configured else None, args.before_merge)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if result.get('status', '').startswith('BLOCKED:') else 0
    except (OSError, ValueError) as exc:
        print('BLOCKED:SYNC_STATE: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
