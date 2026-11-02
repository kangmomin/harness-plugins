#!/usr/bin/env python3
r"""test_failures.py — 테스트 러너 출력 → 실패 레코드 / 회귀 baseline 행 / baseline 대조 분류 (stdlib only).

계약 (canonical — tdd.md·quality-loop.md는 호출법만 둔다):
  사용법: test_failures.py --runner {go|jest|vitest|playwright|auto} --exit-code N [--suite NAME] [--command TEXT]
          [--emit-baseline] [--baseline STATE_FILE] [--expect FILE [--partial]] [--rerun FILE2 --rerun-exit-code M] [FILE|-]
  종료:   결과를 출력하면(unparsed 포함 — 정상 데이터) exit 0. 입력 파일 부재·인자 오류·expect 파일 형식 오류 등 호출 자체 실패만 exit 2.
  지원 러너: go · jest · vitest · playwright(list·json 리포터). 그 외/판별 실패 → 전부 `unparsed`.
  stdout·stderr는 UTF-8로 쓰고 stdin은 UTF-8(replace)로 읽는다(Windows cp949 콘솔 대비).

완주 판정 매트릭스 (러너별 종료 마커 = go `ok|FAIL <pkg>` 요약 줄 또는 단독 PASS/FAIL, jest `Tests:`, vitest `Test Files`,
  playwright list 요약 `N passed|failed|flaky|skipped` 줄 · json `stats`):
  마커 있음 → 완주 Y (exit ≠ 0은 "실패 있음"으로만 해석) / 마커 없음 → 완주 N / 마커 ∧ 실패 0 ∧ exit ≠ 0 → Y + unparsed 1건(실패 없는 비정상 종료)
  / 테스트 0건 → Y + unparsed(테스트 0건). go `[build failed]` → 완주 N(build failed).
  playwright `interrupted`·`did not run`·관측 testcase 수 ≠ 요약 합 → 완주 N, `error(s) … not a part of any test`·json 최상위 errors → unparsed.
식별자: go `{package}::TestX/sub`, jest·vitest `{runner}::{file}::{describe › it}`,
  playwright `playwright::{file}::[{project}] › {describe › title}`(project 없으면 접두 생략, 라인·컬럼 제외. list는 cwd 기준 경로·
  출력 제목(태그 포함) 그대로, json은 rootDir 기준 경로·spec 제목 — 같은 리포터·같은 cwd로 수집한 결과끼리만 대조). 키 = suite + 식별자.
정규화 시그니처: Go는 실패 메시지 첫 줄에서 경로·라인 번호·타임스탬프·메모리 주소(0x…)·goroutine id·소요 시간을 제거하고 공백 축약.
  JS는 JSON failureMessages 또는 텍스트 오류 본문(코드 프레임·stack 제외)의 matcher/Expected/Received/diff 전체를 보존한다.
  playwright는 실패 attempt의 모든 오류를 오류별로 정규화(코드 프레임·stack·`Error Context:`·`Call log:` 제거)해 중복 없이 ` | `로 결합한다.
  메시지 없는 오류(본문이 비었거나 오류 이름만)는 `{이름} at {심볼} ({파일})` — 첫 stack frame, cwd 안 경로는 cwd 상대, 라인·컬럼 제외.
  비교 키 = 정규화된 전체 메시지, 표시 = 120자 + #해시 8자. JSON reporter는 runner를 명시하고 동일 저장소 루트 cwd에서 수집한다.
baseline 셀 문법: 항목 `{ID}` :: `{sig}` (백틱), 항목 구분은 닫는 백틱과 여는 백틱 사이의 ` / ` 만 (regex (?<=`) / (?=`)),
  내부 백틱 → `'`, `|` → `\|`. 파싱 실패·개수 불일치·Tombstone 중복 매핑 → 해당 suite 행 전체 unparsed.
  baseline 진단(완주 N·목록 없음·셀 파싱 실패·수집 실패 행)은 그 suite의 판정에만 붙는다.
대조 우선순위: Tombstone 매핑(분류 전) → `--expect`(red → new_red, pass → regression) → `## TDD Test Map`(+ `## TDD Test Map ID 대응`) 등재 → new_red
  / baseline 동일 키+동일 sig → pre_existing / 다른 sig → regression / 부재 → regression. 모순·중복 → unparsed.
  baseline `수집 실패` 기록 → Test Map 외 전부 unparsed(baseline 없음). playwright 러너 재시도 통과(마지막 attempt passed ∧ expectedStatus passed)
  → flaky(분류·rerun이 덮어쓰지 않고, --emit-baseline 실패 목록에서 제외).
관측 상태: ID별 관측 목록(pass·fail·skip·expected_fail·interrupted). 요약 통과 수 > 0인데 PASS 관측 0 → 진단 pass_observation_unavailable.
--expect FILE: 한 줄 `red {ID}` 또는 `pass {ID}`(빈 줄·`#` 주석 허용, 형식 오류·중복·상충 → exit 2, --baseline 필수).
  평가 = 분류 → rerun → 기대 대조. pass 기대 충족 = 관측 PASS 1회 또는 재실행 FLAKY, red 기대 충족 = 관측 FAIL·PASS 1회(조기 Green 허용)·FLAKY.
  미관측·중복·SKIP·혼재·EXPECTED_FAIL·pass 기대 FAIL → 불충족 → PASS 판정 불가.
  같은 호출에서 baseline 실패 미확인(해당 suite baseline 실패 ID 중 Tombstone 승인 삭제가 아니고, 이름 변경이면 새 ID로 본 관측이
  FAIL 1회·PASS 1회·FLAKY가 아닌 ID)도 계산해 ≥ 1이면 PASS 판정 불가. --partial(부분 실행)은 두 검사를 판정에 쓰지 않고 표만 출력한다.
rerun: verbose 출력 필수. flaky ⇔ 재실행 완주 ∧ 그 식별자가 PASS로 정확히 1회 관측(go `--- PASS: {ID}`, jest/vitest 동일 runner+파일+전체 이름 `✓ {ID}`;
  leaf/suffix 추정 금지, 중복·SKIP 혼재는 증거 아님). 그 외 → 원 분류 + rerun_incomplete.
"""
import argparse
import hashlib
import json
import os
import re
import sys

