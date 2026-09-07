#!/usr/bin/env python3
"""Pure workflow entry/transition decisions. Emits plans; never dispatches or writes."""
import argparse
import json
from pathlib import Path
import re
import sys

TARGETS = {'--be': 'be', '--fe': 'fe', '--fs': 'fs', '--mm': 'mm', '--hd': 'hd'}
DOMAINS = {'be': 'be', 'fe': 'fe', 'fs': 'fs', 'mm': 'be', 'hd': 'fe'}
MODES = {'be': ('be', 'build'), 'fe': ('fe', 'build'), 'fs': ('fs', 'build'),
         'analyze': ('be', 'analyze'), 'verify': ('be', 'verify')}
SUPPORT = {'be': ['build', 'analyze', 'verify'], 'fe': ['build'], 'fs': ['build']}


def blocked(reason):
    return {'status': 'BLOCKED:' + reason, 'actions': []}


def flag_values(args):
    """Do not interpret flag-like values or literal text after -- as flags."""
    result = []
    values = {'--resume', '--codex', '--codex-models', '--tier'}
    i = 0
    while i < len(args):
        flag = args[i]
        if flag == '--':
            break
        result.append(flag)
        if flag in values:
            if i + 1 == len(args):
                raise ValueError('missing value: ' + flag)
            i += 1
        i += 1
    return result


def route(data):
    entry = data.get('entry', 'common')
    args = data.get('arguments', [])
    if entry not in ('common', *DOMAINS) or not isinstance(args, list) or any(not isinstance(x, str) for x in args):
        raise ValueError('invalid entry/arguments')
    flags = flag_values(args)
    targets = [x for x in flags if x in TARGETS]
    if len(targets) > 1:
        return blocked('TARGET_CONFLICT')
    modes = {m for m, names in [('analyze', ('--analyze', '-a')), ('verify', ('--verify', '-v'))] if any(x in flags for x in names)}
    if len(modes) > 1:
        return blocked('MODE_CONFLICT')
    mode = next(iter(modes), data.get('inherited_mode', 'build'))
    if mode not in ('build', 'analyze', 'verify'):
        raise ValueError('invalid inherited mode')
    if modes and data.get('inherited_mode', mode) != mode:
        return blocked('MODE_CONFLICT')
    target = TARGETS[targets[0]] if targets else (entry if entry != 'common' else None)
    if not targets and 'inherited_route_target' in data:
        target = data['inherited_route_target']
        if target not in DOMAINS or (entry != 'common' and DOMAINS[entry] != DOMAINS[target]):
            return blocked('ROUTE_MISMATCH')
    domain = DOMAINS.get(target, data.get('detected_domain'))
    resume = data.get('resume_mode')
    if '--resume' in flags and resume is None:
        return blocked('RUN_MISMATCH')
    if resume is not None:
        if resume not in MODES:
            return blocked('RUN_MISMATCH')
        saved_domain, saved_mode = MODES[resume]
        if (domain is not None and domain != saved_domain) or ((modes or 'inherited_mode' in data) and mode != saved_mode):
            return blocked('RUN_MISMATCH')
        domain, mode = saved_domain, saved_mode
        saved_target = data.get('resume_route_target', saved_domain)
        if saved_target not in DOMAINS or DOMAINS[saved_target] != saved_domain or (targets and target != saved_target):
            return blocked('RUN_MISMATCH')
        target = saved_target
    if domain not in SUPPORT:
        return blocked('DOMAIN_REQUIRED')
    if mode not in SUPPORT[domain]:
        return blocked('UNSUPPORTED_MODE:' + domain + ':' + mode)
    hard = '--hard' in flags or '-h' in flags
    if resume is not None:
        if type(data.get('resume_hard')) is not bool:
            return blocked('RUN_MISMATCH')
        hard = data['resume_hard']
    publish = 'none' if mode != 'build' else ('local' if domain == 'fs' else 'push') if hard else 'pr'
    inherited = data.get('inherited_publish_policy')
    if resume is not None and 'resume_publish_policy' in data:
        saved_policy = data['resume_publish_policy']
        expected = ('none',) if mode != 'build' else ('local',) if domain == 'fs' and hard else ('push', 'local') if hard else ('pr',)
        if saved_policy not in expected:
            return blocked('RUN_MISMATCH')
        publish = saved_policy
    if inherited is not None:
        if inherited not in ('none', 'local', 'push', 'pr'):
            raise ValueError('invalid inherited publish policy')
        # Domain transitions must never increase an established local-only scope.
        if inherited == 'local' and mode == 'build':
            publish, hard = 'local', True
        elif inherited == 'push' and mode == 'build':
            publish, hard = ('local' if domain == 'fs' else 'push'), True
        elif inherited == 'none' and mode == 'build':
            return blocked('PUBLISH_POLICY_MISMATCH')
    if resume is not None and data.get('resume_publish_policy', publish) != publish:
        return blocked('RUN_MISMATCH')
    installed = data.get('installed', {})
    if not isinstance(installed, dict) or any(k not in ('be', 'fe', 'mm', 'hd') or not isinstance(v, str) or not v.strip() for k, v in installed.items()):
        raise ValueError('installed must map logical roles to actual session call names')
    overlay = None
    if domain == 'fs':
        if not all(x in installed for x in ('be', 'fe')):
            return blocked('HARNESS_MISSING')
        dispatch = None
    else:
        base_only = target in ('be', 'fe')
        overlay = {'be': 'mm', 'fe': 'hd'}[domain]
        selected = target if target in ('mm', 'hd') else overlay if not base_only and overlay in installed else domain
        if selected != overlay:
            overlay = None
        # A directly invoked base workflow is already available; common is optional.
        if entry in ('be', 'fe') and domain == entry:
            dispatch = None
        elif selected not in installed or domain not in installed:
            return blocked('HARNESS_MISSING')
        elif selected == entry and entry in ('mm', 'hd'):
            dispatch = installed[domain]
        else:
            dispatch = installed[selected]
    forwarded = list(args)
    if targets:
        forwarded.remove(targets[0])
    if mode != 'build' and not modes:
        forwarded.insert(0, '--' + mode)
    return {'status': 'READY', 'domain': domain, 'mode': mode, 'hard': hard,
            'publish_policy': publish, 'dispatch': dispatch, 'overlay': overlay,
            'route_target': 'fs' if domain == 'fs' else selected,
            'arguments': forwarded, 'resume_validation_required': resume is not None,
            'actions': ['delegate' if dispatch else 'enter:' + domain + ':' + mode]}


