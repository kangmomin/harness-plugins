import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'be-harness/skills/convention-check/assets/convention_facts.py'
SCOPE = ROOT / 'be-harness/skills/start-workflow/assets/workflow_scope.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


facts = load('convention_facts', SCRIPT)
scope = load('workflow_scope', SCOPE)


class ConventionFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='facts repo # ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'trunk')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.write('go.mod', 'module example.com/app\n\ngo 1.22\n\nrequire (\n'
                             '\tgithub.com/old/dep v1.0.0\n\tgithub.com/was/indirect v1.0.0 // indirect\n)\n')
        self.write('package.json', json.dumps({'dependencies': {'react': '18.0.0'},
                                               'devDependencies': {'vitest': '1.0.0'}}, indent=2) + '\n')
        self.write('src/repo.go', 'package app\n')
        self.write('src/components/Old.tsx', 'export const Old = () => null\n')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.start = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True)

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode('utf-8'))

    def collect(self, owned=()):
        return scope.scope(self.root, self.start, list(owned))

    def run_facts(self, checks, pattern=None, owned=()):
        return facts.run(self.collect(owned), checks, pattern)

    def tags(self, result, tag):
        return [f for f in result['findings'] if f['tag'] == tag]

    def test_go_mod_new_direct_and_promoted_dependencies(self):
        self.write('go.mod', 'module example.com/app\n\ngo 1.22\n\nrequire (\n'
                             '\tgithub.com/old/dep v1.0.0\n\tgithub.com/was/indirect v1.0.0\n'
                             '\tgithub.com/new/indirect v1.0.0 // indirect\n)\n\nrequire github.com/new/direct v2.0.0\n')
        found = self.tags(self.run_facts(['new-dependency']), 'NEW_DEPENDENCY')
        details = sorted(f['detail'] for f in found)
        self.assertEqual(2, len(found), details)
        self.assertIn('github.com/new/direct', details[0])
        self.assertIn('승격', details[1])
        self.assertTrue(all(f['path'] == 'go.mod' and f['line'] for f in found))

    def test_package_json_new_key_but_not_section_move(self):
        self.write('package.json', json.dumps({'dependencies': {'react': '18.0.0', 'vitest': '1.0.0'},
                                               'devDependencies': {'lodash': '4.0.0'}}, indent=2) + '\n')
        found = self.tags(self.run_facts(['new-dependency']), 'NEW_DEPENDENCY')
        self.assertEqual(['lodash'], [f['detail'].split(' ')[0] for f in found])
        self.assertEqual(7, found[0]['line'])

    def test_untracked_package_manifest_and_unsupported_manifests(self):
        self.write('web/package.json', json.dumps({'dependencies': {'zod': '3.0.0'}}) + '\n')
        self.write('svc/requirements-dev.txt', 'pytest\n')
        self.write('node_modules/x/package.json', json.dumps({'dependencies': {'evil': '1'}}) + '\n')
        result = self.run_facts(['new-dependency'], owned=['web/package.json', 'svc/requirements-dev.txt',
                                                           'node_modules/x/package.json'])
        self.assertEqual(['web/package.json'], [f['path'] for f in self.tags(result, 'NEW_DEPENDENCY')])
        self.assertEqual([{'path': 'svc/requirements-dev.txt', 'reason': 'unsupported manifest'}], result['unchecked_manifests'])

    def test_broken_package_json_is_unchecked_not_passed(self):
        self.write('package.json', '{"dependencies": {')
        result = self.run_facts(['new-dependency'])
        self.assertEqual([], result['findings'])
        self.assertEqual('package.json', result['unchecked_manifests'][0]['path'])

    def test_sql_single_literal_in_is_flagged_but_slice_placeholder_is_not(self):
        self.write('src/repo.go', 'package app\n'
                                  'const a = "SELECT * FROM t WHERE id IN (?)"\n'
                                  'const b = "SELECT * FROM t WHERE status IN (\'ACTIVE\')"\n'
                                  'const c = "DELETE FROM t WHERE id NOT IN ($1)"\n'
                                  'const d = "SELECT * FROM t WHERE id IN (1, 2)"\n'
                                  '// stored in (1) place\n')
        self.write('docs/sql.md', "WHERE x IN ('a')\n")
        found = self.tags(self.run_facts(['sql-in-literal'], owned=['docs/sql.md']), 'SQL_PATTERN')
        self.assertEqual([('src/repo.go', 3), ('src/repo.go', 4)], [(f['path'], f['line']) for f in found])

    def test_sql_in_untracked_file_uses_whole_file(self):
        self.write('db/query.sql', "SELECT 1;\nSELECT * FROM t WHERE k IN (42);\n")
        found = self.tags(self.run_facts(['sql-in-literal'], owned=['db/query.sql']), 'SQL_PATTERN')
        self.assertEqual([('db/query.sql', 2)], [(f['path'], f['line']) for f in found])

    def test_component_path_rules_per_pattern(self):
        files = ['src/features/cart/components/CartItem.tsx', 'src/features/cart/CartBadge.tsx',
                 'src/components/atoms/Button.tsx', 'src/components/Card/index.tsx', 'src/widgets/Banner.vue',
                 'src/components/Modal.test.tsx', 'src/app/Page.tsx', 'src/hooks/useCart.ts', 'src/lib/format.tsx']
        for path in files:
            self.write(path, 'x\n')
        self.write('src/components/Old.tsx', 'export const Old = () => 1\n')
        def flagged(pattern):
            result = self.run_facts(['component-path'], pattern, owned=files)
            return sorted(f['path'] for f in self.tags(result, 'COMPONENT_PATH'))
        self.assertEqual(['src/features/cart/CartBadge.tsx', 'src/widgets/Banner.vue'], flagged('feature-based'))
        self.assertEqual(['src/components/Card/index.tsx', 'src/features/cart/CartBadge.tsx',
                          'src/features/cart/components/CartItem.tsx', 'src/widgets/Banner.vue'], flagged('atomic'))
        self.assertEqual(['src/features/cart/CartBadge.tsx', 'src/widgets/Banner.vue'], flagged('flat'))
        self.assertTrue(all(f['severity'] == 'WARN' for f in self.run_facts(['component-path'], 'flat', owned=files)['findings']))

    def test_component_path_without_pattern_is_reported_as_skipped(self):
        result = self.run_facts(['component-path'], None)
        self.assertEqual('component-path', result['skipped_checks'][0]['check'])

    def test_hooks_coverage_uses_nearest_declaring_package(self):
        self.write('src/components/New.tsx', 'x\n')
        self.assertFalse(self.run_facts(['hooks-coverage'], owned=['src/components/New.tsx'])['lint_coverage']['react_hooks'])
        self.write('package.json', json.dumps({'devDependencies': {'eslint-plugin-react-hooks': '5.0.0'}}) + '\n')
        result = self.run_facts(['hooks-coverage'], owned=['src/components/New.tsx'])
        self.assertTrue(result['lint_coverage']['react_hooks'])
        self.assertIsNone(self.run_facts(['new-dependency'])['lint_coverage']['react_hooks'])

    def test_cli_reads_patch_files_and_blocks_bad_input(self):
        self.write('src/repo.go', "package app\nconst q = \"WHERE a IN ('x')\"\n")
        with tempfile.TemporaryDirectory(prefix='facts evidence ') as outside:
            run_dir = Path(outside) / 'scope-1'
            out = run_dir / 'scope.json'
            owned = Path(outside) / 'owned.json'
            owned.write_text('[]')
            subprocess.run([sys.executable, '-I', '-B', str(SCOPE), '--cwd', str(self.root), '--start-sha', self.start,
                            '--owned-files', str(owned), '--out', str(out), '--patch-dir', str(run_dir)], check=True)
            ok = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--scope', str(out), '--checks', 'sql-in-literal'],
                                capture_output=True)
            self.assertEqual(0, ok.returncode, ok.stderr.decode('utf-8', 'replace'))
            self.assertEqual(['SQL_PATTERN'], [f['tag'] for f in json.loads(ok.stdout.decode('utf-8'))['findings']])
            data = json.loads(out.read_text())
            Path(data['patch_file']).write_bytes(b'tampered')
            tampered = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--scope', str(out), '--checks', 'sql-in-literal'],
                                      capture_output=True)
            self.assertEqual(2, tampered.returncode)
            self.assertIn('BLOCKED:CONVENTION_FACTS', tampered.stderr.decode('utf-8'))
        for args, stdin in ((['--scope', '-', '--checks', 'nope'], b'{}'), (['--scope', '-', '--checks', 'new-dependency'], b'[]')):
            bad = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), *args], input=stdin, capture_output=True)
            self.assertEqual(2, bad.returncode)

    def test_be_and_fe_copies_are_identical(self):
        fe = ROOT / 'fe-harness/skills/convention-check/assets/convention_facts.py'
        self.assertEqual(SCRIPT.read_bytes(), fe.read_bytes())


if __name__ == '__main__':
    unittest.main()
