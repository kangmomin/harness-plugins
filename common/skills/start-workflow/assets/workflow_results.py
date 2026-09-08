#!/usr/bin/env python3
"""Version 1 verification evidence. One orchestrator serially records agent results.

Commands: tree --cwd DIR; validate FILE; init --out FILE --run-id ID --domain
be|fe|fs --mode build|analyze|verify --cwd DIR. JSON is authoritative; Markdown
is a view. Never reconstruct a successful terminal result from prose.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

KINDS = {'unit', 'integration', 'e2e', 'readback', 'lint', 'typecheck', 'build', 'pr'}
VERDICTS = {'PASS', 'WARN', 'FAIL', 'INCONCLUSIVE', 'PARTIAL', 'SKIPPED'}
DOMAINS = {'be', 'fe', 'fs'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def terminal(value):
    return value in ('DONE', 'RUNNING') or isinstance(value, str) and value.startswith(('BLOCKED:', 'SKIPPED:'))


def tree_valid(value):
    if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in ('head', 'content_sha256')):
        return False
    if not re.fullmatch(r'[0-9a-f]{40,64}', value['head']) or not re.fullmatch(r'[0-9a-f]{64}', value['content_sha256']):
        return False
    if 'fingerprint_version' not in value:
        return 'head_sensitive' not in value
    return type(value['fingerprint_version']) is int and value['fingerprint_version'] == 2 and type(value.get('head_sensitive')) is bool


def same_tree(recorded, current):
    if not tree_valid(recorded) or not tree_valid(current):
        return False
    if recorded.get('fingerprint_version') != 2 or current.get('fingerprint_version') != 2:
        return recorded == current
    return recorded['content_sha256'] == current['content_sha256'] and (
        not (recorded['head_sensitive'] or current['head_sensitive']) or recorded['head'] == current['head'])


def tested_tree(cwd, include_head=False):
    location = cwd
    def git(*args):
        result = subprocess.run(['git', '-C', str(location), *args], capture_output=True, check=True, timeout=30)
        return result.stdout
    root = Path(os.fsdecode(git('rev-parse', '--show-toplevel').rstrip(b'\n')))
    location = root
    head = git('rev-parse', 'HEAD').decode().strip()
    names = set(git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0'))
    gitlinks = set()
    for entry in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            names.add(name)
            if metadata.startswith(b'160000 '):
                gitlinks.add(name)
    for entry in git('ls-files', '--stage', '-z').split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            require(metadata.split()[2] == b'0', 'unmerged index entry')
            if metadata.startswith(b'160000 '):
                gitlinks.add(name)
    digest = hashlib.sha256(b'harness-worktree-v2\0')
    for name in sorted(names - {b''}):
        target = root / os.fsdecode(name)
        require(not any(parent.is_symlink() for parent in target.parents if parent != root and root in parent.parents),
                'symlink parent in tracked path: ' + os.fsdecode(name))
        try:
            mode = target.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            continue
        if stat.S_ISLNK(mode):
            kind, content = b'120000', os.fsencode(os.readlink(target))
        elif stat.S_ISREG(mode):
            kind = b'100755' if mode & 0o111 else b'100644'
            content = target.read_bytes()
        elif stat.S_ISDIR(mode) and name in gitlinks:
            require((target / '.git').exists(), 'uninitialized submodule: ' + os.fsdecode(name))
            child_root = Path(os.fsdecode(git('-C', str(target), 'rev-parse', '--show-toplevel').rstrip(b'\n')))
            require(child_root.resolve() == target.resolve(), 'invalid submodule worktree: ' + os.fsdecode(name))
            child = tested_tree(target, include_head=True)
            kind, content = b'160000', (child['head'] + ':' + child['content_sha256']).encode('ascii')
        elif stat.S_ISDIR(mode):
            continue  # A tracked file replaced by a directory is represented by its actual child files.
        else:
            raise ValueError('unsupported file type: ' + os.fsdecode(name))
        for field in (name, kind, content):
            digest.update(len(field).to_bytes(8, 'big') + field)
    require(git('rev-parse', 'HEAD').decode().strip() == head, 'HEAD changed during fingerprint')
    return {'head': head, 'content_sha256': digest.hexdigest(), 'fingerprint_version': 2, 'head_sensitive': include_head}


def event_key(event):
    return event['domain'], event['kind'], event.get('case_id'), event['iteration']


def validate(data, run_id=None):
    require(isinstance(data, dict) and data.get('schema_version') == 1, 'unsupported result schema_version')
    require(nonempty(data.get('run_id')), 'run_id required')
    require(run_id is None or data['run_id'] == run_id, 'result run_id mismatch')
    require(data.get('mode') in ('build', 'analyze', 'verify') and data.get('domain') in DOMAINS, 'result mode/domain invalid')
    require(terminal(data.get('terminal_state')), 'result terminal_state invalid')
    require(tree_valid(data.get('tested_tree')), 'result tested_tree invalid')
    for key in ('targets', 'cases', 'events', 'fixes'):
        require(isinstance(data.get(key), list), key + ' must be an array')
    targets, cases, events, fixes = {}, {}, {}, set()
    for target in data['targets']:
        require(isinstance(target, dict) and all(nonempty(target.get(k)) for k in ('target_id', 'protocol', 'operation')), 'target identity required')
        require(target['target_id'] not in targets, 'duplicate target_id')
        require(type(target.get('supported')) is bool, 'target supported boolean required')
        require(target['supported'] or nonempty(target.get('reason')), 'unsupported target reason required')
        require(target['protocol'] in ('HTTP', 'GRPC') or not target['supported'], 'unknown protocol cannot be supported')
        if target['protocol'] == 'HTTP':
            require(bool(re.fullmatch(r'(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /\S*', target['operation'])), 'HTTP operation must be METHOD /path')
        targets[target['target_id']] = target
    for case in data['cases']:
        require(isinstance(case, dict) and all(nonempty(case.get(k)) for k in ('case_id', 'target_id', 'category', 'name')), 'case identity required')
        require(case['case_id'] not in cases and case['target_id'] in targets, 'duplicate case_id or unknown target_id')
        cases[case['case_id']] = case
    for event in data['events']:
        require(isinstance(event, dict) and event.get('domain') in DOMAINS and event.get('kind') in KINDS, 'event domain/kind invalid')
        require(data['domain'] == 'fs' or event['domain'] == data['domain'], 'event outside run domain')
        require(nonempty(event.get('phase')) and type(event.get('iteration')) is int and event['iteration'] > 0, 'event phase/iteration required')
        require(event.get('verdict') in VERDICTS and terminal(event.get('terminal_state')), 'event verdict/terminal_state invalid')
        require(event['verdict'] != 'PASS' or event['terminal_state'] == 'DONE', 'PASS requires a completed event')
        require(tree_valid(event.get('tested_tree')), 'event tested_tree required')
        key = event_key(event)
        require(key not in events, 'conflicting duplicate event key')
        if event['kind'] in ('unit', 'integration'):
            require(type(event.get('regression_count')) is int and event['regression_count'] >= 0, event['kind'] + ' regression_count required')
            require(event['verdict'] != 'PASS' or event['regression_count'] == 0, 'PASS conflicts with regressions')
        if event['kind'] == 'e2e':
            require(event.get('case_id') in cases, 'unknown e2e case_id')
            target = targets[cases[event['case_id']]['target_id']]
            require(event.get('protocol') == target['protocol'], 'case protocol differs from target')
            require(all(nonempty(event.get(k)) for k in ('request', 'expected', 'actual')), 'e2e request/expected/actual required')
            require(type(event.get('server_contact')) is bool and type(event.get('client_error')) is bool, 'e2e contact/client_error booleans required')
            require(not event['client_error'] or not event['server_contact'], 'client parsing failure cannot prove server contact')
            if event['protocol'] == 'GRPC':
                require(event.get('streaming') in ('unary', 'server', 'client', 'bidi'), 'gRPC streaming mode required')
                require(event.get('deadline') is None or isinstance(event['deadline'], (str, int, float)), 'gRPC deadline evidence invalid')
                require(event.get('status_origin') in ('server', 'client', 'unknown', 'none'), 'gRPC status_origin required')
                if event['status_origin'] == 'server':
                    require(event['server_contact'] and nonempty(event.get('server_status')), 'server status requires server evidence')
                else:
                    require(event.get('server_status') is None, 'client/unknown status cannot be a server_status')
                require(event['verdict'] != 'PASS' or event['status_origin'] == 'server', 'gRPC PASS requires server result')
            require(event['verdict'] != 'PASS' or target['supported'] and event['server_contact'] and not event['client_error'], 'PASS lacks supported server-call evidence')
        else:
            require(event.get('case_id') is None, 'non-e2e event cannot name a case')
        events[key] = event
    for fix in data['fixes']:
        require(isinstance(fix, dict) and all(nonempty(fix.get(k)) for k in ('domain', 'phase', 'case_id', 'cause', 'change', 'attribution', 'rebuild')), 'fix fields required')
        require(type(fix.get('iteration')) is int, 'fix iteration required')
        key = fix['domain'], 'e2e', fix['case_id'], fix['iteration']
        require(key in events and key not in fixes, 'unknown or duplicate fix case/iteration')
        require(events[key]['phase'] == fix['phase'] and events[key]['verdict'] == 'FAIL', 'fix must reference that failed phase/attempt')
        fixes.add(key)
    # Final passing evidence must describe the final tested tree, never a prior build.
    for event in latest(data).values():
        if event['verdict'] == 'PASS' and data['terminal_state'] == 'DONE':
            require(same_tree(event['tested_tree'], data['tested_tree']), 'final PASS describes a different tested tree')
    return data


def publish_text(directory, basename, content):
    """Atomic no-overwrite publication. Unsupported hard links are an error."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.harness-report-', suffix='.tmp', dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        sequence = 1
        while True:
            target = directory / (basename + ('' if sequence == 1 else '-%d' % sequence) + '.md')
            try:
                os.link(temporary, target)
                return target.resolve()
            except FileExistsError:
                sequence += 1
    finally:
        if temporary is not None:
            temporary.unlink()