def fullstack(data):
    """Current evidence after Phase8; BLOCKED phases still reach decision/report."""
    reasons = [key + ':' + str(data.get(key, 'MISSING')) for key in ('be', 'fe', 'contract', 'hooks') if data.get(key) != 'PASS']
    if data.get('fresh') is not True:
        reasons.append('STALE_OR_MISSING_RESULTS')
    publish = data.get('publish_policy')
    if publish not in ('pr', 'local'):
        raise ValueError('fullstack publish_policy must be pr or local')
    actions = []
    if not reasons:
        actions += ['commit']
        if publish == 'pr':
            actions += ['assumption_gate', 'push', 'pr']
    actions += ['reflect' if data.get('reflect') is True else 'skip_reflect', 'final_decision', 'report']
    return {'status': 'BLOCKED:PREREQUISITES' if reasons else 'READY', 'reasons': reasons,
            'phase9': 'BLOCKED:PREREQUISITES' if reasons else 'READY',
            'next_phases': [9, 10, 11], 'actions': actions, 'prerequisites_met': not reasons}


def compare(data):
    """Exact normalized observable facts, with evidence collected by the reviewers.

    This compares extracted records; it is not an OpenAPI equivalence validator.
    """
    for side in ('contract', 'be', 'fe'):
        if not isinstance(data.get(side), dict) or not data[side]:
            raise ValueError('nonempty normalized facts required: ' + side)
    result = {}
    for left, right in (('be', 'contract'), ('fe', 'contract'), ('be', 'fe')):
        a, b = data[left], data[right]
        result[left + ':' + right] = [key for key in sorted(a.keys() | b.keys()) if key not in a or key not in b or json.dumps(a[key], sort_keys=True) != json.dumps(b[key], sort_keys=True)]
    return {'status': 'FAIL' if any(result.values()) else 'PASS', 'differences': result}