ITEM_SPLIT = re.compile(r"(?<=`) / (?=`)")
ITEM_RE = re.compile(r"^`(.*)` :: `(.*)`$", re.S)
# Go 1.22+ `-cover`: 테스트 파일이 없는 패키지는 `? pkg [no test files]` 대신 `\tpkg\t\tcoverage: 0.0% of statements` 한 줄만 낸다.
GO_NO_TEST_COVERAGE = re.compile(r"^\s+(\S+)\s+coverage: \d+(?:\.\d+)?% of statements\s*$")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
NAME_ONLY = re.compile(r"^[\w.$]*(?:Error|Exception)\w*:?$")
# 같은 실패 블록 안의 첫 stack frame: vitest `❯ [심볼] file:line:col`, V8 `at [심볼 (]file:line:col[)]`.
FRAME_VITEST = re.compile(r"^\s*❯\s+(?:(?P<sym>\S+)\s+)?(?P<file>[^\s:]+):\d+:\d+\s*$")
FRAME_AT = re.compile(r"\bat (?:(?P<sym>[^\s()'\"]+(?: \[as [^\]]+\])?) \()?(?P<file>(?:file://)?[^\s()'\"]+?):\d+(?::\d+)?\)?")
TEST_BOUNDARY = re.compile(r"^\s*(?:●\s|FAIL\s|PASS\s|Test Suites:|Tests:|Test Files|⎯)")


def normalize(msg):
    s = msg.strip()
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", "<ts>", s)
    s = re.sub(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b", "<ts>", s)
    s = re.sub(r"0x[0-9a-fA-F]+", "<addr>", s)
    s = re.sub(r"goroutine \d+", "goroutine <n>", s)
    s = re.sub(r"\(\d+(?:\.\d+)?\s*m?s\)", "", s)
    s = re.sub(r"(?:[A-Za-z]:)?(?:[\w.\-]+[/\\])+[\w.\-]+(?::\d+){0,2}", "<path>", s)
    s = re.sub(r"\b[\w\-]+\.(?:go|ts|tsx|js|jsx|mjs|cjs|py)(?::\d+){0,2}\b", "<path>", s)
    s = re.sub(r":\d+\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def display(sig):
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:8]
    return (sig[:120] + ("…" if len(sig) > 120 else "")) + " #" + h


def cell_escape(s):
    return s.replace("`", "'").replace("|", "\\|")


def cell_unescape(s):
    return s.replace("\\|", "|")


def detect_runner(lines):
    txt = "\n".join(lines)
    if re.search(r"^\s*Test Files\s+", txt, re.M):
        return "vitest"
    if re.search(r"^Tests:\s+", txt, re.M) or re.search(r"^Test Suites:\s+", txt, re.M):
        return "jest"
    try:
        value = json.loads(txt)
    except (ValueError, TypeError):
        value = None
    if isinstance(value, dict) and isinstance(value.get("suites"), list) and "config" in value:
        return "playwright"
    if re.search(r"^Running \d+ tests? using \d+ workers?", txt, re.M) and (
            re.search(r"^  \d+ (?:passed|failed|flaky|skipped|interrupted|did not run)\b", txt, re.M) or re.search(PW_ROW.pattern, txt, re.M)):
        return "playwright"
    if re.search(r"^(?:=== RUN|--- (?:FAIL|PASS)|ok\s+\S+|FAIL\s+\S+|PASS$|FAIL$)", txt, re.M):
        return "go"
    return "unknown"


def parse_go_package(lines):
    failed = []
    passed_ids = set()
    notes = []
    marker = False
    build_failed = False
    current = None
    messages = {}
    result_context = []
    for ln in lines:
        if re.match(r"^(ok|FAIL|PASS)(\s|$)", ln) or re.match(r"^\?\s+\S+\s+\[no test files\]", ln):
            marker = True
            current = None
            result_context.clear()
            if "[build failed]" in ln or "[setup failed]" in ln:
                build_failed = True
        m = re.match(r"^=== (RUN|CONT|NAME|PAUSE)\s+(\S+)", ln)
        if m:
            current = None if m.group(1) == "PAUSE" else m.group(2)
            result_context.clear()
            continue
        m = re.match(r"^\s*--- (FAIL|PASS|SKIP): (\S+)", ln)
        if m:
            verdict, tid = m.groups()
            indent = len(ln) - len(ln.lstrip())
            while result_context and result_context[-1][0] >= indent:
                result_context.pop()
            if verdict == "PASS":
                passed_ids.add(tid)
            if verdict == "FAIL":
                failed.append(tid)
                result_context.append((indent, tid))
            # nonverbose 로그는 FAIL 헤더 뒤에 오류를 출력한다.
            current = tid if verdict == "FAIL" else None
            continue
        if re.match(r"^\s*[\w\-]+\.go:\d+:", ln) or ln.lstrip().startswith("panic:"):
            if result_context and not ln.lstrip().startswith("panic:"):
                # nonverbose 부모 로그는 자식 결과 뒤에도 나온다. dedent로 부모 문맥을 복원한다.
                indent = len(ln) - len(ln.lstrip())
                while result_context and result_context[-1][0] >= indent:
                    result_context.pop()
                current = result_context[-1][1] if result_context else None
            if current:
                messages.setdefault(current, ln.strip())
    # 자체 오류가 없는 컨테이너 부모만 제거한다. 부모의 직접 실패는 보존한다.
    child_parents = set()
    for tid in failed:
        parts = tid.split("/")
        for k in range(1, len(parts)):
            child_parents.add("/".join(parts[:k]))
    failed = [(tid, messages.get(tid, "(실패 메시지 없음)")) for tid in failed
              if tid not in child_parents or tid in messages]
    notes.extend("%s: 실패 메시지 식별 불가" % tid for tid, msg in failed if msg == "(실패 메시지 없음)")
    passed = len([p for p in passed_ids if "/" not in p]) if (passed_ids or failed) else None
    total_leaf = passed + len(failed) if passed is not None else None
    if build_failed:
        return dict(completed=False, reason="build failed", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)
    if not marker:
        return dict(completed=False, reason="종료 마커 없음(중단·크래시·설정 오류)", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)
    return dict(completed=True, reason="", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)


def parse_go(lines):
    # go test의 텍스트 출력은 package 요약 줄에서 한 블록이 끝난다.
    packages = []
    pending = []
    for ln in lines:
        m = GO_NO_TEST_COVERAGE.match(ln)
        if m:
            # 요약 줄이 없는 테스트 0건 패키지 — 진행 중인 블록(pending)은 건드리지 않고 직접 등록한다.
            packages.append((m.group(1), dict(completed=True, reason="", passed=0, failed=[], total=0, notes=[], passed_ids=set())))
            continue
        pending.append(ln)
        m = re.match(r"^(?:ok|FAIL|\?)\s+(\S+)(?:\s|$)", ln)
        if m:
            result = parse_go_package(pending)
            if ln.startswith("FAIL") and not result["failed"]:
                result["notes"].append("%s: package 실패에 테스트 실패 식별자 없음" % m.group(1))
            packages.append((m.group(1), result))
            pending = []
    if any(ln.strip() not in ("", "FAIL", "PASS") for ln in pending) or not packages:
        p = parse_go_package(pending)
        p["notes"].append("Go package 요약 없음 — 식별자 대조 불가")
        p["completed"] = False
        packages.append((None, p))
    failed, passed_ids, notes = [], set(), []
    for pkg, p in packages:
        qualify = lambda tid: "%s::%s" % (pkg, tid) if pkg else tid
        failed.extend((qualify(tid), msg) for tid, msg in p["failed"])
        passed_ids.update(qualify(tid) for tid in p["passed_ids"])
        notes.extend(p["notes"])
    completed = all(p["completed"] for _, p in packages)
    passed = sum(p["passed"] for _, p in packages) if all(p["passed"] is not None for _, p in packages) else None
    total = sum(p["total"] for _, p in packages) if all(p["total"] is not None for _, p in packages) else None
    return dict(completed=completed, reason="" if completed else "package 실행 미완료",
                passed=passed, failed=failed, total=total, notes=notes, passed_ids=passed_ids)


def js_id(runner, filename, title):
    filename = filename.replace("\\", "/")
    if os.path.isabs(filename):
        filename = os.path.relpath(filename).replace("\\", "/")
    while filename.startswith("./"):
        filename = filename[2:]
    return "%s::%s::%s" % (runner, filename, title.replace(" > ", " › "))


def frame_file(path):
    path = path[len("file://"):] if path.startswith("file://") else path
    path = path.replace("\\", "/")
    if os.path.isabs(path):
        cwd = os.getcwd().replace("\\", "/").rstrip("/") + "/"
        if path.startswith(cwd):
            path = path[len(cwd):]
    return path


def messageless_signature(text, lines):
    """본문이 비었거나 오류 이름만이면 이름 + 첫 stack frame. frame이 없으면 None."""
    name = None
    m = re.search(r"^\s*name: '([\w.$]+)'", text, re.M)  # vitest 오류 객체 덤프
    if m:
        name = m.group(1)
    elif NAME_ONLY.match(text):
        name = text.rstrip(":")
    for line in lines:
        line = ANSI.sub("", line)
        fm = FRAME_VITEST.match(line)
        if fm:
            break
    else:
        fm = None
        for line in lines:
            fm = FRAME_AT.search(ANSI.sub("", line))
            if fm:
                break
    if not fm:
        return None
    where = frame_file(fm.group("file"))
    sym = fm.group("sym")
    return "%s at %s" % (name or "Error", ("%s (%s)" % (sym, where)) if sym else where)


def is_messageless(text):
    return not text or bool(NAME_ONLY.match(text)) or (
        text.startswith("{") and re.search(r"^\s*message: ''", text, re.M) is not None
        and re.search(r"^\s*stack: '", text, re.M) is not None)


def error_body(lines):
    # Error values/diffs are semantic. Strip source frames and stack locations only.
    body = []
    for line in lines:
        line = ANSI.sub("", line)
        if re.match(r"^\s*(?:[>❯]?\s*\d+\s*\||\||at |❯|●|FAIL |PASS |Test Suites:|Tests:|Test Files|⎯)", line):
            break
        if line.strip():
            body.append(line.strip())
    text = "\n".join(body)
    if is_messageless(text):
        block = []
        for line in lines:
            if block and TEST_BOUNDARY.match(ANSI.sub("", line)):
                break
            block.append(line)
        return messageless_signature(text, block) or "(실패 메시지 없음)"
    return text


def parse_js_json(lines, runner):
    try:
        value = json.loads("\n".join(lines))
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("testResults"), list):
        return None
    failed, passed_ids, notes, observed = [], set(), [], 0
    pass_list, skip_list = [], []
    for suite in value["testResults"]:
        if not isinstance(suite, dict) or not isinstance(suite.get("name"), str) or not isinstance(suite.get("assertionResults"), list):
            notes.append("JSON suite schema 식별 불가")
            continue
        failed_before = len(failed)
        for case in suite["assertionResults"]:
            if not isinstance(case, dict) or not isinstance(case.get("title"), str) or not isinstance(case.get("ancestorTitles"), list) or not all(isinstance(t, str) for t in case["ancestorTitles"]):
                notes.append("JSON assertion identity 식별 불가")
                continue
            observed += 1
            tid = js_id(runner, suite["name"], " › ".join(case["ancestorTitles"] + [case["title"]]))
            status = case.get("status")
            if status == "passed":
                passed_ids.add(tid)
                pass_list.append(tid)
            elif status == "failed":
                messages = case.get("failureMessages", [])
                if not isinstance(messages, list) or not all(isinstance(m, str) for m in messages):
                    messages = []
                failed.append((tid, "\n".join(error_body(m.splitlines()) for m in messages) or "(실패 메시지 없음)"))
            elif status in ("pending", "todo", "skipped", "disabled"):
                skip_list.append(tid)
            else:
                notes.append(tid + ": unknown assertion status")
        if suite.get("status") == "failed" and failed_before == len(failed):
            notes.append(suite["name"] + ": suite 실패에 assertion 증거 없음")
    total = value.get("numTotalTests")
    completed = isinstance(total, int) and not isinstance(total, bool) and total == observed and not value.get("wasInterrupted", False)
    if not completed:
        notes.append("JSON 실행 미완주/테스트 수 불일치")
    return dict(completed=completed, reason="" if completed else "JSON 실행 미완료", passed=len(passed_ids),
                failed=failed, total=total, notes=notes, passed_ids=passed_ids, expected_failed=value.get("numFailedTests"),
                pass_list=pass_list, skip_list=skip_list)


