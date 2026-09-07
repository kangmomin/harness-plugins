import errno
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from test_workflow_results import ASSETS, TREE, fixture

ARCHIVE = ASSETS / 'workflow_archive.py'
sys.path.insert(0, str(ASSETS))
spec = importlib.util.spec_from_file_location('archive', ARCHIVE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
import workflow_results


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='archive space ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.md'
        self.state = self.root / 'state.md'
        self.evidence = self.root / 'results.json'
        self.out = self.root / 'out'
        self.source.write_text('# Report\n')
        self.state.write_text('## Run\n- RUN_ID: fixture-run\n## Flags\n- MODE: be\n')
        self.data = fixture()

    def argv(self, *extra):
        self.evidence.write_text(json.dumps(self.data))
        return [sys.executable, str(ARCHIVE), 'report', '--src', str(self.source), '--state', str(self.state),
                '--results', str(self.evidence), '--run-id', 'fixture-run', '--report-dir', str(self.out),
                '--task', 'task', *extra]

    def run_archive(self, *extra, code=0, cwd=None):
        result = subprocess.run(self.argv(*extra), capture_output=True, text=True, cwd=cwd or self.root)
        self.assertEqual(result.returncode, code, result.stderr)
        if code:
            return result.stderr
        path = Path(result.stdout.splitlines()[0].removeprefix('경로: '))
        return result.stdout, path, path.read_text()

    def test_latest_paired_counts_and_domain_phases_are_preserved(self):
        for domain, phase in (('be', '8.1'), ('fe', '7.1'), ('fs', '7')):
            with self.subTest(domain=domain):
                self.out = self.root / domain
                self.data['domain'] = domain
                self.state.write_text('## Flags\n- MODE: ' + domain + '\n')
                event_domain = 'be' if domain == 'fs' else domain
                self.data['events'] = [dict(domain=event_domain, kind='unit', phase=phase, iteration=n,
                    verdict=v, regression_count=c, terminal_state='DONE', tested_tree=TREE)
                    for n, v, c in [(1, 'FAIL', 2), (2, 'PASS', 0)]]
                self.data['events'].append(dict(domain=event_domain, kind='readback', phase='8.1' if domain == 'fs' else 'review',
                    iteration=1, verdict='WARN', terminal_state='DONE', tested_tree=TREE))
                stdout, _, report = self.run_archive()
                self.assertIn('상태: OK', stdout)
                self.assertIn('regression_count: 0', report)
                self.assertIn('최종 테스트 판정: %s Phase %s PASS · regression: 0' % (event_domain, phase), report)
                self.assertIn('- Read-back: %s Phase ' % event_domain, report)
                self.assertNotIn('최종 테스트 판정: WARN', report)

    def test_degraded_reuse_retains_status_across_task_change(self):
        first, path, original = self.run_archive('--require-headings', 'Missing')
        second, reused, _ = self.run_archive('--task', 'renamed')
        self.assertIn('DEGRADED', first)
        self.assertIn('DEGRADED', second)
        self.assertEqual(path, reused)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(len(list(self.out.glob('*.md'))), 1)

    def test_run_conflict_and_duplicate_frontmatter_are_controlled(self):
        for header in ('run_id: old-run', 'title: one\ntitle: two'):
            with self.subTest(header=header):
                self.source.write_text('---\n' + header + '\n---\n# Report\n')
                self.run_archive(code=2)
                self.assertFalse(list(self.out.glob('*.md')))

    def test_unfinished_result_cannot_be_archived_as_complete(self):
        self.data['terminal_state'] = 'BLOCKED:TEST_NOT_GREEN'
        self.assertIn('unfinished run', self.run_archive(code=2))

    def test_git_paths_with_newline_tab_colon_unicode_roundtrip(self):
        repo = self.root / 'repo'
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args]).decode().strip()
        git('init', '-q')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (repo / 'base.py').write_text('base')
        git('add', 'base.py')
        git('commit', '-qm', 'baseline')
        head = git('rev-parse', 'HEAD')
        names = ['line\nname.py', 'tab\tname.py', 'colon: name.py', '한글.py']
        for name in names:
            (repo / name).write_text('changed')
        _, _, report = self.run_archive('--start-sha', head, cwd=repo)
        metadata = report.split('---\n', 2)[1].splitlines()
        encoded = next(line.removeprefix('touched_paths: ') for line in metadata if line.startswith('touched_paths:'))
        self.assertEqual(set(json.loads(encoded)), set(names))
        self.assertEqual(sum(line.startswith('touched_paths:') for line in metadata), 1)

    def test_output_directory_and_read_errors_return_exit_two(self):
        self.out.write_text('not a directory')
        self.assertIn('아카이브 생성 실패', self.run_archive(code=2))
        self.out.unlink()
        self.source.unlink()
        self.assertIn('입력 파일 없음', self.run_archive(code=2))

    def test_no_replace_fallback_when_atomic_link_is_unsupported(self):
        argv = self.argv()
        with patch.object(sys, 'argv', argv[1:]), patch.object(workflow_results.os, 'link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')), patch.object(workflow_results.os, 'replace') as replace:
            self.assertEqual(archive.main(), 2)
            replace.assert_not_called()
        self.assertFalse(list(self.out.glob('*.md')))
        self.assertFalse(list(self.out.glob('*.tmp')))

    def test_concurrent_same_run_has_one_archive(self):
        argv = self.argv()
        children = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root) for _ in range(4)]
        try:
            replies = [child.communicate(timeout=15) for child in children]
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
        self.assertTrue(all(child.returncode == 0 for child in children), replies)
        self.assertEqual(len({stdout.splitlines()[0] for stdout, _ in replies}), 1)
        self.assertEqual(len(list(self.out.glob('*.md'))), 1)

    def test_concurrent_publication_preserves_existing_report(self):
        self.out.mkdir()
        sentinel = self.out / 'same.md'
        sentinel.write_text('EXISTING')
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda n: workflow_results.publish_text(self.out, 'same', 'RUN %d' % n), range(4)))
        self.assertEqual(len(set(paths)), 4)
        self.assertEqual(sentinel.read_text(), 'EXISTING')
        self.assertEqual({path.read_text() for path in paths}, {'RUN %d' % n for n in range(4)})


if __name__ == '__main__':
    unittest.main()
