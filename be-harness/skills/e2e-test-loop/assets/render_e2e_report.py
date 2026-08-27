#!/usr/bin/env python3
"""render_e2e_report.py — e2e-test-loop Step 4: {RUN_REPORT} → 정직한 자기 점검 md 리포트 (stdlib only).

계약 (canonical — SKILL.md Step 4는 요약만 둔다):
  사용법: render_e2e_report.py RUN_REPORT --out-dir DIR --level {smoke|full} --status S
          [--level-note TEXT] [--branch NAME]
  종료:   파일을 썼으면 exit 0 + stdout `경로: …` / `상태: OK|DEGRADED({사유})`. 파일을 못 쓰면(인자 오류·입력 파일 부재·쓰기 실패) exit 2.
  출력:   {DIR}/{YYYYMMDD-HHMMSS}-{slug(branch)}-e2e-report.md — 배타적 생성(존재 시 -2, -3 접미), 덮어쓰지 않음.

입력 계약 ({RUN_REPORT} 고정 구조만 사용 — 여기에 적히지 않은 것은 리포트에 없다):
  헤더 `# E2E 테스트 실행 리포트 — {대상}` / `> E2E 메인 플로우:` / `> 수준:` (정보용)
  `## 테스트 대상 엔드포인트` — 백틱 `METHOD PATH` 항목 = 대상
  `## Iteration 기록` — `### Iteration N` 아래 `#### {분류} — {케이스명}` 케이스 블록(- 요청/- 기대/- 실제/- 판정 필수)
      + `**실패 → 수정 (…)**` 블록(- 실패 원인/- 수정/- 귀속(선택)/- 재빌드) — 직전 케이스(시도)에 귀속
  `## 최종 요약` — `- 미해결 이슈:` / `- 커버리지:` (UNCOVERED {ID}({사유}) … / SMOKE_OMITTED {IDs} / 없음)
  fail-closed: 필수 섹션·줄·필드가 없으면 `필수 입력 결여`로 집계(직답은 `아니오`) + DEGRADED. 결여를 0으로 간주하지 않는다.

판정 상태 기계 (TC = (분류, 케이스명), 시도 = 케이스 블록, iteration 순):
  시도 판정: 마커(⚠️ INCONCLUSIVE/PARTIAL) > ❌ FAIL > ✅ PASS. 필수 필드 결여 → INCONCLUSIVE(필수 필드 결여).
  마지막 시도 기준 — 마커 → 그 verdict / FAIL+수정 블록+후속 시도 없음 → INCONCLUSIVE(수정 후 재검증 기록 없음) / FAIL → FAIL
  / PASS·시도 1개 → CLEAN PASS / PASS·선행 FAIL 중 수정 없는 것 있음 → INCONCLUSIVE(수정 없이 재시도 통과)
  / PASS·선행이 INCONCLUSIVE·PARTIAL뿐 → INCONCLUSIVE(선행 시도 판정 불확정) / 그 외 PASS → PASS (after F fixes), F = 귀속 수정 블록 수.
귀속: `- 귀속:` 줄 우선. 없으면 `- 수정:` 경로 — 테스트·mock·fixture·env·docker·헬퍼·scripts → 검증 인프라, 그 외 → 본 변경 코드, 혼재 → 혼합(수정 줄 인용), 수정 줄 없음 → 미분류.
직답 "아무 의심 없이 성공인가?": 경성 결함(FAIL·INCONCLUSIVE·PARTIAL TC·UNCOVERED·미해결·미호출 엔드포인트·필수 입력 결여) 0
  ∧ 수정 후 통과 0 ∧ SMOKE_OMITTED 0 ∧ 상태 DONE → 예 / 경성 0 ∧ DONE ∧ (수정 후 통과>0 ∨ SMOKE_OMITTED>0) → 조건부 예 / 그 외 아니오.
  --level smoke 면 최대 `조건부 예 (smoke 범위)`.
"""
import argparse
import datetime as _dt
import os
import re
import sys

METHODS = "GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS"
REQ_RE = re.compile(r"`?\b(%s)\s+([^\s`·]+)" % METHODS)
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
INFRA_HINTS = ("test", "spec", "mock", "fixture", "env", "docker", "helper", "scripts/", "testdata", "seed", "compose", "stub", "fake")


def slug(s):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip("-")
    return s or "e2e"