def parse_jest(lines):
    structured = parse_js_json(lines, "jest")
    if structured is not None:
        return structured
    failed, passed_ids, notes = [], set(), []
    pass_list, skip_list = [], []
    completed, passed, total, expected_failed = False, None, None, None
    filename, headings, details = None, [], False
    for i, ln in enumerate(lines):
        m = re.match(r"^(?:FAIL|PASS)\s+(.+?\.(?:[cm]?[jt]sx?))(?:\s+\(.*\))?\s*$", ln)
        if m:
            filename, headings, details = m.group(1), [], False
            continue
        m = re.match(r"^\s*●\s+(.+?)\s*$", ln)
        if m:
            details = True
            title = m.group(1)
            if title.startswith("Test suite failed to run"):
                notes.append(title + " — " + error_body(lines[i + 1:]))
            elif title.endswith("Console") or title.startswith("Cannot log after"):
                continue
            elif filename:
                failed.append((js_id("jest", filename, title), error_body(lines[i + 1:])))
            else:
                notes.append(title + ": Jest file identity 없음")
            continue
        m = re.match(r"^(\s*)[✓✔✕×○✎]\s+(.+?)(?:\s+\(\d+(?:\.\d+)?\s*m?s\))?\s*$", ln)
        if m and not details:
            indent = len(m.group(1))
            while headings and headings[-1][0] >= indent:
                headings.pop()
            mark = ln.lstrip()[0]
            if mark in "✓✔" and filename:
                tid = js_id("jest", filename, " › ".join([h[1] for h in headings] + [m.group(2)]))
                passed_ids.add(tid)
                pass_list.append(tid)
            elif mark in "○✎" and filename:
                title = re.sub(r"^(?:skipped|todo) ", "", m.group(2))
                skip_list.append(js_id("jest", filename, " › ".join([h[1] for h in headings] + [title])))
            continue
        if filename and not details and ln.strip() and ln.startswith("  "):
            indent = len(ln) - len(ln.lstrip())
            while headings and headings[-1][0] >= indent:
                headings.pop()
            headings.append((indent, ln.strip()))
        m = re.match(r"^Tests:\s+(.*)$", ln)
        if m:
            completed = True
            mp, mt = re.search(r"(\d+) passed", m.group(1)), re.search(r"(\d+) total", m.group(1))
            passed, total = int(mp.group(1)) if mp else 0, int(mt.group(1)) if mt else None
            mf = re.search(r"(\d+) failed", m.group(1))
            expected_failed = int(mf.group(1)) if mf else 0
    reason = "" if completed else "종료 마커(Tests:) 없음"
    return dict(completed=completed, reason=reason, passed=passed, failed=failed, total=total, notes=notes, passed_ids=passed_ids,
                expected_failed=expected_failed, pass_list=pass_list, skip_list=skip_list)


