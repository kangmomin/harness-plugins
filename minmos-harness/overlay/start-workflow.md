<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:start-workflow`

베이스의 Phase 구성을 그대로 따르고, 아래 델타만 얹는다. **베이스 Phase 번호를 재부여하지 않는다** (`docs/overlay.md` §4).

## Pre-flight 추가

`overlay/common.md` 의 "Pre-flight 추가"를 그대로 적용한다.

## Phase 삽입

| 앵커 | 위치 | 삽입 단계 | 절차 |
|------|------|----------|------|
| `Phase 1 (작업 범위 수집)` | 직후 | **E2E 메인 플로우 수집** | 아래 §E2E 메인 플로우 수집 |
| `Phase 4 (Plan 작성 + 리뷰)` | 내부: Plan Verification Loop | **Codex quota 폴백 보강** | 아래 §Plan 검증 루프 보강 |
| `Phase 8 (품질 루프)` | 직후 | **Codex 품질 리뷰** | `references/codex-review.md` |

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| `Phase 9 (API 문서 동기화)` | Apidog 동기화. 조건(작업 유형이 API 생성/수정/삭제)은 베이스와 동일하되, `{apiDocsPath}` 파일 존재 대신 **Apidog MCP 연결**을 조건으로 쓴다. MCP tool 호출 전 **1회 호출로 read/write capability를 먼저 확인**하고, 지원하지 않는 기능은 시도하지 않고 수동 안내로 전환한다. 실행 주체는 `minmos-harness:workflow-doc-sync` 에이전트. |

## 스킬 치환 매핑

베이스가 호출하는 스킬은 그대로 두고, 각 스킬의 오버레이를 함께 적용한다.

| 베이스가 호출하는 것 | 적용할 오버레이 |
|---------------------|----------------|
| `/be-harness:request` (Phase 1) | `overlay/request.md` |
| `/be-harness:e2e-test` (Phase 8 내부) | `overlay/e2e-test.md` |
| `/be-harness:e2e-test-loop` (Phase 8.6) | `overlay/e2e-test-loop.md` |
| `/be-harness:convention-check` (Phase 8.3) | `overlay/convention-check.md` |
| `/be-harness:default-conventions` | `overlay/default-conventions.md` |

`/be-harness:simplify-loop`, `/be-harness:unit-test` 는 오버레이 없이 베이스 그대로 사용한다.

---

## E2E 메인 플로우 수집 (Phase 1+)

E2E 테스트가 **검증해야 할 핵심 시나리오**를 사용자에게 직접 묻는다. git diff 기반 자동 도출만으로는 의도한 주 사용 흐름이 누락될 수 있다.

**모든 Build 모드 작업에서 항상 질문한다** (작업 유형과 무관). 아직 Plan 모드 대화 중이므로 평문으로 묻는다:

> "E2E 테스트 메인 플로우를 알려주세요. 이 작업의 핵심 사용자 시나리오 또는 주요 API 호출 순서를 서술해주세요.
> 예: `진단지 생성 → 목록 조회 → 단건 수정 → 삭제`
> 자동 도출(git diff 기반)에 맡기려면 `자동`이라고 답해주세요."

- 시나리오를 서술하면 그 텍스트를 **그대로** 보관한다 (재해석·요약 금지).
- `자동`이라 답하거나 응답하지 않으면 `자동 도출 (git diff 기반)`으로 보관한다.
- 보관 값은 베이스의 상태 파일 생성 Phase에서 `## E2E 메인 플로우` 섹션에 **한 번만** 저장한다 (단일 출처). 이후 E2E 단계는 상태 파일에서 읽는다.
- 상태 파일 `Phase Assignments` 표에는 `1+` 행으로 기록한다.

## Plan 검증 루프 보강

베이스의 Plan Verification Loop는 Codex 사용 불가를 `CODEX-UNAVAILABLE` 한 갈래로만 처리한다. 오버레이는 **quota 차단을 분리**해 리뷰를 계속 진행시킨다.

| 감지 패턴 | 분류 | 행동 |
|----------|------|------|
| CLI/MCP 부재 (command not found, 도구 미존재) | 환경 부재 | 베이스대로 `CODEX-UNAVAILABLE` — 사유 기록 후 진행 |
| quota/rate-limit (429, "usage limit", "rate limit", "quota", "try again at") | quota 차단 | **Claude 다관점 패널로 리뷰어 대체** + 상태 파일에 `SKIPPED:CODEX_QUOTA_BLOCKED` 기록 (Phase가 아닌 Codex 호출 항목에 대한 기록 — 검증 루프 자체는 계속 실행된다) |
| 기타 일시 오류 (타임아웃, 5xx) | 모호 | 1회 재시도 → 재실패 시 quota 차단과 동일 취급 |

**Claude 다관점 패널 (대체 리뷰어)**: Logic / Architecture / Edge Cases 3관점 `general-purpose` 에이전트 병렬 실행.

| 패널 판정 | 처리 |
|----------|------|
| 3인 전원 APPROVE | Codex APPROVE와 동일 — 수렴 |
| REJECT 1개 이상 | 지적 반영 후 다음 iteration |
| CONCERN | 베이스의 CONCERN 처리 규칙 준용 |

패널 대체 시에도 **루프 카운터는 승계**한다 (리셋 없음, 최대 반복 상한 동일).

**고지 문구**: "Codex quota 차단 감지 — Claude 다관점 패널로 대체해 계속 진행합니다 (`SKIPPED:CODEX_QUOTA_BLOCKED` 기록)."

## 상태 코드 추가

| 코드 | 의미 |
|------|------|
| `SKIPPED:ENV_MISSING` | `secret/.env` 부재 |
| `SKIPPED:APIDOG_MCP_UNAVAILABLE` | Apidog MCP 미연결 — 문서 동기화 불가 |
| `SKIPPED:POSTGRES_MCP_UNAVAILABLE` | PostgreSQL MCP 미연결 |
| `SKIPPED:CODEX_QUOTA_BLOCKED` | Codex quota 차단 — Claude 패널로 대체 실행됨 |
| `BLOCKED:CODEX_REVIEW` | Codex 품질 리뷰 REJECT 상한 도달 |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/codex-review.md` | Phase 8+ (Codex 품질 리뷰) 진입 시 |
| `references/db-safety.md` | E2E 관련 단계 진입 시 |
