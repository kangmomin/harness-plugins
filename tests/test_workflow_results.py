import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'be-harness/skills/start-workflow/assets'
spec = importlib.util.spec_from_file_location('results', ASSETS / 'workflow_results.py')
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)
RENDER = ROOT / 'be-harness/skills/e2e-test-loop/assets/render_e2e_report.py'
TREE = {'head': 'a' * 40, 'content_sha256': 'b' * 64}


def fixture():
    return {'schema_version': 1, 'run_id': 'fixture-run', 'domain': 'be', 'mode': 'build',
        'terminal_state': 'DONE', 'tested_tree': TREE.copy(), 'targets': [], 'cases': [], 'events': [], 'fixes': [],
        'e2e': {'level': 'full', 'main_flow': 'fixture', 'unresolved': [], 'uncovered': [], 'smoke_omitted': []}}


def target(data, identifier, protocol='HTTP', called=True, supported=True):
    operation = 'GET /' + identifier if protocol == 'HTTP' else 'example.v1.Service/' + identifier
    data['targets'].append({'target_id': identifier, 'protocol': protocol, 'operation': operation,
                            'supported': supported, 'reason': '' if supported else 'unsupported streaming'})
    data['cases'].append({'case_id': identifier, 'target_id': identifier, 'category': 'Happy Path', 'name': identifier})
    if called:
        data['events'].append({'domain': 'be', 'kind': 'e2e', 'phase': '8.6', 'iteration': 1,
            'case_id': identifier, 'protocol': protocol, 'verdict': 'PASS', 'terminal_state': 'DONE',
            'tested_tree': TREE.copy(), 'request': operation, 'expected': 'OK', 'actual': 'OK',
            'server_contact': True, 'client_error': False, 'streaming': 'unary', 'deadline': '2s', 'server_status': 'OK', 'status_origin': 'server'})



