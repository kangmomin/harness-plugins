#!/usr/bin/env python3
r"""workflow_archive.py — Phase 12(fe 11 / 풀스택 11): 슬림 Workflow Report + 상태 파일 + Implementation Notes → md 아카이브 1개 (stdlib only).

계약 (canonical — templates.md는 호출법만 둔다):
  사용법: workflow_archive.py report --src WORK_REPORT --state STATE_FILE --run-id ID --report-dir DIR --task NAME
          [--impl-notes IMPL_NOTES] [--start-sha SHA] [--require-headings "h1,h2,…"]
  종료:   파일을 썼으면(또는 같은 run_id 파일을 재사용하면) exit 0 + stdout `경로: …` / `상태: OK|DEGRADED({사유})`.
          입력 파일 부재·인자 오류·쓰기 실패 → exit 2.
  출력:   {DIR}/{YYYYMMDD}-{slug(task)}-{run_id}-workflow-report.md
          = frontmatter(title/type/tags/status/created/updated/run_id + 파싱 가능 시 tier/escalated/regression_count/touched_paths)
          + 보고서 본문(sentinel 이하 제거 후) + `## 부록 A: 실행 요약` + `## 부록 B: 상태 파일 전문`(헤딩 1단계 강등) + `## 부록 C: Implementation Notes`.
  재사용: 같은 경로의 기존 파일 frontmatter `run_id`가 인자와 같으면 재생성하지 않고 그 경로를 출력(동일 실행 재시도). 다르면 `-2`, `-3` 접미로 새로 생성.
  쓰기:   임시 파일 작성 → 배타적 링크/이름 변경 (덮어쓰기 없음, 생성 후 수정 없음).
  검증:   --require-headings 의 각 항목이 본문 헤딩(#… 텍스트가 항목으로 시작)에 없으면 `### {항목} (INCOMPLETE)` 삽입 + DEGRADED(머리글 누락).
          impl-notes 4 머리글(설계 결정/편차/트레이드오프/미결 질문) 누락 → 플레이스홀더 + DEGRADED.
  touched_paths: --start-sha(없으면 상태 파일 `시작 커밋`/`START_SHA`) 기준 `git diff --name-only SHA` ∪ untracked, 제외 패턴은 verification-tier.md ②와 동일.
"""
import argparse
import datetime as _dt
import fnmatch
import os
import re
import subprocess
import sys

SENTINEL = "<!-- workflow-archive: appendix -->"
IMPL_HEADINGS = ["설계 결정", "편차", "트레이드오프", "미결 질문"]
EXCLUDE_GLOBS = ["*_test.go", "*.test.*", "*.spec.*", "__tests__/*", "*/__tests__/*", "testdata/*", "*/testdata/*", "e2e/*", "*/e2e/*",
                 "vendor/*", "*/vendor/*", "node_modules/*", "*/node_modules/*", "*.pb.go", "*.gen.*", "mocks/*", "*/mocks/*", "__pycache__/*", "*/__pycache__/*", "*.pyc", "*.md", "docs/*", "*/docs/*"]


def slug(s):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip("-")
    return s or "task"


def read(path):
    return open(path, "rb").read().decode("utf-8", errors="replace")


def git(args):
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return [], text
    return m.group(1).splitlines(), text[m.end():]


def fm_get(lines, key):
    for ln in lines:
        m = re.match(r"^%s:\s*(.*)$" % re.escape(key), ln)
        if m:
            return m.group(1).strip().strip('"')
    return None


