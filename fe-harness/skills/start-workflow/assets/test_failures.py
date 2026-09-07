#!/usr/bin/env python3
r"""test_failures.py — 테스트 러너 출력 → 실패 레코드 / 회귀 baseline 행 / baseline 대조 분류 (stdlib only).

계약 (canonical — tdd.md·quality-loop.md는 호출법만 둔다):
  사용법: test_failures.py --runner {go|jest|vitest|auto} --exit-code N [--suite NAME] [--command TEXT]
          [--emit-baseline] [--baseline STATE_FILE] [--rerun FILE2 --rerun-exit-code M] [FILE|-]
  종료:   결과를 출력하면(unparsed 포함 — 정상 데이터) exit 0. 입력 파일 부재·인자 오류 등 호출 자체 실패만 exit 2.
  지원 러너: go · jest · vitest. 그 외/판별 실패 → 전부 `unparsed`.

완주 판정 매트릭스 (러너별 종료 마커 = go `ok|FAIL <pkg>` 요약 줄 또는 단독 PASS/FAIL, jest `Tests:`, vitest `Test Files`):
  마커 있음 → 완주 Y (exit ≠ 0은 "실패 있음"으로만 해석) / 마커 없음 → 완주 N / 마커 ∧ 실패 0 ∧ exit ≠ 0 → Y + unparsed 1건(실패 없는 비정상 종료)
  / 테스트 0건 → Y + unparsed(테스트 0건). go `[build failed]` → 완주 N(build failed).
식별자: go `{package}::TestX/sub`, jest·vitest `{runner}::{file}::{describe › it}`. 키 = suite + 식별자.
정규화 시그니처: Go는 실패 메시지 첫 줄에서 경로·라인 번호·타임스탬프·메모리 주소(0x…)·goroutine id·소요 시간을 제거하고 공백 축약.
  JS는 JSON failureMessages 또는 텍스트 오류 본문(코드 프레임·stack 제외)의 matcher/Expected/Received/diff 전체를 보존한다.
  비교 키 = 정규화된 전체 메시지, 표시 = 120자 + #해시 8자. JSON reporter는 runner를 명시하고 동일 저장소 루트 cwd에서 수집한다.
baseline 셀 문법: 항목 `{ID}` :: `{sig}` (백틱), 항목 구분은 닫는 백틱과 여는 백틱 사이의 ` / ` 만 (regex (?<=`) / (?=`)),
  내부 백틱 → `'`, `|` → `\|`. 파싱 실패·개수 불일치·Tombstone 중복 매핑 → 해당 suite 행 전체 unparsed.
대조 우선순위: Tombstone 매핑(분류 전) → `## TDD Test Map` 등재 → new_red / baseline 동일 키+동일 sig → pre_existing
  / 다른 sig → regression / 부재 → regression. 모순·중복 → unparsed. baseline `수집 실패` 기록 → Test Map 외 전부 unparsed(baseline 없음).
rerun: verbose 출력 필수. flaky ⇔ 재실행 완주 ∧ 그 식별자가 PASS로 명시(go `--- PASS: {ID}`, jest/vitest 동일 runner+파일+전체 이름 `✓ {ID}`; leaf/suffix 추정 금지). 그 외 → 원 분류 + rerun_incomplete.
"""
import argparse
import hashlib
import json
import os
import re
import sys

ITEM_SPLIT = re.compile(r"(?<=`) / (?=`)")
ITEM_RE = re.compile(r"^`(.*)` :: `(.*)`$", re.S)


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


def error_body(lines):
    # Error values/diffs are semantic. Strip source frames and stack locations only.
    body = []
    for line in lines:
        line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
        if re.match(r"^\s*(?:[>❯]?\s*\d+\s*\||\||at |❯|●|FAIL |PASS |Test Suites:|Tests:|Test Files|⎯)", line):
            break
        if line.strip():
            body.append(line.strip())
    return "\n".join(body) or "(실패 메시지 없음)"


def parse_js_json(lines, runner):
    try:
        value = json.loads("\n".join(lines))
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("testResults"), list):
        return None
    failed, passed_ids, notes, observed = [], set(), [], 0
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
            elif status == "failed":
                messages = case.get("failureMessages", [])
                if not isinstance(messages, list) or not all(isinstance(m, str) for m in messages):
                    messages = []
                failed.append((tid, "\n".join(error_body(m.splitlines()) for m in messages) or "(실패 메시지 없음)"))
            elif status not in ("pending", "todo", "skipped", "disabled"):
                notes.append(tid + ": unknown assertion status")
        if suite.get("status") == "failed" and failed_before == len(failed):
            notes.append(suite["name"] + ": suite 실패에 assertion 증거 없음")
    total = value.get("numTotalTests")
    completed = isinstance(total, int) and not isinstance(total, bool) and total == observed and not value.get("wasInterrupted", False)
    if not completed:
        notes.append("JSON 실행 미완주/테스트 수 불일치")
    return dict(completed=completed, reason="" if completed else "JSON 실행 미완료", passed=len(passed_ids),
                failed=failed, total=total, notes=notes, passed_ids=passed_ids, expected_failed=value.get("numFailedTests"))


