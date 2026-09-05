#!/usr/bin/env python3
"""실행별 경로 생성과 명시적 재개 검증. 소스/상태 본문은 변경하지 않는다.

create --cwd DIR --mode be|fe|fs|analyze|verify
resume --cwd DIR --mode MODE --state STATE_FILE
성공 시 절대 경로/실행 ID JSON 출력, 검증 실패 시 exit 2.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import uuid


def run_paths(directory, record):
    return {
        "CWD": record["cwd"], "MODE": record["mode"], "RUN_ID": record["run_id"],
        "RUN_DIR": str(directory), "STATE_FILE": str(directory / "workflow-state.md"),
        "IMPL_NOTES": str(directory / "implementation-notes.md"),
        "WORK_REPORT": str(directory / "workflow-report.md"),
    }


def create(cwd, mode):
    directory = Path(tempfile.mkdtemp(prefix="harness-workflow-")).resolve()
    record = {"cwd": str(cwd), "mode": mode, "run_id": uuid.uuid4().hex}
    (directory / "run.json").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_paths(directory, record)


def resume(cwd, mode, state):
    if not Path(state).is_absolute():
        raise ValueError("resume은 --state 절대 경로가 필요함")
    state = Path(state).resolve(strict=True)
    directory = state.parent
    record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("run.json은 실행 객체여야 함")
    if state.name != "workflow-state.md" or record.get("cwd") != str(cwd) or record.get("mode") != mode:
        raise ValueError("재개 대상의 저장소·모드·상태 경로 불일치")
    if not re.fullmatch(r"[0-9a-f]{32}", record.get("run_id", "")):
        raise ValueError("재개 대상 RUN_ID가 유효하지 않음")
    paths = run_paths(directory, record)
    text = state.read_text(encoding="utf-8")
    sections = re.findall(r"^## Run\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if len(sections) != 1:
        raise ValueError("재개 대상의 ## Run이 없거나 중복됨")
    for key in ("CWD", "MODE", "RUN_ID", "RUN_DIR"):
        values = re.findall(r"^- " + key + r": ([^\n]+)$", sections[0], re.M)
        if values != [paths[key]]:
            raise ValueError("재개 대상의 %s 불일치" % key)
    remaining = re.findall(r"^## Remaining Phases\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if len(remaining) != 1 or not remaining[0].strip():
        raise ValueError("재개 대상의 Remaining Phases가 없거나 중복됨")
    if remaining[0].strip() in ("없음", "- 없음"):
        raise ValueError("완료된 실행은 재개하지 않음 — create로 새 실행 시작")
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "resume"))
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--mode", required=True, choices=("be", "fe", "fs", "analyze", "verify"))
    parser.add_argument("--state")
    args = parser.parse_args()
    try:
        cwd = Path(args.cwd).resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("CWD는 디렉토리여야 함")
        if args.action == "resume" and not args.state:
            raise ValueError("resume은 --state 절대 경로가 필요함")
        if args.action == "create" and args.state:
            raise ValueError("create는 기존 상태 파일을 받지 않음")
        result = create(cwd, args.mode) if args.action == "create" else resume(cwd, args.mode, args.state)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("BLOCKED:RUN_MISMATCH — %s" % error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
