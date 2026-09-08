import importlib.util
import hashlib
import json
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

    def commands(self, run):
        profile = self.cwd / 'profile.md'
        profile.write_text('original profile\n')
        return {'schema_version': 1, 'run_id': run['RUN_ID'], 'cwd': str(self.cwd),
                'profile_path': str(profile), 'profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest(),
                'commands': {'lintCommand': 'make lint', 'buildCommand': 'make build',
                             'typeCheckCommand': '', 'testCommand': 'make test'}}

    def test_verify_resume_uses_frozen_commands_after_live_profile_changes(self):
        run = self.create('verify')
        data = self.commands(run)
        source = self.cwd / 'resolved.json'
        source.write_text(json.dumps(data))
        saved = runner.save_verify_commands(self.cwd, run['STATE_FILE'], source)
        original = Path(saved['VERIFY_COMMANDS_FILE']).read_bytes()
        Path(data['profile_path']).write_text('changed profile\n')
        resumed = runner.resume(self.cwd, 'verify', run['STATE_FILE'])
        self.assertEqual(resumed['VERIFY_COMMANDS'], data)
        source.write_text(json.dumps({**data, 'commands': {**data['commands'], 'testCommand': 'different test'}}))
        with self.assertRaises(FileExistsError):
            runner.save_verify_commands(self.cwd, run['STATE_FILE'], source)
        self.assertEqual(Path(saved['VERIFY_COMMANDS_FILE']).read_bytes(), original)

    def test_verify_missing_foreign_or_duplicate_snapshot_is_not_recreated(self):
        run = self.create('verify')
        state = Path(run['STATE_FILE'])
        original = state.read_bytes()
        with self.assertRaises(OSError):
            runner.resume(self.cwd, 'verify', str(state))
        data = self.commands(run)
        snapshot = Path(run['VERIFY_COMMANDS_FILE'])
        for invalid in ({**data, 'run_id': '0' * 32}, {**data, 'commands': {'testCommand': 'only one'}},
                        {**data, 'profile_path': 'relative'}, {**data, 'profile_sha256': ''}):
            snapshot.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                runner.resume(self.cwd, 'verify', str(state))
            self.assertEqual(state.read_bytes(), original)
        snapshot.write_text(json.dumps(data)[:-1] + ', "commands": {}}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            runner.resume(self.cwd, 'verify', str(state))
        self.assertEqual(state.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
