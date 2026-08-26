> 이 문서는 `minmos-harness` 오버레이의 `overlay/start-workflow.md` 에서 **Phase 8+ (Codex 품질 리뷰)** 진입 시 로드된다. 단독 실행 금지.
> Phase 번호는 베이스(`be-harness:start-workflow`)의 앵커를 따른다 — `Phase 8 (품질 루프)` 완료 직후 1회 실행.

# Codex 품질 리뷰 (Phase 8+)

품질 루프가 완료되면 다음 Phase로 넘어가기 전에 **반드시 Codex 리뷰**를 받는다. 구현 결과 전체를 외부 관점으로 한 번 더 검증하는 단계다.

## 리뷰 입력

Technical Spec / 확정 Plan / 변경 파일 목록 / 구현 Phase 결과 / 품질 루프 결과 및 남은 이슈

## 리뷰 관점

Spec·Plan 대비 구현 누락 / 비즈니스 로직 결함 / 레이어 구조 위반 / 테스트·검증 공백 / 품질 루프가 놓친 단순화·컨벤션 이슈

## 검증 티어별 상한

티어는 `{STATE_FILE}`의 `## Verification Tier` **최종 티어**에서 읽는다 (없으면 `## Flags`의 `TIER`, 그것도 없으면 standard).

| 티어 | 총 리뷰 횟수 `{REVIEW_MAX}` | REJECT 재리뷰 | quota 폴백 패널 |
|------|---------------------------|--------------|----------------|
| standard | 4 (초회 + 재리뷰 3회) | 최대 3회 | `general-purpose` 1 에이전트 (아래 리뷰 관점 전체) |
| light | **2** (초회 + 재리뷰 1회) | 최대 1회 | 동일 (1 에이전트) |

마지막 리뷰도 REJECT면 `BLOCKED:CODEX_REVIEW`. 베이스 승격 ⑦로 Phase 8을 재진입한 뒤의 재리뷰는 standard 상한의 **잔여 횟수**만 쓴다 (`overlay/start-workflow.md` §검증 티어 연동).

## Codex 호출 실패 처리

| 감지 패턴 | 분류 | 행동 |
|----------|------|------|
| CLI/MCP 부재 (command not found, 도구 미존재) | 환경 부재 | `SKIPPED:CODEX_UNAVAILABLE` 기록하고 최종 보고서에 사유 기록 |
| quota/rate-limit (429, "usage limit", "rate limit", "quota", "try again at") | quota 차단 | Claude 패널로 리뷰어 대체 + `SKIPPED:CODEX_QUOTA_BLOCKED` 기록 |
| 기타 일시 오류 (타임아웃, 5xx) | 모호 | 1회 재시도 → 재실패 시 quota 차단과 동일 취급 |

`SKIPPED:CODEX_QUOTA_BLOCKED`는 "Codex 호출" 항목에 대한 기록이며, 리뷰 자체는 아래 Claude 패널로 계속 실행된다 (Phase SKIP이 아니다).

**고지 문구** (패널 대체 시): "Codex quota 차단 감지 — Claude 다관점 패널로 대체해 계속 진행합니다 (`SKIPPED:CODEX_QUOTA_BLOCKED` 기록)."

**대체 패널 구성**: Plan 검증 루프의 3관점 패널이 아니라 위 "리뷰 관점"을 그대로 사용하는 `general-purpose` 에이전트 **1개**로 대체한다. 상한·선택지는 아래 Phase 8+ 고유값(티어별 `{REVIEW_MAX}` · `BLOCKED:CODEX_REVIEW`)을 그대로 유지한다.

## 결과 처리 (REJECT 재리뷰는 티어별 상한까지 — standard 3회 / light 1회)

| Verdict | 처리 |
|---------|------|
| APPROVE | 다음 Phase로 진행 |
| CONCERN | 타당한 항목만 수정 후 필요한 검증 재실행 → 다음 Phase로 진행 |
| REJECT | 수정 후 품질 루프의 관련 검증 재실행 → Codex 품질 리뷰 재요청 |
| 상한 도달 (`{REVIEW_MAX}`번째 리뷰도 REJECT) | `BLOCKED:CODEX_REVIEW` — 미해결 이슈 요약과 함께 사용자 선택지 제시 |

상한 도달 시 선택지:
> "Codex 품질 리뷰가 상한({REVIEW_MAX}회)까지 REJECT입니다. 미해결 이슈: {요약}
> 1. 현재 상태로 진행 — 잔존 이슈를 보고서에 기록하고 다음 Phase로
> 2. 리뷰 계속 — 3회 추가
> 3. 중단 — 워크플로우 종료"

`BLOCKED:CODEX_REVIEW` 여도 **자율 실행은 멈추지 않는다.** 선택지 제시는 베이스의 최종 보고 Phase로 이연한다.

## Implementation Notes 규칙

리뷰 결과 반영 과정에서 설계 결정·편차·트레이드오프·미결 질문이 발생하면, 코드 수정 전에 `{IMPL_NOTES}`의 해당 섹션에 한 줄 append 한다 (append-only, 마크다운).
