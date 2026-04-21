---
name: unit-test
description: "변경된 컴포넌트/함수 대상으로 단위 테스트를 작성하고 실행한다."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

# 단위 테스트

변경된 컴포넌트, hooks, 유틸리티 함수에 대해 단위 테스트를 작성하고 실행한다.

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

### Step 1: 테스트 대상 파악

1. `git diff --name-only`로 변경된 파일 목록을 확인한다.
2. 변경된 파일 중 테스트 대상을 분류한다:
   - **컴포넌트** (`.tsx` + JSX 반환): 렌더링 + 인터랙션 테스트
   - **Hook** (`use*.ts`): renderHook 테스트
   - **유틸리티** (`.ts` 순수 함수): 입출력 테스트
   - **API 호출** (fetch/axios): 모킹 테스트
3. 이미 테스트 파일이 존재하면 기존 패턴을 따른다.

### Step 2: 테스트 작성

각 대상에 맞는 테스트를 작성한다.

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

### Step 3: 테스트 실행

`.claude/fe-harness.local.md`의 `testRunner`에 따라 실행:

- **vitest**: `npx vitest run --reporter=verbose {테스트 파일들}`
- **jest**: `npx jest --verbose {테스트 파일들}`

### Step 4: 결과 보고

```markdown
## 단위 테스트 결과

| 파일 | 테스트 수 | 통과 | 실패 |
|------|----------|------|------|
| ComponentA.test.tsx | 5 | 5 | 0 |
| useHookB.test.tsx | 3 | 2 | 1 |

### 실패 테스트 (있는 경우)
| 테스트 | 에러 | 원인 분석 |
|--------|------|----------|
| "인터랙션 테스트" | Expected: 1, Received: 0 | 이벤트 핸들러 미연결 |

### 종합
- **총 테스트**: N개
- **통과**: M개
- **실패**: K개
- **상태**: ALL PASS / FAILURES FOUND
```

---

## 테스트 원칙

1. **사용자 관점 테스트**: 구현 디테일이 아닌 사용자가 보는 것을 테스트한다.
2. **접근성 쿼리 우선**: `getByRole`, `getByLabelText` > `getByTestId`.
3. **모킹 최소화**: 외부 의존성만 모킹, 내부 구현은 모킹하지 않는다.
4. **기존 패턴 준수**: 프로젝트에 이미 테스트가 있으면 해당 패턴을 따른다.
