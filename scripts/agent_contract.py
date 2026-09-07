#!/usr/bin/env python3
"""Validate this repository's Claude plugin agent contracts (not SKILL fields)."""
import json
from pathlib import Path
import re
import sys

import yaml

READERS = {'code-analyzer', 'code-verifier', 'edge-case-analyzer',
           'scope-reviewer', 'workflow-reflection', 'a11y-reviewer', 'component-reviewer'}
FIELDS = {'name', 'description', 'tools', 'disallowedTools', 'model', 'skills',
          'maxTurns', 'effort', 'background', 'isolation', 'memory', 'initialPrompt'}


def tool_list(value):
    if isinstance(value, str):
        value = [item.strip() for item in value.split(',')]
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x for x in value):
        raise ValueError('nonempty tool list required')
    if len(value) != len(set(value)):
        raise ValueError('duplicate tools')
    return value


def validate(path):
    source = path.read_text()
    parts = source.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('frontmatter required')
    # Reject duplicate keys instead of silently accepting the last value.
    node = yaml.compose(parts[1])
    if not isinstance(node, yaml.MappingNode):
        raise ValueError('frontmatter must be an object')
    keys = [key.value for key, _ in node.value]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate frontmatter keys')
    meta = yaml.safe_load(parts[1])
    if set(meta) - FIELDS:
        raise ValueError('unsupported plugin agent fields: ' + ', '.join(sorted(set(meta) - FIELDS)))
    if meta.get('name') != path.stem or not re.fullmatch(r'[a-z][a-z0-9-]*', meta['name']):
        raise ValueError('agent name must match filename')
    if not isinstance(meta.get('description'), str) or not meta['description'].strip():
        raise ValueError('description required')
    allowed = tool_list(meta.get('tools'))
    denied = tool_list(meta['disallowedTools']) if 'disallowedTools' in meta else []
    if set(allowed) & set(denied):
        raise ValueError('contradictory tool rules')
    if path.stem in READERS and set(allowed) != {'Read', 'Glob', 'Grep'}:
        raise ValueError('read-only reviewer must use Read, Glob, Grep only')
    return {'name': meta['name'], 'tools': allowed, 'disallowedTools': denied}


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    output = []
    for path in sorted(root.glob('*/agents/*.md')):
        try:
            output.append({'path': str(path.relative_to(root)), **validate(path)})
        except (ValueError, yaml.YAMLError) as exc:
            raise SystemExit(f'{path}: {exc}') from exc
    if not output:
        raise SystemExit('no plugin agents found')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
