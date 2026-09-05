from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowCommandTests(unittest.TestCase):
    def test_documented_fe_checks_preserve_failure_exit_codes(self):
        for file in ("fe-harness/skills/start-workflow/SKILL.md", "fe-harness/agents/workflow-implementer.md"):
            blocks = re.findall(r"```bash\n(.*?)```", (ROOT / file).read_text(), re.S)
            for placeholder in ("{buildCommand}", "{typeCheckCommand}"):
                checks = [b.strip() for b in blocks if placeholder in b]
                self.assertEqual(len(checks), 1, (file, placeholder))
                # Run the actual documented snippet, substituting a failing project command.
                command = checks[0].replace(placeholder, "bash -c 'echo compiler-error; exit 7'")
                result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
                self.assertEqual(result.returncode, 7, (file, placeholder, result.stdout))
                self.assertIn("compiler-error", result.stdout)


if __name__ == "__main__":
    unittest.main()