def latest(data):
    result = {}
    for event in data['events']:
        key = event['domain'], event['kind'], event.get('case_id')
        if key not in result or event['iteration'] > result[key]['iteration']:
            result[key] = event
    return result


def test_summary(data, required=()):
    validate(data)
    require(set(required) <= {'unit', 'integration'}, 'unknown required test suite')
    events = [event for event in latest(data).values() if event['kind'] in ('unit', 'integration')]
    for kind in required:
        require(any(event['kind'] == kind for event in events), 'missing required verification: ' + kind)
    if not events:
        verdict = 'INCONCLUSIVE'
    elif any(event['verdict'] in ('FAIL', 'INCONCLUSIVE', 'PARTIAL') or event['regression_count'] > 0 or
             event['terminal_state'] == 'RUNNING' or event['terminal_state'].startswith('BLOCKED:') or
             event['verdict'] == 'SKIPPED' and not event['terminal_state'].startswith('SKIPPED:') for event in events):
        verdict = 'FAIL'
    elif any(event['verdict'] == 'WARN' for event in events):
        verdict = 'WARN'
    elif all(event['verdict'] == 'SKIPPED' for event in events):
        verdict = 'SKIPPED'
    else:
        verdict = 'PASS'
    return {'verdict': verdict, 'regression_count': sum(event['regression_count'] for event in events), 'suites': events}


