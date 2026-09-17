#!/usr/bin/env python3
"""Active package/reference contracts. Executable behavior is tested separately."""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

import yaml
from agent_contract import validate as validate_agent

SKILL_FIELDS = {'name', 'description', 'allowed-tools', 'argument-hint', 'user-invocable',
                'disable-model-invocation', 'model', 'context', 'agent', 'metadata', 'license', 'compatibility'}
EXCLUDED_DIRS = {'node_modules', '__pycache__', 'community-feedback', '.git'}
EXAMPLE_LINKS = {
    'common/skills/start-workflow/references/contract-templates.md': {'범위 밖'},
    'minmos-harness/skills/api-share-note/SKILL.md': {'링크'},
}
MIGRATION_TABLES = {'minmos-harness/README.md', 'hyeondongs-harness/README.md'}
HISTORICAL_DOCS = ('doc-gen-', 'harness-audit-', 'harness-remediation-')


def manifest_paths(directory, data, require):
    def local(value, label, base=directory):
        if not isinstance(value, str) or not value:
            require(False, str(directory) + ': invalid ' + label); return None
        value = value.replace('${CLAUDE_PLUGIN_ROOT}', str(directory))
        candidate = (base / value).resolve()
        require(candidate.is_relative_to(directory.resolve()) and candidate.exists(), str(directory) + ': missing or escaping manifest path: ' + label + '=' + value)
        return candidate
    for key in ('skills', 'agents', 'commands', 'hooks'):
        if key in data and isinstance(data[key], (str, list)):
            for value in data[key] if isinstance(data[key], list) else [data[key]]:
                local(value, key)
    servers = data.get('mcpServers', {})
    if isinstance(servers, str):
        config = local(servers, 'mcpServers')
        if config and config.is_file():
            servers = json.loads(config.read_text()).get('mcpServers', {})
    if isinstance(servers, dict):
        for name, server in servers.items():
            if not isinstance(server, dict):
                require(False, str(directory) + ': invalid MCP server ' + name); continue
            cwd = local(server.get('cwd', '.'), name + '.cwd')
            command = server.get('command', '')
            if isinstance(command, str) and command.startswith(('./', '../', '${CLAUDE_PLUGIN_ROOT}')):
                local(command, name + '.command', cwd or directory)
            for arg in server.get('args', []):
                if isinstance(arg, str) and arg.startswith(('./', '../', '${CLAUDE_PLUGIN_ROOT}')):
                    local(arg, name + '.arg', cwd or directory)


def documents(root):
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for name in files:
            if name.endswith('.md'):
                yield Path(directory) / name


def active_text(relative, text):
    # Only the *old* column in the two documented migration tables is historical.
    # Current replacement calls in the same table remain checked.
    lines, migration = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            migration = line.startswith('## 마이그레이션') and relative in MIGRATION_TABLES
        if migration and line.startswith('|'):
            parts = line.split('|')
            line = '|'.join(parts[2:])
        lines.append(line)
    return '\n'.join(lines)


