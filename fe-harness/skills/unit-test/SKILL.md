---
name: unit-test
description: "컴포넌트/훅/유틸 단위 테스트를 작성하고 실행한다. Spec이 있으면 추적 ID(AC/EC) 기반으로 필요한 만큼만, 없으면 변경 파일 기반으로 작성. '테스트 작성해줘', '유닛 테스트 돌려줘' 요청 시 사용. start-workflow Phase 5.1에서 --red로 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
argument-hint: "[--red] [--init|--doctor] [대상 경로]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/unit-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.


# 단위 테스트

컴포넌트, hooks, 유틸리티 함수에 대해 단위 테스트를 작성하고 실행한다.

## Flags

| 플래그 | 효과 |
|--------|------|
| `--red` | **Red 모드**. 구현 전 단계임을 전제로, 테스트가 실패하는지까지 검증한다 (Step 4). 기본 모드는 통과를 기대한다. |
| `--init` | 테스트 러너 설정 점검 |
| `--doctor` | 전제 조건 진단 |

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## Prerequisites

### 필요 환경
- **테스트 러너**: Vitest 또는 Jest (`.claude/fe-harness.local.md`의 `testRunner` 참조)
- **Testing Library**: `@testing-library/react`, `@testing-library/jest-dom`

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. `.claude/fe-harness.local.md`의 `testRunner` 확인
2. 설정 파일 존재 확인 (`vitest.config.*` / `jest.config.*`)
3. 없으면 기본 설정 파일 생성 안내
4. `@testing-library/react` 설치 여부 확인

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Unit Test — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .claude/fe-harness.local.md | OK / MISSING | testRunner 설정 확인 |
| 테스트 러너 설정 | OK / MISSING | vitest.config / jest.config |
| @testing-library/react | OK / MISSING | package.json 확인 |
| @testing-library/jest-dom | OK / MISSING | package.json 확인 |
| 기존 테스트 파일 | [N]개 발견 | *.test.tsx, *.spec.tsx |
```

---

## Execution

### Step 1: 테스트 근거 확정 (Test Basis)

**모드를 먼저 판정한다.** Spec은 `$ARGUMENTS`, 대화 컨텍스트, 또는 호출자가 전달한 상태 파일에서 얻는다.

| 모드 | 조건 | 근거 |
|------|------|------|
| **Spec 기반** | 추적 ID(`AC-nn`·`EC-nn`)가 있는 Spec이 주어짐 | 그 ID 집합 |
| **Spec 기반 (약식)** | Spec은 있으나 표·ID가 없음 | 본문의 **관측 가능한 조항**에만 ID를 임시 부여, `추적 기준: 본문 조항 기반` 표기 |
| **변경 기반** | Spec이 제공되지 않음 (단독 호출) | `git diff --name-only` 의 변경 파일 |

> 2번째 모드에서 **동작을 추가하지 않는다.** Spec에 없는 기대값을 테스트가 정의하면 그것은 Spec 변경이다.
> Spec에 관측 가능한 조항이 하나도 없으면 `SKIPPED:NO_TEST_BASIS`로 보고하고 종료한다.

**변경 기반 모드**에서는 변경 파일을 아래로 분류한다:

- **컴포넌트** (`.tsx` + JSX 반환): 렌더링 + 인터랙션 테스트
- **Hook** (`use*.ts`): renderHook 테스트
- **유틸리티** (`.ts` 순수 함수): 입출력 테스트
- **API 호출** (fetch/axios): 모킹 테스트

이미 테스트 파일이 존재하면 기존 패턴을 따른다.

### Step 2: 테스트 범위 결정 (필요 수준까지만)

**Spec 기반 모드**에서는 아래 표 밖의 테스트를 작성하지 않는다.

| 작성 대상 | 개수 |
|----------|------|
| `AC-nn` (정상 흐름) | 관측 가능한 렌더 결과당 1개 |
| `EC-nn` (엣지 케이스) | 행당 1개 — props만 다르면 `it.each` 1개로 묶는다 |
| 그 외 | **0개** |

추가 테스트는 Spec의 별도 조항을 인용할 수 있을 때만 허용한다.

**작성 금지**: 커버리지 수치용 테스트, 프레임워크·라이브러리 자체 동작(React가 리렌더하는지 등), 스타일·className 단언, Spec에 없는 방어 로직, props 조합 전수.

**기존 테스트 수정 상한**: 이번 Spec으로 기대 동작이 실제로 바뀐 테스트만 수정한다. 수정 시 `[Breaking]` 태그로 보고한다.

**단위 테스트로 재현 불가한 케이스**는 `deferred_e2e`로 분류해 E2E에 넘긴다. 범주가 아니라 재현 가능성으로 판단한다 — 타이머·네트워크도 fake로 대체 가능하면 단위 테스트 대상이다.

### Step 3: 테스트 작성

각 대상에 맞는 테스트를 작성한다. Spec 기반 모드에서는 각 테스트에 대응 ID를 주석으로 남긴다 (예: `// AC-01`).

#### 컴포넌트 테스트 패턴

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ComponentName } from './ComponentName';