def parse_vitest(lines):
    structured = parse_js_json(lines, "vitest")
    if structured is not None:
        return structured
    failed, passed_ids, notes, messages = [], set(), [], {}
    pass_list, skip_list = [], []
    completed, passed, total, expected_failed = False, None, None, None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*FAIL\s+(.+?)\s+>\s+(.+?)\s*$", ln)
        if m:
            tid = js_id("vitest", *m.groups())
            if tid in messages:
                notes.append(tid + ": duplicate failure identity")
            messages[tid] = error_body(lines[i + 1:])
            continue
        m = re.match(r"^\s*([×✗✓✔↓])\s+(.+?)\s+>\s+(.+?)(?:\s+\d+(?:\.\d+)?\s*m?s)?\s*$", ln)
        if m:
            verdict, filename, title = m.groups()
            tid = js_id("vitest", filename, title)
            if verdict in "✓✔":
                passed_ids.add(tid)
                pass_list.append(tid)
            elif verdict == "↓":
                skip_list.append(tid)
            else:
                failed.append(tid)
        if re.match(r"^\s*Test Files\s+", ln):
            completed = True
        m = re.match(r"^\s*Tests\s+(.*)$", ln)
        if m:
            mp, mt = re.search(r"(\d+) passed", m.group(1)), re.search(r"\((\d+)\)", m.group(1))
            passed, total = int(mp.group(1)) if mp else 0, int(mt.group(1)) if mt else None
            mf = re.search(r"(\d+) failed", m.group(1))
            expected_failed = int(mf.group(1)) if mf else 0
    # Some reporters omit verbose rows. Exact FAIL headers still identify failures.
    ids = list(dict.fromkeys(failed + list(messages)))
    if len(failed) != len(set(failed)):
        notes.append("duplicate verbose failure identity")
    out = [(tid, messages.get(tid, "(실패 메시지 없음)")) for tid in ids]
    reason = "" if completed else "종료 마커(Test Files) 없음"
    return dict(completed=completed, reason=reason, passed=passed, failed=out, total=total, notes=notes, passed_ids=passed_ids,
                expected_failed=expected_failed, pass_list=pass_list, skip_list=skip_list)


PW_ROW = re.compile(r"^  (✓|✘|ok|x|-)\s+(\d+) (.+?)\s*$")
PW_COUNT = re.compile(r"^  (\d+) (failed|interrupted|flaky|skipped|did not run|passed)(?: \(.*\))?\s*$")
PW_FATAL = re.compile(r"^  (?:1 error was|\d+ errors were) not a part of any test")
PW_DETAIL = re.compile(r"^  (\d+)\) (.+?)(?: ─+)?\s*$")
PW_SUMMARY_ITEM = re.compile(r"^    (\S.*?)(?: ─+)?\s*$")
PW_RETRY_SPLIT = re.compile(r"^\s{4}Retry #\d+(?: ─+)?\s*$")
PW_FRAME = re.compile(r"^\s*(?:>\s*)?\d+\s*\||^\s*\|")
PW_LOCATION = re.compile(r"^(?:\[(?P<project>[^\]]*)\] › )?(?P<file>.+?):(?P<line>\d+):(?P<col>\d+) › (?P<titles>.+)$")


def pw_id(file, project, titles):
    return "playwright::%s::%s%s" % (file.replace("\\", "/"), ("[%s] › " % project) if project else "", titles)


def pw_errors(lines):
    """Playwright 오류 텍스트(한 attempt 또는 한 errors[].message) → 오류별 정규화 문자열 목록."""
    errors, current, in_stack, call_log = [], None, False, False
    for raw in lines:
        line = ANSI.sub("", raw)
        s = line.strip()
        if not s:
            call_log = False
            continue
        if s.startswith("Error Context:") or s.startswith("attachment #") or re.match(r"^[─-]{3,}", s):
            continue
        if s == "Call log:":
            call_log = True
            continue
        if call_log and s.startswith("- "):
            continue
        call_log = False
        if PW_FRAME.match(line):
            in_stack = True
            continue
        if re.match(r"^at\s", s):
            if current is None:
                current = dict(msg=[], frames=[])
                errors.append(current)
            current["frames"].append(s)
            in_stack = True
            continue
        if current is None or in_stack:
            current = dict(msg=[], frames=[])
            errors.append(current)
            in_stack = False
        current["msg"].append(s)
    out = []
    for e in errors:
        text = "\n".join(e["msg"])
        if is_messageless(text):
            text = messageless_signature(text, e["frames"]) or ""
        if text and text not in out:
            out.append(text)
    return out


def pw_join(texts):
    seen = []
    for t in texts:
        if t not in seen:
            seen.append(t)
    return " | ".join(seen) or "(실패 메시지 없음)"


