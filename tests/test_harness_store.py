import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'be-harness/skills/start-workflow/assets/harness_store.py'
PROFILE = ROOT / 'be-harness/skills/config/assets/profile.py'
spec = importlib.util.spec_from_file_location('harness_store', SCRIPT)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)
POSIX_ONLY = unittest.skipIf(os.name == 'nt', 'POSIX 권한·symlink 전용 — CI에서 확인')


def load_profile_module():
    profile_spec = importlib.util.spec_from_file_location('harness_profile_parity', PROFILE)
    module = importlib.util.module_from_spec(profile_spec)
    profile_spec.loader.exec_module(module)
    return module


def isolated_env(tmp):
    tmp = Path(tmp)
    for name in ('home', 'functions', 'xdg-config', 'xdg-cache', 'systemp'):
        (tmp / name).mkdir(exist_ok=True)
    gitconfig = tmp / 'gitconfig'
    gitconfig.write_text('')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') and k != 'WORK_LOG_ROOT'}
    env.update(
        HARNESS_PLUGIN_HOME=str(tmp / 'base'), HARNESS_FUNCTION_DIR=str(tmp / 'functions'),
        HOME=str(tmp / 'home'), USERPROFILE=str(tmp / 'home'),
        XDG_CONFIG_HOME=str(tmp / 'xdg-config'), XDG_CACHE_HOME=str(tmp / 'xdg-cache'),
        TMPDIR=str(tmp / 'systemp'), TEMP=str(tmp / 'systemp'), TMP=str(tmp / 'systemp'),
        GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM='1', PYTHONUTF8='1')
    return env


def git(cwd, *args, env=None):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=cwd, env=env,
                          check=True, capture_output=True, text=True).stdout.strip()


