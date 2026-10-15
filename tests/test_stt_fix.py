import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'work-log/skills/stt-fix/assets/stt_fix.py'
spec = importlib.util.spec_from_file_location('stt_fix', SCRIPT)
stt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stt)

SAMPLE = (
    '00:19 참석자 1\n'
    '있는 것 같아요. 상품이 또 GK나 GKE 쪽으로 올리고 상주님 말씀\n'
    '\n'
    '00:28 참석자 2\n'
    '선 프로젝트 구조요 상주님\n'
    '\n'
    '00:28 참석자 1\n'
    '중복 시각 턴 레그 테스트 성준이 너무 끝\n'
    '두 번째 문단\n'
    '\n'
    '그리고 빈 줄 뒤 본문 (헤더 아님)\n'
    '\n'
    '01:00:08 참석자 5\n'
    '한 시간 넘은 턴\n'
    '\n'
    '01:00:11 \n'
    '빈 라벨 턴\n'
)


def _publish_worker(args):
    root, src, dst, content = args
    try:
        return stt.publish(root, src, dst, content)['status']
    except stt.Fail as exc:
        return exc.record['kind']


class SttFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='stt fix # ')
        self.addCleanup(self.temp.cleanup)
        # 헬퍼는 --root 를 다시 resolve 하지 않으므로(심볼릭 링크 구성 요소 거부) 테스트도 canonical 경로를 넘긴다 (macOS /var → /private/var).
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'vault'
        (self.root / 'meeting').mkdir(parents=True)
        self.scratch = self.base / 'scratch'
        self.scratch.mkdir()
        self.src = self.root / 'meeting' / '261014 회의.txt'
        self.src.write_text(SAMPLE, encoding='utf-8')

    def run_apply(self, *extra, src=None):
        log = self.scratch / ('log%d.json' % len(list(self.scratch.iterdir())))
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'apply', '--root', str(self.root),
                                 '--src', str(src or self.src), '--log', str(log), *extra], capture_output=True, text=True)
        self.assertTrue(log.is_file(), 'helper wrote no log: ' + result.stderr)
        return result.returncode, json.loads(log.read_text(encoding='utf-8')), result.stdout

    def write_json(self, name, data):
        path = self.scratch / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def test_parse_mixed_headers_blank_label_and_multi_paragraph_turns(self):
        preamble, turns = stt.parse(SAMPLE)
        self.assertEqual([], preamble)
        self.assertEqual(['00:19 참석자 1', '00:28 참석자 2', '00:28 참석자 1', '01:00:08 참석자 5', '01:00:11 '], [t[0] for t in turns])
        self.assertIn('그리고 빈 줄 뒤 본문 (헤더 아님)', turns[2])
        self.assertEqual(('01:00:11', ''), stt.header_parts(turns[4][0]))
        self.assertEqual('mixed', stt.header_format(turns))

    def test_empty_rules_round_trip_reports_structure(self):
        body = self.scratch / 'body.txt'
        code, log, _ = self.run_apply('--out-body', str(body))
        self.assertEqual(0, code)
        self.assertEqual(SAMPLE, body.read_text(encoding='utf-8'))
        self.assertEqual(5, log['turns'])
        self.assertEqual(['00:28'], log['duplicate_times'])
        self.assertEqual('mixed', log['header_format'])
        self.assertEqual('', log['preamble'])

    def test_nfd_input_is_normalized_and_crlf_folded(self):
        nfd = self.root / 'meeting' / 'nfd.txt'
        nfd.write_text(unicodedata.normalize('NFD', '00:01 참석자 1\r\n상주님 발언\r\n'), encoding='utf-8')
        body = self.scratch / 'nfd-body.txt'
        code, log, _ = self.run_apply('--rules', self.write_json('r.json', {'global': [['상주님', '상준님']]}),
                                      '--out-body', str(body), src=nfd)
        self.assertEqual(0, code)
        self.assertEqual('00:01 참석자 1\n상준님 발언\n', body.read_text(encoding='utf-8'))

    def test_preamble_detects_already_corrected_file(self):
        corrected = self.root / 'meeting' / 'done.txt'
        corrected.write_text('[보정본] 원본: x.txt\n- 안내\n\n' + SAMPLE, encoding='utf-8')
        code, log, _ = self.run_apply(src=corrected)
        self.assertEqual(0, code)
        self.assertTrue(log['preamble'].startswith('[보정본]'))
        self.assertEqual(5, log['turns'])

    def test_no_header_file_is_single_turn_and_round_trips(self):
        plain = self.root / 'meeting' / 'plain.txt'
        plain.write_text('첫 줄 상주님\n둘째 줄\n', encoding='utf-8')
        body = self.scratch / 'plain-body.txt'
        code, log, _ = self.run_apply('--rules', self.write_json('p.json', {'global': [['상주님', '상준님']]}),
                                      '--out-body', str(body), src=plain)
        self.assertEqual(0, code)
        self.assertEqual('format_unknown', log['header_format'])
        self.assertEqual(1, log['turns'])
        self.assertEqual('첫 줄 상준님\n둘째 줄\n', body.read_text(encoding='utf-8'))

    def test_single_pass_boundary_and_scoped_priority(self):
        rules = {'global': [['상주님', '상준님'], ['GK', 'GKE'], ['상준님', '절대안됨'], ['없는말', 'X']],
                 'turns': {'0': [['상품이', '상준님(?)이']], '1': [['상주님', '상우님(?)']]}}
        body = self.scratch / 'b1.txt'
        code, log, _ = self.run_apply('--rules', self.write_json('rules.json', rules), '--out-body', str(body))
        self.assertEqual(0, code, log['failures'])
        text = body.read_text(encoding='utf-8')
        self.assertIn('상준님(?)이 또 GKE나 GKE 쪽으로 올리고 상준님 말씀', text)
        self.assertNotIn('GKEE', text)
        self.assertNotIn('절대안됨', text)
        self.assertIn('선 프로젝트 구조요 상우님(?)', text)
        self.assertEqual(['상준님', '없는말'], log['unused_rules'])
        self.assertEqual(2, log['marker_counts']['estimate'])
        self.assertIn('| `상품이` | 상준님(?)이 | 00:19 (턴 0) |', log['rules_table_md'])
        self.assertEqual([t[0] for t in stt.parse(SAMPLE)[1]], [t[0] for t in stt.parse(text)[1]])

    def test_scoped_mismatch_and_header_change_fail_closed(self):
        body = self.scratch / 'never.txt'
        code, log, _ = self.run_apply('--rules', self.write_json('bad.json', {'turns': {'2': [['상주님', '상준님']]}}),
                                      '--out-body', str(body))
        self.assertEqual(2, code)
        self.assertEqual([{'kind': 'scoped_mismatch', 'turn': 2, 'old': '상주님', 'hits': 0}], log['failures'])
        self.assertFalse(body.exists())
        code, log, _ = self.run_apply('--rules', self.write_json('hdr.json', {'global': [['두 번째 문단', '\n00:30 참석자 9']]}))
        self.assertEqual(2, code)
        self.assertEqual('structure_changed', log['failures'][0]['kind'])
        code, log, _ = self.run_apply('--rules', self.write_json('empty-old.json', {'global': [['', 'x']]}))
        self.assertEqual(2, code)
        self.assertEqual('bad_rules', log['failures'][0]['kind'])
        for wrong in ([], False, {'global': False}, {'turns': []}, {'global': 'x'}):
            code, log, _ = self.run_apply('--rules', self.write_json('wrong-type.json', wrong))
            self.assertEqual(2, code, wrong)
            self.assertEqual('bad_rules', log['failures'][0]['kind'], wrong)

    def test_adjacent_estimate_and_unclear_markers_do_not_overlap(self):
        turns = stt.structure('00:01 A\n상준님(?)과[불명확: 웅얼][불명확: 또](?)끝 그리고 [불명확: 셋]뒤(?) 끝\n')[1]
        markers = stt.extract_markers(turns)
        phrases = [(m['kind'], m['phrase']) for m in markers]
        self.assertEqual([('estimate', '상준님(?)과'), ('unclear', '[불명확: 웅얼]'), ('unclear', '[불명확: 또]'),
                          ('estimate', '(?)끝'), ('unclear', '[불명확: 셋]'), ('estimate', '뒤(?)')], phrases)
        for previous, current in zip(markers, markers[1:]):
            self.assertLessEqual(previous['end'], current['start'])
        stt.apply_decisions(turns, [(markers[0], 'fix', '상준님과')])
        self.assertEqual('상준님과[불명확: 웅얼][불명확: 또](?)끝 그리고 [불명확: 셋]뒤(?) 끝\n', stt.body_of(turns[0]))
        self.assertEqual(5, len(stt.extract_markers(turns)))
        fake = dict(markers[1], start=markers[1]['start'] - 1)
        with self.assertRaises(stt.Fail) as caught:
            stt.apply_decisions(turns, [(markers[0], 'hold', ''), (fake, 'hold', '')])
        self.assertEqual('overlapping_markers', caught.exception.record['kind'])

    def test_decisions_apply_by_marker_id_with_repeated_phrases(self):
        repeated = self.root / 'meeting' / 'rep.txt'
        repeated.write_text('00:01 참석자 1\n클로딕한(?) 말 그리고 클로딕한(?) 말 [불명확: 웅얼] 끝\n', encoding='utf-8')
        body1 = self.scratch / 'rep1.txt'
        code, log, _ = self.run_apply('--out-body', str(body1), src=repeated)
        self.assertEqual(0, code)
        markers = log['markers']
        self.assertEqual(['estimate', 'estimate', 'unclear'], [m['kind'] for m in markers])
        self.assertEqual(3, len({m['marker_id'] for m in markers}))
        decisions = [dict(marker_id=markers[0]['marker_id'], action='fix', text='클로딩한'),
                     dict(marker_id=markers[1]['marker_id'], action='approve'),
                     dict(marker_id=markers[2]['marker_id'], action='restore')]
        body2 = self.scratch / 'rep2.txt'
        code, log, _ = self.run_apply('--decisions', self.write_json('d.json', decisions), '--out-body', str(body2), src=body1)
        self.assertEqual(0, code, log['failures'])
        self.assertEqual('00:01 참석자 1\n클로딩한 말 그리고 클로딕한 말 웅얼 끝\n', body2.read_text(encoding='utf-8'))
        self.assertEqual({'estimate': 0, 'unclear': 0}, log['marker_counts'])
        self.assertEqual(3, len(log['decisions_applied']))
        for bad, kind in [([dict(marker_id='9:0:1:deadbeef', action='approve')], 'unknown_marker'),
                          ([dict(marker_id=markers[2]['marker_id'], action='approve')], 'invalid_action'),
                          ([dict(marker_id=markers[0]['marker_id'], action='hold')] * 2, 'duplicate_decision'),
                          ([dict(marker_id=markers[0]['marker_id'], action='fix', text=' ')], 'bad_decisions')]:
            code, log, _ = self.run_apply('--decisions', self.write_json('bad-d.json', bad), src=body1)
            self.assertEqual(2, code)
            self.assertEqual(kind, log['failures'][0]['kind'])

    def test_assemble_publishes_md_and_txt_exclusively_and_reports_partial(self):
        header = self.scratch / 'header.md'
        header.write_text('---\ntitle: t\n---\n# 머리\n', encoding='utf-8')
        memo = self.scratch / 'memo.md'
        memo.write_text('## 보정 메모\n메모\n', encoding='utf-8')
        out_md, out_txt = self.root / 'docs' / 'out.md', self.root / 'meeting' / '261014 회의 보정.txt'
        code, log, _ = self.run_apply('--assemble', f'{header},{memo}', '--write-md', str(out_md), '--write-txt', str(out_txt), '--expect-turns', '5')
        self.assertEqual(0, code, log['failures'])
        self.assertEqual(['created', 'created'], [o['status'] for o in log['outputs']])
        self.assertEqual(SAMPLE, out_txt.read_text(encoding='utf-8'))
        rendered = out_md.read_text(encoding='utf-8')
        self.assertTrue(rendered.startswith('---\ntitle: t\n---\n# 머리\n\n## 본문\n\n**00:19 참석자 1**\n'))
        self.assertIn('**01:00:11**\n빈 라벨 턴\n\n## 보정 메모\n메모\n', rendered)
        self.assertEqual(0o644 & ~os.umask(os.umask(0)), out_md.stat().st_mode & 0o777 & 0o644)
        code, log, _ = self.run_apply('--assemble', f'{header},{memo}', '--write-md', str(out_md), '--write-txt', str(self.root / 'meeting' / 'other.txt'))
        self.assertEqual(2, code)
        self.assertEqual([('exists', str(out_md)), ('created', str(self.root / 'meeting' / 'other.txt'))], [(o['status'], o['path']) for o in log['outputs']])
        self.assertEqual([{'kind': 'exists', 'path': str(out_md)}], log['failures'])
        self.assertIn('# 머리', out_md.read_text(encoding='utf-8'))
        code, log, _ = self.run_apply('--write-txt', str(out_txt), '--expect-turns', '4')
        self.assertEqual(2, code)
        self.assertEqual('turns_mismatch', log['failures'][0]['kind'])
        self.assertEqual([], log['outputs'])
        second_md = self.root / 'docs' / 'second.md'
        code, log, _ = self.run_apply('--assemble', f'{header},{memo}', '--write-md', str(second_md), '--write-txt', str(self.base / 'escape.txt'))
        self.assertEqual(2, code)
        self.assertEqual([('created', str(second_md))], [(o['status'], o['path']) for o in log['outputs']])
        self.assertEqual(['outside_root'], [f['kind'] for f in log['failures']])
        self.assertTrue(second_md.is_file())
        self.assertFalse((self.base / 'escape.txt').exists())
        self.assertEqual(64, len(log['body_sha256']))

    def test_publish_refuses_outside_root_and_source_overwrite(self):
        code, log, _ = self.run_apply('--write-txt', str(self.base / 'escape.txt'))
        self.assertEqual(2, code)
        self.assertEqual('outside_root', log['failures'][0]['kind'])
        code, log, _ = self.run_apply('--write-txt', str(self.src))
        self.assertEqual(2, code)
        self.assertEqual('same_as_source', log['failures'][0]['kind'])
        outside = self.base / 'outside'
        outside.mkdir()
        (self.root / 'link').symlink_to(outside, target_is_directory=True)
        code, log, _ = self.run_apply('--write-txt', str(self.root / 'link' / 'x.txt'))
        self.assertEqual(2, code)
        self.assertEqual('outside_root', log['failures'][0]['kind'])
        self.assertEqual([], list(outside.iterdir()))
        (self.root / 'inner-link').symlink_to(self.root / 'meeting', target_is_directory=True)
        code, log, _ = self.run_apply('--write-txt', str(self.root / 'inner-link' / 'y.txt'))
        self.assertEqual(2, code, 'symlinked parent is refused even when it resolves inside root')
        self.assertEqual('outside_root', log['failures'][0]['kind'])
        code, log, _ = self.run_apply('--write-txt', str(self.root / 'meeting' / '..' / '..' / 'z.txt'))
        self.assertEqual(2, code)
        self.assertEqual('outside_root', log['failures'][0]['kind'])

    def test_publish_pins_parent_directory_against_swap_after_check(self):
        parent = self.root / 'new-dir'
        parent.mkdir()
        outside = self.base / 'swap-target'
        outside.mkdir()
        moved = self.base / 'moved-away'
        original_open = os.open

        def swapping_open(path, flags, *args, **kwargs):
            # 부모 디렉터리를 fd 로 연 직후, 경로상의 부모를 외부 symlink 로 바꿔 끼운다. 이후 쓰기는 경로가 아닌 fd 를 따라야 한다.
            fd = original_open(path, flags, *args, **kwargs)
            if path == 'new-dir' and not parent.is_symlink():
                parent.rename(moved)
                parent.symlink_to(outside, target_is_directory=True)
            return fd

        with unittest.mock.patch.object(stt.os, 'open', swapping_open):
            result = stt.publish(str(self.root), str(self.src), str(parent / 'pinned.txt'), 'pinned\n')
        self.assertEqual('created', result['status'])
        self.assertEqual([], list(outside.iterdir()), 'nothing may land in the swapped-in symlink target')
        self.assertEqual('pinned\n', (moved / 'pinned.txt').read_text(encoding='utf-8'), 'the write followed the pinned directory fd')
        self.assertEqual(['pinned.txt'], [p.name for p in moved.iterdir()], 'no temp file left behind')

    def _swap_ancestor_fixture(self):
        temp = self.base
        moved, decoy = temp.with_name(temp.name + '-moved'), temp.with_name(temp.name + '-decoy')
        (decoy / 'vault' / 'meeting').mkdir(parents=True)

        def restore():
            if temp.is_symlink():
                temp.unlink()
                moved.rename(temp)
            shutil.rmtree(decoy, ignore_errors=True)

        def swap():
            temp.rename(moved)
            temp.symlink_to(decoy, target_is_directory=True)

        self.addCleanup(restore)
        return temp, moved, decoy, swap

    def test_publish_refuses_when_an_ancestor_of_root_is_already_a_symlink(self):
        temp, moved, decoy, swap = self._swap_ancestor_fixture()
        swap()  # publish 가 root 를 해석하기 전에 상위가 이미 바뀐 상황 — resolve() 를 썼다면 decoy 를 root 로 받아들인다
        with self.assertRaises(stt.Fail) as caught:
            stt.publish(str(self.root), str(moved / 'vault' / 'meeting' / '261014 회의.txt'),
                        str(self.root / 'meeting' / 'escape.txt'), 'escape\n')
        self.assertEqual('outside_root', caught.exception.record['kind'])
        self.assertEqual([], list((decoy / 'vault' / 'meeting').iterdir()), 'nothing may land behind the swapped ancestor')
        self.assertFalse((moved / 'vault' / 'meeting' / 'escape.txt').exists())

    def test_publish_refuses_when_an_ancestor_of_root_becomes_a_symlink_during_the_walk(self):
        temp, moved, decoy, swap = self._swap_ancestor_fixture()
        original_open, fired = os.open, []

        def swapping_open(path, flags, *args, **kwargs):
            # 체인 open 이 상위 디렉터리(임시 폴더) 구성 요소에 도달한 순간 그 경로를 decoy 로 가는 symlink 로 바꿔 끼운다.
            if path == temp.name and 'dir_fd' in kwargs and not temp.is_symlink():
                swap()
                fired.append(path)
            return original_open(path, flags, *args, **kwargs)

        with unittest.mock.patch.object(stt.os, 'open', swapping_open):
            with self.assertRaises(stt.Fail) as caught:
                stt.publish(str(self.root), str(moved / 'vault' / 'meeting' / '261014 회의.txt'),
                            str(self.root / 'meeting' / 'escape.txt'), 'escape\n')
        self.assertEqual([temp.name], fired, 'the swap must have happened inside the chain walk')
        self.assertEqual('outside_root', caught.exception.record['kind'])
        self.assertEqual([], list((decoy / 'vault' / 'meeting').iterdir()), 'nothing may land behind the swapped ancestor')
        self.assertFalse((moved / 'vault' / 'meeting' / 'escape.txt').exists())

    def test_publish_tolerates_concurrent_creation_of_a_new_parent_folder(self):
        original_mkdir = os.mkdir

        def racing_mkdir(path, *args, **kwargs):
            original_mkdir(path, *args, **kwargs)  # 다른 실행이 같은 폴더를 먼저 만든 상황을 재현한다
            return original_mkdir(path, *args, **kwargs)

        with unittest.mock.patch.object(stt.os, 'mkdir', racing_mkdir):
            result = stt.publish(str(self.root), str(self.src), str(self.root / 'fresh' / 'nested' / 'a.txt'), 'a\n')
        self.assertEqual('created', result['status'])
        self.assertEqual('a\n', (self.root / 'fresh' / 'nested' / 'a.txt').read_text(encoding='utf-8'))

    def test_multiple_estimates_in_one_word_get_distinct_markers(self):
        turns = stt.structure('00:01 A\n상준님(?)과상우님(?)이 왔다(?)(?) 끝\n')[1]
        markers = stt.extract_markers(turns)
        self.assertEqual(['상준님(?)', '과상우님(?)이', '왔다(?)', '(?)'], [m['phrase'] for m in markers])
        self.assertEqual(4, len({m['marker_id'] for m in markers}))
        stt.apply_decisions(turns, [(markers[0], 'approve', ''), (markers[3], 'approve', '')])
        self.assertEqual('상준님과상우님(?)이 왔다(?) 끝\n', stt.body_of(turns[0]))
        # 남은 (?) 가 어절에 하나뿐이면 다시 어절 전체가 한 마커가 된다
        self.assertEqual(['상준님과상우님(?)이', '왔다(?)'], [m['phrase'] for m in stt.extract_markers(turns)])

    def test_concurrent_publish_lets_exactly_one_writer_win(self):
        dst = self.root / 'meeting' / 'race.txt'
        jobs = [(str(self.root), str(self.src), str(dst), 'writer %d\n' % i) for i in range(6)]
        with multiprocessing.get_context('spawn').Pool(3) as pool:
            statuses = pool.map(_publish_worker, jobs)
        self.assertEqual(1, statuses.count('created'))
        self.assertEqual(5, statuses.count('exists'))
        self.assertRegex(dst.read_text(encoding='utf-8'), r'^writer \d\n$')
        self.assertEqual(['race.txt'], sorted(p.name for p in dst.parent.iterdir() if p.name.startswith('race') or p.name.startswith('.stt-fix-')))


if __name__ == '__main__':
    unittest.main()
