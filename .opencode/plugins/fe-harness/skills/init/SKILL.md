---
name: init
description: "fe-harness 플러그인의 모든 사전 세팅을 한 번에 진행한다."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/init.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# fe-harness Init

플러그인에서 사용하는 모든 환경 설정을 한 번에 세팅한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

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

- `.claude/fe-harness.local.md` 읽기 → 기존 설정 존재 여부
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
## fe-harness 환경 스캔 결과

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

선택 결과를 `.claude/fe-harness.local.md` 에 YAML frontmatter 포맷으로 저장한다:

```markdown
---
preset: node
language: ko

framework: nextjs
uiLibrary: tailwind
stateManagement: tanstack-query
testRunner: vitest
e2eRunner: playwright
packageManager: pnpm
componentPattern: feature-based
typescript: true
storybook: false

buildCommand: "pnpm build"
testCommand:  "pnpm test"
lintCommand:  "pnpm lint"
typeCheckCommand: "pnpm typecheck"
e2eCommand: "pnpm e2e"

runServerCommand: "pnpm dev"
serverUrl: "http://localhost:3000"

sourceDirs: ["src/"]
testDirs:   ["src/", "tests/", "__tests__/"]

mainBranch: main
featureBranchPrefix: feat/
hotfixBranchPrefix:  hotfix/

commitPrefixes: [Add, Fix, Del, Refactor, Doc, Test, Chore, WIP]
commitCoAuthor: ""

projectConventions: ["CLAUDE.md"]
---

# Project Notes

(프로젝트별 메모는 여기에 자유롭게 작성)
```

필요한 스크립트(`pnpm dev`, `pnpm test` 등)는 `package.json` 의 실제 스크립트 키를 감지하여 기본값을 조정한다.

### Step 4.5: 프로젝트 오버라이드 디렉토리 생성

fe-harness는 플러그인 원본을 수정하지 않고 프로젝트별 스킬/에이전트 동작을 조정할 수 있는 **오버라이드 레이어**를 제공한다 (상세: 플러그인 루트 `OVERRIDES.md`).

디렉토리만 먼저 만든다 (파일은 필요할 때 생성):

```bash
mkdir -p .claude/fe-harness/skills .claude/fe-harness/agents
```

안내용 README를 두되, 이미 존재하면 덮어쓰지 않는다:

```markdown
<!-- .claude/fe-harness/README.md -->
# fe-harness project overrides

이 디렉토리는 프로젝트별 fe-harness 스킬/에이전트 오버라이드를 담는다.
상세 규약은 플러그인 루트 `OVERRIDES.md` 참조.

- `common.md` — 모든 스킬/에이전트에 공통
- `skills/{skill-name}.md` — 특정 스킬 전용
- `agents/{agent-name}.md` — 특정 에이전트 전용

파일은 전부 선택. start-workflow Phase 9 의 보완점이 자동으로 append 된다.
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

설정 파일: `.claude/fe-harness.local.md`
다음 단계: `/fe-harness:doctor`로 전체 상태를 검증하세요.
```
