import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'common' / 'hooks' / 'papercut.py'
FEEDBACK = ROOT / 'common' / 'skills' / 'submit-feedback' / 'assets' / 'feedback.py'
CUT = {
    'plugin': 'common', 'skill': 'commit', 'goal': '커밋 메시지 검사',
    'command': 'python3 assets/commit_check.py', 'expected': 'exit 0', 'actual': 'exit 2: 인자 없음',
    'workaround': '--cwd 를 붙였다', 'proposal': 'SKILL.md 예시에 --cwd 를 넣는다',
}


class PapercutHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / 'repo'
        self.store = base / 'store'
        self.repo.mkdir()
        subprocess.run(['git', '-C', str(self.repo), 'init', '-q', '-b', 'main'], check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, *args, stdin=None):
        env = {**os.environ, 'HARNESS_METRICS_DIR': str(self.store)}
        return subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), *args, '--cwd', str(self.repo)],
                              input=stdin, capture_output=True, text=True, encoding='utf-8', env=env)

    def ok(self, *args, stdin=None):
        out = self.run_helper(*args, stdin=stdin)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def record(self, **changes):
        return self.ok('record', stdin=json.dumps({**CUT, **changes}, ensure_ascii=False))

    def test_record_appends_once_and_skips_the_same_cut(self):
        first = self.record()
        self.assertEqual(first['status'], 'OK')
        self.assertEqual(self.record()['status'], 'DUPLICATE')
        lines = next(self.store.glob('*/papercuts.jsonl')).read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual((row['id'], row['skill'], row['actual']), (first['id'], 'commit', CUT['actual']))

    def test_record_rejects_missing_fields_and_path_like_names(self):
        for changes in ({'actual': ' '}, {'skill': '../x'}, {'goal': 3}):
            with self.subTest(changes=changes):
                out = self.run_helper('record', stdin=json.dumps({**CUT, **changes}))
                self.assertEqual(out.returncode, 2)
                self.assertIn('BAD_INPUT', out.stderr)
        self.assertEqual(list(self.store.glob('*/papercuts.jsonl')), [])

    def test_long_fields_are_cut(self):
        self.record(actual='x' * 5000)
        self.assertEqual(len(self.ok('list')['items'][0]['actual']), 2000)

    def test_list_counts_by_skill_and_filters_by_plugin(self):
        self.record()
        self.record(goal='다른 일')
        self.record(plugin='be-harness', skill='doctor')
        listed = self.ok('list')
        self.assertEqual((listed['total'], listed['by_skill']), (3, {'common:commit': 2, 'be-harness:doctor': 1}))
        self.assertEqual(self.ok('list', '--plugin', 'be-harness')['total'], 1)

    def test_export_matches_submit_feedback_input_after_generality_is_set(self):
        self.record()
        payload = self.ok('export', '--plugin', 'common')['payload']
        item = payload['items'][0]
        self.assertEqual((item['target_type'], item['target_name'], item['generality']), ('skill', 'commit', ''))
        self.assertIn('- 실제 결과: exit 2: 인자 없음', item['context'])
        item['generality'] = '범용'
        prepared = subprocess.run(
            [sys.executable, '-I', '-B', str(FEEDBACK), 'prepare', '-'], capture_output=True, text=True, encoding='utf-8',
            # feedback.py 는 stdin 을 기본 인코딩으로 읽는다. ASCII 로 넘겨 Windows 에서도 같게 한다.
            input=json.dumps({'payload': payload, 'artifact_root': str(Path(self.tmp.name) / 'artifacts')}))
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)

    def test_mark_removes_submitted_cuts_and_keeps_them_deduplicated(self):
        key = self.record()['id']
        self.assertEqual(self.ok('mark', '--ids', key + ',unknown')['marked'], [key])
        self.assertEqual(self.ok('list')['total'], 0)
        self.assertEqual(self.record()['status'], 'DUPLICATE')

    def test_bom_input_broken_bytes_and_a_cut_last_line_lose_no_record(self):
        # PowerShell 파이프는 stdin 앞에 BOM 을 붙인다.
        self.assertEqual(self.ok('record', stdin='﻿' + json.dumps(CUT))['status'], 'OK')
        records = next(self.store.glob('*/papercuts.jsonl'))
        with records.open('ab') as handle:
            handle.write(b'\xff broken\n{"id": "cut-off"')
        self.assertEqual(self.record(goal='잘린 줄 뒤의 기록')['status'], 'OK')
        self.assertEqual([row['goal'] for row in self.ok('list')['items']], [CUT['goal'], '잘린 줄 뒤의 기록'])

    def test_export_summaries_differ_when_only_the_actual_result_differs(self):
        self.record()
        self.record(actual='exit 3: 권한 없음')
        summaries = [item['summary'] for item in self.ok('export', '--plugin', 'common')['payload']['items']]
        self.assertEqual(len(set(summaries)), 2)


if __name__ == '__main__':
    unittest.main()