def parse_playwright_json(value):
    failed, pass_list, skip_list, notes = [], [], [], []
    extra = []  # (id, status) — expected_fail·interrupted 관측
    flaky = []
    completed = True
    count = 0

    def walk(suite, titles, file):
        nonlocal completed, count
        for spec in suite.get("specs") or []:
            if not isinstance(spec, dict) or not isinstance(spec.get("title"), str):
                notes.append("Playwright JSON spec identity 식별 불가")
                continue
            for case in spec.get("tests") or []:
                count += 1
                tid = pw_id(spec.get("file") or file, case.get("projectName") or "", " › ".join(titles + [spec["title"]]))
                results = case.get("results") or []
                outcome, expected = case.get("status"), case.get("expectedStatus")
                errs = []
                for r in results:
                    if r.get("status") in ("failed", "timedOut"):
                        for e in r.get("errors") or []:
                            if isinstance(e, dict) and isinstance(e.get("message"), str):
                                errs.extend(pw_errors(e["message"].splitlines()))
                    if r.get("status") == "interrupted":
                        completed = False
                if not results:
                    completed = False  # did not run
                    continue
                if outcome == "expected":
                    if expected == "passed":
                        pass_list.append(tid)
                    elif expected == "failed":
                        extra.append((tid, "expected_fail"))
                    else:
                        skip_list.append(tid)
                elif outcome == "flaky" and results[-1].get("status") == "passed" and expected == "passed":
                    flaky.append(tid)
                elif outcome in ("unexpected", "flaky"):
                    unexpected_pass = ("Expected to fail, but passed." if expected == "failed" else "unexpected pass (expected %s)" % expected)
                    msg = pw_join(errs) if errs else (
                        unexpected_pass if any(r.get("status") == "passed" for r in results) else "(실패 메시지 없음)")
                    failed.append((tid, msg))
                elif outcome == "skipped":
                    if expected == "skipped" and all(r.get("status") == "skipped" for r in results):
                        skip_list.append(tid)
                    else:
                        completed = False
                        extra.append((tid, "interrupted"))
                else:
                    notes.append(tid + ": unknown outcome")
        for child in suite.get("suites") or []:
            if isinstance(child, dict):
                walk(child, titles + [child.get("title", "")], child.get("file") or file)

    for top in value.get("suites") or []:
        if isinstance(top, dict):
            walk(top, [], top.get("file") or top.get("title", ""))
    stats = value.get("stats") if isinstance(value.get("stats"), dict) else {}
    total = sum(stats.get(k, 0) for k in ("expected", "unexpected", "flaky", "skipped") if isinstance(stats.get(k), int))
    if not stats or total != count:
        completed = False
        notes.append("Playwright JSON 관측 testcase 수와 stats 합 불일치")
    for e in value.get("errors") or []:
        notes.append("Playwright 전역 오류: " + ANSI.sub("", (e or {}).get("message", "") if isinstance(e, dict) else str(e)).splitlines()[0][:120])
    passed = stats.get("expected") if isinstance(stats.get("expected"), int) else None
    return dict(completed=completed, reason="" if completed else "Playwright 실행 미완료(interrupted·did not run·수 불일치)",
                passed=passed, failed=failed, total=count, notes=notes, passed_ids=set(pass_list),
                pass_list=pass_list, skip_list=skip_list, extra=extra, runner_flaky=flaky)


def parse_playwright_list(lines):
    failed, pass_list, skip_list, notes, extra, flaky = [], [], [], [], [], []
    cases, order = {}, []  # key(project, file, line, col, titles) → attempt marks
    counts, lists, details = {}, {}, []
    current_list, detail = None, None
    fatal = False
    for ln in lines:
        m = PW_ROW.match(ln)
        if m and detail is None:
            mark, text = m.group(1), m.group(3)
            if mark != "-":
                text = re.sub(r" \(\d+(?:\.\d+)?(?:ms|s|m|h)\)$", "", text)
            text = re.sub(r" \(retry #\d+\)$", "", text)
            lm = PW_LOCATION.match(text)
            if not lm:
                notes.append("Playwright 행 식별 불가: " + text[:80])
                continue
            key = (lm.group("project") or "", lm.group("file"), lm.group("line"), lm.group("col"), lm.group("titles"))
            if key not in cases:
                cases[key] = []
                order.append(key)
            cases[key].append({"✓": "pass", "ok": "pass", "✘": "fail", "x": "fail", "-": "skip"}[mark])
            continue
        m = PW_COUNT.match(ln)
        if m:
            counts[m.group(2)] = int(m.group(1))
            current_list = m.group(2) if m.group(2) in ("failed", "interrupted", "flaky") else None
            detail = None
            continue
        if PW_FATAL.match(ln):
            fatal = True
            current_list = None
            continue
        if current_list:
            sm = PW_SUMMARY_ITEM.match(ln)
            if sm:
                lists.setdefault(current_list, []).append(sm.group(1))
                continue
            current_list = None
        dm = PW_DETAIL.match(ln)
        if dm:
            detail = dict(header=dm.group(2), lines=[])
            details.append(detail)
            continue
        if detail is not None:
            detail["lines"].append(ln)
    if not counts:
        return dict(completed=False, reason="종료 마커(Playwright 요약) 없음", passed=None, failed=[], total=None,
                    notes=notes, passed_ids=set(), pass_list=[], skip_list=[], extra=[], runner_flaky=[])

    def text_of(key):
        project, file, line, col, titles = key
        return ("[%s] › " % project if project else "") + "%s:%s:%s › %s" % (file, line, col, titles)

    by_text = {text_of(k): k for k in order}
    block_of = {}
    for d in details:
        hm = PW_LOCATION.match(d["header"])
        cands = []
        if hm:
            for k in order:
                if (k[0], k[1], k[2], k[3]) != (hm.group("project") or "", hm.group("file"), hm.group("line"), hm.group("col")):
                    continue
                core = re.sub(r"(?: @\S+)+$", "", k[4])
                h = hm.group("titles")
                if h == k[4] or h == core or h.startswith(core + " › ") or h.startswith(core + " @"):
                    cands.append(k)
        if len(cands) != 1 or cands[0] in block_of:
            notes.append("Playwright 실패 상세 연결 불가: " + d["header"][:80])
            continue
        block_of[cands[0]] = d["lines"]
    listed = {}
    for name, items in lists.items():
        for item in items:
            if item not in by_text:
                notes.append("Playwright 요약 목록 항목 식별 불가: " + item[:80])
                continue
            listed[by_text[item]] = name

    def message(key):
        attempts, chunk = [], []
        for ln in block_of.get(key, []):
            if PW_RETRY_SPLIT.match(ln):
                attempts.append(chunk)
                chunk = []
            else:
                chunk.append(ln)
        attempts.append(chunk)
        errs = []
        for a in attempts:
            errs.extend(pw_errors(a))
        return errs

    for key in order:
        project, file = key[0], key[1]
        tid = pw_id(file, project, key[4])
        marks = cases[key]
        state = listed.get(key)
        errs = message(key)
        if state == "failed":
            failed.append((tid, pw_join(errs)))
        elif state == "flaky":
            if marks[-1] == "pass" and not any("Expected to fail, but passed" in e for e in errs):
                flaky.append(tid)
            else:
                failed.append((tid, pw_join(errs)))
        elif state == "interrupted":
            extra.append((tid, "interrupted"))
        elif marks[-1] == "pass":
            pass_list.append(tid)
        elif marks[-1] == "fail":
            extra.append((tid, "expected_fail"))
        else:
            skip_list.append(tid)
    expected_total = sum(counts.get(k, 0) for k in ("failed", "flaky", "skipped", "passed", "interrupted"))
    completed = not counts.get("interrupted") and not counts.get("did not run") and expected_total == len(order)
    if expected_total != len(order):
        notes.append("Playwright 관측 testcase 수(%d)와 요약 합(%d) 불일치" % (len(order), expected_total))
    if counts.get("failed", 0) != len(lists.get("failed", [])) or counts.get("flaky", 0) != len(lists.get("flaky", [])):
        notes.append("Playwright 요약 수와 목록 불일치")
    if fatal:
        notes.append("Playwright 테스트 밖 오류(error … not a part of any test)")
    return dict(completed=completed, reason="" if completed else "Playwright 실행 미완료(interrupted·did not run·수 불일치)",
                passed=counts.get("passed", 0), failed=failed, total=len(order), notes=notes, passed_ids=set(pass_list),
                pass_list=pass_list, skip_list=skip_list, extra=extra, runner_flaky=flaky)


