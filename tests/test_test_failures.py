import importlib.util
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


if __name__ == "__main__":
    unittest.main()
