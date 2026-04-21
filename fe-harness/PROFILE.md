# fe-harness Project Profile

모든 fe-harness 스킬은 프로젝트 루트의 **`.claude/fe-harness.local.md`** 를 읽어 프레임워크/러너/빌드 명령 등을 결정한다.
파일이 없으면 `/fe-harness:init` 을 실행해 대화형으로 생성한다.

> profile 은 **값(settings)** 을 담는다. 스킬/에이전트 **동작**을 프로젝트별로 조정하려면 별도의 **Project Overrides** 레이어를 쓴다 → `OVERRIDES.md` 참조.

## 파일 위치

```
<repo-root>/.claude/fe-harness.local.md
```

## 포맷

YAML frontmatter + 선택적 마크다운 본문.

```markdown
---
preset: node
language: ko          # ko | en

# 프레임워크/러너 선택
framework: nextjs             # nextjs | vite | nuxt | cra | 기타
uiLibrary: tailwind           # tailwind | styled-components | shadcn | mui | antd | css-modules
stateManagement: tanstack-query   # tanstack-query | redux-toolkit | swr | zustand | jotai
testRunner: vitest            # vitest | jest
e2eRunner: playwright         # playwright | cypress | none
packageManager: pnpm          # pnpm | yarn | npm | bun
componentPattern: feature-based   # feature-based | atomic | flat
typescript: true
storybook: false

# 빌드/검증 명령
buildCommand: "pnpm build"
testCommand:  "pnpm test"
lintCommand:  "pnpm lint"
typeCheckCommand: "pnpm typecheck"
e2eCommand: "pnpm e2e"

# 로컬 서버
runServerCommand: "pnpm dev"
serverUrl: "http://localhost:3000"

# 소스 레이아웃
sourceDirs: ["src/"]
testDirs:   ["src/", "tests/", "__tests__/"]

# Git
mainBranch: main
featureBranchPrefix: feat/
hotfixBranchPrefix:  hotfix/

# 커밋 컨벤션
commitPrefixes: [Add, Fix, Del, Refactor, Doc, Test, Chore, WIP]
commitCoAuthor: ""

# 프로젝트 컨벤션
projectConventions: ["CLAUDE.md"]
---

# Project Notes

(선택) 프로젝트별 메모.
```

## 읽기 우선순위

1. `.claude/fe-harness.local.md` 의 YAML 값
2. `package.json` 의 `scripts` 자동 감지 (예: `scripts.build` 있으면 `pnpm build`)
3. lock 파일로 패키지 매니저 추정 (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn 등)
4. 사용자에게 `/fe-harness:init` 실행 안내

## 명령 실행 규칙

- 하드코딩된 명령 대신 profile의 `{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{e2eCommand}` 를 사용.
- 명령이 비어있으면 해당 단계를 `SKIPPED`로 표기하고 다음 단계로 진행 (실패 아님).
- `e2eRunner: none` 이거나 `e2eCommand` 가 비어있으면 모든 E2E 단계 SKIP.

## profile 생성

`/fe-harness:init` 실행 → 자동 감지 + 사용자 확인 → 파일 생성.
