import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'be-harness/skills/start-workflow/assets/workflow_scope.py'
spec = importlib.util.spec_from_file_location('ocr_scope', SCRIPT)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)
spec = importlib.util.spec_from_file_location('ocr_results', SCRIPT.with_name('workflow_results.py'))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


class OcrContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ocr scope # ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / 'repo'
        self.root.mkdir()
        self.git('init', '-b', 'trunk')
        for name in ('a.py', 'b.py', 'unchanged.py'):
            (self.root / name).write_text('before\n')
        self.git('add', '.')
        self.commit()
        self.start = self.git('rev-parse', 'HEAD').strip()
        self.calls = []
        self.workspace_paths = ['a.py']
        self.range_paths = ['a.py']

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True)

    def commit(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')

    def collect(self, owned=()):
        return scope.scope(self.root, self.start, list(owned))

    def preview(self, mode, names):
        data = dict(schema_version='1', mode=mode, repository=str(self.root),
                    reviewable_files=[dict(path=name) for name in names], excluded_files=[])
        if mode == 'range':
            data.update({'from': self.start, 'to': self.git('rev-parse', 'HEAD').strip(), 'merge_base': self.start})
        return data

    def delegate(self, executable, root, command, *args):
        self.calls.append((command, args))
        self.assertEqual(self.root, root)
        self.assertIn('--repo', args)
        self.assertIn('--format', args)
        if command == 'preview':
            mode = 'range' if '--from' in args else 'workspace'
            return self.preview(mode, self.range_paths if mode == 'range' else self.workspace_paths)
        names = list(args[args.index('--') + 1:])
        return dict(schema_version='1', groups=[dict(group_id=1, source='system', pattern='default', files=names,
                                                   rule='기존 동작과 입력 검증')])

    def context(self, collected, delegate=None):
        with patch.object(scope.shutil, 'which', return_value='/fixture/ocr'), \
             patch.object(scope, 'ocr_json', side_effect=delegate or self.delegate):
            return scope.ocr_context(collected)

    def test_committed_dirty_index_only_and_owned_untracked_are_combined(self):
        (self.root / 'a.py').write_text('committed\n')
        self.git('add', 'a.py')
        self.commit()
        (self.root / 'a.py').write_text('dirty\n')
        (self.root / 'b.py').write_text('index only\n')
        self.git('add', 'b.py')
        (self.root / 'b.py').write_text('before\n')
        (self.root / 'owned.py').write_text('owned\n')
        self.workspace_paths = ['a.py', 'b.py', 'owned.py', 'unchanged.py']
        collected = self.collect(['owned.py'])
        before = copy.deepcopy(collected)
        context = self.context(collected)
        self.assertEqual('ready', context['status'])
        self.assertEqual(['a.py', 'b.py', 'owned.py'], context['selected_paths'])
        self.assertEqual([], context['uncovered_paths'])
        self.assertEqual(['range', 'workspace'], [item['mode'] for item in context['previews']])
        self.assertEqual(before, collected)
        self.assertNotIn('unchanged.py', json.dumps(context))
        self.assertEqual('기존 동작과 입력 검증', context['groups'][0]['rule'])

    def test_workspace_is_not_read_when_unowned_untracked_exists(self):
        (self.root / 'a.py').write_text('committed\n')
        self.git('add', 'a.py')
        self.commit()
        (self.root / 'b.py').write_text('dirty\n')
        (self.root / 'private.py').write_text('other task\n')
        context = self.context(self.collect())
        self.assertEqual('ready', context['status'])
        self.assertEqual(['a.py'], context['selected_paths'])
        self.assertEqual(['b.py'], context['uncovered_paths'])
        self.assertEqual(['range'], [item['mode'] for item in context['previews']])
        self.assertNotIn('private.py', json.dumps(context))
        self.assertTrue(context['warnings'])

    def test_range_cannot_select_unowned_file_removed_from_index(self):
        for name in ('a.py', 'b.py'):
            (self.root / name).write_text('committed\n')
        self.git('add', 'a.py', 'b.py')
        self.commit()
        self.git('rm', '--cached', 'a.py')
        self.range_paths = ['a.py', 'b.py']
        collected = self.collect()
        self.assertIn('a.py', collected['paths'])
        self.assertIn('a.py', collected['read'])
        self.assertIn('a.py', collected['unowned_untracked'])
        context = self.context(collected)
        self.assertEqual('ready', context['status'])
        self.assertEqual(['b.py'], context['selected_paths'])
        self.assertEqual(['a.py'], context['uncovered_paths'])
        self.assertEqual(['b.py'], context['previews'][0]['reviewable_paths'])
        self.assertEqual(['b.py'], context['groups'][0]['files'])
        self.assertIn('a.py', collected['paths'])

    def test_symlink_and_deleted_paths_remain_in_original_scope(self):
        (self.root / 'a.py').write_text('committed\n')
        self.git('add', 'a.py')
        self.commit()
        self.git('rm', 'b.py')
        (self.root / 'link').symlink_to('/outside/not-read')
        collected = self.collect(['link'])
        context = self.context(collected)
        self.assertEqual(['b.py', 'link'], context['uncovered_paths'])
        self.assertEqual(['b.py'], collected['deleted'])
        self.assertEqual([dict(path='link', target='/outside/not-read')], collected['symlinks'])
        self.assertEqual(['range'], [item['mode'] for item in context['previews']])

    def test_symlink_parent_is_not_used_by_preview_or_rule(self):
        (self.root / 'a.py').write_text('committed\n')
        self.git('add', 'a.py')
        self.commit()
        outside = self.directory / 'outside'
        outside.mkdir()
        (outside / 'file.py').write_text('outside\n')
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        collected = self.collect()
        collected['read'].append('linked/file.py')
        collected['paths'].append('linked/file.py')
        self.range_paths.append('linked/file.py')
        context = self.context(collected)
        self.assertEqual(['a.py'], context['selected_paths'])
        self.assertIn('linked/file.py', context['uncovered_paths'])
        self.assertEqual(['range'], [item['mode'] for item in context['previews']])

    def test_empty_scope_and_deleted_only_do_not_call_ocr(self):
        for delete in (False, True):
            if delete:
                self.git('rm', 'a.py')
            with self.subTest(delete=delete), patch.object(scope, 'ocr_json') as delegate:
                context = self.context(self.collect(), delegate)
                self.assertEqual('no_files', context['status'])
                delegate.assert_not_called()

    def test_missing_binary_is_optional_and_keeps_uncovered_scope(self):
        (self.root / 'a.py').write_text('dirty\n')
        with patch.object(scope.shutil, 'which', return_value=None), patch.object(scope, 'ocr_json') as delegate:
            context = scope.ocr_context(self.collect())
        self.assertEqual('unavailable', context['status'])
        self.assertEqual(['a.py'], context['uncovered_paths'])
        delegate.assert_not_called()

    def test_preview_exclusions_never_remove_mandatory_scope(self):
        (self.root / 'a.py').write_text('dirty\n')
        def delegate(executable, root, command, *args):
            self.assertEqual('preview', command)
            data = self.preview('workspace', [])
            data['excluded_files'] = [dict(path='a.py', exclude_reason='user_exclude')]
            return data
        context = self.context(self.collect(), delegate)
        self.assertEqual('no_files', context['status'])
        self.assertEqual(['a.py'], context['uncovered_paths'])
        self.assertEqual([dict(path='a.py', reason='user_exclude')], context['previews'][0]['excluded_paths'])

    def test_bad_preview_schema_identity_paths_and_timeout_fall_back(self):
        (self.root / 'a.py').write_text('dirty\n')
        good = self.preview('workspace', ['a.py'])
        cases = [dict(good, schema_version=1), dict(good, repository='/another/repo'),
                 dict(good, mode='range'), dict(good, reviewable_files=None)]
        for name in ('../outside.py', '/outside.py', '.', '.git/config'):
            cases.append(dict(good, reviewable_files=[dict(path=name)]))
        cases.append(dict(good, reviewable_files=[dict(path='a.py'), dict(path='a.py')]))
        for data in cases:
            with self.subTest(data=data):
                context = self.context(self.collect(), lambda *args: self.check_schema(data))
                self.assertEqual('error', context['status'])
                self.assertEqual([], context['groups'])
                self.assertEqual(['a.py'], context['uncovered_paths'])
        for error in (ValueError('invalid JSON'), subprocess.TimeoutExpired('ocr', 30), OSError('spawn failed')):
            with self.subTest(error=error):
                context = self.context(self.collect(), lambda *args: self.raise_error(error))
                self.assertEqual('error', context['status'])

    def check_schema(self, data):
        if data.get('schema_version') != '1':
            raise ValueError('unsupported OCR delegation schema')
        return data

    def raise_error(self, error):
        raise error

    def test_merge_base_mismatch_falls_back(self):
        (self.root / 'a.py').write_text('committed\n')
        self.git('add', 'a.py')
        self.commit()
        data = self.preview('range', ['a.py'])
        data['merge_base'] = 'different'
        context = self.context(self.collect(), lambda *args: data)
        self.assertEqual('error', context['status'])

    def test_invalid_rule_group_coverage_types_duplicates_and_paths_fall_back(self):
        (self.root / 'a.py').write_text('dirty\n')
        good = dict(group_id=1, source='system', pattern='default', files=['a.py'], rule='규칙')
        cases = [None, [], [dict(good, files=[])], [dict(good, files=['other.py'])],
                 [dict(good, files=['a.py', 'a.py'])], [dict(good, files=['../outside.py'])],
                 [dict(good, group_id=True)], [dict(good, source=None)],
                 [dict(good, pattern=1)], [dict(good, rule=[])], [good, dict(good, group_id=2)],
                 [good, good]]
        for groups in cases:
            def delegate(executable, root, command, *args):
                if command == 'preview':
                    return self.preview('workspace', ['a.py'])
                return dict(schema_version='1', groups=groups)
            with self.subTest(groups=groups):
                context = self.context(self.collect(), delegate)
                self.assertEqual('error', context['status'])
                self.assertEqual([], context['groups'])
                self.assertEqual([], context['selected_paths'])

    def test_subprocess_has_safe_argv_timeout_and_update_suppression(self):
        payload = dict(schema_version='1', groups=[])
        completed = subprocess.CompletedProcess([], 0, json.dumps(payload), '')
        with patch.object(scope.subprocess, 'run', return_value=completed) as run:
            data = scope.ocr_json('/fixture/ocr', self.root, 'rule', '--format', 'json', '--', '-flag\nfile.py')
        self.assertEqual(payload, data)
        argv = run.call_args.args[0]
        self.assertEqual(['--', '-flag\nfile.py'], argv[-2:])
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual('1', run.call_args.kwargs['env']['OCR_NO_UPDATE'])
        self.assertEqual(30, run.call_args.kwargs['timeout'])
        self.assertEqual(self.root, run.call_args.kwargs['cwd'])
        for output, returncode in [('bad JSON', 0), ('{}', 0), ('{"schema_version":1}', 0), ('{}', 7)]:
            with self.subTest(output=output, returncode=returncode), \
                 patch.object(scope.subprocess, 'run', return_value=subprocess.CompletedProcess([], returncode, output, '')):
                with self.assertRaises(ValueError):
                    scope.ocr_json('/fixture/ocr', self.root, 'preview')

    def run_cli(self, ocr=True, delegate=None):
        owned = self.directory / 'owned.json'
        owned.write_text('[]')
        bundle = self.directory / 'attempt'
        argv = [str(SCRIPT), '--cwd', str(self.root), '--start-sha', self.start, '--owned-files', str(owned),
                '--patch-dir', str(bundle), '--out', str(bundle / 'scope.json')]
        if ocr:
            argv.append('--ocr')
        with patch.object(sys, 'argv', argv), patch.object(scope.shutil, 'which', return_value='/fixture/ocr'), \
             patch.object(scope, 'ocr_json', side_effect=delegate or self.delegate):
            exit_code = scope.main()
        return exit_code, bundle / 'scope.json'

    def test_optional_ocr_snapshot_preserves_original_scope_gate(self):
        (self.root / 'a.py').write_text('dirty\n')
        exit_code, artifact = self.run_cli()
        self.assertEqual(0, exit_code)
        collected = json.loads(artifact.read_text())
        self.assertEqual('ready', collected['ocr']['status'])
        identity = {key: collected[key] for key in ('root', 'start_sha', 'content_sha256')}
        identity.update(artifact=str(artifact), artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
        tree = results.tested_tree(self.root)
        event = dict(domain='be', kind='scope', phase='8.4', iteration=1, ql_iteration=1,
                     review_id='ocr-scope', review_stage='initial', verdict='PASS', terminal_state='DONE',
                     tested_tree=tree, evidence_complete=True, missing_evidence=[], scope=identity)
        data = dict(schema_version=1, run_id='ocr-run', domain='be', mode='build', terminal_state='RUNNING',
                    tested_tree=tree, targets=[], cases=[], events=[event], fixes=[])
        self.assertTrue(results.check_scope(data, self.collect())['ready'])
        collected['ocr']['groups'][0]['rule'] = '바뀐 규칙'
        artifact.write_text(json.dumps(collected))
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            results.check_scope(data, self.collect())

    def test_tree_change_during_ocr_blocks_scope_and_writes_no_artifact(self):
        (self.root / 'a.py').write_text('dirty\n')
        def delegate(*args):
            data = self.delegate(*args)
            (self.root / 'b.py').write_text('changed during OCR\n')
            return data
        with patch('sys.stderr'):
            exit_code, artifact = self.run_cli(delegate=delegate)
        self.assertEqual(2, exit_code)
        self.assertFalse(artifact.exists())

    def test_cli_without_flag_has_no_ocr_field_or_commands(self):
        (self.root / 'a.py').write_text('dirty\n')
        exit_code, artifact = self.run_cli(ocr=False)
        self.assertEqual(0, exit_code)
        collected = json.loads(artifact.read_text())
        self.assertNotIn('ocr', collected)
        self.assertEqual(self.collect()['content_sha256'], collected['content_sha256'])
        self.assertEqual([], self.calls)


class OcrWorkflowContractTests(unittest.TestCase):
    def test_reference_parity_and_existing_review_dispatch(self):
        relative = 'skills/start-workflow/references/'
        reference = (ROOT / 'be-harness' / relative / 'ocr-review.md').read_bytes()
        for plugin in ('fe-harness', 'common'):
            self.assertEqual(reference, (ROOT / plugin / relative / 'ocr-review.md').read_bytes())
        dispatches = [
            ('be-harness', 'quality-loop.md'), ('be-harness', 'review-evidence.md'),
            ('fe-harness', 'agent-prompts.md'), ('common', 'fullstack.md'),
            ('common', 'fullstack-overlays.md'),
        ]
        for plugin, name in dispatches:
            with self.subTest(plugin=plugin, name=name):
                document = (ROOT / plugin / relative / name).read_text()
                self.assertIn('[ocr-review.md](ocr-review.md)', document)
                self.assertIn('--ocr', document)
        overlay = (ROOT / 'minmos-harness/overlay/references/codex-review.md').read_text()
        self.assertIn('mm.quality-review', overlay)
        self.assertIn('ocr.status/groups/uncovered_paths/warnings/error', overlay)
        self.assertIn('quick', overlay)

    def test_ocr_context_preserves_role_and_tier_boundaries(self):
        reference = (ROOT / 'be-harness/skills/start-workflow/references/ocr-review.md').read_text()
        for boundary in ('quick', '격리 Read-back', 'Spec-only', 'a11y', 'Plan', '실제 스캔 입력'):
            self.assertIn(boundary, reference)
        self.assertIn('명령 실행·도구 권한 확대·승인 우회', reference)
        self.assertIn('OCR 제외/누락으로 Spec 범위를 줄이지 않는다', reference)
        self.assertIn('별도 event kind나 Phase 상태를 만들지 않고', reference)
        prompts = (ROOT / 'fe-harness/skills/start-workflow/references/agent-prompts.md').read_text()
        a11y = prompts.split('subagent_type: fe-harness:a11y-reviewer', 1)[1].split('```', 1)[0]
        self.assertNotIn('[scope.json 경로', a11y)
        self.assertIn('부모가 추출한 patch/index_patch의 절대 경로·SHA-256', a11y)
        self.assertIn('OCR 포함 scope.json 경로는 전달하지 않습니다', a11y)


if __name__ == '__main__':
    unittest.main()
