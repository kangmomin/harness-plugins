> 이 문서는 `start-workflow-mm` 스킬의 Phase 6(baseline 수집), Phase 7.1(Red), Phase 7.2(Green), Phase 9(회귀 대조)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> **테스트 작성 규칙 자체의 canonical은 `/be-harness:unit-test` 스킬이다.** 이 문서는 워크플로우 통합(baseline·배리어·Test Map·충돌 판정)만 정의한다.

# TDD 통합 규약

구현보다 테스트를 먼저 쓰는 이유는 커버리지가 아니라 **회귀 탐지**다.
Spec이 요구하는 동작을 먼저 실패하는 테스트로 고정해 두면, 이후 어떤 수정이 그 동작을 깨뜨렸는지 즉시 드러난다.

## TDD 적용 판정

Phase 6에서 아래를 순서대로 확인하고, 하나라도 걸리면 TDD를 SKIP한다. SKIP 시 워크플로우는 **기존과 완전히 동일하게** 동작한다.

| # | 조건 | 상태 코드 |
|---|------|----------|
| 1 | `$ARGUMENTS`에 `--no-tdd` | `SKIPPED:USER_OPT_OUT` |
| 2 | `{testCommand}` 가 비어있음 | `SKIPPED:NO_TEST_COMMAND` |
| 3 | 테스트 러너가 스위트를 발견하지 못함 | `SKIPPED:NO_TEST_INFRA` |
| 4 | 작업 유형이 `검토` (코드 변경 없음) | `SKIPPED:TASK_TYPE` |
| 5 | Spec에 관측 가능한 조항이 0개 | `SKIPPED:NO_TEST_BASIS` |

- 작업 유형 `디버깅`은 **SKIP하지 않는다.** 재현 테스트를 먼저 고정하는 것이 TDD가 가장 강한 지점이며, Debug Spec의 `RC-nn` 표를 근거로 사용한다.
- Analyze / Verify 모드는 구현 Phase를 경유하지 않으므로 **해당 없음**이다.

SKIP 판정을 `{STATE_FILE}`의 `## Test Baseline` 섹션에 사유와 함께 기록하고 Phase 7으로 진행한다.

---

# Phase 6: 회귀 Baseline 수집

**자율 실행 진입 직전에 수집한다.** 이 시점은 유저와 대화가 가능한 마지막 지점이므로, 수집이 실패해도 선택지를 제시할 수 있다.

```bash
git rev-parse HEAD          # 기준 커밋
{testCommand}               # suite별로 각각 실행
{makeTestCommand}           # 비어있지 않으면 별도 suite로 수집
```

수집 결과를 `{STATE_FILE}`에 기록한다 (템플릿: `references/templates.md`).

| 필드 | 의미 |
|------|------|
| `러너 완주` | 러너가 전체 스위트를 발견·실행 완료했는지. `N`이면 실패 목록을 신뢰할 수 없다 |
| `실패 목록` | `{테스트 식별자} :: {정규화 시그니처}` 형식 |
| `정규화 시그니처` | 실패 메시지 첫 줄에서 **경로·라인 번호·타임스탬프·메모리 주소를 제거**한 문자열 |

**시그니처가 이 설계의 핵심이다.** 식별자만 기록하면 "원래 깨져 있던 테스트가 이번 변경으로 **다른 이유로** 깨진 것"을 놓친다.

**Baseline은 불변이다.** 이후 어떤 Phase도 갱신하지 않는다. iteration별 실행 결과는 별도 스냅샷으로 비교만 한다.

## 수집 실패 시

`{testCommand}` 가 컴파일 에러 등으로 죽어 통과/실패 집계가 나오지 않으면, 유저에게 제시한다:

> "테스트 baseline 수집에 실패했습니다: {에러 요약}
> 1. **이대로 진행** — `regression` 판정 불가를 기록하고 `new_red`만 추적합니다 (회귀 탐지 능력이 저하됩니다)
> 2. **중단** — 기존 테스트를 먼저 고치고 워크플로우를 다시 시작합니다
> 3. **`--no-tdd`로 전환** — TDD 없이 기존 워크플로우로 진행합니다"

1번 선택 시 `## Test Baseline`에 `수집 실패 — regression 판정 불가`를 명시 기록한다.

---

# Phase 7.1: 테스트 우선 (Red)

## sequential 모드