def norm_path(path):
    path = path.split("?")[0]
    segs = []
    for seg in path.split("/"):
        if seg == "":
            segs.append(seg)
            continue
        if seg.startswith("{") or seg.startswith(":") or seg.isdigit() or UUID_RE.match(seg):
            segs.append("*")
        else:
            segs.append(seg)
    return "/".join(segs)


def parse_verdict(text):
    """→ (kind, reason). kind ∈ PASS FAIL INCONCLUSIVE PARTIAL MISSING"""
    if text is None:
        return "MISSING", ""
    m = re.search(r"(INCONCLUSIVE|PARTIAL)\s*(?:\(([^)]*)\))?", text)
    if m:
        return m.group(1), (m.group(2) or "").strip()
    if "❌" in text:
        return "FAIL", ""
    if "✅" in text:
        return "PASS", ""
    if "실패" in text:
        return "FAIL", ""
    if "통과" in text:
        return "PASS", ""
    return "MISSING", ""


def bullet(lines, key):
    """`- key: value` 줄의 value (첫 매치). 없으면 None."""
    for ln in lines:
        m = re.match(r"^\s*-\s*%s\s*[:：]\s*(.*)$" % re.escape(key), ln)
        if m:
            return m.group(1).strip()
    return None


def sections(text):
    """`## ` 헤딩 기준 섹션 dict(title → lines). 헤딩 앞 부분은 '' 키."""
    out = {"": []}
    cur = ""
    for ln in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", ln)
        if m and not ln.startswith("###"):
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        out.setdefault(cur, []).append(ln)
    return out


def attribution_from_fix(fix_text):
    if not fix_text:
        return "미분류", "수정 줄 없음"
    tokens = re.findall(r"[\w./\\-]+\.(?:go|ts|tsx|js|jsx|py|yaml|yml|json|env|sh|sql|toml)(?::\d+)?|[\w./\\-]+/", fix_text)
    low = fix_text.lower()
    infra = any(h in low for h in INFRA_HINTS)
    source = any(not any(h in t.lower() for h in INFRA_HINTS) for t in tokens)
    if infra and source:
        return "혼합", "수정 줄 인용: " + fix_text
    if infra:
        return "검증 인프라", "수정 경로 기반 추정"
    if tokens:
        return "본 변경 코드", "수정 경로 기반 추정"
    return "미분류", "수정 줄에 경로 없음: " + fix_text


def parse_iterations(lines, diags):
    """→ (attempts[list of dict], orphan_fix_count). attempt = {iter, cat, name, req, exp, act, verdict, reason, fixes[], missing[]}"""
    attempts = []
    cur_iter = None
    cur = None
    in_fix = None
    for ln in lines:
        m_it = re.match(r"^###\s+Iteration\s+(\d+)", ln)
        if m_it:
            cur_iter = int(m_it.group(1))
            cur = None
            in_fix = None
            continue
        m_case = re.match(r"^####\s+(.+?)\s*$", ln)
        if m_case:
            title = m_case.group(1)
            if " — " in title:
                cat, name = title.split(" — ", 1)
            elif " - " in title:
                cat, name = title.split(" - ", 1)
            else:
                cat, name = title, ""
            cur = {"iter": cur_iter if cur_iter is not None else 0, "cat": cat.strip(), "name": name.strip(),
                   "lines": [], "fixes": []}
            attempts.append(cur)
            in_fix = None
            continue
        if re.match(r"^\*\*실패\s*→\s*수정", ln):
            in_fix = {"lines": []}
            if cur is None:
                diags.append("귀속 불가 수정 블록(선행 케이스 없음)")
                in_fix = None
                continue
            cur["fixes"].append(in_fix)
            continue
        if in_fix is not None:
            if ln.strip() == "" and in_fix["lines"]:
                in_fix = None
            elif ln.strip().startswith("-"):
                in_fix["lines"].append(ln)
            else:
                in_fix = None
            continue
        if cur is not None:
            cur["lines"].append(ln)
    for a in attempts:
        L = a["lines"]
        a["req"] = bullet(L, "요청")
        a["exp"] = bullet(L, "기대")
        a["act"] = bullet(L, "실제")
        v = bullet(L, "판정")
        a["missing"] = [k for k, val in (("요청", a["req"]), ("기대", a["exp"]), ("실제", a["act"]), ("판정", v)) if val is None]
        kind, reason = parse_verdict(v)
        if a["missing"]:
            kind, reason = "INCONCLUSIVE", "필수 필드 결여: " + ", ".join(a["missing"])
        elif kind == "MISSING":
            kind, reason = "INCONCLUSIVE", "판정 표기 해석 불가: " + (v or "")
        a["verdict"], a["reason"] = kind, reason
        for f in a["fixes"]:
            FL = f["lines"]
            f["cause"] = bullet(FL, "실패 원인") or "(미기재)"
            f["fix"] = bullet(FL, "수정")
            f["rebuild"] = bullet(FL, "재빌드/재시작") or "(미기재)"
            attr = bullet(FL, "귀속")
            if attr:
                f["attr"], f["attr_basis"] = attr, "기록된 귀속 줄"
            else:
                f["attr"], f["attr_basis"] = attribution_from_fix(f["fix"])
    return attempts


