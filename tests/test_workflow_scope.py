import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'be-harness/skills/start-workflow/assets/workflow_scope.py'
spec = importlib.util.spec_from_file_location('workflow_scope', SCRIPT)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)
spec = importlib.util.spec_from_file_location('workflow_results', SCRIPT.with_name('workflow_results.py'))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='scope repo # ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'trunk')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'src').mkdir()
        (self.root / 'src/committed.py').write_text('before\n')
        (self.root / 'src/staged.py').write_text('before\n')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.start = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-b', 'feat/work')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True)

    def collect(self, owned=(), cwd=None):
        return scope.scope(cwd or self.root, self.start, list(owned))


    def test_readable_patch_bundle_is_complete_and_cannot_overwrite_prior_attempt(self):
        with tempfile.TemporaryDirectory(prefix='review evidence ') as outside:
            directory = Path(outside)
            owned = directory / 'owned.json'
            owned.write_text(json.dumps(['src/new file.py', 'src/link']))
            (self.root / 'src/new file.py').write_text('new owned code\n')
            (self.root / 'src/link').symlink_to('/outside/not-read')
            self.git('rm', 'src/committed.py')
            (self.root / 'src/staged.py').write_text('index only\n')
            self.git('add', 'src/staged.py')
            (self.root / 'src/staged.py').write_text('before\n')
            bundle = directory / 'attempt-1'
            artifact = bundle / 'scope.json'
            command = [sys.executable, '-B', str(SCRIPT), '--cwd', str(self.root / 'src'),
                       '--start-sha', self.start, '--owned-files', str(owned),
                       '--patch-dir', str(bundle), '--out', str(artifact)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stderr)
            data = json.loads(artifact.read_text())
            self.assertNotIn('patch', data)
            self.assertEqual(['src/committed.py'], data['deleted'])
            self.assertIn('src/new file.py', data['owned_untracked'])
            self.assertEqual([{'path': 'src/link', 'target': '/outside/not-read'}], data['symlinks'])
            self.assertIn('-before', Path(data['patch_file']).read_text())
            self.assertIn('+index only', Path(data['index_patch_file']).read_text())
            for key in ('patch', 'index_patch'):
                self.assertEqual(data[key + '_sha256'], hashlib.sha256(Path(data[key + '_file']).read_bytes()).hexdigest())
            original = artifact.read_bytes()
            repeat = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, repeat.returncode)
            self.assertEqual(original, artifact.read_bytes())

    def test_review_gate_detects_index_only_change_ignored_by_worktree_fingerprint(self):
        with tempfile.TemporaryDirectory(prefix='scope review ') as outside:
            directory = Path(outside)
            owned = directory / 'owned.json'
            owned.write_text('[]')
            bundle = directory / 'attempt-1'
            artifact = bundle / 'scope.json'
            subprocess.run([sys.executable, '-B', str(SCRIPT), '--cwd', str(self.root),
                            '--start-sha', self.start, '--owned-files', str(owned),
                            '--patch-dir', str(bundle), '--out', str(artifact)], check=True, capture_output=True)
            collected = json.loads(artifact.read_text())
            tree = results.tested_tree(self.root)
            identity = {key: collected[key] for key in ('root', 'start_sha', 'content_sha256')}
            identity.update(artifact=str(artifact), artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
            event = dict(domain='be', kind='scope', phase='8.4', iteration=1, ql_iteration=1,
                         review_id='scope-1', review_stage='initial', verdict='PASS', terminal_state='DONE',
                         tested_tree=tree, evidence_complete=True, missing_evidence=[], scope=identity)
            data = dict(schema_version=1, run_id='scope-run', domain='be', mode='build', terminal_state='RUNNING',
                        tested_tree=tree, targets=[], cases=[], events=[event], fixes=[])
            self.assertTrue(results.check_scope(data, collected)['ready'])
            (self.root / 'src/staged.py').write_text('changed index only\n')
            self.git('add', 'src/staged.py')
            (self.root / 'src/staged.py').write_text('before\n')
            self.assertTrue(results.same_tree(tree, results.tested_tree(self.root)))
            self.assertTrue(results.check_current(data, results.tested_tree(self.root), ['scope'])['current'])
            with self.assertRaisesRegex(ValueError, 'stale scope evidence'):
                results.check_scope(data, self.collect())

    def test_committed_implementation_survives_unrelated_untracked_dirty_tree(self):
        (self.root / 'src/committed.py').write_text('implementation\n')
        self.git('add', '.')
        self.git('commit', '-m', 'implementation')
        clean = self.collect()
        (self.root / 'notes.md').write_text('unrelated user note\n')
        dirty = self.collect()
        self.assertEqual(['src/committed.py'], clean['paths'])
        self.assertEqual(clean['paths'], dirty['paths'])
        self.assertEqual(['notes.md'], dirty['unowned_untracked'])
        self.assertIn('+implementation', dirty['patch'])

    def test_staged_and_working_and_owned_untracked_union_from_subdirectory(self):
        (self.root / 'src/committed.py').write_text('committed\n')
        self.git('add', '.')
        self.git('commit', '-m', 'implementation')
        (self.root / 'src/staged.py').write_text('staged\n')
        self.git('add', 'src/staged.py')
        name = 'src/new 한글\nfile.py'
        (self.root / name).write_text('owned new code\n')
        (self.root / 'src/unowned.md').write_text('user\n')
        result = self.collect([name], self.root / 'src')
        self.assertEqual({'src/committed.py', 'src/staged.py', name}, set(result['paths']))
        self.assertEqual([name], result['owned_untracked'])
        self.assertEqual(result, self.collect([name]))

    def test_index_change_not_hidden_by_worktree_restored_to_baseline(self):
        (self.root / 'src/staged.py').write_text('staged only\n')
        self.git('add', 'src/staged.py')
        (self.root / 'src/staged.py').write_text('before\n')
        result = self.collect()
        self.assertEqual(['src/staged.py'], result['paths'])
        self.assertEqual('', result['patch'])
        self.assertIn('+staged only', result['index_patch'])

    def test_hard_mode_commit_on_base_branch_retains_start_scope(self):
        self.git('checkout', 'trunk')
        (self.root / 'src/committed.py').write_text('direct branch implementation\n')
        self.git('add', '.')
        self.git('commit', '-m', 'hard-mode implementation')
        self.assertEqual('', self.git('diff', '--name-only', 'trunk...HEAD'))
        self.assertEqual(['src/committed.py'], self.collect()['read'])

    def test_rename_delete_and_symlink_do_not_read_external_target(self):
        self.git('mv', 'src/committed.py', 'src/renamed.py')
        self.git('rm', 'src/staged.py')
        link = self.root / 'src/alias'
        link.symlink_to('/does-not-exist/outside')
        result = self.collect(['src/alias'])
        self.assertEqual(['src/committed.py', 'src/staged.py'], result['deleted'])
        self.assertEqual(['src/renamed.py'], result['read'])
        self.assertEqual([{'path':'src/alias','target':'/does-not-exist/outside'}], result['symlinks'])

    def test_standalone_explicit_base_and_invalid_start_fail_closed(self):
        (self.root / 'src/committed.py').write_text('new\n')
        self.git('add', '.')
        self.git('commit', '-m', 'new')
        result = scope.scope(self.root, None, [], 'trunk')
        self.assertEqual(self.start, result['start_sha'])
        with self.assertRaises(scope.ScopeError):
            scope.scope(self.root, 'missing-ref', [])
        with self.assertRaises(scope.ScopeError):
            scope.scope(self.root, None, [])
        for invalid in (['../outside'], ['src/../outside'], ['src/x', 'src/x'], 'src/x'):
            with self.assertRaises(scope.ScopeError):
                self.collect(invalid) if isinstance(invalid, list) else scope.scope(self.root, self.start, invalid)

    def test_tree_identity_is_repository_root_relative(self):
        (self.root / 'owned outside src.txt').write_text('new\n')
        (self.root / 'src/owned.py').write_text('new\n')
        self.assertEqual(results.tested_tree(self.root), results.tested_tree(self.root / 'src'))

    def test_cli_git_error_is_nonzero_and_never_empty_success(self):
        owned = self.root / 'owned.json'
        owned.write_text('[]')
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--cwd', str(self.root), '--start-sha', 'bad-ref', '--owned-files', str(owned)], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertIn('BLOCKED:REVIEW_SCOPE', result.stderr)


if __name__ == '__main__':
    unittest.main()
