import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