def parse_jest(lines):
    structured = parse_js_json(lines, "jest")
    if structured is not None:
        return structured
    failed, passed_ids, notes = [], set(), []
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
        m = re.match(r"^(\s*)[✓✔✕×]\s+(.+?)(?:\s+\(\d+(?:\.\d+)?\s*m?s\))?\s*$", ln)
        if m and not details:
            indent = len(m.group(1))
            while headings and headings[-1][0] >= indent:
                headings.pop()
            if ln.lstrip()[0] in "✓✔" and filename:
                passed_ids.add(js_id("jest", filename, " › ".join([h[1] for h in headings] + [m.group(2)])))
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
    return dict(completed=completed, reason=reason, passed=passed, failed=failed, total=total, notes=notes, passed_ids=passed_ids, expected_failed=expected_failed)


def parse_vitest(lines):
    structured = parse_js_json(lines, "vitest")
    if structured is not None:
        return structured
    failed, passed_ids, notes, messages = [], set(), [], {}
    completed, passed, total, expected_failed = False, None, None, None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*FAIL\s+(.+?)\s+>\s+(.+?)\s*$", ln)
        if m:
            tid = js_id("vitest", *m.groups())
            if tid in messages:
                notes.append(tid + ": duplicate failure identity")
            messages[tid] = error_body(lines[i + 1:])
            continue
        m = re.match(r"^\s*([×✗✓✔])\s+(.+?)\s+>\s+(.+?)(?:\s+\d+(?:\.\d+)?\s*m?s)?\s*$", ln)
        if m:
            verdict, filename, title = m.groups()
            tid = js_id("vitest", filename, title)
            if verdict in "✓✔":
                passed_ids.add(tid)
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
    return dict(completed=completed, reason=reason, passed=passed, failed=out, total=total, notes=notes, passed_ids=passed_ids, expected_failed=expected_failed)


PARSERS = {"go": parse_go, "jest": parse_jest, "vitest": parse_vitest}


def analyze(lines, runner, exit_code):
    lines = [re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line) for line in lines]
    if runner == "auto":
        runner = detect_runner(lines)
    res = dict(runner=runner, records=[], unparsed=[], completed=False, reason="", passed=None, total=None, passed_ids=set())
    if runner not in PARSERS:
        res["reason"] = "지원하지 않는 러너/판별 실패 (go·jest·vitest만 지원)"
        res["unparsed"].append("러너 %s: 출력 전체 unparsed" % runner)
        return res
    p = PARSERS[runner](lines)
    res.update(completed=p["completed"], reason=p["reason"], passed=p["passed"], total=p["total"], passed_ids=p["passed_ids"])
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


def parse_baseline(state_text):
    out = dict(failed={}, collect_failed=False, tomb_new_to_old={}, deleted=set(), testmap=set(), unparsed_suites=[], commit="")
    m = re.search(r"^## Test Baseline\s*$(.*?)(?=^## |\Z)", state_text, re.M | re.S)
    if not m:
        out["failed"] = None
        return out
    sec = m.group(1)
    if "수집 실패" in sec:
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
        if done.upper() != "Y":
            out["unparsed_suites"].append("%s: 러너 완주 N (baseline 신뢰 불가)" % suite)
            continue
        if items in ("", "-", "없음"):
            if failed_n.isdigit() and int(failed_n) != 0:
                out["unparsed_suites"].append("%s: 실패 %s건인데 목록 없음" % (suite, failed_n))
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
            out["unparsed_suites"].append("%s: 셀 파싱 실패 또는 개수 불일치" % suite)
            continue
        for tid, sig in parsed:
            if (suite, tid) in out["failed"]:
                out["unparsed_suites"].append("%s: 중복 테스트 식별자 %s" % (suite, tid))
            out["failed"][(suite, tid)] = sig
    seen_old = set()
    for mm in re.finditer(r"^\s*-\s*`([^`]+)`\s*→\s*(?:`([^`]+)`|삭제\s*\(([^)]*)\))", sec, re.M):
        old, new = mm.group(1), mm.group(2)
        if old in seen_old:
            out["unparsed_suites"].append("Tombstone 중복 매핑: %s" % old)
            continue
        seen_old.add(old)
        if new:
            if new in out["tomb_new_to_old"]:
                out["unparsed_suites"].append("Tombstone 중복 매핑(신 식별자): %s" % new)
            out["tomb_new_to_old"][new] = old
        else:
            out["deleted"].add(old)
    mt = re.search(r"^## TDD Test Map\s*$(.*?)(?=^## |\Z)", state_text, re.M | re.S)
    if mt:
        for ln in mt.group(1).splitlines():
            if ln.strip().startswith("|"):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if len(cells) >= 2 and cells[1] not in ("테스트", "—", "-", "") and not set(cells[1]) <= set("-: "):
                    out["testmap"].add(cells[1].strip("`"))
    return out


