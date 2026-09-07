import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'common/skills/start-workflow/assets'
spec = importlib.util.spec_from_file_location('workflow_policy', ASSETS / 'workflow_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
INSTALLED = dict(be='codex-be:start-workflow', fe='other-fe:start-workflow',
                 mm='minmos:start-workflow-mm', hd='company-ui:start-workflow')


class WorkflowPolicyTests(unittest.TestCase):
    def test_domain_mode_matrix_and_aliases_never_dispatch_unsupported(self):
        for domain in ('be', 'fe', 'fs'):
            for flag in ('', '--analyze', '-a', '--verify', '-v'):
                args = ['--' + domain] + ([flag] if flag else [])
                result = policy.route(dict(arguments=args, installed=INSTALLED))
                if flag and domain != 'be':
                    self.assertTrue(result['status'].startswith('BLOCKED:UNSUPPORTED_MODE'), result)
                    self.assertEqual(result['actions'], [])
                else:
                    self.assertEqual(result['status'], 'READY', result)
        for args in (['--fs', '-a', '-v'], ['--be', '--fe']):
            self.assertEqual(policy.route(dict(arguments=args))['actions'], [])

    def test_base_selection_auto_overlay_and_wrappers_use_actual_calls(self):
        for domain, overlay in (('be', 'mm'), ('fe', 'hd')):
            base = policy.route(dict(arguments=['--' + domain], installed=INSTALLED))
            auto = policy.route(dict(detected_domain=domain, installed=INSTALLED))
            wrapper = policy.route(dict(entry=overlay, installed=INSTALLED))
            self.assertEqual(base['dispatch'], INSTALLED[domain])
            self.assertIsNone(base['overlay'])
            self.assertEqual(auto['dispatch'], INSTALLED[overlay])
            self.assertEqual(wrapper['dispatch'], INSTALLED[domain])
            self.assertEqual(wrapper['overlay'], overlay)
        self.assertEqual(policy.route(dict(entry='be', arguments=['-a']))['mode'], 'analyze')
        self.assertEqual(policy.route(dict(entry='fe'))['status'], 'READY')
        self.assertEqual(policy.route(dict(entry='hd', arguments=['-v'], installed=INSTALLED))['actions'], [])
        self.assertEqual(policy.route(dict(arguments=['--mm']))['actions'], [])

    def test_resume_mismatch_and_lost_cli_flags_preserve_mode_and_hard(self):
        data = dict(arguments=['--resume', '/tmp/run/workflow-state.md'], resume_mode='fs',
                    resume_hard=True, resume_publish_policy='local', installed=INSTALLED)
        got = policy.route(data)
        self.assertEqual(got['publish_policy'], 'local')
        self.assertTrue(got['resume_validation_required'])
        self.assertEqual(policy.route(dict(data, arguments=data['arguments'] + ['-a']))['actions'], [])
        self.assertEqual(policy.route(dict(data, resume_publish_policy='push'))['actions'], [])
        saved_analyze = policy.route(dict(resume_mode='analyze', resume_hard=False, installed=INSTALLED))
        self.assertEqual(saved_analyze['mode'], 'analyze')
        self.assertIn('--analyze', saved_analyze['arguments'])
        self.assertEqual(policy.route(dict(entry='fe', resume_mode='analyze', resume_hard=False))['actions'], [])
        self.assertEqual(policy.route(dict(entry='fe', arguments=['--resume', '/tmp/missing']))['actions'], [])
        local_be = policy.route(dict(entry='common', resume_mode='be', resume_hard=True,
                                     resume_publish_policy='local', resume_route_target='be', installed=INSTALLED))
        self.assertEqual(local_be['publish_policy'], 'local')
        self.assertEqual(local_be['dispatch'], INSTALLED['be'])
        for target in ('be', 'mm'):
            resumed = policy.route(dict(resume_mode='be', resume_hard=False, resume_route_target=target, installed=INSTALLED))
            self.assertEqual(resumed['dispatch'], INSTALLED[target])
            self.assertEqual(resumed['route_target'], target)
        delegated = policy.route(dict(entry='be', inherited_route_target='mm', installed=INSTALLED))
        self.assertIsNone(delegated['dispatch'])
        self.assertEqual(delegated['route_target'], 'mm')

    def test_domain_transitions_do_not_widen_local_or_drop_read_mode(self):
        for entry in ('be', 'fe', 'fs'):
            result = policy.route(dict(entry=entry, arguments=['-h'], installed=INSTALLED))
            self.assertEqual(result['publish_policy'], 'local' if entry == 'fs' else 'push')
        for entry in ('be', 'fe'):
            result = policy.route(dict(entry=entry, inherited_publish_policy='local', installed=INSTALLED))
            self.assertEqual(result['publish_policy'], 'local')
            self.assertTrue(result['hard'])
        for mode in ('analyze', 'verify'):
            self.assertEqual(policy.route(dict(entry='fs', inherited_mode=mode, installed=INSTALLED))['actions'], [])
        for entry in ('be', 'fe', 'fs'):
            result = policy.route(dict(entry=entry, inherited_mode='build', inherited_publish_policy='push', installed=INSTALLED))
            self.assertEqual(result['publish_policy'], 'local' if entry == 'fs' else 'push')
            self.assertTrue(result['hard'])

    def test_literal_arguments_and_flag_values_not_interpreted(self):
        got = policy.route(dict(entry='fe', arguments=['--codex-models', '--analyze', '--', '--fs']))
        self.assertEqual(got['domain'], 'fe')
        self.assertEqual(got['arguments'], ['--codex-models', '--analyze', '--', '--fs'])

    def test_blocked_fullstack_reaches_decision_without_git_even_without_tdd(self):
        green = dict(be='PASS', fe='PASS', contract='PASS', hooks='PASS', fresh=True, publish_policy='pr')
        for key, failure in [('be', 'BLOCKED:TEST_NOT_GREEN'), ('contract', 'BLOCKED:CONTRACT_DIFF'),
                             ('hooks', 'BLOCKED:CODEX_REVIEW'), ('fresh', False)]:
            got = policy.fullstack(dict(green, **{key: failure}, tdd=False))
            self.assertFalse(got['prerequisites_met'])
            self.assertEqual(got['actions'], ['skip_reflect', 'final_decision', 'report'])
            self.assertEqual(got['next_phases'][-1], 11)
        trace = policy.fullstack(dict(green, publish_policy='local', reflect=True))
        self.assertEqual(trace['actions'], ['commit', 'reflect', 'final_decision', 'report'])
        self.assertEqual(policy.fullstack(green)['actions'][:4], ['commit', 'assumption_gate', 'push', 'pr'])

    def test_contract_three_way_comparison_detects_same_direction_drift(self):
        contract = {'GET /books status': 200, 'response.total type': 'integer'}
        both = dict(contract, **{'response.total type': 'string'})
        got = policy.compare(dict(contract=contract, be=both, fe=both))
        self.assertEqual(got['status'], 'FAIL')
        self.assertEqual(got['differences'], {'be:contract': ['response.total type'],
                                            'fe:contract': ['response.total type'], 'be:fe': []})
        self.assertEqual(policy.compare(dict(contract=contract, be=contract, fe=contract))['status'], 'PASS')

    def test_overlay_forward_plan_covers_skipped_request_and_no_api_docs_file(self):
        manifest = json.loads((ASSETS / 'fullstack_overlays.json').read_text())
        data = dict(selected=['minmos-harness', 'hyeondongs-harness'],
                    facts=dict(request_needed=False, codex_enabled=False, e2e=True, api_change=True),
                    capabilities=['review', 'http-or-grpc', 'apidog-read', 'apidog-import-authorized'])
        plan = policy.overlays(data, manifest)
        ready = [h['id'] for h in plan['hooks'] if h['status'] == 'READY']
        self.assertEqual(plan['status'], 'READY')
        self.assertNotIn('mm.request', ready)
        self.assertIn('mm.e2e-flow', ready)
        self.assertIn('mm.doc-sync', ready)  # no apiDocsPath condition
        self.assertLess(ready.index('mm.e2e'), ready.index('mm.quality-review'))
        self.assertLess(ready.index('mm.quality-review'), ready.index('mm.doc-sync'))
        for hook in plan['hooks']:
            for file in hook['files']:
                self.assertTrue((ROOT / hook['overlay'] / file).is_file(), file)
        fresh = policy.overlays(data, manifest)
        self.assertEqual(fresh, plan)  # helper does not cache old-tree APPROVE
        self.assertEqual(next(h['valid_for'] for h in fresh['hooks'] if h['id'] == 'mm.quality-review'), 'tested_tree')
        absent = policy.overlays(dict(data, capabilities=['review']), manifest)
        self.assertEqual(absent['status'], 'BLOCKED:OVERLAY_HOOKS')
        self.assertEqual(next(h['status'] for h in absent['hooks'] if h['id'] == 'mm.doc-sync'), 'BLOCKED:HOOK_CAPABILITY')

    def test_unsupported_cli_is_read_only_and_all_packaged_copies_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sentinel').write_bytes(b'keep')
            for plugin in ('common', 'be-harness', 'fe-harness', 'minmos-harness', 'hyeondongs-harness'):
                script = ROOT / plugin / 'skills/start-workflow/assets/workflow_policy.py'
                self.assertEqual(script.read_bytes(), (ASSETS / 'workflow_policy.py').read_bytes())
                proc = subprocess.run([sys.executable, '-I', '-B', str(script), 'route', '-'],
                                      input=json.dumps(dict(entry='fe', arguments=['-a'])),
                                      cwd=root, text=True, capture_output=True)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertEqual(json.loads(proc.stdout)['actions'], [])
            self.assertEqual(list(root.iterdir()), [root / 'sentinel'])
            self.assertEqual((root / 'sentinel').read_bytes(), b'keep')

    def test_partial_copied_overlay_deduplicates_per_file_and_keeps_user_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            base = project / '.claude/be-harness'
            (base / 'skills').mkdir(parents=True)
            data = dict(plugin='minmos-harness', plugin_root=str(ROOT / 'minmos-harness'),
                        cwd=str(project), files=['overlay/common.md', 'overlay/start-workflow.md'])
            copied_start = base / 'skills/start-workflow.md'
            copied_start.write_text('<!-- overlay-source: minmos-harness@2.0.0 -->\ncustom copy\n')
            got = policy.sources(data)
            self.assertEqual(got['files']['overlay/start-workflow.md'], str(copied_start))
            self.assertEqual(got['files']['overlay/common.md'], str(ROOT / 'minmos-harness/overlay/common.md'))
            (base / 'common.md').write_text('<!-- overlay-source: minmos-harness@2.0.0 -->\ncommon copy\n')
            copied_start.write_text('user rules with no overlay marker\n')
            got = policy.sources(data)
            self.assertEqual(got['files']['overlay/common.md'], str(base / 'common.md'))
            self.assertEqual(got['files']['overlay/start-workflow.md'], str(ROOT / 'minmos-harness/overlay/start-workflow.md'))
            self.assertEqual(got['project_rules'], [str(copied_start)])


if __name__ == '__main__':
    unittest.main()
