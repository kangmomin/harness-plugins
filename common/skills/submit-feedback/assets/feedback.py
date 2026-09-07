#!/usr/bin/env python3
"""Local feedback artifacts, one destination mapping, and transport decisions."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def segment(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', value):
        raise ValueError('invalid single path segment')
    return value


def normalize(data):
    plugin = segment(data['plugin'])
    day = data['date']
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('canonical ISO date required')
    if not isinstance(data.get('items'), list):
        raise ValueError('items must be a list')
    items = []
    for item in data['items']:
        if item['target_type'] not in ('skill', 'agent', 'common'):
            raise ValueError('unknown target type')
        name = segment(item['target_name'])
        values = {key: item.get(key, '') for key in ('summary', 'context', 'proposal', 'generality', 'condition')}
        if any(not isinstance(v, str) for v in values.values()) or not values['summary'].strip() or not values['proposal'].strip():
            raise ValueError('summary/proposal and string fields required')
        if '\n' in values['summary'] or '\r' in values['summary']:
            raise ValueError('summary must be a single line')
        if values['generality'] not in ('범용', '특정 조건', '프로젝트 한정'):
            raise ValueError('invalid generality')
        items.append({'target_type': item['target_type'], 'target_name': name, **values})
    return {'plugin': plugin, 'date': day, 'items': items}


def identity(day, item):
    return digest(json.dumps([day, item['target_type'], item['target_name'], item['summary']], ensure_ascii=False).encode())


def destination(data, item):
    """The only mapping used for previews and actual checkout writes."""
    kind, name = item['target_type'], item['target_name']
    if kind == 'common':
        slug = re.sub(r'[^a-z0-9]+', '-', item['summary'].lower()).strip('-')[:40] or 'feedback'
        tail = f"common/{data['date']}-{slug}-{identity(data['date'], item)[:12]}.md"
    else:
        tail = {'skill': 'skills', 'agent': 'agents'}[kind] + '/' + name + '.md'
    return data['plugin'] + '/community-feedback/' + tail


def section(data, item):
    return (f"\n<!-- feedback:{identity(data['date'], item)} -->\n## {data['date']}\n\n"
            f"**대상**: {item['target_type']}:{item['target_name']}\n"
            f"**요지**: {item['summary']}\n**범용성**: {item['generality']}\n"
            f"**조건**: {item['condition']}\n\n### 컨텍스트\n{item['context']}\n\n### 제안\n{item['proposal']}\n")


def prepare(data, artifact_root):
    data = normalize(data)
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='feedback-', dir=root))
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    # Private durable artifact is separate from active overrides. Never apply a
    # failed submission's proposals as executable local instructions.
    fd = os.open(run / 'payload.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    return {'status': 'LOCAL_SAVED', 'artifact': str(run / 'payload.json'), 'sha256': digest(encoded),
            'destinations': sorted({destination(data, item) for item in data['items'] if item['generality'] != '프로젝트 한정'})}


def load(receipt):
    path = Path(receipt['artifact'])
    if path.is_symlink() or not path.is_file():
        raise ValueError('artifact missing or symlink')
    content = path.read_bytes()
    if digest(content) != receipt['sha256']:
        raise ValueError('artifact changed since local save')
    return normalize(json.loads(content))


def apply(receipt, checkout):
    data = load(receipt)
    root = Path(checkout).resolve(strict=True)
    pending, added = {}, 0
    for item in data['items']:
        if item['generality'] == '프로젝트 한정':
            continue
        relative = destination(data, item)
        path = root / relative
        for parent in [*path.parents, path]:
            if parent == root:
                continue
            if root in parent.parents and parent.is_symlink():
                raise ValueError('checkout destination has symlink: ' + relative)
        if path.exists() and not path.is_file():
            raise ValueError('checkout destination is not a file: ' + relative)
        original = pending.get(relative, path.read_text() if path.exists() else '')
        marker = f"<!-- feedback:{identity(data['date'], item)} -->"
        # Recognize the old published format too; exact entry fields only.
        prior = [original]
        if item['target_type'] == 'common' and path.parent.exists():
            for legacy_path in path.parent.glob(data['date'] + '-*.md'):
                if legacy_path.is_symlink() or not legacy_path.is_file():
                    raise ValueError('legacy common destination is not a regular file')
                prior.append(legacy_path.read_text())
        legacy = any(f"**대상**: {item['target_type']}:{item['target_name']}\n" in block and
                     f"**요지**: {item['summary']}\n" in block
                     for source in prior for block in re.findall(r'(?m)^## ' + re.escape(data['date']) + r'\n(.*?)(?=^## |\Z)', source, re.S | re.M))
        if marker in original or legacy:
            continue
        if not original:
            original = f"---\ntarget: {item['target_type']}:{item['target_name']}\ncreated: {data['date']}\n---\n\n# Community Feedback\n"
        pending[relative] = original + section(data, item)
        added += 1
    # Validate every destination before the first write. This runs only inside
    # the owned temporary clone, never in the user's working checkout.
    for relative, content in pending.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return {'status': 'NO_CHANGES' if not added else 'READY', 'added': added, 'paths': sorted(pending)}


def outcome(stage, result, added=0):
    """Choose the next authorized stage. UNKNOWN never means safe to retry."""
    if stage not in ('auth', 'fork', 'clone', 'apply', 'commit', 'push', 'pr'):
        raise ValueError('unknown stage')
    if result not in ('ACK', 'FAILED', 'UNKNOWN', 'EXISTS_MATCH', 'EXISTS_OTHER'):
        raise ValueError('unknown result')
    if type(added) is not int or added < 0:
        raise ValueError('invalid added count')
    if result == 'EXISTS_MATCH' and stage == 'pr':
        return {'status': 'ALREADY_SUBMITTED', 'next': None, 'preserve_artifact': True}
    if result != 'ACK':
        return {'status': 'UNKNOWN' if result == 'UNKNOWN' else 'LOCAL_ONLY', 'next': None,
                'preserve_artifact': True, 'readback_required': stage in ('push', 'pr') and result == 'UNKNOWN'}
    if stage in ('apply', 'commit', 'push', 'pr') and added == 0:
        return {'status': 'NO_CHANGES', 'next': None, 'preserve_artifact': True}
    stages = ['auth', 'fork', 'clone', 'apply', 'commit', 'push', 'pr']
    next_stage = stages[stages.index(stage) + 1] if stage != 'pr' else None
    return {'status': 'SUBMITTED' if stage == 'pr' else 'READY', 'next': next_stage, 'preserve_artifact': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'outcome'])
    parser.add_argument('input', help='JSON file or -')
    args = parser.parse_args()
    try:
        data = json.load(sys.stdin) if args.input == '-' else json.loads(Path(args.input).read_text())
        if args.action == 'prepare':
            result = prepare(data['payload'], data['artifact_root'])
        elif args.action == 'apply':
            result = apply(data['receipt'], data['checkout'])
        else:
            result = outcome(data['stage'], data['result'], data.get('added', 0))
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)})); return 2


if __name__ == '__main__':
    sys.exit(main())