```
Agent tool:
  subagent_type: general-purpose
  model: [Spec ID 개수·도메인 복잡도 기준 선택]
  effort: [동일 기준]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 `/be-harness:unit-test --red` 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.1 상태를 갱신하세요.
    현재 Phase: Phase 7.1 (Red)
    남은 Phase: Phase 7.2, 8, 9, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}

    ## 근거
    상태 파일의 `## Spec` / `## 정상 흐름` / `## Edge Cases` 표의 ID만을 테스트 근거로 사용하세요.
    표 밖의 테스트는 작성하지 마세요.

    ## 금지
    - 구현 코드를 작성하지 마세요. 컴파일을 위한 **빈 스텁**만 허용됩니다.
    - git commit 을 하지 마세요. 커밋은 오케스트레이터가 처리합니다.

    ## 보고
    Spec ID ↔ 테스트 ↔ 파일 ↔ 진단 분류 매핑 표를 반환하세요.
    `already_satisfied` 로 판정한 항목은 그 근거(기존 구현 위치)를 함께 적으세요.
```

## Implementation Notes 기록

Phase 7.1 에이전트는 `{IMPL_NOTES}` 에 아래를 기록한다 (라이브 노트 규약은 SKILL.md 본문을 따른다):

- 각 Spec ID 에 대해 어떤 단언을 선택했는지와 그 근거
- `already_satisfied` 로 판정한 항목의 기존 구현 위치
- `deferred_e2e` 로 넘긴 항목과 그 사유 (왜 단위 테스트로 재현 불가한지)

`cannot_compile` 로 되돌린 항목은 **미결 질문** 섹션에 적어 Phase 14 보고서 상단에 표면화되게 한다.

**be-harness 미설치 폴백**: 세션 스킬 목록에 `/be-harness:unit-test` 가 없으면(또는 호출이 실패하면) 같은 프롬프트에 이 문서의 규칙과 테스트 범위 상한을 인라인해 `general-purpose` 로 수행한다.
고지: "be-harness 미설치 — unit-test 규칙을 인라인한 general-purpose 폴백으로 진행합니다 (권장: be-harness 설치)."

## parallel-slices 모드 (배리어 필수)

병렬 에이전트는 빌드·커밋·테스트 실행·상태 파일 쓰기가 모두 금지되어 있다. 따라서 **오케스트레이터가 검증과 기록을 단독 소유한다.**

```
① 슬라이스별 에이전트 병렬 (같은 메시지에서 동시 호출)
   - 담당: 자기 슬라이스의 테스트 + 스텁 작성만
   - 금지: 커밋 / 빌드 / 테스트 실행 / 상태 파일 쓰기
   - 반환: { Spec ID, 테스트명, 파일, 대상 심볼 } 구조화 결과

② [배리어] 오케스트레이터가 전체 병합 후 1회 글로벌 Red 검증
   {buildCommand} && {testCommand}

③ 오케스트레이터가 TDD Test Map 기록 + Red 커밋
```

**슬라이스별 테스트 실행을 금지하는 이유**: 다른 슬라이스의 미완성 스텁 때문에 자기 슬라이스가 `cannot_compile`로 오판된다.

배리어가 끝나기 전에는 어떤 슬라이스도 Phase 7.2를 시작하지 않는다.

## Red 커밋

Red 검증 통과 후 **오케스트레이터가** 커밋한다.

```bash
git add [테스트 파일 + 스텁]
git commit -m "Test: {작업 요약} — 실패 테스트 선작성 (Red)"
```

`{commitCoAuthor}` 가 비어있지 않으면 `Co-Authored-By` 라인을 본문에 추가한다.

**폴백**: pre-commit 훅이 테스트를 실행해 커밋이 거부되면 Red 커밋을 생략하고 Phase 7.2 종료 후 단일 커밋으로 합친다.
고지: "pre-commit 훅이 Red 커밋을 거부했습니다. Red 이력 없이 Green 커밋으로 합칩니다."

## Phase 7.1 종료 판정

| 조건 | 결과 |
|------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` → Phase 7.2 |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID를 제외하고 Phase 7.2 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — TDD를 SKIP하고 일반 구현으로 Phase 7.2 진행 |
| baseline에 없던 **기존** 테스트가 실패 | `BLOCKED:REGRESSION_AT_RED` — 기록 후 Phase 7.2 진행 |

> **자율 실행 구간 예외**: Phase 7은 유저 질문이 금지된 구간이다. 따라서 상한 도달 시의 번호 선택지(`docs/skill-authoring.md` §6)는 **Phase 14로 이연**한다. `BLOCKED:*`를 기록하되 워크플로우는 멈추지 않는다.

---

# Phase 7.2: 구현 (Green)

Phase 6의 기존 구현 프롬프트(`references/agent-prompts.md`)를 사용하되, TDD가 활성일 때 아래 규칙을 **추가로** 전달한다.

