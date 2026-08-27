# be-harness Project Profile

모든 be-harness 스킬은 프로젝트 루트의 **`.claude/be-harness.local.md`** 를 읽어 빌드/테스트/소스 경로 등을 결정한다.
이 파일이 없으면 기본값으로 동작한다 (언어 자동 탐지 후 Go/Node 프리셋 fallback).

> profile 은 **값(settings)** 을 담는다. 스킬/에이전트 **동작**을 프로젝트별로 조정하려면 별도의 **Project Overrides** 레이어를 쓴다 → `OVERRIDES.md` 참조.

## 파일 위치

```
<repo-root>/.claude/be-harness.local.md
```

## 포맷

YAML frontmatter + 선택적 마크다운 본문.

```markdown
---
preset: go            # go | node | custom
language: ko          # ko | en (유저 대화 언어)
codexMode: mix        # none | mix | max — start-workflow의 Codex 사용 모드 (none: Codex 미사용·Claude 패널 리뷰 / mix: Plan 리뷰만 Codex / max: 탐색·판정·구현 서브에이전트까지 Codex 위임). `--codex` 또는 첫 실행 질문으로 저장
# codexModels:         # 선택 — Codex 위임 모델 슬롯(review | explore | judge | write). 생략 슬롯 = OpenAI 기본값(codex-mode.md 기본값 표). `--codex-models` 또는 init으로 저장
#   review: { provider: zai, model: glm-5.3, effort: high }     # provider = openai | ~/.codex/config.toml [model_providers.<id>]의 id — 아래 "Codex provider 설정"
#   write:  { provider: openrouter, model: moonshotai/kimi-k2.7 }

# 빌드/검증 명령 (preset 기본값을 override 하고 싶을 때만 작성)
buildCommand: "go build ./..."
testCommand:  "go test ./..."
lintCommand:  "go vet ./..."
typeCheckCommand: ""       # 해당 없으면 빈 문자열
makeTestCommand: ""        # Makefile 기반 테스트 러너가 있으면 지정

# 서버/E2E
runServerCommand: ""       # 로컬 서버 기동 커맨드 (백그라운드 실행용). 없으면 생략.
serverUrl: "http://localhost:8080"
e2eEnabled: true           # false면 e2e-test, e2e-test-loop 스킵
apiDocsPath: ""            # OpenAPI/Swagger 스펙 파일 경로. 없으면 생략.
e2eLockDir: ""             # E2E 실행 락 디렉토리. 비우면 자동 해석
                           # (work-log vault의 .wiki/e2e-locks → 없으면 /tmp/harness-e2e-locks).
                           # 환경변수 HARNESS_E2E_LOCK_DIR 로도 지정 가능.

# 리포트 출력
reportDir: ""              # E2E 자기 점검·Workflow Report(md) 저장 디렉토리. 비우면 `.claude/harness-reports`. work-log vault 하위 경로를 지정하면 wiki 인덱싱 대상이 된다

# 소스 레이아웃
sourceDirs: ["internal/", "cmd/", "pkg/"]
testDirs:   ["internal/", "pkg/"]

# Git
mainBranch: main
featureBranchPrefix: feat/
hotfixBranchPrefix:  hotfix/

# 커밋 컨벤션
commitPrefixes: [Add, Fix, Del, Refactor, Doc, Test, Chore, WIP]
commitCoAuthor: ""         # 비우면 Co-Authored-By 라인 생략

# 프로젝트 컨벤션 참조 (convention-check 및 default-conventions에서 사용)
projectConventions:
  - "CLAUDE.md"            # 프로젝트 루트 기준 경로
---

# Project Notes

(선택) 프로젝트별 메모. 모든 스킬이 참고.
```

## 프리셋 기본값

### `preset: go`

```yaml
buildCommand: "go build ./..."
testCommand:  "go test ./..."
lintCommand:  "go vet ./..."
typeCheckCommand: ""
makeTestCommand: ""
runServerCommand: ""
serverUrl: "http://localhost:8080"
sourceDirs: ["internal/", "cmd/", "pkg/"]
testDirs:   ["internal/", "pkg/"]
```

### `preset: node`

```yaml
buildCommand: "npm run build"
testCommand:  "npm test"
lintCommand:  "npm run lint"
typeCheckCommand: "npm run typecheck"
makeTestCommand: ""
runServerCommand: "npm run dev"
serverUrl: "http://localhost:3000"
sourceDirs: ["src/"]
testDirs:   ["src/", "tests/", "__tests__/"]
```

### `preset: custom`

모든 필드를 직접 지정해야 한다. 누락 시 경고.

## 읽기 우선순위

모든 스킬은 아래 순서로 값을 결정한다:

1. `.claude/be-harness.local.md` 의 YAML 값
2. 해당 preset의 기본값
3. 언어 자동 탐지 (`go.mod` → go, `package.json` → node)
4. 사용자에게 `init` 실행 안내

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

- 모든 스킬/에이전트는 하드코딩된 명령 대신 **profile의 `{buildCommand}`, `{testCommand}`** 등을 사용한다.
- profile에 해당 명령이 없거나 비어있으면 해당 단계를 `SKIPPED`로 표기하고 넘어간다 (실패로 보지 않는다).
- 예: `typeCheckCommand`가 비어있으면 타입 체크 단계를 스킵.

## profile 생성

`/be-harness:init` 을 실행하여 대화형으로 생성한다. 기존 파일이 있으면 diff를 보여준 뒤 업데이트.
