import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_state', ROOT / 'common/skills/sync-base/assets/sync_state.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncStateTests(unittest.TestCase):
    def test_worktree_subdirectory_detects_real_rebase_and_retains_conflict(self):
        with tempfile.TemporaryDirectory(prefix='sync repo 한글 ') as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            def git(cwd, *args, check=True):
                return subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, check=check, text=True)
            git(root, 'init', '-b', 'main')
            git(root, 'config', 'user.name', 'Fixture')
            git(root, 'config', 'user.email', 'fixture@example.invalid')
            (root / 'file').write_text('base\n')
            git(root, 'add', '.')
            git(root, 'commit', '-m', 'base')
            wt = Path(tmp) / 'linked worktree'
            git(root, 'worktree', 'add', '-b', 'feature', str(wt))
            (root / 'file').write_text('main\n')
            git(root, 'commit', '-am', 'main')
            (wt / 'file').write_text('feature\n')
            git(wt, 'commit', '-am', 'feature')
            result = git(wt, 'rebase', 'main', check=False)
            self.assertNotEqual(result.returncode, 0)
            (wt / 'nested').mkdir()
            before = (wt / 'file').read_bytes()
            state = sync.state(wt / 'nested')
            self.assertEqual(state['status'], 'BLOCKED:OTHER_OP_IN_PROGRESS')
            self.assertIn('rebase-merge', state['operations'])
            self.assertTrue(Path(state['git_paths']['rebase-merge']).is_dir())
            self.assertEqual(before, (wt / 'file').read_bytes())
            git(wt, 'rebase', '--abort')

    def test_saved_stash_oid_restores_index_and_untracked_after_other_stash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (root / 'file').write_text('base\n')
            git('add', '.')
            git('commit', '-m', 'base')
            (root / 'file').write_text('staged\n')
            git('add', 'file')
            (root / 'file').write_text('unstaged\n')
            (root / 'untracked 한글').write_text('owned snapshot\n')
            index = git('ls-files', '-s')
            token = 'sync-base:' + uuid.uuid4().hex
            before_stash = git('rev-parse', 'HEAD')
            git('stash', 'push', '--include-untracked', '-m', token)
            saved = git('rev-parse', 'refs/stash')
            self.assertFalse(sync.state(root)['dirty'])
            (root / 'other-user-file').write_text('later stash\n')
            git('stash', 'push', '--include-untracked', '-m', 'later stash')
            other = git('rev-parse', 'refs/stash')
            self.assertNotEqual(saved, other)
            # Another worktree/user can push a stash before our post-push OID lookup.
            identified = sync.owned_stash(root, token, before_stash)['oid']
            self.assertEqual(identified, saved)
            git('stash', 'apply', '--index', identified)
            self.assertEqual(git('ls-files', '-s'), index)
            self.assertEqual((root / 'file').read_text(), 'unstaged\n')
            self.assertEqual((root / 'untracked 한글').read_text(), 'owned snapshot\n')
            self.assertEqual(git('rev-parse', 'refs/stash'), other)
            self.assertFalse((root / 'other-user-file').exists())

    def test_refresh_added_renamed_deleted_targets_without_recreating_old_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            git('init', '-b', 'main')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (root / 'VERSION').write_text('1.0.0\n')
            (root / 'swagger.json').write_text('{"info":{"version":"1.0.0"}}\n')
            git('add', '.')
            git('commit', '-m', 'baseline')
            git('checkout', '-b', 'feature')
            git('commit', '--allow-empty', '-m', 'feature change')
            saved_head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
            before = sync.targets(root, ['swagger.json'])
            self.assertEqual(before['versions'], ['VERSION'])
            git('checkout', 'main')
            (root / 'VERSION').rename(root / 'VERSION.txt')
            (root / 'swagger.json').rename(root / 'api-spec.json')
            (root / 'openapi.yaml').write_text('info:\n  version: 1.0.0\n')
            git('add', '-A')
            git('commit', '-m', 'rename version and replace swagger')
            git('checkout', 'feature')
            git('merge', '--no-ff', '--no-edit', 'main')
            after = sync.targets(root, ['swagger.json', 'openapi.yaml'], saved_head)
            self.assertEqual(after['versions'], ['VERSION.txt'])
            self.assertEqual(after['swagger'], ['openapi.yaml'])
            self.assertEqual(after['missing'], ['swagger.json'])
            self.assertEqual(after['renames']['swagger.json'], 'api-spec.json')
            mapped = sync.targets(root, [after['renames']['swagger.json'], 'openapi.yaml'])
            self.assertEqual(mapped['swagger'], ['api-spec.json', 'openapi.yaml'])
            (root / 'VERSION.txt').unlink()
            self.assertEqual(sync.targets(root)['version_status'], 'ABSENT')
            self.assertFalse((root / 'swagger.json').exists())

    def test_diff3_and_zdiff3_separate_ancestor_and_preserve_nonconflict_lines(self):
        for size in (5, 7, 10):
            for ancestor in ('', '|' * size + ' base\r\n  version: 1.0.0\r\n'):
                text = ('info:\r\n' + '<' * size + ' ours\r\n  version: 1.0.1\r\n' + ancestor +
                        '=' * size + '\r\n  version: 1.0.2\r\n' + '>' * size + ' theirs\r\npaths: {}\r\n')
                block, = sync.hunks(text)
                self.assertEqual(block['ours'], ['  version: 1.0.1\r\n'])
                self.assertEqual(block['theirs'], ['  version: 1.0.2\r\n'])
                self.assertEqual(block['ancestor'], ['  version: 1.0.0\r\n'] if ancestor else [])
                lines = text.splitlines(keepends=True)
                merged = ''.join(lines[:block['start_line']-1] + ['  version: 1.0.2\r\n'] + lines[block['end_line']:])
                self.assertEqual(merged, 'info:\r\n  version: 1.0.2\r\npaths: {}\r\n')
        with self.assertRaises(ValueError):
            sync.hunks('<<<<<<< ours\n1.0.0\n=======\n1.0.1\n')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, version in [('ours', '1.0.1'), ('base', '1.0.0'), ('theirs', '1.0.2')]:
                (root / name).write_text(version + '\n')
            for style in ('--diff3', '--zdiff3'):
                proc = subprocess.run(['git', 'merge-file', '-p', style, '--marker-size=5',
                                       str(root / 'ours'), str(root / 'base'), str(root / 'theirs')],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                block, = sync.hunks(proc.stdout)
                self.assertEqual(block['marker_size'], 5)
                self.assertEqual(block['ancestor'], ['1.0.0\n'])

    def test_new_version_from_merge_replaces_premerge_absent_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            git('commit', '--allow-empty', '-m', 'initial')
            git('checkout', '-b', 'feature')
            git('commit', '--allow-empty', '-m', 'feature')
            before_sha = git('rev-parse', 'HEAD')
            self.assertEqual(sync.targets(root)['version_status'], 'ABSENT')
            git('checkout', 'main')
            (root / 'VERSION').write_text('1.2.0\n')
            (root / 'openapi.json').write_text('{"info":{"version":"1.2.0"}}\n')
            git('add', '.')
            git('commit', '-m', 'add version')
            git('checkout', 'feature')
            git('merge', '--no-ff', '--no-edit', 'main')
            current = sync.targets(root, before_merge=before_sha)
            self.assertEqual(current['version_status'], 'FOUND')
            self.assertEqual(current['versions'], ['VERSION'])
            self.assertEqual(current['swagger'], ['openapi.json'])


if __name__ == '__main__':
    unittest.main()
