import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'be-harness/skills/e2e-test/assets/e2e_functions.py'
POSIX_ONLY = unittest.skipIf(os.name == 'nt', 'POSIX 권한·symlink 전용 — CI에서 확인')
ECHO = 'import json, sys\nprint(json.dumps(sys.argv[1:]))\n'


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


class FunctionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='e2e-functions-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = isolated_env(self.tmp)
        self.functions = self.tmp / 'functions'
        self.repo = self.tmp / 'repos' / 'demo-repo'
        self.repo.mkdir(parents=True)
        git(self.repo, 'init', '-q', env=self.env)

    def run_fn(self, *args, cwd=None, env=None, timeout=60):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), *args], cwd=cwd or self.tmp, env=env or self.env,
                              capture_output=True, text=True, encoding='utf-8', timeout=timeout)

    def ok(self, *args, **kwargs):
        result = self.run_fn(*args, **kwargs)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def fails(self, *args, **kwargs):
        result = self.run_fn(*args, **kwargs)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def listing(self, harness='be', cwd=None, env=None):
        return self.ok('list', '--cwd', str(cwd or self.repo), '--harness', harness, env=env)

    def manifest(self, folder, scripts, raw=None, files=True):
        folder = self.functions / folder
        folder.mkdir(parents=True, exist_ok=True)
        for entry in scripts:
            if files and isinstance(entry.get('path'), str) and '/' not in entry['path'] and '\\' not in entry['path']:
                (folder / entry['path']).write_text(ECHO)
        text = raw if raw is not None else json.dumps({'version': 1, 'scripts': scripts})
        (folder / 'manifest.json').write_text(text, encoding='utf-8')
        return folder

    @staticmethod
    def entry(name, harness=('be',), path=None, **extra):
        return {'name': name, 'path': path or name + '.py', 'description': name + ' desc',
                'harness': list(harness), 'usage': name + '.py <arg>', **extra}

    def names(self, result):
        return sorted(item['name'] for item in result['scripts'])