def in_testmap(tid, testmap):
    return tid in testmap


def classify(records, suite, bl):
    for r in records:
        tid = r["id"]
        if r.get("cls") == "unparsed":
            continue
        if bl is None or bl["failed"] is None:
            r["cls"], r["note"] = "unparsed", "baseline 섹션 없음"
            continue
        if in_testmap(tid, bl["testmap"]):
            r["cls"], r["note"] = "new_red", "TDD Test Map 등재"
            continue
        if bl["collect_failed"]:
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
        if r.get("cls") == "unparsed":
            continue  # 재실행 성공으로 모호한 baseline의 대조 실패를 해소하지 않는다.
        if not rerun_res["completed"] or rerun_res["unparsed"]:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(재실행 미완주/파싱 불가)"
            continue
        ids = rerun_res.get("passed_ids", set())
        failed_ids = {item["id"] for item in rerun_res["records"]}
        passed = r["id"] in ids
        if passed and r["id"] not in failed_ids:
            r["cls"] = "flaky"
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "재실행 PASS 명시"
        else:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(PASS 증거 없음)"
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--runner", required=True, choices=["go", "jest", "vitest", "auto"])
    ap.add_argument("--exit-code", required=True, type=int)
    ap.add_argument("--suite", default="unit")
    ap.add_argument("--command", default="-")
    ap.add_argument("--emit-baseline", action="store_true")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--rerun", default=None)
    ap.add_argument("--rerun-exit-code", type=int, default=None)
    args = ap.parse_args()

    try:
        text = sys.stdin.read() if args.file == "-" else open(args.file, "rb").read().decode("utf-8", errors="replace")
    except OSError as e:
        print("오류: 입력 파일 읽기 실패: %s" % e, file=sys.stderr)
        return 2
    if args.rerun and args.rerun_exit_code is None:
        print("오류: --rerun 은 --rerun-exit-code 와 함께 써야 합니다", file=sys.stderr)
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
        classify(records, args.suite, bl)
        res["unparsed"].extend(bl["unparsed_suites"])
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

    done = "Y" if res["completed"] else "N"
    passed_txt = "?" if res["passed"] is None else str(res["passed"])
    print("## test_failures — suite `%s` (runner %s, exit %d)" % (args.suite, res["runner"], args.exit_code))
    print("- 러너 완주: %s%s" % (done, (" (%s)" % res["reason"]) if res["reason"] else ""))
    print("- 통과: %s / 실패: %d / unparsed: %d" % (passed_txt, len(records), len(res["unparsed"])))
    if records:
        print("")
        print("| 식별자 | 분류 | 시그니처 | 비고 |")
        print("|--------|------|----------|------|")
        for r in records:
            print("| `%s` | %s | `%s` | %s |" % (cell_escape(r["id"]), r.get("cls", "-"), cell_escape(display(r["sig"])), r.get("note", "-")))
    for u in res["unparsed"]:
        print("- unparsed: %s" % u)
    if args.emit_baseline:
        items = " / ".join("`%s` :: `%s`" % (cell_escape(r["id"]), cell_escape(r["sig"])) for r in records)
        if res["unparsed"]:
            items = (items + " / " if items else "") + "`unparsed` :: `%s`" % cell_escape("; ".join(res["unparsed"]))
        print("")
        print("baseline 행:")
        print("| %s | %s | %s | %s | %d | %s |" % (args.suite, args.command, done, passed_txt, len(records), items or "-"))
    cls_counts = {}
    for r in records:
        cls_counts[r.get("cls", "-")] = cls_counts.get(r.get("cls", "-"), 0) + 1
    summary = "요약: 완주 %s / 통과 %s / 실패 %d / unparsed %d" % (done, passed_txt, len(records), len(res["unparsed"]))
    if args.baseline:
        summary += " / " + " / ".join("%s %d" % (k, cls_counts.get(k, 0)) for k in ("regression", "new_red", "pre_existing", "flaky", "unparsed"))
    if res["unparsed"] or not res["completed"]:
        summary += " — PASS 판정 불가(unparsed·완주 N 잔존)"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
