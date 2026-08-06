> 이 문서는 `start-workflow` 스킬의 Phase 5.2(구현), 6(빌드/타입 체크), 7(품질 루프), 8(리뷰), 9(PR), 10(성찰)에서 로드된다. 단독 실행 금지.
> Phase 5.1(Red)의 프롬프트는 `references/tdd.md`에 있다.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 서브 에이전트 프롬프트 모음

## Phase 5.2: 구현 (workflow-implementer)

### Implementation Notes 공통 추가 블록

**파일을 수정하는 모든 자율 실행 에이전트 프롬프트에 아래 블록을 추가한다.** 읽기 전용 스캔 에이전트에는 넣지 않는다 (이슈 보고서로 대신 전달되고, 통합 수정 단계가 기록한다).

```
    [Implementation Notes 규칙]
    설계 결정·편차·트레이드오프·미결 질문이 발생하면 **코드 수정 전에**
    `{IMPL_NOTES}`의 해당 섹션(`## 설계 결정` / `## 편차` / `## 트레이드오프` / `## 미결 질문`)에
    한 줄을 append 하세요.
    기존 줄 수정 금지(append-only), 마크다운만 작성(HTML/JSON 금지).
    [Assumption] 항목은 `## 편차` 섹션에도 동시 기록하세요.
```


```
Agent tool:
  subagent_type: fe-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 5.2
    남은 Phase: Phase 6, 7, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    [커밋 단위 규칙]
    컴포넌트 1개 = 커밋 1개를 원칙으로 합니다.
    관련 없는 컴포넌트 변경을 하나의 커밋에 묶지 마세요.

    {TDD 활성 시: 아래 "TDD 규칙" 블록을 여기에 삽입}

    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption]·[TestConflict] 목록을 보고하세요.
```

### TDD 활성 시 추가 블록

`$TDD = true` 이고 Phase 5.1이 `SKIPPED:*`가 아니면 아래를 프롬프트에 추가한다:

```
    ## TDD 규칙 (Phase 5.1에서 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 테스트를 고쳐서 통과시키는 것은 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고
      `[TestConflict]` 태그로 보고하세요. 판정은 오케스트레이터가 합니다.
    - Phase 5.1이 만든 스텁 컴포넌트를 실제 구현으로 채우세요.
    - 통과 기준: 상태 파일 `## TDD Test Map`의 모든 테스트 통과
      AND `## Test Baseline` 대비 신규 실패 0건
```

완료 후 유저에게 간략 보고: "Phase 5.2 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

## Phase 6: 빌드 실패 수정 에이전트

빌드/타입 체크 실패 시에만 호출한다.

```
Agent tool:
  subagent_type: general-purpose
  model: [빌드 실패 심각도 기준 선택]
  effort: [빌드 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 `{buildCommand}` / `{typeCheckCommand}` 에러를 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 6 상태를 갱신하세요.
    남은 Phase: Phase 7, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}
    에러 메시지: {빌드 에러 출력}
    수정 후 빌드가 성공하는지 확인하세요.
```

수정 후 커밋: `git add [수정 파일들] && git commit -m "Fix: 빌드 에러 수정 (Phase 6)"`

## Phase 7: 품질 루프 단계별 프롬프트

### Phase 7.2: Simplify

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:simplify-loop 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.2 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    완료 후 "수정: Y/N, N건" 형식으로 보고하세요.
```

### Phase 7.3: Convention Check

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:convention-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    위반 사항이 있으면 수정하세요.
    완료 후 "위반: N건, 수정: Y/N" 형식으로 보고하세요.
```

### Phase 7.4: Test Loop

```
Agent tool:
  subagent_type: general-purpose
  model: [테스트 실패 심각도 기준 선택]
  effort: [테스트 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:test-loop 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.4 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}

    {TDD 활성 시}
    상태 파일에 `## TDD Test Map` 이 있으므로 test-loop은 **frozen 모드**로 동작합니다.
    테스트 파일을 수정하지 말고 소스만 고치세요. 테스트 자체가 잘못되었다고 판단되면
    `[TestConflict]` 태그로 보고만 하세요.
    실패는 `## Test Baseline` 과 대조해 regression / pre_existing / new_red / flaky 로 분류해
    보고하세요. `pre_existing` 은 이번 범위 밖이므로 손대지 마세요.

    완료 후 "이슈: N건, 수정: Y/N, 분류: regression N / new_red N / pre_existing N / flaky N" 형식으로 보고하세요.
