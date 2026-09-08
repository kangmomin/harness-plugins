#!/usr/bin/env python3
r"""workflow_archive.py — Phase 12(fe 11 / 풀스택 11): 슬림 Workflow Report + 상태 파일 + Implementation Notes → md 아카이브 1개 (stdlib only).

계약 (canonical — templates.md는 호출법만 둔다):
  사용법: workflow_archive.py report --src WORK_REPORT --state STATE_FILE --run-id ID --report-dir DIR --task NAME
          [--results RESULTS_JSON] [--impl-notes IMPL_NOTES] [--start-sha SHA] [--require-headings "h1,h2,…"]
  종료:   파일을 썼으면(또는 같은 run_id 파일을 재사용하면) exit 0 + stdout `경로: …` / `상태: OK|DEGRADED({사유})`.
          입력 파일 부재·인자 오류·쓰기 실패 → exit 2.
  출력:   {DIR}/{YYYYMMDD}-{slug(task)}-{run_id}-workflow-report.md
          = frontmatter(title/type/tags/status/created/updated/run_id + 파싱 가능 시 tier/escalated/regression_count/touched_paths)
          + 보고서 본문(sentinel 이하 제거 후) + `## 부록 A: 실행 요약` + `## 부록 B: 상태 파일 전문`(헤딩 1단계 강등) + `## 부록 C: Implementation Notes`.
  재사용: report-dir의 같은 run_id 파일을 날짜/task와 무관하게 찾고 저장된 archive_status를 보존한다. 기존 파일 frontmatter `run_id`가 인자와 같으면 재생성하지 않고 그 경로를 출력(동일 실행 재시도). 다르면 `-2`, `-3` 접미로 새로 생성.
  쓰기:   임시 파일 작성 → 배타적 링크; 미지원 시 exit2, replace 폴백 없음 (덮어쓰기 없음, 생성 후 수정 없음).
  검증:   --require-headings 의 각 항목이 본문 헤딩(#… 텍스트가 항목으로 시작)에 없으면 `### {항목} (INCOMPLETE)` 삽입 + DEGRADED(머리글 누락).
          impl-notes 4 머리글(설계 결정/편차/트레이드오프/미결 질문) 누락 → 플레이스홀더 + DEGRADED.
  touched_paths: --start-sha(없으면 상태 파일 `시작 커밋`/`START_SHA`) 기준 `git diff --name-only SHA` ∪ untracked, 제외 패턴은 verification-tier.md ②와 동일.
"""
import argparse
import datetime as _dt
import fnmatch
import fcntl
import json
from pathlib import Path
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from workflow_results import load as load_results, latest, publish_text

SENTINEL = "<!-- workflow-archive: appendix -->"
IMPL_HEADINGS = ["설계 결정", "편차", "트레이드오프", "미결 질문"]
EXCLUDE_GLOBS = ["*_test.go", "*.test.*", "*.spec.*", "__tests__/*", "*/__tests__/*", "testdata/*", "*/testdata/*", "e2e/*", "*/e2e/*",
                 "vendor/*", "*/vendor/*", "node_modules/*", "*/node_modules/*", "*.pb.go", "*.gen.*", "mocks/*", "*/mocks/*", "__pycache__/*", "*/__pycache__/*", "*.pyc", "*.md", "docs/*", "*/docs/*"]


def slug(s):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip("-")
    return s or "task"


def read(path):
    return Path(path).read_bytes().decode("utf-8", errors="replace")


def git(args, raw=False):
    try:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, timeout=30).stdout.rstrip(b"\n")
        r = subprocess.run(["git", "-C", os.fsdecode(root)] + args, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout if raw else r.stdout.decode("utf-8", errors="surrogateescape")) if r.returncode == 0 else None


def split_frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n)?", text, re.S)
    if not m:
        return [], text
    return m.group(1).splitlines(), text[m.end():]