def same(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def inside(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='harness-store-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = isolated_env(self.tmp)
        self.base = self.tmp / 'base'
        self.home = self.tmp / 'home'

    def repo(self, name='demo-repo', origin=None):
        path = self.tmp / 'repos' / name
        path.mkdir(parents=True)
        git(path, 'init', '-q', env=self.env)
        if origin:
            git(path, 'remote', 'add', 'origin', origin, env=self.env)
        return path

    def run_store(self, *args, cwd=None, env=None, body=None, flags=('-B',)):
        return subprocess.run([sys.executable, *flags, str(SCRIPT), *args], cwd=cwd or self.tmp,
                              env=env or self.env, input=body, capture_output=True, text=True,
                              encoding='utf-8', timeout=60)

    def ok(self, *args, **kwargs):
        result = self.run_store(*args, **kwargs)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def fails(self, *args, **kwargs):
        result = self.run_store(*args, **kwargs)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def profile(self, cwd, text, domain='be'):
        path = Path(cwd) / '.claude' / (domain + '-harness.local.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8') if isinstance(text, str) else text)
        return path


class AbsolutePathRuleTests(unittest.TestCase):
    def test_shared_absolute_path_table_for_both_platforms(self):
        cases = json.loads((ROOT / 'tests/fixtures/abs-path-cases.json').read_text(encoding='utf-8'))
        for case in cases:
            for platform in ('win', 'posix'):
                with self.subTest(input=case['input'], platform=platform):
                    self.assertIs(case[platform], store.is_abs_strict(case['input'], platform))


class ResolveTests(StoreCase):
    def test_default_function_root_and_project_without_env(self):
        repo = self.repo()
        env = {k: v for k, v in self.env.items() if k not in ('HARNESS_PLUGIN_HOME', 'HARNESS_FUNCTION_DIR')}
        result = self.ok('resolve', '--cwd', str(repo), env=env)
        self.assertTrue(same(result['functionRoot'], self.home / '.harness-plugin' / 'function'))
        self.assertEqual('demo-repo', result['project'])

    def test_function_dir_env_overrides_function_root(self):
        repo = self.repo()
        functions = self.tmp / 'custom-functions'
        result = self.ok('resolve', '--cwd', str(repo), env={**self.env, 'HARNESS_FUNCTION_DIR': str(functions)})
        self.assertTrue(same(result['functionRoot'], functions))

    def test_env_combinations_choose_base_doc_root_and_function_root(self):
        repo = self.repo()
        vault = self.tmp / 'vault'
        vault.mkdir()
        functions = self.tmp / 'fn'
        plain = {k: v for k, v in self.env.items() if k not in ('HARNESS_PLUGIN_HOME', 'HARNESS_FUNCTION_DIR')}
        default_base = self.home / '.harness-plugin'
        combos = [
            ('none', plain, default_base, default_base / 'work-log/docs', default_base / 'function'),
            ('home', {**plain, 'HARNESS_PLUGIN_HOME': str(self.base)}, self.base, self.base / 'work-log/docs', self.base / 'function'),
            ('home+root', {**plain, 'HARNESS_PLUGIN_HOME': str(self.base), 'WORK_LOG_ROOT': str(vault)}, self.base, vault, self.base / 'function'),
            ('all', {**plain, 'HARNESS_PLUGIN_HOME': str(self.base), 'WORK_LOG_ROOT': str(vault), 'HARNESS_FUNCTION_DIR': str(functions)},
             self.base, vault, functions),
        ]
        for label, env, base, doc_root, function_root in combos:
            with self.subTest(label):
                result = self.ok('resolve', '--cwd', str(repo), env=env)
                self.assertTrue(same(result['base'], base))
                self.assertTrue(same(result['docRoot'], doc_root))
                self.assertTrue(same(result['docDir'], doc_root / 'demo-repo'))
                self.assertTrue(same(result['functionRoot'], function_root))
                self.assertTrue(same(result['feedbackRoot'], base / 'feedback-submissions' / 'demo-repo'))
                self.assertEqual([], result['warnings'])

    def test_blank_or_relative_env_is_ignored_with_warning(self):
        repo = self.repo()
        for value in ('', '   ', 'relative/dir', './x'):
            for name in ('HARNESS_PLUGIN_HOME', 'HARNESS_FUNCTION_DIR', 'WORK_LOG_ROOT'):
                with self.subTest(name=name, value=value):
                    result = self.ok('resolve', '--cwd', str(repo), env={**self.env, name: value})
                    default_base = self.home / '.harness-plugin'
                    if name == 'HARNESS_PLUGIN_HOME':
                        self.assertTrue(same(result['base'], default_base))
                    elif name == 'HARNESS_FUNCTION_DIR':
                        self.assertTrue(same(result['functionRoot'], self.base / 'function'))
                    else:
                        self.assertTrue(same(result['docRoot'], self.base / 'work-log/docs'))
                    if value.strip():
                        self.assertTrue(any(name in w for w in result['warnings']), result['warnings'])

    def test_ensure_creates_doc_dir_only_when_requested(self):
        repo = self.repo()
        result = self.ok('resolve', '--cwd', str(repo))
        self.assertFalse(Path(result['docDir']).exists())
        result = self.ok('resolve', '--cwd', str(repo), '--ensure')
        self.assertTrue(Path(result['docDir']).is_dir())

    def test_input_runs_under_isolated_python(self):
        repo = self.repo()
        result = self.ok('resolve', '--cwd', str(repo), flags=('-I', '-B'))
        self.assertEqual('demo-repo', result['project'])


class ProjectNameTests(StoreCase):
    def test_remote_url_table(self):
        cases = [
            ('https://user:s3cret@git.example.com:8443/org/my-repo.git', 'my-repo'),
            ('https://git.example.com/org/my-repo/', 'my-repo'),
            ('git@github.com:org/my-repo.git', 'my-repo'),
            ('git@host:my-repo.git', 'my-repo'),
            ('C:\\work\\my-repo', 'my-repo'),
            ('/srv/git/my-repo.git', 'my-repo'),
            ('', None),
            ('/.git', None),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(expected, store.remote_project_name(url))

    def test_origin_name_is_used_and_url_is_not_printed(self):
        repo = self.repo('local-name', origin='https://user:TOPSECRET@git.example.com/org/remote-name.git')
        result = self.run_store('resolve', '--cwd', str(repo))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(('remote-name', 'origin'), (data['project'], data['projectSource']))
        self.assertNotIn('TOPSECRET', result.stdout + result.stderr)
        self.assertNotIn('git.example.com', result.stdout + result.stderr)

    def test_missing_origin_uses_common_dir_name(self):
        repo = self.repo('no-origin')
        sub = repo / 'nested'
        sub.mkdir()
        data = self.ok('resolve', '--cwd', str(sub))
        self.assertEqual(('no-origin', 'common-dir'), (data['project'], data['projectSource']))

    def test_main_checkout_and_worktree_share_origin_project(self):
        layout = self.tmp / 'harness-plugins'
        main = layout / '_main'
        main.mkdir(parents=True)
        git(main, 'init', '-q', env=self.env)
        git(main, 'remote', 'add', 'origin', 'git@github.com:owner/harness-plugins.git', env=self.env)
        git(main, 'commit', '-q', '--allow-empty', '-m', 'init', env=self.env)
        worktree = layout / 'issue-1'
        git(main, 'worktree', 'add', '-q', '--detach', str(worktree), env=self.env)
        names = {self.ok('resolve', '--cwd', str(cwd))['project'] for cwd in (main, worktree)}
        self.assertEqual({'harness-plugins'}, names)

    def test_bare_repository_strips_git_suffix(self):
        bare = self.tmp / 'bare-name.git'
        git(self.tmp, 'init', '-q', '--bare', str(bare), env=self.env)
        data = self.ok('resolve', '--cwd', str(bare))
        self.assertEqual('bare-name', data['project'])

    def test_non_git_directory_uses_folder_name(self):
        folder = self.tmp / 'plain-folder'
        folder.mkdir()
        data = self.ok('resolve', '--cwd', str(folder))
        self.assertEqual(('plain-folder', 'dir'), (data['project'], data['projectSource']))

    def test_korean_repository_name(self):
        repo = self.repo('한글저장소')
        self.assertEqual('한글저장소', self.ok('resolve', '--cwd', str(repo))['project'])

    def test_broken_git_metadata_is_error(self):
        folder = self.tmp / 'broken'
        folder.mkdir()
        (folder / '.git').write_text('gitdir: missing-git-dir\n')
        self.fails('resolve', '--cwd', str(folder))
        self.fails('save-doc', '--cwd', str(folder), '--name', 'a.md', body='body')

    def test_git_not_executable_is_error(self):
        repo = self.repo()
        empty = self.tmp / 'empty-path'
        empty.mkdir()
        self.fails('resolve', '--cwd', str(repo), env={**self.env, 'PATH': str(empty)})

    @POSIX_ONLY
    def test_dubious_ownership_reports_safe_directory_hint(self):
        repo = self.repo()
        fake = self.tmp / 'fake-bin'
        fake.mkdir()
        (fake / 'git').write_text('#!/bin/sh\necho "fatal: detected dubious ownership in repository" >&2\nexit 128\n')
        (fake / 'git').chmod(0o755)
        result = self.fails('resolve', '--cwd', str(repo), env={**self.env, 'PATH': str(fake) + os.pathsep + self.env['PATH']})
        self.assertIn('safe.directory', result.stdout + result.stderr)

    def test_slug_reserved_excluded_and_truncated_names(self):
        cases = [
            ('a b', 'a-b'),
            ('한글', '한글'),
            ('CON', 'CON-project'),
            ('con.x', 'con.x-project'),
            ('Lpt1', 'Lpt1-project'),
            ('node_modules', 'node_modules-project'),
            ('.hidden', 'hidden'),
            ('a' * 63 + '.b', 'a' * 63),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(expected, store.slug(name))
        for name in ('', '.', '..', '...'):
            with self.subTest(name=name), self.assertRaises(store.ConfigError):
                store.slug(name)


class SaveDocTests(StoreCase):
    def test_default_location_without_work_log_root(self):
        repo = self.repo()
        env = {k: v for k, v in self.env.items() if k != 'HARNESS_PLUGIN_HOME'}
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'spec.md', body='# Spec\n', env=env)
        expected = self.home / '.harness-plugin/work-log/docs/demo-repo/spec.md'
        self.assertTrue(Path(result['path']).is_absolute())
        self.assertTrue(same(result['path'], expected))
        self.assertEqual('# Spec\n', expected.read_text(encoding='utf-8'))
        self.assertIs(True, result['needsSync'])

    def test_work_log_root_location(self):
        repo = self.repo()
        vault = self.tmp / 'vault'
        vault.mkdir()
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'spec.md', body='body',
                         env={**self.env, 'WORK_LOG_ROOT': str(vault)})
        self.assertTrue(same(result['path'], vault / 'demo-repo' / 'spec.md'))

    def test_missing_work_log_root_or_unwritable_base_is_error_without_fallback(self):
        repo = self.repo()
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body',
                   env={**self.env, 'WORK_LOG_ROOT': str(self.tmp / 'missing-vault')})
        self.assertFalse((self.base / 'work-log').exists())
        self.base.mkdir()
        (self.base / 'work-log').write_text('not a directory')
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body')
        self.assertEqual([], list((self.home).rglob('a.md')))

    def test_existing_name_gets_numbered_suffix_and_original_is_unchanged(self):
        repo = self.repo()
        first = self.ok('save-doc', '--cwd', str(repo), '--name', 'note.md', body='one')
        second = self.ok('save-doc', '--cwd', str(repo), '--name', 'note.md', body='two')
        third = self.ok('save-doc', '--cwd', str(repo), '--name', 'note.md', body='three')
        self.assertEqual(['note.md', 'note-2.md', 'note-3.md'], [Path(r['path']).name for r in (first, second, third)])
        self.assertEqual('one', Path(first['path']).read_text(encoding='utf-8'))

    def test_invalid_names_are_rejected(self):
        repo = self.repo()
        for name in ('../escape.md', 'sub/dir.md', str(self.tmp / 'abs.md'), 'note.txt', 'CON.md', 'nul.html',
                     'x-workflow-report.md', 'x-e2e-report.html', 'bad\x01.md', 'trail.md.', 'trail.md ',
                     '가' * 67 + '.md'):
            with self.subTest(name=name):
                self.fails('save-doc', '--cwd', str(repo), '--name', name, body='body')
        self.assertEqual([], [p for p in self.tmp.rglob('*') if p.is_file() and p.suffix in ('.md', '.html', '.txt')])

    def test_empty_body_is_rejected(self):
        repo = self.repo()
        self.fails('save-doc', '--cwd', str(repo), '--name', 'empty.md', body='')
        self.assertFalse((self.base / 'work-log/docs/demo-repo/empty.md').exists())

    def test_prefer_file_and_directory_branches(self):
        repo = self.repo()
        target = repo / 'docs' / 'spec.md'
        target.parent.mkdir()
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'ignored.md', '--prefer', str(target), body='spec')
        self.assertTrue(same(result['path'], target))
        self.fails('save-doc', '--cwd', str(repo), '--name', 'ignored.md', '--prefer', str(target), body='again')
        self.assertEqual('spec', target.read_text(encoding='utf-8'))
        self.fails('save-doc', '--cwd', str(repo), '--name', 'x.md', '--prefer', str(repo / 'nope' / 'x.md'), body='x')
        in_dir = self.ok('save-doc', '--cwd', str(repo), '--name', 'spec.md', '--prefer', str(target.parent), body='other')
        self.assertTrue(same(in_dir['path'], target.parent / 'spec-2.md'))
        self.fails('save-doc', '--cwd', str(repo), '--name', 'x.md', '--prefer', str(repo / 'missing-dir'), body='x')

    def test_link_exists_and_unsupported_link_paths(self):
        folder = self.tmp / 'plain'
        folder.mkdir()
        env = {**self.env}
        real_link = os.link
        calls = []

        def first_exists(src, dst, *args, **kwargs):
            calls.append(dst)
            if len(calls) == 1:
                raise FileExistsError(17, 'exists')
            return real_link(src, dst, *args, **kwargs)

        with mock.patch.object(store.os, 'link', side_effect=first_exists):
            result = store.save_doc(folder, 'a.md', 'body', env=env, home=self.home)
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual('a-2.md', Path(result['path']).name)
        self.assertEqual('body', Path(result['path']).read_text(encoding='utf-8'))
        with mock.patch.object(store.os, 'link', side_effect=PermissionError(1, 'not permitted')):
            result = store.save_doc(folder, 'b.md', 'linkless', env=env, home=self.home)
        self.assertEqual('linkless', Path(result['path']).read_text(encoding='utf-8'))
        self.assertEqual([], [p.name for p in Path(result['path']).parent.iterdir() if p.name.startswith('.hs-')])

    def test_concurrent_save_doc_never_overwrites(self):
        repo = self.repo()
        procs = [subprocess.Popen([sys.executable, '-B', str(SCRIPT), 'save-doc', '--cwd', str(repo), '--name', 'race.md'],
                                  env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding='utf-8') for _ in range(2)]
        outputs = [p.communicate('body-%d' % i, timeout=60) for i, p in enumerate(procs)]
        self.assertEqual([0, 0], [p.returncode for p in procs], outputs)
        paths = [json.loads(out)['path'] for out, _ in outputs]
        self.assertEqual(2, len(set(paths)))
        self.assertEqual({'body-0', 'body-1'}, {Path(p).read_text(encoding='utf-8') for p in paths})

    def test_find_docs_matches_nfc_and_nfd_names(self):
        repo = self.repo()
        doc_dir = self.base / 'work-log/docs/demo-repo'
        doc_dir.mkdir(parents=True)
        (doc_dir / unicodedata.normalize('NFD', '2026-11-25-공유노트.md')).write_text('x', encoding='utf-8')
        (doc_dir / 'other.md').write_text('x', encoding='utf-8')
        result = self.ok('find-docs', '--cwd', str(repo), '--contains', unicodedata.normalize('NFC', '공유노트'))
        names = [unicodedata.normalize('NFC', Path(p if isinstance(p, str) else p['path']).name)
                 for p in (result if isinstance(result, list) else result['files'])]
        self.assertEqual(['2026-11-25-공유노트.md'], names)