```

### Phase 7.5: Scope Review

```
Agent tool:
  subagent_type: fe-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 7.5
    남은 Phase: Phase 7.6, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}
```

### Phase 7.6: Lint Check

```
Agent tool:
  subagent_type: general-purpose
  model: [lint 이슈 심각도 기준 선택]
  effort: [lint 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:lint-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.6 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    이슈가 있으면 수정하세요.
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

## Phase 7.7: Spec 정합 Read-back (루프 밖, 1회)

품질 루프(7.1~7.6)가 종료된 뒤 **정확히 1회** 실행한다. 루프 안에서 반복하지 않는다 — 수렴 전 산출물을 읽으면 곧 사라질 차이가 Diff로 잡혀 무의미하다.

**목적**: 구현·테스트 산출물이 *실제로 보장하는 것*을 **Spec을 모르는 에이전트가 복원**하고, 그 복원본을 Spec과 대조해 조용한 이탈을 드러낸다.
자기가 쓴 Spec을 자기가 읽으면 언제나 일치해 보인다. **격리가 이 단계의 전부다.**

### 입력 소스 선정

| 순위 | 소스 | 조건 |
|------|------|------|
| 1 | 이번 브랜치가 추가·변경한 테스트 파일 (`*.test.tsx`, `*.spec.ts`) | `git diff --name-only main...HEAD` 결과에 있을 때 |
| 2 | Phase 7.4 test-loop / e2e 결과 리포트 | 1이 없고 리포트가 있을 때 |
| 3 | 변경된 컴포넌트의 공개 인터페이스 (Props 타입 + 렌더 분기) | 1·2 모두 없을 때 |

3순위는 "테스트가 보장하는 것"이 아니라 "코드가 하는 것"의 복원이므로 Diff 유형 A(검증 누락)를 판정할 수 없다 — 이 경우 A는 집계에서 제외하고 `A 판정 불가(소스=구현 코드)`로 적는다.
세 순위 모두 해당 없으면 `SKIPPED:NO_READBACK_SOURCE`로 기록하고 Phase 8로 진행한다.

### 격리 규칙 (CRITICAL)

1. `{STATE_FILE}` 경로를 전달하지 않고, 읽지 말라고 명시한다 (Spec·Plan·엣지 케이스 표 전문이 들어있다).
2. Spec / Plan / 엣지 케이스 표를 프롬프트 본문에 넣지 않는다.
3. 다른 Phase 프롬프트와 달리 **"상태 파일을 읽고 상태를 갱신하세요" 문구를 넣지 않는다.** 상태 갱신은 오케스트레이터가 대신 수행한다.
4. **`## TDD Test Map`을 전달하지 않는다.** Test Map은 Spec ID ↔ 테스트 매핑이므로, 이를 본 에이전트는 Spec을 역추론하게 되어 격리가 무너진다. Test Map은 오케스트레이터의 대조 입력으로만 쓴다.

> 이 네 줄이 Phase 7.7의 유일한 실효 장치다. 하나라도 빠지면 에이전트가 Spec을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 되고, 이 단계는 요식 행위가 된다.

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
    - `/tmp/workflow-state.md` 를 비롯한 명세·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 코드의 의도를 추측하지 말고, **단언(assertion)·조건부 렌더링·상태 분기가 실제로 보장하는 것**만 적으세요.
    - 의미를 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 시나리오
    | # | Given (props·상태·데이터) | When (사용자 조작·이벤트) | Then (실제로 검증되는 렌더 결과) | 출처 |
    |---|--------------------------|--------------------------|--------------------------------|------|
    | 1 | items=[] , isLoading=false | 페이지 진입 | EmptyState 렌더, "결과 없음" 텍스트 노출 | `ProductList.test.tsx:42` |

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    ### 보장되지 않는 것
    - [읽은 범위에서 눈에 띄게 **검증되지 않고 있는** 동작 (로딩/에러/빈 상태 누락 등). 없으면 "없음"]

    완료 후 "복원: N개 시나리오, 해석 불가: M건" 형식으로 보고하세요.
```

### Diff 생성 (오케스트레이터가 직접 수행)

에이전트 결과를 받으면 **오케스트레이터가** 상태 파일의 `## Spec` / `## Edge Cases`와 대조해 5분류로 판정한다. Spec을 가진 쪽만 할 수 있으므로 **에이전트에 위임하지 않는다**.

| 유형 | 의미 | 판정 방법 |
|------|------|----------|
| **A. 검증 누락** | Spec 엣지 케이스에 있는데 복원본에 없음 | `EC-nn`이 복원 시나리오 어디에도 대응되지 않음 |
| **B. Spec 밖** | 복원본에 있는데 Spec에 없음 | 암묵 요구가 구현된 것 — 유지/제거 결정 필요 |
| **C. 기대값 불일치** | 같은 케이스인데 기대 동작이 다름 | Spec은 EmptyState인데 복원본은 스켈레톤 유지 등 |
| **D. 해석 불가** | 에이전트가 분리한 항목 | 그대로 승계 |
| **E. 컨벤션 이탈** | 복원본이 **기존 코드**와 다름 | Spec 엣지 케이스 표의 `참조 구현` 열(`file:line`)과 대조 |

**E가 이 단계의 고유 가치다.** A~D는 Spec 기준 대조라 Spec 자체가 프로젝트 패턴에서 벗어나 있으면 아무것도 잡지 못한다. 참조 구현 열이 `-`이거나 없는 행은 E 판정 대상이 아니다.

### 판정

| 판정 | 조건 |
|------|------|
| `PASS` | A + C + E 합계 0건 |
| `WARN` | A + C + E 합계 1~2건 |
| `FAIL` | A + C + E 합계 3건 이상 |

B·D는 판정에 반영하지 않고 보고만 한다.

### 수정 금지 (CRITICAL)

Phase 7.7은 **판정만 하고 코드를 수정하지 않는다.** Diff 항목은 대부분 "Spec 해석 차이"라 기계적으로 고칠 수 없고, 자동 수정하면 유저가 승인한 Spec이 조용히 바뀐다.
결과를 상태 파일 `## Readback Diff` 섹션에 기록하고 Phase 8로 진행한다. **판정이 `FAIL`이어도 자율 실행을 중단하지 않는다** (유일한 정지 지점은 Phase 11).

## Phase 8: 컴포넌트/접근성 리뷰 (병렬 2개)

```
Agent tool (병렬 1):
  subagent_type: fe-harness:component-reviewer
  model: [컴포넌트 변경량 기준 선택]
  effort: [컴포넌트 변경량 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8 component review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}

Agent tool (병렬 2):
  subagent_type: fe-harness:a11y-reviewer
  model: [접근성 영향 기준 선택]
  effort: [접근성 영향 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8 a11y review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
```

Critical 이슈가 있으면 general-purpose 에이전트로 수정을 위임한다.

## Phase 9: PR 생성 (workflow-pr)

```
Agent tool:
  subagent_type: fe-harness:workflow-pr
  model: [PR 복잡도 기준 선택]
  effort: [PR 복잡도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 PR을 생성하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 9
    남은 Phase: Phase 10, 11
    배정 model/effort: {model}/{effort}
    PR URL을 반드시 보고하세요.
```

## Phase 10: 성찰 (workflow-reflection)

```
Agent tool:
  subagent_type: fe-harness:workflow-reflection
  model: [워크플로우 변경량 기준 선택]
  effort: [워크플로우 변경량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 10
    남은 Phase: Phase 11
    배정 model/effort: {model}/{effort}
    성찰 결과와 스킬 보완점을 보고하세요.
```
