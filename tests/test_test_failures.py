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
