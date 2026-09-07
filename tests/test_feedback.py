import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('feedback', ROOT / 'common/skills/submit-feedback/assets/feedback.py')
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.item = {'target_type': 'skill', 'target_name': 'start-workflow', 'summary': 'Use exact paths',
                     'context': 'Concurrent workflow', 'proposal': 'Keep the full path.', 'generality': '범용'}
        self.data = {'plugin': 'new-harness', 'date': '2026-09-06', 'items': [self.item]}

    def test_mapping_preview_matches_written_paths_and_common_slug_collision(self):
        for kind in ('agent', 'common'):
            self.data['items'].append({**self.item, 'target_type': kind})
        self.data['items'].append({**self.item, 'target_type': 'common', 'summary': '한글 내용'})
        self.data['items'].append({**self.item, 'target_type': 'common', 'summary': '다른 내용'})
        receipt = feedback.prepare(self.data, self.root / 'artifacts')
        checkout = self.root / 'checkout'; checkout.mkdir()
        applied = feedback.apply(receipt, checkout)
        self.assertEqual(receipt['destinations'], applied['paths'])
        self.assertEqual(5, applied['added'])
        self.assertNotIn('/commons/', str(applied))
        self.assertEqual(0o600, Path(receipt['artifact']).stat().st_mode & 0o777)
        self.assertEqual('NO_CHANGES', feedback.apply(receipt, checkout)['status'])

    def test_duplicate_only_real_git_clone_does_not_invoke_empty_commit_push_or_pr(self):
        upstream = self.root / 'upstream'; upstream.mkdir()
        def git(*args, cwd=upstream):
            return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)
        git('init'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
        receipt = feedback.prepare(self.data, self.root / 'artifacts')
        feedback.apply(receipt, upstream)
        git('add', '.'); git('commit', '-m', 'Fixture feedback')
        before = git('rev-parse', 'HEAD').stdout
        calls = []
        with tempfile.TemporaryDirectory(dir=self.root, prefix='owned-clone-') as clone:
            git('clone', '--no-hardlinks', str(upstream), clone)
            result = feedback.apply(receipt, clone)
            decision = feedback.outcome('apply', 'ACK', result['added'])
            if decision['next']:
                calls.append(decision['next'])
            self.assertFalse(git('status', '--porcelain', cwd=clone).stdout)
        self.assertEqual([], calls)
        self.assertEqual(before, git('rev-parse', 'HEAD').stdout)
        self.assertTrue(Path(receipt['artifact']).is_file())
        self.assertFalse(Path(clone).exists())

    def test_every_transport_failure_preserves_local_copy_and_only_owned_checkout_is_cleaned(self):
        sentinel = self.root / 'user-checkout'; sentinel.mkdir(); (sentinel / 'keep').write_text('user')
        for stage in ('auth', 'fork', 'clone', 'commit', 'push', 'pr'):
            receipt = feedback.prepare(self.data, self.root / 'artifacts')  # before auth
            with tempfile.TemporaryDirectory(dir=self.root, prefix='owned-') as checkout:
                Path(checkout, 'partial-clone').write_text('partial')
                result = feedback.outcome(stage, 'FAILED', 1)
                self.assertIsNone(result['next'])
            self.assertFalse(Path(checkout).exists())
            self.assertEqual('new-harness', feedback.load(receipt)['plugin'])
            self.assertEqual('user', (sentinel / 'keep').read_text())
        self.assertFalse((self.root / '.claude/new-harness/common.md').exists())

    def test_accepted_push_and_pr_response_loss_never_resends_and_existing_pr_is_reused(self):
        remote_calls = []
        for stage in ('push', 'pr'):
            remote_calls.append(stage)  # local mock accepts, then loses response
            result = feedback.outcome(stage, 'UNKNOWN', 1)
            self.assertEqual('UNKNOWN', result['status'])
            self.assertTrue(result['readback_required'])
            self.assertIsNone(result['next'])
        self.assertEqual(['push', 'pr'], remote_calls)
        self.assertEqual('ALREADY_SUBMITTED', feedback.outcome('pr', 'EXISTS_MATCH', 1)['status'])
        self.assertEqual('LOCAL_ONLY', feedback.outcome('pr', 'EXISTS_OTHER', 1)['status'])

    def test_invalid_path_modified_artifact_and_symlink_block(self):
        for key, value in [('target_name', '../outside'), ('target_type', 'commons')]:
            with self.assertRaises(ValueError):
                feedback.prepare({**self.data, 'items': [{**self.item, key: value}]}, self.root / 'artifacts')
        receipt = feedback.prepare(self.data, self.root / 'artifacts')
        checkout = self.root / 'checkout'; checkout.mkdir()
        (checkout / 'new-harness').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            feedback.apply(receipt, checkout)
        Path(receipt['artifact']).write_text('{}')
        with self.assertRaises(ValueError):
            feedback.load(receipt)

    def test_legacy_entry_fields_are_recognized_as_duplicate(self):
        receipt = feedback.prepare(self.data, self.root / 'artifacts')
        path = self.root / 'clone' / receipt['destinations'][0]
        path.parent.mkdir(parents=True)
        path.write_text('## 2026-09-06\n\n**대상**: skill:start-workflow\n**요지**: Use exact paths\n\nOld body\n')
        self.assertEqual('NO_CHANGES', feedback.apply(receipt, self.root / 'clone')['status'])
        self.data['items'][0]['target_type'] = 'common'
        receipt = feedback.prepare(self.data, self.root / 'artifacts')
        path = self.root / 'clone/new-harness/community-feedback/common/2026-09-06-use-exact-paths.md'
        path.parent.mkdir(parents=True)
        path.write_text('## 2026-09-06\n\n**대상**: common:start-workflow\n**요지**: Use exact paths\n')
        self.assertEqual('NO_CHANGES', feedback.apply(receipt, self.root / 'clone')['status'])
        self.assertEqual(1, len(list(path.parent.iterdir())))
