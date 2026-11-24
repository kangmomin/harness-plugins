import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'common' / 'hooks' / 'metrics.py'


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class MetricsHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / 'repo'
        self.store = base / 'store'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.email', 't@example.com')
        git(self.repo, 'config', 'user.name', 't')
        git(self.repo, 'config', 'commit.gpgsign', 'false')

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, *args, stdin=None, cwd=None):
        env = {**os.environ, 'HARNESS_METRICS_DIR': str(self.store)}
        out = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), *args, '--cwd', str(cwd or self.repo)],
                             input=stdin, capture_output=True, text=True, encoding='utf-8', env=env)
        return out

    def ok(self, *args, stdin=None, cwd=None):
        out = self.run_helper(*args, stdin=stdin, cwd=cwd)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def commit(self, name, lines):
        (self.repo / name).write_text(''.join(f'{i}\n' for i in range(lines)), encoding='utf-8')
        git(self.repo, 'add', name)
        git(self.repo, 'commit', '-q', '-m', f'Feat: {name}')
        return git(self.repo, 'rev-parse', 'HEAD')

    def test_head_marker_resolves_and_dedupes(self):
        sha = self.commit('a.txt', 3)
        self.ok('record', stdin=self.segment(sha[:7]).replace('"commits": [', '"commits": [{"short": "HEAD", "branch": "", "amend": false}, '))
        row = json.loads(next(self.store.glob('*/commits.jsonl')).read_text(encoding='utf-8'))
        self.assertEqual([(c['sha'], c['short'], c['branch']) for c in row['commits']], [(sha, sha[:7], 'main')])

    def test_amend_is_not_a_new_commit_and_unknown_lines_skip_ratio(self):
        self.ok('record', stdin=self.segment(self.commit('a.txt', 10)[:7], tokens=1000))
        amend = json.loads(self.segment(git(self.repo, 'rev-parse', '--short', 'HEAD'), tokens=200))
        amend['commits'][0]['amend'] = True
        self.ok('record', stdin=json.dumps(amend))
        self.ok('record', stdin=self.segment('deadbee', tokens=5000))  # 줄 수를 모르는 커밋
        group = self.ok('summary')['groups'][0]
        self.assertEqual(group['commits'], 2)
        self.assertEqual(group['avgTokens'], 3100)  # (1000 + 200 + 5000) / 2
        self.assertEqual(group['tokensPerLine'], 100)  # 1000 / 10, deadbee 기록은 빠진다

    def segment(self, short, tokens=1000, prompts=2, active=120000):
        return json.dumps({
            'tokens': {'main': {'input': tokens, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0},
                       'sub': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}},
            'costUsd': 0.5, 'time': {'wallMs': active, 'activeMs': active, 'turns': 1},
            'input': {'prompts': prompts, 'followUps': prompts - 1, 'aborted': 0, 'denied': 1},
            'review': {'agents': 1, 'skills': 0, 'codex': 1, 'workflow': None},
            'commits': [{'short': short, 'branch': 'main', 'amend': False}] if short else [],
        })

    def test_record_expands_short_sha_with_line_counts(self):
        sha = self.commit('a.txt', 10)
        self.assertEqual(self.ok('record', stdin=self.segment(sha[:7]))['commits'], 1)
        files = list(self.store.glob('*/commits.jsonl'))
        self.assertEqual(len(files), 1)
        row = json.loads(files[0].read_text(encoding='utf-8'))
        self.assertEqual(row['commits'][0]['sha'], sha)
        self.assertEqual(row['commits'][0]['subject'], 'Feat: a.txt')
        self.assertEqual((row['commits'][0]['files'], row['commits'][0]['added'], row['commits'][0]['deleted']), (1, 10, 0))
        self.assertTrue(row['plugin'])

    def test_unknown_sha_is_kept_without_stats(self):
        self.commit('a.txt', 1)
        self.ok('record', stdin=self.segment('deadbee'))
        row = json.loads(next(self.store.glob('*/commits.jsonl')).read_text(encoding='utf-8'))
        self.assertEqual(row['commits'][0], {'sha': None, 'short': 'deadbee', 'branch': 'main', 'subject': None,
                                             'files': None, 'added': None, 'deleted': None, 'amend': False})

    def test_summary_groups_by_label_for_before_after(self):
        self.ok('record', stdin=self.segment(self.commit('a.txt', 10)[:7], tokens=1000))
        self.ok('label', '--set', 'after tdd')
        self.ok('record', stdin=self.segment(self.commit('b.txt', 20)[:7], tokens=400, prompts=1))
        self.ok('record', stdin=self.segment(None))  # 미커밋 구간
        summary = self.ok('summary')
        self.assertEqual(summary['label'], 'after tdd')
        self.assertEqual(summary['uncommitted'], 1)
        before, after = summary['groups']
        self.assertTrue(before['label'].startswith('common@'))
        self.assertEqual((before['avgTokens'], before['tokensPerLine'], before['avgActiveMin']), (1000, 100, 2.0))
        self.assertEqual((after['label'], after['avgTokens'], after['avgPrompts'], after['tokensPerLine']), ('after tdd', 400, 1.0, 20))
        self.assertEqual(after['avgReviews'], 2.0)
        self.assertEqual([r['subject'] for r in summary['recent']], ['Feat: b.txt', 'Feat: a.txt'])

    def test_worktrees_share_one_store(self):
        self.commit('a.txt', 1)
        tree = Path(self.tmp.name) / 'wt'
        git(self.repo, 'worktree', 'add', '-q', str(tree), '-b', 'other')
        self.ok('label', '--set', 'x')
        self.assertEqual(self.ok('label', cwd=tree)['label'], 'x')

    def test_label_clear_and_bad_input(self):
        self.ok('label', '--set', 'a')
        self.assertIsNone(self.ok('label', '--clear')['label'])
        out = self.run_helper('record', stdin='not json')
        self.assertEqual(out.returncode, 2)
        self.assertIn('BAD_INPUT', out.stderr)

    def test_outside_git_repo_fails_with_status(self):
        outside = Path(self.tmp.name) / 'plain'
        outside.mkdir()
        out = self.run_helper('summary', cwd=outside)
        self.assertEqual(out.returncode, 2)
        self.assertIn('NOT_GIT_REPO', out.stderr)

    def test_utf8_round_trip_on_every_platform(self):
        # Windows 기본 인코딩(cp949)과 상관없이 UTF-8 로 주고받는다.
        (self.repo / 'k.txt').write_text('x\n', encoding='utf-8')
        git(self.repo, 'add', 'k.txt')
        git(self.repo, 'commit', '-q', '-m', 'Feat: 한글 제목')
        self.ok('label', '--set', '도입 후')
        self.ok('record', stdin=self.segment(git(self.repo, 'rev-parse', '--short', 'HEAD')))
        summary = self.ok('summary')
        self.assertEqual(summary['recent'][0]['subject'], 'Feat: 한글 제목')
        self.assertEqual(summary['groups'][0]['label'], '도입 후')

    def test_truncated_line_is_skipped(self):
        self.ok('record', stdin=self.segment(self.commit('a.txt', 2)[:7]))
        path = next(self.store.glob('*/commits.jsonl'))
        with open(path, 'a', encoding='utf-8') as f:
            f.write('{"broken"\n')
        self.assertEqual(self.ok('summary')['groups'][0]['commits'], 1)


if __name__ == '__main__':
    unittest.main()
