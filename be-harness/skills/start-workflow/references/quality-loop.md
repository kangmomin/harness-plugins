> 이 문서는 `start-workflow` 스킬의 Phase 8(품질 루프)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> 각 프롬프트의 "남은 Phase" 목록은 예시다 — 실제 값은 상태 파일 `Remaining Phases` 기준으로 치환한다 (예: `--reflect` 미지정 시 Phase 11 제외).
> `## Flags`의 `CODEX: max`면 읽기 전용 단계(8.2+8.3 스캐너 · 8.4)는 Codex `judge` 슬롯, 8.8 Read-back 복원은 `explore` 슬롯, 수정 단계(8.5 · 8.7)는 `write` 슬롯으로 위임하고 러너(8.6)에는 §8 포인터 1줄을 추가한다 — 매핑·호출 계약: `references/codex-mode.md`.

# Phase 8: 품질 루프 상세 (병렬 스캔 → 통합 수정 → 순차 실행 → Read-back)

루프 구조·상한·판정은 SKILL.md 본문이 canonical이다. 이 문서는 각 단계의 실행 상세와 에이전트 프롬프트를 정의한다.
티어별 축소·승격 규칙은 `references/verification-tier.md`가 canonical이다 — light에서 달라지는 단계는 각 절에 **light:** 로 표기한다.

Phase 8.1~8.7은 **루프 안**에서 최대 `{QL_MAX}`회(standard 3 / light 2) 반복되고, Phase 8.8은 **루프가 종료된 뒤 1회만** 실행된다.

## Batch A: 병렬 스캔 (Phase 8.1 ~ 8.4)

세 실행 단위(8.1 Bash 직접 / 8.2·8.3 통합 스캐너 / 8.4 scope-reviewer)를 **하나의 메시지에서 동시에 호출**한다. 모든 서브 에이전트는 **이슈 목록만 반환하며 파일을 수정하지 않는다**.
파일 수정은 Phase 8.5(통합 수정)에서 일괄 처리하여 에이전트 간 파일 편집 경합을 제거한다.

> **CRITICAL**: Batch A의 에이전트는 모두 읽기/분석만 수행한다. 같은 메시지에서 병렬 실행해도 편집 충돌이 발생하지 않는다.
> 만약 에이전트가 파일을 수정했다면 해당 변경을 **무시**하고 이슈 목록만 채택한다 (통합 수정 시 기준 상태에서 다시 편집).

### Phase 8.1: 빌드 + 테스트 — Bash로 직접 실행 (에이전트 아님)

```bash
{buildCommand} && {testCommand} 2>&1
```

둘 중 하나라도 비어있으면 해당 단계 SKIP. 에러 로그를 Batch A 결과에 수집한다. 파일 수정 없음.

**회귀 대조 (TDD 활성 시)**: 테스트 출력을 `assets/test_failures.py`로 파싱해 `{STATE_FILE}`의 `## Test Baseline`과 대조한다. 상세 절차·폴백은 `references/tdd.md`의 "Phase 8: 회귀 대조".

```bash
{testCommand} > /tmp/test-output.log 2>&1; EXIT=$?
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/test_failures.py --runner auto --exit-code $EXIT --suite unit --baseline {STATE_FILE} /tmp/test-output.log
```

| # | 조건 | 분류 |
|---|------|------|
| 1 | `## TDD Test Map`에 등재된 테스트의 실패 | `new_red` |
| 2 | baseline에 동일 식별자 + **동일** 시그니처 | `pre_existing` |
| 3 | baseline에 동일 식별자 + **다른** 시그니처 | `regression` |
| 4 | baseline에 없는 식별자의 실패 | `regression` |
| 5 | 3·4 판정 전 1회 재실행, 결과가 뒤집히면 | `flaky` |

Phase 8.5에 전달하는 이슈 순서는 `regression` → `new_red` 다. `pre_existing`은 **이번 범위 밖이므로 전달하지 않고 보고만** 한다.
TDD가 SKIP된 경우 분류 없이 기존대로 전체 실패 로그를 수집한다.

