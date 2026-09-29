<!-- overlay-source: minmos-harness@2.6.1 -->

BE Phase 8.4는 be-harness `review-evidence.md` 계약을 따른다. 추가 품질 리뷰의 APPROVE로 베이스의 BLOCKED:REVIEW_SCOPE를 해소하지 않으며, diff·검사 근거의 독립 보완과 최종 check-scope를 먼저 완료한다.

## Base

`be-harness:start-workflow`

베이스의 Phase 구성을 그대로 따르고, 아래 델타만 얹는다. **베이스 Phase 번호를 재부여하지 않는다** (`docs/overlay.md` §4).

## Pre-flight 추가

`overlay/common.md` 의 "Pre-flight 추가"를 그대로 적용한다.
단 `$TIER_DECLARED = quick`이면 E2E 전용 행(`secret/.env`·PostgreSQL MCP)의 누락은 선택지 대신 1줄 고지로 처리하고, 베이스 Phase 4.4 승인 화면에서 동의받는다 (베이스 `verification-tier.md` §3). probe(파일 확인·`SELECT 1`)는 그대로 실행하고 Apidog MCP 행은 기존 선택지를 유지한다.

## Phase 삽입

| 앵커 | 위치 | 삽입 단계 | 절차 |
|------|------|----------|------|
| `Phase 1 (작업 범위 수집)` | 직후 | **E2E 메인 플로우 수집** | 아래 §E2E 메인 플로우 수집 |
| `Phase 4 (Plan 작성 + 리뷰)` | 내부: Plan Verification Loop | **Codex 실패 폴백 기록** | 아래 §Plan 검증 루프 보강 |
| `Phase 8 (품질 루프)` | 직후 | **Codex 품질 리뷰** (검증 티어 light면 총 2회 상한, quick이면 SKIP — §검증 티어 연동. 리뷰어는 베이스 `codexMode`를 따른다 — `none`이면 Claude 패널 1개가 정규 리뷰어) | `references/codex-review.md` |
| `Phase 12 (최종 보고)` | 내부: Read-back 결정 후, 보완점 분기 전 (`--reflect` 여부와 무관) | **이연 문서 동기화 결정** (Phase 9가 `SKIPPED:DOC_SYNC_DEFERRED`일 때만) | 아래 §quick 문서 동기화 이연 |

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| `Phase 9 (API 문서 동기화)` | Apidog 동기화. 조건(작업 유형이 API 생성/수정/삭제)은 베이스와 동일하되, `{apiDocsPath}` 파일 존재 대신 **Apidog MCP 연결**을 조건으로 쓴다. MCP tool 호출 전 **1회 호출로 read/write capability를 먼저 확인**하고, 지원하지 않는 기능은 시도하지 않고 수동 안내로 전환한다. 실행 주체는 `minmos-harness:workflow-doc-sync` 에이전트. 검증 티어가 quick이고 E2E 결과가 없으면 `SKIPPED:DOC_SYNC_DEFERRED`로 기록하고 Phase 12로 이연한다 (승격으로 E2E 결과가 있으면 기존 경로). |

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

**모든 Build 모드 작업에서 메인 플로우를 확보한다** (작업 유형과 무관). 요청·대화에 이미 있으면 재질문하지 않고 그 원문을 보관한다. `$TIER_DECLARED = quick`이면 질문하지 않고 `자동 도출 (git diff 기반)`을 보관한다 — 승인 전에 유효 티어 T가 quick보다 높아지면(4.1 §3 상향·선언 변경·4.4 재판정) 4.4 승인 대화에서 1회 묻고, 승인 후 승격이면 자동 도출을 쓴다. Plan 깊이 P만 바뀌면 묻지 않는다. 그 외에 없으면 아직 Plan 모드 대화 중이므로 평문으로 묻는다:

> "E2E 테스트 메인 플로우를 알려주세요. 이 작업의 핵심 사용자 시나리오 또는 주요 API 호출 순서를 서술해주세요.
> 예: `진단지 생성 → 목록 조회 → 단건 수정 → 삭제`
> 자동 도출(git diff 기반)에 맡기려면 `자동`이라고 답해주세요."