def load(filename, run_id=None):
    with open(filename, encoding='utf-8') as stream:
        return validate(json.load(stream), run_id)


def check_current(data, current, required):
    """Freshness gate before PR/commit; existing verdict policy remains separate."""
    validate(data)
    require(tree_valid(current), 'invalid current tree')
    require(set(required) <= KINDS - {'pr'}, 'unknown required verification kind')
    events = [e for e in latest(data).values() if e['kind'] != 'pr']
    for kind in required:
        require(any(e['kind'] == kind for e in events), 'missing required verification: ' + kind)
    for event in events:
        label = event['domain'] + ':' + event['kind'] + ':' + str(event.get('case_id'))
        require(same_tree(event['tested_tree'], current), 'stale verification: ' + label)
        require(event['terminal_state'] != 'RUNNING', 'unfinished verification: ' + label)
    require(same_tree(data['tested_tree'], current), 'result tree is not the current tree')
    return {'current': True, 'run_id': data['run_id'], 'checks': len(events),
            'note': 'freshness only; FAIL/BLOCKED and required-case coverage still govern publication'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    tree = sub.add_parser('tree')
    tree.add_argument('--cwd', required=True)
    tree.add_argument('--include-head', action='store_true', help='Keep commit identity as a verification input')
    check = sub.add_parser('validate')
    check.add_argument('file')
    check.add_argument('--run-id')
    summary = sub.add_parser('test-summary')
    summary.add_argument('file')
    summary.add_argument('--run-id', required=True)
    summary.add_argument('--require', action='append', default=[])
    fresh = sub.add_parser('check-current')
    fresh.add_argument('file')
    fresh.add_argument('--run-id', required=True)
    fresh.add_argument('--cwd', required=True)
    fresh.add_argument('--require', action='append', default=[])
    fresh.add_argument('--include-head', action='store_true')
    init = sub.add_parser('init')
    for key in ('out', 'run-id', 'domain', 'mode', 'cwd'):
        init.add_argument('--' + key, required=True)
    init.add_argument('--include-head', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'tree':
            result = tested_tree(args.cwd, args.include_head)
        elif args.command == 'validate':
            data = load(args.file, args.run_id)
            result = {'valid': True, 'run_id': data['run_id'], 'events': len(data['events'])}
        elif args.command == 'check-current':
            result = check_current(load(args.file, args.run_id), tested_tree(args.cwd, args.include_head), args.require)
        elif args.command == 'test-summary':
            result = test_summary(load(args.file, args.run_id), args.require)
        else:
            result = validate({'schema_version': 1, 'run_id': args.run_id, 'domain': args.domain, 'mode': args.mode,
                'terminal_state': 'RUNNING', 'tested_tree': tested_tree(args.cwd, args.include_head), 'targets': [], 'cases': [], 'events': [], 'fixes': []})
            with open(args.out, 'x', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print('result error: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
