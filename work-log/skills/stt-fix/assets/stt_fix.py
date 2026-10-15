#!/usr/bin/env python3
"""STT 전사 보정 헬퍼 — 결정적 치환·마커 추출·결정 반영·조립·배타적 신규 생성 (stdlib only).

apply --root <vault root> --src <txt> [--rules <json> | --decisions <json>] --log <json>
      [--out-body <txt>] [--assemble <header.md>,<memo.md> --write-md <path>] [--write-txt <path>]
      [--expect-turns N]

--out-body/--log 는 스크래치 산출물이라 덮어쓴다. --write-md/--write-txt 는 vault 산출물이라
root 안의 새 파일만 배타적으로(os.link) 만들고, 이미 있으면 그 파일만 `exists` 로 보고한다.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

HEADER = re.compile(r'^(\d{1,2}:)?\d{2}:\d{2}(?: (.*))?$')
UNCLEAR = re.compile(r'\[불명확:\s*([^\]]*)\]')
ESTIMATE = '(?)'
ASCII_WORD = re.compile(r'^[A-Za-z0-9]+$')
ACTIONS = {'approve': 'estimate', 'restore': 'unclear', 'fix': None, 'hold': None}


class Fail(Exception):
    def __init__(self, kind, **detail):
        super().__init__(kind)
        self.record = dict(kind=kind, **detail)


# ──────────────────────────── 파싱 ────────────────────────────

def parse(text):
    """헤더 = 파일 시작 또는 빈 줄 직후의 타임스탬프 줄. 다음 헤더 전까지의 모든 줄이 턴 본문."""
    lines = text.split('\n')
    preamble, turns, previous_blank = [], [], True
    for line in lines:
        if previous_blank and HEADER.match(line):
            turns.append([line])
        elif turns:
            turns[-1].append(line)
        else:
            preamble.append(line)
        previous_blank = line.strip() == ''
    return preamble, turns


def header_parts(header):
    """(time, speaker). 헤더 없는 전사의 단일 턴은 header 가 None 이다."""
    if header is None:
        return '', ''
    match = HEADER.match(header)
    return header.split(' ', 1)[0], (match.group(2) or '') if match else ''


def header_format(turns):
    kinds = {'h:mm:ss' if turn[0].count(':') == 2 else 'mm:ss' for turn in turns}
    return kinds.pop() if len(kinds) == 1 else 'mixed'


def structure(text):
    """(preamble, turns, has_headers). 헤더가 하나도 없으면 전체를 헤더 None 인 단일 턴으로 다룬다."""
    preamble, turns = parse(text)
    if turns:
        return preamble, turns, True
    return [], [[None] + preamble], False


def render(preamble, turns):
    return '\n'.join(preamble + [line for turn in turns for line in turn if line is not None])


def body_of(turn):
    return '\n'.join(turn[1:])


def with_body(turn, body):
    return [turn[0]] + body.split('\n')


# ──────────────────────────── 규칙 치환 ────────────────────────────

def load_json(filename):
    if not filename or filename == '/dev/null':
        return None
    raw = Path(filename).read_text(encoding='utf-8').strip()
    return json.loads(raw) if raw else None


def load_rules(filename, turn_count):
    data = load_json(filename)
    data = {} if data is None else data
    if not isinstance(data, dict) or set(data) - {'global', 'turns'}:
        raise Fail('bad_rules', reason='rules 는 {"global": [[old,new]...], "turns": {"<서수>": [[old,new]...]}} 객체')
    global_items = data.get('global')
    turn_items = data.get('turns')
    global_items = [] if global_items is None else global_items
    turn_items = {} if turn_items is None else turn_items
    if not isinstance(turn_items, dict):
        raise Fail('bad_rules', reason='turns 는 {"<서수>": [[old,new]...]} 객체여야 함')

    def pairs(items, where):
        if not isinstance(items, list):
            raise Fail('bad_rules', reason=where + ' 은 배열이어야 함')
        result = []
        for item in items:
            if not (isinstance(item, list) and len(item) == 2 and all(isinstance(x, str) for x in item)) or item[0] == '':
                raise Fail('bad_rules', reason=where + ' 의 각 항목은 [old, new] 문자열 쌍이며 old 는 비어 있을 수 없음', item=item)
            result.append((unicodedata.normalize('NFC', item[0]), unicodedata.normalize('NFC', item[1])))
        return result

    scoped = {}
    for key, items in turn_items.items():
        if not re.fullmatch(r'\d+', str(key)) or int(key) >= turn_count:
            raise Fail('bad_rules', reason='turns 키는 0 이상 ' + str(turn_count - 1) + ' 이하의 턴 서수', key=key)
        scoped[int(key)] = pairs(items, 'turns[' + str(key) + ']')
    return pairs(global_items, 'global'), scoped


def compile_rules(candidates):
    """후보 old 를 길이 내림차순 alternation 으로 묶는다. ASCII 영숫자 old 는 단어 경계를 강제한다."""
    ordered = sorted(candidates, key=len, reverse=True)
    parts = []
    for old in ordered:
        escaped = re.escape(old)
        parts.append('(?<![A-Za-z0-9])' + escaped + '(?![A-Za-z0-9])' if ASCII_WORD.match(old) else escaped)
    return re.compile('|'.join(parts)) if parts else None


def apply_rules(turns, global_rules, scoped):
    hits = {('global', old): 0 for old, _ in global_rules}
    for index, rules in scoped.items():
        for old, _ in rules:
            hits[('turn', index, old)] = 0
    changes = []
    for index, turn in enumerate(turns):
        candidates = {old: ('global', new) for old, new in global_rules}
        for old, new in scoped.get(index, []):
            candidates[old] = ('turn', new)
        pattern = compile_rules(candidates)
        if not pattern:
            continue
        segments = []

        def replace(match):
            old = match.group(0)
            scope, new = candidates[old]
            hits[('global', old) if scope == 'global' else ('turn', index, old)] += 1
            segments.append([old, new])
            return new

        body = pattern.sub(replace, body_of(turn))
        if segments:
            time, speaker = header_parts(turn[0])
            changes.append(dict(turn=index, time=time, speaker=speaker, segments=segments))
            turns[index] = with_body(turn, body)
    failures = [dict(kind='scoped_mismatch', turn=key[1], old=key[2], hits=count)
                for key, count in hits.items() if key[0] == 'turn' and count != 1]
    unused = [key[1] for key, count in hits.items() if key[0] == 'global' and count == 0]
    return changes, hits, unused, failures


def rules_table(global_rules, scoped, hits, turns):
    rows = ['| 원문 | 보정 | 횟수 · 범위 |', '|------|------|------------|']
    for old, new in global_rules:
        if hits[('global', old)]:
            rows.append('| `' + old + '` | ' + new + ' | ' + str(hits[('global', old)]) + '회 |')
    for index in sorted(scoped):
        time = header_parts(turns[index][0])[0]
        for old, new in scoped[index]:
            rows.append('| `' + old + '` | ' + new + ' | ' + time + ' (턴 ' + str(index) + ') |')
    return '\n'.join(rows)


# ──────────────────────────── 마커 ────────────────────────────

def extract_markers(turns):
    markers = []
    for index, turn in enumerate(turns):
        body = body_of(turn)
        time, speaker = header_parts(turn[0])
        unclear = [(m.start(), m.end()) for m in UNCLEAR.finditer(body)]
        spans = [(start, end, 'unclear') for start, end in unclear]
        positions, position = [], body.find(ESTIMATE)
        while position != -1:
            if not any(start <= position < end for start, end in unclear):
                positions.append(position)
            position = body.find(ESTIMATE, position + len(ESTIMATE))
        last_end = 0
        for order, position in enumerate(positions):
            # (?) 어절 = 공백/줄바꿈 경계. 인접한 [불명확: …] 구간과 같은 어절의 앞 (?) 마커도 경계로 취급해
            # 마커 구간이 서로 겹치지 않고 각 구간에 (?) 가 정확히 하나만 들어가게 한다.
            start = max(body.rfind(' ', 0, position), body.rfind('\n', 0, position),
                        *[end - 1 for _, end in unclear if end <= position]) + 1
            start = max(start, last_end)
            after = position + len(ESTIMATE)
            end_candidates = [i for i in (body.find(' ', after), body.find('\n', after)) if i != -1]
            end_candidates += [s for s, _ in unclear if s >= after]
            end = min(end_candidates) if end_candidates else len(body)
            if order + 1 < len(positions) and positions[order + 1] < end:
                end = after  # 같은 어절에 (?) 가 더 있으면 이 마커는 자기 (?) 바로 뒤에서 끝난다
            last_end = end
            spans.append((start, end, 'estimate'))
        for start, end, kind in sorted(spans):
            phrase = body[start:end]
            line_start, line_end = body.rfind('\n', 0, start) + 1, body.find('\n', end)
            sentence = body[line_start:len(body) if line_end == -1 else line_end]
            if len(sentence) > 200:
                sentence = '…' + body[max(line_start, start - 80):min(len(body), end + 80)].strip() + '…'
            marker_id = ':'.join([str(index), str(start), str(end), hashlib.sha256(phrase.encode()).hexdigest()[:8]])
            markers.append(dict(marker_id=marker_id, turn=index, time=time, speaker=speaker, kind=kind,
                                phrase=phrase, sentence=sentence, start=start, end=end))
    return markers


def load_decisions(filename, markers):
    data = load_json(filename)
    if not isinstance(data, list):
        raise Fail('bad_decisions', reason='decisions 는 [{"marker_id","action","text"?}] 배열')
    by_id, seen, decisions = {m['marker_id']: m for m in markers}, set(), []
    for item in data:
        if not isinstance(item, dict) or item.get('action') not in ACTIONS or not isinstance(item.get('marker_id'), str):
            raise Fail('bad_decisions', reason='각 결정은 marker_id 와 action(approve|restore|fix|hold)을 가짐', item=item)
        marker = by_id.get(item['marker_id'])
        if marker is None:
            raise Fail('unknown_marker', marker_id=item['marker_id'])
        if item['marker_id'] in seen:
            raise Fail('duplicate_decision', marker_id=item['marker_id'])
        required_kind = ACTIONS[item['action']]
        if required_kind and marker['kind'] != required_kind:
            raise Fail('invalid_action', marker_id=item['marker_id'], action=item['action'], marker_kind=marker['kind'])
        if item['action'] == 'fix' and (not isinstance(item.get('text'), str) or not item['text'].strip()):
            raise Fail('bad_decisions', reason='fix 는 비어 있지 않은 text 가 필요', marker_id=item['marker_id'])
        seen.add(item['marker_id'])
        decisions.append((marker, item['action'], unicodedata.normalize('NFC', item.get('text') or '')))
    return decisions


def apply_decisions(turns, decisions):
    applied = []
    ordered = sorted(decisions, key=lambda d: (d[0]['turn'], d[0]['start']))
    for previous, current in zip(ordered, ordered[1:]):
        if previous[0]['turn'] == current[0]['turn'] and current[0]['start'] < previous[0]['end']:
            raise Fail('overlapping_markers', marker_ids=[previous[0]['marker_id'], current[0]['marker_id']])
    for marker, action, text in sorted(decisions, key=lambda d: (d[0]['turn'], -d[0]['start'])):
        turn = turns[marker['turn']]
        body = body_of(turn)
        phrase = body[marker['start']:marker['end']]
        if phrase != marker['phrase']:
            raise Fail('phrase_mismatch', marker_id=marker['marker_id'], expected=marker['phrase'], actual=phrase)
        if action == 'approve':
            new = phrase.replace(ESTIMATE, '')
        elif action == 'restore':
            new = UNCLEAR.sub(lambda m: m.group(1), phrase)
        elif action == 'fix':
            new = text
        else:
            new = phrase
        if new != phrase:
            turns[marker['turn']] = with_body(turn, body[:marker['start']] + new + body[marker['end']:])
        applied.append(dict(marker_id=marker['marker_id'], action=action, turn=marker['turn'], time=marker['time'],
                            before=phrase, after=new))
    return applied


# ──────────────────────────── 생성 ────────────────────────────

def markdown_body(preamble, turns):
    parts = [line.rstrip() for line in preamble]
    for turn in turns:
        if turn[0] is not None:
            parts.append('**' + turn[0].rstrip() + '**')
        parts.extend(line.rstrip() for line in turn[1:])
    return '\n'.join(parts).strip('\n') + '\n'


DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0)


def open_directory_chain(fixed, creatable):
    """'/' 에서 시작해 구성 요소를 심볼릭 링크를 따라가지 않고 한 단계씩 연 디렉터리 fd 를 돌려준다.

    fixed(root 까지)는 있어야 하고, creatable(root 아래 상대 경로)은 없으면 만든다. 어느 단계든 심볼릭 링크·
    비디렉터리면 OSError(ELOOP·ENOTDIR)가 난다. 호출자가 fd 를 닫는다.
    """
    fd = os.open('/', DIR_FLAGS)
    try:
        for part, create in [(p, False) for p in fixed] + [(p, True) for p in creatable]:
            try:
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o777, dir_fd=fd)
                except FileExistsError:
                    pass  # 다른 실행이 먼저 만들었다 — 다시 열어 디렉터리인지 확인한다
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        result, fd = fd, None
        return result
    finally:
        if fd is not None:
            os.close(fd)


def publish(root, source, destination, content):
    """root 안의 새 파일만 만든다.

    root 는 호출자가 확정한 canonical 절대경로다. 여기서 다시 resolve() 하지 않고(해석 시점에 상위가 바뀌면
    외부 경로를 root 로 받아들이게 된다) '/' 부터 대상 부모 디렉터리까지 모든 구성 요소를 심볼릭 링크를
    따라가지 않고 한 단계씩 열어 부모를 fd 로 고정한 뒤, 그 fd 기준으로 임시 파일 생성·os.link 게시·정리를
    수행한다. 경로 어딘가가 링크로 바뀌어 있으면 실패하고, 같은 대상에 대한 경쟁 생성은 하나만 성공한다.
    """
    root_abs, dst = Path(os.path.abspath(root)), Path(os.path.abspath(destination))
    try:
        relative = dst.parent.relative_to(root_abs)
    except ValueError:
        raise Fail('outside_root', path=str(dst))
    if any(part in ('', '.', '..') for part in relative.parts):
        raise Fail('outside_root', path=str(dst))
    mask = os.umask(0)
    os.umask(mask)
    try:
        fd = open_directory_chain(root_abs.parts[1:], relative.parts)
    except OSError as exc:  # ELOOP(심볼릭 링크)·ENOTDIR·ENOENT — root 상위를 포함해 어떤 구성 요소도 링크면 거부한다
        raise Fail('outside_root', path=str(dst),
                   reason=(exc.strerror or type(exc).__name__) + ' — root 경로에 심볼릭 링크가 있으면 canonical(realpath) 경로를 --root 로 넘긴다')
    try:
        try:
            existing = os.stat(dst.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and os.path.samestat(existing, os.stat(source)):
            raise Fail('same_as_source', path=str(dst))
        if existing is not None:
            return dict(path=str(dst), status='exists')
        data = content.encode('utf-8')
        temp = '.stt-fix-' + os.urandom(6).hex()
        temp_fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o666 & ~mask, dir_fd=fd)
        try:
            with os.fdopen(temp_fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, dst.name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            except FileExistsError:
                return dict(path=str(dst), status='exists')
            return dict(path=str(dst), status='created', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        finally:
            os.unlink(temp, dir_fd=fd)
    finally:
        os.close(fd)


# ──────────────────────────── 진입점 ────────────────────────────

def run(args):
    raw = Path(args.src).read_bytes()
    text = unicodedata.normalize('NFC', raw.decode('utf-8')).replace('\r\n', '\n')
    preamble, turns, has_headers = structure(text)
    original_headers = [turn[0] for turn in turns]
    times = [header_parts(h)[0] for h in original_headers] if has_headers else []
    log = dict(status='OK', source=str(args.src), source_sha256=hashlib.sha256(raw).hexdigest(), turns=len(turns),
               header_format=header_format(turns) if has_headers else 'format_unknown',
               duplicate_times=sorted({t for t in times if times.count(t) > 1}),
               preamble='\n'.join(preamble).strip(), failures=[], outputs=[], changes=[], unused_rules=[])
    if args.rules and args.decisions:
        raise Fail('bad_args', reason='--rules 와 --decisions 는 동시에 쓸 수 없음')

    if args.decisions:
        decisions = load_decisions(args.decisions, extract_markers(turns))
        log['decisions_applied'] = apply_decisions(turns, decisions)
    else:
        global_rules, scoped = load_rules(args.rules, len(turns))
        changes, hits, unused, failures = apply_rules(turns, global_rules, scoped)
        log.update(changes=changes, unused_rules=unused, rules_table_md=rules_table(global_rules, scoped, hits, turns),
                   rule_hits={('global:' if k[0] == 'global' else 'turn' + str(k[1]) + ':') + k[-1]: v for k, v in hits.items()})
        log['failures'].extend(failures)

    body = render(preamble, turns)
    check_turns = structure(body)[1]
    if len(check_turns) != len(turns) or [t[0] for t in check_turns] != original_headers:
        log['failures'].append(dict(kind='structure_changed', turns_before=len(turns), turns_after=len(check_turns)))
    if args.expect_turns is not None and len(check_turns) != args.expect_turns:
        log['failures'].append(dict(kind='turns_mismatch', expected=args.expect_turns, actual=len(check_turns)))
    log['markers'] = extract_markers(turns)
    log['marker_counts'] = dict(estimate=sum(m['kind'] == 'estimate' for m in log['markers']),
                                unclear=sum(m['kind'] == 'unclear' for m in log['markers']))
    log['body_sha256'] = hashlib.sha256(body.encode('utf-8')).hexdigest()

    if not log['failures']:
        if args.out_body:
            Path(args.out_body).write_text(body, encoding='utf-8')
        if args.write_md and (not args.assemble or len(args.assemble.split(',')) != 2):
            raise Fail('bad_args', reason='--write-md 는 --assemble <header.md>,<memo.md> 가 필요')
        targets = []
        if args.write_md:
            header, memo = (Path(p).read_text(encoding='utf-8') for p in args.assemble.split(','))
            targets.append((args.write_md, header.rstrip('\n') + '\n\n## 본문\n\n' + markdown_body(preamble, turns) + '\n' + memo.lstrip('\n')))
        if args.write_txt:
            targets.append((args.write_txt, body))
        # 출력은 파일별로 독립 처리한다: 하나가 실패해도 앞서 생성된 파일은 outputs 에 남는다 (부분 성공 보존).
        for destination, content in targets:
            try:
                output = publish(args.root, args.src, destination, content)
            except Fail as exc:
                log['failures'].append(exc.record)
                continue
            except OSError as exc:
                log['failures'].append(dict(kind='io_error', path=str(destination), reason=str(exc)))
                continue
            log['outputs'].append(output)
            if output['status'] == 'exists':  # 이미 있는 대상은 건너뛰되 성공으로 보고하지 않는다
                log['failures'].append(dict(kind='exists', path=output['path']))
    log['status'] = 'FAIL' if log['failures'] else 'OK'
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    apply = sub.add_parser('apply')
    apply.add_argument('--root', required=True, help='vault root — --write-md/--write-txt 는 이 안의 새 파일만 생성')
    apply.add_argument('--src', required=True)
    apply.add_argument('--rules', help='치환 규칙 JSON. /dev/null 또는 생략 = 빈 규칙')
    apply.add_argument('--decisions', help='마커 결정 JSON (--rules 와 배타)')
    apply.add_argument('--log', required=True)
    apply.add_argument('--out-body')
    apply.add_argument('--assemble', help='<header.md>,<memo.md>')
    apply.add_argument('--write-md')
    apply.add_argument('--write-txt')
    apply.add_argument('--expect-turns', type=int)
    args = parser.parse_args(argv)
    try:
        log = run(args)
    except Fail as exc:
        log = dict(status='FAIL', failures=[exc.record], outputs=[])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log = dict(status='FAIL', failures=[dict(kind='io_error', reason=str(exc))], outputs=[])
    except Exception as exc:  # 어떤 경로로도 로그 없이 끝나지 않는다 (fail-closed + 진단 가능)
        log = dict(status='FAIL', failures=[dict(kind='internal_error', reason=type(exc).__name__ + ': ' + str(exc))], outputs=[])
    Path(args.log).write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding='utf-8')
    summary = {k: log.get(k) for k in ('status', 'turns', 'header_format', 'marker_counts', 'unused_rules', 'failures', 'outputs')}
    print(json.dumps(dict(summary, log=str(args.log)), ensure_ascii=False))
    return 0 if log['status'] == 'OK' else 2


if __name__ == '__main__':
    sys.exit(main())
