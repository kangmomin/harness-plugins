import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "be-harness/skills/config/assets/profile.py"
spec = importlib.util.spec_from_file_location("harness_profile", SCRIPT)
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def edit(self, raw, changes, domain="be"):
        return profile.Document(raw).edit(changes, domain)

    def test_mixed_eol_quotes_comments_body_and_multiple_edits(self):
        before = (b"--- \r\npreset: go # language\n# neutral\r\n"
                  b"testCommand:  'go test ./...'  # keep\r\n"
                  b'commitCoAuthor: "Bot # one" # two\n'
                  b"sourceDirs: ['a,b', 'old'] # layout\r\n---\n"
                  b"# Project Notes\r\n---\nopaque: anything\r\n")
        after = self.edit(before, dict(testCommand="echo '한글'", sourceDirs=["a,b", "new"], commitCoAuthor="Bot # three"))
        expected = before.replace(b"'go test ./...'", "'echo ''한글'''".encode()).replace(b"['a,b', 'old']", b'["a,b", "new"]').replace(b'"Bot # one"', b'"Bot # three"')
        self.assertEqual(expected, after)

    def test_unchanged_is_byte_exact_even_noncanonical_quotes_and_numbers(self):
        raw = b"---\r\npreset: 'go'\nsourceDirs: ['a,b', 'x',]  # keep\r\ntestCommand: go test ./...\n---"
        self.assertEqual(raw, self.edit(raw, dict(preset="go", sourceDirs=["a,b", "x"], testCommand="go test ./...")))

    def test_block_sequence_preserves_positions_and_comments(self):
        raw = b'---\nsourceDirs: # paths\r\n    - "a"  # first\n    - \'b\'\r\n# neutral\n---\nbody\n'
        after = self.edit(raw, {"sourceDirs": ["x", "y"]})
        self.assertEqual(raw.replace(b'"a"', b'"x"').replace(b"'b'", b"'y'"), after)
        shortened = self.edit(raw, {"sourceDirs": ["a"]})
        self.assertNotIn(b"'b'", shortened)
        with self.assertRaisesRegex(profile.ProfileError, "commented"):
            self.edit(raw, {"sourceDirs": []})

    def test_placeholder_only_first_activation_and_body_delimiter(self):
        raw = b"---\n# codexModels: # defaults\r\n#   review: example\n# codexModels: second\n---\n---\n"
        record = dict(provider="openai", model="fixture-model", effort="high")
        after = self.edit(raw, {"codexModels": {"review": record}})
        self.assertEqual(after, b"---\ncodexModels: # defaults\r\n  review: { provider: openai, model: fixture-model, effort: high }\r\n#   review: example\n# codexModels: second\n---\n---\n")
        self.assertEqual(raw, self.edit(raw, {"codexModels": {"write": None}}))

    def test_slot_merge_preserves_other_slots_quotes_and_eol(self):
        raw = b"---\ncodexModels:\r\n  review:  { provider: custom, model: vendor/name, effort: high } # review\n  write: { provider: custom, model: writer }\r\n---\n"
        after = self.edit(raw, {"codexModels": {"review": {"provider": "custom", "model": "reviewer"}, "write": None}})
        self.assertEqual(after, b"---\ncodexModels:\r\n  review:  { provider: custom, model: reviewer } # review\n---\n")
        with self.assertRaisesRegex(profile.ProfileError, "commented"):
            self.edit(raw, {"codexModels": {"review": None}})
        with self.assertRaisesRegex(profile.ProfileError, "INVALID_SLOT"):
            self.edit(raw, {"codexModels": {"write": dict(provider="openai", model="fixture", effort="tiered")}})

    def test_batch_invalid_duplicate_or_unsupported_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".claude/be-harness.local.md"
            path.parent.mkdir()
            for raw, changes in [
                (b"---\npreset: go\npreset: node\n---\n", '{"language":"en"}'),
                (b"---\npreset: go\n---\n", '{"language":"en","e2eEnabled":"false"}'),
                (b"---\npreset: go\n---\n", '{"language":"en","language":"ko"}'),
                (b"---\ntestCommand: |\n  multi\n---\n", '{"language":"en","testCommand":"new"}'),
                (b'---\nsourceDirs:\n  - "a"\n# gap\n  - "b"\n---\n', '{"sourceDirs":["new"]}'),
                (b'---\n"preset": go\n---\n', '{"language":"en"}'),
            ]:
                path.write_bytes(raw)
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "edit", "--domain", "be", "--cwd", directory, "--apply", "--expected-sha256", hashlib.sha256(raw).hexdigest()], input=changes, text=True, capture_output=True)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertEqual(raw, path.read_bytes())
                self.assertEqual([path.name], [p.name for p in path.parent.iterdir()])

    def test_unrelated_unsupported_value_is_opaque(self):
        raw = b"---\nunknown: &anchor\n  complex: value\ntestCommand: |\n  multiline\nlanguage: ko\n---\n"
        self.assertEqual(raw.replace(b"language: ko", b"language: en"), self.edit(raw, {"language": "en"}))

    def test_new_children_inherit_indent_and_preserve_untouched_slots(self):
        raw = b'---\nsourceDirs:\n    -  "a"\ncodexModels:\n    review:  {provider: custom, model: reviewer} # compact\n---\n'
        new = self.edit(raw, {"sourceDirs": ["a", "b"], "codexModels": {"write": {"provider": "custom", "model": "writer"}}})
        self.assertIn(b'    -  "b"\n', new)
        self.assertIn(b'    review:  {provider: custom, model: reviewer} # compact\n', new)
        self.assertIn(b'    write:  { provider: custom, model: writer }\n', new)

    def test_invalid_layout_does_not_become_a_valid_default_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            (root / 'go.mod').touch()
            for raw in ('---\n  buildCommand: "custom"\n---\n', '---\nbuildCommand: - broken yaml\n---\n'):
                (root / '.claude/be-harness.local.md').write_text(raw)
                with self.assertRaisesRegex(profile.ProfileError, 'UNSUPPORTED_LAYOUT'):
                    profile.resolve(root, 'be')

    def test_invalid_model_slot_preserves_valid_siblings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            (root / '.claude/be-harness.local.md').write_text('---\ncodexModels:\n  review: { provider: custom, model: chosen-reviewer }\n  write: { provider: custom }\n---\n')
            result = profile.resolve(root, 'be')
            self.assertEqual({'review': {'provider': 'custom', 'model': 'chosen-reviewer'}}, result['values']['codexModels'])
            self.assertIn('INVALID_SLOT: write.model', result['diagnostics'][0])

    def test_empty_scalar_insertion_with_comments(self):
        raw = b"---\ntestCommand:   # note\nlintCommand:\r\n---"
        self.assertEqual(b'---\ntestCommand: "npm test"   # note\nlintCommand: ""\r\n---', self.edit(raw, {"testCommand": "npm test", "lintCommand": ""}))

    def test_apostrophe_in_plain_scalar_does_not_consume_comment(self):
        raw = b"---\ncommitCoAuthor: O'Reilly # retain attribution note\nsourceDirs: [O'Reilly, \"a # b\"] # paths\n---\n"
        after = self.edit(raw, {"commitCoAuthor": "Another Author", "sourceDirs": ["new", "a # b"]})
        self.assertEqual(b'---\ncommitCoAuthor: "Another Author" # retain attribution note\nsourceDirs: ["new", "a # b"] # paths\n---\n', after)

    def test_cli_atomic_apply_hash_modes_and_no_creation(self):
        with tempfile.TemporaryDirectory(prefix="profile 한글 # ") as directory:
            path = Path(directory) / ".claude/be-harness.local.md"
            path.parent.mkdir()
            raw = b"---\npreset: go\n---\n"
            path.write_bytes(raw)
            path.chmod(0o640)
            command = [sys.executable, "-B", str(SCRIPT), "edit", "--domain", "be", "--cwd", directory]
            preview = subprocess.run(command, input='{"language":"en"}', text=True, capture_output=True)
            output = json.loads(preview.stdout)
            self.assertEqual(raw, path.read_bytes())
            result = subprocess.run(command + ["--apply", "--expected-sha256", output["sha256_before"]], input='{"language":"en"}', text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(0o640, path.stat().st_mode & 0o777)
            saved = path.read_bytes()
            stale = subprocess.run(command + ["--apply", "--expected-sha256", output["sha256_before"]], input='{"language":"ko"}', text=True, capture_output=True)
            self.assertEqual(2, stale.returncode)
            self.assertEqual(saved, path.read_bytes())
            path.unlink()
            missing = subprocess.run(command, input='{}', text=True, capture_output=True)
            self.assertEqual(2, missing.returncode)
            self.assertFalse(path.exists())

    def test_resolve_be_missing_preset_defaults_and_explicit_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "go.mod").write_text("module fixture\n")
            result = profile.resolve(root, "be")
            self.assertEqual("go test ./...", result["commands"]["testCommand"]["value"])
            self.assertEqual("detected:go.mod", result["sources"]["preset"])
            (root / ".claude").mkdir()
            (root / ".claude/be-harness.local.md").write_text('---\npreset: go\ntestCommand: ""\n---\n')
            result = profile.resolve(root, "be")
            self.assertEqual({"value": "", "source": "profile"}, result["commands"]["testCommand"])

    def test_resolve_fe_primary_ignores_invalid_legacy_and_selected_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude").mkdir()
            (root / ".claude/fe-harness.local.md").write_text('---\nframework: nuxt\ntypescript: false\ntestRunner: jest\ne2eRunner: none\ne2eCommand: "custom e2e"\npackageManager: yarn\n---\n')
            (root / ".hyeondong-config.json").write_text("null")
            (root / "package.json").write_text(json.dumps({"scripts": {"lint": "customlint", "typecheck": "tsc"}}))
            (root / "pnpm-lock.yaml").write_text("")
            result = profile.resolve(root, "fe")
            self.assertEqual("profile", result["profile_source"])
            self.assertEqual("yarn run lint", result["commands"]["lintCommand"]["value"])
            self.assertEqual("", result["commands"]["typeCheckCommand"]["value"])
            self.assertEqual("", result["commands"]["e2eCommand"]["value"])
            self.assertEqual("jest", result["values"]["testRunner"])
            self.assertEqual("nuxt", result["values"]["framework"])

    def test_legacy_mapping_invalid_primary_and_ambiguous_lockfiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".hyeondong-config.json"
            text = json.dumps(dict(testRunner="jest", typescript=False, e2eRunner="cypress", conventions=[dict(source="project", path="STYLE.md"), dict(source="plugin", skill="anything")]))
            legacy.write_text(text)
            result = profile.resolve(root, "fe")
            self.assertEqual("legacy", result["profile_source"])
            self.assertFalse(result["writable"])
            self.assertEqual(["STYLE.md"], result["values"]["projectConventions"])
            self.assertEqual(text, legacy.read_text())
            (root / ".claude").mkdir()
            primary = root / ".claude/fe-harness.local.md"
            primary.write_text("---\ntypescript: maybe\n---\n")
            with self.assertRaisesRegex(profile.ProfileError, "INVALID_VALUE"):
                profile.resolve(root, "fe")
            primary.unlink()
            (root / "pnpm-lock.yaml").touch()
            (root / "yarn.lock").touch()
            with self.assertRaisesRegex(profile.ProfileError, "AMBIGUOUS_PACKAGE_MANAGER"):
                profile.resolve(root, "fe")

    def test_profile_schema_matches_documented_keys(self):
        root = SCRIPT.parents[4]
        for domain in ("be", "fe"):
            doc = (root / (domain + "-harness") / "PROFILE.md").read_text()
            frontmatter = doc.split("\n---\n")[1]
            import re
            keys = set(re.findall(r"^(?:# )?([A-Za-z0-9_-]+):", frontmatter, re.M))
            self.assertEqual(keys, set(profile.schema(domain)))

    def test_custom_lint_runs_exact_workspace_env_command_without_eslint(self):
        with tempfile.TemporaryDirectory(prefix='lint # 한글 ') as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            (root / 'workspace with space').mkdir()
            runner = root / 'workspace with space/custom-lint'
            runner.write_text('#!/bin/sh\nprintf "%s\\n" "$LINT_MARK" "$PWD" "$@" > trace\n')
            runner.chmod(0o700)
            raw = b'---\n---\n'
            command = 'cd "workspace with space" && LINT_MARK="actual custom runner" ./custom-lint --config "config with space"'
            path = root / '.claude/fe-harness.local.md'
            path.write_bytes(self.edit(raw, {'lintCommand': command, 'typescript': False}, 'fe'))
            argv = [sys.executable, '-B', str(SCRIPT), 'run', '--domain', 'fe', '--cwd', directory, '--key', 'lintCommand']
            result = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(['actual custom runner', str(runner.parent), '--config', 'config with space'], (runner.parent / 'trace').read_text().splitlines())
            (runner.parent / 'trace').unlink()
            denied = subprocess.run(argv + ['--fix'], capture_output=True, text=True)
            self.assertEqual(2, denied.returncode)
            self.assertFalse((runner.parent / 'trace').exists())

    def test_installed_lint_fallback_fix_and_missing_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = [sys.executable, '-B', str(SCRIPT), 'run', '--domain', 'fe', '--cwd', directory, '--key', 'lintCommand']
            missing = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual('SKIPPED', json.loads(missing.stdout)['status'])
            binary = root / 'node_modules/.bin/eslint'
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > lint-trace\n')
            binary.chmod(0o700)
            fallback = subprocess.run(argv + ['--fix'], capture_output=True, text=True)
            self.assertEqual(0, fallback.returncode, fallback.stderr)
            self.assertEqual(['.', '--format=stylish', '--fix'], (root / 'lint-trace').read_text().splitlines())
            self.assertEqual('runner:eslint', json.loads(fallback.stdout)['source'])


if __name__ == "__main__":
    unittest.main()
