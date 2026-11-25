import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "be-harness/skills/start-workflow/assets/workflow_run.py"
SPEC = importlib.util.spec_from_file_location("workflow_run", SCRIPT)
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



def isolated_env(tmp):
    tmp = Path(tmp)
    for name in ("home", "functions", "xdg-config", "xdg-cache", "systemp"):
        (tmp / name).mkdir(exist_ok=True)
    gitconfig = tmp / "gitconfig"
    gitconfig.write_text("")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "WORK_LOG_ROOT"}
    env.update(
        HARNESS_PLUGIN_HOME=str(tmp / "base"), HARNESS_FUNCTION_DIR=str(tmp / "functions"),
        HOME=str(tmp / "home"), USERPROFILE=str(tmp / "home"),
        XDG_CONFIG_HOME=str(tmp / "xdg-config"), XDG_CACHE_HOME=str(tmp / "xdg-cache"),
        TMPDIR=str(tmp / "systemp"), TEMP=str(tmp / "systemp"), TMP=str(tmp / "systemp"),
        GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM="1", PYTHONUTF8="1")
    return env


def inside(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


def same(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


class WorkflowRunStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="harness-run-store-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = isolated_env(self.tmp)
        self.repo = self.tmp / "repos" / "demo-repo"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, env=self.env, check=True, capture_output=True)
        self.docs = self.tmp / "base" / "work-log" / "docs"

    def cli(self, *args, env=None, flags=("-B",)):
        return subprocess.run([sys.executable, *flags, str(SCRIPT), *args], env=env or self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def create(self, mode="be", env=None, flags=("-B",)):
        result = self.cli("create", "--cwd", str(self.repo), "--mode", mode, env=env, flags=flags)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        run = json.loads(result.stdout)
        text = "## Run\n" + "".join(f"- {k}: {run[k]}\n" for k in ("CWD", "MODE", "RUN_ID", "RUN_DIR"))
        Path(run["STATE_FILE"]).write_text(text + "\n## Remaining Phases\nPhase 6\n", encoding="utf-8")
        return run

    def resume(self, run, mode="be", env=None):
        return self.cli("resume", "--cwd", str(self.repo), "--mode", mode, "--state", run["STATE_FILE"], env=env)

    def profile(self, text, domain="be"):
        path = self.repo / ".claude" / (domain + "-harness.local.md")
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def record(self, run):
        return json.loads((Path(run["RUN_DIR"]) / "run.json").read_text(encoding="utf-8"))

    def test_create_runs_under_isolated_python(self):
        run = self.create(flags=("-I", "-B"))
        self.assertIn("REPORT_DIR", run)

    def test_default_report_dir_uses_doc_root_and_resume_keeps_it(self):
        run = self.create()
        self.assertTrue(inside(run["RUN_DIR"], self.docs / ".harness-runs" / "demo-repo"))
        self.assertTrue(same(run["REPORT_DIR"], self.docs / "demo-repo"))
        self.assertTrue(Path(run["REPORT_DIR"]).is_dir())
        self.assertEqual("default", self.record(run)["report_dir_source"])
        resumed = self.resume(run)
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertEqual(run["REPORT_DIR"], json.loads(resumed.stdout)["REPORT_DIR"])

    def test_empty_profile_value_uses_default_location(self):
        self.profile('---\nreportDir: ""\n---\n')
        run = self.create()
        self.assertTrue(same(run["REPORT_DIR"], self.docs / "demo-repo"))
        self.assertTrue(inside(run["RUN_DIR"], self.docs / ".harness-runs" / "demo-repo"))

    def test_explicit_profile_value_uses_temp_run_dir_and_absolute_report_dir(self):
        absolute = self.tmp / "abs-reports"
        for value, expected in ((absolute.as_posix(), absolute), ("rel/reports", self.repo / "rel" / "reports")):
            with self.subTest(value):
                self.profile('---\nreportDir: "%s"\n---\n' % value)
                run = self.create()
                self.assertTrue(Path(run["REPORT_DIR"]).is_absolute())
                self.assertTrue(same(run["REPORT_DIR"], expected))
                self.assertTrue(inside(run["RUN_DIR"], self.tmp / "systemp"))
                self.assertEqual("profile", self.record(run)["report_dir_source"])

    def test_explicit_value_does_not_need_doc_root_or_git(self):
        self.profile('---\nreportDir: "%s"\n---\n' % (self.tmp / "reports").as_posix())
        empty = self.tmp / "empty-path"
        empty.mkdir()
        env = {**self.env, "WORK_LOG_ROOT": str(self.tmp / "missing-vault"), "PATH": str(empty)}
        result = self.cli("create", "--cwd", str(self.repo), "--mode", "be", env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(same(json.loads(result.stdout)["REPORT_DIR"], self.tmp / "reports"))

    def test_profile_parse_error_blocks_with_store_config(self):
        self.profile("---\nreportDir: null\n---\n")
        result = self.cli("create", "--cwd", str(self.repo), "--mode", "be")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("BLOCKED:STORE_CONFIG", result.stderr)

    def test_folder_creation_failure_blocks_with_store_config(self):
        (self.tmp / "base").mkdir()
        (self.tmp / "base" / "work-log").write_text("file, not a directory")
        result = self.cli("create", "--cwd", str(self.repo), "--mode", "be")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("BLOCKED:STORE_CONFIG", result.stderr)

    def test_home_relative_report_dir_expands_to_injected_home(self):
        self.profile('---\nreportDir: "~/reports"\n---\n')
        run = self.create()
        self.assertTrue(same(run["REPORT_DIR"], self.tmp / "home" / "reports"))

    @unittest.skipUnless(os.name == "nt", "Windows 드라이브·루트 상대 경로 전용")
    def test_drive_relative_report_dir_is_rejected_on_windows(self):
        for value in ("C:foo", "\\\\foo", "/c/foo"):
            with self.subTest(value):
                self.profile('---\nreportDir: "%s"\n---\n' % value)
                result = self.cli("create", "--cwd", str(self.repo), "--mode", "be")
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("BLOCKED:STORE_CONFIG", result.stderr)

    def test_run_dir_inside_working_tree_falls_back_to_temp_with_warning(self):
        vault = self.repo / "vault"
        vault.mkdir()
        run = self.create(env={**self.env, "WORK_LOG_ROOT": str(vault)})
        self.assertFalse(inside(run["RUN_DIR"], self.repo))
        self.assertTrue(inside(run["RUN_DIR"], self.tmp / "systemp"))
        self.assertTrue(run["warnings"])

    def test_report_dir_inside_working_tree_warns(self):
        self.profile('---\nreportDir: ".claude/harness-reports"\n---\n')
        run = self.create()
        self.assertTrue(same(run["REPORT_DIR"], self.repo / ".claude" / "harness-reports"))
        self.assertTrue(run["warnings"])

    @unittest.skipIf(os.name == "nt", "POSIX symlink 전용 — CI에서 확인")
    def test_symlinked_temp_parent_creates_and_resumes(self):
        real = self.tmp / "real-temp"
        real.mkdir()
        link = self.tmp / "temp-link"
        link.symlink_to(real, target_is_directory=True)
        self.profile('---\nreportDir: "%s"\n---\n' % (self.tmp / "reports").as_posix())
        env = {**self.env, "TMPDIR": str(link)}
        run = self.create(env=env)
        resumed = self.resume(run, env=env)
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertEqual(run["RUN_DIR"], json.loads(resumed.stdout)["RUN_DIR"])
        self.assertEqual(run["REPORT_DIR"], json.loads(resumed.stdout)["REPORT_DIR"])

    def test_resume_keeps_recorded_report_dir_after_env_change(self):
        run = self.create()
        vault = self.tmp / "other-vault"
        vault.mkdir()
        resumed = self.resume(run, env={**self.env, "WORK_LOG_ROOT": str(vault)})
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertEqual(run["REPORT_DIR"], json.loads(resumed.stdout)["REPORT_DIR"])

    def legacy_run(self):
        run = runner.create(self.repo, "be")
        self.addCleanup(shutil.rmtree, run["RUN_DIR"], True)
        record = json.loads((Path(run["RUN_DIR"]) / "run.json").read_text(encoding="utf-8"))
        record = {k: record[k] for k in ("cwd", "mode", "run_id")}
        (Path(run["RUN_DIR"]) / "run.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
        text = "## Run\n" + "".join(f"- {k}: {run[k]}\n" for k in ("CWD", "MODE", "RUN_ID", "RUN_DIR"))
        Path(run["STATE_FILE"]).write_text(text + "\n## Remaining Phases\nPhase 6\n", encoding="utf-8")
        return run

    def test_legacy_run_without_report_dir_resumes_with_legacy_location(self):
        run = self.legacy_run()
        resumed = self.resume(run)
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertTrue(same(json.loads(resumed.stdout)["REPORT_DIR"], self.repo / ".claude" / "harness-reports"))
        self.profile('---\nreportDir: "kept-reports"\n---\n')
        resumed = self.resume(run)
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertTrue(same(json.loads(resumed.stdout)["REPORT_DIR"], self.repo / "kept-reports"))

    def test_legacy_resume_with_profile_parse_error_blocks(self):
        run = self.legacy_run()
        self.profile("---\nreportDir: ~\n---\n")
        resumed = self.resume(run)
        self.assertEqual(1, resumed.returncode, resumed.stdout + resumed.stderr)
        self.assertIn("BLOCKED:STORE_CONFIG", resumed.stderr)

    def test_fullstack_mode_prefers_non_empty_be_value(self):
        self.profile('---\nreportDir: "fe-reports"\n---\n', "fe")
        self.profile('---\nreportDir: ""\n---\n', "be")
        self.assertTrue(same(self.create("fs")["REPORT_DIR"], self.repo / "fe-reports"))
        self.profile('---\nreportDir: "be-reports"\n---\n', "be")
        self.assertTrue(same(self.create("fs")["REPORT_DIR"], self.repo / "be-reports"))


if __name__ == "__main__":
    unittest.main()
