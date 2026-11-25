#!/usr/bin/env python3
"""스킬 실행 중 겪은 마찰(papercut) 기록·집계 helper.

에이전트가 마찰 1건을 stdin JSON 으로 넘기면 JSONL 1줄로 추가한다. 저장소 밖 로컬 전용이다.
저장 위치는 metrics.py 와 같은 폴더다: $HARNESS_METRICS_DIR 또는 ~/.claude/harness-metrics/<repo>-<hash>/.
외부 제출은 하지 않는다. 제출은 /common:submit-feedback 이 export 결과를 받아서 한다.

사용:
  papercut.py record --cwd .                      (stdin: {plugin, skill, goal, actual, command?, expected?, workaround?, proposal?})
  papercut.py list --cwd . [--plugin NAME]
  papercut.py export --cwd . --plugin NAME        (submit-feedback 입력 형식. generality 는 비워 둔다)
  papercut.py mark --cwd . --ids ID[,ID...]       (제출했거나 제외한 항목을 목록에서 뺀다)
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time

SCHEMA = 1
RECORDS = "papercuts.jsonl"
REQUIRED = ("plugin", "skill", "goal", "actual")
OPTIONAL = ("command", "expected", "workaround", "proposal")
LIMIT = 2000  # 로그 전체를 붙이지 않게 필드 길이를 자른다.


def metrics():
    # -I 로 실행하면 스크립트 폴더가 sys.path 에 없다. 그래서 경로로 직접 읽는다.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metrics.py")
    spec = importlib.util.spec_from_file_location("harness_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path):
    """(열린 기록, 제출 표시된 id) 를 돌려준다. 잘린 줄은 건너뛴다."""
    rows, marked = {}, set()
    try:
        # 깨진 바이트 1개가 전체 읽기를 막지 않게 한다. 그 줄만 JSON 오류로 건너뛴다.
        with open(os.path.join(path, RECORDS), encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                    continue
                if row.get("submitted"):
                    marked.add(row["id"])
                else:
                    rows.setdefault(row["id"], row)
    except FileNotFoundError:
        pass
    return [row for key, row in rows.items() if key not in marked], marked | set(rows)


def append(path, record):
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    target = os.path.join(path, RECORDS)
    try:
        with open(target, "rb") as f:
            f.seek(-1, os.SEEK_END)
            # 마지막 줄이 잘렸으면 새 줄이 거기에 붙어 함께 버려진다. 줄을 먼저 끝낸다.
            if f.read(1) != b"\n":
                line = "\n" + line
    except OSError:
        pass  # 파일이 없거나 비어 있다.
    # 한 번의 write 로 1줄을 붙인다. 동시에 쓰는 세션이 있어도 줄이 섞이지 않게 한다.
    fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def cmd_record(args, m):
    try:
        data = json.load(sys.stdin)
    except ValueError as err:
        return m.fail("BAD_INPUT", f"stdin JSON 을 읽지 못했습니다: {err}")
    if not isinstance(data, dict):
        return m.fail("BAD_INPUT", "stdin 은 JSON 객체여야 합니다")
    fields = {}
    for key in REQUIRED + OPTIONAL:
        value = data.get(key, "")
        if not isinstance(value, str):
            return m.fail("BAD_INPUT", f"{key} 는 문자열이어야 합니다")
        fields[key] = value.strip()[:LIMIT]
    missing = [key for key in REQUIRED if not fields[key]]
    if missing:
        return m.fail("BAD_INPUT", "필수 필드가 없습니다: " + ", ".join(missing))
    for key in ("plugin", "skill"):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", fields[key]):
            return m.fail("BAD_INPUT", f"{key} 는 이름 1개여야 합니다 (예: common, commit)")
    path = m.store_dir(args.cwd)
    identity = json.dumps([fields[k] for k in ("plugin", "skill", "goal", "command", "expected", "actual")], ensure_ascii=False)
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    _, seen = load(path)
    if key in seen:
        print(json.dumps({"status": "DUPLICATE", "id": key}, ensure_ascii=False))
        return 0
    append(path, {"v": SCHEMA, "ts": int(time.time() * 1000), "id": key, "common": m.plugin_version(), **fields})
    print(json.dumps({"status": "OK", "id": key, "dir": path}, ensure_ascii=False))
    return 0


def selected(args, m):
    rows, _ = load(m.store_dir(args.cwd))
    return [row for row in rows if not args.plugin or row.get("plugin") == args.plugin]


def cmd_list(args, m):
    rows = selected(args, m)
    counts = {}
    for row in rows:
        name = f"{row.get('plugin')}:{row.get('skill')}"
        counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    print(json.dumps({"status": "OK", "total": len(rows), "by_skill": dict(ordered), "items": rows}, ensure_ascii=False))
    return 0


def cmd_export(args, m):
    items = []
    for row in selected(args, m):
        context = "\n".join(f"- {label}: {row[key]}" for key, label in (
            ("goal", "하려던 일"), ("command", "실행한 명령"), ("expected", "기대한 결과"),
            ("actual", "실제 결과"), ("workaround", "우회 방법")) if row.get(key))
        items.append({
            "id": row["id"], "target_type": "skill", "target_name": row["skill"],
            # submit-feedback 은 요지가 같은 항목을 중복으로 본다. 그래서 실제 결과까지 넣어 구분한다.
            "summary": " ".join((row["goal"] + " — " + row["actual"]).split())[:120], "context": context,
            "proposal": row.get("proposal", ""), "generality": "",
        })
    day = time.strftime("%Y-%m-%d", time.localtime())
    print(json.dumps({"status": "OK", "payload": {"plugin": args.plugin, "date": day, "items": items}}, ensure_ascii=False))
    return 0


def cmd_mark(args, m):
    path = m.store_dir(args.cwd)
    rows, _ = load(path)
    known = {row["id"] for row in rows}
    ids = [value for value in args.ids.split(",") if value in known]
    for value in ids:
        append(path, {"v": SCHEMA, "ts": int(time.time() * 1000), "id": value, "submitted": True})
    print(json.dumps({"status": "OK", "marked": ids}, ensure_ascii=False))
    return 0


def main(argv=None):
    # Windows 기본 인코딩(cp949 등)이 아니라 UTF-8 로 고정한다.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            # PowerShell 파이프는 BOM 을 붙인다. stdin 만 BOM 을 받아들인다.
            stream.reconfigure(encoding="utf-8-sig" if stream is sys.stdin else "utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "list", "export", "mark"):
        p = sub.add_parser(name)
        p.add_argument("--cwd", default=".")
        if name in ("list", "export"):
            p.add_argument("--plugin", required=name == "export")
        if name == "mark":
            p.add_argument("--ids", required=True)
    args = parser.parse_args(argv)
    return {"record": cmd_record, "list": cmd_list, "export": cmd_export, "mark": cmd_mark}[args.command](args, metrics())


if __name__ == "__main__":
    sys.exit(main())
