import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('agent_contract', ROOT / 'scripts/agent_contract.py')
agent_contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_contract)


class AgentContractTests(unittest.TestCase):
    def test_all_plugin_agents_and_recorded_actual_loader_tools(self):
        evidence = json.loads((ROOT / 'tests/fixtures/host-contract/observed.json').read_text())
        actual = {entry['agent']: entry for entry in evidence['agents']}
        paths = list(ROOT.glob('*/agents/*.md'))
        self.assertEqual(len(paths), len(actual))
        for path in paths:
            with self.subTest(path=path):
                meta = agent_contract.validate(path)
                observed = actual[f'{path.parents[1].name}:{path.stem}']
                self.assertTrue(observed['delegation_verified'])
                self.assertLessEqual(set(observed['tools']), set(meta['tools']))
                if path.stem in agent_contract.READERS:
                    self.assertEqual({'Read', 'Glob', 'Grep'}, set(observed['tools']))
                if path.stem == 'workflow-pr':
                    self.assertIn('Skill', observed['tools'])
        self.assertLessEqual({'Bash', 'Edit', 'Write'}, set(evidence['negative_control']['tools']))

    def test_rejects_skill_field_missing_or_duplicate_tools_and_reader_shell(self):
        base = '---\nname: scope-reviewer\ndescription: Example\ntools: Read, Glob, Grep\n---\nRead only.\n'
        mutations = [base.replace('tools:', 'allowed-tools:'),
                     base.replace('tools: Read, Glob, Grep\n', ''),
                     base.replace('tools: Read, Glob, Grep', 'tools: Read, Glob, Grep, Bash'),
                     base.replace('tools: Read, Glob, Grep', 'tools: Read, Read'),
                     base.replace('tools: Read, Glob, Grep', 'tools: Read\ntools: Read, Glob, Grep'),
                     base.replace('tools: Read, Glob, Grep', 'tools: Read, Glob, Grep\npermissionMode: bypassPermissions')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scope-reviewer.md'
            for source in mutations:
                path.write_text(source)
                with self.assertRaises(ValueError):
                    agent_contract.validate(path)

    def test_parallel_review_prompts_return_and_parent_records(self):
        text = (ROOT / 'fe-harness/skills/start-workflow/references/agent-prompts.md').read_text()
        for kind in ('component', 'a11y'):
            self.assertNotIn(f'Phase 8 {kind} review 상태를 갱신하세요', text)
            self.assertIn(f'Phase 8 {kind} review 결과를 반환하세요', text)
        self.assertIn('오케스트레이터가 두 리뷰 결과를 수집', text)