class TrustBoundaryTests(StoreCase):
    def test_default_doc_dir_rejects_plugin_source_and_warns_inside_working_tree(self):
        repo = self.repo()
        doc_dir = self.base / 'work-log/docs/demo-repo'
        (doc_dir / '.claude-plugin').mkdir(parents=True)
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body')
        vault = repo / 'vault'
        vault.mkdir()
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body',
                         env={**self.env, 'WORK_LOG_ROOT': str(vault)})
        self.assertTrue(result['warnings'])

    @POSIX_ONLY
    def test_default_doc_dir_symlink_outside_doc_root_is_rejected(self):
        repo = self.repo()
        docs = self.base / 'work-log/docs'
        docs.mkdir(parents=True)
        outside = self.tmp / 'outside'
        outside.mkdir()
        (docs / 'demo-repo').symlink_to(outside, target_is_directory=True)
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body')
        self.fails('resolve', '--cwd', str(repo), '--ensure')
        self.assertEqual([], list(outside.iterdir()))

    @POSIX_ONLY
    def test_default_doc_dir_loose_mode_warns_and_new_dirs_are_private(self):
        repo = self.repo()
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'a.md', body='body')
        for path in (self.base, Path(result['path']).parent):
            self.assertEqual(0o700, path.stat().st_mode & 0o777)
        Path(result['path']).parent.chmod(0o777)
        result = self.ok('save-doc', '--cwd', str(repo), '--name', 'b.md', body='body')
        self.assertTrue(result['warnings'])

    def test_prefer_allows_repository_docs_but_rejects_plugin_source(self):
        repo = self.repo()
        (repo / 'docs').mkdir()
        self.ok('save-doc', '--cwd', str(repo), '--name', 'a.md', '--prefer', str(repo / 'docs'), body='body')
        plugin = repo / 'plugin'
        (plugin / '.claude-plugin').mkdir(parents=True)
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', '--prefer', str(plugin), body='body')

    @POSIX_ONLY
    def test_prefer_symlink_is_rejected(self):
        repo = self.repo()
        real = self.tmp / 'real-docs'
        real.mkdir()
        (repo / 'linked').symlink_to(real, target_is_directory=True)
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', '--prefer', str(repo / 'linked'), body='body')
        self.fails('save-doc', '--cwd', str(repo), '--name', 'a.md', '--prefer', str(repo / 'linked' / 'a.md'), body='body')

    def test_report_dir_rejects_plugin_source_and_warns_inside_working_tree(self):
        repo = self.repo()
        plugin = self.tmp / 'plugin-src'
        (plugin / 'mcp').mkdir(parents=True)
        (plugin / 'mcp' / 'server.js').write_text('')
        self.profile(repo, '---\nreportDir: "%s"\n---\n' % plugin.as_posix())
        self.fails('report-dir', '--cwd', str(repo), '--domain', 'be')
        self.profile(repo, '---\nreportDir: ".claude/harness-reports"\n---\n')
        result = self.ok('report-dir', '--cwd', str(repo), '--domain', 'be')
        self.assertTrue(same(result['reportDir'], repo / '.claude/harness-reports'))
        self.assertEqual('profile', result['source'])
        self.assertTrue(result['warnings'])

    @POSIX_ONLY
    def test_report_dir_symlink_and_loose_mode(self):
        repo = self.repo()
        real = self.tmp / 'real-reports'
        real.mkdir()
        link = self.tmp / 'reports-link'
        link.symlink_to(real, target_is_directory=True)
        self.profile(repo, '---\nreportDir: "%s"\n---\n' % link)
        self.fails('report-dir', '--cwd', str(repo), '--domain', 'be')
        loose = self.tmp / 'loose'
        loose.mkdir(mode=0o777)
        loose.chmod(0o777)
        self.profile(repo, '---\nreportDir: "%s"\n---\n' % loose)
        self.assertTrue(self.ok('report-dir', '--cwd', str(repo), '--domain', 'be')['warnings'])

    def test_default_report_and_run_dir_locations(self):
        repo = self.repo()
        result = self.ok('report-dir', '--cwd', str(repo), '--domain', 'be')
        docs = self.base / 'work-log/docs'
        self.assertEqual('default', result['source'])
        self.assertTrue(same(result['reportDir'], docs / 'demo-repo'))
        self.assertTrue(inside(result['runDir'], docs / '.harness-runs' / 'demo-repo'))
        self.assertTrue(Path(result['runDir']).is_dir())

    def test_run_dir_inside_working_tree_falls_back_to_system_temp(self):
        repo = self.repo()
        vault = repo / 'vault'
        vault.mkdir()
        result = self.ok('report-dir', '--cwd', str(repo), '--domain', 'be', env={**self.env, 'WORK_LOG_ROOT': str(vault)})
        self.assertFalse(inside(result['runDir'], repo))
        self.assertTrue(inside(result['runDir'], self.tmp / 'systemp'))
        self.assertTrue(result['warnings'])

    def test_run_dir_parent_plugin_source_is_rejected(self):
        repo = self.repo()
        runs = self.base / 'work-log/docs/.harness-runs/demo-repo'
        (runs / '.codex-plugin').mkdir(parents=True)
        self.fails('report-dir', '--cwd', str(repo), '--domain', 'be')

    @POSIX_ONLY
    def test_run_dir_symlink_is_rejected_and_loose_mode_warns(self):
        repo = self.repo()
        docs = self.base / 'work-log/docs'
        docs.mkdir(parents=True)
        outside = self.tmp / 'outside-runs'
        outside.mkdir()
        (docs / '.harness-runs').symlink_to(outside, target_is_directory=True)
        self.fails('report-dir', '--cwd', str(repo), '--domain', 'be')
        (docs / '.harness-runs').unlink()
        (docs / '.harness-runs' / 'demo-repo').mkdir(parents=True)
        (docs / '.harness-runs' / 'demo-repo').chmod(0o777)
        self.assertTrue(self.ok('report-dir', '--cwd', str(repo), '--domain', 'be')['warnings'])


