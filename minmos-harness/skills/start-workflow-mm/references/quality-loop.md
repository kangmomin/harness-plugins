> 이 문서는 `start-workflow-mm` 스킬의 Phase 9(품질 루프)와 Phase 10(Codex 품질 리뷰)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# Phase 9: 품질 루프 상세 (병렬 스캔 → 통합 수정 → 순차 실행 → Read-back)

루프 구조·상한·판정은 SKILL.md 본문이 canonical이다. 이 문서는 각 단계의 실행 상세와 에이전트 프롬프트를 정의한다.

Phase 9.1~9.7은 **루프 안**에서 최대 3회 반복되고, Phase 9.8은 **루프가 종료된 뒤 1회만** 실행된다.

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
    남은 Phase: Phase 9.5~9.8, 10, 11, 12, 13, 14
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
    남은 Phase: Phase 9.6, 9.7, 9.8, 10, 11, 12, 13, 14
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
    남은 Phase: Phase 9.7, 9.8, 10, 11, 12, 13, 14
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

# Phase 9.8: Spec 정합 Read-back (루프 밖, 1회)

품질 루프(9.1~9.7)가 종료된 뒤 **정확히 1회** 실행한다. 루프 안에서 반복하지 않는다 — 수렴 전 산출물을 읽으면 곧 사라질 차이가 Diff로 잡혀 무의미하다.

**목적**: 구현·검증 산출물이 *실제로 보장하는 것*을 **Spec을 모르는 에이전트가 복원**하고, 그 복원본을 Spec과 대조해 조용한 이탈을 드러낸다.
자기가 쓴 Spec을 자기가 읽으면 언제나 일치해 보인다. **격리가 이 단계의 전부다.**

## 입력 소스 선정

| 순위 | 소스 | 조건 |
|------|------|------|
| 1 | 이번 브랜치가 추가·변경한 Go 테스트 파일 | `git diff --name-only main...HEAD` 결과에 `*_test.go`가 있을 때 |
| 2 | Phase 9.6 E2E 테스트 결과 리포트 (`/tmp/e2e-run-report.md`) | 1이 없고, 9.6이 `SKIPPED:*`가 아닐 때 |
| 3 | 변경된 handler/route의 공개 인터페이스 | 1·2 모두 없을 때 |

소스마다 복원 신뢰도가 다르므로 리포트에 **반드시 명시**한다.
3순위는 "테스트가 보장하는 것"이 아니라 "코드가 하는 것"의 복원이므로 Diff 유형 A(검증 누락)를 판정할 수 없다 — 이 경우 A는 집계에서 제외하고 `A 판정 불가(소스=구현 코드)`로 적는다.

세 순위 모두 해당 없으면 `SKIPPED:NO_READBACK_SOURCE`로 기록하고 Phase 10으로 진행한다.

## 격리 규칙 (CRITICAL)

에이전트 프롬프트는 아래 세 조건을 **모두** 만족해야 한다:

1. `{STATE_FILE}`·`{IMPL_NOTES}` 경로를 전달하지 않고, 읽지 말라고 명시한다 (각각 Spec·Plan·엣지 케이스 표 전문과 설계 결정·편차 기록이 들어있다).
2. Spec / Plan / 엣지 케이스 표를 프롬프트 본문에 넣지 않는다.
3. 다른 Phase 프롬프트와 달리 **"상태 파일을 읽고 상태를 갱신하세요" 문구를 넣지 않는다.** 상태 갱신은 오케스트레이터가 대신 수행한다.

> 이 세 줄이 Phase 9.8의 유일한 실효 장치다. 하나라도 빠지면 에이전트가 Spec을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 되고, 이 단계는 요식 행위가 된다.

