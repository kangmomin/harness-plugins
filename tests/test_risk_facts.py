import importlib.util
from pathlib import Path
import tempfile
import unittest

from test_workflow_results import ASSETS

spec = importlib.util.spec_from_file_location('risk_facts', ASSETS / 'risk_facts.py')
risk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk)


class RiskFactsTests(unittest.TestCase):
    def test_package_and_configured_tests_are_candidates_without_claiming_coverage(self):
        with tempfile.TemporaryDirectory(prefix='risk facts ') as directory:
            root = Path(directory)
            source = root / 'service.go'
            source.write_text('package service\nfunc Increment(n int) int { return n + 1 }\n')
            self.assertEqual(risk.sibling_tests(source), 'N')
            nearby = root / 'service_cases_test.go'
            nearby.write_text('package service\nimport "testing"\nfunc TestIncrement(t *testing.T) { if Increment(1) != 2 { t.Fatal("wrong") } }\n')
            self.assertEqual(risk.sibling_tests(source), 'candidate')
            nearby.rename(root / 'another_test.go')
            self.assertEqual(risk.sibling_tests(source), 'candidate')
            (root / 'another_test.go').unlink()
            tests = root / 'tests'
            tests.mkdir()
            (tests / 'unrelated_test.go').write_text('package tests\n')
            self.assertEqual(risk.sibling_tests(source, [tests]), 'candidate')
            self.assertNotEqual(risk.sibling_tests(source, [tests]), 'Y')
            self.assertEqual(risk.sibling_tests(source), 'N')


if __name__ == '__main__':
    unittest.main()