REPORT_DIR_CASES = [
    ('missing key', '---\npreset: go\n---\n', ''),
    ('empty with comment', '---\nreportDir: ""   # 주석\n---\n', ''),
    ('windows escape', '---\nreportDir: "C:\\\\work"\n---\n', 'C:\\work'),
    ('single quote escape', "---\nreportDir: 'it''s'\n---\n", "it's"),
    ('nested child key', '---\ncodexModels:\n  reportDir: x\n---\n', ''),
    ('commented key', '---\n# reportDir: x\n---\n', ''),
    ('body key', '---\npreset: go\n---\nreportDir: x\n', ''),
    ('crlf', '---\r\nreportDir: out\r\n---\r\n', 'out'),
    ('relative', '---\nreportDir: reports/run\n---\n', 'reports/run'),
    ('no value', '---\nreportDir:\n---\n', ValueError),
    ('null', '---\nreportDir: null\n---\n', ValueError),
    ('tilde', '---\nreportDir: ~\n---\n', ValueError),
    ('number', '---\nreportDir: 12\n---\n', ValueError),
    ('duplicate', '---\nreportDir: a\nreportDir: b\n---\n', ValueError),
    ('child line', '---\nreportDir: a\n  extra: b\n---\n', ValueError),
    ('bom', '\ufeff---\nreportDir: a\n---\n', ValueError),
    ('control char', '---\nreportDir: "a\\x01"\n---\n', ValueError),
]


