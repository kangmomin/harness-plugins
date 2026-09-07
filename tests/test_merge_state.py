import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'common/skills/merge/assets/merge_state.py'
spec = importlib.util.spec_from_file_location('merge_state', SCRIPT)
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)


def fixture():
    return dict(id='PR_fixture', number=42, url='https://example.invalid/o/r/pull/42',
                headRefName='feat/work', baseRefName='trunk', headRefOid='a' * 40,
                baseRefOid='b' * 40, state='OPEN', autoMergeRequest=None, mergeCommit=None)


class MergeStateTests(unittest.TestCase):
    def test_summary_and_approval_are_bound_to_original_head(self):
        before = fixture()
        reviewed = merge.snapshot(before)
        after_summary = {**before, 'headRefOid': 'c' * 40}
        with self.assertRaisesRegex(ValueError, 'REVIEW_STALE'):
            merge.same_review(reviewed, after_summary)
        with self.assertRaisesRegex(ValueError, 'REVIEW_STALE'):
            merge.merge_command(reviewed, after_summary, 'squash')
        argv = merge.merge_command(reviewed, before, 'squash')
        self.assertEqual('a' * 40, argv[argv.index('--match-head-commit') + 1])
        self.assertNotIn('--delete-branch', argv)

    def test_exit_zero_open_is_neither_merged_nor_proven_queued(self):
        current = fixture()
        result = merge.outcome(current, current, 0)
        self.assertEqual('OPEN_UNCONFIRMED', result['status'])
        self.assertFalse(result['delete_allowed'])
        self.assertIsNone(result['merge_sha'])
        current['autoMergeRequest'] = {'enabledAt': 'fixture'}
        result = merge.outcome(current, current, 0)
        self.assertEqual('PENDING_AUTO_MERGE', result['status'])
        self.assertFalse(result['delete_allowed'])

    def test_remote_merge_commit_wins_even_when_command_exit_is_nonzero(self):
        reviewed = fixture()
        current = {**reviewed, 'state':'MERGED', 'baseRefOid':'c' * 40, 'mergeCommit':{'oid':'d' * 40}}
        result = merge.outcome(reviewed, current, 1)
        self.assertEqual('MERGED', result['status'])
        self.assertEqual('d' * 40, result['merge_sha'])
        self.assertNotEqual(current['baseRefOid'], result['merge_sha'])
        self.assertTrue(result['delete_allowed'])

    def test_missing_merge_evidence_or_different_head_is_not_reviewed_success(self):
        reviewed = fixture()
        with self.assertRaisesRegex(ValueError, 'WITHOUT_COMMIT'):
            merge.outcome(reviewed, {**reviewed, 'state':'MERGED'}, 0)
        current = {**reviewed, 'state':'MERGED', 'headRefOid':'c' * 40, 'mergeCommit':{'oid':'d' * 40}}
        result = merge.outcome(reviewed, current, 0)
        self.assertEqual('MERGED_DIFFERENT_REVIEW', result['status'])
        self.assertFalse(result['delete_allowed'])


if __name__ == '__main__':
    unittest.main()