def fm_get(lines, key):
    for ln in lines:
        m = re.match(r"^%s:\s*(.*)$" % re.escape(key), ln)
        if m:
            value = m.group(1).strip()
            if value.startswith('"'):
                return json.loads(value)
            if value.startswith("'") and value.endswith("'"):
                return value[1:-1].replace("''", "'")
            return value
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
    diff = git(["diff", "--no-relative", "--name-only", "-z", sha, "--"], raw=True)
    untracked = git(["ls-files", "--others", "--exclude-standard", "-z"], raw=True)
    if diff is None or untracked is None:
        return None
    paths = {os.fsdecode(name) for name in (diff + untracked).split(b"\0") if name}
    return sorted(p for p in paths if not excluded(p))


def update_frontmatter(lines, values):
    blocks, seen = [], set()
    for line in lines:
        match = re.match(r'^("(?:\\.|[^"\\])*"|\w[\w-]*):', line)
        if match:
            key = json.loads(match[1]) if match[1].startswith('"') else match[1]
            if key in seen:
                raise ValueError("duplicate frontmatter key: " + key)
            seen.add(key)
            blocks.append([key, [line]])
        elif not line.strip() or line.startswith((" ", "\t", "#")):
            if not blocks:
                blocks.append([None, []])
            blocks[-1][1].append(line)
        else:
            raise ValueError("unsupported frontmatter layout")
    out = [line for key, block in blocks if key not in values for line in block]
    out.extend(key + ": " + json.dumps(value, ensure_ascii=True) for key, value in values.items())
    return out


def final_results(data, rows, mode):
    if data is not None:
        selected = list(latest(data).values())
        return {kind: [event for event in selected if event["kind"] == kind] for kind in ("unit", "integration", "e2e", "readback")}
    # Legacy migration view only: paired values come from the SAME last row.
    phases = {"be": {"unit": "8.1", "integration": "8.7", "e2e": "8.6"},
              "fe": {"unit": "7.1", "e2e": "7.4"},
              "fs": {"unit": "7", "e2e": "8.2", "readback": "8.1"}}.get(mode, {})
    out = {kind: [] for kind in ("unit", "integration", "e2e", "readback")}
    for kind, phase in phases.items():
        matches = [row for row in rows if len(row) >= 3 and row[0] == phase]
        if not matches:
            continue
        row = matches[-1]
        verdicts = re.findall(r"\b(PASS|WARN|FAIL)\b", row[2])
        verdict = next((v for v in ("FAIL", "WARN", "PASS") if v in verdicts), "INCONCLUSIVE")
        event = dict(domain=mode, kind=kind, phase=phase, verdict=verdict, terminal_state=row[1])
        count = re.search(r"regression\s*\[?(\d+)\]?\s*건", row[2])
        if count:
            event["regression_count"] = int(count[1])
        out[kind].append(event)
    return out


def describe_results(events):
    return "; ".join("%s Phase %s %s%s" % (e["domain"], e["phase"], e["verdict"],
        " · regression: %s" % e.get("regression_count", "기록 없음") if e["kind"] in ("unit", "integration") else "") for e in events) or "기록 없음"


