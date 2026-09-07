import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FEReviewScopeTests(unittest.TestCase):
    def test_documented_scope_includes_committed_staged_unstaged_and_owned_untracked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE).decode().strip()

            git('init', '-q')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.test')
            for name in ('Committed.tsx', 'Staged.tsx', 'Unstaged.tsx', 'Deleted.tsx', 'Old Name.tsx'):
                (root / name).write_text(name)
            git('add', '.')
            git('commit', '-qm', 'baseline')
            start = git('rev-parse', 'HEAD')
            (root / 'Committed.tsx').write_text('committed change')
            git('mv', 'Old Name.tsx', 'New Name.tsx')
            git('add', '.')
            git('commit', '-qm', 'implementation')
            (root / 'Staged.tsx').write_text('staged change')
            git('add', 'Staged.tsx')
            (root / 'Unstaged.tsx').write_text('unstaged change')
            (root / 'Deleted.tsx').unlink()
            for name in ('Owned\nComponent.tsx', 'User Component.tsx'):
                (root / name).write_text('new component')
            (root / 'review-owned-files.json').write_text(json.dumps(['Owned\nComponent.tsx']))
            doc = (ROOT / 'fe-harness/skills/start-workflow/references/agent-prompts.md').read_text()
            self.assertIn('scope-contract.md', doc)
            contract = (ROOT / 'fe-harness/skills/start-workflow/references/scope-contract.md').read_text()
            command = next(b for b in re.findall(r'```bash\n(.*?)```', contract, re.S) if 'workflow_scope.py' in b)
            values = {'PLUGIN_ROOT': ROOT / 'fe-harness', 'CWD': root, 'START_SHA': start,
                      'OWNED_FILES': root / 'review-owned-files.json', 'RUN_DIR': root}
            for key, value in values.items():
                command = command.replace('{' + key + '}', str(value))
            result = subprocess.run(['bash', '-c', command], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            scope = json.loads((root / 'scope.json').read_text())
            self.assertEqual(set(scope['read']), {'Committed.tsx', 'Staged.tsx', 'Unstaged.tsx', 'New Name.tsx', 'Owned\nComponent.tsx'})
            self.assertEqual(set(scope['deleted']), {'Deleted.tsx', 'Old Name.tsx'})
            diff = scope['patch']
            self.assertIn('--- a/Deleted.tsx', diff)
            self.assertIn('-Deleted.tsx', diff)
            self.assertIn('+committed change', diff)
            invalid = subprocess.run(['bash', '-c', command.replace(start, 'missing-workflow-sha')], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertEqual(invalid.stdout, '')


if __name__ == '__main__':
    unittest.main()