class ProfileReportDirTests(StoreCase):
    def write_case(self, text, name):
        cwd = self.tmp / ('case-' + name.replace(' ', '-'))
        cwd.mkdir()
        self.profile(cwd, text.encode('utf-8'))
        return cwd

    def test_parser_table(self):
        empty = self.tmp / 'no-profile'
        empty.mkdir()
        self.assertEqual('', store.profile_report_dir(empty, 'be'))
        for name, text, expected in REPORT_DIR_CASES:
            with self.subTest(name):
                cwd = self.write_case(text, name)
                if expected is ValueError:
                    with self.assertRaises(store.ConfigError) as caught:
                        store.profile_report_dir(cwd, 'be')
                    self.assertIn('be-harness.local.md', str(caught.exception))
                    self.assertIn('reportDir', str(caught.exception))
                else:
                    self.assertEqual(expected, store.profile_report_dir(cwd, 'be'))

    def test_parser_matches_profile_resolve(self):
        profile = load_profile_module()
        for name, text, _ in REPORT_DIR_CASES:
            with self.subTest(name):
                cwd = self.write_case(text, name)
                try:
                    expected = ('ok', profile.resolve(cwd, 'be')['values'].get('reportDir', ''))
                except profile.ProfileError:
                    expected = ('error', None)
                try:
                    actual = ('ok', store.profile_report_dir(cwd, 'be'))
                except store.ConfigError:
                    actual = ('error', None)
                self.assertEqual(expected, actual)

    def test_profile_directory_is_error(self):
        cwd = self.tmp / 'dir-profile'
        (cwd / '.claude' / 'be-harness.local.md').mkdir(parents=True)
        with self.assertRaises(store.ConfigError):
            store.profile_report_dir(cwd, 'be')

    @POSIX_ONLY
    def test_dangling_profile_symlink_is_error(self):
        cwd = self.tmp / 'dangling'
        (cwd / '.claude').mkdir(parents=True)
        (cwd / '.claude' / 'be-harness.local.md').symlink_to(cwd / 'missing.md')
        with self.assertRaises(store.ConfigError):
            store.profile_report_dir(cwd, 'be')


if __name__ == '__main__':
    unittest.main()