class ListTests(FunctionCase):
    def test_lists_only_requested_harness_with_absolute_paths(self):
        self.manifest('_shared', [self.entry('shared-be'), self.entry('shared-fe', ('fe',)), self.entry('both', ('be', 'fe'))])
        self.manifest('demo-repo', [self.entry('project-be')])
        result = self.listing('be')
        self.assertEqual(['both', 'project-be', 'shared-be'], self.names(result))
        for item in result['scripts']:
            self.assertTrue(Path(item['path']).is_absolute())
            self.assertTrue(Path(item['path']).is_file())
        sources = {item['name']: item['source'] for item in result['scripts']}
        self.assertNotEqual(sources['shared-be'], sources['project-be'])

    def test_missing_root_or_manifest_is_empty_without_warning(self):
        shutil.rmtree(self.functions)
        self.assertEqual({'scripts': [], 'warnings': []}, self.listing())
        self.functions.mkdir()
        (self.functions / '_shared').mkdir()
        self.assertEqual({'scripts': [], 'warnings': []}, self.listing())

    def test_broken_manifest_or_entry_is_skipped_with_warning(self):
        good = self.entry('good')
        cases = [
            ('broken json', '{not json'),
            ('version mismatch', json.dumps({'version': 2, 'scripts': [self.entry('v2')]})),
            ('missing field', json.dumps({'version': 1, 'scripts': [{'name': 'nopath', 'harness': ['be']}]})),
            ('long description', json.dumps({'version': 1, 'scripts': [self.entry('long', description='x' * 201)]})),
            ('bad name', json.dumps({'version': 1, 'scripts': [self.entry('Bad Name')]})),
        ]
        self.manifest('_shared', [good])
        for label, raw in cases:
            with self.subTest(label):
                self.manifest('demo-repo', [], raw=raw)
                result = self.listing()
                self.assertEqual(['good'], self.names(result))
                self.assertTrue(result['warnings'])

    def test_utf8_bom_manifest_is_read(self):
        folder = self.manifest('_shared', [self.entry('bom')])
        data = (folder / 'manifest.json').read_bytes()
        (folder / 'manifest.json').write_bytes(b'\xef\xbb\xbf' + data)
        self.assertEqual(['bom'], self.names(self.listing()))

    def test_path_outside_folder_is_rejected(self):
        outside = self.tmp / 'outside.py'
        outside.write_text(ECHO)
        (self.functions / 'evil').mkdir()
        (self.functions / 'evil' / 'x.py').write_text(ECHO)
        for path in ('../outside.py', str(outside), '../evil/x.py', 'sub/x.py'):
            with self.subTest(path=path):
                self.manifest('_shared', [self.entry('escape', path=path)], files=False)
                result = self.listing()
                self.assertEqual([], result['scripts'])
                self.assertTrue(result['warnings'])

    @POSIX_ONLY
    def test_symlink_script_is_rejected(self):
        outside = self.tmp / 'outside.py'
        outside.write_text(ECHO)
        folder = self.manifest('_shared', [self.entry('linked')], files=False)
        (folder / 'linked.py').symlink_to(outside)
        result = self.listing()
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])

    def test_same_name_in_shared_and_project_excludes_both(self):
        self.manifest('_shared', [self.entry('dup'), self.entry('keep')])
        self.manifest('demo-repo', [self.entry('dup')])
        result = self.listing()
        self.assertEqual(['keep'], self.names(result))
        self.assertTrue(any('dup' in w for w in result['warnings']))

    def test_unknown_harness_value_is_rejected(self):
        self.manifest('_shared', [self.entry('qa-only', ('qa',)), self.entry('mixed', ('be', 'qa')), self.entry('ok')])
        result = self.listing()
        self.assertEqual(['ok'], self.names(result))
        self.assertTrue(result['warnings'])

    def test_cmd_and_bat_scripts_are_rejected(self):
        self.manifest('_shared', [self.entry('win-cmd', path='win-cmd.cmd'), self.entry('win-bat', path='win-bat.bat')])
        result = self.listing()
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])
        self.fails('run', '--cwd', str(self.repo), '--harness', 'be', '--name', 'win-cmd')

    def test_function_folder_trust_checks(self):
        self.manifest('_shared', [self.entry('plugin')])
        (self.functions / '_shared' / '.claude-plugin').mkdir()
        result = self.listing()
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])
        inner = self.repo / 'functions'
        (inner / '_shared').mkdir(parents=True)
        (inner / '_shared' / 'inner.py').write_text(ECHO)
        (inner / '_shared' / 'manifest.json').write_text(json.dumps({'version': 1, 'scripts': [self.entry('inner')]}))
        result = self.listing(env={**self.env, 'HARNESS_FUNCTION_DIR': str(inner)})
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])

    @POSIX_ONLY
    def test_function_folder_owner_mode_and_symlink_checks(self):
        folder = self.manifest('_shared', [self.entry('loose')])
        folder.chmod(0o777)
        result = self.listing()
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])
        folder.chmod(0o700)
        (folder / 'manifest.json').rename(self.tmp / 'real-manifest.json')
        (folder / 'manifest.json').symlink_to(self.tmp / 'real-manifest.json')
        result = self.listing()
        self.assertEqual([], result['scripts'])
        self.assertTrue(result['warnings'])

    def test_worktrees_share_project_folder(self):
        git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'init', env=self.env)
        worktree = self.tmp / 'other-worktree-name'
        git(self.repo, 'worktree', 'add', '-q', '--detach', str(worktree), env=self.env)
        self.manifest('demo-repo', [self.entry('project-only')])
        self.assertEqual(['project-only'], self.names(self.listing(cwd=worktree)))

    def test_non_git_directory_lists_shared_and_folder_project(self):
        plain = self.tmp / 'plain-folder'
        plain.mkdir()
        self.manifest('_shared', [self.entry('shared')])
        self.manifest('plain-folder', [self.entry('local')])
        self.assertEqual(['local', 'shared'], self.names(self.listing(cwd=plain)))