**light 승격 ③**: `regression` ≥ 1, 또는 판정 불가(러너 완주 N / `UNPARSED` 잔존을 오케스트레이터도 분류하지 못함) → 종료 조건 평가 전에 standard 전환(`{QL_MAX}` = 3 복원), 이 iteration의 8.6부터 full E2E, 루프 후 8.8 실행 (`verification-tier.md` §4).

### Phase 8.2 + 8.3: 품질 스캔 — Simplify + Convention (통합 스캐너 1에이전트)

두 Phase는 **ID·상태·집계를 각각 유지**하되, 하나의 에이전트가 두 스킬을 순차 실행한다
(검사 내용·판정 기준은 각 스킬 그대로 — 에이전트 부팅 고정 비용만 루프 반복마다 1회 절감).

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 스캔 범위 기준 선택]
  effort: [품질 스캔 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 두 스캔을 순서대로 실행하세요.
    상태 파일 `{STATE_FILE}`은 참고로만 읽으세요 (상태 갱신은 오케스트레이터가 수행 — 갱신하지 마세요).
    배정 model/effort: {model}/{effort}
    **파일을 수정하지 말고** 목록만 반환하세요.

    ## 스캔 1 — Simplify (Phase 8.2)
    /be-harness:simplify-loop 를 **dry-run** 관점으로 실행하세요.
    각 항목: {file:line, 현재 코드 요약, 제안 변경, 근거}.

    ## 스캔 2 — Convention (Phase 8.3)
    /be-harness:convention-check 를 실행하세요.
    각 항목: {file:line, 위반 규칙, 제안 수정}.

    두 결과를 섞지 말고 별도 목록으로 유지한 채,
    완료 후 "simplify 후보: N건 / convention 위반: M건" 형식으로 보고하세요.
```

**light (8.2 = `SKIPPED:TIER_LIGHT`)**: 위 프롬프트에서 "## 스캔 1 — Simplify (Phase 8.2)" 블록을 제거하고 스캔 2(convention)만 실행한다. 보고 형식은 "convention 위반: M건". `Phase Results`에 8.2 행을 `SKIPPED:TIER_LIGHT`로 기록한다.

결과 수신 후 **오케스트레이터가** 8.2/8.3 상태를 각각 갱신한다 — `Phase Assignments`는 기존 Phase 8 통합 행을 유지하고, 개별 상태·건수는 `Phase Results` 표에 8.2/8.3 행으로 기록한다.

### Phase 8.4: Scope Review

```
Agent tool:
  subagent_type: be-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요. 프로젝트 루트: {CWD}.
    현재 Phase: Phase 8.4
    남은 Phase: Phase 8.5~8.8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}
    누락/불일치 항목만 반환하고 파일은 수정하지 마세요.
```

## Phase 8.5: 통합 수정

Batch A에서 수집된 이슈(빌드/테스트 에러 + simplify 후보 + convention 위반 + scope 누락)가 하나라도 있으면, **단일 `general-purpose` 에이전트**에 일괄 위임한다. 이슈가 없으면 이 단계를 건너뛴다.

```
Agent tool:
  subagent_type: general-purpose
  model: [수정 이슈 심각도 기준 선택]
  effort: [수정 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 이슈 목록을 순서대로 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.5 상태를 갱신하세요.
    남은 Phase: Phase 8.6, 8.7, 8.8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}

    ## 규칙
    {TDD 활성 시}
    - **테스트 파일을 수정하지 마세요.** 실패한 테스트는 소스를 고쳐서 통과시킵니다.
    - 테스트 자체가 잘못되었다고 판단되면 `[TestConflict]` 태그로 보고만 하세요.
    - `pre_existing` 분류는 이번 범위 밖입니다. 손대지 마세요.

    ## 이슈 목록
    ### 빌드/테스트 에러 (최우선 — regression → new_red 순)
    {build / test 로그 + 회귀 분류}

    ### Scope 누락
    {scope-reviewer 보고서}

    ### Convention 위반
    {convention-check 보고서}

    ### Simplify 후보
    {simplify 후보 목록 — 안전한 변경만 적용, 의심스러우면 생략}

    같은 파일에 여러 이슈가 있으면 한 번의 편집으로 합쳐 처리하세요.
    수정 후 `{buildCommand}` 로 빌드가 통과하는지 확인하세요 (buildCommand가 비어있으면 이 체크는 생략).
    완료 후 "수정: N건, 파일: [목록]" 형식으로 보고하세요.