def section(text, title):
    m = re.search(r"^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(title), text, re.M | re.S)
    return m.group(1) if m else None


def kv(sec, key):
    if sec is None:
        return None
    m = re.search(r"^\s*-\s*%s\s*[:：]\s*(.*)$" % re.escape(key), sec, re.M)
    return m.group(1).strip() if m else None


def table_rows(sec):
    rows = []
    if not sec:
        return rows
    for ln in sec.splitlines():
        if ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells and not set(cells[0]) <= set("-: "):
                rows.append(cells)
    return rows[1:] if rows else rows  # 헤더 제거


def demote(text):
    return re.sub(r"^(#{1,5})\s", lambda m: "#" + m.group(1) + " ", text, flags=re.M)


def excluded(path):
    return any(fnmatch.fnmatch(path, g) for g in EXCLUDE_GLOBS)


def touched_paths(sha):
    if not sha or git(["cat-file", "-e", sha]) is None:
        return None
    diff = git(["diff", "--name-only", sha])
    untracked = git(["ls-files", "--others", "--exclude-standard"])
    if diff is None or untracked is None:
        return None
    paths = set(l.strip() for l in (diff + "\n" + untracked).splitlines() if l.strip())
    return sorted(p for p in paths if not excluded(p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["report"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--impl-notes", default=None)
    ap.add_argument("--start-sha", default=None)
    ap.add_argument("--require-headings", default=None)
    args = ap.parse_args()

    for p in (args.src, args.state) + ((args.impl_notes,) if args.impl_notes else ()):
        if not os.path.isfile(p):
            print("오류: 입력 파일 없음: %s" % p, file=sys.stderr)
            return 2
    degraded = []
    today = _dt.date.today().isoformat()
    src = read(args.src)
    state = read(args.state)
    impl = read(args.impl_notes) if args.impl_notes else None

    fm_lines, body = split_frontmatter(src)
    if SENTINEL in body:
        body = body[:body.index(SENTINEL)]
    body = body.rstrip() + "\n"

    # 머리글 검증
    if args.require_headings:
        heads = [h.strip() for h in args.require_headings.split(",") if h.strip()]
        present = [re.sub(r"^#{1,6}\s*", "", ln).strip() for ln in body.splitlines() if re.match(r"^#{1,6}\s", ln)]
        missing = [h for h in heads if not any(t.startswith(h) for t in present)]
        if missing:
            body += "\n" + "\n".join("### %s (INCOMPLETE)\n(INCOMPLETE)\n" % h for h in missing)
            degraded.append("머리글 누락: " + ", ".join(missing))

    # 상태 파일 파싱
    flags = section(state, "Flags")
    vt = section(state, "Verification Tier")
    tier = kv(flags, "TIER") or (kv(vt, "최종 티어") or "").split(" ")[0] or None
    mode = kv(flags, "MODE")
    start_sha = args.start_sha or kv(flags, "START_SHA") or kv(vt, "시작 커밋")
    if start_sha in ("없음", "{START_SHA}"):
        start_sha = None
    esc_rows = [r for r in table_rows(vt) if r and not r[0].startswith("{") and not r[0].startswith("[")] if vt else []
    escalated = None
    if vt is not None:
        escalated = bool(esc_rows) or "tier_escalated" in state
    pr = section(state, "Phase Results")
    pr_rows = table_rows(pr) if pr else []
    regression_count = None
    m = re.search(r"regression\s*\[?(\d+)\]?\s*건", state)
    if m:
        regression_count = int(m.group(1))
    test_verdict = None
    e2e_row = None
    for r in pr_rows:
        if len(r) >= 3 and r[0].startswith("8.1"):
            mv = re.search(r"\b(PASS|WARN|FAIL)\b", r[2])
            if mv:
                test_verdict = mv.group(1)
        if len(r) >= 3 and r[0].startswith("8.6"):
            e2e_row = "%s — %s" % (r[1], r[2])
    artifacts = section(state, "Artifacts")
    open_q = None
    impl_missing = []
    if impl is not None:
        for h in IMPL_HEADINGS:
            if not re.search(r"^##\s+%s\s*$" % re.escape(h), impl, re.M):
                impl_missing.append(h)
        sec_q = section(impl, "미결 질문")
        open_q = len([l for l in (sec_q or "").splitlines() if re.match(r"^\s*-\s+", l) and not l.strip().startswith("<!--")])
        if impl_missing:
            impl += "\n" + "\n".join("## %s\n(INCOMPLETE)\n" % h for h in impl_missing)
            degraded.append("impl-notes 머리글 누락: " + ", ".join(impl_missing))
    tp = touched_paths(start_sha)
    commits = git(["log", "--format=- %h %s", "%s..HEAD" % start_sha]) if start_sha and git(["cat-file", "-e", start_sha]) is not None else None
    head = (git(["rev-parse", "HEAD"]) or "").strip() or None

    # frontmatter
    if fm_lines:
        fm = list(fm_lines)
        for k, v in (("run_id", args.run_id), ("type", "report"), ("status", "active"), ("created", today), ("updated", today)):
            if fm_get(fm, k) is None:
                fm.append("%s: %s" % (k, v))
        if fm_get(fm, "title") is None:
            fm.append('title: "%s 워크플로우 리포트"' % args.task.replace('"', "'"))
        if fm_get(fm, "tags") is None:
            fm.append("tags: [workflow-report, harness, %s]" % slug(args.task))
    else:
        fm = ['title: "%s 워크플로우 리포트"' % args.task.replace('"', "'"), "type: report",
              "tags: [workflow-report, harness, %s]" % slug(args.task), "status: active",
              "created: %s" % today, "updated: %s" % today, "run_id: %s" % args.run_id]
    if tier:
        fm.append("tier: %s" % tier)
    if escalated is not None:
        fm.append("escalated: %s" % ("true" if escalated else "false"))
    if regression_count is not None:
        fm.append("regression_count: %d" % regression_count)
    if tp is not None:
        fm.append("touched_paths:")
        fm.extend("  - %s" % p for p in tp)

    # 부록 A
    a = ["## 부록 A: 실행 요약", ""]
    a.append("- run_id: `%s` · MODE: %s · 상태 파일: `%s`" % (args.run_id, mode or "기록 없음", os.path.abspath(args.state)))
    a.append("- 시작 커밋: %s · 종료 커밋: %s" % (start_sha or "기록 없음", head or "기록 없음"))
    a.append("- Flags: %s" % (" / ".join(l.strip().lstrip("- ") for l in (flags or "").splitlines() if l.strip().startswith("-")) or "기록 없음"))
    a.append("- 검증 티어: %s" % (tier or "기록 없음"))
    a.append("- 승격 이력: %s" % ("; ".join(" | ".join(r) for r in esc_rows) if esc_rows else ("없음" if vt is not None else "기록 없음")))
    a.append("- 최종 테스트 판정(8.1): %s · regression: %s" % (test_verdict or "기록 없음", regression_count if regression_count is not None else "기록 없음"))
    a.append("- E2E(8.6): %s" % (e2e_row or "기록 없음"))
    a.append("- 산출물: %s" % (" / ".join(l.strip().lstrip("- ") for l in (artifacts or "").splitlines() if l.strip().startswith("-")) or "기록 없음"))
    a.append("- 미결 질문: %s" % ("%d건" % open_q if open_q is not None else "기록 없음(impl-notes 미전달)"))
    a.append("- touched_paths: %s" % ("%d개 (frontmatter)" % len(tp) if tp is not None else "생략(시작 SHA 없음·도달 불가)"))
    a.append("")
    a.append("커밋 목록 (`%s..HEAD`):" % (start_sha or "?"))
    a.append("")
    a.append(commits.rstrip() if commits and commits.strip() else "- 기록 없음")
    a.append("")
    b = ["## 부록 B: 상태 파일 전문", "", demote(state).rstrip(), ""]
    c = ["## 부록 C: Implementation Notes", "", (demote(impl).rstrip() if impl is not None else "(impl-notes 미전달)"), ""]

    doc = "---\n" + "\n".join(fm) + "\n---\n" + body + "\n" + SENTINEL + "\n\n" + "\n".join(a + b + c)

    # 경로 결정 + 재사용 검사
    os.makedirs(args.report_dir, exist_ok=True)
    base = os.path.join(args.report_dir, "%s-%s-%s-workflow-report" % (_dt.datetime.now().strftime("%Y%m%d"), slug(args.task), args.run_id))
    path = base + ".md"
    n = 1
    while os.path.exists(path):
        ex_fm, _ = split_frontmatter(read(path))
        if fm_get(ex_fm, "run_id") == args.run_id:
            print("경로: %s" % os.path.abspath(path))
            print("상태: OK(재사용 — 같은 run_id 파일 존재)")
            return 0
        n += 1
        path = "%s-%d.md" % (base, n)
    tmp = path + ".tmp-%d" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(doc)
        try:
            os.link(tmp, path)
            os.unlink(tmp)
        except OSError:
            if os.path.exists(path):
                os.unlink(tmp)
                raise FileExistsError(path)
            os.replace(tmp, path)
    except OSError as e:
        print("오류: 파일 생성 실패: %s" % e, file=sys.stderr)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return 2
    print("경로: %s" % os.path.abspath(path))
    print("상태: %s" % ("OK" if not degraded else "DEGRADED(%s)" % " | ".join(degraded)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