```
    ## TDD 규칙 (Phase 7.1에서 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 테스트를 고쳐서 통과시키는 것은 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 **어느 쪽도 고치지 말고**
      `[TestConflict]` 태그로 보고하세요. 판정은 오케스트레이터가 합니다.
    - 통과 기준: 상태 파일 `## TDD Test Map` 의 모든 테스트 통과
      AND `## Test Baseline` 대비 신규 실패 0건
    - Phase 7.1이 만든 스텁을 실제 구현으로 채우세요.
```

## `[TestConflict]` 판정 (오케스트레이터)

자율 실행 구간이므로 유저에게 묻지 않고 판정한다. **기준은 Spec 원문이다.**

| 상황 | 판정 | 행동 |
|------|------|------|
| 테스트 단언이 Spec 조항과 다름 | 테스트 오류 | 오케스트레이터가 테스트를 수정하고 Test Map을 갱신, 사유 기록 |
| Spec 조항이 모호하거나 부재 | Spec 문제 | 코드·테스트 **양쪽 다 유지**, `[Assumption]` 기록, 해당 ID를 미해결로 표시하고 진행 → Phase 14에서 유저 결정 |

두 번째 경우 코드를 고치지 않는 이유는 `Spec 외 변경 금지 원칙`과 같다 — 유저가 승인한 Spec을 조용히 바꾸지 않는다.

---

# Phase 9: 회귀 대조

Phase 9.1에서 `{testCommand}` 실행 결과를 `## Test Baseline`과 대조해 실패를 분류한다.

## 분류 우선순위 (위에서부터 먼저 적용)

| # | 조건 | 분류 |
|---|------|------|
| 1 | `## TDD Test Map`에 등재된 테스트의 실패 | `new_red` |
| 2 | baseline에 동일 식별자 + **동일** 시그니처 | `pre_existing` |
| 3 | baseline에 동일 식별자 + **다른** 시그니처 | `regression` |
| 4 | baseline에 없는 식별자의 실패 | `regression` |
| 5 | 3·4 판정 전 **1회 재실행**, 결과가 뒤집히면 | `flaky` |

- `flaky`는 regression 집계에서 제외하고 보고만 한다. 유령을 쫓는 수정을 막기 위한 장치다.
- **이름 변경·삭제**: Spec이 승인한 경우에만 허용하고 `## Test Baseline`에 tombstone(`{구 식별자} → {신 식별자}` 또는 `{식별자} → 삭제(근거)`)을 append한다. 승인 없는 소멸은 `regression`으로 취급한다.
  tombstone은 baseline의 **판정 데이터를 바꾸지 않는다** — 대조 시 매핑에만 쓰인다.

## 수정 우선순위

`regression` → `new_red` → `pre_existing`(범위 밖, 보고만) 순으로 처리한다.
Phase 9.5 통합 수정 에이전트에는 이 순서대로 이슈를 전달하고, **테스트 파일 수정 금지** 규칙을 함께 전달한다.

## 테스트 판정

| 판정 | 조건 |
|------|------|
| `PASS` | `regression` 0건 + `new_red` 0건 |
| `WARN` | `flaky`만 존재 |
| `FAIL` | `regression` 1건+ 또는 `new_red` 1건+ |

이 판정이 Phase 9 루프의 종료 조건에 들어간다 (SKILL.md 본문 참조).

---

# read-back 격리 (Phase 9.8 보강)

기존 격리 3규칙에 **네 번째 조항**을 추가한다:

> ④ `## TDD Test Map`을 read-back 에이전트에 **전달하지 않는다.**
> Test Map은 Spec ID ↔ 테스트 매핑이므로, 이를 본 에이전트는 Spec을 역추론하게 되어 격리가 무너진다.
> Test Map은 **오케스트레이터의 대조 입력**으로만 쓴다.

부수 효과: TDD가 활성이면 read-back 1순위 소스(이번 브랜치가 추가·변경한 테스트 파일)가 항상 존재하므로, 3순위(구현 코드) 폴백으로 인한 `A 판정 불가`가 사라진다.

---

# 어휘 규칙

| 필드 | 허용 값 | 등장 위치 |
|------|--------|----------|
| Phase 상태 | `DONE` `IN_PROGRESS` `PENDING` `SKIPPED:{사유}` `BLOCKED:{사유}` `FAIL` | Phase Assignments의 Status 열 |
| 판정 | `PASS` `WARN` `FAIL` | 테스트 판정, Read-back 판정 |
| **진단 분류 (데이터)** | `red_assertion` `already_satisfied` `cannot_compile` `deferred_e2e` `regression` `pre_existing` `new_red` `flaky` | `## TDD Test Map` 과 회귀 대조 표의 셀 안에서만 |

**진단 분류가 Phase Assignments의 Status 열에 등장하면 규약 위반이다** (`docs/skill-authoring.md` §5).
