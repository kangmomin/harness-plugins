import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('skill_catalog', ROOT / 'common/skills/how-to-use/assets/skill_catalog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.skills = [
            {'name': 'codex-be-harness:start-workflow', 'description': 'BE workflow.',
             'invocation': '$codex-be-harness:start-workflow', 'roles': ['be'], 'roles_source': 'session:plugin-role'},
            {'name': 'new-team:build', 'description': 'New harness task.', 'invocation': '/new-team:build'},
            {'name': 'brand-new:start-workflow', 'description': 'New workflow.', 'invocation': '/brand-new:start-workflow'},
        ]

    def test_renamed_new_plugins_and_duplicate_basenames_keep_actual_calls(self):
        result = module.catalog({'skills': self.skills})
        self.assertEqual([s['name'] for s in self.skills], [s['name'] for s in result['skills']])
        result = module.catalog({'skills': self.skills, 'skill': 'start-workflow'})
        self.assertEqual(2, len(result['entrypoints']))
        self.assertEqual('$codex-be-harness:start-workflow', result['skills'][0]['invocation'])
        self.assertNotIn('common:start-workflow', str(result))

    def test_role_filter_needs_evidence_and_missing_invocation_is_not_invented(self):
        result = module.catalog({'skills': self.skills, 'filter': '--be'})
        self.assertEqual(['codex-be-harness:start-workflow'], result['entrypoints'])
        self.assertEqual('NO_MATCH', module.catalog({'skills': self.skills, 'filter': '--be', 'skill': 'missing'})['status'])
        self.assertEqual('UNVERIFIED_FILTER', module.catalog({'skills': self.skills, 'filter': '--fe'})['status'])
        self.skills[0].pop('roles_source')
        with self.assertRaises(ValueError):
            module.catalog({'skills': self.skills})
        result = module.catalog({'skills': [{'name': 'unscoped', 'description': 'Description'}]})
        self.assertIsNone(result['skills'][0]['invocation'])

    def test_missing_catalog_and_duplicate_full_identifier(self):
        with self.assertRaises(ValueError):
            module.catalog({})
        with self.assertRaises(ValueError):
            module.catalog({'skills': self.skills + [self.skills[0]]})
        self.assertEqual('NO_MATCH', module.catalog({'skills': []})['status'])