```

수정 발생 시 `modified = true`.

## Batch B: 순차 실행 (Phase 8.6 → 8.7)

서버/테스트 프로세스가 포트·DB·바이너리를 점유하므로 순차로 실행한다.

### Phase 8.6: E2E Test

```
Agent tool:
  subagent_type: general-purpose
  model: [E2E 범위/실패 심각도 기준 선택]
  effort: [E2E 범위/실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /be-harness:e2e-test-loop {TIER = light면 `--smoke`} 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.6 상태를 갱신하세요.
    남은 Phase: Phase 8.7, 8.8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}
    결과가 `SKIPPED:*`이면 스킵 사유를 그대로 보고하세요.
    완료 후 "이슈: N건, 수정: Y/N, 종료 상태: {DONE|BLOCKED:*|SKIPPED:*}, 실행 수준: {smoke|full|full(smoke 미적용: 사유)}, E2E 리포트: {경로|없음 (SKIPPED:사유)}" 형식으로
    e2e-test-loop의 종료 출력 줄을 **그대로** 옮겨 보고하세요.
```

- `SKIPPED:*` 반환 시 → `modified`에 영향 주지 않고 다음 단계 진행 (루프 재시작 트리거 아님). `Phase Results` 8.6 행에 `E2E 리포트: 없음 (SKIPPED:{사유})`로 기록
- "수정: Y" → `modified = true`
- 실행 수준 줄과 E2E 리포트 경로를 `Phase Results` 8.6 행과 `## Artifacts`(`e2e-report`)에 기록
- **light 승격 ⑥**: 종료 상태가 `BLOCKED:MAX_ITERATIONS`·`BLOCKED:NO_PROGRESS`이거나 실행 수준이 `full(smoke 미적용: …)`이면 standard 전환 + 현재 iteration 종료 후 standard iteration 1회 추가 (`verification-tier.md` §4)

### Phase 8.7: 통합 테스트 (조건부)

profile의 `{makeTestCommand}`가 비어있지 않으면 Bash로 직접 실행:

```bash
{makeTestCommand}
```

비어있으면 `SKIPPED:PROFILE_EMPTY`로 기록하고 넘어간다.
실패 시 `general-purpose` 에이전트로 수정 위임 (Phase 8.5 프롬프트 형식 재사용, 이슈 목록 = 통합 테스트 실패 로그). 수정 발생 시 `modified = true`.

### iteration 종료 시 (light만): 승격 ⑦ 재평가

종료 조건을 평가하기 **전에** `verification-tier.md` §4의 집계 규칙(`START_SHA` 기준 변경 소스 파일 > 3 또는 금지 조건 발견)을 재평가한다. 발화 시 standard 전환 + standard iteration 1회 추가. 승격은 1회뿐이다(latch) — standard가 된 뒤에는 평가하지 않는다.

---

# Phase 8.8: Spec 정합 Read-back (루프 밖, 1회)

**light: `SKIPPED:TIER_LIGHT`** — 승격으로 standard가 됐다면 실행한다.

품질 루프(8.1~8.7)가 종료된 뒤 **정확히 1회** 실행한다. 루프 안에서 반복하지 않는다 — 수렴 전 산출물을 읽으면 곧 사라질 차이가 Diff로 잡혀 무의미하다.

**목적**: 구현·검증 산출물이 *실제로 보장하는 것*을 **Spec을 모르는 에이전트가 복원**하고, 그 복원본을 Spec과 대조해 조용한 이탈을 드러낸다.
자기가 쓴 Spec을 자기가 읽으면 언제나 일치해 보인다. **격리가 이 단계의 전부다.**

