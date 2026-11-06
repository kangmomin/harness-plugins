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

    def test_commit_prompts_limit_paths_and_preserve_partial_staging(self):
        files = ('be-harness/agents/workflow-implementer.md',
                 'fe-harness/agents/workflow-implementer.md',
                 'minmos-harness/agents/workflow-doc-sync.md',
                 'be-harness/skills/start-workflow/references/agent-prompts.md',
                 'fe-harness/skills/start-workflow/references/agent-prompts.md',
                 'be-harness/skills/start-workflow/references/tdd.md',
                 'fe-harness/skills/start-workflow/references/tdd.md')
        for file in files:
            with self.subTest(file=file):
                text = (ROOT / file).read_text()
                self.assertIn('--literal-pathspecs commit --only -F "{MESSAGE_FILE}" -- {관련 파일 인자들}', text)
                self.assertIn('부분 스테이징을 전체 파일로 덮지', text)
                self.assertIn('별도 임시 index', text)
                self.assertIn('기존 index/working bytes', text)
                self.assertIn('작업 트리의 파일 전체', text)
                self.assertIn('같은 파일의 무관한 hunk', text)
                self.assertIn('새 커밋의 경로/트리', text)
                self.assertNotIn('git commit -m', text)
        for domain in ('be', 'fe'):
            meta = agent_contract.validate(ROOT / f'{domain}-harness/agents/workflow-implementer.md')
            self.assertNotIn('Skill', meta['tools'])

    def test_fe_commit_metadata_uses_profile_and_keeps_workflow_unit(self):
        text = (ROOT / 'fe-harness/agents/workflow-implementer.md').read_text()
        profile = (ROOT / 'fe-harness/PROFILE.md').read_text()
        self.assertIn('profile의 `commitPrefixes`를 사용', text)
        self.assertIn('[Add, Fix, Del, Refactor, Doc, Test, Chore, WIP]', text)
        self.assertIn('commitPrefixes: [Add, Fix, Del, Refactor, Doc, Test, Chore, WIP]', profile)
        self.assertIn('Co-Authored-By: {commitCoAuthor}', text)
        self.assertIn('빈 값이면 이 trailer를 넣지 않는다', text)
        self.assertNotIn('noreply@anthropic.com', text)
        self.assertIn('Workflow-Unit: {RUN_ID}/{단위 ID}', text)

    def test_streaming_skip_is_harness_scope_not_grpcurl_capability(self):
        text = (ROOT / 'minmos-harness/overlay/references/e2e-test-postmath.md').read_text()
        self.assertIn('`SKIP:STREAMING`', text)
        self.assertIn('하네스 기본 시나리오에서 미실행 (grpcurl 자체는 지원)', text)
        self.assertNotIn('grpcurl 미지원', text)

    def test_changed_plugin_versions_match_readme_and_marketplace_paths(self):
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        entries = {entry['name']: entry for entry in marketplace['plugins']}
        readme = (ROOT / 'README.md').read_text()
        for name, label in (('be-harness', 'BE'), ('fe-harness', 'FE'), ('minmos-harness', 'minmos')):
            with self.subTest(name=name):
                manifest = json.loads((ROOT / name / '.claude-plugin/plugin.json').read_text())
                self.assertEqual(f'./{name}', entries[name]['source'])
                if 'version' in entries[name]:
                    self.assertEqual(manifest['version'], entries[name]['version'])
                self.assertIn(f"{label} {manifest['version']}", readme)

    def test_parallel_review_prompts_return_and_parent_records(self):
        text = (ROOT / 'fe-harness/skills/start-workflow/references/agent-prompts.md').read_text()
        for kind in ('component', 'a11y'):
            self.assertNotIn(f'Phase 8 {kind} review 상태를 갱신하세요', text)
            self.assertIn(f'Phase 8 {kind} review 결과를 반환하세요', text)
        self.assertIn('오케스트레이터가 두 리뷰 결과를 수집', text)
