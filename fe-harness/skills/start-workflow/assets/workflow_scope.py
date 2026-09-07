#!/usr/bin/env python3
"""Root-relative scope: frozen task start through current worktree and index."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


class ScopeError(ValueError):
    pass


def git(cwd, *args):
    result = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ScopeError('git ' + args[0] + ' failed: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def root_dir(cwd):
    return Path(os.fsdecode(git(cwd, 'rev-parse', '--show-toplevel').rstrip(b'\n')))


def commit(root, ref):
    return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def names(raw):
    return {os.fsdecode(p) for p in raw.split(b'\0') if p}


def paths(value):
    if not isinstance(value, list) or any(not isinstance(p, str) or not p or '\0' in p for p in value):
        raise ScopeError('owned paths must be a JSON string array')
    if len(value) != len(set(value)):
        raise ScopeError('duplicate owned paths')
    for path in value:
        pure = PurePosixPath(path)
        if pure.is_absolute() or '..' in pure.parts or str(pure) != path or pure.parts[0] == '.git':
            raise ScopeError('owned paths must be normalized repository-relative paths')
    return set(value)


def scope(cwd, start_sha, owned, base_ref=None):
    root = root_dir(cwd)
    if bool(start_sha) == bool(base_ref):
        raise ScopeError('supply exactly one of start_sha or base_ref')
    head = commit(root, 'HEAD')
    if start_sha:
        start = commit(root, start_sha)
        git(root, 'merge-base', '--is-ancestor', start, head)
        origin = 'START_SHA'
    else:
        base_commit = commit(root, base_ref)
        start = git(root, 'merge-base', base_commit, head).decode().strip()
        origin = 'merge-base:' + base_ref
    owned = paths(owned)
    # Literal NUL-delimited paths, no pathspec interpolation or clean/dirty branch.
    options = ('--no-ext-diff', '--no-textconv', '--no-renames')
    working = names(git(root, 'diff', *options, '--name-only', '-z', start, '--'))
    staged = names(git(root, 'diff', '--cached', *options, '--name-only', '-z', start, '--'))
    untracked = names(git(root, 'ls-files', '--others', '--exclude-standard', '-z'))
    files = sorted(working | staged | (owned & untracked))
    read, deleted, links = [], [], []
    for name in files:
        target = root / name
        if target.is_symlink():
            links.append(dict(path=name, target=os.readlink(target)))
        elif target.is_file():
            read.append(name)
        elif target.is_dir():
            # E.g. submodule: review the Git diff and delegate its own repository scope.
            continue
        else:
            deleted.append(name)
    patch = git(root, 'diff', *options, '--binary', start, '--')
    index_patch = git(root, 'diff', '--cached', *options, '--binary', start, '--')
    digest = hashlib.sha256(patch + b'\0INDEX\0' + index_patch)
    for name in sorted(owned & untracked):
        target = root / name
        content = os.fsencode(os.readlink(target)) if target.is_symlink() else target.read_bytes()
        encoded = os.fsencode(name)
        digest.update(len(encoded).to_bytes(8, 'big') + encoded + len(content).to_bytes(8, 'big') + content)
    if commit(root, 'HEAD') != head:
        raise ScopeError('HEAD moved during scope collection; collect again')
    return dict(schema_version=1, root=str(root), start_sha=start, origin=origin, head=head,
                paths=files, read=read, deleted=deleted, symlinks=links,
                owned_untracked=sorted(owned & untracked), unowned_untracked=sorted(untracked - owned),
                staged_paths=sorted(staged), worktree_paths=sorted(working),
                content_sha256=digest.hexdigest(), patch=patch.decode(errors='surrogateescape'),
                index_patch=index_patch.decode(errors='surrogateescape'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--start-sha')
    parser.add_argument('--base-ref', help='Standalone only: explicit/resolved PR base, never the branch upstream by default')
    parser.add_argument('--owned-files', required=True, help='Run-owned root-relative paths JSON array; [] is explicit')
    parser.add_argument('--out', help='Run-owned JSON artifact, refreshed each iteration by the orchestrator')
    args = parser.parse_args()
    try:
        result = scope(args.cwd, args.start_sha, json.loads(Path(args.owned_files).read_text()), args.base_ref)
        output = json.dumps(result, ensure_ascii=True, indent=2) + '\n'
        if args.out:
            destination = Path(args.out)
            if not destination.is_absolute() or destination.is_symlink():
                raise ScopeError('out must be an absolute, run-owned regular artifact path')
            destination.write_text(output)
        else:
            print(output, end='')
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('BLOCKED:REVIEW_SCOPE — ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