def scope_event(directory):
    patches = {}
    for key in ('patch', 'index_patch'):
        path = directory / (key + '.diff')
        path.write_text('diff fixture\n')
        patches[key + '_file'] = str(path)
        patches[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(schema_version=1, root=str(directory), start_sha='a' * 40, content_sha256='c' * 64, **patches)
    artifact = directory / 'scope.json'
    artifact.write_text(json.dumps(manifest))
    identity = {key: manifest[key] for key in ('root', 'start_sha', 'content_sha256')}
    identity.update(artifact=str(artifact), artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
    event = dict(domain='be', kind='scope', phase='8.4', iteration=1, ql_iteration=1, review_id='scope-1',
                 review_stage='initial', verdict='PASS', terminal_state='DONE', tested_tree=TREE.copy(),
                 evidence_complete=True, missing_evidence=[], scope=identity)
    return event, manifest

class ResultsTest(unittest.TestCase):
    def test_scope_pending_cannot_pass_and_followup_preserves_initial_result(self):
        with tempfile.TemporaryDirectory() as outside:
            event, current = scope_event(Path(outside))
            data = fixture()
            data['terminal_state'] = 'RUNNING'
            pending = {**event, 'evidence_complete': False, 'missing_evidence': ['pending_8.1'],
                       'verdict': 'PARTIAL', 'terminal_state': 'RUNNING'}
            data['events'] = [pending]
            results.validate(data)
            with self.assertRaisesRegex(ValueError, 'scope review incomplete'):
                results.check_scope(data, current)
            invalid = copy.deepcopy(data)
            invalid['events'][0].update(verdict='PASS', terminal_state='DONE')
            with self.assertRaisesRegex(ValueError, 'scope PASS requires complete evidence'):
                results.validate(invalid)
            data['events'].append({**event, 'iteration': 2, 'review_id': 'scope-2', 'review_stage': 'followup'})
            self.assertTrue(results.check_scope(data, current)['ready'])
            self.assertEqual(['pending_8.1'], data['events'][0]['missing_evidence'])
            self.assertEqual(2, len(data['events']))
            data['terminal_state'] = 'DONE'
            results.validate(data)
            data['terminal_state'] = 'RUNNING'
            data['events'].append({**pending, 'iteration': 3, 'review_id': 'scope-3'})
            with self.assertRaisesRegex(ValueError, 'scope review incomplete'):
                results.check_scope(data, current)
            data['terminal_state'] = 'DONE'
            with self.assertRaisesRegex(ValueError, 'completed run requires accepted scope evidence'):
                results.validate(data)

    def test_scope_gate_rejects_missing_review_and_lost_or_changed_artifacts(self):
        with self.assertRaisesRegex(ValueError, 'missing required verification: scope'):
            results.check_scope(fixture(), {})
        for damage in ('manifest', 'patch', 'index_patch', 'lost'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as outside:
                event, current = scope_event(Path(outside))
                data = fixture()
                data['events'] = [event]
                if damage == 'lost':
                    Path(event['scope']['artifact']).unlink()
                    with self.assertRaises(OSError):
                        results.check_scope(data, current)
                else:
                    path = Path(event['scope']['artifact'] if damage == 'manifest' else current[damage + '_file'])
                    path.write_text(path.read_text() + 'tampered')
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        results.check_scope(data, current)

    def test_scope_cli_fails_closed_without_changing_other_freshness_policy(self):
        with tempfile.TemporaryDirectory() as outside:
            directory = Path(outside)
            event, current = scope_event(directory)
            data = fixture()
            data['terminal_state'] = 'RUNNING'
            data['events'] = [{**event, 'verdict': 'INCONCLUSIVE', 'evidence_complete': False,
                               'missing_evidence': ['diff unreadable'], 'terminal_state': 'DONE'}]
            self.assertTrue(results.check_current(data, TREE, ['scope'])['current'])
            source = directory / 'results.json'
            source.write_text(json.dumps(data))
            run = subprocess.run([sys.executable, str(ASSETS / 'workflow_results.py'), 'check-scope', str(source),
                                  '--run-id', data['run_id'], '--scope', event['scope']['artifact']], capture_output=True, text=True)
            self.assertEqual(2, run.returncode)
            self.assertIn('scope review incomplete', run.stderr)


    def test_unit_rerun_preserves_integration_failure_and_required_evidence(self):
        data = fixture()
        data['events'] = [dict(domain='be', kind=kind, phase=phase, iteration=1, verdict=verdict,
                               terminal_state='DONE', tested_tree=TREE.copy(), regression_count=count)
                          for kind, phase, verdict, count in [('unit', '8.1', 'PASS', 0), ('integration', '8.7', 'FAIL', 1)]]
        data['events'].append({**data['events'][0], 'iteration': 2})
        final = results.latest(results.validate(data))
        self.assertEqual(final[('be', 'integration', None)]['verdict'], 'FAIL')
        self.assertEqual(final[('be', 'integration', None)]['regression_count'], 1)
        self.assertEqual(results.test_summary(data, ['unit', 'integration'])['verdict'], 'FAIL')
        self.assertTrue(results.check_current(data, TREE, ['unit', 'integration'])['current'])
        invalid = copy.deepcopy(data)
        invalid['events'][1]['verdict'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'PASS conflicts with regressions'):
            results.validate(invalid)
        del invalid['events'][1]
        with self.assertRaisesRegex(ValueError, 'missing required verification: integration'):
            results.check_current(invalid, TREE, ['unit', 'integration'])
        with self.assertRaisesRegex(ValueError, 'missing required verification: integration'):
            results.test_summary(invalid, ['unit', 'integration'])

    def test_skipped_unit_cannot_hide_failed_or_unfinished_integration(self):
        data = fixture()
        data['events'] = [dict(domain='be', kind=kind, phase='8', iteration=1, verdict=verdict,
                               terminal_state=terminal, tested_tree=TREE.copy(), regression_count=0)
                          for kind, verdict, terminal in [('unit', 'SKIPPED', 'SKIPPED:USER_OPT_OUT'),
                                                          ('integration', 'FAIL', 'DONE')]]
        self.assertEqual(results.test_summary(data)['verdict'], 'FAIL')
        data['events'][1].update(verdict='SKIPPED', terminal_state='RUNNING')
        self.assertEqual(results.test_summary(data)['verdict'], 'FAIL')
        data['events'][1].update(terminal_state='SKIPPED:PROFILE_EMPTY')
        self.assertEqual(results.test_summary(data)['verdict'], 'SKIPPED')

    def test_single_file_review_fix_requires_new_verification_even_while_running(self):
        data = fixture()
        data['domain'] = 'fe'
        data['terminal_state'] = 'RUNNING'
        required = ['unit', 'build', 'lint', 'typecheck', 'readback']
        data['events'] = [dict(domain='fe', kind=kind, phase='7', iteration=1, verdict='PASS',
                               terminal_state='DONE', tested_tree=TREE.copy(), **({'regression_count': 0} if kind == 'unit' else {})) for kind in required]
        self.assertTrue(results.check_current(data, TREE, required)['current'])
        changed = {**TREE, 'content_sha256': 'd' * 64}
        data['tested_tree'] = changed
        with self.assertRaisesRegex(ValueError, 'stale verification'):
            results.check_current(data, changed, required)
        for old in list(data['events']):
            data['events'].append({**old, 'iteration': 2, 'phase': '8-recheck', 'tested_tree': changed})
        self.assertTrue(results.check_current(data, changed, required)['current'])
        with self.assertRaisesRegex(ValueError, 'missing required verification'):
            results.check_current(data, changed, required + ['e2e'])

    def render(self, data, expected_code=0):
        with tempfile.TemporaryDirectory(prefix='results space ') as directory:
            root = Path(directory)
            source = root / 'results.json'
            source.write_text(json.dumps(data))
            result = subprocess.run([sys.executable, str(RENDER), str(source), '--out-dir', str(root / 'out'),
                '--run-id', 'fixture-run', '--level', 'full', '--status', 'DONE'], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected_code, result.stderr)
            if expected_code:
                self.assertFalse((root / 'out').exists())
                return result.stderr
            path = Path(result.stdout.splitlines()[0].removeprefix('경로: '))
            return result.stdout, path.read_text()

    def test_rest_rpc_and_mixed_denominators_include_uncalled_rpc(self):
        for protocol in ('HTTP', 'GRPC'):
            data = fixture()
            target(data, 'Health', protocol)
            _, report = self.render(data)
            self.assertIn('대상 엔드포인트 1건 / 호출 1건 / 미호출 0건', report)
            self.assertIn('verdict: "예"', report)
        data = fixture()
        target(data, 'health')
        target(data, 'GetUser', 'GRPC', called=False)
        stdout, report = self.render(data)
        self.assertIn('대상 엔드포인트 2건 / 호출 1건 / 미호출 1건', report)
        self.assertIn('verdict: "아니오"', report)
        self.assertIn('DEGRADED', stdout)

    def test_client_parse_failure_cannot_claim_server_validation(self):
        data = fixture()
        target(data, 'GetUser', 'GRPC')
        event = data['events'][0]
        event.update(server_contact=False, client_error=True, actual='unknown field: grpcurl rejected JSON', status_origin='client', server_status=None)
        self.assertIn('PASS requires', self.render(data, 2))
        event.update(verdict='INCONCLUSIVE')
        _, report = self.render(data)
        self.assertIn('미호출 1건', report)
        self.assertIn('verdict: "아니오"', report)

    def test_unsupported_streaming_stays_in_denominator(self):
        data = fixture()
        target(data, 'Watch', 'GRPC', supported=False)
        data['events'][0].update(verdict='SKIPPED', server_contact=False, streaming='bidi', actual='not called', reason='unsupported', status_origin='none', server_status=None)
        _, report = self.render(data)
        self.assertIn('대상 엔드포인트 1건 / 호출 0건 / 미호출 1건', report)
        self.assertIn('PARTIAL', report)

    def test_fix_after_other_case_is_attached_to_exact_iteration_and_id(self):
        data = fixture()
        target(data, 'A')
        target(data, 'B')
        data['events'][0].update(verdict='FAIL', actual='500')
        data['fixes'].append({'domain': 'be', 'phase': '8.6', 'iteration': 1, 'case_id': 'A',
            'cause': 'bad handler', 'change': 'handler.go:3 use corrected name', 'attribution': '본 변경 코드', 'rebuild': 'rebuilt'})
        for previous in list(data['events']):
            new = copy.deepcopy(previous)
            new.update(iteration=2, verdict='PASS', actual='OK')
            data['events'].append(new)
        _, report = self.render(data)
        a = report.split('### A Happy Path')[1].split('### B Happy Path')[0]
        b = report.split('### B Happy Path')[1].split('## GAP')[0]
        self.assertIn('PASS (after 1 fixes)', a)
        self.assertIn('handler.go:3', a)
        self.assertNotIn('handler.go:3', b)
        data['fixes'][0]['case_id'] = 'UNKNOWN'
        self.assertIn('unknown or duplicate fix', self.render(data, 2))

    def test_conflicting_and_stale_evidence_is_rejected(self):
        data = fixture()
        target(data, 'health')
        for mutate in (lambda d: d['events'].append(copy.deepcopy(d['events'][0])),
                       lambda d: d['events'][0].update(protocol='GRPC'),
                       lambda d: d.update(run_id='another-run'),
                       lambda d: d['events'][0]['tested_tree'].update(content_sha256='c' * 64),
                       lambda d: d['events'][0].update(terminal_state='RUNNING')):
            changed = copy.deepcopy(data)
            mutate(changed)
            self.render(changed, 2)

    def test_latest_unit_and_readback_are_independent(self):
        data = fixture()
        data['events'] = [dict(domain='be', kind='unit', phase='8.1', iteration=n, verdict=v,
            terminal_state='DONE', tested_tree=TREE, regression_count=count) for n, v, count in [(1, 'FAIL', 2), (2, 'PASS', 0)]]
        data['events'].append(dict(domain='be', kind='readback', phase='8.8', iteration=1, verdict='WARN', terminal_state='DONE', tested_tree=TREE))
        final = results.latest(results.validate(data))
        self.assertEqual(final[('be', 'unit', None)]['regression_count'], 0)
        self.assertEqual(final[('be', 'readback', None)]['verdict'], 'WARN')

    def test_recorded_grpcurl_boundary_does_not_promote_client_errors(self):
        observed = json.loads((Path(__file__).parent / 'fixtures/grpcurl/observed.json').read_text())
        values = {item['case_id']: item for item in observed['observations']}
        self.assertEqual(values['unknown-field']['handler_arrivals'], 0)
        self.assertEqual(values['oneof-conflict']['handler_arrivals'], 1)
        self.assertEqual(values['server-validation']['handler_arrivals'], 1)
        data = fixture()
        target(data, 'Read', 'GRPC')
        event = data['events'][0]
        event.update(actual=values['deadline']['stderr'], server_status=None, status_origin='client',
                     observed_status='DeadlineExceeded', verdict='INCONCLUSIVE')
        results.validate(data)
        event['server_status'] = 'DeadlineExceeded'
        with self.assertRaisesRegex(ValueError, 'cannot be a server_status'):
            results.validate(data)

    def record_cli(self, path, *args, run_id='fixture-run', stdin=None):
        return subprocess.run([sys.executable, str(ASSETS / 'workflow_results.py'), 'record', str(path), '--run-id', run_id, *args],
                              capture_output=True, text=True, input=stdin)

    def test_record_appends_refreshes_tree_and_finishes_in_one_validated_write(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, run = Path(temp) / 'repo', Path(temp) / 'run'
            repo.mkdir()
            run.mkdir()
            for args in (('init', '-q'), ('config', 'user.name', 'Fixture'), ('config', 'user.email', 'fixture@example.invalid'),
                         ('config', 'core.hooksPath', '/dev/null'), ('config', 'commit.gpgsign', 'false')):
                subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
            (repo / 'app.go').write_text('package app\n')
            subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture'], check=True, capture_output=True)
            source = run / 'verification-results.json'
            subprocess.run([sys.executable, str(ASSETS / 'workflow_results.py'), 'init', '--out', str(source), '--run-id', 'fixture-run',
                            '--domain', 'be', '--mode', 'build', '--cwd', str(repo)], check=True, capture_output=True)
            source.chmod(0o640)
            (repo / 'app.go').write_text('package app\n\nconst Keywords = true\n')
            tree = results.tested_tree(repo)
            build = dict(domain='be', kind='build', phase='7', iteration=1, verdict='PASS', terminal_state='DONE', tested_tree=tree)
            done = self.record_cli(source, '--event', json.dumps(build), '--tree-cwd', str(repo), '--terminal-state', 'DONE')
            self.assertEqual(done.returncode, 0, done.stderr)
            output = json.loads(done.stdout)
            self.assertEqual((output['recorded'], output['events'], output['terminal_state'], output['tested_tree']), (1, 1, 'DONE', tree))
            data = results.load(source, 'fixture-run')
            self.assertEqual((data['events'], data['targets'], data['mode']), ([build], [], 'build'))
            self.assertEqual(source.stat().st_mode & 0o777, 0o640)
            unit = dict(build, kind='unit', phase='8.1', regression_count=0)
            piped = self.record_cli(source, '--event', '-', '--tree-cwd', str(repo), '--include-head', stdin=json.dumps(unit))
            self.assertEqual(piped.returncode, 0, piped.stderr)
            data = results.load(source, 'fixture-run')
            self.assertEqual(data['events'], [build, unit])
            self.assertTrue(data['tested_tree']['head_sensitive'])
            self.assertEqual([p.name for p in run.iterdir()], ['verification-results.json'])

    def test_record_rejections_leave_the_file_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            data = fixture()
            data['terminal_state'] = 'RUNNING'
            unit = dict(domain='be', kind='unit', phase='8.1', iteration=1, verdict='PASS', terminal_state='DONE',
                        tested_tree=TREE.copy(), regression_count=0)
            data['events'].append(unit)
            source, link = Path(temp) / 'results.json', Path(temp) / 'link.json'
            source.write_text(json.dumps(data))
            link.symlink_to(source)
            original = source.read_bytes()
            build_event = dict(domain='be', kind='build', phase='7', iteration=1, verdict='PASS', terminal_state='DONE', tested_tree=TREE.copy())
            build = json.dumps(build_event)
            for label, path, args, run_id, message in (
                    ('no change requested', source, [], 'fixture-run', 'record requires'),
                    ('include-head without tree-cwd', source, ['--event', build, '--include-head'], 'fixture-run', '--include-head requires --tree-cwd'),
                    ('run-id mismatch', source, ['--event', build], 'another-run', 'result run_id mismatch'),
                    ('malformed JSON', source, ['--event', '{'], 'fixture-run', 'Expecting'),
                    ('array event', source, ['--event', '[]'], 'fixture-run', 'event must be a JSON object'),
                    ('batch with a duplicate key', source, ['--event', build, '--event', json.dumps(dict(build_event, phase='7.1'))],
                     'fixture-run', 'conflicting duplicate event key'),
                    ('duplicate of a recorded event', source, ['--event', json.dumps(dict(unit, phase='8.7'))], 'fixture-run',
                     'conflicting duplicate event key'),
                    ('invalid terminal state', source, ['--terminal-state', 'FINISHED'], 'fixture-run', 'result terminal_state invalid'),
                    ('symlinked file', link, ['--event', build], 'fixture-run', 'must not be a symlink')):
                with self.subTest(label):
                    rejected = self.record_cli(path, *args, run_id=run_id)
                    self.assertEqual(rejected.returncode, 2, rejected.stderr)
                    self.assertTrue(rejected.stderr.startswith('result error: ') and message in rejected.stderr, rejected.stderr)
                    self.assertEqual(source.read_bytes(), original)
                    self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ['link.json', 'results.json'])

    def test_record_cannot_finish_on_a_stale_final_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            data = fixture()
            data.update(terminal_state='RUNNING', tested_tree=dict(TREE, content_sha256='c' * 64))
            data['events'].append(dict(domain='be', kind='unit', phase='8.1', iteration=1, verdict='PASS', terminal_state='DONE',
                                       tested_tree=TREE.copy(), regression_count=0))
            source = Path(temp) / 'results.json'
            source.write_text(json.dumps(data))
            original = source.read_bytes()
            rejected = self.record_cli(source, '--terminal-state', 'DONE')
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.assertIn('final PASS describes a different tested tree', rejected.stderr)
            self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
