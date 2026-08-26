> 이 문서는 `start-workflow` 스킬의 Phase 4(baseline 수집), Phase 5.1(Red), Phase 5.2(Green), Phase 7(회귀 대조)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{testCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> **테스트 작성 규칙 자체의 canonical은 `/fe-harness:unit-test` 스킬이다.** 이 문서는 워크플로우 통합(baseline·Test Map·충돌 판정)만 정의한다.

# TDD 통합 규약

구현보다 테스트를 먼저 쓰는 이유는 커버리지가 아니라 **회귀 탐지**다.
Spec이 요구하는 렌더 결과를 먼저 실패하는 테스트로 고정해 두면, 이후 어떤 수정이 그 동작을 깨뜨렸는지 즉시 드러난다.

## TDD 적용 판정

Phase 4에서 아래를 순서대로 확인하고, 하나라도 걸리면 TDD를 SKIP한다. SKIP 시 워크플로우는 **기존과 완전히 동일하게** 동작한다.

| # | 조건 | 상태 코드 |
|---|------|----------|
| 1 | `$ARGUMENTS`에 `--no-tdd` | `SKIPPED:USER_OPT_OUT` |
| 2 | `{testCommand}` 가 비어있고 `{testRunner}` 도 없음 | `SKIPPED:NO_TEST_COMMAND` |
| 3 | 테스트 러너가 스위트를 발견하지 못함 | `SKIPPED:NO_TEST_INFRA` |
| 4 | Spec에 관측 가능한 조항이 0개 | `SKIPPED:NO_TEST_BASIS` |

SKIP 판정을 `{STATE_FILE}`의 `## Test Baseline`에 사유와 함께 기록하고 Phase 5로 진행한다.

---

# Phase 4: 회귀 Baseline 수집

**자율 실행 진입 직전에 수집한다.** 유저와 대화 가능한 마지막 지점이므로, 수집이 실패해도 선택지를 제시할 수 있다.

```bash
git rev-parse HEAD  # 기준 커밋 (= `## Flags`의 START_SHA)
{testCommand} > /tmp/baseline-unit.log 2>&1; EXIT=$?   # 비어있으면 {testRunner} 기반 fallback (vitest run --reporter=verbose / jest --verbose)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/test_failures.py --runner auto --exit-code $EXIT --suite unit --emit-baseline /tmp/baseline-unit.log
{e2eCommand}        # e2eRunner 가 none 이 아니면 같은 방식으로 --suite e2e 수집 (playwright/cypress 출력은 지원 러너 밖 → unparsed 행으로 기록)
```

`--emit-baseline` 출력(표 행)을 `{STATE_FILE}`의 `## Test Baseline`에 그대로 붙인다. 스크립트가 exit ≠ 0이면 아래 필드 규칙대로 수동 기록하고 진단 `script_fallback(test_failures:{사유})`를 남긴다.

| 필드 | 의미 |
|------|------|
| `러너 완주` | 러너가 전체 스위트를 발견·실행 완료했는지. `N`이면 실패 목록을 신뢰할 수 없다. 판정 매트릭스: 종료 마커(jest `Tests:`, vitest `Test Files`) 있음 → `Y` (exit ≠ 0은 "실패 있음"으로만 해석) / 마커 없음 → `N` / 마커 있음 ∧ 실패 0 ∧ exit ≠ 0 → `Y` + `unparsed` 1건 / 테스트 0건 → `Y` + `unparsed`(테스트 0건) |
| `실패 목록` | 항목 = `` `{식별자}` :: `{정규화 시그니처}` ``, 항목 구분은 닫는 백틱과 여는 백틱 사이의 ` / `만. 식별자는 러너 네이티브 전체 ID(`describe › it` / `describe > it`), 키 = suite + 식별자. 내부 백틱은 `'`로, `\|`는 escape |
| `정규화 시그니처` | 실패 메시지 **첫 줄**에서 경로·라인 번호·타임스탬프·메모리 주소·스냅샷 해시를 제거하고 공백을 축약한 문자열. **비교 키는 정규화된 첫 줄 전체**, 표시만 120자 + 해시 8자 |
| `unparsed` | 지원 러너(jest · vitest · go) 밖이거나 파싱이 불확실한 항목. 대조 불가 데이터 — 잔존 시 테스트 판정 `PASS` 불가 |

**시그니처가 이 설계의 핵심이다.** 식별자만 기록하면 "원래 깨져 있던 테스트가 이번 변경으로 **다른 이유로** 깨진 것"을 놓친다.

**Baseline은 불변이다.** 이후 어떤 Phase도 갱신하지 않는다.

## 수집 실패 시

> "테스트 baseline 수집에 실패했습니다: {에러 요약}
> 1. **이대로 진행** — `regression` 판정 불가를 기록하고 `new_red`만 추적합니다 (회귀 탐지 능력이 저하됩니다)
> 2. **중단** — 기존 테스트를 먼저 고치고 워크플로우를 다시 시작합니다
> 3. **`--no-tdd`로 전환** — TDD 없이 기존 워크플로우로 진행합니다"

1번 선택 시 `## Test Baseline`에 `수집 실패 — regression 판정 불가`를 명시 기록한다. 검증 티어가 light면 승격 ④로 standard 전환을 함께 기록한다 (SKILL.md Phase 2 승격 표).

---

# Phase 5.1: 테스트 우선 (Red)

```
Agent tool:
  subagent_type: general-purpose
  model: [Spec ID 개수·컴포넌트 복잡도 기준 선택]
  effort: [동일 기준]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 `/fe-harness:unit-test --red` 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 5.1 상태를 갱신하세요.
    현재 Phase: Phase 5.1 (Red)
    남은 Phase: Phase 5.2, 6, 7, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}

    ## 근거
    상태 파일의 `## Spec` / `## Acceptance Criteria` / `## Edge Cases` 표의 ID만을
    테스트 근거로 사용하세요. 표 밖의 테스트는 작성하지 마세요.

    ## 금지
    - 컴포넌트·훅의 실제 구현을 작성하지 마세요. 렌더를 위한 **빈 스텁**만 허용됩니다.
    - git commit 을 하지 마세요. 커밋은 오케스트레이터가 처리합니다.

    ## 보고
    Spec ID ↔ 테스트 ↔ 파일 ↔ 진단 분류 매핑 표를 반환하세요.
    `already_satisfied` 로 판정한 항목은 그 근거(기존 구현 위치)를 함께 적으세요.
```

`codexMode: max`(`## Flags` `CODEX`)면 러너 프롬프트에 `references/codex-mode.md` §8 포인터 1줄을 추가하고, 테스트·스텁 작성 리프는 Codex sol(`workspace-write`)이 `${CLAUDE_PLUGIN_ROOT}/skills/unit-test/SKILL.md` 절차를 직접 읽어 수행한다 (§5 쓰기 안전 적용, 커밋 금지 동일). none·mix는 위 Skill tool 경로 그대로.

## 유효 Red

**유효 Red = ① 스위트가 컴파일·트랜스파일된다 ② 대상 테스트가 실행된다 ③ 실패 원인이 Spec이 요구하는 미구현 동작에 귀속된다.**

타입 에러·import 실패·러너 크래시는 **Red가 아니다.** 실행조차 되지 않는 테스트는 오라클 역할을 할 수 없다.

FE에서 흔한 함정:

| 증상 | 조치 |
|------|------|
| 컴포넌트가 없어 import 실패 | 빈 스텁 컴포넌트 생성 (`export function X() { return null }`) |
| `screen.getByRole` 이 요소를 못 찾아 실패 | **정상 Red다** — 미구현이 원인 |
| 스냅샷이 없어 자동 생성되며 통과 | 스냅샷 테스트는 Red 근거로 쓰지 않는다. role/텍스트 단언으로 대체 |

## Red 커밋

Red 검증 통과 후 **오케스트레이터가** 커밋한다.

```bash
git add [테스트 파일 + 스텁]
git commit -m "Test: {작업 요약} — 실패 테스트 선작성 (Red)"
```

**폴백**: pre-commit 훅이 테스트를 실행해 커밋이 거부되면 Red 커밋을 생략하고 Phase 5.2 종료 후 단일 커밋으로 합친다.
고지: "pre-commit 훅이 Red 커밋을 거부했습니다. Red 이력 없이 Green 커밋으로 합칩니다."

## Phase 5.1 종료 판정

| 조건 | 결과 |
|------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` → Phase 5.2 |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID 제외하고 Phase 5.2 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — TDD SKIP 후 Phase 5.2 진행 |
| baseline에 없던 **기존** 테스트가 실패 | `BLOCKED:REGRESSION_AT_RED` — 기록 후 Phase 5.2 진행 |

> **자율 실행 구간 예외**: Phase 5는 유저 질문이 금지된 구간이다. 상한 도달 시의 번호 선택지(`docs/skill-authoring.md` §6)는 **Phase 11로 이연**한다. `BLOCKED:*`를 기록하되 워크플로우는 멈추지 않는다.

---

# Phase 5.2: 구현 (Green)

기존 구현 프롬프트(`references/agent-prompts.md`)에 아래 블록을 **추가로** 전달한다.

```
    ## TDD 규칙 (Phase 5.1에서 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 테스트를 고쳐서 통과시키는 것은 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고
      `[TestConflict]` 태그로 보고하세요. 판정은 오케스트레이터가 합니다.
    - Phase 5.1이 만든 스텁 컴포넌트를 실제 구현으로 채우세요.
    - 통과 기준: 상태 파일 `## TDD Test Map`의 모든 테스트 통과
      AND `## Test Baseline` 대비 신규 실패 0건
```

## `[TestConflict]` 판정 (오케스트레이터)

자율 실행 구간이므로 유저에게 묻지 않고 판정한다. **기준은 Spec 원문이다.**

| 상황 | 판정 | 행동 |
|------|------|------|
| 테스트 단언이 Spec 조항과 다름 | 테스트 오류 | 오케스트레이터가 테스트를 수정하고 Test Map을 갱신, 사유 기록 |
| Spec 조항이 모호하거나 부재 | Spec 문제 | 코드·테스트 **양쪽 다 유지**, `[Assumption]` 기록, 해당 ID를 미해결로 표시하고 진행 → Phase 11에서 유저 결정 |

---

# Phase 7: 회귀 대조

Phase 7.4(test-loop) 결과를 `## Test Baseline`과 대조해 분류한다 (7.1은 빌드·타입 체크라 대조 대상이 아니다). 대조는 `assets/test_failures.py --baseline {STATE_FILE}`이 수행한다:

```bash
{testCommand} > /tmp/test-output.log 2>&1; EXIT=$?
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/test_failures.py --runner auto --exit-code $EXIT --suite unit --baseline {STATE_FILE} /tmp/test-output.log
```

스크립트가 exit ≠ 0이면 오케스트레이터가 아래 규칙으로 직접 대조하고 진단 `script_fallback(test_failures:{사유})`를 남긴다. Tombstone 매핑은 분류 **전에** 식별자에 적용하며, 셀 파싱 실패·항목 수 불일치·Tombstone 중복 매핑이면 해당 suite 행 전체를 `unparsed`로 취급한다.

| # | 조건 | 분류 |
|---|------|------|
| 1 | `## TDD Test Map`에 등재된 테스트의 실패 | `new_red` |
| 2 | baseline에 동일 식별자 + **동일** 시그니처 | `pre_existing` |
| 3 | baseline에 동일 식별자 + **다른** 시그니처 | `regression` |
| 4 | baseline에 없는 식별자의 실패 | `regression` |
| 5 | 3·4 판정 전 **1회 재실행**, 결과가 뒤집히면 | `flaky` |

- `flaky`는 regression 집계에서 제외하고 보고만 한다. FE는 비동기 렌더·타이머로 flaky가 잦으므로 이 규칙이 특히 중요하다.
  재실행은 verbose 출력 필수(jest `--verbose`, vitest `--reporter=verbose`) — `--rerun FILE2 --rerun-exit-code M`으로 전달한다. `flaky` ⇔ 재실행이 완주했고 **그 식별자가 PASS로 명시**됨(`✓ {ID}`). 그 외(미완주·PASS 줄 부재)는 원 분류 유지 + `rerun_incomplete`.
- `unparsed`·러너 완주 `N`이 남아 있으면 `PASS` 판정을 내릴 수 없다. 오케스트레이터가 로그를 직접 읽어 분류하고, 그래도 분류하지 못하면 **판정 불가** = 테스트 판정 `FAIL`로 취급한다 (light: 승격 ③).
- **이름 변경·삭제**: Spec이 승인한 경우에만 허용하고 `## Test Baseline`에 tombstone을 append한다. 승인 없는 소멸은 `regression`으로 취급한다.

수정 우선순위: `regression` → `new_red` → `pre_existing`(범위 밖, 보고만).

## 테스트 판정

| 판정 | 조건 |
|------|------|
| `PASS` | `regression` 0건 + `new_red` 0건 |
| `WARN` | `flaky`만 존재 |
| `FAIL` | `regression` 1건+ 또는 `new_red` 1건+ 또는 판정 불가(`unparsed`·완주 `N` 잔존을 분류하지 못함) |

이 판정이 Phase 7 루프의 종료 조건에 들어간다 (SKILL.md 본문 참조).

## frozen 모드

TDD가 활성이면 Phase 7.4의 `/fe-harness:test-loop` 를 **frozen 모드**로 호출한다 (테스트 파일 수정 금지, 소스만 수정).
TDD가 SKIP이면 test-loop은 **기존 동작 그대로** 실행된다 (테스트·소스 양쪽 수정 허용) — 하위 호환을 위한 장치다.
검증 티어가 light면 `--smoke`를 함께 전달한다 — 단위 테스트·frozen 모드는 그대로이고 E2E 범위만 `## Related E2E Specs`로 줄어든다 (test-loop이 `E2E 실행 수준`을 보고).

---

# read-back 격리 (Phase 7.7 보강)

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
| **진단 분류 (데이터)** | `red_assertion` `already_satisfied` `cannot_compile` `deferred_e2e` `regression` `pre_existing` `new_red` `flaky` `unparsed` `rerun_incomplete` | `## TDD Test Map` 과 회귀 대조 표의 셀 안에서만 |

**진단 분류가 Phase Assignments의 Status 열에 등장하면 규약 위반이다** (`docs/skill-authoring.md` §5).
