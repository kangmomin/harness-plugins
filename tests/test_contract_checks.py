import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_contracts
sys.path.pop(0)


class ContractChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='harness-contracts-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        for name in ['be-harness', 'fe-harness', 'common', 'minmos-harness', 'hyeondongs-harness', 'work-log', '.claude-plugin', '.github', 'docs', 'tests']:
            shutil.copytree(ROOT / name, cls.root / name, ignore=shutil.ignore_patterns('node_modules', '__pycache__'))
        if (ROOT / 'README.md').is_file():
            shutil.copyfile(ROOT / 'README.md', cls.root / 'README.md')

    def changed(self, relative, transform):
        path = self.root / relative
        original = path.read_bytes()
        try:
            path.write_text(transform(original.decode()))
            return check_contracts.check(self.root)
        finally:
            path.write_bytes(original)

    def test_repository_passes_with_historical_calls_and_explicit_examples(self):
        self.assertEqual([], check_contracts.check(self.root))

    def test_invalid_manifest_agent_field_and_parity_fail(self):
        changes = [
            ('work-log/.codex-plugin/plugin.json', lambda s: s.replace('"version": "0.3.0"', '"version": "0.0.0"'), 'version mismatch'),
            ('be-harness/agents/scope-reviewer.md', lambda s: s.replace('tools:', 'allowed-tools:', 1), 'unsupported'),
            ('common/skills/start-workflow/assets/workflow_policy.py', lambda s: s + '\n# divergence\n', 'parity mismatch'),
        ]
        for relative, transform, expected in changes:
            with self.subTest(relative=relative):
                self.assertTrue(any(expected in error for error in self.changed(relative, transform)))

    def test_active_file_reference_and_actual_internal_call_fail(self):
        for addition, expected in [('\n[missing](references/does-not-exist.md)\n', 'missing local link'),
                                   ('\nUse `assets/missing.py`.\n', 'missing skill-owned reference'),
                                   ('\nCall /be-harness:does-not-exist now.\n', 'missing internal skill call')]:
            errors = self.changed('be-harness/skills/start-workflow/SKILL.md', lambda s: s + addition)
            self.assertTrue(any(expected in error for error in errors))

    def test_phase_and_override_drift_fail(self):
        errors = self.changed('be-harness/skills/start-workflow/references/templates.md', lambda s: s.replace('| 12 | orchestrator', '| 99 | orchestrator'))
        self.assertTrue(any('phase assignment/canonical' in e for e in errors))
        errors = self.changed('common/OVERRIDES.md', lambda s: s.replace('**오버라이드가 우선**', '**기본값이 우선**'))
        self.assertTrue(any('conflict rule' in e for e in errors))

    def test_root_active_docs_codex_manifest_and_go_assets_are_checked(self):
        changes = [
            ('README.md', lambda s: s + '\n[broken](docs/missing.md)\n', 'missing local link'),
            ('docs/host-contract.md', lambda s: s + '\n/be-harness:missing-current-skill\n', 'missing internal skill call'),
            ('work-log/.codex-plugin/plugin.json', lambda s: s.replace('"./skills/"', '"./DOES-NOT-EXIST/"'), 'manifest path'),
            ('work-log/.codex-plugin/plugin.json', lambda s: s.replace('./mcp/server.js', './mcp/missing.js'), 'manifest path'),
            ('minmos-harness/skills/pagenation/SKILL.md', lambda s: s + '\n`assets/missing.go`\n', 'missing skill-owned reference'),
        ]
        for relative, transform, expected in changes:
            with self.subTest(relative=relative):
                self.assertTrue(any(expected in error for error in self.changed(relative, transform)))

    def test_migration_exclusion_keeps_current_replacement_column_active(self):
        relative = 'minmos-harness/README.md'
        def change_current(source):
            before, after = source.split('## 마이그레이션', 1)
            return before + '## 마이그레이션' + after.replace('/minmos-harness:start-workflow`', '/minmos-harness:missing-replacement`')
        self.assertTrue(any('missing-replacement' in e for e in self.changed(relative, change_current)))
