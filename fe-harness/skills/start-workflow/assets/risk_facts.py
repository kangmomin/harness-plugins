#!/usr/bin/env python3
"""risk_facts.py — Phase 2 B축(회귀 리스크) 근거 사실 수집 (stdlib only, 판단 없음).

계약 (canonical — verification-tier.md §1은 호출법만 둔다):
  사용법: risk_facts.py --paths p1 [p2 …] [--since 90d] [--report-dir DIR]
  종료:   결과(unknown 포함)를 출력하면 exit 0. 인자 오류만 exit 2.
  출력:   경로별 — 존재 / 최근 변경 커밋 수({since}) / 동반 테스트 존재 / 과거 워크플로우 리포트 일치(escalated·regression_count 집계).
          git 미설치·저장소 아님·조회 실패 → 해당 셀 `unknown` (게이트는 unknown을 높음으로 취급).
  과거 리포트 일치 규칙: {report-dir}/*-workflow-report.md frontmatter `touched_paths` 항목과 정확 일치 또는 디렉토리 prefix 일치.
"""
import argparse
import glob
import os
import re
import subprocess
import sys


def git(args, cwd=None):
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def since_to_git(s):
    m = re.match(r"^(\d+)([dwmy])$", s.strip())
    if not m:
        return s
    n, u = int(m.group(1)), m.group(2)
    return "%d %s ago" % (n, {"d": "days", "w": "weeks", "m": "months", "y": "years"}[u])


def commit_count(path, since):
    out = git(["log", "--since=%s" % since_to_git(since), "--format=%h", "--", path])
    if out is None:
        return "unknown"
    return str(len([l for l in out.splitlines() if l.strip()]))


TEST_PATTERNS = ("_test.go", ".test.", ".spec.", "__tests__")


def is_test_file(name):
    return any(p in name for p in TEST_PATTERNS)


def sibling_tests(path):
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            if "node_modules" in root or "/vendor" in root:
                continue
            if any(is_test_file(f) for f in files) or os.path.basename(root) == "__tests__":
                return "Y"
        return "N"
    if not os.path.isfile(path):
        return "unknown"
    d, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    cands = []
    if ext == ".go":
        cands.append(os.path.join(d, stem + "_test.go"))
    else:
        for e in (".test", ".spec"):
            cands.extend(glob.glob(os.path.join(d, stem + e + ".*")))
        cands.extend(glob.glob(os.path.join(d, "__tests__", stem + ".*")))
    return "Y" if any(os.path.exists(c) for c in cands) else "N"


def frontmatter(path):
    try:
        txt = open(path, "rb").read().decode("utf-8", errors="replace")
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}
    fm = {}
    key = None
    for ln in m.group(1).splitlines():
        mk = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if mk:
            key = mk.group(1)
            val = mk.group(2).strip()
            fm[key] = [] if val == "" else val
            continue
        ml = re.match(r"^\s*-\s+(.*)$", ln)
        if ml and key and isinstance(fm.get(key), list):
            fm[key].append(ml.group(1).strip().strip('"\''))
    return fm


def path_matches(p, item):
    p = p.rstrip("/")
    item = item.rstrip("/")
    return p == item or p.startswith(item + "/") or item.startswith(p + "/")


def history(path, report_dir):
    if not report_dir:
        return "unknown(report-dir 미지정)"
    if not os.path.isdir(report_dir):
        return "unknown(report-dir 없음)"
    n = esc = reg = 0
    for f in sorted(glob.glob(os.path.join(report_dir, "*-workflow-report.md"))):
        fm = frontmatter(f)
        tp = fm.get("touched_paths")
        if not isinstance(tp, list) or not any(path_matches(path, it) for it in tp):
            continue
        n += 1
        if str(fm.get("escalated", "")).lower() == "true":
            esc += 1
        try:
            reg += int(str(fm.get("regression_count", "0")))
        except ValueError:
            pass
    return "리포트 %d건 / 승격 %d건 / regression %d건" % (n, esc, reg) if n else "이력 없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+", required=True)
    ap.add_argument("--since", default="90d")
    ap.add_argument("--report-dir", default=None)
    args = ap.parse_args()
    in_repo = git(["rev-parse", "--is-inside-work-tree"]) is not None
    print("## risk_facts (since %s%s)" % (args.since, "" if in_repo else ", git 저장소 아님 — 커밋 수 unknown"))
    print("")
    print("| 경로 | 존재 | 최근 변경 커밋 | 동반 테스트 | 과거 워크플로우 이력 |")
    print("|------|------|---------------|-------------|---------------------|")
    for p in args.paths:
        exists = "Y" if os.path.exists(p) else "N"
        cc = commit_count(p, args.since) if in_repo and exists == "Y" else ("unknown" if in_repo else "unknown")
        if exists == "N":
            cc = "unknown(경로 없음)"
        tests = sibling_tests(p) if exists == "Y" else "unknown"
        print("| `%s` | %s | %s | %s | %s |" % (p, exists, cc, tests, history(p, args.report_dir)))
    print("")
    print("- 해석 규칙: `unknown`·동반 테스트 `N`은 B축 `변경 영역 기존 테스트` 높음, 최근 변경이 잦거나 과거 승격/regression 이력이 있으면 `기존 동작 변경 범위` 근거로 상향 검토. 판단은 오케스트레이터가 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
