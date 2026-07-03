> 이 문서는 `start-workflow-mm` 스킬의 Phase 9(품질 루프)와 Phase 10(Codex 품질 리뷰)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# Phase 9: 품질 루프 상세 (병렬 스캔 → 통합 수정 → 순차 실행)

루프 구조·상한·판정은 SKILL.md 본문이 canonical이다. 이 문서는 각 단계의 실행 상세와 에이전트 프롬프트를 정의한다.

## Batch A: 병렬 스캔 (Phase 9.1 ~ 9.4)

네 단계를 **하나의 메시지에서 동시에 호출**한다. 모든 서브 에이전트는 **이슈 목록만 반환하며 파일을 수정하지 않는다**.
파일 수정은 Phase 9.5(통합 수정)에서 일괄 처리하여 에이전트 간 파일 편집 경합을 제거한다.

> **CRITICAL**: Batch A의 에이전트는 모두 읽기/분석만 수행한다. 만약 에이전트가 파일을 수정했다면 해당 변경을 **무시**하고 이슈 목록만 채택한다.
> 읽기 전용 스캔 에이전트는 `{IMPL_NOTES}`에도 직접 쓰지 않는다 — 발견한 판단 사항은 이슈 보고서에 포함하여 통합 수정 단계가 대신 기록한다.

### Phase 9.1: Go 빌드 + 테스트 — Bash로 직접 실행 (에이전트 아님)

```bash
go build ./cmd/main.go && go test ./internal/... 2>&1
```

에러 로그를 Batch A 결과에 수집한다. 파일 수정 없음.

