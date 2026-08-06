---
name: unit-test
description: "Spec의 추적 ID(AC/EC/RC)를 근거로 단위 테스트를 필요한 만큼만 작성하고 실행한다. '테스트 작성해줘', '유닛 테스트 돌려줘', 구현 전 실패 테스트를 먼저 만들 때 사용. start-workflow Phase 6.1에서 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
argument-hint: "[--red] [--init|--doctor] [대상 경로]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/unit-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# 단위 테스트

Spec이 요구하는 동작을 **필요한 만큼만** 검증하는 단위 테스트를 작성하고 실행한다.

이 스킬은 **테스트 작성 규칙의 canonical**이다. `start-workflow`의 TDD 단계(Phase 6.1)와 다른 하네스의 `unit-test`는 여기의 Step 1~4를 참조하고 차이점만 기술한다.

**플레이스홀더 정의**:

- `{testCommand}`, `{testDirs}`, `{sourceDirs}`, `{language}` = profile(`.claude/be-harness.local.md`)에서 로드
- `{CWD}` = 프로젝트 루트

## Flags

| 플래그 | 효과 |
|--------|------|
| `--red` | **Red 모드**. 구현 전 단계임을 전제로, 테스트가 실패하는지까지 검증한다 (Step 4). 기본 모드는 통과를 기대한다. |
| `--init` | 테스트 러너 설정 상태를 점검하고 부재 시 안내한 뒤 종료 |
| `--doctor` | 전제 조건을 진단해 표로 보고한 뒤 종료 |

## Language Rule

유저와의 모든 대화는 profile의 `{language}` 값(기본 `ko`, 한국어)을 따른다.

## 전제 조건

| 항목 | 확인 | 미충족 시 |
|------|------|----------|
| profile 존재 | `.claude/be-harness.local.md` | "`/be-harness:init`을 먼저 실행하세요" 안내 후 종료 |
| `{testCommand}` | 비어있지 않음 | `SKIPPED:NO_TEST_COMMAND` 보고 후 종료 |
| 테스트 러너 동작 | `{testCommand}` 가 실행되고 러너가 스위트를 발견 | `SKIPPED:NO_TEST_INFRA` 보고 후 종료 |

### `--init`

1. profile의 `{testCommand}`·`{testDirs}` 확인
2. `{testCommand}` 를 실제로 1회 실행해 러너가 동작하는지 확인
3. 기존 테스트 파일을 탐색해 프로젝트의 테스트 패턴(네이밍·테이블 드리븐 여부·헬퍼 위치)을 요약 보고

### `--doctor`

```markdown
## Unit Test — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .claude/be-harness.local.md | OK / MISSING | |
| testCommand | OK / EMPTY / FAIL | 실행 결과 |
| 러너 스위트 발견 | OK / NONE | 발견된 테스트 N개 |
| testDirs 경로 | OK / MISSING_PATHS | |
| 기존 테스트 파일 | [N]개 | |
```

---

## Step 1: 테스트 근거 확정 (Test Basis)

**테스트의 유일한 원천은 Spec이다.** 근거 없는 테스트는 작성하지 않는다.

Spec은 `$ARGUMENTS`, 대화 컨텍스트, 또는 호출자가 전달한 상태 파일에서 얻는다. 3단계로 폴백한다:

| 단계 | 조건 | 근거 집합 | 표기 |
|------|------|----------|------|
| 1 | 추적 ID가 있는 Spec | `AC-nn` + `EC-nn` (+ 디버깅이면 `RC-nn`) | 정상 |
| 2 | 표·ID는 없으나 본문에 **관측 가능한 조항**이 있음 | 그 조항에만 ID를 임시 부여 | `추적 기준: 본문 조항 기반` |
| 3 | 관측 가능한 조항이 0개 | 없음 | `SKIPPED:NO_TEST_BASIS` — 종료 |
| — | Spec 자체가 제공되지 않음 (단독 호출) | `git diff` 기반 변경 함수의 **공개 계약** | `추적 기준 없음` |

> 2단계에서 **동작을 추가하지 않는다.** Spec에 없는 기대값을 테스트가 정의하면 그것은 Spec 변경이다. 조항이 모호하면 지어내지 말고 그 ID를 `deferred_e2e` 또는 미해결로 남긴다.

## Step 2: 테스트 범위 결정 (필요 수준까지만)