## Read-back 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: [복원 범위 기준 선택]
  effort: [복원 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 파일만 읽고, 이 코드가 **실제로 보장하는 동작**을 자연어로 복원하세요.

    ## 읽을 파일
    {선정된 소스 파일 경로 목록}

    ## 규칙
    - 위에 나열된 파일과 그것이 직접 참조하는 코드만 읽으세요.
    - `/tmp/workflow-state.md`, `/tmp/implementation-notes.md` 를 비롯한 명세·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 코드의 의도를 추측하지 말고, **단언(assertion)·조건 분기·반환 status code가 실제로 보장하는 것**만 적으세요.
    - 의미를 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 시나리오
    | # | Given (전제) | When (입력·요청) | Then (실제로 검증되는 것) | 출처 |
    |---|--------------|-----------------|--------------------------|------|
    | 1 | 상품 P1 존재, 인증 유저 U1 | POST /v1/reviews {productId:P1, rating:5} | 201, 응답에 id 존재, DB에 1건 생성 | `review_handler_test.go:24` |

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    ### 보장되지 않는 것
    - [읽은 범위에서 눈에 띄게 **검증되지 않고 있는** 동작. 없으면 "없음"]

    완료 후 "복원: N개 시나리오, 해석 불가: M건" 형식으로 보고하세요.
```

## Diff 생성 (오케스트레이터가 직접 수행)

에이전트 결과를 받으면 **오케스트레이터가** 상태 파일의 `## Spec` / `## Edge Cases`와 대조해 아래 5분류로 판정한다.
Spec을 가진 쪽만 할 수 있는 작업이므로 **에이전트에 위임하지 않는다**.

| 유형 | 의미 | 판정 방법 |
|------|------|----------|
| **A. 검증 누락** | Spec 엣지 케이스에 있는데 복원본에 없음 | `EC-nn`이 복원 시나리오 어디에도 대응되지 않음 |
| **B. Spec 밖** | 복원본에 있는데 Spec에 없음 | 암묵 요구가 구현된 것 — 유지/제거 결정 필요 |
| **C. 기대값 불일치** | 같은 케이스인데 기대 동작이 다름 | Spec은 400인데 복원본은 409 등 |
| **D. 해석 불가** | 에이전트가 분리한 항목 | 그대로 승계 |
| **E. 컨벤션 이탈** | 복원본이 **기존 코드**와 다름 | Spec 엣지 케이스 표의 `참조 구현` 열(`file:line`)과 대조 |

**E가 이 단계의 고유 가치다.** A~D는 Spec을 기준으로 한 대조라, Spec 자체가 프로젝트 컨벤션에서 벗어나 있으면 아무것도 잡지 못한다. E는 참조 구현을 기준으로 하므로 "Spec도 구현도 일관되게 틀린" 경우를 잡는다.
참조 구현 열이 `-`이거나 없는 행(구버전 Spec)은 E 판정 대상이 아니다.

## 판정

| 판정 | 조건 |
|------|------|
| `PASS` | A + C + E 합계 0건 |
| `WARN` | A + C + E 합계 1~2건 |
| `FAIL` | A + C + E 합계 3건 이상 |

B·D는 판정에 반영하지 않고 보고만 한다 (유저가 결정할 사항이지 결함이 아니다).

## 수정 금지 (CRITICAL)

Phase 9.8은 **판정만 하고 코드를 수정하지 않는다.** Diff 항목은 대부분 "Spec 해석 차이"라 기계적으로 고칠 수 없고, 자동 수정하면 유저가 승인한 Spec이 조용히 바뀐다.
SKILL.md 본문의 **Spec 외 변경 금지 원칙**과 동일하게 처리한다 — 기록 → Phase 14 보고 → 유저 승인 후 적용.

결과를 상태 파일 `## Readback Diff` 섹션에 기록하고 Phase 10으로 진행한다.
**판정이 `FAIL`이어도 자율 실행을 중단하지 않는다** (유일한 정지 지점은 Phase 14).

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

**고지 문구** (패널 대체 시): "Codex quota 차단 감지 — Claude 다관점 패널로 대체해 계속 진행합니다 (`SKIPPED:CODEX_QUOTA_BLOCKED` 기록)."

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
