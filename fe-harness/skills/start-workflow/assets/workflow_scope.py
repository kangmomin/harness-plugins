#!/usr/bin/env python3
"""Root-relative scope: frozen task start through current worktree and index."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
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
        if not pure.parts or pure.is_absolute() or '..' in pure.parts or str(pure) != path or pure.parts[0] == '.git':
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


def ocr_json(executable, root, *args):
    result = subprocess.run(
        [executable, 'delegate', *args], cwd=root, capture_output=True,
        text=True, encoding='utf-8', timeout=30,
        env={**os.environ, 'OCR_NO_UPDATE': '1'},
    )
    if result.returncode:
        raise ValueError('OCR command failed: exit ' + str(result.returncode))
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get('schema_version') != '1':
        raise ValueError('unsupported OCR delegation schema')
    return data


def ocr_context(collected):
    context = dict(status='no_files', selected_paths=[], uncovered_paths=list(collected['paths']),
                   groups=[], previews=[], warnings=[])
    root = Path(collected['root'])
    unowned = set(collected['unowned_untracked'])
    readable = []
    for name in collected['read']:
        if name in unowned:
            continue
        target = root / name
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != root and root in parent.parents):
            context['warnings'].append('symlink path excluded from OCR: ' + name)
        else:
            readable.append(name)
    if not readable:
        return context
    executable = shutil.which('ocr')
    if not executable:
        context.update(status='unavailable', error='OCR executable not installed')
        return context
    allowed, selected = set(collected['paths']), set()
    try:
        modes = []
        if collected['start_sha'] != collected['head']:
            modes.append(('range', ['--from', collected['start_sha'], '--to', collected['head']]))
        if collected['unowned_untracked'] or collected['symlinks'] or len(readable) != len(collected['read']):
            context['warnings'].append('workspace preview skipped: unowned untracked or symlink paths')
        else:
            modes.append(('workspace', []))
        for mode, refs in modes:
            data = ocr_json(executable, root, 'preview', '--repo', str(root), '--format', 'json', *refs)
            if data.get('mode') != mode or data.get('repository') != str(root):
                raise ValueError('OCR preview repository or mode mismatch')
            if mode == 'range' and any(data.get(key) != collected[value] for key, value in
                                       [('from', 'start_sha'), ('to', 'head'), ('merge_base', 'start_sha')]):
                raise ValueError('OCR preview range mismatch')
            preview = dict(mode=mode, reviewable_paths=[], excluded_paths=[])
            seen = set()
            for key in ('reviewable_files', 'excluded_files'):
                entries = data.get(key)
                if not isinstance(entries, list):
                    raise ValueError('invalid OCR preview files')
                for item in entries:
                    if not isinstance(item, dict):
                        raise ValueError('invalid OCR preview entry')
                    name = item.get('path')
                    paths([name])
                    if name in seen:
                        raise ValueError('duplicate OCR preview path')
                    seen.add(name)
                    if name not in allowed or name in unowned:
                        continue
                    if key == 'reviewable_files':
                        preview['reviewable_paths'].append(name)
                        selected.add(name)
                    else:
                        reason = item.get('exclude_reason')
                        if not isinstance(reason, str):
                            raise ValueError('invalid OCR exclusion reason')
                        preview['excluded_paths'].append(dict(path=name, reason=reason))
            context['previews'].append(preview)
        selected = sorted(selected.intersection(readable))
        if not selected:
            return context
        data = ocr_json(executable, root, 'rule', '--repo', str(root), '--format', 'json', '--', *selected)
        groups = data.get('groups')
        if not isinstance(groups, list):
            raise ValueError('invalid OCR rule groups')
        covered, identities = set(), set()
        for group in groups:
            if not isinstance(group, dict) or type(group.get('group_id')) is not int or group['group_id'] <= 0:
                raise ValueError('invalid OCR rule group identity')
            if group['group_id'] in identities:
                raise ValueError('duplicate OCR rule group identity')
            identities.add(group['group_id'])
            if any(not isinstance(group.get(key), str) for key in ('source', 'pattern', 'rule')):
                raise ValueError('invalid OCR rule text')
            members = paths(group.get('files'))
            if not members or not members <= set(selected) or members & covered:
                raise ValueError('OCR rule group paths mismatch')
            covered.update(members)
        if covered != set(selected):
            raise ValueError('incomplete OCR rule coverage')
        context.update(status='ready', selected_paths=selected,
                       uncovered_paths=sorted(allowed - set(selected)),
                       groups=[{key: group[key] for key in ('group_id', 'source', 'pattern', 'files', 'rule')} for group in groups])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        context.update(status='error', selected_paths=[], groups=[], error=str(exc))
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--start-sha')
    parser.add_argument('--base-ref', help='Standalone only: explicit/resolved PR base, never the branch upstream by default')
    parser.add_argument('--owned-files', required=True, help='Run-owned root-relative paths JSON array; [] is explicit')
    parser.add_argument('--out', help='Run-owned JSON artifact, refreshed each iteration by the orchestrator')
    parser.add_argument('--patch-dir', help='New absolute run directory for readable patches; requires --out')
    parser.add_argument('--ocr', action='store_true', help='OCR delegation 보조 규칙을 수집한다; 필수 scope 판정은 유지한다')
    args = parser.parse_args()
    try:
        owned = json.loads(Path(args.owned_files).read_text())
        result = scope(args.cwd, args.start_sha, owned, args.base_ref)
        if args.ocr:
            result['ocr'] = ocr_context(result)
            current = scope(args.cwd, args.start_sha, owned, args.base_ref)
            if any(current[key] != result[key] for key in ('root', 'start_sha', 'head', 'content_sha256')):
                raise ScopeError('scope changed during OCR collection; collect again')
        if args.patch_dir:
            directory = Path(args.patch_dir)
            if not args.out or not directory.is_absolute() or directory.resolve().is_relative_to(Path(result['root']).resolve()):
                raise ScopeError('patch-dir requires --out and an absolute directory outside the repository')
            if directory.resolve() != directory or Path(args.out).resolve().parent != directory:
                raise ScopeError('out must be inside patch-dir; symlink directories are not allowed')
            # One directory per review attempt: a later collection cannot overwrite reviewed evidence.
            directory.mkdir(parents=True, exist_ok=False)
            for key in ('patch', 'index_patch'):
                destination = directory / (key + '.diff')
                payload = result.pop(key).encode('utf-8', errors='surrogateescape')
                destination.write_bytes(payload)
                result[key + '_file'] = str(destination)
                result[key + '_sha256'] = hashlib.sha256(payload).hexdigest()
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