- 시나리오를 서술하면 그 텍스트를 **그대로** 보관한다 (재해석·요약 금지).
- `자동`이라 답하거나 응답하지 않으면 `자동 도출 (git diff 기반)`으로 보관한다.
- 보관 값은 베이스의 상태 파일 생성 Phase에서 `## E2E 메인 플로우` 섹션에 **한 번만** 저장한다 (단일 출처). 이후 E2E 단계는 상태 파일에서 읽는다.
- 상태 파일 `Phase Assignments` 표에는 `1+` 행으로 기록한다.

## Plan 검증 루프 보강

베이스의 Codex 실패 정책(`codexMode` 계약 §7 — 범위별(전역·provider·슬롯) latch·대표 사유·Claude 패널 폴백·`## Codex Runtime` 기록)을 그대로 따르되, minmos 고유 상태 코드(`SKIPPED:CODEX_*`)를 함께 기록한다. `codexMode: none`이면 이 절은 적용하지 않는다 (패널이 정규 경로, 기록 없음).

| 감지 패턴 | 분류 | 행동 |
|----------|------|------|
| MCP 부재 (`mcp_missing` — 베이스 runtime latch) | 환경 부재 | Claude 다관점 패널로 리뷰어 대체 + `SKIPPED:CODEX_UNAVAILABLE` 기록 (검증 루프는 계속 실행된다) |
| 인증 오류 / 모델·effort 미지원 (`auth_failed` / `model_unavailable(…)` — `review` 슬롯에 적용되는 provider·슬롯 범위 latch) | 환경 부재 | 위와 동일 (패널 + `SKIPPED:CODEX_UNAVAILABLE`) |
| quota/rate-limit (`quota_exhausted` — 베이스 §7 판정 순서 ③) | quota 차단 | **Claude 다관점 패널로 리뷰어 대체** + 상태 파일에 `SKIPPED:CODEX_QUOTA_BLOCKED` 기록 (Phase가 아닌 Codex 호출 항목에 대한 기록 — 검증 루프 자체는 계속 실행된다) |
| 기타 일시 오류 (타임아웃, 5xx) | `tool_error` | 1회 재시도 → 재실패 시 **이 호출만** 패널로 대체 (latch 없음, 진단 `codex_fallback(plan_review:tool_error)`) |

**Claude 다관점 패널 (대체 리뷰어)**: Logic / Architecture / Edge Cases 3관점 `general-purpose` 에이전트 병렬 실행.

| 패널 판정 | 처리 |
|----------|------|
| 3인 전원 APPROVE | Codex APPROVE와 동일 — 수렴 |
| REJECT 1개 이상 | 지적 반영 후 다음 iteration |
| CONCERN | 베이스의 CONCERN 처리 규칙 준용 |

패널 대체 시에도 **루프 카운터는 승계**한다 (리셋 없음, 최대 반복 상한 동일). 슬롯 사망·무효 verdict·정족수(유효 verdict 3개, 미달 시 `CODEX-UNAVAILABLE`) 처리는 베이스 `codexMode` 계약 §6을 따른다.

**고지 문구**: "Codex quota 차단 감지 — Claude 다관점 패널로 대체해 계속 진행합니다 (`SKIPPED:CODEX_QUOTA_BLOCKED` 기록)."

## 검증 티어 연동

베이스가 판정한 유효 티어(`{STATE_FILE}`의 `## Flags` `TIER` — 승격 시 갱신되는 재개 기준, 없으면 `## Verification Tier`의 유효 티어)를 오버레이 단계도 따른다.

