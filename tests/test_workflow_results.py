import copy
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


class ResultsTest(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