def parse_playwright(lines):
    try:
        value = json.loads("\n".join(lines))
    except (ValueError, TypeError):
        value = None
    if isinstance(value, dict) and isinstance(value.get("suites"), list) and "config" in value:
        return parse_playwright_json(value)
    return parse_playwright_list(lines)


PARSERS = {"go": parse_go, "jest": parse_jest, "vitest": parse_vitest, "playwright": parse_playwright}


def analyze(lines, runner, exit_code):
    lines = [ANSI.sub("", line) for line in lines]
    if runner == "auto":
        runner = detect_runner(lines)
    res = dict(runner=runner, records=[], unparsed=[], completed=False, reason="", passed=None, total=None, passed_ids=set(),
               observed={}, diagnostics=[])
    if runner not in PARSERS:
        res["reason"] = "지원하지 않는 러너/판별 실패 (go·jest·vitest·playwright만 지원)"
        res["unparsed"].append("러너 %s: 출력 전체 unparsed" % runner)
        return res
    p = PARSERS[runner](lines)
    res.update(completed=p["completed"], reason=p["reason"], passed=p["passed"], total=p["total"], passed_ids=p["passed_ids"])
    observed = res["observed"]
    for tid in p.get("pass_list", sorted(p["passed_ids"])):
        observed.setdefault(tid, []).append("pass")
    for tid, _ in p["failed"]:
        observed.setdefault(tid, []).append("fail")
    for tid in p.get("skip_list", []):
        observed.setdefault(tid, []).append("skip")
    for tid, status in p.get("extra", []):
        observed.setdefault(tid, []).append(status)
    for tid in p.get("runner_flaky", []):
        observed.setdefault(tid, []).append("flaky")
        res["records"].append(dict(id=tid, sig="", raw="", cls="flaky", note="러너 재시도 통과", runner_flaky=True))
    if isinstance(p["passed"], int) and p["passed"] > 0 and not any("pass" in v for v in observed.values()):
        res["diagnostics"].append("pass_observation_unavailable(통과 %d건이 식별자 없이 요약만 출력됨 — verbose/JSON 리포터 필요)" % p["passed"])
    if runner == "playwright":
        res["unparsed"].extend("중복 테스트 식별자: " + tid for tid, v in observed.items() if len(v) > 1)
    for tid, msg in p["failed"]:
        record = dict(id=tid, sig=normalize(msg) if runner == "go" else re.sub(r"\s+", " ", msg).strip(), raw=msg)
        if msg == "(실패 메시지 없음)":
            record.update(cls="unparsed", note="실패 메시지 식별 불가")
            res["unparsed"].append(tid + ": 실패 메시지 식별 불가")
        res["records"].append(record)
    res["unparsed"].extend(p["notes"])
    if p.get("expected_failed") is not None and p["expected_failed"] != len(p["failed"]):
        res["unparsed"].append("러너 실패 수와 식별한 실패 수 불일치")
    if len({tid for tid, _ in p["failed"]}) != len(p["failed"]):
        res["unparsed"].append("중복 실패 ID — 자동 대조 불가")
        for record in res["records"]:
            record.update(cls="unparsed", note="중복 실패 ID")
    if p["completed"] and not p["failed"] and exit_code != 0 and not p["notes"]:
        res["unparsed"].append("실패 없는 비정상 종료 (exit %d)" % exit_code)
    if p["completed"] and (p["total"] == 0 or (p["total"] is None and p["passed"] == 0 and not p["failed"])):
        res["unparsed"].append("테스트 0건")
    return res


