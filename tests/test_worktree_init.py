import ast
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'minmos-harness/skills/init/assets'
sys.path.insert(0, str(ASSETS))
spec = importlib.util.spec_from_file_location('worktree_init', ASSETS / 'worktree_init.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
sys.path.pop(0)


class WorktreeInstallTests(unittest.TestCase):
    def test_metadata_class_keeps_tested_linux_darwin_boundary_parity(self):
        def klass(path):
            source = path.read_text()
            node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Metadata')
            return ast.get_source_segment(source, node)
        self.assertEqual(klass(ASSETS / 'hook_metadata.py'), klass(ROOT / 'work-log/mcp/lib/io_worker.py'))

    def test_missing_settings_first_install_and_repeat_keep_exact_bytes(self):
        with tempfile.TemporaryDirectory(prefix='hook 설정 ') as tmp:
            settings = Path(tmp) / '.claude/settings.json'
            got = hook.install(settings)
            self.assertEqual(got['status'], 'INSTALLED')
            self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)
            data = settings.read_bytes()
            self.assertEqual(hook.install(settings)['status'], 'UNCHANGED')
            self.assertEqual(settings.read_bytes(), data)
            self.assertTrue(Path(shlex.split(got['command'])[1]).is_file())
            self.assertEqual(len(json.loads(data)['hooks']['SessionStart']), 1)
            self.assertEqual(hook.inspect_install(settings)['status'], 'INSTALLED')

    def test_existing_hooks_metadata_and_user_script_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            original = {'permissions': {'deny': ['Write(secret/**)']}, 'hooks': {
                'SessionStart': [{'matcher': 'startup', 'hooks': [{'type': 'command', 'command': 'echo user-hook'}]}],
                'Stop': [{'hooks': [{'type': 'command', 'command': 'echo stop'}]}]}}
            settings.write_text(json.dumps(original))
            settings.chmod(0o640)
            if sys.platform == 'linux':
                os.setxattr(settings, 'user.fixture', b'preserved')
            result = hook.install(settings)
            actual = json.loads(settings.read_bytes())
            self.assertEqual(actual['hooks']['SessionStart'][0], original['hooks']['SessionStart'][0])
            self.assertEqual(actual['hooks']['Stop'], original['hooks']['Stop'])
            self.assertEqual(actual['permissions'], original['permissions'])
            self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o640)
            if sys.platform == 'linux':
                self.assertEqual(os.getxattr(settings, 'user.fixture'), b'preserved')
            self.assertEqual(result['status'], 'INSTALLED')

    def test_invalid_duplicate_and_legacy_settings_block_unchanged(self):
        cases = [b'broken{', b'null', b'{"hooks":{},"hooks":{}}',
                 json.dumps({'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': '~/.claude/hooks/worktree-init.sh'}]}]}}).encode()]
        for content in cases:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                settings = Path(tmp) / 'settings.json'
                settings.write_bytes(content)
                with self.assertRaises((ValueError, hook.Blocked)):
                    hook.install(settings)
                self.assertEqual(settings.read_bytes(), content)
                self.assertFalse((Path(tmp) / 'hooks').exists())

    def test_noncooperating_settings_change_and_first_create_are_not_overwritten(self):
        for exists in [True, False]:
            with self.subTest(exists=exists), tempfile.TemporaryDirectory() as tmp:
                settings = Path(tmp) / 'settings.json'
                if exists:
                    settings.write_text('{"original":true}')
                with self.assertRaisesRegex(hook.Blocked, 'SETTINGS_CHANGED|DESTINATION_CREATED'):
                    hook.install(settings, before_publish=lambda: settings.write_text('{"other_writer":true}'))
                self.assertEqual(settings.read_text(), '{"other_writer":true}')
                self.assertEqual(list(Path(tmp).rglob('*.tmp')), [])
                self.assertEqual(list((Path(tmp) / 'hooks').glob('minmos-worktree-init-*')), [])

    def test_replaced_temp_does_not_overwrite_settings_or_delete_other_writer_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            original = b'{"permissions":{"deny":["Write(secret/**)"]}}'
            settings.write_bytes(original)
            replacements = []
            def swap():
                path = next(Path(tmp).glob('.minmos-*.tmp'))
                path.unlink()
                path.write_text('{"other_writer":true}')
                replacements.append(path)
            with self.assertRaisesRegex(hook.Blocked, 'TEMP_CHANGED'):
                hook.install(settings, before_publish=swap)
            self.assertEqual(settings.read_bytes(), original)
            self.assertEqual(replacements[0].read_text(), '{"other_writer":true}')

    def test_last_moment_publication_change_reports_unknown_without_false_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            settings.write_text('{"original":true}')
            replace = hook.os.replace
            def swap(source, destination, *args, **kwargs):
                fd = kwargs['src_dir_fd']
                os.unlink(source, dir_fd=fd)
                with os.fdopen(os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd), 'wb') as stream:
                    stream.write(b'{"other_writer":true}')
                return replace(source, destination, *args, **kwargs)
            with patch.object(hook.os, 'replace', swap), self.assertRaisesRegex(hook.Blocked, 'UNKNOWN:PUBLISH'):
                hook.install(settings)
            self.assertEqual(settings.read_text(), '{"other_writer":true}')
            self.assertTrue(list((Path(tmp) / 'hooks').glob('minmos-worktree-init-*')))

    def test_interrupt_during_bundle_creation_cleans_earlier_owned_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            settings.write_text('{"original":true}')
            publish = hook.publish
            def interrupted(anchor, content, *args, **kwargs):
                if anchor.name == 'hook_metadata.py':
                    raise KeyboardInterrupt()
                return publish(anchor, content, *args, **kwargs)
            with patch.object(hook, 'publish', interrupted), self.assertRaises(KeyboardInterrupt):
                hook.install(settings)
            self.assertEqual(settings.read_text(), '{"original":true}')
            self.assertEqual(list((Path(tmp) / 'hooks').glob('minmos-worktree-init-*')), [])
            self.assertEqual(hook.inspect_install(settings)['status'], 'MISSING')

    def test_hook_directory_symlink_never_creates_external_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'home'
            root.mkdir()
            outside = Path(tmp) / 'outside'
            outside.mkdir()
            (root / 'hooks').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OSError):
                hook.install(root / 'settings.json')
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((root / 'settings.json').exists())

    def test_directory_fsync_after_write_is_unknown_and_cleanup_failure_is_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            settings.write_text('{"original":true}')
            sync = hook.os.fsync
            armed = False
            def arm():
                nonlocal armed
                armed = True
            def fail(fd):
                if armed and stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise OSError('injected directory sync error')
                return sync(fd)
            with patch.object(hook.os, 'fsync', fail), self.assertRaisesRegex(hook.Blocked, 'UNKNOWN:PUBLISH'):
                hook.install(settings, before_publish=arm)
            self.assertIn('hooks', json.loads(settings.read_bytes()))
            self.assertEqual(hook.inspect_install(settings)['status'], 'INSTALLED')
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            original_unlink = hook.os.unlink
            parent = Path(tmp).stat().st_ino
            def fail_unlink(name, *args, **kwargs):
                if str(name).startswith('.minmos-') and os.fstat(kwargs['dir_fd']).st_ino == parent:
                    raise OSError('injected cleanup error')
                return original_unlink(name, *args, **kwargs)
            with patch.object(hook.os, 'unlink', fail_unlink):
                result = hook.install(settings)
            self.assertEqual(result['status'], 'INSTALLED')
            self.assertEqual(result['cleanup_warnings'][0]['reason'], 'TEMP_CLEANUP_FAILED')
            self.assertEqual(hook.inspect_install(settings)['status'], 'INSTALLED')

    def test_interrupt_before_settings_publish_leaves_original_and_no_partial_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            settings.write_text('{"original":true}')
            def interrupted():
                raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                hook.install(settings, before_publish=interrupted)
            self.assertEqual(settings.read_text(), '{"original":true}')
            self.assertEqual(list(Path(tmp).rglob('*.tmp')), [])
            self.assertEqual(list((Path(tmp) / 'hooks').glob('minmos-worktree-init-*')), [])


class WorktreeCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='worktree 한글 ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.main = self.base / 'main with space'
        self.other = self.base / 'worktree 공백'
        self.main.mkdir()
        self.git(self.main, 'init', '-b', 'main')
        self.git(self.main, 'config', 'user.name', 'Fixture')
        self.git(self.main, 'config', 'user.email', 'fixture@example.invalid')
        (self.main / '.gitignore').write_text('.env\n.mcp.json\nsecret/\n')
        self.git(self.main, 'add', '.')
        self.git(self.main, 'commit', '-m', 'baseline')
        self.git(self.main, 'worktree', 'add', '-b', 'test', str(self.other))
        for name in hook.FILES:
            path = self.main / name
            path.parent.mkdir(exist_ok=True)
            path.write_text('fixture-only:' + name)
            path.chmod(0o600)

    def git(self, root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)

    def test_real_installed_sessionstart_from_nested_whitespace_path_copies_exact_files(self):
        result = hook.install(self.base / 'home/.claude/settings.json')
        nested = self.other / 'nested folder'
        nested.mkdir()
        called = subprocess.run(shlex.split(result['command']), input=json.dumps({'cwd': str(nested)}), text=True, capture_output=True)
        self.assertEqual(called.returncode, 0, called.stderr)
        report = json.loads(called.stderr)
        self.assertEqual(report['copied'], list(hook.FILES))
        for name in hook.FILES:
            destination = self.other / name
            self.assertEqual(destination.read_bytes(), (self.main / name).read_bytes())
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertEqual(self.git(self.other, 'ls-files', '--', name), b'')
            self.git(self.other, 'check-ignore', '--quiet', '--', name)
        self.assertEqual(hook.copy_worktree(nested)['copied'], [])
        self.assertEqual(hook.copy_worktree(self.main)['status'], 'MAIN_WORKTREE')

    def test_legal_trailing_newline_worktree_path_keeps_complete_root(self):
        renamed = self.base / 'worktree ending newline\n'
        self.git(self.main, 'worktree', 'move', str(self.other), str(renamed))
        got = hook.copy_worktree(renamed)
        self.assertEqual(got['copied'], list(hook.FILES))
        self.assertEqual((renamed / '.env').read_bytes(), (self.main / '.env').read_bytes())

    def test_existing_files_and_symlinks_are_never_overwritten(self):
        (self.other / '.env').write_text('own-worktree')
        outside = self.base / 'outside'
        outside.write_text('sentinel')
        (self.other / '.mcp.json').symlink_to(outside)
        hook.copy_worktree(self.other)
        self.assertEqual((self.other / '.env').read_text(), 'own-worktree')
        self.assertEqual(outside.read_text(), 'sentinel')
        self.assertTrue((self.other / '.mcp.json').is_symlink())

    def test_missing_ignore_or_tracked_source_blocks_before_any_copy(self):
        (self.other / '.gitignore').write_text('secret/\n')
        with self.assertRaisesRegex(hook.Blocked, 'NOT_IGNORED'):
            hook.copy_worktree(self.other)
        self.assertFalse((self.other / '.mcp.json').exists())
        (self.other / '.gitignore').write_text('.env\n.mcp.json\nsecret/\n')
        self.git(self.main, 'add', '-f', '.env')
        with self.assertRaisesRegex(hook.Blocked, 'TRACKED_COPY_PATH'):
            hook.copy_worktree(self.other)
        self.assertFalse((self.other / '.mcp.json').exists())

    def test_parent_directory_swap_blocks_external_write_and_preserves_sentinel(self):
        directory = self.other / 'secret'
        directory.mkdir()
        outside = self.base / 'outside'
        outside.mkdir()
        sentinel = outside / '.env'
        sentinel.write_text('sentinel')
        original_publish = hook.publish
        swapped = False
        def publish(anchor, content, *args, **kwargs):
            nonlocal swapped
            if anchor.path == directory / '.env' and not swapped:
                swapped = True
                directory.rename(self.other / 'secret-old')
                directory.symlink_to(outside, target_is_directory=True)
            return original_publish(anchor, content, *args, **kwargs)
        with patch.object(hook, 'publish', publish), self.assertRaisesRegex(hook.Blocked, 'DIRECTORY_CHANGED'):
            hook.copy_worktree(self.other)
        self.assertEqual(sentinel.read_text(), 'sentinel')
        self.assertEqual(list((self.other / 'secret-old').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
