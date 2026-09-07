import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'common/skills/commit/assets/git_checks.py'
spec = importlib.util.spec_from_file_location('git_checks', SCRIPT)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class GitChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='git checks # ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'trunk')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'base.txt').write_text('base\n')
        (self.root / 'nested').mkdir()
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.start = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-b', 'feat/change')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True)

    def test_base_resolves_without_version_and_version_is_root_relative(self):
        result = checks.base(self.root / 'nested', 'trunk')
        self.assertEqual(self.start, result['base_sha'])
        self.assertIsNone(result['version_path'])
        (self.root / 'VERSION').write_text('1.0.0\n')
        result = checks.base(self.root / 'nested', 'trunk')
        self.assertEqual('VERSION', result['version_path'])
        self.assertEqual(str(self.root), result['root'])

    def test_tag_in_filename_is_not_content_but_hunk_content_is_found(self):
        (self.root / '[Assumption].txt').write_text('ordinary content\n')
        self.git('add', '.')
        self.git('commit', '-m', 'ordinary commit')
        self.assertEqual('PASS', checks.assumption_gate(self.root, 'trunk', self.start)['status'])
        (self.root / 'base.txt').write_text('base\n++ [Assumption] real addition\n')
        self.git('add', '.')
        self.git('commit', '-m', 'real addition')
        result = checks.assumption_gate(self.root, 'trunk', self.start)
        self.assertEqual([{'path':'base.txt', 'line':2, 'text':'++ [Assumption] real addition'}], result['code_tags'])

    def test_branch_code_and_unpublished_messages_have_distinct_ranges(self):
        self.git('commit', '--allow-empty', '-m', '[Assumption] already published')
        published = self.git('rev-parse', 'HEAD').strip()
        self.git('commit', '--allow-empty', '-m', 'new subject', '-m', '[Assumption] private body')
        result = checks.assumption_gate(self.root, 'trunk', published)
        self.assertEqual(1, len(result['message_tags']))
        self.assertIn('private body', result['message_tags'][0]['message'])
        self.assertNotIn('already published', result['message_tags'][0]['message'])

    def test_failed_git_lookup_cannot_be_a_clean_gate(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'assumptions', '--cwd', str(self.root), '--base-ref', 'bad', '--message-base', self.start], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertIn('BLOCKED:GIT_CHECK', result.stderr)

    def test_worktree_path_filter_applies_to_tracked_and_untracked(self):
        (self.root / 'nested/selected.txt').write_text('[Assumption] selected new file\n')
        (self.root / 'outside.txt').write_text('[Assumption] unrelated file\n')
        (self.root / 'base.txt').write_text('[Assumption] changed tracked file\n')
        result = checks.worktree_tags(self.root / 'nested', ['nested/'])
        self.assertEqual(['nested/selected.txt'], [tag['path'] for tag in result['tags']])
        result = checks.worktree_tags(self.root, ['*.txt'])
        self.assertEqual({'nested/selected.txt', 'outside.txt', 'base.txt'}, {tag['path'] for tag in result['tags']})
        self.assertIn('[Assumption]', (self.root / 'outside.txt').read_text())
        self.assertEqual(3, len(checks.worktree_tags(self.root, ['.'])['tags']))

    def test_nested_workflow_commit_uses_root_paths(self):
        (self.root / 'nested/source.py').write_text('implementation\n')
        self.git('add', '.')
        self.git('commit', '-m', 'implementation')
        (self.root / 'nested/source.py').write_text('validated fix\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '--', 'nested/source.py'], cwd=self.root / 'nested', check=True)
        subprocess.run(['git', '-C', str(self.root), '--literal-pathspecs', 'commit', '--only', '-m', 'fix', '--', 'nested/source.py'], cwd=self.root / 'nested', check=True, capture_output=True)
        self.assertEqual('validated fix\n', self.git('show', 'HEAD:nested/source.py'))

    def test_bump_only_preserves_unrelated_stage_and_worktree(self):
        (self.root / 'VERSION').write_text('1.0.0\n')
        (self.root / 'unrelated.txt').write_text('before\n')
        self.git('add', '.')
        self.git('commit', '-m', 'version baseline')
        (self.root / 'unrelated.txt').write_text('user staged\n')
        self.git('add', 'unrelated.txt')
        (self.root / 'unrelated.txt').write_text('user unstaged after stage\n')
        stage = self.git('ls-files', '-s', '--', 'unrelated.txt')
        (self.root / 'VERSION').write_text('1.0.1\n')
        self.git('add', '--', 'VERSION')
        self.git('--literal-pathspecs', 'commit', '--only', '-m', 'bump', '--', 'VERSION')
        self.assertEqual(['VERSION'], self.git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines())
        self.assertEqual(stage, self.git('ls-files', '-s', '--', 'unrelated.txt'))
        self.assertEqual('user unstaged after stage\n', (self.root / 'unrelated.txt').read_text())
        self.assertEqual('before\n', self.git('show', 'HEAD:unrelated.txt'))

    def test_message_only_amend_preserves_head_tree_and_staged_changes(self):
        self.git('commit', '--allow-empty', '-m', '[Assumption] title')
        tree = self.git('rev-parse', 'HEAD^{tree}')
        (self.root / 'staged.txt').write_text('user stage\n')
        self.git('add', '.')
        index = self.git('ls-files', '-s')
        self.git('commit', '--amend', '--only', '--allow-empty', '-m', 'title')
        self.assertEqual(tree, self.git('rev-parse', 'HEAD^{tree}'))
        self.assertEqual(index, self.git('ls-files', '-s'))

    def test_hard_path_commits_dirty_quality_fix_before_gate_and_push(self):
        # Local bare transport only; exercise the documented current-branch order.
        self.git('checkout', 'trunk')
        with tempfile.TemporaryDirectory(prefix='hard remote ') as tmp:
            remote = Path(tmp) / 'remote.git'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            self.git('remote', 'add', 'origin', str(remote))
            self.git('push', '-u', 'origin', 'trunk')
            (self.root / 'source.py').write_text('implemented\n')
            self.git('add', '--', 'source.py')
            self.git('commit', '--only', '-m', 'implementation', '--', 'source.py')
            (self.root / 'source.py').write_text('[Assumption] quality fix\n')
            trace = []
            self.git('commit', '--only', '-m', 'quality fix', '--', 'source.py')
            trace.append('commit')
            gate = checks.assumption_gate(self.root, 'origin/trunk', 'origin/trunk')
            trace.append(gate['status'])
            self.assertNotEqual('PASS', gate['status'])
            self.assertEqual(self.start, self.git('ls-remote', 'origin', 'refs/heads/trunk').split()[0])
            (self.root / 'source.py').write_text('quality fix\n')
            self.git('commit', '--only', '-m', 'approved resolution', '--', 'source.py')
            trace.append('commit')
            gate = checks.assumption_gate(self.root, 'origin/trunk', 'origin/trunk')
            trace.append(gate['status'])
            self.assertEqual('PASS', gate['status'])
            self.assertEqual(gate['head'], self.git('rev-parse', 'HEAD').strip())
            self.git('push', 'origin', 'trunk')
            trace.append('push')
            self.assertEqual(['commit', gate['status'], 'push'], trace[-3:])
            remote_head = self.git('ls-remote', 'origin', 'refs/heads/trunk').split()[0]
            self.assertEqual(remote_head, self.git('rev-parse', 'HEAD').strip())
            self.assertEqual('quality fix\n', self.git('show', remote_head + ':source.py'))


if __name__ == '__main__':
    unittest.main()