### Phase 9.2: Simplify Scan

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 스캔 범위 기준 선택]
  effort: [품질 스캔 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /minmos-harness:simplify-loop-mm 를 **dry-run** 관점으로 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 9.2 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    **파일을 수정하지 말고** 단순화 후보 목록만 반환하세요.
    각 항목: {file:line, 현재 코드 요약, 제안 변경, 근거}.
    완료 후 "후보: N건" 형식으로 보고하세요.
```

### Phase 9.3: Convention Check Scan

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 스캔 범위 기준 선택]
  effort: [품질 스캔 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /minmos-harness:convention-check-mm 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 9.3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    **파일을 수정하지 말고** 위반 목록만 반환하세요.
    각 항목: {file:line, 위반 규칙, 제안 수정}.
    완료 후 "위반: N건" 형식으로 보고하세요.
```

### Phase 9.4: Scope Review

```
Agent tool:
  subagent_type: be-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요. 프로젝트 루트: {CWD}.
    현재 Phase: Phase 9.4
    남은 Phase: Phase 9.5~9.7, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}
    누락/불일치 항목만 반환하고 파일은 수정하지 마세요.
```

## Phase 9.5: 통합 수정

Batch A에서 수집된 이슈(빌드/테스트 에러 + simplify 후보 + convention 위반 + scope 누락)가 하나라도 있으면, **단일 `general-purpose` 에이전트**에 일괄 위임한다. 이슈가 없으면 건너뛴다.

```
Agent tool:
  subagent_type: general-purpose
  model: [수정 이슈 심각도 기준 선택]
  effort: [수정 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 이슈 목록을 순서대로 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 9.5 상태를 갱신하세요.
    남은 Phase: Phase 9.6, 9.7, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}

    ## 이슈 목록
    ### 빌드/테스트 에러 (최우선)
    {go build / go test 로그}

    ### Scope 누락
    {scope-reviewer 보고서}

    ### Convention 위반
    {convention-check 보고서}

    ### Simplify 후보
    {simplify 후보 목록 — 안전한 변경만 적용, 의심스러우면 생략}

    같은 파일에 여러 이슈가 있으면 한 번의 편집으로 합쳐 처리하세요.
    수정 후 `go build ./cmd/main.go`로 빌드가 통과하는지 확인하세요.

    [Implementation Notes 규칙]
    Batch A 스캔 에이전트들이 발견했지만 직접 기록하지 못한 판단 사항 중,
    수정 과정에서 설계 결정/편차/트레이드오프/미결 질문에 해당하는 항목이 있으면
    `{IMPL_NOTES}`의 해당 섹션에 한 줄씩 append 하세요(append-only, 마크다운).
    Simplify 후보 중 안전성이 의심되어 적용을 보류한 항목은 `## 미결 질문`에 체크박스로 기록하세요.

    완료 후 "수정: N건, 파일: [목록]" 형식으로 보고하세요.
```

수정 발생 시 `modified = true`.

## Batch B: 순차 실행 (Phase 9.6 → 9.7)

서버/테스트 프로세스가 포트·DB·바이너리를 점유하므로 순차로 실행한다.

### Phase 9.6: E2E Test

```
Agent tool:
  subagent_type: general-purpose
  model: [E2E 범위/실패 심각도 기준 선택]
  effort: [E2E 범위/실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /minmos-harness:e2e-test-loop-mm 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 9.6 상태를 갱신하세요.
    남은 Phase: Phase 9.7, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}
    결과가 `SKIPPED:*`이면 스킵 사유를 그대로 보고하세요.

    [E2E 메인 플로우 규칙]
    상태 파일의 `## E2E 메인 플로우` 섹션을 읽어 e2e-test-loop-mm에 호출 컨텍스트로 전달하세요.
    값이 "자동 도출 (git diff 기반)"이 아니면, 해당 플로우를 Happy Path 필수 시나리오로 반드시 포함하도록 지시하세요.

    [Implementation Notes 규칙]
    E2E에서 드러난 Spec 모호성·예상치 못한 응답 형식·검증 보류 케이스가 있으면
    `{IMPL_NOTES}`의 해당 섹션에 한 줄 append 하세요(append-only, 마크다운).
    `SKIPPED:*`로 검증을 못 했다면 그 사유를 `## 미결 질문`에 체크박스로 기록하세요.

    완료 후 "이슈: N건, 수정: Y/N, 스킵 사유: {있으면}, E2E 리포트 HTML: {경로 또는 미생성}" 형식으로 보고하세요.
    e2e-test-loop-mm이 출력한 `E2E 리포트 HTML:` 절대 경로를 그대로 보고에 포함해야 합니다 (Phase 14 보고서가 이 경로를 참조합니다).
```

- `SKIPPED:*` 반환 시 → `modified`에 영향 주지 않고 다음 단계 진행 (루프 재시작 트리거 아님)
- "수정: Y" → `modified = true`

### Phase 9.7: Make Test

Bash로 직접 실행:

```bash
make test
```

실패 시 `general-purpose` 에이전트로 수정 위임 (Phase 9.5 프롬프트 형식 재사용, 이슈 목록 = make test 실패 로그). 수정 발생 시 `modified = true`.

---

# Phase 10: Codex 품질 리뷰 (항상)

품질 루프가 완료되면 Phase 11로 넘어가기 전에 **반드시 Codex 리뷰**를 받는다.

**Codex 호출 실패 처리**:

| 감지 패턴 | 분류 | 행동 |
|----------|------|------|
| CLI/MCP 부재 (command not found, 도구 미존재) | 환경 부재 | `SKIPPED:CODEX_UNAVAILABLE` 기록하고 Phase 14 보고서에 사유 기록 (현행 유지) |
| quota/rate-limit (429, "usage limit", "rate limit", "quota", "try again at") | quota 차단 | Claude 패널로 리뷰어 대체 + `SKIPPED:CODEX_QUOTA_BLOCKED` 기록 |
| 기타 일시 오류 (타임아웃, 5xx) | 모호 | 1회 재시도 → 재실패 시 quota 차단과 동일 취급 |

`SKIPPED:CODEX_QUOTA_BLOCKED`는 "Codex 호출" 항목에 대한 기록이며, 리뷰 자체는 아래 Claude 패널로 계속 실행된다 (SKIP 아님).

**리뷰 입력**: Technical Spec / 확정 Plan / 변경 파일 목록 / Phase 7 구현 결과 / Phase 9 품질 루프 결과 및 남은 이슈

**리뷰 관점**: Spec/Plan 대비 구현 누락, 비즈니스 로직 결함, 레이어 구조 위반, 테스트·검증 공백, 품질 루프가 놓친 단순화/컨벤션 이슈

**Phase 10 대체 패널 (quota 차단 시)**: Phase 5.3의 3관점이 아니라 위 "리뷰 관점"을 그대로 사용하는 `general-purpose` 에이전트로 대체한다. 상한·선택지는 Phase 10 고유값(아래 REJECT 최대 3회 · `BLOCKED:CODEX_REVIEW`)을 그대로 유지한다.

**결과 처리** (REJECT 재리뷰는 최대 3회):

| Verdict | 처리 |
|---------|------|
| APPROVE | Phase 11로 진행 |
| CONCERN | 타당한 항목만 수정 후 필요한 검증 재실행 → Phase 11로 진행 |
| REJECT | 수정 후 Phase 9 관련 검증 재실행 → Codex 품질 리뷰 재요청 |
| REJECT 3회 도달 | `BLOCKED:CODEX_REVIEW` — 미해결 이슈 요약과 함께 사용자 선택지 제시 |

REJECT 3회 도달 시 선택지:
> "Codex 품질 리뷰가 3회 연속 REJECT입니다. 미해결 이슈: {요약}
> 1. 현재 상태로 진행 — 잔존 이슈를 보고서에 기록하고 Phase 11로
> 2. 리뷰 계속 — 3회 추가
> 3. 중단 — 워크플로우 종료"
