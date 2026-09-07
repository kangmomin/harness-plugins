#!/usr/bin/env python3
"""Render help data from caller-provided session metadata; never invent a call."""
import argparse
import json
from pathlib import Path
import sys

FILTERS = {'--be': 'be', '--fe': 'fe', '--mm': 'mm', '--hd': 'hd'}


def catalog(data):
    entries = data.get('skills')
    if not isinstance(entries, list):
        raise ValueError('actual session skills metadata required')
    selector = data.get('filter')
    if selector is not None and selector not in FILTERS:
        raise ValueError('unknown capability filter')
    rows, names, verified_filter = [], set(), False
    for skill in entries:
        if not isinstance(skill, dict):
            raise ValueError('skill metadata must be an object')
        name, description = skill.get('name'), skill.get('description')
        if not isinstance(name, str) or not name.strip() or not isinstance(description, str):
            raise ValueError('exact session name and description required')
        if name in names:
            raise ValueError('ambiguous duplicate session name: ' + name)
        names.add(name)
        plugin, _, local = name.rpartition(':')
        local = local or name
        roles = skill.get('roles', [])
        if not isinstance(roles, list) or any(role not in FILTERS.values() for role in roles):
            raise ValueError('invalid verified roles')
        if roles and not skill.get('roles_source'):
            raise ValueError('role annotation needs a metadata/manifest evidence source')
        if selector and FILTERS[selector] in roles:
            verified_filter = True
        if selector and FILTERS[selector] not in roles:
            continue
        if data.get('plugin') and data['plugin'] != plugin:
            continue
        if data.get('skill') and data['skill'] not in (name, local):
            continue
        # The host supplies the rendered invocation, if available. A file path or
        # a familiar namespace is never sufficient to guess a slash/dollar call.
        invocation = skill.get('invocation')
        if invocation is not None and (not isinstance(invocation, str) or not invocation.strip()):
            raise ValueError('invalid invocation metadata')
        rows.append({'name': name, 'plugin': plugin or '(unscoped)', 'skill': local,
                     'description': description, 'argument_hint': skill.get('argument_hint', ''),
                     'invocation': invocation, 'roles': roles,
                     'entrypoint': local == 'start-workflow'})
    return {'status': 'READY' if rows else 'UNVERIFIED_FILTER' if selector and not verified_filter else 'NO_MATCH',
            'skills': rows, 'entrypoints': [r['name'] for r in rows if r['entrypoint']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='JSON file or - for stdin')
    args = parser.parse_args()
    try:
        data = json.load(sys.stdin) if args.input == '-' else json.loads(Path(args.input).read_text())
        print(json.dumps(catalog(data), ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({'status': 'BLOCKED:METADATA', 'reason': str(exc)})); return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
