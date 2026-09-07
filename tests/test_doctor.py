import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'be-harness/skills/config/assets/doctor.py'
spec = importlib.util.spec_from_file_location('harness_doctor', SCRIPT)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def project(self, root, legacy=False):
        values = dict(framework='nuxt', testRunner='jest', e2eRunner='cypress', typescript=False, storybook=False)
        (root / 'package.json').write_text('{}')
        if legacy:
            (root / '.hyeondong-config.json').write_text(json.dumps(values))
        else:
            (root / '.claude').mkdir()
            text = '---\n' + '\n'.join(key + ': ' + json.dumps(value) for key, value in values.items()) + '\ncodexMode: none\n---\n'
            (root / '.claude/fe-harness.local.md').write_text(text)
        for package in ('nuxt', 'vue', 'jest', 'cypress'):
            path = root / 'node_modules' / package / 'package.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
        for name in ('jest', 'cypress'):
            path = root / 'node_modules/.bin' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#!/bin/sh\nexit 7\n')
            path.chmod(0o700)

    def test_modern_js_cypress_none_checks_only_selected_features(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root)
            result = doctor.diagnose(root, 'fe', 'claude')
            rows = {c['key']: c for c in result['checks']}
            self.assertEqual('OK', rows['profile']['status'])
            self.assertEqual('SKIP', rows['typescript']['status'])
            self.assertEqual('SKIP', rows['codex']['status'])
            self.assertEqual('OK', rows['package:cypress']['status'])
            self.assertFalse(any('playwright' in k or 'vitest' in k or k == 'tsconfig' for k in rows))
            self.assertEqual('none', result['downloads'])
            self.assertFalse(result['validation_executed'])
            self.assertFalse(any(c['status'] == 'MISSING' for c in result['checks']))

    def test_legacy_stays_read_only_and_actual_tool_names_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root, legacy=True)
            path = root / '.hyeondong-config.json'
            before = path.read_bytes()
            result = doctor.diagnose(root, 'fe', 'claude', [{'name': 'actual_session__delegate_v2', 'capability': 'codex-delegation'}])
            rows = {c['key']: c for c in result['checks']}
            self.assertEqual('LEGACY', rows['profile']['status'])
            self.assertEqual('DISCOVERED', rows['codex']['status'])
            self.assertEqual('actual_session__delegate_v2', rows['codex']['detail'])
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((root / '.claude/fe-harness.local.md').exists())

    def test_native_host_does_not_require_delegation_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root, legacy=True)
            result = doctor.diagnose(root, 'fe', 'codex')
            codex = next(c for c in result['checks'] if c['key'] == 'codex')
            self.assertEqual('NATIVE', codex['status'])

    def test_diagnosis_executes_no_project_command_or_package_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root)
            path = root / '.claude/fe-harness.local.md'
            text = path.read_text().replace('codexMode: none', 'codexMode: none\nlintCommand: "touch SHOULD_NOT_EXIST"\nbuildCommand: "pnpm run build"')
            path.write_text(text)
            real_run = doctor.subprocess.run
            executed = []
            def run(argv, **kwargs):
                executed.append(argv)
                self.assertEqual(['node', '--version'], argv)
                return real_run(argv, **kwargs)
            with patch.object(doctor.subprocess, 'run', side_effect=run):
                result = doctor.diagnose(root, 'fe', 'codex')
            self.assertFalse((root / 'SHOULD_NOT_EXIST').exists())
            self.assertEqual('none', result['downloads'])
            self.assertLessEqual(len(executed), 1)


if __name__ == '__main__':
    unittest.main()