근거 집합의 각 ID를 테스트 1개에 매핑한다. **아래 표 밖의 테스트는 작성하지 않는다.**

| 작성 대상 | 개수 |
|----------|------|
| `AC-nn` (정상 흐름) | 관측 가능한 결과당 1개 |
| `EC-nn` (엣지 케이스) | 행당 1개 — 입력만 다르면 **테이블 드리븐 1개로 묶는다** |
| `RC-nn` (재현 케이스) | 재현 조건당 1개 |
| 그 외 | **0개** |

추가 테스트는 **Spec의 별도 조항을 인용할 수 있을 때만** 허용한다. 인용할 조항이 없으면 작성하지 않는다.

### 작성 금지 (명시)

- 커버리지 수치를 올리기 위한 테스트
- getter/setter, 단순 위임 함수
- 프레임워크·ORM·표준 라이브러리 자체의 동작 검증
- Spec에 없는 방어 로직(nil 체크 등)에 대한 테스트
- 파라미터 조합 전수 — Spec이 구분하지 않는 조합은 하나로 묶는다

### 기존 테스트 수정 상한

이번 Spec으로 **기대 동작이 실제로 바뀐** 테스트만 수정한다. 그 외 기존 테스트는 읽기만 한다.
수정했다면 보고에 `[Breaking]` 태그를 붙인다 — 기대 동작 변경은 호환성 검토가 필요한 신호다.

### 단위 테스트로 재현 불가한 케이스

결정론적으로 재현할 수 없는 케이스만 `deferred_e2e`로 분류하고 E2E 단계에 넘긴다.

> **범주가 아니라 재현 가능성으로 판단한다.** "시간 경과"·"외부 호출"이라도 clock 주입이나 인터페이스 seam이 있으면 단위 테스트 대상이다. 실제로 주입 지점이 없을 때만 이연한다.

## Step 3: 테스트 작성

1. **기존 패턴을 먼저 읽는다.** `{testDirs}` 에서 유사 기능의 테스트를 찾아 네이밍·구조·헬퍼·픽스처 방식을 따른다.
2. 각 테스트에 대응 ID를 주석으로 남긴다 (예: `// AC-01`, `// EC-03`).
3. 단언은 **ID가 명시한 관측 결과만** 검증한다. 곁다리 단언을 붙이지 않는다.

### 스텁 우선 (`--red` 모드)

테스트가 아직 없는 심볼을 참조하면 스위트 전체가 컴파일되지 않는다. 테스트와 함께 **빈 스텁**을 만든다.

| 언어 | 스텁 |
|------|------|
| Go | zero value 반환 (`return nil, nil`) |
| TypeScript/Node | `throw new Error('not implemented')` |

- **범위 제한**: Spec이 명시적으로 고정한 시그니처에만 만든다.
- `panic()`은 다른 테스트를 연쇄 실패시킬 수 있으므로 Go에서는 zero value 반환을 기본으로 한다.
- 스텁이 **무관한 기존 테스트를 깨뜨리지 않는지** 확인한다.

## Step 4: 실행과 판정

```bash
{testCommand}
```

### 기본 모드

전체 통과를 기대한다. 실패 시 원인을 분석해 보고한다 (이 스킬은 소스를 고치지 않는다 — 수정은 호출자나 `/be-harness:e2e-test-loop` 가 담당).

### `--red` 모드 — 유효 Red 검증

**유효 Red는 아래 3조건을 모두 만족한다:**

1. 테스트 스위트가 **컴파일된다**
2. 대상 테스트가 **실행된다**
3. 실패 원인이 **Spec이 요구하는 미구현 동작에 귀속된다**

컴파일 에러·러너 크래시는 **Red가 아니다.** 실행조차 되지 않는 테스트는 오라클 역할을 할 수 없다.

#### Red 검증 상태 머신

테스트 ID당 카운터 1개, **총 3회 합산 상한**.

```
[작성] → 실행
  ├ 어서션 실패 & 원인이 미구현     → red_assertion      ✔ 종료
  ├ 통과 + 단언이 Spec 조항과 일치  → already_satisfied  ✔ 종료 (테스트 유지)
  ├ 통과 + 단언이 부정확            → 교정 (카운터+1) → 재실행
  └ 컴파일/러너 실패                → 스텁 보강 (카운터+1) → 재실행

카운터 3 도달 & 미종료 → cannot_compile ✔ 종료 (해당 테스트 변경을 되돌린다)
```

