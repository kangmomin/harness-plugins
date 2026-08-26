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
식별자: 러너 네이티브 전체 ID (go `TestX/sub`, jest·vitest `describe › it`). 키 = suite + 식별자.
정규화 시그니처: 실패 메시지 첫 줄에서 경로·라인 번호·타임스탬프·메모리 주소(0x…)·goroutine id·소요 시간을 제거하고 공백 축약.
  비교 키 = 정규화된 첫 줄 전체, 표시 = 120자 + #해시 8자.
baseline 셀 문법: 항목 `{ID}` :: `{sig}` (백틱), 항목 구분은 닫는 백틱과 여는 백틱 사이의 ` / ` 만 (regex (?<=`) / (?=`)),
  내부 백틱 → `'`, `|` → `\|`. 파싱 실패·개수 불일치·Tombstone 중복 매핑 → 해당 suite 행 전체 unparsed.
대조 우선순위: Tombstone 매핑(분류 전) → `## TDD Test Map` 등재 → new_red / baseline 동일 키+동일 sig → pre_existing
  / 다른 sig → regression / 부재 → regression. 모순·중복 → unparsed. baseline `수집 실패` 기록 → Test Map 외 전부 unparsed(baseline 없음).
rerun: verbose 출력 필수. flaky ⇔ 재실행 완주 ∧ 그 식별자가 PASS로 명시(go `--- PASS: {ID}`, jest/vitest `✓ {ID}` 또는 leaf). 그 외 → 원 분류 + rerun_incomplete.
"""
import argparse
import hashlib
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


def parse_go(lines):
    failed = []
    passed_ids = set()
    notes = []
    marker = False
    build_failed = False
    for i, ln in enumerate(lines):
        if re.match(r"^(ok|FAIL|PASS)(\s|$)", ln) or re.match(r"^\?\s+\S+\s+\[no test files\]", ln):
            marker = True
            if "[build failed]" in ln or "[setup failed]" in ln:
                build_failed = True
        m = re.match(r"^\s*--- PASS: (\S+)", ln)
        if m:
            passed_ids.add(m.group(1))
        m = re.match(r"^\s*--- FAIL: (\S+)", ln)
        if m:
            tid = m.group(1)
            indent = len(ln) - len(ln.lstrip())
            msg = None
            for nl in lines[i + 1:i + 8]:
                if nl.strip() == "":
                    continue
                nin = len(nl) - len(nl.lstrip())
                if nin <= indent and not nl.lstrip().startswith("panic:"):
                    break
                if re.match(r"^\s*--- (FAIL|PASS): ", nl):
                    continue
                if re.match(r"^\s*[\w\-]+\.go:\d+:", nl) or nl.lstrip().startswith("panic:"):
                    msg = nl.strip()
                    break
            if msg is None:
                start = None
                for j in range(i - 1, -1, -1):
                    if re.match(r"^=== RUN\s+%s\s*$" % re.escape(tid), lines[j]):
                        start = j
                        break
                if start is not None:
                    for nl in lines[start + 1:i]:
                        if re.match(r"^=== RUN", nl):
                            break  # 다른 (서브)테스트 구간 — 부모가 자식 로그를 가져가지 않는다
                        if re.match(r"^\s*[\w\-]+\.go:\d+:", nl) or nl.lstrip().startswith("panic:"):
                            msg = nl.strip()
                            break
            if msg is None:
                msg = "(실패 메시지 없음)"
            failed.append((tid, msg))
    # 자식 실패가 있는 부모는 컨테이너 — 자식만 남긴다 (부모 ID = 자식 ID의 `/` 앞부분)
    child_parents = set()
    for tid, _ in failed:
        parts = tid.split("/")
        for k in range(1, len(parts)):
            child_parents.add("/".join(parts[:k]))
    failed = [(tid, m) for tid, m in failed if tid not in child_parents]
    passed = len([p for p in passed_ids if "/" not in p]) if (passed_ids or failed) else None
    total_leaf = passed + len(failed) if passed is not None else None
    if build_failed:
        return dict(completed=False, reason="build failed", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)
    if not marker:
        return dict(completed=False, reason="종료 마커 없음(중단·크래시·설정 오류)", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)
    return dict(completed=True, reason="", passed=passed, failed=failed, total=total_leaf, notes=notes, passed_ids=passed_ids)


def parse_jest(lines):
    failed = []
    passed_ids = set()
    notes = []
    completed = False
    passed = None
    total = None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*●\s+(.+?)\s*$", ln)
        if m:
            tid = m.group(1)
            if tid.startswith("Test suite failed to run"):
                msg = "(사유 없음)"
                for nl in lines[i + 1:i + 6]:
                    if nl.strip():
                        msg = nl.strip()
                        break
                notes.append("Test suite failed to run — " + msg)
                continue
            if tid.endswith("Console") or tid.startswith("Cannot log after"):
                continue
            msg = "(실패 메시지 없음)"
            for nl in lines[i + 1:i + 12]:
                if nl.strip():
                    msg = nl.strip()
                    break
            failed.append((tid, msg))
            continue
        m = re.match(r"^\s*✓\s+(.+?)(?:\s+\(\d+\s*m?s\))?\s*$", ln)
        if m:
            passed_ids.add(m.group(1).strip())
        m = re.match(r"^Tests:\s+(.*)$", ln)
        if m:
            completed = True
            mp = re.search(r"(\d+) passed", m.group(1))
            mt = re.search(r"(\d+) total", m.group(1))
            passed = int(mp.group(1)) if mp else 0
            total = int(mt.group(1)) if mt else None
    reason = "" if completed else "종료 마커(Tests:) 없음"
    return dict(completed=completed, reason=reason, passed=passed, failed=failed, total=total, notes=notes, passed_ids=passed_ids)


def parse_vitest(lines):
    failed = []
    passed_ids = set()
    notes = []
    completed = False
    passed = None
    total = None
    msgs = {}
    arrow = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*FAIL\s+(\S+)\s+>\s+(.+?)\s*$", ln)
        if m:
            tid = m.group(2).strip()
            msg = "(실패 메시지 없음)"
            for nl in lines[i + 1:i + 8]:
                if nl.strip() and not nl.strip().startswith("❯"):
                    msg = nl.strip()
                    break
            msgs[tid] = msg
            continue
        m = re.match(r"^\s*[×✗]\s+(.+?)(?:\s+\d+\s*m?s)?\s*$", ln)
        if m:
            tid = m.group(1).strip()
            failed.append(tid)
            for nl in lines[i + 1:i + 3]:
                mm = re.match(r"^\s*→\s+(.*)$", nl)
                if mm:
                    arrow[tid] = mm.group(1).strip()
                    break
            continue
        m = re.match(r"^\s*✓\s+(.+?)(?:\s+\d+\s*m?s)?\s*$", ln)
        if m and " > " in m.group(1):
            passed_ids.add(m.group(1).strip())
        if re.match(r"^\s*Test Files\s+", ln):
            completed = True
        m = re.match(r"^\s*Tests\s+(.*)$", ln)
        if m and ("passed" in m.group(1) or "failed" in m.group(1)):
            mp = re.search(r"(\d+) passed", m.group(1))
            mt = re.search(r"\((\d+)\)", m.group(1))
            passed = int(mp.group(1)) if mp else 0
            total = int(mt.group(1)) if mt else None
    out = []
    seen = set()
    for tid in failed:
        if tid in seen:
            continue
        seen.add(tid)
        msg = msgs.get(tid)
        if msg is None:
            for k, v in msgs.items():
                if k.endswith(tid) or tid.endswith(k):
                    msg = v
                    break
        if msg is None:
            msg = arrow.get(tid, "(실패 메시지 없음)")
        out.append((tid, msg))
    reason = "" if completed else "종료 마커(Test Files) 없음"
    return dict(completed=completed, reason=reason, passed=passed, failed=out, total=total, notes=notes, passed_ids=passed_ids)


PARSERS = {"go": parse_go, "jest": parse_jest, "vitest": parse_vitest}


def analyze(lines, runner, exit_code):
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
        res["records"].append(dict(id=tid, sig=normalize(msg), raw=msg))
    res["unparsed"].extend(p["notes"])
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


def leaf_of(tid):
    return tid.split("/")[-1].split(" › ")[-1].split(" > ")[-1]


def in_testmap(tid, testmap):
    if tid in testmap:
        return True
    leaf = leaf_of(tid)
    return any(t == leaf or tid.endswith(t) for t in testmap)


def classify(records, suite, bl):
    for r in records:
        tid = r["id"]
        if bl is None or bl["failed"] is None:
            r["cls"], r["note"] = "unparsed", "baseline 섹션 없음"
            continue
        if in_testmap(tid, bl["testmap"]):
            r["cls"], r["note"] = "new_red", "TDD Test Map 등재"
            continue
        if bl["collect_failed"]:
            r["cls"], r["note"] = "unparsed", "baseline 수집 실패 — regression 판정 불가"
            continue
        lookup = bl["tomb_new_to_old"].get(tid, tid)
        note = ("Tombstone %s → %s; " % (lookup, tid)) if lookup != tid else ""
        key = (suite, lookup)
        if key in bl["failed"]:
            if bl["failed"][key] == r["sig"]:
                r["cls"], r["note"] = "pre_existing", note + "baseline 동일 시그니처"
            else:
                r["cls"], r["note"] = "regression", note + "baseline과 다른 시그니처"
        else:
            r["cls"], r["note"] = "regression", note + "baseline에 없는 실패"
    return records


def apply_rerun(records, rerun_res):
    for r in records:
        if not rerun_res["completed"]:
            r["note"] = (r.get("note", "") + "; " if r.get("note") else "") + "rerun_incomplete(재실행 미완주)"
            continue
        ids = rerun_res.get("passed_ids", set())
        leaf = leaf_of(r["id"])
        if r["id"] in ids or any(p == leaf or p.endswith(" " + leaf) or p.endswith(">" + leaf) or p.endswith("/" + leaf) for p in ids):
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
