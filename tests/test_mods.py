import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOD_PLUGINS = ['common', 'be-harness', 'fe-harness', 'minmos-harness', 'work-log', 'harness-settings']


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class ModTests(unittest.TestCase):
    def test_each_mod_plugin_names_an_existing_module_and_contract(self):
        for name in MOD_PLUGINS:
            with self.subTest(plugin=name):
                hooks = json.loads(read(f'{name}/hooks/hooks.json'))
                # command hook 은 mod 로 옮겼다. 모듈 형식만 남는다.
                self.assertEqual(set(hooks), {'modules'})
                for module in hooks['modules']:
                    self.assertTrue((ROOT / name / 'hooks' / module).is_file(), module)
                manifest = json.loads(read(f'{name}/.claude-plugin/plugin.json'))
                self.assertTrue((ROOT / name / manifest['types']).is_file())

    def test_be_and_fe_profile_mods_differ_only_in_domain_block(self):
        # 두 파일은 복사본이다. 도메인 블록·atom plugin 이름 외에 어긋나면 한쪽만 고친 것이다.
        def normalize(text):
            text = re.sub(r"// (be|fe)-harness/hooks/register\.tsx[^\n]*\n", '', text)
            text = re.sub(r"(?s)const PLUGIN = .*?// ---\n", '', text)
            return re.sub(r"'(be|fe)-harness'", "'X'", text)
        self.assertEqual(normalize(read('be-harness/hooks/register.tsx')), normalize(read('fe-harness/hooks/register.tsx')))
        self.assertEqual(read('be-harness/types/index.d.ts').replace('be-harness', 'X'), read('fe-harness/types/index.d.ts').replace('fe-harness', 'X'))

    def test_language_block_is_identical_in_common_and_work_log(self):
        # 같은 이름이어야 둘 다 설치돼도 한 번만 주입된다.
        pattern = re.compile(r"export const LANGUAGE_BLOCK = \{.*?\n\}", re.S)
        common = pattern.search(read('common/hooks/register.tsx'))
        work_log = pattern.search(read('work-log/hooks/register.tsx'))
        self.assertIsNotNone(common)
        self.assertEqual(common.group(0), work_log.group(0))


if __name__ == '__main__':
    unittest.main()
