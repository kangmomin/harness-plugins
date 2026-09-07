import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'fe-harness/skills/component/assets/component_templates.py'
spec = importlib.util.spec_from_file_location('component_templates', SCRIPT)
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)


class ComponentTemplateTests(unittest.TestCase):
    def test_unsupported_combination_produces_no_files_or_partial_json(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--name', 'Example', '--framework', 'nuxt', '--typescript', 'false', '--runner', 'jest'], cwd=directory, capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertEqual('', result.stdout)
            self.assertEqual('BLOCKED', json.loads(result.stderr)['status'])
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_javascript_vue_has_vue_artifacts_and_explicit_runner_apis(self):
        data = component.templates('Example', 'nuxt', False, 'vitest', True)
        self.assertEqual({'Example.vue', 'Example.test.js', 'Example.stories.js', 'index.js'}, set(data['files']))
        source = '\n'.join(data['files'].values())
        self.assertNotIn('@testing-library/react', source)
        self.assertNotIn('import type', source)
        self.assertNotIn('lang="ts"', source)
        self.assertIn("from 'vitest'", source)

    def test_ui_and_identifier_validation_precedes_generation(self):
        for name, framework, ui in (('React', 'vite', 'tailwind'), ('../Escape', 'vite', 'tailwind'), ('Example', 'nuxt', 'mui'), ('Example', 'unknown', 'tailwind')):
            with self.assertRaises(ValueError):
                component.templates(name, framework, True, 'vitest', ui=ui)


if __name__ == '__main__':
    unittest.main()
