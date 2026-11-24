import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'be-harness/skills/start-workflow/assets/harness_config.py'
spec = importlib.util.spec_from_file_location('harness_config', SCRIPT)
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


class HarnessConfigTests(unittest.TestCase):
    def run_with(self, config, **kw):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            if config is not None:
                (root / '.claude').mkdir()
                text = config if isinstance(config, str) else json.dumps(config)
                (root / '.claude/harness.config.json').write_text(text, encoding='utf-8')
            kw.setdefault('codex_mode', 'mix')
            kw.setdefault('codex_source', 'profile')
            return hc.resolve(root, **kw)

    def test_missing_file_keeps_current_behavior(self):
        result = self.run_with(None)
        self.assertEqual({'plan': 'codex', 'quality': 'codex'}, result['reviewers'])
        self.assertEqual('ocr=on,e2e=on,simplify=on,reflect=off', result['flags']['STEPS'])
        self.assertIsNone(result['config_path'])
        self.assertEqual([], result['diagnostics'])
        self.assertEqual('claude', self.run_with(None, codex_mode='none')['reviewers']['plan'])

    def test_review_off_means_claude_panel_not_skip(self):
        result = self.run_with({'review': {'enabled': False, 'engine': 'gemini'}})
        self.assertEqual({'plan': 'claude', 'quality': 'claude'}, result['reviewers'])
        self.assertNotIn('GEMINI_MODEL', result['flags'])

    def test_per_point_toggle_and_gemini_model(self):
        result = self.run_with({'review': {'engine': 'gemini', 'points': {'quality': False},
                                           'gemini': {'model': 'gemini-x-pro'}}})
        self.assertEqual('plan=gemini,quality=claude', result['flags']['REVIEW'])
        self.assertEqual('gemini-x-pro', result['flags']['GEMINI_MODEL'])
        self.assertEqual('-', self.run_with({'review': {'engine': 'gemini'}})['flags']['GEMINI_MODEL'])

    def test_config_codex_engine_lifts_profile_none(self):
        result = self.run_with({'review': {'engine': 'codex'}}, codex_mode='none', codex_source='profile')
        self.assertEqual(('mix', 'config'), (result['values']['codexMode'], result['sources']['codexMode']))
        self.assertEqual('codex', result['reviewers']['plan'])

    def test_codex_none_flag_beats_config(self):
        result = self.run_with({'review': {'engine': 'codex'}}, codex_mode='none', codex_source='flag')
        self.assertEqual('none', result['values']['codexMode'])
        self.assertEqual('claude', result['reviewers']['plan'])
        self.assertIn('CODEX_DISABLED_BY_FLAG', [d['code'] for d in result['diagnostics']])

    def test_step_precedence(self):
        self.assertFalse(self.run_with(None, e2e_enabled=False)['values']['steps.e2e'])
        result = self.run_with({'steps': {'e2e': True, 'reflect': False, 'ocr': False}},
                               e2e_enabled=False, reflect_flag=True)
        self.assertEqual('config', result['sources']['steps.e2e'])
        self.assertTrue(result['values']['steps.e2e'])
        self.assertEqual(('flag', True), (result['sources']['steps.reflect'], result['values']['steps.reflect']))
        self.assertEqual('ocr=off,e2e=on,simplify=on,reflect=on', result['flags']['STEPS'])

    def test_invalid_key_only_drops_that_key(self):
        result = self.run_with({'version': 1, 'review': {'engine': 'gpt', 'points': {'plan': 'no'}},
                                'steps': {'ocr': False}, 'extra': 1})
        codes = {(d['code'], d['key']) for d in result['diagnostics']}
        self.assertEqual({('INVALID_KEY', 'review.engine'), ('INVALID_KEY', 'review.points.plan'),
                          ('UNKNOWN_KEY', 'extra')}, codes)
        self.assertEqual('codex', result['reviewers']['plan'])
        self.assertFalse(result['values']['steps.ocr'])

    def test_parse_error_ignores_whole_file(self):
        for text in ('{bad', '[]'):
            result = self.run_with(text)
            self.assertEqual('PARSE_ERROR', result['diagnostics'][0]['code'])
            self.assertEqual('codex', result['reviewers']['plan'])

    def test_model_pattern_rejects_shell_chars(self):
        result = self.run_with({'review': {'engine': 'gemini', 'gemini': {'model': 'x; rm -rf /'}}})
        self.assertEqual('-', result['flags']['GEMINI_MODEL'])


    def test_model_cannot_start_with_dash(self):
        for model in ('--yolo', '-y', '-'):
            result = self.run_with({'review': {'engine': 'gemini', 'gemini': {'model': model}}})
            self.assertEqual('-', result['flags']['GEMINI_MODEL'])
            self.assertIn(('INVALID_KEY', 'review.gemini.model'), {(d['code'], d['key']) for d in result['diagnostics']})

    def test_no_promotion_when_no_codex_reviewer_remains(self):
        for review in ({'enabled': False, 'engine': 'codex'},
                       {'engine': 'codex', 'points': {'plan': False, 'quality': False}}):
            result = self.run_with({'review': review}, codex_mode='none', codex_source='profile')
            self.assertEqual('none', result['values']['codexMode'])
            self.assertEqual({'plan': 'claude', 'quality': 'claude'}, result['reviewers'])
            self.assertEqual([], result['diagnostics'])

    def test_explicit_none_from_question_is_kept(self):
        # 3지선다 질문 응답은 명시 입력이므로 source flag 로 전달된다.
        result = self.run_with({'review': {'engine': 'codex', 'enabled': False}}, codex_mode='none', codex_source='flag')
        self.assertEqual([], result['diagnostics'])
        self.assertEqual('claude', result['reviewers']['plan'])


if __name__ == '__main__':
    unittest.main()