> **`already_satisfied`는 실패가 아니다.** 테스트가 통과했다는 것이 곧 테스트가 잘못됐다는 뜻은 아니며, 요구된 동작이 이미 구현되어 있을 수 있다.
> 단언이 Spec 조항을 정확히 검증하고 있으면 **그대로 둔다** — 이후 회귀를 막는 자산이 된다.
> "실패시키기 위해" 단언을 조작하면 Spec 범위 밖 테스트가 만들어지므로 금지한다.

`단언이 부정확`은 아래처럼 **항상 참이라 아무것도 검증하지 못하는** 경우만 해당한다:

- `assert.NotNil(err)` 없이 에러 경로를 지나침
- 조항과 무관한 필드만 단언
- 조건 없이 항상 성립하는 단언 (`assert.True(true)` 류)

| 종료 조건 | 결과 |
|----------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | DONE |
| 일부 ID가 `cannot_compile` | DONE — 해당 ID만 제외하고 보고 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — 아래 선택지 제시 |

전체 실패 시:
> "유효한 Red 상태를 만들지 못했습니다: {에러 요약}
> 1. TDD 없이 진행 — 테스트를 되돌리고 일반 구현으로 넘어감
> 2. 스텁을 직접 지정 — 필요한 시그니처를 알려주면 그에 맞춰 재시도
> 3. 중단 — 여기서 종료"

> 호출자가 자율 실행 구간(`start-workflow` Phase 6)이면 질문 대신 결과만 반환한다. 선택지 제시는 호출자가 워크플로우 종료 시점에 수행한다.

## 출력 형식

```markdown
## 단위 테스트 결과

**Test Basis**: 추적 ID 기반 / 본문 조항 기반 / 추적 기준 없음
**모드**: 기본 / Red

| Spec ID | 테스트 | 파일 | 분류 | 비고 |
|---------|--------|------|------|------|
| AC-01 | TestCreateUser_정상 | user_test.go:12 | red_assertion | 미구현 |
| EC-01 | TestCreateUser_중복이메일 | user_test.go:42 | already_satisfied | 기존 구현이 이미 409 반환 |
| EC-02 | — | — | deferred_e2e | 외부 결제사 타임아웃 — 주입 지점 없음 |
| RC-01 | TestOrder_음수수량 | order_test.go:88 | cannot_compile | 3회 시도 후 되돌림 |

### 종합
- **작성**: N개 (신규 M개 / 수정 K개)
- **분류**: red_assertion N / already_satisfied N / deferred_e2e N / cannot_compile N
- **`[Breaking]`**: [기대 동작이 바뀐 기존 테스트, 없으면 "없음"]
- **범위 밖으로 판단해 작성하지 않은 것**: [있으면 사유와 함께, 없으면 "없음"]
```

마지막 줄에 `"테스트: N개, 분류: {요약}"` 형식으로 한 줄 요약한다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 정상 완료 |
| `SKIPPED:NO_TEST_COMMAND` | profile에 `{testCommand}` 없음 |
| `SKIPPED:NO_TEST_INFRA` | 테스트 러너가 동작하지 않음 |
| `SKIPPED:NO_TEST_BASIS` | Spec에 관측 가능한 조항이 없음 |
| `BLOCKED:NO_VALID_RED` | `--red` 모드에서 유효 Red를 만들지 못함 |

**진단 분류** (데이터 — 위 상태 코드와 다른 필드이며 결과 표의 `분류` 열에만 등장한다):
`red_assertion` · `already_satisfied` · `cannot_compile` · `deferred_e2e`

## 테스트 원칙

1. **Spec이 상한이다.** 근거 없는 테스트는 작성하지 않는다.
2. **공개 계약을 테스트한다.** 내부 구현 디테일이 아니라 호출자가 관측하는 결과를 검증한다.
3. **모킹 최소화.** 외부 경계(DB·HTTP·시계)만 대체하고 내부 로직은 실제로 실행한다.
4. **기존 패턴 준수.** 프로젝트에 테스트가 있으면 그 구조를 따른다.
5. **하나의 테스트는 하나의 ID를 검증한다.** 여러 ID를 한 테스트에 묶으면 실패 원인이 흐려진다.