def tc_verdict(atts):
    last = atts[-1]
    k = last["verdict"]
    if k in ("INCONCLUSIVE", "PARTIAL"):
        return "%s(%s)" % (k, last["reason"] or "사유 미기재")
    if k == "FAIL":
        return "INCONCLUSIVE(수정 후 재검증 기록 없음)" if last["fixes"] else "FAIL"
    # PASS
    if len(atts) == 1:
        return "CLEAN PASS"
    priors = atts[:-1]
    if any(p["verdict"] == "FAIL" and not p["fixes"] for p in priors):
        return "INCONCLUSIVE(수정 없이 재시도 통과)"
    if all(p["verdict"] in ("INCONCLUSIVE", "PARTIAL") for p in priors):
        return "INCONCLUSIVE(선행 시도 판정 불확정)"
    fixes = sum(len(p["fixes"]) for p in priors)
    return "PASS (after %d fixes)" % fixes


def verdict_class(v):
    if v == "CLEAN PASS":
        return "CLEAN PASS"
    if v.startswith("PASS (after"):
        return "PASS (after fixes)"
    if v.startswith("INCONCLUSIVE"):
        return "INCONCLUSIVE"
    if v.startswith("PARTIAL"):
        return "PARTIAL"
    return "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_report")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--branch", default="")
    ap.add_argument("--level", required=True, choices=["smoke", "full"])
    ap.add_argument("--level-note", default="")
    ap.add_argument("--status", required=True, choices=["DONE", "BLOCKED:MAX_ITERATIONS", "BLOCKED:NO_PROGRESS"])
    args = ap.parse_args()

    if not os.path.isfile(args.run_report):
        print("오류: 입력 파일 없음: %s" % args.run_report, file=sys.stderr)
        return 2
    raw = open(args.run_report, "rb").read()
    text = raw.decode("utf-8", errors="replace")
    diags = []
    missing = []  # 필수 입력 결여 항목
    if "�" in text and b"\xef\xbf\xbd" not in raw:
        diags.append("인코딩 치환 발생(U+FFFD)")
    if not text.strip():
        missing.append("입력 비어있음")

    secs = sections(text)
    head = secs.get("", [])
    title = ""
    main_flow = ""
    header_level = ""
    created = ""
    for ln in head:
        m = re.match(r"^#\s+E2E 테스트 실행 리포트\s*(?:—|-)?\s*(.*)$", ln)
        if m:
            title = m.group(1).strip() or "(대상 미기재)"
        m = re.match(r"^>\s*E2E 메인 플로우\s*[:：]\s*(.*)$", ln)
        if m:
            main_flow = m.group(1).strip()
        m = re.match(r"^>\s*수준\s*[:：]\s*(.*)$", ln)
        if m:
            header_level = m.group(1).strip()
        m = re.match(r"^>\s*생성\s*[:：]\s*(.*)$", ln)
        if m:
            created = m.group(1).strip()
    if not title and text.strip():
        missing.append("헤더(# E2E 테스트 실행 리포트)")
    if not main_flow and text.strip():
        missing.append("E2E 메인 플로우 줄")

    # 대상 엔드포인트
    targets = []
    if "테스트 대상 엔드포인트" in secs:
        for ln in secs["테스트 대상 엔드포인트"]:
            for m in REQ_RE.finditer(ln):
                targets.append((m.group(1), m.group(2)))
        if not targets:
            missing.append("테스트 대상 엔드포인트 항목(0건)")
    elif text.strip():
        missing.append("## 테스트 대상 엔드포인트")

    # Iteration 기록
    attempts = []
    if "Iteration 기록" in secs:
        attempts = parse_iterations(secs["Iteration 기록"], diags)
    elif text.strip():
        missing.append("## Iteration 기록")

    # 최종 요약
    unresolved = []
    uncovered = []
    smoke_omitted = []
    total_iter = ""
    total_tests = ""
    if "최종 요약" in secs:
        S = secs["최종 요약"]
        total_iter = bullet(S, "총 iteration") or ""
        total_tests = bullet(S, "총 테스트") or ""
        u = bullet(S, "미해결 이슈")
        if u is None:
            missing.append("최종 요약 `- 미해결 이슈:` 줄")
        elif u.strip() not in ("없음", "-", ""):
            unresolved = [x.strip() for x in re.split(r"\s*/\s*|,\s*|;\s*", u) if x.strip()]
        c = bullet(S, "커버리지")
        if c is None:
            missing.append("최종 요약 `- 커버리지:` 줄")
        else:
            for m in re.finditer(r"UNCOVERED\s*[:：]?\s*([A-Z]+-\d+)\s*(?:\(([^)]*)\))?", c):
                uncovered.append((m.group(1), (m.group(2) or "").strip()))
            m = re.search(r"SMOKE_OMITTED\s*[:：]?\s*([A-Za-z0-9\-~,\s]+)", c)
            if m:
                smoke_omitted = [x.strip() for x in re.split(r",\s*|\s+", m.group(1).strip()) if x.strip() and x.strip() != "/"]
    elif text.strip():
        missing.append("## 최종 요약")

    # TC 그룹핑
    tcs = []
    index = {}
    for a in attempts:
        key = (a["cat"], a["name"])
        if key not in index:
            index[key] = len(tcs)
            tcs.append({"cat": a["cat"], "name": a["name"], "atts": []})
        tcs[index[key]]["atts"].append(a)
    for i, tc in enumerate(tcs, 1):
        tc["id"] = "TC-%02d" % i
        tc["verdict"] = tc_verdict(tc["atts"])
        tc["class"] = verdict_class(tc["verdict"])
        fixes = [f for a in tc["atts"] for f in a["fixes"]]
        attrs = sorted(set(f["attr"] for f in fixes))
        if not fixes:
            tc["attr"], tc["attr_basis"] = "-", "수정 없음"
        elif len(attrs) == 1:
            tc["attr"], tc["attr_basis"] = attrs[0], fixes[0]["attr_basis"]
        else:
            tc["attr"], tc["attr_basis"] = "혼합", "수정 블록 귀속 상이: " + ", ".join(attrs)

    # 케이스 연속성 검증
    iters = sorted(set(a["iter"] for a in attempts))
    by_iter = {}
    first_iter = {}
    for a in attempts:
        by_iter.setdefault(a["iter"], set()).add((a["cat"], a["name"]))
        first_iter.setdefault((a["cat"], a["name"]), a["iter"])
    for k_idx, k in enumerate(iters[:-1]):
        nxt = iters[k_idx + 1]
        for a in attempts:
            if a["iter"] == k and a["verdict"] == "FAIL" and a["fixes"] and (a["cat"], a["name"]) not in by_iter.get(nxt, set()):
                newcomers = [key for key in by_iter.get(nxt, set()) if first_iter.get(key) == nxt]
                if newcomers:
                    nm = newcomers[0]
                    diags.append("케이스 연속성 위반 의심: %s — %s → %s — %s?" % (a["cat"], a["name"], nm[0], nm[1]))
                    break

    if text.strip() and "Iteration 기록" in secs and not attempts:
        diags.append("파싱 실패: 파싱 가능한 케이스 없음")

    # 호출·미호출
    called = set()
    for a in attempts:
        if a["req"]:
            m = REQ_RE.search(a["req"])
            if m:
                called.add((m.group(1), norm_path(m.group(2))))
    uncalled = [t for t in targets if (t[0], norm_path(t[1])) not in called]

    # 집계
    counts = {"CLEAN PASS": 0, "PASS (after fixes)": 0, "FAIL": 0, "INCONCLUSIVE": 0, "PARTIAL": 0}
    for tc in tcs:
        counts[tc["class"]] += 1
    hard = []
    if counts["FAIL"]:
        hard.append("FAIL TC %d건" % counts["FAIL"])
    if counts["INCONCLUSIVE"]:
        hard.append("INCONCLUSIVE TC %d건" % counts["INCONCLUSIVE"])
    if counts["PARTIAL"]:
        hard.append("PARTIAL TC %d건" % counts["PARTIAL"])
    if uncovered:
        hard.append("UNCOVERED %d건" % len(uncovered))
    if unresolved:
        hard.append("미해결 이슈 %d건" % len(unresolved))
    if uncalled:
        hard.append("미호출 엔드포인트 %d건" % len(uncalled))
    if missing:
        hard.append("필수 입력 결여 %d건" % len(missing))
    if not tcs:
        hard.append("실행된 케이스 0건")
    fixed_pass = counts["PASS (after fixes)"]
    if not hard and fixed_pass == 0 and not smoke_omitted and args.status == "DONE":
        answer, why = "예", ["경성 결함 0건, 수정 후 통과 0건, SMOKE_OMITTED 0건, 종료 DONE"]
    elif not hard and args.status == "DONE":
        answer, why = "조건부 예", []
        if fixed_pass:
            why.append("수정 후 통과 %d건 (1차 시도 실패 이력)" % fixed_pass)
        if smoke_omitted:
            why.append("SMOKE_OMITTED %d건 (범용 시나리오 미실행)" % len(smoke_omitted))
    else:
        answer, why = "아니오", list(hard)
        if args.status != "DONE":
            why.append("종료 상태 %s" % args.status)
    if args.level == "smoke" and answer == "예":
        answer, why = "조건부 예 (smoke 범위)", ["smoke 실행 — BASE-02~05 범용 시나리오는 검증되지 않음"] + why
    elif args.level == "smoke" and answer == "조건부 예":
        answer = "조건부 예 (smoke 범위)"

    status_reasons = []
    if missing:
        status_reasons.append("필수 입력 결여: " + "; ".join(missing))
    status_reasons.extend(d for d in diags if d.startswith("파싱 실패") or d.startswith("케이스 연속성") or d.startswith("귀속 불가"))
    status = "OK" if not status_reasons else "DEGRADED(%s)" % " | ".join(status_reasons)

    today = _dt.date.today().isoformat()
    level_txt = args.level + (("(smoke 미적용: %s)" % args.level_note) if args.level_note else "")
    branch = args.branch or "e2e"
    out = []
    out.append("---")
    out.append('title: "E2E 리포트 — %s"' % (title or branch).replace('"', "'"))
    out.append("type: report")
    out.append("tags: [e2e-report, harness, %s]" % slug(branch))
    out.append("status: active")
    out.append("created: %s" % today)
    out.append("updated: %s" % today)
    out.append("level: %s" % args.level)
    out.append("loop_status: %s" % args.status)
    out.append('verdict: "%s"' % answer)
    out.append("---")
    out.append("")
    out.append("# E2E 자기 점검 리포트 — %s" % (title or "(대상 미기재)"))
    out.append("")
    out.append("- 브랜치: `%s`" % branch)
    out.append("- E2E 메인 플로우: %s" % (main_flow or "(기록 없음)"))
    out.append("- 실행 수준: %s%s" % (level_txt, (" (헤더 기록: %s)" % header_level) if header_level and header_level != args.level else ""))
    out.append("- 종료 상태: %s" % args.status)
    out.append("- 원시 기록: %s · 총 iteration %s · 총 테스트 %s · 생성 %s" % (os.path.abspath(args.run_report), total_iter or "?", total_tests or "?", created or "?"))
    out.append("")
    out.append("## 정직한 결론")
    out.append("")
    out.append("**아무 의심 없이 성공인가? — %s**" % answer)
    for w in why:
        out.append("- %s" % w)
    out.append("")
    out.append("## 요약")
    out.append("")
    out.append("| verdict | 건수 |")
    out.append("|---------|------|")
    for k in ("CLEAN PASS", "PASS (after fixes)", "FAIL", "INCONCLUSIVE", "PARTIAL"):
        out.append("| %s | %d |" % (k, counts[k]))
    out.append("")
    out.append("- 대상 엔드포인트 %d건 / 호출 %d건 / 미호출 %d건" % (len(targets), len(targets) - len(uncalled), len(uncalled)))
    out.append("- UNCOVERED %d건 / SMOKE_OMITTED %d건 / 미해결 이슈 %d건" % (len(uncovered), len(smoke_omitted), len(unresolved)))
    out.append("")
    out.append("## 결함 귀속")
    out.append("")
    out.append("| TC | verdict | 귀속 | 근거 |")
    out.append("|----|---------|------|------|")
    for tc in tcs:
        if tc["attr"] != "-" or tc["class"] not in ("CLEAN PASS",):
            out.append("| %s | %s | %s | %s |" % (tc["id"], tc["verdict"], tc["attr"], tc["attr_basis"].replace("|", "\\|")))
    if not tcs:
        out.append("| - | - | - | 케이스 없음 |")
    out.append("")
    out.append("## 테스트 케이스")
    out.append("")
    for tc in tcs:
        out.append("### %s %s — %s [%s]" % (tc["id"], tc["cat"], tc["name"], tc["verdict"]))
        out.append("")
        out.append("| 차수 | iteration | 요청 | 기대 | 실제 | 판정 |")
        out.append("|------|-----------|------|------|------|------|")
        for n, a in enumerate(tc["atts"], 1):
            v = a["verdict"] + (("(%s)" % a["reason"]) if a["reason"] else "")
            cells = [str(n), str(a["iter"]), a["req"] or "(결여)", a["exp"] or "(결여)", a["act"] or "(결여)", v]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        fixes = [(n, f) for n, a in enumerate(tc["atts"], 1) for f in a["fixes"]]
        if fixes:
            out.append("")
            out.append("수정 이력:")
            for n, f in fixes:
                out.append("- %d차 시도 후 — 원인: %s / 수정: %s / 귀속: %s (%s) / 재빌드·재시작: %s" % (
                    n, f["cause"], f["fix"] or "(미기재)", f["attr"], f["attr_basis"], f["rebuild"]))
        out.append("")
    if not tcs:
        out.append("(파싱 가능한 케이스 없음 — INCONCLUSIVE)")
        out.append("")
    out.append("## GAP / 한계")
    out.append("")
    gap = []
    for u in unresolved:
        gap.append("- 미해결 이슈: %s" % u)
    for tc in tcs:
        if tc["class"] == "FAIL":
            gap.append("- FAIL: %s %s — %s" % (tc["id"], tc["cat"], tc["name"]))
    for t in uncalled:
        gap.append("- 미호출 엔드포인트: `%s %s`" % t)
    for idv, why_u in uncovered:
        gap.append("- UNCOVERED: %s%s" % (idv, (" (%s)" % why_u) if why_u else ""))
    if smoke_omitted:
        gap.append("- SMOKE_OMITTED: %s (smoke — 범용 시나리오 미실행)" % ", ".join(smoke_omitted))
    for m in missing:
        gap.append("- 필수 입력 결여: %s" % m)
    out.extend(gap if gap else ["기록 없음 — 리포트는 실행된 케이스만 증명한다"])
    out.append("")
    out.append("## 루프 이력")
    out.append("")
    out.append("| iteration | 케이스 | 통과 | 실패 | INCONCLUSIVE/PARTIAL | 수정 블록 |")
    out.append("|-----------|--------|------|------|----------------------|-----------|")
    for it in iters:
        A = [a for a in attempts if a["iter"] == it]
        out.append("| %d | %d | %d | %d | %d | %d |" % (
            it, len(A), sum(a["verdict"] == "PASS" for a in A), sum(a["verdict"] == "FAIL" for a in A),
            sum(a["verdict"] in ("INCONCLUSIVE", "PARTIAL") for a in A), sum(len(a["fixes"]) for a in A)))
    if not iters:
        out.append("| - | 0 | 0 | 0 | 0 | 0 |")
    out.append("")
    out.append("## 진단")
    out.append("")
    all_diags = (["필수 입력 결여: " + m for m in missing] + diags) or ["없음"]
    out.extend("- %s" % d for d in all_diags)
    if text.strip() and "Iteration 기록" in secs and not attempts:
        out.append("")
        out.append("## 원문 (파싱 실패 — verbatim)")
        out.append("")
        out.append("```markdown")
        out.append(text.rstrip("\n"))
        out.append("```")
    out.append("")

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(args.out_dir, "%s-%s-e2e-report" % (stamp, slug(branch)))
    path = base + ".md"
    n = 1
    while True:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            break
        except FileExistsError:
            n += 1
            path = "%s-%d.md" % (base, n)
        except OSError as e:
            print("오류: 파일 생성 실패: %s" % e, file=sys.stderr)
            return 2
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("경로: %s" % os.path.abspath(path))
    print("상태: %s" % status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