describe('ComponentName', () => {
  it('렌더링이 정상적으로 된다', () => {
    render(<ComponentName />);
    expect(screen.getByRole('...')).toBeInTheDocument();
  });

  it('사용자 인터랙션에 올바르게 반응한다', async () => {
    const onAction = vi.fn();
    render(<ComponentName onAction={onAction} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
```

#### Hook 테스트 패턴

```tsx
import { renderHook, act } from '@testing-library/react';
import { useCustomHook } from './useCustomHook';

describe('useCustomHook', () => {
  it('초기값이 올바르다', () => {
    const { result } = renderHook(() => useCustomHook());
    expect(result.current.value).toBe(initialValue);
  });
});
```

#### 유틸리티 테스트 패턴

```ts
import { utilFunction } from './utils';

describe('utilFunction', () => {
  it('정상 입력에 올바른 결과를 반환한다', () => {
    expect(utilFunction(input)).toBe(expected);
  });

  it('엣지 케이스를 처리한다', () => {
    expect(utilFunction(edgeCase)).toBe(expected);
  });
});
```

#### 스텁 우선 (`--red` 모드)

테스트가 아직 없는 컴포넌트·훅을 import하면 스위트 전체가 트랜스파일되지 않는다. 테스트와 함께 **빈 스텁**을 만든다.

```tsx
export function ProductList() { return null }        // 컴포넌트
export function useProducts() { throw new Error('not implemented') }  // 훅
```

Spec이 명시적으로 고정한 시그니처에만 만들고, 스텁이 무관한 기존 테스트를 깨뜨리지 않는지 확인한다.

### Step 4: 테스트 실행과 판정

`.claude/fe-harness.local.md`의 `testRunner`에 따라 실행:

- **vitest**: `npx vitest run --reporter=verbose {테스트 파일들}`
- **jest**: `npx jest --verbose {테스트 파일들}`

#### `--red` 모드 — 유효 Red 검증

**유효 Red = ① 스위트가 트랜스파일된다 ② 대상 테스트가 실행된다 ③ 실패 원인이 Spec이 요구하는 미구현 동작에 귀속된다.**

타입 에러·import 실패·러너 크래시는 **Red가 아니다.**

테스트 ID당 카운터 1개, **총 3회 합산 상한**:

```
[작성] → 실행
  ├ 어서션 실패 & 원인이 미구현     → red_assertion      ✔ 종료
  ├ 통과 + 단언이 Spec 조항과 일치  → already_satisfied  ✔ 종료 (테스트 유지)
  ├ 통과 + 단언이 부정확            → 교정 (카운터+1) → 재실행
  └ 트랜스파일/러너 실패            → 스텁 보강 (카운터+1) → 재실행

카운터 3 도달 & 미종료 → cannot_compile ✔ 종료 (해당 테스트 변경을 되돌린다)
```

> **`already_satisfied`는 실패가 아니다.** 통과했다는 것이 곧 테스트가 잘못됐다는 뜻은 아니며, 요구된 동작이 이미 구현되어 있을 수 있다.
> 단언이 Spec 조항을 정확히 검증하고 있으면 **그대로 둔다** — 이후 회귀를 막는 자산이 된다. "실패시키기 위해" 단언을 조작하는 것은 금지다.

FE 특유의 함정:

| 증상 | 조치 |
|------|------|
| `getByRole` 이 요소를 못 찾아 실패 | **정상 Red다** — 미구현이 원인 |
| 스냅샷이 없어 자동 생성되며 통과 | 스냅샷은 Red 근거로 쓰지 않는다. role/텍스트 단언으로 대체 |
| 컴포넌트 미존재로 import 실패 | 빈 스텁 생성 후 재실행 |

| 종료 조건 | 결과 |
|----------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID 제외하고 보고 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — 호출자에게 결과 반환 |

### Step 5: 결과 보고

```markdown
## 단위 테스트 결과

**Test Basis**: 추적 ID 기반 / 본문 조항 기반 / 변경 기반
**모드**: 기본 / Red

| Spec ID | 테스트 | 파일 | 분류 | 비고 |
|---------|--------|------|------|------|
| AC-01 | 목록 렌더 | ProductList.test.tsx:12 | red_assertion | 미구현 |
| EC-01 | 빈 목록 EmptyState | ProductList.test.tsx:40 | already_satisfied | 기존 구현이 이미 처리 |

> 변경 기반 모드에서는 `Spec ID` 열 대신 대상 파일명을 적는다.

### 실패 테스트 (기본 모드)
| 테스트 | 에러 | 원인 분석 |
|--------|------|----------|
| "인터랙션 테스트" | Expected: 1, Received: 0 | 이벤트 핸들러 미연결 |

### 종합
- **작성**: N개 (신규 M개 / 수정 K개)
- **분류**: red_assertion N / already_satisfied N / deferred_e2e N / cannot_compile N
- **`[Breaking]`**: [기대 동작이 바뀐 기존 테스트, 없으면 "없음"]
- **범위 밖으로 판단해 작성하지 않은 것**: [있으면 사유와 함께, 없으면 "없음"]
- **상태**: ALL PASS / FAILURES FOUND / RED
```

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 정상 완료 |
| `SKIPPED:NO_TEST_BASIS` | Spec에 관측 가능한 조항이 없음 |
| `BLOCKED:NO_VALID_RED` | `--red` 모드에서 유효 Red를 만들지 못함 |

**진단 분류** (데이터 — 상태 코드와 다른 필드이며 결과 표의 `분류` 열에만 등장한다):
`red_assertion` · `already_satisfied` · `cannot_compile` · `deferred_e2e`

---

## 테스트 원칙

1. **Spec이 상한이다**: Spec 기반 모드에서 근거 없는 테스트는 작성하지 않는다.
2. **사용자 관점 테스트**: 구현 디테일이 아닌 사용자가 보는 것을 테스트한다.
3. **접근성 쿼리 우선**: `getByRole`, `getByLabelText` > `getByTestId`.
4. **모킹 최소화**: 외부 의존성만 모킹, 내부 구현은 모킹하지 않는다.
5. **기존 패턴 준수**: 프로젝트에 이미 테스트가 있으면 해당 패턴을 따른다.
6. **하나의 테스트는 하나의 ID를 검증한다**: 여러 ID를 묶으면 실패 원인이 흐려진다.