class RunTests(FunctionCase):
    def test_run_passes_args_without_executing_usage(self):
        marker = self.tmp / 'PWNED'
        usage = 'echo.py a && python -c "open(%r, \'w\')"' % str(marker)
        self.manifest('_shared', [self.entry('echo', usage=usage)])
        result = self.ok('run', '--cwd', str(self.repo), '--harness', 'be', '--name', 'echo', '--', 'one', 'two words')
        self.assertEqual(0, result['exitCode'])
        self.assertEqual(['one', 'two words'], json.loads(result['stdout']))
        self.assertIs(False, result['timedOut'])
        self.assertFalse(marker.exists())

    def test_timeout_kills_grandchild_holding_pipe(self):
        script = ('import subprocess, sys, time\n'
                  'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
                  'print("started", flush=True)\n'
                  'time.sleep(60)\n')
        folder = self.manifest('_shared', [self.entry('hang')], files=False)
        (folder / 'hang.py').write_text(script)
        started = time.monotonic()
        result = self.ok('run', '--cwd', str(self.repo), '--harness', 'be', '--name', 'hang', '--timeout', '2', timeout=45)
        self.assertLess(time.monotonic() - started, 30)
        self.assertIs(True, result['timedOut'])


class AddTests(FunctionCase):
    def source(self, name='helper.py', body=ECHO):
        path = self.tmp / 'src' / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(body)
        return path

    def add(self, name, src, harness='be', cwd=None):
        return ['add', '--cwd', str(cwd or self.repo), '--src', str(src), '--name', name,
                '--description', name + ' desc', '--harness', harness, '--usage', name + ' <arg>']

    def test_add_creates_project_folder_manifest_and_copy(self):
        src = self.source()
        self.ok(*self.add('helper', src, 'be,fe'))
        folder = self.functions / 'demo-repo'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(1, manifest['version'])
        self.assertEqual([{'name': 'helper', 'path': 'helper.py', 'description': 'helper desc',
                           'harness': ['be', 'fe'], 'usage': 'helper <arg>'}], manifest['scripts'])
        self.assertEqual(ECHO, (folder / 'helper.py').read_text())
        self.assertEqual(['helper'], self.names(self.listing('fe')))

    def test_add_same_name_or_file_does_not_overwrite(self):
        self.ok(*self.add('helper', self.source()))
        folder = self.functions / 'demo-repo'
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        self.fails(*self.add('helper', self.source('other.py', 'print(1)\n')))
        self.fails(*self.add('renamed', self.source('helper.py', 'print(2)\n')))
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_add_rejects_disallowed_source(self):
        for name in ('tool.cmd', 'tool.bat', 'tool.exe'):
            with self.subTest(name):
                self.fails(*self.add('tool', self.source(name, 'echo hi\n')))
        self.assertFalse((self.functions / 'demo-repo' / 'manifest.json').exists())

    def test_add_in_non_git_directory_uses_folder_name(self):
        plain = self.tmp / 'plain-folder'
        plain.mkdir()
        self.ok(*self.add('helper', self.source(), cwd=plain))
        self.assertTrue((self.functions / 'plain-folder' / 'helper.py').is_file())

    def test_concurrent_add_keeps_both_entries(self):
        procs = [subprocess.Popen([sys.executable, '-B', str(SCRIPT), *self.add(name, self.source(name + '.py'))],
                                  env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for name in ('first', 'second')]
        outputs = [p.communicate(timeout=60) for p in procs]
        self.assertEqual([0, 0], [p.returncode for p in procs], outputs)
        manifest = json.loads((self.functions / 'demo-repo' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(['first', 'second'], sorted(item['name'] for item in manifest['scripts']))


if __name__ == '__main__':
    unittest.main()