## 입력 소스 선정

| 순위 | 소스 | 조건 |
|------|------|------|
| 1 | `{testDirs}` 중 이번 브랜치가 추가·변경한 테스트 파일 | `git diff --name-only {mainBranch}...HEAD` 결과에 테스트 파일이 있을 때 |
| 2 | Phase 8.6 E2E Test Report | 1이 없고, 8.6이 `SKIPPED:*`가 아닐 때 |
| 3 | 변경된 handler/route의 공개 인터페이스 | 1·2 모두 없을 때 |

소스마다 복원 신뢰도가 다르므로 리포트에 **반드시 명시**한다.
TDD가 활성이면 Phase 6.1이 테스트를 선작성하므로 1순위 소스가 항상 존재한다 — 3순위 폴백으로 인한 `A 판정 불가`가 사라진다.
3순위는 "테스트가 보장하는 것"이 아니라 "코드가 하는 것"의 복원이므로 Diff 유형 A(검증 누락)를 판정할 수 없다 — 이 경우 A는 집계에서 제외하고 리포트에 `A 판정 불가(소스=구현 코드)`로 적는다.

세 순위 모두 해당 없으면 `SKIPPED:NO_READBACK_SOURCE`로 기록하고 Phase 9로 진행한다.

## 격리 규칙 (CRITICAL)

에이전트 프롬프트는 아래 네 조건을 **모두** 만족해야 한다:

1. `{STATE_FILE}` 경로를 전달하지 않고, 읽지 말라고 명시한다 (Spec·Plan·엣지 케이스 표 전문이 들어있다).
2. Spec / Plan / 엣지 케이스 표를 프롬프트 본문에 넣지 않는다.
3. 다른 Phase 프롬프트와 달리 **"상태 파일을 읽고 상태를 갱신하세요" 문구를 넣지 않는다.** 상태 갱신은 오케스트레이터가 대신 수행한다.
4. **`## TDD Test Map`을 전달하지 않는다.** Test Map은 Spec ID ↔ 테스트 매핑이므로, 이를 본 에이전트는 Spec을 역추론하게 되어 격리가 무너진다. Test Map은 오케스트레이터의 대조 입력으로만 쓴다.

> 이 네 줄이 Phase 8.8의 유일한 실효 장치다. 하나라도 빠지면 에이전트가 Spec을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 되고, 이 단계는 요식 행위가 된다.

## Read-back 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: sonnet   # 작업 성격 '이해·요약' — SKILL.md Model/Effort 규칙. 판정(Diff)은 오케스트레이터 몫이라 강등이 검출력을 깎지 않는다
  effort: medium
  prompt: |
    프로젝트 루트 {CWD}에서 아래 파일만 읽고, 이 코드가 **실제로 보장하는 동작**을 자연어로 복원하세요.

    ## 읽을 파일
    {선정된 소스 파일 경로 목록}

    ## 규칙
    - 위에 나열된 파일과 그것이 직접 참조하는 코드만 읽으세요.
    - `/tmp/workflow-state.md` 를 비롯한 명세·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 코드의 의도를 추측하지 말고, **단언(assertion)·조건 분기·반환 코드가 실제로 보장하는 것**만 적으세요.
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

Phase 8.8은 **판정만 하고 코드를 수정하지 않는다.** Diff 항목은 대부분 "Spec 해석 차이"라 기계적으로 고칠 수 없고, 자동 수정하면 유저가 승인한 Spec이 조용히 바뀐다.
SKILL.md 본문의 **Spec 외 변경 금지 원칙**과 동일하게 처리한다 — 기록 → Phase 12 보고 → 유저 승인 후 적용.

결과를 상태 파일 `## Readback Diff` 섹션에 기록하고 Phase 9로 진행한다.
**판정이 `FAIL`이어도 자율 실행을 중단하지 않는다** (유일한 정지 지점은 Phase 12).