def overlays(data, manifest):
    selected = data.get('selected', [])
    facts = data.get('facts', {})
    capabilities = data.get('capabilities', [])
    if not isinstance(selected, list) or any(x not in manifest for x in selected) or len(set(selected)) != len(selected):
        raise ValueError('invalid selected overlays')
    if not isinstance(facts, dict) or any(type(v) is not bool for v in facts.values()) or not isinstance(capabilities, list):
        raise ValueError('invalid overlay facts/capabilities')
    plan = []
    for name in selected:
        for hook in manifest[name]:
            item = dict(hook, overlay=name)
            needed = hook.get('when', [])
            missing_facts = [x for x in needed if x not in facts]
            missing = [x for x in hook.get('requires', []) if x not in capabilities]
            item['status'] = ('BLOCKED:HOOK_FACTS' if missing_facts else 'SKIPPED:NOT_APPLICABLE' if any(not facts[x] for x in needed)
                              else 'BLOCKED:HOOK_CAPABILITY' if missing else 'READY')
            item['missing'] = missing_facts + missing
            plan.append(item)
    return {'status': 'BLOCKED:OVERLAY_HOOKS' if any(x['status'].startswith('BLOCKED:') for x in plan) else 'READY', 'hooks': sorted(plan, key=lambda x: x['order'])}


def sources(data):
    """Resolve each copied delta independently; retain separate user rules."""
    plugin = data.get('plugin')
    base = {'minmos-harness': 'be-harness', 'hyeondongs-harness': 'fe-harness'}.get(plugin)
    if not base:
        raise ValueError('unsupported overlay')
    root, project = Path(data['plugin_root']), Path(data['cwd'])
    if not root.is_absolute() or not project.is_absolute():
        raise ValueError('absolute resolved roots required')
    files = data.get('files')
    if not isinstance(files, list) or any(not isinstance(x, str) or not x or Path(x).is_absolute() or '..' in Path(x).parts for x in files):
        raise ValueError('invalid source files')
    resolved, rules, missing = {}, [], []
    for relative in dict.fromkeys(files):
        installed = root / relative
        path = Path(relative)
        copied = project / '.claude' / base / ('common.md' if path.name == 'common.md' else 'skills/' + path.name)
        can_copy = path.parent == Path('overlay') and path.suffix == '.md'
        if can_copy and copied.is_file():
            marker = re.search(r'<!--\s*overlay-source:\s*([^@\s]+)@[^>]+-->', copied.read_text())
            if marker and marker[1] == plugin:
                resolved[relative] = str(copied)
                continue
            rules.append(str(copied))
        if installed.is_file():
            resolved[relative] = str(installed)
        else:
            missing.append(relative)
    return {'status': 'BLOCKED:OVERLAY_SOURCE' if missing else 'READY', 'files': resolved,
            'project_rules': sorted(set(rules)), 'missing': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['route', 'fullstack', 'compare', 'overlays', 'sources'])
    parser.add_argument('input', help='JSON path or - for stdin')
    args = parser.parse_args()
    try:
        data = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text())
        if not isinstance(data, dict):
            raise ValueError('input must be an object')
        if args.action == 'overlays':
            result = overlays(data, json.loads(Path(__file__).with_name('fullstack_overlays.json').read_text()))
        else:
            result = {'route': route, 'fullstack': fullstack, 'compare': compare, 'sources': sources}[args.action](data)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if result['status'].startswith('BLOCKED:') or result['status'] == 'FAIL' else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('BLOCKED:WORKFLOW_POLICY: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
