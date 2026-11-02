import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "test_failures", Path(__file__).resolve().parents[1] / "be-harness/skills/start-workflow/assets/test_failures.py")
parser = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parser)


def package_log(package, failed=True, test="TestCreate"):
    verdict = "FAIL" if failed else "PASS"
    message = "    example_test.go:3: expected 1, got 2\n" if failed else ""
    return (f"=== RUN   {test}\n{message}--- {verdict}: {test} (0.00s)\n"
            f"{verdict}\n{'FAIL' if failed else 'ok'}\t{package}\t0.001s\n")


class GoIdentityTests(unittest.TestCase):
    def analyze(self, *logs, exit_code=1):
        return parser.analyze("".join(logs).splitlines(), "go", exit_code)

    def baseline(self):
        result = self.analyze(package_log("example.test/a"), package_log("example.test/b", False))
        item = result["records"][0]
        state = ("## Test Baseline\n| suite | command | complete | passed | failed | list |\n"
                 f"| unit | go test -v ./... | Y | 1 | 1 | `{item['id']}` :: `{item['sig']}` |\n")
        return parser.parse_baseline(state)

    def test_parallel_cont_and_name_keep_failure_messages_with_their_test(self):
        log = """=== RUN   TestFirst
=== PAUSE TestFirst
=== RUN   TestSecond
=== PAUSE TestSecond
=== CONT  TestFirst
=== CONT  TestSecond
=== NAME  TestFirst
    first_test.go:3: changed first failure
--- FAIL: TestFirst (0.00s)
=== NAME  TestSecond
    second_test.go:4: stable second failure
--- FAIL: TestSecond (0.00s)
FAIL
FAIL example.test/a 0.001s
"""
        result = self.analyze(log)
        self.assertEqual([r['raw'] for r in result['records']],
                         ['first_test.go:3: changed first failure', 'second_test.go:4: stable second failure'])
        baseline_log = log.replace('changed first failure', 'old first failure')
        baseline = self.analyze(baseline_log)
        state = '## Test Baseline\n| unit | go test -v | Y | 0 | 2 | ' + ' / '.join(
            f"`{r['id']}` :: `{r['sig']}`" for r in baseline['records']) + ' |\n'
        records = parser.classify(result['records'], 'unit', parser.parse_baseline(state))
        self.assertEqual([r['cls'] for r in records], ['regression', 'pre_existing'])

    def test_parent_own_failure_is_kept_alongside_failed_child(self):
        result = self.analyze('''=== RUN   TestParent
    parent_test.go:2: parent failed
=== RUN   TestParent/child
    parent_test.go:3: child failed
--- FAIL: TestParent (0.00s)
    --- FAIL: TestParent/child (0.00s)
FAIL
FAIL example.test/a 0.001s
''')
        self.assertEqual(len(result['records']), 2)
        self.assertIn('parent failed', result['records'][0]['raw'])
        self.assertIn('child failed', result['records'][1]['raw'])

    def test_message_less_leaf_failure_is_unparsed(self):
        result = self.analyze('=== RUN   TestEmpty\n--- FAIL: TestEmpty (0.00s)\nFAIL\nFAIL example.test/a 0.001s\n')
        self.assertTrue(result['unparsed'])
        parser.classify(result['records'], 'unit', self.baseline())
        parser.apply_rerun(result['records'], self.analyze(package_log('example.test/a', False, 'TestEmpty'), exit_code=0))
        self.assertEqual(result['records'][0]['cls'], 'unparsed')

    def test_old_message_less_baseline_is_not_comparable(self):
        baseline = self.baseline()
        baseline['failed'][('unit', 'example.test/a::TestCreate')] = parser.normalize('(실패 메시지 없음)')
        result = self.analyze(package_log('example.test/a'))
        parser.classify(result['records'], 'unit', baseline)
        self.assertEqual(result['records'][0]['cls'], 'unparsed')

    def test_parent_without_own_error_is_only_a_container(self):
        result = self.analyze('''=== RUN   TestParent
=== RUN   TestParent/child
    parent_test.go:3: child failed
--- FAIL: TestParent (0.00s)
    --- FAIL: TestParent/child (0.00s)
FAIL
FAIL example.test/a 0.001s
''')
        self.assertEqual([r['id'] for r in result['records']], ['example.test/a::TestParent/child'])
        self.assertFalse(result['unparsed'])

    def test_quick_test_evidence_is_not_test_map_so_new_failure_is_regression(self):
        log = '''=== RUN   TestQuickFilter
=== RUN   TestQuickFilter/default_unchanged
    filter_test.go:9: expected 3 items, got 2
--- FAIL: TestQuickFilter (0.00s)
    --- FAIL: TestQuickFilter/default_unchanged (0.00s)
FAIL
FAIL example.test/a 0.001s
'''
        evidence = ('## Quick Test Evidence\n| Spec ID | suite | 테스트 ID | 파일 |\n|---|---|---|---|\n'
                    '| EC-09 | unit | `example.test/a::TestQuickFilter` | filter_test.go |\n'
                    '| EC-09 | unit | `example.test/a::TestQuickFilter/default_unchanged` | filter_test.go |\n')
        baseline = '## Test Baseline\n| unit | go test -v ./... | Y | 5 | 0 | 없음 |\n'
        test_map = '## TDD Test Map\n| Spec ID | 테스트 | 파일 | Red | Green |\n|---|---|---|---|---|\n'
        for state in (baseline + evidence, baseline + test_map + evidence, baseline + evidence + test_map):
            parsed = parser.parse_baseline(state)
            self.assertEqual(parsed['testmap'], set())
            records = parser.classify(self.analyze(log)['records'], 'unit', parsed)
            self.assertEqual([(r['id'], r['cls']) for r in records],
                             [('example.test/a::TestQuickFilter/default_unchanged', 'regression')])

    def test_nonverbose_go_failure_keeps_message_after_header(self):
        result = self.analyze('--- FAIL: TestCreate (0.00s)\n    user_test.go:3: bad user\nFAIL\nFAIL example.test/a 0.001s\n')
        self.assertEqual(result['records'][0]['raw'], 'user_test.go:3: bad user')

    def test_nonverbose_parent_error_after_child_is_a_separate_regression(self):
        log = '''--- FAIL: TestParent (0.00s)
    --- FAIL: TestParent/child (0.00s)
        parent_test.go:4: child failure
    parent_test.go:5: new parent failure after child
FAIL
FAIL example.test/a 0.001s
'''
        baseline = self.analyze(log.replace('    parent_test.go:5: new parent failure after child\n', ''))
        state = '## Test Baseline\n| unit | go test | Y | 0 | 1 | ' + ' / '.join(
            f"`{r['id']}` :: `{r['sig']}`" for r in baseline['records']) + ' |\n'
        result = self.analyze(log)
        self.assertEqual([r['raw'] for r in result['records']],
                         ['parent_test.go:5: new parent failure after child', 'parent_test.go:4: child failure'])
        records = parser.classify(result['records'], 'unit', parser.parse_baseline(state))
        self.assertEqual([r['cls'] for r in records], ['regression', 'pre_existing'])

    def test_new_failure_in_different_package_is_regression(self):
        result = self.analyze(package_log("example.test/a"), package_log("example.test/b"))
        records = parser.classify(result["records"], "unit", self.baseline())
        self.assertEqual([r["cls"] for r in records], ["pre_existing", "regression"])
        self.assertEqual([r["id"] for r in records], ["example.test/a::TestCreate", "example.test/b::TestCreate"])

    def test_pass_in_other_package_cannot_mark_failure_flaky(self):
        result = self.analyze(package_log("example.test/a"))
        parser.classify(result["records"], "unit", self.baseline())
        rerun = self.analyze(package_log("example.test/a"), package_log("example.test/b", False))
        parser.apply_rerun(result["records"], rerun)
        self.assertEqual(result["records"][0]["cls"], "pre_existing")

    def test_same_package_pass_can_mark_failure_flaky(self):
        result = self.analyze(package_log("example.test/a"))
        parser.classify(result["records"], "unit", self.baseline())
        parser.apply_rerun(result["records"], self.analyze(package_log("example.test/a", False), exit_code=0))
        self.assertEqual(result["records"][0]["cls"], "flaky")

    def test_testmap_does_not_suffix_match_go_id(self):
        self.assertFalse(parser.in_testmap("example.test/a::TestCreate", {"TestCreate", "example.test/b::TestCreate"}))
        self.assertTrue(parser.in_testmap("example.test/a::TestCreate", {"example.test/a::TestCreate"}))

    def test_legacy_baseline_is_not_silently_reused(self):
        baseline = self.baseline()
        baseline["failed"] = {(suite, tid.split("::")[1]): sig for (suite, tid), sig in baseline["failed"].items()}
        result = self.analyze(package_log("example.test/a"))
        self.assertEqual(parser.classify(result["records"], "unit", baseline)[0]["cls"], "unparsed")

    def test_missing_package_summary_is_incomplete(self):
        result = self.analyze("=== RUN   TestCreate\n--- FAIL: TestCreate (0.00s)\nFAIL\n")
        self.assertFalse(result["completed"])
        self.assertTrue(result["unparsed"])

    def test_parent_filter_does_not_remove_other_package_failure(self):
        result = self.analyze(package_log("example.test/a"), package_log("example.test/b", test="TestCreate/sub"))
        self.assertEqual(len(result["records"]), 2)

    def test_init_panic_in_other_package_is_not_ignored(self):
        result = self.analyze(package_log("example.test/a"), "panic: init failed\nFAIL\texample.test/b\t0.001s\n")
        self.assertTrue(result["unparsed"])

    def test_trailing_crash_without_package_summary_is_incomplete(self):
        result = self.analyze(package_log("example.test/a"), "panic: runtime failure\n")
        self.assertFalse(result["completed"])
        self.assertTrue(result["unparsed"])

    def test_cover_no_test_package_lines_do_not_hide_completion(self):
        # Go 1.22+ `go test -v -cover ./...` 실제 출력 — 테스트 없는 패키지는 coverage 한 줄만 낸다(마지막 패키지일 수 있다).
        log = ("\texample.test/m/cmd\t\tcoverage: 0.0% of statements\n"
               "=== RUN   TestA\n--- PASS: TestA (0.00s)\nPASS\ncoverage: 100.0% of statements\n"
               "ok  \texample.test/m\t0.004s\tcoverage: 100.0% of statements\n"
               "\texample.test/m/types\t\tcoverage: 0.0% of statements\n")
        result = self.analyze(log, exit_code=0)
        self.assertTrue(result["completed"])
        self.assertEqual(result["unparsed"], [])
        self.assertEqual(result["passed"], 1)

    def test_cover_no_test_line_does_not_close_an_unfinished_package(self):
        log = "=== RUN   TestA\n--- PASS: TestA (0.00s)\n\texample.test/m/types\t\tcoverage: 0.0% of statements\n"
        result = self.analyze(log, exit_code=0)
        self.assertFalse(result["completed"])
        self.assertTrue(result["unparsed"])

    def test_cover_only_no_test_packages_is_zero_tests(self):
        result = self.analyze("\texample.test/m/types\t\tcoverage: 0.0% of statements\n", exit_code=0)
        self.assertIn("테스트 0건", result["unparsed"])

    def test_unparsed_baseline_cannot_become_flaky_on_rerun(self):
        records = [{"id": "example.test/a::TestCreate", "cls": "unparsed"}]
        parser.apply_rerun(records, self.analyze(package_log("example.test/a", False), exit_code=0))
        self.assertEqual(records[0]["cls"], "unparsed")

    def test_rerun_panic_is_reported_and_cannot_mark_failure_flaky(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial, rerun, baseline = (root / name for name in ("initial.log", "rerun.log", "state.md"))
            initial.write_text(package_log("example.test/a"))
            rerun.write_text(package_log("example.test/a", False) + "panic: init failed\nFAIL\texample.test/b\t0.001s\n")
            baseline.write_text("## Test Baseline\n| unit | go test -v ./... | Y | 1 | 0 | - |\n")
            result = subprocess.run([sys.executable, parser.__file__, str(initial), "--runner", "go", "--exit-code", "1",
                                     "--baseline", str(baseline), "--rerun", str(rerun), "--rerun-exit-code", "1"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("regression 1", result.stdout)
            self.assertIn("flaky 0", result.stdout)
            self.assertIn("unparsed: rerun: example.test/b", result.stdout)


class JavascriptIdentityTests(unittest.TestCase):
    def recorded(self, runner, name, exit_code=1):
        log = (Path(__file__).parent / 'fixtures/runners' / runner / name).read_text()
        return parser.analyze(log.splitlines(), runner, exit_code)

    def classify_pair(self, runner):
        old = self.recorded(runner, 'baseline.log')
        current = self.recorded(runner, 'current.log')
        state = '## Test Baseline\n| unit | run | Y | 0 | %d | %s |\n' % (
            len(old['records']), ' / '.join('`%s` :: `%s`' % (r['id'], r['sig']) for r in old['records']))
        parser.classify(current['records'], 'unit', parser.parse_baseline(state))
        return current

    def test_real_vitest_duplicate_titles_only_changed_file_is_regression(self):
        current = self.classify_pair('vitest')
        self.assertEqual({r['id']: r['cls'] for r in current['records']}, {
            'vitest::a.test.js::User › rejects invalid input': 'regression',
            'vitest::b.test.js::User › rejects invalid input': 'pre_existing'})
        self.assertFalse(current['unparsed'])

    def test_real_jest_received_change_is_a_regression(self):
        current = self.classify_pair('jest')
        self.assertEqual(current['records'][0]['cls'], 'regression')
        self.assertIn('Received: 4', current['records'][0]['sig'])
        self.assertEqual(current['records'][0]['id'], 'jest::a.test.js::User › rejects invalid input')

    def test_real_vitest_partial_rerun_cannot_pass_unexecuted_file(self):
        current = self.classify_pair('vitest')
        parser.apply_rerun(current['records'], self.recorded('vitest', 'rerun-b-only.log', 0))
        records = {r['id']: r for r in current['records']}
        self.assertEqual(records['vitest::b.test.js::User › rejects invalid input']['cls'], 'flaky')
        self.assertEqual(records['vitest::a.test.js::User › rejects invalid input']['cls'], 'regression')
        self.assertIn('rerun_incomplete', records['vitest::a.test.js::User › rejects invalid input']['note'])

    def test_test_map_requires_file_and_runner(self):
        self.assertFalse(parser.in_testmap('vitest::a.test.js::User › case 2', {'case 2', 'User › case 2'}))

    def test_missing_failure_message_is_not_baseline_evidence(self):
        result = parser.analyze([' × a.test.js > suite > case 1ms', ' Test Files 1 failed (1)', ' Tests 1 failed (1)'], 'vitest', 1)
        self.assertTrue(result['unparsed'])
        self.assertEqual(result['records'][0]['cls'], 'unparsed')

    def test_jest_verbose_nested_pass_keeps_filename_suite_and_case(self):
        result = parser.analyze('''PASS ./b.test.js
  User
    nested
      ✓ case 1 (3 ms)
      ✓ case 2 (2 ms)
    ✓ sibling (1 ms)
Tests: 3 passed, 3 total
'''.splitlines(), 'jest', 0)
        self.assertEqual(result['passed_ids'], {'jest::b.test.js::User › nested › case 1',
            'jest::b.test.js::User › nested › case 2', 'jest::b.test.js::User › sibling'})
        records = [{'id': 'jest::a.test.js::User › nested › case 1', 'cls': 'regression'},
                   {'id': 'jest::b.test.js::User › nested › case 1', 'cls': 'regression'}]
        parser.apply_rerun(records, result)
        self.assertEqual([r['cls'] for r in records], ['regression', 'flaky'])

    def test_json_failure_values_and_parameterized_ids_are_preserved(self):
        for runner in ('jest', 'vitest'):
            def report(message, status='failed', title='case 1'):
                return parser.analyze([json.dumps({'numTotalTests': 1, 'numFailedTests': int(status == 'failed'),
                    'testResults': [{'name': './a.test.js', 'status': status, 'assertionResults': [{
                        'ancestorTitles': ['User', 'nested'], 'title': title, 'status': status,
                        'failureMessages': [message]}]}]})], runner, int(status == 'failed'))
            old = report('Error: /api/v1 failed\nExpected: 1\nReceived: 2\n    at fn (/tmp/a.js:12:3)')
            for new_message in ('Error: /api/v2 failed\nExpected: 1\nReceived: 2',
                                'Error: /api/v1 failed\nExpected: 1\nReceived: 4',
                                'TypeError: /api/v1 failed\nExpected: 1\nReceived: 2'):
                self.assertNotEqual(old['records'][0]['sig'], report(new_message)['records'][0]['sig'])
            self.assertNotIn('/tmp/a.js', old['records'][0]['sig'])
            old['records'][0]['cls'] = 'regression'
            parser.apply_rerun(old['records'], report('', 'passed', 'case 2'))
            self.assertEqual(old['records'][0]['cls'], 'regression')
            parser.apply_rerun(old['records'], report('', 'passed', 'case 1'))
            self.assertEqual(old['records'][0]['cls'], 'flaky')

    def test_reported_but_unidentified_failure_blocks_green(self):
        for runner in ('jest', 'vitest'):
            log = (Path(__file__).parent / 'fixtures/runners' / runner / 'baseline.log').read_text()
            if runner == 'jest':
                log = log.replace('1 failed, 1 total', '2 failed, 2 total')
            else:
                log = log.replace('Tests  2 failed (2)', 'Tests  3 failed (3)')
            self.assertTrue(parser.analyze(log.splitlines(), runner, 1)['unparsed'])



FIXTURES = Path(__file__).parent / 'fixtures/runners'
SCRIPT = Path(parser.__file__)


def run_cli(*args, stdin=None, cwd=None, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], input=stdin, capture_output=True, cwd=cwd, env=env)


def baseline_state(rows, extra=''):
    return '## Test Baseline\n| suite | 명령 | 러너 완주 | 통과 | 실패 | 실패 목록 |\n|---|---|---|---|---|---|\n' + ''.join(
        rows) + extra


def items(records):
    return ' / '.join('`%s` :: `%s`' % (parser.cell_escape(r['id']), parser.cell_escape(r['sig'])) for r in records)


class ExpectAndObservationTests(unittest.TestCase):
    def cli(self, log, state, expect=None, extra=(), runner='vitest', exit_code=1):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'run.log').write_text(log, encoding='utf-8')
            (root / 'state.md').write_text(state, encoding='utf-8')
            args = ['--runner', runner, '--exit-code', exit_code, '--baseline', root / 'state.md']
            if expect is not None:
                (root / 'expect.txt').write_text(expect, encoding='utf-8')
                args += ['--expect', root / 'expect.txt']
            result = run_cli(root / 'run.log', *args, *extra)
            return result.returncode, result.stdout.decode('utf-8'), result.stderr.decode('utf-8')

    VERBOSE = (' ✓ a.test.js > A > one 1ms\n'
               ' × a.test.js > A > two 1ms\n'
               '\n FAIL  a.test.js > A > two\nAssertionError: expected 1 to be 2\n ❯ a.test.js:3:1\n'
               ' Test Files  1 failed (1)\n      Tests  1 failed | 1 passed (2)\n')

    def test_expect_red_failure_is_new_red_and_pass_failure_is_regression(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'])
        code, out, _ = self.cli(self.VERBOSE, state, 'red vitest::a.test.js::A › two\npass vitest::a.test.js::A › one\n')
        self.assertEqual(code, 0)
        self.assertIn('| `vitest::a.test.js::A › two` | new_red |', out)
        self.assertIn('| red | `vitest::a.test.js::A › two` | FAIL | Y |', out)
        self.assertIn('| pass | `vitest::a.test.js::A › one` | PASS | Y |', out)
        self.assertNotIn('PASS 판정 불가', out)
        code, out, _ = self.cli(self.VERBOSE, state, 'pass vitest::a.test.js::A › two\n')
        self.assertIn('| `vitest::a.test.js::A › two` | regression | ', out)
        self.assertIn('expect 불충족 1', out)

    def test_unobserved_expected_id_blocks_pass_but_partial_run_reports_only(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'])
        expect = 'pass vitest::a.test.js::A › one\npass vitest::b.test.js::B › missing\n'
        _, out, _ = self.cli(self.VERBOSE.replace(' × a.test.js > A > two 1ms\n', '').replace(
            '\n FAIL  a.test.js > A > two\nAssertionError: expected 1 to be 2\n ❯ a.test.js:3:1\n', '').replace(
            '1 failed (1)', '1 passed (1)').replace('1 failed | 1 passed (2)', '1 passed (1)'), state, expect, exit_code=0)
        self.assertIn('| pass | `vitest::b.test.js::B › missing` | 미관측 | N |', out)
        self.assertIn('PASS 판정 불가(expect 불충족 1)', out)
        _, out, _ = self.cli(self.VERBOSE.replace('Tests  1 failed | 1 passed (2)', 'Tests  1 failed | 1 passed (2)'), state,
                             expect, extra=['--partial'])
        self.assertIn('부분 실행', out)
        self.assertNotIn('expect 불충족', out)

    def test_duplicate_and_mixed_observations_are_not_pass_evidence(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'])
        dup = ' ✓ a.test.js > A > one 1ms\n ✓ a.test.js > A > one 1ms\n Test Files  1 passed (1)\n      Tests  2 passed (2)\n'
        _, out, _ = self.cli(dup, state, 'pass vitest::a.test.js::A › one\n', exit_code=0)
        self.assertIn('| 중복 | N |', out)
        report = json.dumps({'numTotalTests': 2, 'numFailedTests': 0, 'testResults': [{'name': 'a.test.js', 'status': 'passed',
            'assertionResults': [{'ancestorTitles': ['A'], 'title': 'one', 'status': 'passed', 'failureMessages': []},
                                 {'ancestorTitles': ['A'], 'title': 'one', 'status': 'pending', 'failureMessages': []}]}]})
        _, out, _ = self.cli(report, state, 'pass vitest::a.test.js::A › one\n', exit_code=0)
        self.assertIn('| 혼재 | N |', out)

    def test_expect_file_errors_and_missing_baseline_are_call_failures(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'])
        for expect in ('pass x\npass x\n', 'pass x\nred x\n', 'maybe x\n'):
            self.assertEqual(self.cli(self.VERBOSE, state, expect)[0], 2)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'e.txt').write_text('pass x\n')
            (Path(d) / 'run.log').write_text(self.VERBOSE)
            self.assertEqual(run_cli(Path(d) / 'run.log', '--runner', 'vitest', '--exit-code', 1, '--expect', Path(d) / 'e.txt').returncode, 2)

    def test_summary_only_output_is_not_pass_evidence(self):
        state = baseline_state(['| unit | t | Y | 0 | 1 | `vitest::a.test.js::A › gone` :: `x` |\n'])
        summary = ' Test Files  1 passed (1)\n      Tests  1 passed (1)\n'
        _, out, _ = self.cli(summary, state, 'pass vitest::a.test.js::A › one\n', exit_code=0)
        self.assertIn('pass_observation_unavailable', out)
        self.assertIn('| pass | `vitest::a.test.js::A › one` | 미관측 | N |', out)
        self.assertIn('`vitest::a.test.js::A › gone` (미관측)', out)
        self.assertIn('baseline 실패 미확인 1', out)

    def test_baseline_failure_must_stay_observed_unless_tombstone_deletes_it(self):
        old = '| unit | t | Y | 1 | 1 | `vitest::a.test.js::A › two` :: `AssertionError: expected 1 to be 2` |\n'
        expect = 'pass vitest::a.test.js::A › one\n'
        _, out, _ = self.cli(self.VERBOSE, baseline_state([old]), expect)
        self.assertIn('| `vitest::a.test.js::A › two` | pre_existing |', out)
        self.assertIn('baseline 실패 미확인: 0', out)
        gone = ' ✓ a.test.js > A > one 1ms\n ↓ a.test.js > A > two\n Test Files  1 passed (1)\n      Tests  1 passed | 1 skipped (2)\n'
        _, out, _ = self.cli(gone, baseline_state([old]), expect, exit_code=0)
        self.assertIn('`vitest::a.test.js::A › two` (SKIP)', out)
        self.assertIn('baseline 실패 미확인 1', out)
        _, out, _ = self.cli(gone, baseline_state([old], '\n**Tombstone**\n- `vitest::a.test.js::A › two` → 삭제(Spec 승인)\n'), expect, exit_code=0)
        self.assertIn('baseline 실패 미확인: 0', out)
        renamed = baseline_state([old], '\n**Tombstone**\n- `vitest::a.test.js::A › two` → `vitest::a.test.js::A › three`\n')
        _, out, _ = self.cli(gone, renamed, expect, exit_code=0)
        self.assertIn('`vitest::a.test.js::A › three` (미관측)', out)
        three = ' ✓ a.test.js > A > one 1ms\n ✓ a.test.js > A > three 1ms\n Test Files  1 passed (1)\n      Tests  2 passed (2)\n'
        _, out, _ = self.cli(three, renamed, expect, exit_code=0)
        self.assertIn('baseline 실패 미확인: 0', out)

    def test_expected_pass_flaky_on_same_tree_rerun_is_warn_not_blocking(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'])
        rerun = ' ✓ a.test.js > A > two 1ms\n Test Files  1 passed (1)\n      Tests  1 passed (1)\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'rerun.log').write_text(rerun)
            _, out, _ = self.cli(self.VERBOSE, state, 'pass vitest::a.test.js::A › two\n',
                                 extra=['--rerun', Path(d) / 'rerun.log', '--rerun-exit-code', 0])
        self.assertIn('| `vitest::a.test.js::A › two` | flaky |', out)
        self.assertIn('| pass | `vitest::a.test.js::A › two` | FLAKY | Y |', out)
        self.assertNotIn('expect 불충족', out)

    def test_rerun_duplicate_or_skip_mixed_pass_keeps_regression(self):
        for rerun in (' ✓ a.test.js > A > two 1ms\n ✓ a.test.js > A > two 1ms\n Test Files  1 passed (1)\n      Tests  2 passed (2)\n',
                      ' ✓ a.test.js > A > two 1ms\n ↓ a.test.js > A > two\n Test Files  1 passed (1)\n      Tests  1 passed | 1 skipped (2)\n'):
            records = [{'id': 'vitest::a.test.js::A › two', 'cls': 'regression'}]
            parser.apply_rerun(records, parser.analyze(rerun.splitlines(), 'vitest', 0))
            self.assertEqual(records[0]['cls'], 'regression')
            self.assertIn('혼재', records[0]['note'])

    def test_baseline_diagnostics_apply_only_to_their_suite(self):
        state = baseline_state(['| unit | t | Y | 1 | 0 | - |\n', '| e2e | SKIPPED:TIER_QUICK | - | - | - | - |\n'])
        _, out, _ = self.cli(self.VERBOSE, state)
        self.assertNotIn('e2e: 러너 완주 N', out)
        _, out, _ = self.cli(self.VERBOSE, state, extra=['--suite', 'e2e'])
        self.assertIn('e2e: 러너 완주 N', out)
        state = baseline_state(['| unit | t | N | 1 | 0 | - |\n'])
        _, out, _ = self.cli(self.VERBOSE, state)
        self.assertIn('unit: 러너 완주 N', out)

    def test_test_map_cells_keep_escaped_pipes_and_legacy_names_are_diagnosed(self):
        state = baseline_state(['| unit | t | Y | 0 | 0 | - |\n'], '\n## TDD Test Map\n| Spec ID | 테스트 | 파일 | Red | Green |\n'
                               '|---|---|---|---|---|\n| AC-01 | `vitest::a.test.js::A › two a\\|b` | a.test.js:3 | red_assertion | - |\n')
        bl = parser.parse_baseline(state)
        self.assertIn('vitest::a.test.js::A › two a|b', bl['testmap'])
        self.assertFalse(bl['testmap_legacy'])
        legacy = state.replace('`vitest::a.test.js::A › two a\\|b`', '목록 렌더')
        _, out, _ = self.cli(self.VERBOSE, legacy)
        self.assertIn('test_map_legacy_ids', out)
        mapped = parser.parse_baseline(legacy + '\n## TDD Test Map ID 대응\n| 구 표시명 | 정확 ID |\n|---|---|\n| 목록 렌더 | `vitest::a.test.js::A › two` |\n')
        self.assertIn('vitest::a.test.js::A › two', mapped['testmap'])

    def test_emit_baseline_escapes_pipes_in_command_cell(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'run.log').write_text(self.VERBOSE)
            out = run_cli(Path(d) / 'run.log', '--runner', 'vitest', '--exit-code', 1, '--emit-baseline',
                          '--command', 'vitest run --reporter=verbose | tee unit.log').stdout.decode('utf-8')
        row = [ln for ln in out.splitlines() if ln.startswith('| unit |')][0]
        bl = parser.parse_baseline(baseline_state([row + '\n']))
        self.assertEqual(bl['unparsed_suites'], [])
        self.assertEqual(list(bl['failed']), [('unit', 'vitest::a.test.js::A › two')])
        self.assertEqual(parser.table_cells(row)[1], 'vitest run --reporter=verbose | tee unit.log')


class PlaywrightTests(unittest.TestCase):
    def analyze(self, name, exit_code=1, text=None):
        text = text if text is not None else (FIXTURES / 'playwright' / name).read_text(encoding='utf-8')
        return parser.analyze(text.splitlines(), 'auto', exit_code)

    def by_id(self, result):
        return {r['id'].split('::')[-1]: r for r in result['records']}

    def assert_outcomes(self, result):
        self.assertEqual(result['runner'], 'playwright')
        self.assertTrue(result['completed'])
        self.assertEqual(result['unparsed'], [])
        records = self.by_id(result)
        self.assertEqual(records['form › flaky']['cls'], 'flaky')
        self.assertTrue(records['form › flaky']['runner_flaky'])
        self.assertNotIn('cls', records['form › fail then skip'])  # flaky outcome without a passing attempt
        self.assertIn('Received: 1', records['form › fail then skip']['sig'])
        self.assertEqual(records['form › unexpected pass']['sig'], 'Expected to fail, but passed.')
        self.assertEqual(records['form › throw no message']['sig'], 'Error at /repo/tests/a.spec.mjs')
        self.assertEqual(records['form › soft two errors']['sig'].count('Error: expect'), 2)
        self.assertIn('Received: 3', records['form › step fail']['sig'])
        self.assertNotIn('Error Context', ''.join(r['sig'] for r in result['records']))
        observed = {k.split('::')[-1]: v for k, v in result['observed'].items()}
        self.assertEqual(observed['form › expected fail'], ['expected_fail'])
        self.assertEqual(observed['form › skipped'], ['skip'])
        self.assertEqual(observed['form › passes'], ['pass'])
        self.assertEqual(observed['form › submit @new'], ['pass'])

    def test_json_reporter_outcomes(self):
        result = self.analyze('report.json')
        self.assert_outcomes(result)
        self.assertIn('playwright::a.spec.mjs::form › passes', result['observed'])
        self.assertIn('playwright::a.spec.mjs::form › tagged', result['observed'])

    def test_list_reporter_outcomes_and_non_utf8_marks(self):
        result = self.analyze('list.log')
        self.assert_outcomes(result)
        self.assertIn('playwright::tests/a.spec.mjs::form › tagged @smoke', result['observed'])
        text = (FIXTURES / 'playwright/list.log').read_text(encoding='utf-8')
        ascii_marks = re.sub(r'^  ✓ ', '  ok', re.sub(r'^  ✘ ', '  x ', text, flags=re.M), flags=re.M)
        self.assertNotEqual(ascii_marks, text)
        self.assert_outcomes(self.analyze(None, text=ascii_marks))

    def test_projects_are_part_of_identity(self):
        for name in ('projects-list.log', 'projects-report.json'):
            result = self.analyze(name)
            self.assertEqual([r['id'].split('::', 2)[2] for r in result['records']], ['[mobile] › same title'])
            self.assertEqual(sum(1 for k in result['observed'] if k.endswith('[chromium] › same title')), 1)

    def test_stopped_runs_and_global_errors_cannot_pass(self):
        for name in ('maxfail-list.log', 'maxfail-report.json'):
            result = self.analyze(name)
            self.assertFalse(result['completed'])
            self.assertTrue(result['unparsed'])
        result = self.analyze('import-error-report.json')
        self.assertTrue(any('전역 오류' in u for u in result['unparsed']))
        self.assertTrue(self.analyze('import-error-list.log')['unparsed'])

    def test_added_soft_error_changes_signature(self):
        for name in ('list.log', 'report.json'):
            current = self.analyze(name)
            soft = self.by_id(current)['form › soft two errors']
            first_only = soft['sig'].split(' | ')[0]
            for baseline_sig, expected in ((first_only, 'regression'), (soft['sig'], 'pre_existing')):
                state = baseline_state(['| e2e | pw | Y | 4 | 1 | `%s` :: `%s` |\n' % (
                    parser.cell_escape(soft['id']), parser.cell_escape(baseline_sig))])
                records = [dict(r) for r in current['records'] if r['id'] == soft['id']]
                parser.classify(records, 'e2e', parser.parse_baseline(state))
                self.assertEqual(records[0]['cls'], expected)

    def test_runner_flaky_is_not_baseline_failure_and_not_reclassified(self):
        result = self.analyze('list.log')
        flaky = [r for r in result['records'] if r.get('runner_flaky')]
        parser.classify(flaky, 'e2e', parser.parse_baseline(baseline_state(['| e2e | pw | Y | 0 | 0 | - |\n'])))
        self.assertEqual(flaky[0]['cls'], 'flaky')
        with tempfile.TemporaryDirectory() as d:
            out = run_cli(FIXTURES / 'playwright/list.log', '--runner', 'playwright', '--exit-code', 1, '--suite', 'e2e',
                          '--emit-baseline').stdout.decode('utf-8')
        row = [ln for ln in out.splitlines() if ln.startswith('| e2e |')][0]
        self.assertNotIn('form › flaky`', row)
        self.assertIn('| 6 |', row)

    def test_list_flaky_requires_final_passing_attempt(self):
        log = ('Running 1 test using 1 worker\n\n'
               '  ✓  1 tests/x.spec.mjs:3:1 › marked fail (2ms)\n'
               '  ✘  2 tests/x.spec.mjs:3:1 › marked fail (retry #1) (3ms)\n\n'
               '  1) tests/x.spec.mjs:3:1 › marked fail ─────\n\n    Expected to fail, but passed.\n\n'
               '  1 flaky\n    tests/x.spec.mjs:3:1 › marked fail ─────\n')
        result = parser.analyze(log.splitlines(), 'playwright', 0)
        self.assertEqual([r.get('cls') for r in result['records']], [None])
        self.assertEqual(result['records'][0]['sig'], 'Expected to fail, but passed.')

    def test_same_printed_title_from_title_tag_and_metadata_tag_is_duplicate(self):
        log = ('Running 2 tests using 1 worker\n\n'
               '  ✓  1 tests/x.spec.mjs:3:1 › submit @new (2ms)\n'
               '  ✓  2 tests/x.spec.mjs:4:1 › submit @new (2ms)\n'
               '  ✓  3 tests/x.spec.mjs:5:1 › submit @old (2ms)\n\n'
               '  3 passed (1.0s)\n')
        result = parser.analyze(log.splitlines(), 'playwright', 0)
        self.assertTrue(any('중복' in u for u in result['unparsed']))
        self.assertEqual(result['observed']['playwright::tests/x.spec.mjs::submit @old'], ['pass'])


class MessagelessErrorTests(unittest.TestCase):
    def test_vitest_text_and_json_use_name_and_first_frame(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('messageless-verbose.log', 'messageless.json'):
                (root / name).write_text((FIXTURES / 'vitest' / name).read_text(encoding='utf-8').replace('/repo', str(root)))
            sigs = []
            for name in ('messageless-verbose.log', 'messageless.json'):
                out = run_cli(root / name, '--runner', 'vitest', '--exit-code', 1, cwd=root).stdout.decode('utf-8')
                sigs.append(re.findall(r'\| `([^`]+)` \| - \| `([^`]+?) #', out))
            self.assertEqual(sigs[0], sigs[1])
            self.assertEqual([sig for _, sig in sigs[0]],
                             ['Error at a.test.mjs', 'TypeError at a.test.mjs', 'Error at helperThrows (a.test.mjs)'])

    def test_line_moves_keep_signature_and_other_file_changes_it(self):
        log = (FIXTURES / 'vitest/messageless-verbose.log').read_text(encoding='utf-8')
        base = parser.analyze(log.splitlines(), 'vitest', 1)['records'][0]['sig']
        moved = parser.analyze(log.replace('a.test.mjs:4:36', 'a.test.mjs:9:12').splitlines(), 'vitest', 1)['records'][0]['sig']
        other = parser.analyze(log.replace('❯ a.test.mjs:4:36', '❯ sub/a.test.mjs:4:36').splitlines(), 'vitest', 1)['records'][0]['sig']
        self.assertEqual(base, moved)
        self.assertNotEqual(base, other)

    def test_jest_name_only_body_uses_at_frame_and_no_frame_stays_unparsed(self):
        def jest(body):
            return parser.analyze(('FAIL ./a.test.js\n  ● S › case\n\n' + body + '\nTests: 1 failed, 1 total\n').splitlines(), 'jest', 1)
        self.assertEqual(jest('    TypeError: \n\n      at Object.<anonymous> (a.test.js:4:36)\n')['records'][0]['sig'],
                         'TypeError at Object.<anonymous> (a.test.js)')
        result = jest('    Error: \n')
        self.assertEqual(result['records'][0]['cls'], 'unparsed')


class EncodingTests(unittest.TestCase):
    def test_utf8_output_under_cp949_console_and_stdin(self):
        log = (FIXTURES / 'playwright/projects-list.log').read_bytes()
        env = dict(os.environ, PYTHONIOENCODING='cp949')
        for args, data in (([FIXTURES / 'playwright/projects-list.log'], None), (['-'], log)):
            result = run_cli(*args, '--runner', 'playwright', '--exit-code', 1, stdin=data, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('[mobile] › same title', result.stdout.decode('utf-8'))
        result = run_cli(FIXTURES / 'missing.log', '--runner', 'vitest', '--exit-code', 1, env=env)
        self.assertEqual(result.returncode, 2)
        result.stderr.decode('utf-8')


if __name__ == "__main__":
    unittest.main()