def table_cells(line):
    return [cell_unescape(c.strip()) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def parse_baseline(state_text):
    # unparsed_suites: (suite 또는 None=전역, 메시지). 호출 suite와 전역 진단만 판정에 붙인다.
    out = dict(failed={}, collect_failed=False, collect_failed_suites=set(), tomb_new_to_old={}, deleted=set(), testmap=set(),
               testmap_legacy=False, unparsed_suites=[], commit="")
    m = re.search(r"^## Test Baseline\s*$(.*?)(?=^## |\Z)", state_text, re.M | re.S)
    if not m:
        out["failed"] = None
        return out
    sec = m.group(1)
    if any("수집 실패" in ln for ln in sec.splitlines() if not ln.strip().startswith("|")):
        out["collect_failed"] = True
    mc = re.search(r"커밋\s*[:：]\s*([0-9a-fA-F]{7,40})", sec)
    if mc:
        out["commit"] = mc.group(1)
    for ln in sec.splitlines():
        if not ln.strip().startswith("|"):
            continue
        raw = ln.strip().strip("|")
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", raw)]
        if len(cells) < 6 or cells[0] in ("suite", "") or set(cells[0]) <= set("-: "):
            continue
        suite, done, failed_n, items = cells[0], cells[2], cells[4], cells[5]
        if "수집 실패" in ln:
            out["collect_failed_suites"].add(suite)
            continue
        if done.upper() != "Y":
            out["unparsed_suites"].append((suite, "%s: 러너 완주 N (baseline 신뢰 불가)" % suite))
            continue
        if items in ("", "-", "없음"):
            if failed_n.isdigit() and int(failed_n) != 0:
                out["unparsed_suites"].append((suite, "%s: 실패 %s건인데 목록 없음" % (suite, failed_n)))
            continue
        parsed = []
        ok = True
        for it in ITEM_SPLIT.split(items):
            mm = ITEM_RE.match(it.strip())
            if not mm:
                ok = False
                break
            parsed.append((cell_unescape(mm.group(1)), cell_unescape(mm.group(2))))
        if not ok or (failed_n.isdigit() and int(failed_n) != len(parsed)):
            out["unparsed_suites"].append((suite, "%s: 셀 파싱 실패 또는 개수 불일치" % suite))
            continue
        for tid, sig in parsed:
            if (suite, tid) in out["failed"]:
                out["unparsed_suites"].append((suite, "%s: 중복 테스트 식별자 %s" % (suite, tid)))
            out["failed"][(suite, tid)] = sig
    seen_old = set()
    for mm in re.finditer(r"^\s*-\s*`([^`]+)`\s*→\s*(?:`([^`]+)`|삭제\s*\(([^)]*)\))", sec, re.M):
        old, new = mm.group(1), mm.group(2)
        if old in seen_old:
            out["unparsed_suites"].append((None, "Tombstone 중복 매핑: %s" % old))
            continue
        seen_old.add(old)
        if new:
            if new in out["tomb_new_to_old"]:
                out["unparsed_suites"].append((None, "Tombstone 중복 매핑(신 식별자): %s" % new))
            out["tomb_new_to_old"][new] = old
        else:
            out["deleted"].add(old)
    mt = re.search(r"^## TDD Test Map\s*$(.*?)(?=^## |\Z)", state_text, re.M | re.S)
    if mt:
        for ln in mt.group(1).splitlines():
            if ln.strip().startswith("|"):
                cells = table_cells(ln)
                if len(cells) >= 2 and cells[1] not in ("테스트", "—", "-", "") and not set(cells[1]) <= set("-: "):
                    tid = cells[1].strip("`")
                    out["testmap"].add(tid)
                    out["testmap_legacy"] = out["testmap_legacy"] or "::" not in tid
    # 이전 형식(표시명) Test Map을 재개할 때 오케스트레이터가 복원한 정확 ID 대응(구 표시명 → 정확 ID).
    mm = re.search(r"^## TDD Test Map ID 대응\s*$(.*?)(?=^## |\Z)", state_text, re.M | re.S)
    if mm:
        for ln in mm.group(1).splitlines():
            if ln.strip().startswith("|"):
                cells = table_cells(ln)
                if len(cells) >= 2 and "::" in cells[1]:
                    out["testmap"].add(cells[1].strip("`"))
    return out


def in_testmap(tid, testmap):
    return tid in testmap


def classify(records, suite, bl, expect=None):
    for r in records:
        tid = r["id"]
        if r.get("cls") in ("unparsed", "flaky"):
            continue
        if bl is None or bl["failed"] is None:
            r["cls"], r["note"] = "unparsed", "baseline 섹션 없음"
            continue
        if expect and tid in expect:
            r["cls"], r["note"] = ("new_red", "expect red") if expect[tid] == "red" else ("regression", "expect pass 재실패")
            continue
        if in_testmap(tid, bl["testmap"]):
            r["cls"], r["note"] = "new_red", "TDD Test Map 등재"
            continue
        if bl["collect_failed"] or suite in bl.get("collect_failed_suites", ()):
            r["cls"], r["note"] = "unparsed", "baseline 수집 실패 — regression 판정 불가"
            continue
        if "::" in tid and any(s == suite and "::" not in old for s, old in bl["failed"]):
            r["cls"], r["note"] = "unparsed", "구 baseline에 package 또는 runner/file 없음 — 자동 대조 불가"
            continue
        lookup = bl["tomb_new_to_old"].get(tid, tid)
        note = ("Tombstone %s → %s; " % (lookup, tid)) if lookup != tid else ""
        key = (suite, lookup)
        if key in bl["failed"]:
            if "::" in tid and bl["failed"][key] == normalize("(실패 메시지 없음)"):
                r["cls"], r["note"] = "unparsed", "Go baseline 실패 메시지 식별 불가"
                continue
            if bl["failed"][key] == r["sig"]:
                r["cls"], r["note"] = "pre_existing", note + "baseline 동일 시그니처"
            else:
                r["cls"], r["note"] = "regression", note + "baseline과 다른 시그니처"
        else:
            r["cls"], r["note"] = "regression", note + "baseline에 없는 실패"
    return records


def apply_rerun(records, rerun_res):
    for r in records:
        if r.get("cls") == "unparsed" or r.get("runner_flaky"):
            continue  # 재실행 성공으로 모호한 baseline의 대조 실패를 해소하지 않는다.
        if not rerun_res["completed"] or rerun_res["unparsed"]:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(재실행 미완주/파싱 불가)"
            continue
        observed = rerun_res.get("observed")
        if observed is None:  # 호출자가 관측 목록 없이 만든 결과 — passed_ids를 1회 관측으로 본다.
            observed = {tid: ["pass"] for tid in rerun_res.get("passed_ids", set())}
            for item in rerun_res["records"]:
                observed.setdefault(item["id"], []).append("fail")
        seen = observed.get(r["id"], [])
        if seen == ["pass"]:
            r["cls"] = "flaky"
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "재실행 PASS 명시"
        elif "pass" in seen:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(중복/skip 혼재)"
        else:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(PASS 증거 없음)"
    return records


def parse_expect(text):
    expect = {}
    for n, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^(red|pass)\s+(\S.*)$", s)
        if not m:
            raise ValueError("%d행: `red {ID}` 또는 `pass {ID}` 형식이 아님" % n)
        if m.group(2) in expect:
            raise ValueError("%d행: 중복·상충 기대 %s" % (n, m.group(2)))
        expect[m.group(2)] = m.group(1)
    return expect


def obs_label(seen, flaky=False):
    if flaky:
        return "FLAKY"
    if not seen:
        return "미관측"
    if len(seen) > 1:
        return "중복" if len(set(seen)) == 1 else "혼재"
    return {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "expected_fail": "EXPECTED_FAIL",
            "interrupted": "INTERRUPTED", "flaky": "FLAKY"}.get(seen[0], seen[0])


def baseline_unconfirmed(bl, suite, observed, flaky_ids):
    """baseline 실패 ID가 현재 실행에서 FAIL·PASS 1회·FLAKY로 확인되지 않으면(승인 삭제 제외) 목록으로 반환한다."""
    old_to_new = {old: new for new, old in bl["tomb_new_to_old"].items()}
    out = []
    for s, tid in bl["failed"]:
        if s != suite or tid == "unparsed" or tid in bl["deleted"]:
            continue
        cid = old_to_new.get(tid, tid)
        label = obs_label(observed.get(cid, []), cid in flaky_ids)
        if label not in ("FAIL", "PASS", "FLAKY"):
            out.append((cid, label))
    return out


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--runner", required=True, choices=["go", "jest", "vitest", "playwright", "auto"])
    ap.add_argument("--exit-code", required=True, type=int)
    ap.add_argument("--suite", default="unit")
    ap.add_argument("--command", default="-")
    ap.add_argument("--emit-baseline", action="store_true")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--expect", default=None, help="한 줄 `red {ID}` 또는 `pass {ID}` (UTF-8)")
    ap.add_argument("--partial", action="store_true", help="부분 실행: 기대 미관측·baseline 실패 미확인을 판정에 쓰지 않는다")
    ap.add_argument("--rerun", default=None)
    ap.add_argument("--rerun-exit-code", type=int, default=None)
    args = ap.parse_args()

    try:
        if args.file == "-":
            text = sys.stdin.buffer.read().decode("utf-8", errors="replace") if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        else:
            text = open(args.file, "rb").read().decode("utf-8", errors="replace")
    except OSError as e:
        print("오류: 입력 파일 읽기 실패: %s" % e, file=sys.stderr)
        return 2
    if args.rerun and args.rerun_exit_code is None:
        print("오류: --rerun 은 --rerun-exit-code 와 함께 써야 합니다", file=sys.stderr)
        return 2
    expect = None
    if args.expect:
        if not args.baseline:
            print("오류: --expect 는 --baseline 과 함께 써야 합니다", file=sys.stderr)
            return 2
        try:
            expect = parse_expect(open(args.expect, "rb").read().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as e:
            print("오류: expect 파일: %s" % e, file=sys.stderr)
            return 2
    lines = text.splitlines()
    res = analyze(lines, args.runner, args.exit_code)
    records = res["records"]

    bl = None
    if args.baseline:
        try:
            bl = parse_baseline(open(args.baseline, "rb").read().decode("utf-8", errors="replace"))
        except OSError as e:
            print("오류: baseline 파일 읽기 실패: %s" % e, file=sys.stderr)
            return 2
        classify(records, args.suite, bl, expect)
        res["unparsed"].extend(msg for suite, msg in bl["unparsed_suites"] if suite in (None, args.suite))
        if bl["testmap_legacy"]:
            res["diagnostics"].append("test_map_legacy_ids(Test Map에 정확 ID가 아닌 표시명 — `## TDD Test Map ID 대응` 복원 필요)")
    if args.rerun:
        try:
            rl = open(args.rerun, "rb").read().decode("utf-8", errors="replace").splitlines()
        except OSError as e:
            print("오류: rerun 파일 읽기 실패: %s" % e, file=sys.stderr)
            return 2
        rr = analyze(rl, res["runner"] if res["runner"] in PARSERS else args.runner, args.rerun_exit_code)
        apply_rerun(records, rr)
        res["unparsed"].extend("rerun: " + note for note in rr["unparsed"])
        original_ids = {r["id"] for r in records}
        res["unparsed"].extend("rerun 추가 실패: " + r["id"] for r in rr["records"] if r["id"] not in original_ids)

    failures = [r for r in records if not r.get("runner_flaky")]
    flaky_ids = {r["id"] for r in records if r.get("cls") == "flaky"}
    gate = []  # 판정 불가 사유 (unparsed·완주 N 외)
    expect_rows = []
    if expect is not None:
        for tid, kind in expect.items():
            label = obs_label(res["observed"].get(tid, []), tid in flaky_ids)
            ok = label in ("PASS", "FLAKY") if kind == "pass" else label in ("FAIL", "PASS", "FLAKY")
            expect_rows.append((kind, tid, label, ok))
        bad = [row for row in expect_rows if not row[3]]
        if bad and not args.partial:
            gate.append("expect 불충족 %d" % len(bad))
    unconfirmed = []
    if expect is not None and bl is not None and bl["failed"] is not None:
        unconfirmed = baseline_unconfirmed(bl, args.suite, res["observed"], flaky_ids)
        if unconfirmed and not args.partial:
            gate.append("baseline 실패 미확인 %d" % len(unconfirmed))

    done = "Y" if res["completed"] else "N"
    passed_txt = "?" if res["passed"] is None else str(res["passed"])
    print("## test_failures — suite `%s` (runner %s, exit %d)" % (args.suite, res["runner"], args.exit_code))
    print("- 러너 완주: %s%s" % (done, (" (%s)" % res["reason"]) if res["reason"] else ""))
    print("- 통과: %s / 실패: %d / unparsed: %d" % (passed_txt, len(failures), len(res["unparsed"])))
    if records:
        print("")
        print("| 식별자 | 분류 | 시그니처 | 비고 |")
        print("|--------|------|----------|------|")
        for r in records:
            print("| `%s` | %s | `%s` | %s |" % (cell_escape(r["id"]), r.get("cls", "-"), cell_escape(display(r["sig"])), r.get("note", "-")))
    for u in res["unparsed"]:
        print("- unparsed: %s" % u)
    for d in res["diagnostics"]:
        print("- 진단: %s" % d)
    if expect is not None:
        print("")
        print("expect 대조%s:" % (" (부분 실행 — 판정에 쓰지 않음)" if args.partial else ""))
        print("| 기대 | ID | 관측 | 충족 |")
        print("|------|----|------|------|")
        for kind, tid, label, ok in expect_rows:
            print("| %s | `%s` | %s | %s |" % (kind, cell_escape(tid), label, "Y" if ok else "N"))
        print("- baseline 실패 미확인: %d%s" % (len(unconfirmed), " (부분 실행 — 판정에 쓰지 않음)" if args.partial and unconfirmed else ""))
        for tid, label in unconfirmed:
            print("  - `%s` (%s)" % (cell_escape(tid), label))
    if args.emit_baseline:
        items = " / ".join("`%s` :: `%s`" % (cell_escape(r["id"]), cell_escape(r["sig"])) for r in failures)
        if res["unparsed"]:
            items = (items + " / " if items else "") + "`unparsed` :: `%s`" % cell_escape("; ".join(res["unparsed"]))
        print("")
        print("baseline 행:")
        print("| %s | %s | %s | %s | %d | %s |" % (args.suite, args.command.replace("|", "\\|"), done, passed_txt, len(failures), items or "-"))
    cls_counts = {}
    for r in records:
        cls_counts[r.get("cls", "-")] = cls_counts.get(r.get("cls", "-"), 0) + 1
    summary = "요약: 완주 %s / 통과 %s / 실패 %d / unparsed %d" % (done, passed_txt, len(failures), len(res["unparsed"]))
    if args.baseline:
        summary += " / " + " / ".join("%s %d" % (k, cls_counts.get(k, 0)) for k in ("regression", "new_red", "pre_existing", "flaky", "unparsed"))
    if res["unparsed"] or not res["completed"]:
        gate.insert(0, "unparsed·완주 N 잔존")
    if gate:
        summary += " — PASS 판정 불가(%s)" % ", ".join(gate)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
