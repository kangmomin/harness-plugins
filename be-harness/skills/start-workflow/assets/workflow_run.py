#!/usr/bin/env python3
"""실행별 경로 생성과 명시적 재개 검증. 소스/상태 본문은 변경하지 않는다.

create --cwd DIR --mode be|fe|fs|analyze|verify [--report-dir V]
resume --cwd DIR --mode MODE --state STATE_FILE
save-verify-commands --cwd DIR --mode verify --state STATE_FILE --commands JSON
성공 시 절대 경로/실행 ID JSON 출력, 검증 실패 시 exit 2, 경로·profile·git 오류는 exit 1 BLOCKED:STORE_CONFIG.
REPORT_DIR·RUN_DIR 위치는 같은 폴더의 harness_store.py가 profile reportDir로 정한다.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import uuid


VERIFY_COMMAND_KEYS = {'lintCommand', 'buildCommand', 'typeCheckCommand', 'testCommand'}
_STORE_SPEC = importlib.util.spec_from_file_location('harness_store', Path(__file__).with_name('harness_store.py'))
store = importlib.util.module_from_spec(_STORE_SPEC)
_STORE_SPEC.loader.exec_module(store)


def profile_value(cwd, mode):
    """mode의 profile reportDir. fs는 be 값이 비어 있지 않으면 be, 아니면 fe."""
    if mode == 'fe':
        return store.profile_report_dir(cwd, 'fe')
    value = store.profile_report_dir(cwd, 'be')
    if mode == 'fs' and not value:
        return store.profile_report_dir(cwd, 'fe')
    return value


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
    if 'report_dir' in record:
        paths['REPORT_DIR'] = record['report_dir']
    if record['mode'] == 'verify':
        paths['VERIFY_COMMANDS_FILE'] = str(directory / 'verify-commands.json')
    return paths


def create(cwd, mode, report_dir=None):
    """report_dir: None = 기존 temp RUN_DIR + legacy REPORT_DIR, '' = doc root 기본 위치, 값 = profile 명시값."""
    if report_dir is None:
        directory = Path(tempfile.mkdtemp(prefix="harness-workflow-")).resolve()
        location = {'reportDir': store.report_location(cwd, ''), 'source': 'legacy', 'warnings': []}
    else:
        location = store.run_location(cwd, report_dir, prefix="harness-workflow-")
        directory = Path(location['runDir'])
    record = {"cwd": str(cwd), "mode": mode, "run_id": uuid.uuid4().hex,
              "report_dir": location['reportDir'], "report_dir_source": location['source']}
    (directory / "run.json").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "owned-files.json").write_text("[]\n", encoding="utf-8")
    return {**run_paths(directory, record), 'warnings': location['warnings']}


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
    warnings = []
    if 'report_dir' in record:
        if not isinstance(record['report_dir'], str) or not Path(record['report_dir']).is_absolute():
            raise ValueError("run.json report_dir는 절대 경로여야 함")
    else:
        record = {**record, 'report_dir': store.report_location(cwd, profile_value(cwd, mode))}
        warnings.append('옛 run: REPORT_DIR을 legacy 위치로 계산함 (%s)' % record['report_dir'])
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
    paths['warnings'] = warnings
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "resume", "save-verify-commands"))
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--mode", required=True, choices=("be", "fe", "fs", "analyze", "verify"))
    parser.add_argument("--state")
    parser.add_argument("--commands", help='Resolved Verify commands JSON; saved once before execution')
    parser.add_argument("--report-dir", help="profile reportDir 대신 쓸 값 (테스트·수동용)")
    args = parser.parse_args()
    try:
        cwd = Path(args.cwd).resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("CWD는 디렉토리여야 함")
        if args.action == "resume" and not args.state:
            raise ValueError("resume은 --state 절대 경로가 필요함")
        if args.action == "create" and args.state:
            raise ValueError("create는 기존 상태 파일을 받지 않음")
        if args.report_dir is not None and args.action != "create":
            raise ValueError("--report-dir는 create에만 씀")
        if args.action == 'save-verify-commands':
            if args.mode != 'verify' or not args.state or not args.commands:
                raise ValueError('save-verify-commands requires verify mode, --state and --commands')
            result = save_verify_commands(cwd, args.state, args.commands)
        else:
            if args.commands:
                raise ValueError('--commands is only valid for save-verify-commands')
            if args.action == "create":
                value = args.report_dir if args.report_dir is not None else profile_value(cwd, args.mode)
                result = create(cwd, args.mode, value)
            else:
                result = resume(cwd, args.mode, args.state)
    except store.ConfigError as error:
        print("BLOCKED:STORE_CONFIG — %s" % error, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("BLOCKED:RUN_MISMATCH — %s" % error, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
