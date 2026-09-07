#!/usr/bin/env python3
"""Pure PR review/merge-state checks. This helper never invokes gh or writes remotely."""
import argparse
import json
from pathlib import Path
import re
import sys


def oid(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value))


def snapshot(data):
    if not isinstance(data, dict) or not oid(data.get('headRefOid')) or not oid(data.get('baseRefOid')):
        raise ValueError('PR identity/commit evidence missing')
    for key in ('id', 'url', 'headRefName', 'baseRefName'):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError('PR field missing: ' + key)
    if type(data.get('number')) is not int or data['number'] <= 0:
        raise ValueError('PR number missing')
    return {key: data[key] for key in ('id', 'number', 'url', 'headRefName', 'baseRefName', 'headRefOid', 'baseRefOid')}


def same_review(reviewed, current):
    expected, actual = snapshot(reviewed), snapshot(current)
    for key in expected:
        if expected[key] != actual[key]:
            raise ValueError('REVIEW_STALE: ' + key + ' changed; refresh the summary and applicable approval')
    if current.get('state') != 'OPEN':
        raise ValueError('PR_NOT_OPEN: inspect state before merging')
    return expected


def merge_command(reviewed, current, method):
    pin = same_review(reviewed, current)
    if method not in ('merge', 'squash', 'rebase'):
        raise ValueError('unknown merge method')
    # Deletion is separate, after remote MERGED confirmation.
    return ['gh', 'pr', 'merge', pin['url'], '--' + method, '--match-head-commit', pin['headRefOid']]


def outcome(reviewed, current, command_exit):
    pin = snapshot(reviewed)
    actual = snapshot(current)
    if pin['id'] != actual['id'] or pin['url'] != actual['url']:
        raise ValueError('PR_IDENTITY_MISMATCH')
    state = current.get('state')
    result = dict(command_exit=command_exit, url=pin['url'], delete_allowed=False, merge_sha=None)
    if state == 'MERGED':
        merge = current.get('mergeCommit')
        if not isinstance(merge, dict) or not oid(merge.get('oid')):
            raise ValueError('MERGED_WITHOUT_COMMIT_EVIDENCE: re-read the remote result')
        matches = actual['headRefOid'] == pin['headRefOid'] and actual['baseRefName'] == pin['baseRefName']
        result.update(status='MERGED' if matches else 'MERGED_DIFFERENT_REVIEW',
                      merge_sha=merge['oid'], delete_allowed=matches)
    elif state == 'OPEN':
        result['status'] = 'PENDING_AUTO_MERGE' if current.get('autoMergeRequest') else 'OPEN_UNCONFIRMED'
    elif state == 'CLOSED':
        result['status'] = 'CLOSED_UNMERGED'
    else:
        raise ValueError('UNKNOWN_REMOTE_STATE')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('snapshot', 'check-review', 'command', 'outcome'))
    p.add_argument('--current', required=True)
    p.add_argument('--reviewed')
    p.add_argument('--method', choices=('merge', 'squash', 'rebase'))
    p.add_argument('--command-exit', type=int)
    args = p.parse_args()
    try:
        current = json.loads(Path(args.current).read_text())
        reviewed = json.loads(Path(args.reviewed).read_text()) if args.reviewed else None
        if args.action == 'snapshot':
            result = snapshot(current)
        elif args.action == 'check-review':
            result = same_review(reviewed, current)
        elif args.action == 'command':
            result = dict(argv=merge_command(reviewed, current, args.method))
        else:
            if args.command_exit is None:
                raise ValueError('command-exit is required')
            result = outcome(reviewed, current, args.command_exit)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print('BLOCKED:MERGE_STATE — ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
