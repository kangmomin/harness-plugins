> 이 문서는 start-workflow의 Pre-flight와 재개 시 항상 읽는다. 소속 플러그인의 assets/workflow_run.py가 경로 생성·검증의 정본이다.

# 실행 경로와 재개

모드 판별 직후, Codex 설정 resolve·첫 dispatch보다 먼저 실행 경로를 확정한다.
`{RUN_MODE}`는 BE Build `be`, FE Build `fe`, 풀스택 `fs`, Analyze `analyze`, Verify `verify`다.

## 신규 실행

새 작업은 이전 상태 파일의 존재와 무관하게 항상 새 실행을 만든다. Plan 모드 진입 전 임시 운영 메타데이터만 생성하며, 소스·브랜치·상태 본문은 기존 승인 시점을 따른다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/workflow_run.py" create --cwd "{CWD}" --mode "{RUN_MODE}"
```

JSON 출력의 `CWD`, `RUN_ID`, `RUN_DIR`, `STATE_FILE`, `IMPL_NOTES`, `WORK_REPORT` 절대 경로를 이번 실행의 유일한 값으로 보관한다. `{RUN_DIR}/run.json`은 변경하지 않는다. 경로를 셸 코드로 eval하지 않는다.
모든 하위 에이전트/스킬에 필요한 실제 경로를 전달한다. baseline·iteration 로그도 `{RUN_DIR}` 아래에 저장한다. 격리 Read-back에는 이 경로를 전달하지 않는다.
상태 본문을 처음 생성할 때 아래 헤더를 포함한다. `RUN_ID`는 재생성하지 않고 `START_SHA`만 구현 직전 기존 Phase에서 수집한다.

```markdown
## Run
- CWD: {CWD}
- MODE: {RUN_MODE}
- RUN_ID: {RUN_ID}
- RUN_DIR: {RUN_DIR}
```

## 명시적 재개

`--resume {STATE_FILE의 절대 경로}` 또는 현재 미완료 실행의 계속 요청에 대해 보관 중인 절대 경로가 있을 때만 재개한다. 새 작업 요청을 재개로 해석하거나 `/tmp`를 스캔해 임의 상태를 고르지 않는다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/workflow_run.py" resume --cwd "{CWD}" --mode "{RUN_MODE}" --state "{STATE_FILE}"
```

검증 성공 뒤에만 상태의 Flags·Codex Runtime을 재사용하고 기록된 미완료 Phase부터 계속한다. 상태/노트를 새 템플릿으로 덮어쓰지 않는다.
검증은 실제 작업 디렉토리(서로 다른 worktree 구별), 모드, RUN_ID, RUN_DIR, 상태 파일명, 미완료 여부를 대조한다.
상태 생성 전 중단·경로 분실·구 전역 상태·불일치는 `BLOCKED:RUN_MISMATCH`로 고지하고 해당 상태를 실행하지 않는다. 새 작업은 create로 시작한다. 스크립트 실패 시 전역 경로로 폴백하지 않는다.

## 마감

최종 승인 수정의 검증·commit/push 결과까지 반영한 뒤 상태를 마감하고 아카이브한다. 미해결 BLOCKED/FAIL을 DONE으로 바꾸지 않는다.
기본은 실행 디렉토리를 보관한다. 정리 요청 시 서버/세션 종료를 확인하고 검증된 이번 `{RUN_DIR}`만 삭제한다. 완료된 실행의 상태는 새 작업에 재사용하지 않는다.
