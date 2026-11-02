> 일반 위임 프롬프트에는 [작업 계약과 실행 원칙](execution-policy.md)의 인계 항목과 정책 경로를 포함한다. 격리 Read-back에는 적용하지 않는다.

> 이 문서는 `start-workflow` 스킬의 Phase 4(baseline 수집), Phase 5.1(Red), Phase 5.2(Green), Phase 7(회귀 대조)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{testCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> **테스트 작성 규칙 자체의 canonical은 `/fe-harness:unit-test` 스킬이다.** 이 문서는 워크플로우 통합(baseline·Test Map·충돌 판정)만 정의한다.

# TDD 통합 규약

구현보다 테스트를 먼저 쓰는 이유는 커버리지가 아니라 **회귀 탐지**다.
Spec이 요구하는 렌더 결과를 먼저 실패하는 테스트로 고정해 두면, 이후 어떤 수정이 그 동작을 깨뜨렸는지 즉시 드러난다.

## TDD 적용 판정

Phase 4에서 아래를 순서대로 확인하고, 하나라도 걸리면 TDD를 SKIP한다. SKIP 시 TDD 단계(baseline 수집·Phase 5.1 Red·frozen 모드·회귀 대조)만 빠지고 나머지 절차는 그대로 진행한다.

| # | 조건 | 상태 코드 |
|---|------|----------|
| 1 | `$ARGUMENTS`에 `--no-tdd` | `SKIPPED:USER_OPT_OUT` |
| 2 | `{testCommand}` 가 비어있고 `{testRunner}` 도 없음 | `SKIPPED:NO_TEST_COMMAND` |
| 3 | 테스트 러너가 스위트를 발견하지 못함 | `SKIPPED:NO_TEST_INFRA` |
| 4 | Spec에 관측 가능한 조항이 0개 | `SKIPPED:NO_TEST_BASIS` |

SKIP 판정을 `{STATE_FILE}`의 `## Test Baseline`에 사유와 함께 기록하고 Phase 5로 진행한다. R0에 없던 SKIP이고 검증 티어가 standard가 아니면 승격 ④를 함께 기록한다 (`references/verification-tier.md` §5).

---

# Phase 4: 회귀 Baseline 수집

**자율 실행 진입 직전에 수집한다.** 유저와 대화 가능한 마지막 지점이므로, 수집이 실패해도 선택지를 제시할 수 있다.

**단위 명령 정본 확정** (baseline 수집 전): PASS를 관측할 수 없으면 Test Map 통과·baseline 실패 소멸을 확인할 수 없다(`test_failures.py` 진단 `pass_observation_unavailable` = 판정 불가).
1. `{testCommand}`가 비었거나 runner 단일 호출(`[npx|pnpm|yarn] vitest run [옵션]`·`[npx|pnpm|yarn] jest [옵션]`·로컬 `node_modules/.bin/` runner — `&&`·`;`·`|`·환경변수 할당·`cd` 없음)이면, verbose/JSON 리포터가 없을 때 옵션을 보존해 `--reporter=verbose`(vitest)·`--verbose`(jest)를 덧붙인 명령으로 확정한다.
2. 그 외 custom 명령은 baseline 출력에서 PASS 관측이 1건 이상 확인될 때만 그대로 쓴다. 확인되지 않으면(통과 0건 포함) AskUserQuestion 1회 — "관측 가능한 명령 입력"(그 명령으로 baseline 재수집) / "실패 대조만으로 진행(Test Map 통과·소멸 검사 생략 수용)". 수용은 `## Final Decisions`·보고서에 기록하고 그때만 `--expect`·소멸 검사를 생략한다. 비대화형이면 판정 불가를 유지한다.

확정 명령은 `## Test Baseline`의 `단위 명령 (정본):` 다음 `sh` 펜스 블록에 원문 그대로 기록한다(표 셀이 아님 — 파이프·백틱 보존). 이 블록이 **단위 명령 정본**이다 — 5.1·5.2·7.4(test-loop)·재개·finalization이 `{testCommand}` 대신 이 명령을 쓴다. 블록이 없는 이전 상태 파일은 profile에서 해석한다. 아래 `{단위 명령}`은 이 정본이다.

```bash
unset RED_MODE      # 상위 셸의 Red 빠른 실패 설정 상속 차단 (/fe-harness:unit-test "빠른 실패") — 모든 단위 실행 블록 공통
git rev-parse HEAD  # 기준 커밋 (= `## Flags`의 START_SHA)
{단위 명령} > "{RUN_DIR}/baseline-unit.log" 2>&1; EXIT=$?
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/test_failures.py --runner auto --exit-code $EXIT --suite unit --emit-baseline "{RUN_DIR}/baseline-unit.log"
{e2eCommand}        # e2eRunner가 none이면 SKIP, 명령이 비면 PROFILE.md의 runner fallback(playwright는 --reporter=list)으로 --suite e2e 수집 — playwright는 --runner playwright(list·json), cypress는 지원 러너 밖 → unparsed 행
```

E2E 수집은 test-loop Step 2와 같이 락 획득 → `e2eResetCommand`(있으면 `profile.py run --key e2eResetCommand --timeout 540`) → E2E → 락 해제 순서다. 리셋이 실패하면 e2e 행을 성공으로 만들지 않고 아래 "수집 실패 시" 선택지를 제시한다.

검증 티어가 quick이면 `{e2eCommand}` 줄을 실행하지 않고 e2e suite 행을 `SKIPPED:TIER_QUICK`으로 기록한다. 승격 후 E2E 실패의 귀속은 `references/verification-tier.md` §5 "효과"를 따르며, 사후 실행 결과를 baseline으로 쓰지 않는다. Phase 4 안에서 승격 ④가 일어나면 남은 E2E baseline을 새 티어대로 수집한다.

`--emit-baseline` 출력(표 행)을 `{STATE_FILE}`의 `## Test Baseline`에 그대로 붙인다. 스크립트가 exit ≠ 0이면 아래 필드 규칙대로 수동 기록하고 진단 `script_fallback(test_failures:{사유})`를 남긴다.

| 필드 | 의미 |
|------|------|
| `러너 완주` | 러너가 전체 스위트를 발견·실행 완료했는지. `N`이면 실패 목록을 신뢰할 수 없다. 판정 매트릭스: 종료 마커(jest `Tests:`, vitest `Test Files`) 있음 → `Y` (exit ≠ 0은 "실패 있음"으로만 해석) / 마커 없음 → `N` / 마커 있음 ∧ 실패 0 ∧ exit ≠ 0 → `Y` + `unparsed` 1건 / 테스트 0건 → `Y` + `unparsed`(테스트 0건) |
| `실패 목록` | 항목 = `` `{식별자}` :: `{정규화 시그니처}` ``, 항목 구분은 닫는 백틱과 여는 백틱 사이의 ` / `만. 식별자는 러너·파일을 포함한 전체 ID(`{runner}::{file}::{describe › it}`), 키 = suite + 식별자. 내부 백틱은 `'`로, `\|`는 escape |
| `정규화 시그니처` | Go는 실패 메시지 첫 줄에서 경로·라인 번호·타임스탬프·메모리 주소(`0x…`)·goroutine id·소요 시간을 제거하고 공백을 축약한다. JS는 JSON `failureMessages` 또는 텍스트 오류 본문의 matcher·Expected/Received·diff 전체에서 stack/source frame만 제거한다. 실제 오류 값의 경로·숫자는 보존한다. 비교는 전체 문자열, 표시만 120자 + 해시 8자 |
| `unparsed` | 지원 러너(jest · vitest · go · playwright) 밖이거나 파싱이 불확실한 항목. 대조 불가 데이터 — 잔존 시 테스트 판정 `PASS` 불가 |

JS는 가능하면 `--json` reporter 결과 파일을 baseline·현재·재실행에 동일하게 사용한다. `--runner`를 명시하고 동일 저장소 루트 cwd에서 파싱한다. 텍스트는 Jest `--verbose`, Vitest `--reporter=verbose`를 사용한다. 파일 없는 구 baseline은 다시 수집하며 Test Map도 정확한 전체 ID를 기록한다. leaf/suffix 매칭, 다른 파일의 동명 PASS 추정은 금지한다. Playwright는 같은 리포터·같은 cwd(저장소 루트)로 baseline·현재·재실행을 수집한다 — list는 cwd 기준, JSON은 rootDir 기준 경로라 섞어 대조하지 않는다.

**시그니처가 이 설계의 핵심이다.** 식별자만 기록하면 "원래 깨져 있던 테스트가 이번 변경으로 **다른 이유로** 깨진 것"을 놓친다.

**Baseline은 불변이다.** 이후 어떤 Phase도 갱신하지 않는다.

## 수집 실패 시

> "테스트 baseline 수집에 실패했습니다: {에러 요약}
> 1. **이대로 진행** — `regression` 판정 불가를 기록하고 `new_red`만 추적합니다 (회귀 탐지 능력이 저하됩니다)
> 2. **중단** — 기존 테스트를 먼저 고치고 워크플로우를 다시 시작합니다
> 3. **`--no-tdd`로 전환** — TDD 없이 기존 워크플로우로 진행합니다"

1번 선택 시 `## Test Baseline`에 `수집 실패 — regression 판정 불가`를 명시 기록한다. 검증 티어가 standard가 아니면 승격 ④로 standard 전환을 함께 기록한다 (`references/verification-tier.md` §5). 이 경우 선택지에 "1·3번은 검증 티어를 standard로 올립니다"를 함께 표시한다.

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
    테스트 실행 명령: `## Test Baseline`의 `단위 명령 (정본):` 블록 (unit-test Step 4 "호출자 명령").
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
    Spec ID ↔ 테스트 ID(러너 네이티브 정확 ID — unit-test Step 5) ↔ 파일 ↔ 진단 분류 매핑 표를 반환하세요.
    `already_satisfied` 로 판정한 항목은 그 근거(기존 구현 위치)를 함께 적으세요.
```

`codexMode: max`(`## Flags` `CODEX`)면 러너 프롬프트에 `references/codex-mode.md` §8 포인터 1줄을 추가하고, 테스트·스텁 작성 리프는 Codex `write` 슬롯(`workspace-write`)이 `${CLAUDE_PLUGIN_ROOT}/skills/unit-test/SKILL.md` 절차를 직접 읽어 수행한다 (§5 쓰기 안전 적용, 커밋 금지 동일). none·mix는 위 Skill tool 경로 그대로.

## 유효 Red

**유효 Red = ① 스위트가 컴파일·트랜스파일된다 ② 대상 테스트가 실행된다 ③ 실패 원인이 Spec이 요구하는 미구현 동작에 귀속된다.**

타입 에러·import 실패·러너 크래시는 **Red가 아니다.** 실행조차 되지 않는 테스트는 오라클 역할을 할 수 없다.

FE에서 흔한 함정:

| 증상 | 조치 |
|------|------|
| 컴포넌트가 없어 import 실패 | 빈 스텁 컴포넌트 생성 (`export function X() { return null }`) |
| `screen.getByRole` 이 요소를 못 찾아 실패 | **정상 Red다** — 미구현이 원인 |
| 스냅샷이 없어 자동 생성되며 통과 | 스냅샷 테스트는 Red 근거로 쓰지 않는다. role/텍스트 단언으로 대체 |

## Red 영역 병렬

Plan에 이름 계약과 Red 영역 표가 있고 아래 조건을 **모두** 충족하면 영역별 Red를 병렬로 작성한다. 하나라도 아니면 위 단일 에이전트 Red를 쓴다.
조건: Red 영역 2~4개 · 소유 파일 비중첩(공용 파일은 `공용(오케스트레이터)`) · 부모 작업 트리 clean · writer-safety.md "병렬 slice 격리"대로 리프의 실제 cwd/writable root를 영역 checkout으로 지정 가능.

1. **공용 스텁 커밋**: 오케스트레이터가 공용 파일(이름 계약의 모듈·export·시그니처, 테스트 보조 파일)을 이름 계약대로 작성해 부모에 커밋한다(`Test: {작업 요약} — 이름 계약 공용 스텁`). pre-commit 훅이 거부하면 단일 에이전트 Red로 폴백한다. 이 커밋이 영역 checkout의 시작 HEAD이자 receipt `start_sha`(writer_guard 기준)다.
2. **영역 리프 병렬**: 영역마다 `git worktree add --detach "{RUN_DIR}/red-{영역}" HEAD`(테스트를 실행하지 않으므로 의존성 준비 불필요). 프롬프트 = 위 Red 프롬프트 + 배정 Spec ID·소유 파일 + "`/fe-harness:unit-test` Step 1~3(근거·범위·작성)만 수행 — **Step 4 실행·판정 금지(이 지시가 우선)**. 커밋·빌드·상태 파일 쓰기·배정 밖 수정 금지, 공용 파일 변경이 필요하면 `[SharedChange]`로 보고". 반환 = `Spec ID | 테스트 ID(정확 ID) | 파일 | 예정(red/deferred_e2e) | 대상 심볼`.
3. **배리어**: 모든 리프의 실제 종료 → `writer_guard.py scope` PASS → patch·new_files 순차 반영 → `[SharedChange]` 반영 → 전체 단위 1회(RED_MODE 없음) + `test_failures.py --baseline {STATE_FILE} --expect "{RUN_DIR}/red-expect-1.txt"`(실제 작성된 테스트 ID 전부 `red`).
4. **테스트 ID 단위 확정**: FAIL ∧ 시그니처가 미구현 귀속(assertion·role 미발견) → `red_assertion` / FAIL ∧ 트랜스파일·import·러너 오류 → 보정 대상 / PASS 1회 관측 ∧ 단언이 Spec과 일치 → `already_satisfied` / 미관측·중복·skip → 보정 대상. 보정 대상만 부모에서 `/fe-harness:unit-test --red` 1회(그 테스트·파일 한정 — 3회 카운터·`cannot_compile` 되돌리기 동일).
5. **확정 대조**: 확정 분류로 `red-expect-2.txt`를 만든다(`red_assertion` = red, `already_satisfied` = pass, `cannot_compile`·`deferred_e2e`는 제외하고 사유를 Test Map에 기록). 보정·되돌리기로 파일이 바뀌었으면 최종 통합 실행(RED_MODE 없음), 안 바뀌었으면 3의 로그를 재분석 → `regression` 0 · 미관측 0 · baseline 실패 미확인 0 · 분류 일치 확인 → Test Map(정확 ID) 기록 + Red 커밋.

- 종료 판정은 Spec ID별로 테스트 분류를 모아 아래 "Phase 5.1 종료 판정"을 그대로 적용한다. 실행 집합 밖 신규 실패 = `regression` → `BLOCKED:REGRESSION_AT_RED`.
- `codexMode: max`: 영역 리프 = Codex `write` 슬롯, cwd = 영역 checkout, pending·check-stop 배리어는 codex-mode.md §5·writer-safety.md 그대로. 반영 파일은 scope-contract `{OWNED_FILES}`에 합친다.
- 정리(writer-safety.md §6): 부모 반영·hash 대조 뒤 영역 checkout에서 receipt의 소유 경로만 되돌리고(tracked는 `git -C {wt} checkout -- {경로}`, 소유 새 파일은 삭제) `git worktree remove`(강제 금지). 다른 변경이 남아 거부되면 보존하고 경로를 보고한다.

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
      (위임 묶음 블록이 있으면 그 블록의 묶음 통과 기준이 대신합니다)
```

## 위임 묶음·커밋별 검증 (Plan 커밋 단위 표가 있을 때)

위임 단위는 `references/agent-prompts.md` "위임 묶음"을 따른다. TDD 활성이면 오케스트레이터가 dispatch 전에 기대 파일을 만들어 묶음 블록과 함께 전달한다.
Phase 4에서 "실패 대조만" 수용이 기록됐으면 기대 파일 없이 `--baseline`만 쓴다 — 커밋마다 = `regression` 0, 묶음 통과 = `regression` 0 ∧ 완주 Y ∧ `unparsed` 0 ∧ 실패 목록에 완료 단위의 Test Map 테스트 없음(남은 단위의 Red 실패는 `new_red`로 허용). 통과 관측은 수용한 대로 생략한다.

- **단위별 누적 기대 파일** `{RUN_DIR}/expect-{단위 ID}.txt`: `pass` = `already_satisfied` 전부 + 이전 묶음과 이번 묶음의 이 단위까지가 대상으로 하는 테스트 / `red` = 나머지 `red_assertion`. 묶음 끝 기대 = 마지막 단위 파일이고, 마지막 묶음의 마지막 단위 = Test Map 전체 `pass`. 모든 기대 파일(재개 검증 포함)에서 `cannot_compile`·`deferred_e2e` 행은 expect-final과 같이 제외한다. Test Map이 표시명 형식이면 Phase 7 "Test Map 형식 검사"로 정확 ID를 먼저 복원한다.
- **커밋마다** (구현 에이전트): 설정된 lint·typecheck·build + 테스트 → `test_failures.py --baseline {STATE_FILE} --expect expect-{단위 ID}.txt`(부분 실행이면 `--partial`). 범위: 단위 명령 정본이 runner 단일 호출(Phase 4의 1)이면 옵션을 보존해 대상 테스트 + 관련 테스트(`vitest related --run <변경 소스…>` / `jest --findRelatedTests <변경 소스…>`)만, 그 외 custom 명령이면 정본 원문 전체. 부분 실행은 `regression` 0만 본다(관련 테스트 0건은 증거가 아니다).
- **위임 끝 1회** (구현 에이전트): 전체 단위(정본) + `--expect` 마지막 단위 파일. **묶음 통과** = `pass` 전부 1회 PASS(재실행 flaky는 WARN) ∧ `red` 1회 FAIL 또는 PASS(조기 Green — 보고) ∧ `regression` 0 ∧ 미관측·중복·skip 0 ∧ baseline 실패 미확인 0 ∧ 완주 Y ∧ `unparsed` 0. 마지막 단위의 커밋별 검증이 전체 실행이고 명령·기대 파일·검증 트리(result-contract `tested_tree`)가 같으면 그 로그를 재분석하고 다시 실행하지 않는다.
- **커밋 trailer**: 단위 커밋 메시지 끝 trailer 블록(`Co-Authored-By`와 같은 위치)에 `Workflow-Unit: {RUN_ID}/{단위 ID}`.
- **기록·재개**: `## Phase 5.2 Units`(`| 단위 ID | SHA | 커밋별 검증 |`)와 `Phase Results`의 `5.2 묶음 {n}/{N}` 행(단위·SHA·검증 트리·expect 판정)은 오케스트레이터만 쓴다. 재개 시 `git log {START_SHA}..HEAD`의 `Workflow-Unit: {RUN_ID}/…` trailer로 완료 단위를 복구해 Units를 보충하고(미커밋 변경은 기존 재개 규칙) → 완료한 마지막 단위의 기대 파일로 검증 → 남은 단위만 재위임 → 묶음 검증.
- **pre-commit 훅이 단위 커밋을 거부**(전체 Green 요구)하면 "Red 커밋" 폴백처럼 단위 커밋·trailer 없이 5.2 종료 후 단일 Green 커밋으로 합친다. 커밋별 검증은 미커밋 상태에서 수행해 결과 표만 반환하고, 재개는 기존 재개 규칙(미커밋 변경)을 따른다.

## quick 테스트 동반 모드 (quick + TDD 활성)

Phase 5.1이 `SKIPPED:TIER_QUICK`이면 위 블록 대신 아래 규칙을 전달한다. 필수 ID 목록은 오케스트레이터가 승인 Spec에서 만든다 (`references/verification-tier.md` §4.1). Phase 7.5 보완 위임도 같은 블록에 누락·잘못된 대응 ID만 넣어 전달한다.

```
    ## quick 테스트 동반 모드 (Phase 5.1 Red가 생략되었습니다)
    - 필수 ID마다 그 요구를 검증하는 **신규** 테스트를 작성하세요: {필수 ID 목록}
      근거 표 밖의 테스트는 작성하지 마세요. 스냅샷은 근거로 쓰지 말고 role/텍스트 단언을 쓰세요.
    - 기존 테스트(케이스·단언·fixture·스냅샷)는 수정하지 마세요. 충돌하면 `[TestConflict]` 태그로 보고하세요.
    - 작성한 테스트를 verbose로 직접 실행해 green을 확인하세요 (jest `--verbose`, vitest `--reporter=verbose`).
    - 통과 기준: 작성한 신규 테스트 전부 PASS AND `## Test Baseline` 대비 신규 실패 0건
    - 보고: Spec ID | 러너 네이티브 정확 ID | 파일 표.
      식별자는 baseline 규칙과 같습니다(`{runner}::{file}::{describe › it}`). 같은 ID를 두 번 선언하지 마세요.
```

오케스트레이터는 보고 표를 `## Quick Test Evidence`에 기록(보완분은 append)하고 `## TDD Test Map`에는 등재하지 않는다.

## `[TestConflict]` 판정 (오케스트레이터)

자율 실행 구간이므로 유저에게 묻지 않고 판정한다. **기준은 Spec 원문이다.**

| 상황 | 판정 | 행동 |
|------|------|------|
| 테스트 단언이 Spec 조항과 다름 | 테스트 오류 | 오케스트레이터가 테스트를 수정하고 Test Map(Evidence 테스트면 `## Quick Test Evidence`)을 갱신, 사유 기록 |
| Spec 조항이 모호하거나 부재 | Spec 문제 | 코드·테스트 **양쪽 다 유지**, `[Assumption]` 기록, 해당 ID를 미해결로 표시하고 진행 → Phase 11에서 유저 결정 |

---

# Phase 7: 회귀 대조

Phase 7.4(test-loop) 결과를 `## Test Baseline`과 대조해 분류한다 (7.1은 빌드·타입 체크라 대조 대상이 아니다). 대조는 `assets/test_failures.py --baseline {STATE_FILE}`이 수행한다:

```bash
unset RED_MODE
{단위 명령} > "{RUN_DIR}/test-output.log" 2>&1; EXIT=$?
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/test_failures.py --runner auto --exit-code $EXIT --suite unit --baseline {STATE_FILE} [--expect "{RUN_DIR}/expect-final.txt"] "{RUN_DIR}/test-output.log"
```

- **expect-final** (Test Map이 있을 때): 단위 판정 실행은 **전체 단위 실행** + `--expect expect-final.txt`(`## TDD Test Map`의 단위 테스트 전체 = `pass`, `cannot_compile`·`deferred_e2e` 제외). 미관측·중복·skip이면 판정 불가(FAIL). finalization의 단위 재검증도 같은 규칙이다(templates.md "Phase 11 실행 절차"). Phase 4 "실패 대조만" 수용이면 생략한다.
- **Test Map 형식 검사**: 기대 파일은 Test Map `테스트` 열이 정확 ID(`{runner}::{file}::{title}`)일 때 만든다. 이전 형식(표시명) 상태 파일을 재개하면(진단 `test_map_legacy_ids`) Test Map의 파일 열 + 표시명으로 전체 실행 로그의 정확 ID에 **유일하게** 대응하는 것만 복원해 `## TDD Test Map ID 대응`(구 표시명 → 정확 ID) 섹션을 append하고(원 Test Map 보존) 그 대응으로 기대 파일을 만든다. 대응 0개·2개 이상인 행이 하나라도 있으면 판정 불가(FAIL).
- E2E는 `--runner playwright --suite e2e`(e2e baseline 행이 완주 Y일 때만 — test-loop "frozen 모드")로 같은 대조를 한다.

스크립트가 exit ≠ 0이면 오케스트레이터가 아래 규칙으로 직접 대조하고 진단 `script_fallback(test_failures:{사유})`를 남긴다. Tombstone 매핑은 분류 **전에** 식별자에 적용하며, 셀 파싱 실패·항목 수 불일치·Tombstone 중복 매핑이면 해당 suite 행 전체를 `unparsed`로 취급한다.

| # | 조건 | 분류 |
|---|------|------|
| 1 | `## TDD Test Map`에 등재된 테스트의 실패 | `new_red` |
| 2 | baseline에 동일 식별자 + **동일** 시그니처 | `pre_existing` |
| 3 | baseline에 동일 식별자 + **다른** 시그니처 | `regression` |
| 4 | baseline에 없는 식별자의 실패 | `regression` |
| 5 | 3·4 판정 전 **1회 재실행**, 결과가 뒤집히면 | `flaky` |

- `## Quick Test Evidence`의 테스트는 Test Map에 등재하지 않으므로, 실패하면 4행(`regression`)으로 분류된다 (`references/verification-tier.md` §4.1).
- `flaky`는 regression 집계에서 제외하고 보고만 한다. FE는 비동기 렌더·타이머로 flaky가 잦으므로 이 규칙이 특히 중요하다.
  재실행은 verbose 출력 필수(jest `--verbose`, vitest `--reporter=verbose`) — `--rerun FILE2 --rerun-exit-code M`으로 전달한다. `flaky` ⇔ 재실행이 완주했고 **그 식별자가 PASS로 명시**됨(`✓ {ID}`). 그 외(미완주·PASS 줄 부재)는 원 분류 유지 + `rerun_incomplete`.
- `unparsed`·러너 완주 `N`이 남아 있으면 `PASS` 판정을 내릴 수 없다. 오케스트레이터가 로그를 직접 읽어 분류하고, 그래도 분류하지 못하면 **판정 불가** = 테스트 판정 `FAIL`로 취급한다 (T < standard면 승격 ③).
- **이름 변경·삭제**: Spec이 승인한 경우에만 허용하고 `## Test Baseline`에 tombstone을 append한다. 승인 없는 소멸은 `regression`으로 취급한다 — 전체 실행에서 스크립트가 `baseline 실패 미확인` ≥ 1을 보고하면 FAIL이다(부분 실행은 무시).

수정 우선순위: `regression` → `new_red` → `pre_existing`(범위 밖, 보고만).

## 테스트 판정

| 판정 | 조건 |
|------|------|
| `PASS` | `regression` 0건 + `new_red` 0건 |
| `WARN` | `flaky`만 존재 |
| `FAIL` | `regression` 1건+ 또는 `new_red` 1건+ 또는 판정 불가(`unparsed`·완주 `N` 잔존을 분류하지 못함, 스크립트 요약 `PASS 판정 불가(…)`) |

이 판정이 Phase 7 루프의 종료 조건에 들어간다 (SKILL.md 본문 참조). 입력은 test-loop의 **최종 분류**(최종 트리의 마지막 실행)이고, 호출 중 **관측 누적**된 regression·판정 불가는 승격 ③에만 쓴다. quick 종료 증거 게이트 미충족으로 기록한 `INCONCLUSIVE`도 `FAIL`로 취급한다 (test-summary도 FAIL로 집계).

## frozen 모드

TDD가 활성이면 Phase 7.4의 `/fe-harness:test-loop` 를 **frozen 모드**로 호출한다 (테스트 파일 수정 금지, 소스만 수정). `## Quick Test Evidence`가 있으면(Test Map이 비어 있을 수 있으므로) 승격 후에도 프롬프트에 frozen 지시를 명시한다 — Evidence 보완(`references/verification-tier.md` §4.1)만 예외다.
TDD가 SKIP이면 test-loop은 frozen 모드 없이 실행된다 (테스트·소스 양쪽 수정 허용).
검증 티어가 light면 `--smoke`를 함께 전달한다 — 단위 테스트·frozen 모드는 그대로이고 E2E 범위만 `## Related E2E Specs`로 줄어든다 (test-loop이 `E2E 실행 수준`을 보고). quick이면 `--unit-only`를 전달한다 — E2E 단계를 실행하지 않고 `E2E 실행 수준: SKIPPED:UNIT_ONLY`를 보고한다.

---

# read-back 격리 (Phase 7.7 보강)

Phase 7.7 격리 규칙 ④(`references/agent-prompts.md`와 동일):

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
