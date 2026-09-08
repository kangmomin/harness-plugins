import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_workflow_results import fixture, results


class WorktreeFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fingerprint space ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.git('config', 'commit.gpgsign', 'false')
        (self.root / 'app.py').write_text('# stable header\nVALUE = 1\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '--allow-empty', '-qm', 'fixture')

    def record(self, include_head=False):
        tree = results.tested_tree(self.root, include_head=include_head)
        data = fixture()
        data['tested_tree'] = tree
        data['events'] = [dict(domain='be', kind='unit', phase='8.1', iteration=1,
                               verdict='PASS', terminal_state='DONE', tested_tree=tree.copy(), regression_count=0)]
        return data

    def test_actual_bytes_are_detected_with_textconv_and_index_flags(self):
        (self.root / '.gitattributes').write_text('*.py diff=audit\n')
        self.git('config', 'diff.audit.textconv', 'head -n 1')
        self.commit()
        for flag in (None, '--assume-unchanged', '--skip-worktree'):
            with self.subTest(flag=flag):
                (self.root / 'app.py').write_text('# stable header\nVALUE = 1\n')
                if flag:
                    self.git('update-index', flag, 'app.py')
                data = self.record()
                (self.root / 'app.py').write_text('# stable header\nVALUE = 999\n')
                changed = results.tested_tree(self.root)
                with self.assertRaisesRegex(ValueError, 'stale verification'):
                    results.check_current(data, changed, ['unit'])
                if flag:
                    self.git('update-index', flag.replace('--', '--no-', 1), 'app.py')

    def test_staging_addition_deletion_and_commits_keep_identical_inputs(self):
        for action in ('add', 'delete', 'directory-to-file', 'file-to-directory', 'empty'):
            with self.subTest(action=action):
                if action == 'add':
                    (self.root / '한글\nname.py').write_text('new input\n')
                elif action == 'delete':
                    (self.root / 'app.py').unlink()
                elif action == 'directory-to-file':
                    (self.root / 'package').mkdir()
                    (self.root / 'package/source.py').write_text('nested input\n')
                    self.commit()
                    (self.root / 'package/source.py').unlink()
                    (self.root / 'package').rmdir()
                    (self.root / 'package').write_text('flat input\n')
                elif action == 'file-to-directory':
                    (self.root / 'package').unlink()
                    (self.root / 'package').mkdir()
                    (self.root / 'package/source.py').write_text('nested input\n')
                data = self.record()
                self.git('add', '-A')
                self.assertTrue(results.check_current(data, results.tested_tree(self.root), ['unit'])['current'])
                self.commit()
                current = results.tested_tree(self.root)
                self.assertNotEqual(data['tested_tree']['head'], current['head'])
                self.assertTrue(results.check_current(data, current, ['unit'])['current'])
                data['tested_tree'] = current
                results.validate(data)

    def test_recorded_head_dependency_and_legacy_evidence_stay_strict(self):
        data = self.record(include_head=True)
        self.commit()
        with self.assertRaisesRegex(ValueError, 'stale verification'):
            results.check_current(data, results.tested_tree(self.root), ['unit'])
        legacy = fixture()['tested_tree']
        self.assertTrue(results.same_tree(legacy, legacy))
        self.assertFalse(results.same_tree(legacy, {**legacy, 'head': 'c' * 40}))
        self.assertFalse(results.same_tree(legacy, {**legacy, 'fingerprint_version': 2, 'head_sensitive': False}))
        for bad in ({'fingerprint_version': 3}, {'head_sensitive': 'false'}):
            invalid = copy.deepcopy(data)
            invalid['tested_tree'].update(bad)
            with self.assertRaisesRegex(ValueError, 'tested_tree invalid'):
                results.validate(invalid)

    def test_modes_symlink_targets_and_deletions_change_the_fingerprint(self):
        path = self.root / 'app.py'
        previous = results.tested_tree(self.root)
        path.chmod(0o755)
        changed = results.tested_tree(self.root)
        self.assertFalse(results.same_tree(previous, changed))
        path.unlink()
        path.symlink_to('missing-one')
        symlink = results.tested_tree(self.root)
        self.assertFalse(results.same_tree(changed, symlink))
        path.unlink()
        path.symlink_to('missing-two')
        self.assertFalse(results.same_tree(symlink, results.tested_tree(self.root)))
        path.unlink()
        self.assertFalse(results.same_tree(symlink, results.tested_tree(self.root)))

    def test_parent_symlink_and_special_files_fail_without_reading_them(self):
        nested = self.root / 'nested'
        nested.mkdir()
        (nested / 'tracked.py').write_text('tracked\n')
        self.commit()
        (nested / 'tracked.py').unlink()
        nested.rmdir()
        nested.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink parent'):
            results.tested_tree(self.root)
        nested.unlink()
        (self.root / 'app.py').unlink()
        os.mkfifo(self.root / 'app.py')
        with self.assertRaisesRegex(ValueError, 'unsupported file type'):
            results.tested_tree(self.root)

    def test_submodule_bytes_are_included_even_when_git_hides_dirty_content(self):
        with tempfile.TemporaryDirectory(prefix='submodule source ') as directory:
            child = Path(directory)
            subprocess.run(['git', 'init', '-q', str(child)], check=True)
            (child / 'source.py').write_text('original\n')
            subprocess.run(['git', '-C', str(child), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(child), '-c', 'user.name=Fixture', '-c',
                            'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                            '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'initial'], check=True)
            self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'module')
            self.commit()
            data = self.record()
            self.git('-C', str(self.root / 'module'), 'update-index', '--assume-unchanged', 'source.py')
            (self.root / 'module/source.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'stale verification'):
                results.check_current(data, results.tested_tree(self.root), ['unit'])

    def test_incomplete_submodule_cannot_fall_back_to_the_parent_repository(self):
        head = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '160000', head, 'module')
        (self.root / 'module/.git').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'invalid submodule worktree'):
            results.tested_tree(self.root)


if __name__ == '__main__':
    unittest.main()
