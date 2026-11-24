#!/usr/bin/env python3
"""커밋 단위 Claude 사용량 기록·집계 helper (common mod 의 정본).

mod(`metrics.ts`)가 세션 구간 카운터를 stdin JSON 으로 넘기면 git 정보를 붙여 JSONL 1줄로 추가한다.
저장 위치는 repo 밖이다: $HARNESS_METRICS_DIR 또는 ~/.claude/harness-metrics/<repo>-<hash>/.
같은 repo 의 worktree 는 git common dir 기준으로 한 폴더를 쓴다 (전후 비교가 worktree 로 갈리지 않게).
Windows 기본 Python 에서도 동작해야 하므로 fcntl 을 쓰지 않는다.

사용:
  metrics.py record --cwd .        (stdin: 구간 JSON)
  metrics.py summary --cwd . [--recent 10]
  metrics.py label --cwd . [--set NAME | --clear]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

SCHEMA = 1
RECORDS = "commits.jsonl"
LABEL = "label"
TOKEN_KINDS = ("input", "output", "cacheRead", "cacheWrite")


def git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def store_dir(cwd):
    base = os.environ.get("HARNESS_METRICS_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "harness-metrics")
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        # git 2.31 미만은 --path-format 이 없다.
        rel = git(cwd, "rev-parse", "--git-common-dir")
        common = os.path.abspath(os.path.join(cwd, rel)) if rel else None
    if not common:
        raise SystemExit(fail("NOT_GIT_REPO", f"git 저장소가 아닙니다: {cwd}"))
    common = os.path.normcase(os.path.normpath(common))
    name = os.path.basename(os.path.dirname(common)) if os.path.basename(common) == ".git" else os.path.basename(common)
    digest = hashlib.sha256(common.encode("utf-8")).hexdigest()[:8]
    path = os.path.join(base, f"{name}-{digest}")
    os.makedirs(path, exist_ok=True)
    return path


def fail(status, error):
    print(json.dumps({"status": status, "error": error}, ensure_ascii=False), file=sys.stderr)
    return 2


def read_label(path):
    try:
        with open(os.path.join(path, LABEL), encoding="utf-8") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def plugin_version():
    manifest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude-plugin", "plugin.json")
    try:
        with open(manifest, encoding="utf-8") as f:
            return str(json.load(f).get("version") or "")
    except (OSError, ValueError):
        return ""


def commit_info(cwd, short, branch):
    """출력에서 읽은 짧은 sha 를 풀어서 제목·변경 줄 수를 붙인다. 풀 수 없으면 짧은 sha 만 남긴다."""
    info = {"sha": None, "short": short, "branch": branch, "subject": None, "files": None, "added": None, "deleted": None}
    full = git(cwd, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}")
    if not full:
        return info
    info["sha"] = full
    info["subject"] = git(cwd, "log", "-1", "--format=%s", full)
    numstat = git(cwd, "show", "--numstat", "--format=", full)
    if numstat is not None:
        files = added = deleted = 0
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            files += 1
            # 바이너리 파일은 '-' 로 나온다. 줄 수에 넣지 않는다.
            added += int(parts[0]) if parts[0].isdigit() else 0
            deleted += int(parts[1]) if parts[1].isdigit() else 0
        info.update(files=files, added=added, deleted=deleted)
    return info


def cmd_record(args):
    try:
        segment = json.load(sys.stdin)
    except ValueError as err:
        return fail("BAD_INPUT", f"stdin JSON 을 읽지 못했습니다: {err}")
    if not isinstance(segment, dict):
        return fail("BAD_INPUT", "stdin 은 JSON 객체여야 합니다")
    path = store_dir(args.cwd)
    commits = []
    seen = set()
    for item in segment.get("commits") or []:
        short = str((item or {}).get("short") or "")
        if not short or short in seen:
            continue
        seen.add(short)
        info = commit_info(args.cwd, short, (item or {}).get("branch"))
        # -q 커밋의 HEAD 가 출력에서 읽은 커밋과 같으면 한 번만 넣는다.
        if info["sha"] and any(c["sha"] == info["sha"] for c in commits):
            continue
        if short == "HEAD" and info["sha"]:
            info["short"] = info["sha"][:7]
            info["branch"] = info["branch"] or git(args.cwd, "rev-parse", "--abbrev-ref", "HEAD")
        info["amend"] = bool((item or {}).get("amend"))
        commits.append(info)
    record = {
        "v": SCHEMA,
        "ts": int(time.time() * 1000),
        "label": read_label(path),
        "plugin": plugin_version(),
        **{k: v for k, v in segment.items() if k != "commits"},
        "commits": commits,
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    # 한 번의 write 로 1줄을 붙인다. 동시에 쓰는 세션이 있어도 줄이 섞이지 않게 한다.
    fd = os.open(os.path.join(path, RECORDS), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    print(json.dumps({"status": "OK", "dir": path, "commits": len(commits)}, ensure_ascii=False))
    return 0


def load(path):
    rows = []
    try:
        with open(os.path.join(path, RECORDS), encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # 잘린 줄은 건너뛴다.
                if isinstance(row, dict):
                    rows.append(row)
    except FileNotFoundError:
        pass
    return rows


def num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def total_tokens(row):
    tokens = row.get("tokens") or {}
    return sum(num((tokens.get(side) or {}).get(kind)) for side in ("main", "sub") for kind in TOKEN_KINDS)


def group_key(row):
    return row.get("label") or f"common@{row.get('plugin') or '?'}"


def summarize(rows, recent):
    groups = {}
    uncommitted = 0
    for row in rows:
        commits = row.get("commits") or []
        if not commits:
            uncommitted += 1
            continue
        g = groups.setdefault(group_key(row), {"commits": 0, "tokens": 0, "cost": 0.0, "activeMs": 0, "prompts": 0,
                                               "followUps": 0, "aborted": 0, "denied": 0, "reviews": 0, "lines": 0,
                                               "lineTokens": 0, "first": row.get("ts")})
        # --amend 는 같은 커밋을 고친 것이다. 토큰은 더하고 커밋 수·변경 줄 수는 다시 세지 않는다.
        fresh = [c for c in commits if not c.get("amend")]
        g["commits"] += len(fresh)
        g["tokens"] += total_tokens(row)
        g["cost"] += num(row.get("costUsd"))
        g["activeMs"] += num((row.get("time") or {}).get("activeMs"))
        user = row.get("input") or {}
        g["prompts"] += num(user.get("prompts"))
        g["followUps"] += num(user.get("followUps"))
        g["aborted"] += num(user.get("aborted"))
        g["denied"] += num(user.get("denied"))
        review = row.get("review") or {}
        g["reviews"] += num(review.get("agents")) + num(review.get("skills")) + num(review.get("codex"))
        # 줄 수를 모르는 커밋(다른 repo, 사라진 sha)이 있는 기록은 줄당 토큰 계산에서 뺀다.
        if fresh and all(c.get("added") is not None for c in fresh):
            g["lines"] += sum(num(c.get("added")) + num(c.get("deleted")) for c in fresh)
            g["lineTokens"] += total_tokens(row)
    out = []
    for key, g in sorted(groups.items(), key=lambda kv: kv[1]["first"] or 0):
        n = g["commits"] or 1  # amend 만 있는 그룹에서 0 으로 나누지 않는다
        out.append({
            "label": key,
            "commits": g["commits"],
            "avgTokens": round(g["tokens"] / n),
            "avgCostUsd": round(g["cost"] / n, 4),
            "avgActiveMin": round(g["activeMs"] / n / 60000, 1),
            "avgPrompts": round(g["prompts"] / n, 1),
            "avgFollowUps": round(g["followUps"] / n, 1),
            "avgAborted": round(g["aborted"] / n, 2),
            "avgDenied": round(g["denied"] / n, 2),
            "avgReviews": round(g["reviews"] / n, 1),
            "tokensPerLine": round(g["lineTokens"] / g["lines"]) if g["lines"] else None,
        })
    latest = []
    for row in reversed(rows):
        for c in row.get("commits") or []:
            latest.append({"ts": row.get("ts"), "short": c.get("short"), "subject": c.get("subject"), "label": group_key(row),
                           "tokens": total_tokens(row), "shared": len(row.get("commits") or [])})
        if len(latest) >= recent:
            break
    return {"groups": out, "recent": latest[:recent], "uncommitted": uncommitted}


def cmd_summary(args):
    path = store_dir(args.cwd)
    result = summarize(load(path), args.recent)
    print(json.dumps({"status": "OK", "dir": path, "label": read_label(path), **result}, ensure_ascii=False))
    return 0


def cmd_label(args):
    path = store_dir(args.cwd)
    target = os.path.join(path, LABEL)
    if args.clear:
        try:
            os.remove(target)
        except FileNotFoundError:
            pass
    elif args.set is not None:
        name = " ".join(args.set.split())[:60]
        if not name:
            return fail("BAD_INPUT", "label 이 비어 있습니다")
        with open(target, "w", encoding="utf-8") as f:
            f.write(name + "\n")
    print(json.dumps({"status": "OK", "label": read_label(path)}, ensure_ascii=False))
    return 0


def main(argv=None):
    # Windows 기본 인코딩(cp949 등)이 아니라 mod 가 주고받는 UTF-8 로 고정한다.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "summary", "label"):
        p = sub.add_parser(name)
        p.add_argument("--cwd", default=".")
        if name == "summary":
            p.add_argument("--recent", type=int, default=10)
        if name == "label":
            group = p.add_mutually_exclusive_group()
            group.add_argument("--set")
            group.add_argument("--clear", action="store_true")
    args = parser.parse_args(argv)
    return {"record": cmd_record, "summary": cmd_summary, "label": cmd_label}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