def archive_main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["report"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--impl-notes", default=None)
    ap.add_argument("--results")
    ap.add_argument("--start-sha", default=None)
    ap.add_argument("--require-headings", default=None)
    args = ap.parse_args()

    for p in (args.src, args.state) + ((args.impl_notes,) if args.impl_notes else ()):
        if not os.path.isfile(p):
            print("오류: 입력 파일 없음: %s" % p, file=sys.stderr)
            return 2
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", args.run_id):
        raise ValueError("invalid run_id")
    evidence = load_results(args.results, args.run_id) if args.results else None
    degraded = [] if evidence is not None else ["구조화된 결과 없음 — legacy 요약은 검증 증거가 아님"]
    today = _dt.date.today().isoformat()
    src = read(args.src)
    state = read(args.state)
    impl = read(args.impl_notes) if args.impl_notes else None

    fm_lines, body = split_frontmatter(src)
    source_run = fm_get(fm_lines, "run_id")
    state_run = kv(section(state, "Run"), "RUN_ID")
    if source_run not in (None, args.run_id) or state_run not in (None, args.run_id):
        raise ValueError("source/state/CLI run_id mismatch")
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
    if evidence is not None:
        if mode in ("be", "fe", "fs") and mode != evidence["domain"]:
            raise ValueError("state/result domain mismatch")
        if mode in ("analyze", "verify") and mode != evidence["mode"]:
            raise ValueError("state/result mode mismatch")
        if evidence["terminal_state"] != "DONE":
            raise ValueError("unfinished run must retain live results before permanent archive")
    start_sha = args.start_sha or kv(flags, "START_SHA") or kv(vt, "시작 커밋")
    if start_sha in ("없음", "{START_SHA}"):
        start_sha = None
    esc_rows = [r for r in table_rows(vt) if r and not r[0].startswith("{") and not r[0].startswith("[")] if vt else []
    escalated = None
    if vt is not None:
        escalated = bool(esc_rows) or "tier_escalated" in state
    pr = section(state, "Phase Results")
    pr_rows = table_rows(pr) if pr else []
    final = final_results(evidence, pr_rows, mode)
    counts = [event.get("regression_count") for event in final["unit"] + final["integration"]]
    regression_count = sum(counts) if counts and all(isinstance(c, int) for c in counts) else None
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

    # Owned metadata is replaced once; unknown blocks remain untouched.
    owned = dict(run_id=args.run_id, type="report", status="active", updated=today,
                 archive_status="DEGRADED" if degraded else "OK", archive_diagnostics=degraded,
                 result_summary=final)
    for key, value in (("created", today), ("title", args.task + " 워크플로우 리포트"),
                       ("tags", ["workflow-report", "harness", slug(args.task)])):
        if fm_get(fm_lines, key) is None:
            owned[key] = value
    if evidence is not None:
        owned.update(result_schema_version=evidence["schema_version"], tested_tree=evidence["tested_tree"], terminal_state=evidence["terminal_state"])
    if tier:
        owned["tier"] = tier
    if escalated is not None:
        owned["escalated"] = escalated
    owned["regression_count"] = regression_count
    owned["touched_paths"] = tp
    fm = update_frontmatter(fm_lines, owned)

    # 부록 A
    a = ["## 부록 A: 실행 요약", ""]
    a.append("- run_id: `%s` · MODE: %s · 상태 파일: `%s`" % (args.run_id, mode or "기록 없음", os.path.abspath(args.state)))
    a.append("- 시작 커밋: %s · 종료 커밋: %s" % (start_sha or "기록 없음", head or "기록 없음"))
    a.append("- Flags: %s" % (" / ".join(l.strip().lstrip("- ") for l in (flags or "").splitlines() if l.strip().startswith("-")) or "기록 없음"))
    a.append("- 검증 티어: %s" % (tier or "기록 없음"))
    a.append("- 승격 이력: %s" % ("; ".join(" | ".join(r) for r in esc_rows) if esc_rows else ("없음" if vt is not None else "기록 없음")))
    a.append("- 최종 테스트 판정: " + describe_results(final["unit"] + final["integration"]))
    a.append("- E2E: " + describe_results(final["e2e"]))
    a.append("- Read-back: " + describe_results(final["readback"]))
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

    # Run identity survives date/task changes. Reused completeness is never upgraded.
    directory = Path(args.report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(directory / ".workflow-archive.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "a+b") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        if directory.exists():
            for candidate in sorted(directory.glob("*-workflow-report*.md")):
                if candidate.is_symlink():
                    continue
                existing, _ = split_frontmatter(read(candidate))
                if fm_get(existing, "run_id") == args.run_id:
                    saved = fm_get(existing, "archive_status") or "DEGRADED"
                    reasons = fm_get(existing, "archive_diagnostics") or "legacy archive completeness unknown"
                    print("경로: %s" % candidate.resolve())
                    print("상태: %s(재사용%s)" % (saved, " — " + str(reasons) if saved != "OK" else ""))
                    return 0
        base = "%s-%s-%s-workflow-report" % (_dt.datetime.now().strftime("%Y%m%d"), slug(args.task), args.run_id)
        path = publish_text(directory, base, doc)
        print("경로: %s" % path)
        print("상태: %s" % ("OK" if not degraded else "DEGRADED(%s)" % " | ".join(degraded)))
        return 0


def main():
    try:
        return archive_main()
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("오류: 아카이브 생성 실패: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
