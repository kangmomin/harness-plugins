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
2. `.hyeondong-config.json` (레거시 호환 — 아래 참조)
3. `package.json` 의 `scripts` 자동 감지 (예: `scripts.build` 있으면 `pnpm build`)
4. lock 파일로 패키지 매니저 추정 (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn 등)
5. 사용자에게 `/fe-harness:init` 실행 안내

## 레거시 profile 호환 (`.hyeondong-config.json`)

구 `hyeondongs-harness` 는 fe-harness 스킬을 복제하고 설정만 JSON으로 바꾼 fork였다(자체 에이전트 없이 fe-harness 에이전트에 의존).
중복 스킬 10종을 fe-harness 로 흡수하면서, 기존 프로젝트가 설정을 다시 만들지 않아도 되도록 이 파일을 2순위 profile로 읽는다.

1순위(`.claude/fe-harness.local.md`)가 있으면 이 파일은 **읽지 않는다.**

### 필드 매핑

키는 대부분 동일하다. 다른 것만 아래에 정의한다.

| fe-harness.local.md | .hyeondong-config.json | 처리 |
|---------------------|------------------------|------|
| `framework` · `uiLibrary` · `stateManagement` · `testRunner` · `e2eRunner` · `packageManager` · `componentPattern` · `typescript` · `storybook` | 같은 키 | 그대로 사용 |
| `language` | (없음) | 기본값 `ko` |
| 빌드/검증 명령, 서버, 소스 레이아웃, Git, 커밋 컨벤션 | (없음) | 위 "읽기 우선순위" 3·4순위(자동 감지)로 채우고, 못 채우면 해당 단계 `SKIPPED` |
| `projectConventions: ["CLAUDE.md"]` | `conventions: [{name, source, path\|skill}]` | `source: "project"` 항목의 `path` 만 모아 배열로. `source: "plugin"` 항목은 무시하고 `/fe-harness:default-conventions` 를 쓴다 |

`.hyeondong-config.json` 에만 있는 키는 무시한다.

### 쓰기 규칙

- **레거시 파일에 쓰지 않는다.** `.hyeondong-config.json` 은 읽기 전용으로 취급한다.
- 설정 갱신이 필요한 스킬(`convention-check` 의 `projectConventions` 업데이트 등)은 레거시 profile을 쓰는 중이면 갱신을 건너뛰고 안내한다:
  > "`.hyeondong-config.json` 은 읽기 전용입니다. 설정을 갱신하려면 `/fe-harness:init` 으로 `.claude/fe-harness.local.md` 를 생성하세요 (기존 값이 기본값으로 채워집니다)."
- `/fe-harness:init` 은 `.hyeondong-config.json` 이 있으면 그 값을 기본값으로 제시해 마이그레이션을 돕는다. 원본은 삭제하지 않는다.

## 명령 실행 규칙

- 하드코딩된 명령 대신 profile의 `{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{e2eCommand}` 를 사용.
- 명령이 비어있으면 해당 단계를 `SKIPPED`로 표기하고 다음 단계로 진행 (실패 아님).
- `e2eRunner: none` 이거나 `e2eCommand` 가 비어있으면 모든 E2E 단계 SKIP.

## profile 생성

`/fe-harness:init` 실행 → 자동 감지 + 사용자 확인 → 파일 생성.
