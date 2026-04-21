# be-harness Project Profile

모든 be-harness 스킬은 프로젝트 루트의 **`.claude/be-harness.local.md`** 를 읽어 빌드/테스트/소스 경로 등을 결정한다.
이 파일이 없으면 기본값으로 동작한다 (언어 자동 탐지 후 Go/Node 프리셋 fallback).

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

## 명령 실행 규칙

- 모든 스킬/에이전트는 하드코딩된 명령 대신 **profile의 `{buildCommand}`, `{testCommand}`** 등을 사용한다.
- profile에 해당 명령이 없거나 비어있으면 해당 단계를 `SKIPPED`로 표기하고 넘어간다 (실패로 보지 않는다).
- 예: `typeCheckCommand`가 비어있으면 타입 체크 단계를 스킵.

## profile 생성

`/be-harness:init` 을 실행하여 대화형으로 생성한다. 기존 파일이 있으면 diff를 보여준 뒤 업데이트.