| 단계 | quick | light | standard |
|------|-------|-------|----------|
| Phase 1+ E2E 메인 플로우 수집 | 선언 quick: 질문 없이 `자동 도출` 보관 | 동일 (항상 확보, 재질문 없음) | 동일 |
| Phase 4 Plan 검증 루프 보강 — **Plan 깊이 P 기준** (베이스 §2.1) | 해당 없음 (4.3 `SKIPPED:PLAN_QUICK`) | quota 폴백 패널 그대로 — 패널 대체는 리뷰 수행으로 간주(베이스 승격 ⑤ 아님) | 동일 |
| Phase 8 내부 e2e-test / e2e-test-loop | 미호출 (8.6 `SKIPPED:TIER_QUICK`) | `--smoke` 실효 수준에 따라 `overlay/e2e-test.md` §smoke 분기 | 동일 (삽입 전부) |
| Phase 8+ Codex 품질 리뷰 | **SKIP** (`SKIPPED:TIER_QUICK`, 사용 0회) | **총 2회** (초회 + 재리뷰 1회), quota 폴백 패널 1 에이전트 | 총 4회 (초회 + 재리뷰 3회) |
| Phase 9 Apidog 동기화 | E2E 결과 없으면 `SKIPPED:DOC_SYNC_DEFERRED` → Phase 12 결정 | 기존 | 기존 |

리뷰 사용 횟수는 `## Verification Tier`에 `- minmos 리뷰 사용: {N}회`로 기록한다 (구 상태면 `Phase Results`의 8+ 행 수로 복원). 승격으로 티어가 오르면 quick 출신(사용 0회)은 새 티어 상한으로 최초 실행하고, light → standard는 사용 횟수를 승계한다(잔여 = 4 − 사용).

베이스 승격 ⑦(Phase 10 진입 직전 재판정)로 Phase 8을 새 티어 루프로 재진입한 경우: 재진입 루프에서 파일이 1회라도 수정됐으면(`modified == true`) Codex 품질 리뷰를 그 검증 트리에 대해 **1회 재실행**한다 — 새 티어 규칙(REJECT 시 `codex-review.md`의 수정·재검증·재리뷰)을 따르되 그 티어 상한의 **잔여 횟수**만 쓰고, 잔여 0이면 `BLOCKED:CODEX_REVIEW`. 수정이 없었으면 기존 APPROVE가 유효하다. quick 출신이라 리뷰 이력이 없으면 수정 여부와 무관하게 1회 실행한다.

## quick 문서 동기화 이연 (Phase 12)

Phase 9가 `SKIPPED:DOC_SYNC_DEFERRED`로 기록된 경우에만 베이스 Phase 12 절차의 Read-back 결정 뒤, 보완점 분기 전에 실행한다.

- Spec의 API 변경 대상 `{METHOD PATH}`마다 "`/minmos-harness:apidog-schema-gen {METHOD PATH}`를 지금 대화형으로 실행할까요?"를 묻는다. 확인·push는 스킬 절차를 그대로 재사용한다.
- 결정은 대상과 함께 `## Final Decisions`에 기록하고, 재개 시 재사용해 다시 묻지 않는다. 거절은 `SKIPPED:USER_OPT_OUT`으로 종결하고, 미응답·진행 중은 미완료로 보존한다.
- 스키마 생성 · push 승인 · 실제 반영 결과를 구분해 보고서 §5에 기록한다. repo 파일이 바뀌면 베이스의 최종 반영 절차(`finalization.md`)를 따른다.

## 상태 코드 추가

| 코드 | 의미 |
|------|------|
| `SKIPPED:ENV_MISSING` | `secret/.env` 부재 |
| `SKIPPED:APIDOG_MCP_UNAVAILABLE` | Apidog MCP 미연결 — 문서 동기화 불가 |
| `SKIPPED:POSTGRES_MCP_UNAVAILABLE` | PostgreSQL MCP 미연결 |
| `SKIPPED:CODEX_QUOTA_BLOCKED` | Codex quota 차단 — Claude 패널로 대체 실행됨 |
| `SKIPPED:CODEX_UNAVAILABLE` | Codex MCP 부재·인증 오류·모델 미지원 — Claude 패널로 대체 실행됨 |
| `SKIPPED:DOC_SYNC_DEFERRED` | quick — E2E 결과 없이 Apidog 동기화를 Phase 12 대화형 결정으로 이연 |
| `BLOCKED:CODEX_REVIEW` | Codex 품질 리뷰 REJECT 상한 도달 |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/codex-review.md` | Phase 8+ (Codex 품질 리뷰) 진입 시 |
| `references/db-safety.md` | E2E 관련 단계 진입 시 |
