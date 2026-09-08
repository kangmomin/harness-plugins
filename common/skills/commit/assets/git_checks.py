#!/usr/bin/env python3
"""Read-only root/base resolution and fail-closed Assumption scanning."""
import argparse
import hashlib
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('git ' + args[0] + ' failed: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def repository(cwd):
    return Path(os.fsdecode(git(cwd, 'rev-parse', '--show-toplevel').rstrip(b'\n')))


def sha(root, ref):
    return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def base(cwd, ref):
    root = repository(cwd)
    resolved = sha(root, ref)
    # VERSION detection never decides whether the base is resolved.
    version_files = [name for name in ('VERSION', 'VERSION.txt') if (root / name).is_file()]
    return dict(root=str(root), base_ref=ref, base_sha=resolved,
                version_path=version_files[0] if len(version_files) == 1 else None,
                version_candidates=version_files, version_status='AMBIGUOUS' if len(version_files) > 1 else 'FOUND' if version_files else 'ABSENT')


def load_literals(filename):
    if not filename:
        return []
    def unique(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError('duplicate literal tag JSON key')
        return value
    rules = json.loads(Path(filename).read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(rules, list):
        raise ValueError('literal tags must be an array')
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {'path', 'line', 'sha256', 'reason'}:
            raise ValueError('literal tag requires path, line, sha256 and reason')
        path, number = rule['path'], rule['line']
        if not isinstance(path, str) or path in ('', '.') or '\0' in path or Path(path).is_absolute() or '..' in Path(path).parts or Path(path).as_posix() != path:
            raise ValueError('literal tag path must be an exact repository-relative file')
        if type(number) is not int or number < 1 or (path, number) in seen:
            raise ValueError('literal tag line must be positive and unique per path')
        if not isinstance(rule['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', rule['sha256']) or not isinstance(rule['reason'], str) or not rule['reason'].strip():
            raise ValueError('literal tag requires a raw-line SHA-256 and review reason')
        seen.add((path, number))
    return rules


def tag_record(raw, path, number, literals, excluded):
    tag = dict(path=path, line=number, text=raw.decode(errors='replace'))
    digest = hashlib.sha256(raw).hexdigest()
    for rule in literals:
        if (rule['path'], rule['line'], rule['sha256']) == (path, number, digest):
            excluded.append({**tag, 'sha256': digest, 'reason': rule['reason']})
            return None
    return tag


def hunk_tags(patch, path, literals=(), excluded=None):
    found, line_number, in_hunk = [], 0, False
    excluded = [] if excluded is None else excluded
    for line in patch.split(b'\n'):
        hunk = re.match(rb'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
        if hunk:
            line_number, in_hunk = int(hunk[1]), True
        elif in_hunk and line.startswith(b'+'):
            if b'[Assumption]' in line[1:]:
                tag = tag_record(line[1:], path, line_number, literals, excluded)
                if tag:
                    found.append(tag)
            line_number += 1
        elif in_hunk and line.startswith(b' '):
            line_number += 1
    return found


def worktree_tags(cwd, patterns, literals=()):
    root = repository(cwd)
    for pattern in patterns:
        if not pattern or pattern.startswith('/') or '..' in pattern.split('/') or '\0' in pattern:
            raise ValueError('path filters must stay within the repository')
    def selected(path):
        return not patterns or any(p == '.' or path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/') or
            not (root / p).exists() and not (root / p).is_symlink() and fnmatch.fnmatchcase(path, p) for p in patterns)
    untracked = {os.fsdecode(p) for p in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p}
    found, excluded = [], []
    for cached in ((), ('--cached',)):
        changed = git(root, 'diff', *cached, '--name-only', '--no-renames', '-z', 'HEAD', '--')
        for name in changed.split(b'\0'):
            path = os.fsdecode(name)
            if not name or not selected(path):
                continue
            patch = git(root, '--literal-pathspecs', 'diff', *cached, '--no-ext-diff', '--no-textconv', '--no-color', '--no-renames', '--unified=0', 'HEAD', '--', path)
            found.extend({**tag, 'source': 'index' if cached else 'worktree'} for tag in hunk_tags(patch, path, literals, excluded))
    for path in sorted(untracked):
        if selected(path):
            target = root / path
            if target.is_symlink():
                continue
            for number, line in enumerate(target.read_bytes().split(b'\n'), 1):
                if b'[Assumption]' in line:
                    tag = tag_record(line, path, number, literals, excluded)
                    if tag:
                        found.append({**tag, 'source': 'untracked'})
    return dict(status='DONE', root=str(root), patterns=patterns, tags=found, literal_tags=excluded)


def assumption_gate(cwd, base_ref, message_base, literals=()):
    root = repository(cwd)
    head, base_sha, message_sha = sha(root, 'HEAD'), sha(root, base_ref), sha(root, message_base)
    changes = git(root, 'diff', '--no-renames', '--name-only', '-z', base_sha + '...' + head, '--')
    code_tags, excluded = [], []
    for name in changes.split(b'\0'):
        if not name:
            continue
        path = os.fsdecode(name)
        patch = git(root, '--literal-pathspecs', 'diff', '--no-ext-diff', '--no-textconv', '--no-color', '--no-renames', '--unified=0', base_sha + '...' + head, '--', path)
        code_tags.extend(hunk_tags(patch, path, literals, excluded))
    raw = git(root, 'log', message_sha + '..' + head, '--format=%H%x00%B%x00')
    pieces, message_tags = raw.split(b'\0'), []
    for i in range(0, len(pieces) - 1, 2):
        commit_id = pieces[i].strip().decode('ascii')
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit_id):
            raise ValueError('INVALID_GIT_LOG_RECORD')
        body = pieces[i + 1].decode(errors='replace')
        if '[Assumption]' in body:
            message_tags.append(dict(commit=commit_id, message=body))
    if pieces[-1].strip():
        raise ValueError('INCOMPLETE_GIT_LOG_RECORD')
    if sha(root, 'HEAD') != head:
        raise ValueError('HEAD_CHANGED: scan again')
    return dict(status='PASS' if not code_tags and not message_tags else 'BLOCKED:ASSUMPTION_UNRESOLVED',
                root=str(root), head=head, base_sha=base_sha, message_base_sha=message_sha,
                code_tags=code_tags, message_tags=message_tags, literal_tags=excluded)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('base', 'assumptions', 'worktree'))
    p.add_argument('--cwd', required=True)
    p.add_argument('--base-ref')
    p.add_argument('--message-base')
    p.add_argument('--path', action='append', default=[], help='Same root-relative file/directory/glob filter for tracked and untracked')
    p.add_argument('--literal-tags', help='Reviewed exact path/line/raw-line SHA-256/reason JSON; never applies to commit messages')
    args = p.parse_args()
    try:
        if args.path and args.action != 'worktree':
            raise ValueError('--path applies only to worktree; branch Gate always scans the complete branch')
        if args.literal_tags and args.action == 'base':
            raise ValueError('--literal-tags applies only to tag scans')
        literals = load_literals(args.literal_tags)
        if args.action == 'worktree':
            result = worktree_tags(args.cwd, args.path, literals)
        elif not args.base_ref:
            raise ValueError('base-ref is required')
        elif args.action == 'base':
            result = base(args.cwd, args.base_ref)
        else:
            if not args.message_base:
                raise ValueError('message-base is required; absence is not an empty commit range')
            result = assumption_gate(args.cwd, args.base_ref, args.message_base, literals)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result.get('status', 'PASS') in ('PASS', 'DONE') else 1
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('BLOCKED:GIT_CHECK — ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
