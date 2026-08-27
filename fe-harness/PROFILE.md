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
codexMode: mix        # none | mix | max — start-workflow의 Codex 사용 모드 (none: Codex 미사용·Claude 패널 리뷰 / mix: Plan 리뷰만 Codex / max: 탐색·판정·구현 서브에이전트까지 Codex 위임). `--codex` 또는 첫 실행 질문으로 저장
# codexModels:         # 선택 — Codex 위임 모델 슬롯(review | explore | judge | write). 생략 슬롯 = OpenAI 기본값(codex-mode.md 기본값 표). `--codex-models` 또는 init으로 저장
#   review: { provider: zai, model: glm-5.3, effort: high }     # provider = openai | ~/.codex/config.toml [model_providers.<id>]의 id — 아래 "Codex provider 설정"
#   write:  { provider: openrouter, model: moonshotai/kimi-k2.7 }

# 프레임워크/러너 선택
framework: nextjs             # nextjs | vite | nuxt | cra | 기타
uiLibrary: tailwind           # tailwind | styled-components | shadcn | mui | antd | css-modules
stateManagement: tanstack-query   # tanstack-query | redux-toolkit | swr | zustand | jotai
testRunner: vitest            # vitest | jest
e2eRunner: playwright         # playwright | cypress | none
reportDir: ""                 # Workflow Report(md) 등 리포트 저장 디렉토리. 비우면 `.claude/harness-reports`. work-log vault 하위 경로를 지정하면 wiki 인덱싱 대상이 된다
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
e2eLockDir: ""                # E2E 실행 락 디렉토리. 비우면 자동 해석
                              # (work-log vault의 .wiki/e2e-locks → 없으면 /tmp/harness-e2e-locks).
                              # 환경변수 HARNESS_E2E_LOCK_DIR 로도 지정 가능.

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
| `codexMode` | (없음) | 기본값 `mix`, ephemeral — 레거시 파일에는 쓰지 않는다 (저장하려면 `/fe-harness:init`) |
| `codexModels` | (없음) | 기본값(OpenAI 슬롯), ephemeral — 레거시 파일에는 쓰지 않는다 (저장하려면 `/fe-harness:init`) |
| 빌드/검증 명령, 서버, 소스 레이아웃, Git, 커밋 컨벤션 | (없음) | 위 "읽기 우선순위" 3·4순위(자동 감지)로 채우고, 못 채우면 해당 단계 `SKIPPED` |
| `projectConventions: ["CLAUDE.md"]` | `conventions: [{name, source, path\|skill}]` | `source: "project"` 항목의 `path` 만 모아 배열로. `source: "plugin"` 항목은 무시하고 `/fe-harness:default-conventions` 를 쓴다 |

`.hyeondong-config.json` 에만 있는 키는 무시한다.

### 쓰기 규칙

- **레거시 파일에 쓰지 않는다.** `.hyeondong-config.json` 은 읽기 전용으로 취급한다.
- 설정 갱신이 필요한 스킬(`convention-check` 의 `projectConventions` 업데이트 등)은 레거시 profile을 쓰는 중이면 갱신을 건너뛰고 안내한다:
  > "`.hyeondong-config.json` 은 읽기 전용입니다. 설정을 갱신하려면 `/fe-harness:init` 으로 `.claude/fe-harness.local.md` 를 생성하세요 (기존 값이 기본값으로 채워집니다)."
- `/fe-harness:init` 은 `.hyeondong-config.json` 이 있으면 그 값을 기본값으로 제시해 마이그레이션을 돕는다. 원본은 삭제하지 않는다.

## Codex provider 설정 (`codexModels` 슬롯이 `openai` 외 provider를 쓸 때)

슬롯 = `review`(Plan 검증 리뷰) · `explore`(탐색·요약) · `judge`(읽기 전용 판정) · `write`(구현·수정). 레코드 = `{provider, model, effort?}` — 문법·기본값·병합·검증은 `skills/start-workflow/references/codex-mode.md` §1·§2.1.
provider 정의(URL·키)는 **이 profile이 아니라** Codex `~/.codex/config.toml`(`$CODEX_HOME` 우선)에 둔다. 키·URL·헤더를 profile에 적지 않는다.

```toml
[model_providers.<id>]          # <id> = profile의 provider 값과 대소문자까지 동일
name = "…"
base_url = "https://…"          # OpenAI Responses API 호환 엔드포인트
env_key = "<ENV_VAR>"           # 키는 환경변수로만 (experimental_bearer_token 비권장)
wire_api = "responses"          # Codex는 responses만 지원
```

- 모델 메타데이터(컨텍스트 창·reasoning summary)는 Codex `model_catalog_json` 또는 root 키(`model_context_window`·`model_supports_reasoning_summaries`)로 설정한다. "Model metadata for X not found" 경고는 정상 동작이다. 프로젝트 `.codex/config.toml`에는 provider auth를 둘 수 없다.
- 예시 (비규범 — 벤더 문서 우선, 2026-08 확인): Z.ai GLM = `base_url = "https://api.z.ai/api/v1"`, 모델 `glm-5.3`/`glm-5-turbo` (Z.ai 공식 Codex 문서). Kimi = Moonshot API 직결은 Responses 미제공 → Moonshot 공식 Codex 가이드의 로컬 프록시, 또는 OpenRouter(`moonshotai/kimi-k2.7`, `env_key = "OPENROUTER_API_KEY"`).
- doctor가 provider 테이블·인증·`wire_api`를 점검한다 — WARN 코드 `NO_TABLE`·`ENV_UNSET`·`BEARER_TOKEN`·`WIRE_API`·`PROJECT_ONLY`·`INVALID_SLOT` (값은 출력하지 않음, 비차단 — 실행 시 해당 provider·슬롯만 Claude 폴백).

## 명령 실행 규칙

- 하드코딩된 명령 대신 profile의 `{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{e2eCommand}` 를 사용.
- 명령이 비어있으면 해당 단계를 `SKIPPED`로 표기하고 다음 단계로 진행 (실패 아님).
- `e2eRunner: none` 이거나 `e2eCommand` 가 비어있으면 모든 E2E 단계 SKIP.

## profile 생성

`/fe-harness:init` 실행 → 자동 감지 + 사용자 확인 → 파일 생성.
