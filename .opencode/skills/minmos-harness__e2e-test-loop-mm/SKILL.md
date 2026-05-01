---
name: minmos-harness__e2e-test-loop-mm
description: "E2E 테스트 → 이슈 수정 → 재테스트 반복. 모든 테스트가 통과할 때까지 루프한다. (최대 5회)"
user-invocable: true
---

## Prerequisites

e2e-test와 동일한 환경이 필요하다. 세팅 확인: `/minmos-harness:e2e-test-mm --doctor`

### `--init`

`$ARGUMENTS`가 `--init`이면 `/minmos-harness:e2e-test-mm --init`을 실행하고 종료한다.

### `--doctor`

`$ARGUMENTS`가 `--doctor`이면 `/minmos-harness:e2e-test-mm --doctor`를 실행하고 종료한다.

### 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--init` | | 초기 세팅 후 종료 |
| `--doctor` | | 상태 진단 후 종료 |
| `--skip-doctor` | `-sd` | 실행 전 자동 doctor 점검을 건너뜀 |

---

/minmos-harness:e2e-test-mm 를 실행하고, 발견된 이슈를 수정한 뒤 재테스트하는 과정을 반복해:

## 절차

### 0. Pre-flight Probe (Fast SKIP Gate)

`$ARGUMENTS`에 `--skip-doctor` 또는 `-sd`가 **없으면**, 루프 진입 전 빠른 환경 probe를 실행한다.
**환경 부재가 확정되면 루프를 한 번도 돌지 않고 즉시 `SKIPPED`를 반환한다** — 실패 후 판정이 아니라, 진입 게이트에서 끊어낸다.

**Probe 항목 (e2e-test-mm Step 0과 동일):**
- `secret/.env` 존재 → 없으면 `[SKIPPED:ENV_MISSING]`
- `.mcp.json` 존재 → 없으면 `[SKIPPED:MCP_CONFIG_MISSING]`
- PostgreSQL MCP 등록 → 없으면 `[SKIPPED:POSTGRES_MCP_MISSING]`
- DB 호스트 로컬 전용 → 위반이면 `[SKIPPED:REMOTE_DB_BLOCKED]` (화이트리스트 승인 없으면)

**처리 규칙:**
- 모두 OK → Step 1로 진행
- 하나라도 FAIL → **루프 진입 없이** 즉시 아래 형식으로 종료:
  ```
  ## E2E Test Loop — SKIPPED
  사유: [SKIPPED:{REASON}]
  누락 항목: {항목}
  복구 방법: `/minmos-harness:e2e-test-mm --init`
  ```
- `--skip-doctor` / `-sd` 지정 시 → probe를 건너뛰고 바로 Step 1로 진행 (사용자 책임)

1. `/minmos-harness:e2e-test-mm` 를 실행한다.
   - 하위 스킬이 `[SKIPPED:*]`를 반환하면 루프를 추가 진행하지 않고 동일 SKIP 사유로 종료한다.
2. 결과를 확인한다:
   - **이슈 없음** (모든 테스트 통과, STATUS_MISMATCH 없음) → 루프를 종료한다.
   - **이슈 발견** → 3번으로 진행한다.
3. 발견된 이슈를 수정한다:
   - 코드 수정 후 서버를 재빌드/재시작한다.
   - 수정 내용을 기록한다.
4. iteration 카운트를 1 증가시키고 1번으로 돌아간다.
5. **최대 5회** iteration 후에는 미해결 이슈와 함께 종료한다.

## 종료 시 출력

```
E2E Test Loop 완료
- 총 iteration: N회
- 발견된 이슈: M건
- 수정된 이슈: X건
- 미해결 이슈: Y건 (있으면 목록)
```

probe SKIP인 경우:
```
E2E Test Loop — SKIPPED
- 사유: [SKIPPED:{REASON}]
- 총 iteration: 0회
```
