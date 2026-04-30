---
name: hyeondong-init-hd
description: "hyeondongs-harness 플러그인의 모든 사전 세팅을 한 번에 진행한다."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

# hyeondong's harness Init

플러그인에서 사용하는 모든 환경 설정을 한 번에 세팅한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## 세팅 대상

| # | 항목 | 관련 스킬 |
|---|------|----------|
| 1 | 프레임워크 선택 | component, request, start-workflow |
| 2 | UI 라이브러리 선택 | component, default-conventions |
| 3 | 상태관리 라이브러리 선택 | default-conventions |
| 4 | 테스트 러너 선택 | unit-test, test-loop |
| 5 | E2E 러너 선택 | e2e-test, test-loop |
| 6 | 패키지 매니저 확인 | 전체 |
| 7 | TypeScript 설정 확인 | lint-check, convention-check |
| 8 | ESLint/Prettier 확인 | lint-check |
| 9 | 컨벤션 선택 | convention-check |
| 10 | Storybook 사용 여부 | component |

---

## 실행 흐름

### Step 1: 현재 상태 스캔

먼저 모든 항목의 현재 상태를 조용히 점검한다:

- `.hyeondong-config.json` 읽기 → 기존 설정 존재 여부
- `package.json` 읽기 → 프레임워크, 의존성, 스크립트 확인
- `tsconfig.json` 존재 여부
- `.eslintrc.*` / `eslint.config.*` 존재 여부
- `.prettierrc.*` 존재 여부
- `vitest.config.*` / `jest.config.*` 존재 여부
- `playwright.config.*` 존재 여부
- `.storybook/` 디렉토리 존재 여부
- `node_modules/` 존재 여부 → 패키지 설치 상태
- lock 파일 (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`, `bun.lockb`) → 패키지 매니저 판별

### Step 2: 상태 요약 보고

스캔 결과를 유저에게 보여준다:

```markdown
## hyeondong's harness 환경 스캔 결과

| # | 항목 | 상태 | 감지된 값 |
|---|------|------|----------|
| 1 | 프레임워크 | DETECTED / UNKNOWN | next / vite / nuxt |
| 2 | UI 라이브러리 | DETECTED / UNKNOWN | tailwind / styled-components / ... |
| 3 | 상태관리 | DETECTED / UNKNOWN | tanstack-query / redux / ... |
| 4 | 테스트 러너 | DETECTED / MISSING | vitest / jest |
| 5 | E2E 러너 | DETECTED / MISSING | playwright / cypress |
| 6 | 패키지 매니저 | DETECTED | pnpm / yarn / npm / bun |
| 7 | TypeScript | OK / MISSING | tsconfig.json 확인 |
| 8 | ESLint | OK / MISSING | 설정 파일 확인 |
| 9 | Prettier | OK / MISSING | 설정 파일 확인 |
| 10 | Storybook | OK / MISSING | .storybook/ 확인 |
```

### Step 3: 설정 확인 및 선택

자동 감지된 값을 기본값으로 제시하고, 유저에게 확인/변경을 요청한다.

#### 3.1 프레임워크

> "프레임워크가 [감지 결과]로 감지되었습니다. 맞나요?"

감지 실패 시:
> "어떤 프레임워크를 사용하나요?"
> 1. `nextjs` — Next.js (App Router / Pages Router)
> 2. `vite` — React + Vite
> 3. `nuxt` — Vue + Nuxt
> 4. `cra` — Create React App
> 5. 기타 (직접 입력)

#### 3.2 UI 라이브러리

> "UI 라이브러리를 선택해주세요:"
> 1. `tailwind` — Tailwind CSS (기본값)
> 2. `styled-components` — Styled Components
> 3. `shadcn` — shadcn/ui + Tailwind
> 4. `mui` — Material UI
> 5. `antd` — Ant Design
> 6. `css-modules` — CSS Modules
> 7. 기타 (직접 입력)

#### 3.3 상태관리

> "상태관리 라이브러리를 선택해주세요:"
> 1. `tanstack-query` — TanStack Query (기본값)
> 2. `redux-toolkit` — Redux Toolkit + RTK Query
> 3. `swr` — SWR
> 4. `zustand` — Zustand (클라이언트 상태 전용)
> 5. `jotai` — Jotai
> 6. 기타 (직접 입력)

#### 3.4 테스트 러너

> "단위 테스트 러너를 선택해주세요:"
> 1. `vitest` — Vitest (기본값)
> 2. `jest` — Jest

#### 3.5 E2E 러너

> "E2E 테스트 러너를 선택해주세요:"
> 1. `playwright` — Playwright (기본값)
> 2. `cypress` — Cypress
> 3. `none` — E2E 테스트 사용 안 함

#### 3.6 컴포넌트 패턴

> "컴포넌트 구조 패턴을 선택해주세요:"
> 1. `feature-based` — 기능별 디렉토리 (기본값)
> 2. `atomic` — Atomic Design (atoms/molecules/organisms)
> 3. `flat` — 플랫 구조 (components/)

#### 3.7 Storybook

> "Storybook을 사용하나요?"
> 1. `true` — 사용 (컴포넌트 생성 시 .stories.tsx 자동 생성)
> 2. `false` — 사용 안 함 (기본값)

#### 3.8 컨벤션 선택

> "convention-check에서 사용할 컨벤션을 설정합니다.
> 어떤 컨벤션을 적용할까요? (복수 선택 가능, 쉼표 구분)"
>
> **플러그인 내장:**
> 1. `default-conventions` — React/Next.js/TypeScript 가이드라인
>
> **프로젝트:**
> 2. `CLAUDE.md` — 프로젝트 아키텍처 컨벤션
>
> 예: `1,2` (전체) 또는 `1` (기본만)

### Step 4: 설정 파일 생성

선택 결과를 `.hyeondong-config.json`으로 저장한다:

```json
{
  "framework": "nextjs",
  "uiLibrary": "tailwind",
  "stateManagement": "tanstack-query",
  "testRunner": "vitest",
  "e2eRunner": "playwright",
  "packageManager": "pnpm",
  "componentPattern": "feature-based",
  "typescript": true,
  "storybook": false,
  "conventions": [
    { "name": "default-conventions", "source": "plugin", "skill": "hyeondongs-harness:default-conventions-hd" },
    { "name": "CLAUDE.md", "source": "project", "path": "CLAUDE.md" }
  ]
}
```

### Step 5: 최종 결과

```markdown
## Init 완료

| # | 항목 | 설정값 |
|---|------|--------|
| 1 | 프레임워크 | nextjs |
| 2 | UI 라이브러리 | tailwind |
| 3 | 상태관리 | tanstack-query |
| 4 | 테스트 러너 | vitest |
| 5 | E2E 러너 | playwright |
| 6 | 패키지 매니저 | pnpm |
| 7 | 컴포넌트 패턴 | feature-based |
| 8 | TypeScript | true |
| 9 | Storybook | false |
| 10 | 컨벤션 | default-conventions, CLAUDE.md |

설정 파일: `.hyeondong-config.json`
다음 단계: `/hyeondongs-harness:hyeondong-doctor-hd`로 전체 상태를 검증하세요.
```
