---
name: component
description: "컴포넌트 보일러플레이트를 자동 생성한다. .claude/fe-harness.local.md 설정에 따라 스타일, 테스트, Storybook 파일을 함께 생성."
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
argument-hint: <컴포넌트 이름 또는 설명>
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/component.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Component Generator

`.claude/fe-harness.local.md` 설정에 따라 컴포넌트 보일러플레이트를 생성한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## Prerequisites

- `.claude/fe-harness.local.md` 필요. 없으면 `/fe-harness:init` 실행을 안내한다.

---

## 실행 흐름

### Step 1: 설정 로드

`.claude/fe-harness.local.md`에서 다음을 읽는다:
- `framework` — 프레임워크 (nextjs, vite 등)
- `uiLibrary` — UI 라이브러리 (tailwind, styled-components 등)
- `testRunner` — 테스트 러너 (vitest, jest)
- `componentPattern` — 컴포넌트 구조 패턴 (feature-based, atomic, flat)
- `typescript` — TypeScript 사용 여부
- `storybook` — Storybook 사용 여부

### Step 2: 컴포넌트 정보 수집

`$ARGUMENTS`에서 컴포넌트 이름을 추출한다. 없으면 질문한다:

> "어떤 컴포넌트를 생성할까요? (이름과 간단한 설명)"
> 예: `SearchBar 상품 검색 입력 필드`

추가 질문:

> "컴포넌트 배치 경로를 선택해주세요:"

`componentPattern`에 따라:
- **feature-based**: `src/features/{도메인}/components/{ComponentName}/`
- **atomic**: `src/components/{atoms|molecules|organisms}/{ComponentName}/`
- **flat**: `src/components/{ComponentName}/`

기존 프로젝트의 디렉토리 구조를 `Glob`으로 탐색하여 적합한 경로를 제안한다.

### Step 3: 파일 생성

설정에 따라 다음 파일들을 생성한다:

#### 3.1 컴포넌트 파일 (`{ComponentName}.tsx`)

```tsx
interface {ComponentName}Props {
  // TODO: props 정의
}

export function {ComponentName}({ }: {ComponentName}Props) {
  return (
    <div>
      {/* TODO: 구현 */}
    </div>
  );
}
```

**인터랙티브 요소가 포함되는 경우**, 보일러플레이트에 `aria-label`을 기본 포함한다:

```tsx
// 버튼이 포함되는 컴포넌트
export function {ComponentName}({ }: {ComponentName}Props) {
  return (
    <div>
      <button aria-label="{ComponentName} 동작 설명">
        {/* 아이콘 버튼이면 aria-label 필수 */}
      </button>
    </div>
  );
}

// 입력 필드가 포함되는 컴포넌트
export function {ComponentName}({ }: {ComponentName}Props) {
  return (
    <div>
      <label htmlFor="{componentName}-input">레이블</label>
      <input id="{componentName}-input" aria-describedby="{componentName}-help" />
      <p id="{componentName}-help">도움말 텍스트</p>
    </div>
  );
}
```

#### 3.2 스타일 파일 (uiLibrary에 따라 분기)

| uiLibrary | 파일 | 형식 |
|-----------|------|------|
| `tailwind` | 생성 안 함 | className으로 직접 작성 |
| `css-modules` | `{ComponentName}.module.css` | CSS Modules |
| `styled-components` | `{ComponentName}.styled.ts` | Styled Components |
| `shadcn` | 생성 안 함 | shadcn 컴포넌트 조합 |
| `mui` / `antd` | 생성 안 함 | 라이브러리 컴포넌트 조합 |

#### 3.3 테스트 파일 (`{ComponentName}.test.tsx`)

```tsx
import { render, screen } from '@testing-library/react';
import { {ComponentName} } from './{ComponentName}';

describe('{ComponentName}', () => {
  it('renders without crashing', () => {
    render(<{ComponentName} />);
  });
});
```

#### 3.4 Storybook 파일 (`{ComponentName}.stories.tsx`) — storybook: true일 때만

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { {ComponentName} } from './{ComponentName}';

const meta: Meta<typeof {ComponentName}> = {
  title: '{경로}/{ComponentName}',
  component: {ComponentName},
};

export default meta;
type Story = StoryObj<typeof {ComponentName}>;

export const Default: Story = {
  args: {},
};
```

#### 3.5 배럴 파일 (`index.ts`)

```ts
export { {ComponentName} } from './{ComponentName}';
```

### Step 4: 결과 보고

```markdown
## 컴포넌트 생성 완료

| 파일 | 경로 |
|------|------|
| 컴포넌트 | `src/features/auth/components/LoginForm/LoginForm.tsx` |
| 테스트 | `src/features/auth/components/LoginForm/LoginForm.test.tsx` |
| 스토리 | `src/features/auth/components/LoginForm/LoginForm.stories.tsx` |
| 배럴 | `src/features/auth/components/LoginForm/index.ts` |

다음 단계: 컴포넌트 Props를 정의하고 UI를 구현하세요.
```

---

## 컴포넌트 네이밍 규칙

| 규칙 | 올바른 예 | 잘못된 예 |
|------|----------|----------|
| PascalCase | `SearchBar` | `searchBar`, `search-bar` |
| 의미 있는 이름 | `ProductCard` | `Card1` |
| 접미사 패턴 | `LoginForm`, `UserList`, `NavBar` | `Login`, `Users` |
