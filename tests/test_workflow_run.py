import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "workflow_run", Path(__file__).resolve().parents[1] / "be-harness/skills/start-workflow/assets/workflow_run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class WorkflowRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="harness-run-test-")
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name).resolve()

    def create(self, mode="be"):
        result = runner.create(self.cwd, mode)
        self.addCleanup(shutil.rmtree, result["RUN_DIR"])
        text = "## Run\n" + "".join(f"- {k}: {result[k]}\n" for k in ("CWD", "MODE", "RUN_ID", "RUN_DIR"))
        Path(result["STATE_FILE"]).write_text(text + "\n## Remaining Phases\nPhase 6\n")
        return result

    def test_new_runs_have_distinct_state_notes_and_reports(self):
        a, b = self.create(), self.create()
        for key in ("RUN_ID", "RUN_DIR", "STATE_FILE", "IMPL_NOTES", "WORK_REPORT"):
            self.assertNotEqual(a[key], b[key])
        self.assertEqual(runner.resume(self.cwd, "be", a["STATE_FILE"]), a)

    def test_other_repo_or_mode_cannot_resume(self):
        run = self.create()
        other = self.cwd / "other-worktree"
        other.mkdir()
        for cwd, mode in ((other, "be"), (self.cwd, "fe")):
            with self.assertRaises(ValueError):
                runner.resume(cwd, mode, run["STATE_FILE"])

    def test_completed_or_overwritten_state_is_rejected(self):
        a, b = self.create(), self.create()
        state = Path(a["STATE_FILE"])
        original = state.read_text()
        state.write_text(original.replace(a["RUN_ID"], b["RUN_ID"]))
        with self.assertRaises(ValueError):
            runner.resume(self.cwd, "be", str(state))
        state.write_text(original.replace("Phase 6", "없음"))
        with self.assertRaises(ValueError):
            runner.resume(self.cwd, "be", str(state))

    def test_unrelated_legacy_state_is_rejected(self):
        state = self.cwd / "workflow-state.md"
        state.write_text("## Flags\n- MODE: be\n")
        with self.assertRaises(OSError):
            runner.resume(self.cwd, "be", str(state))

    def test_incomplete_state_without_remaining_phases_is_rejected(self):
        run = self.create()
        state = Path(run["STATE_FILE"])
        state.write_text(state.read_text().split("## Remaining Phases")[0])
        with self.assertRaises(ValueError):
            runner.resume(self.cwd, "be", str(state))

    def test_relative_state_path_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.resume(self.cwd, "be", "workflow-state.md")


if __name__ == "__main__":
    unittest.main()
