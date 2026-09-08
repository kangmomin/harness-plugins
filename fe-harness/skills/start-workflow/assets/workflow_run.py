#!/usr/bin/env python3
"""실행별 경로 생성과 명시적 재개 검증. 소스/상태 본문은 변경하지 않는다.

create --cwd DIR --mode be|fe|fs|analyze|verify
resume --cwd DIR --mode MODE --state STATE_FILE
save-verify-commands --cwd DIR --mode verify --state STATE_FILE --commands JSON
성공 시 절대 경로/실행 ID JSON 출력, 검증 실패 시 exit 2.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import uuid


VERIFY_COMMAND_KEYS = {'lintCommand', 'buildCommand', 'typeCheckCommand', 'testCommand'}


def load_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def verify_commands(data, record):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('invalid verify commands snapshot version')
    if data.get('run_id') != record['run_id'] or data.get('cwd') != record['cwd']:
        raise ValueError('verify commands snapshot belongs to another run or cwd')
    commands = data.get('commands')
    if not isinstance(commands, dict) or set(commands) != VERIFY_COMMAND_KEYS or not all(isinstance(value, str) for value in commands.values()):
        raise ValueError('verify commands snapshot requires four resolved command strings')
    if not isinstance(data.get('profile_path'), str) or not Path(data['profile_path']).is_absolute():
        raise ValueError('verify commands snapshot requires an absolute profile_path')
    if not isinstance(data.get('profile_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', data['profile_sha256']):
        raise ValueError('verify commands snapshot requires profile_sha256')
    return data


def save_verify_commands(cwd, state, source):
    state = Path(state)
    if not state.is_absolute() or state.name != 'workflow-state.md':
        raise ValueError('verify commands require the absolute STATE_FILE path')
    directory = state.parent.resolve(strict=True)
    record = load_json(directory / 'run.json')
    if not isinstance(record, dict) or record.get('cwd') != str(cwd) or record.get('mode') != 'verify' or not re.fullmatch(r'[0-9a-f]{32}', str(record.get('run_id', ''))):
        raise ValueError('verify commands run identity mismatch')
    data = verify_commands(load_json(source), record)
    destination = directory / 'verify-commands.json'
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'VERIFY_COMMANDS_FILE': str(destination), 'VERIFY_COMMANDS': data}


def run_paths(directory, record):
    paths = {
        "CWD": record["cwd"], "MODE": record["mode"], "RUN_ID": record["run_id"],
        "RUN_DIR": str(directory), "STATE_FILE": str(directory / "workflow-state.md"),
        "IMPL_NOTES": str(directory / "implementation-notes.md"),
        "WORK_REPORT": str(directory / "workflow-report.md"),
        "RESULTS_FILE": str(directory / "verification-results.json"),
        "OWNED_FILES": str(directory / "owned-files.json"),
    }
    if record['mode'] == 'verify':
        paths['VERIFY_COMMANDS_FILE'] = str(directory / 'verify-commands.json')
    return paths


def create(cwd, mode):
    directory = Path(tempfile.mkdtemp(prefix="harness-workflow-")).resolve()
    record = {"cwd": str(cwd), "mode": mode, "run_id": uuid.uuid4().hex}
    (directory / "run.json").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "owned-files.json").write_text("[]\n", encoding="utf-8")
    return run_paths(directory, record)


def resume(cwd, mode, state):
    if not Path(state).is_absolute():
        raise ValueError("resume은 --state 절대 경로가 필요함")
    state = Path(state).resolve(strict=True)
    directory = state.parent
    record = load_json(directory / 'run.json')
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
    if mode == 'verify':
        paths['VERIFY_COMMANDS'] = verify_commands(load_json(paths['VERIFY_COMMANDS_FILE']), record)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "resume", "save-verify-commands"))
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--mode", required=True, choices=("be", "fe", "fs", "analyze", "verify"))
    parser.add_argument("--state")
    parser.add_argument("--commands", help='Resolved Verify commands JSON; saved once before execution')
    args = parser.parse_args()
    try:
        cwd = Path(args.cwd).resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("CWD는 디렉토리여야 함")
        if args.action == "resume" and not args.state:
            raise ValueError("resume은 --state 절대 경로가 필요함")
        if args.action == "create" and args.state:
            raise ValueError("create는 기존 상태 파일을 받지 않음")
        if args.action == 'save-verify-commands':
            if args.mode != 'verify' or not args.state or not args.commands:
                raise ValueError('save-verify-commands requires verify mode, --state and --commands')
            result = save_verify_commands(cwd, args.state, args.commands)
        else:
            if args.commands:
                raise ValueError('--commands is only valid for save-verify-commands')
            result = create(cwd, args.mode) if args.action == "create" else resume(cwd, args.mode, args.state)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("BLOCKED:RUN_MISMATCH — %s" % error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