def section(text, title):
    match = re.search(r'^## ' + re.escape(title) + r'\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not match:
        raise ValueError('missing section: ' + title)
    return match.group(1)


def check(root):
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    manifests = sorted(root.glob('*/.claude-plugin/plugin.json'))
    products = {}
    for path in manifests:
        data = json.loads(path.read_text())
        product = path.parents[1].name
        require(data.get('name') == product, f'{path}: plugin name differs from directory')
        require(isinstance(data.get('version'), str) and re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', data['version']), f'{path}: invalid version')
        require(isinstance(data.get('description'), str) and bool(data['description'].strip()), f'{path}: description missing')
        products[product] = data
        manifest_paths(path.parents[1], data, require)
        for sibling in [path.parents[1] / '.codex-plugin/plugin.json', path.parents[1] / 'package.json']:
            if sibling.exists():
                other = json.loads(sibling.read_text())
                require(other.get('version') == data['version'], f'{sibling}: product version mismatch')
                if sibling.parent.name == '.codex-plugin':
                    require(other.get('name') == product, f'{sibling}: product name mismatch')
                    manifest_paths(path.parents[1], other, require)
        mcp = path.parents[1] / '.mcp.json'
        if mcp.exists():
            manifest_paths(path.parents[1], json.loads(mcp.read_text()), require)
    require(bool(products), 'no products')
    marketplace = json.loads((root / '.claude-plugin/marketplace.json').read_text())
    entries = marketplace['plugins']
    require(len({entry['name'] for entry in entries}) == len(entries), 'duplicate marketplace name')
    require({entry['name'] for entry in entries} == products.keys(), 'marketplace/product inventory mismatch')
    for entry in entries:
        require(entry['source'] == './' + entry['name'], f"marketplace source mismatch: {entry['name']}")
        if 'version' in entry and entry['name'] in products:
            require(entry['version'] == products[entry['name']]['version'], f"marketplace version mismatch: {entry['name']}")
    skills = {product: {p.parent.name for p in (root / product / 'skills').glob('*/SKILL.md')} for product in products}
    for product in [*products, '@root']:
        paths = documents(root / product) if product != '@root' else [root / 'README.md', *(p for p in documents(root / 'docs') if not p.name.startswith(HISTORICAL_DOCS))]
        for path in paths:
            relative = path.relative_to(root).as_posix()
            source = path.read_text()
            text = active_text(relative, source)
            if path.name == 'SKILL.md':
                parts = source.split('---', 2)
                require(len(parts) == 3 and not parts[0].strip(), relative + ': frontmatter missing')
                if len(parts) == 3:
                    meta = yaml.safe_load(parts[1])
                    if not isinstance(meta, dict):
                        errors.append(relative + ': frontmatter is not a map'); continue
                    require(not set(meta) - SKILL_FIELDS, relative + ': unsupported skill fields')
                    require(meta.get('name') == path.parent.name, relative + ': skill name mismatch')
                    require(isinstance(meta.get('description'), str) and bool(meta['description'].strip()), relative + ': description missing')
            if path.parent.name == 'agents':
                try:
                    validate_agent(path)
                except (ValueError, yaml.YAMLError) as exc:
                    errors.append(relative + ': ' + str(exc))
            for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
                if re.match(r'^[a-z]+:', target) or target.startswith('#') or any(c in target for c in '{}<>*'):
                    continue
                if target in EXAMPLE_LINKS.get(relative, set()):
                    continue
                local = unquote(target.split('#')[0])
                require(not local or (path.parent / local).is_file(), relative + ': missing local link: ' + target)
            for called_product, called_skill in re.findall(r'/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)', text):
                if called_product in products:
                    require(called_skill in skills[called_product], relative + ': missing internal skill call: ' + called_product + ':' + called_skill)
            owner = next((parent for parent in path.parents if (parent / 'SKILL.md').is_file()), None)
            if owner is None and 'overlay' in path.parts:
                owner = root / product / 'overlay'
            if owner is not None:
                for target in re.findall(r'(?<![\w./-])((?:references|assets)/[\w./-]+\.(?:md|py|sh|mjs|cjs|js|go|json|yaml|yml|html))(?!\w)', text):
                    require((owner / target).is_file(), relative + ': missing skill-owned reference: ' + target)
    for product, basefile, template in [
        ('be-harness', 'SKILL.md', 'templates.md'), ('fe-harness', 'SKILL.md', 'templates.md'),
        ('common', 'references/fullstack.md', 'contract-templates.md'),
    ]:
        base = root / product / 'skills/start-workflow'
        text = (base / basefile).read_text()
        canonical = re.findall(r'^#{2,4} Phase (\d+):', text, re.M)
        require(canonical == [str(i) for i in range(1, len(canonical) + 1)], product + ': main phases are not contiguous and unique')
        template_text = (base / 'references' / template).read_text()
        assignments = re.findall(r'^\| (\d+(?:\.\d+)?) \|', section(template_text, 'Phase Assignments'), re.M)
        require(len(assignments) == len(set(assignments)), product + ': duplicate phase assignment')
        require(set(x.split('.')[0] for x in assignments) == set(canonical), product + ': phase assignment/canonical mismatch')
        remaining = re.findall(r'^- Phase (\d+(?:\.\d+)?):', section(template_text, 'Remaining Phases'), re.M)
        require(all(value in assignments for value in remaining) and len(remaining) == len(set(remaining)), product + ': invalid remaining phases')
        override = (root / product / 'OVERRIDES.md').read_text()
        positions = [override.find(token) for token in ['1. **플러그인 기본 동작**', '2. **공통 오버라이드**', '3. **스킬별 오버라이드**']]
        require(all(i >= 0 for i in positions) and positions == sorted(positions), product + ': override load order differs')
        require('**오버라이드가 우선**' in override, product + ': override conflict rule missing')
    # Every new duplicated runtime contract must agree, including overlay routers.
    sw = 'skills/start-workflow/'
    groups = [
        ([f'{p}/{sw}assets/{name}' for p in ('be-harness', 'fe-harness', 'common')])
        for name in ('workflow_scope.py', 'workflow_results.py', 'writer_guard.py')
    ]
    groups += [[f'{p}/{sw}assets/workflow_policy.py' for p in ('be-harness', 'fe-harness', 'common', 'minmos-harness', 'hyeondongs-harness')]]
    groups += [[f'{p}/{sw}references/entry-contract.md' for p in ('be-harness', 'fe-harness', 'common', 'minmos-harness', 'hyeondongs-harness')]]
    groups += [[f'{p}/{sw}references/{name}' for p in ('be-harness', 'fe-harness', 'common')] for name in ('writer-safety.md', 'scope-contract.md', 'result-contract.md', 'review-evidence.md', 'execution-policy.md')]
    groups += [[f'{p}/skills/config/assets/{name}' for p in ('be-harness', 'fe-harness')] for name in ('profile.py', 'doctor.py')]
    groups += [[f'{p}/skills/e2e-test/assets/e2e_lock.py' for p in ('be-harness', 'fe-harness')]]
    groups += [[f'{p}/skills/simplify-loop/references/workflow-script.md' for p in ('be-harness', 'fe-harness')]]
    for group in groups:
        require(all((root / p).is_file() for p in group), 'missing parity member: ' + ', '.join(group))
        if all((root / p).is_file() for p in group):
            require(len({(root / p).read_bytes() for p in group}) == 1, 'parity mismatch: ' + ', '.join(group))
    return errors


if __name__ == '__main__':
    try:
        errors = check(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError) as exc:
        errors = [str(exc)]
    if errors:
        print('\n'.join('FAIL: ' + error for error in errors)); sys.exit(1)
    print('active contracts: OK')
