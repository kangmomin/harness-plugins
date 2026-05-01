---
name: be-harness__init
description: "be-harness 플러그인의 project profile(.claude/be-harness.local.md)을 대화형으로 생성/갱신한다. Go/Node 프리셋 지원."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/init.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# be-harness Init

프로젝트 profile(`.claude/be-harness.local.md`)을 생성/갱신한다.
모든 be-harness 스킬이 이 profile을 읽어 빌드/테스트/소스 경로를 결정한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다 (profile에서 변경 가능).

---

## Step 1: 현재 상태 스캔

아래 항목을 조용히 점검한다.

- `.claude/be-harness.local.md` 존재 여부
- 프로젝트 언어 자동 탐지
  - `go.mod` 존재 → `go`
  - `package.json` 존재 → `node`
  - 둘 다 없음 → `custom`
- `Makefile` 존재 여부 (`make test` 후보)
- `.git` 및 기본 브랜치 확인 (`git symbolic-ref refs/remotes/origin/HEAD` 또는 `git config init.defaultBranch`)

## Step 2: 상태 요약

```markdown
## be-harness 환경 스캔

| 항목 | 상태 |
|------|------|
| profile (.claude/be-harness.local.md) | 존재 / 없음 |
| 감지된 언어 | go / node / custom |
| 감지된 빌드 러너 | Makefile / npm scripts / go / 없음 |
| 기본 브랜치 | main / master / 미확인 |
```

## Step 3: 프리셋 선택

기존 profile이 없거나 사용자가 재생성을 원하면:

> "어떤 프리셋을 사용할까요?"
> 1. `go` — Go 프로젝트 (`go build ./...`, `go test ./...`)
> 2. `node` — Node 프로젝트 (`npm run build`, `npm test`)
> 3. `custom` — 모든 명령을 수동 입력

`AskUserQuestion`으로 수집한다. 감지 결과에 맞는 옵션을 기본으로 권장한다.

## Step 4: 값 확정

프리셋 기본값을 기준으로 사용자에게 빠르게 override 여부만 확인한다.
한꺼번에 여러 질문을 던지지 말고 **아래 네 그룹씩** 묻는다.

### Group A — 빌드/테스트

- `buildCommand`
- `testCommand`
- `lintCommand`
- `typeCheckCommand` (선택)
- `makeTestCommand` (Makefile 있으면 제안)

### Group B — 서버/E2E

- `runServerCommand` (선택, 없으면 빈 값)
- `serverUrl` (기본 http://localhost:8080 또는 :3000)
- `e2eEnabled` (기본 true)
- `apiDocsPath` (선택)

### Group C — 디렉토리/Git

- `sourceDirs`
- `testDirs`
- `mainBranch` (감지 결과를 기본값으로)
- `featureBranchPrefix`
- `hotfixBranchPrefix`

### Group D — 컨벤션

- `commitPrefixes` (기본: Add, Fix, Del, Refactor, Doc, Test, Chore, WIP)
- `commitCoAuthor` (선택, 비우면 Co-Authored-By 라인 생략)
- `projectConventions` (기본: `["CLAUDE.md"]`, 없으면 빈 배열)
- `language` (ko/en, 기본 ko)

> 각 그룹에서 값을 제시하고 "이대로 진행하시겠습니까? (변경할 항목 번호 또는 `ok`)" 식으로 확인한다.
> 그룹 단위 확정으로 진행한다.

## Step 5: Profile 생성

`.claude/be-harness.local.md` 를 아래 형식으로 Write한다.

```markdown
---
preset: {preset}
language: {language}

buildCommand: "{buildCommand}"
testCommand:  "{testCommand}"
lintCommand:  "{lintCommand}"
typeCheckCommand: "{typeCheckCommand}"
makeTestCommand: "{makeTestCommand}"

runServerCommand: "{runServerCommand}"
serverUrl: "{serverUrl}"
e2eEnabled: {e2eEnabled}
apiDocsPath: "{apiDocsPath}"

sourceDirs: {sourceDirs}
testDirs:   {testDirs}

mainBranch: {mainBranch}
featureBranchPrefix: {featureBranchPrefix}
hotfixBranchPrefix:  {hotfixBranchPrefix}

commitPrefixes: {commitPrefixes}
commitCoAuthor: "{commitCoAuthor}"

projectConventions: {projectConventions}
---

# Project Notes

(프로젝트별 메모는 아래에 자유롭게 작성)
```

## Step 6: convention-check 설정

- `.convention-check.json`이 없으면 생성 여부를 묻는다.
- 기본값:

  ```json
  {
    "conventions": [
      { "name": "default-conventions", "source": "plugin", "skill": "be-harness:default-conventions" },
      { "name": "project", "source": "project", "path": "CLAUDE.md" }
    ]
  }
  ```

- `CLAUDE.md`가 없으면 `project` 엔트리는 제외한다.

## Step 7: 프로젝트 오버라이드 디렉토리 생성

be-harness는 플러그인 원본을 수정하지 않고 프로젝트별로 스킬/에이전트 동작을 조정할 수 있는 **오버라이드 레이어**를 제공한다 (상세: 플러그인 루트 `OVERRIDES.md`).

디렉토리 구조만 미리 만들어둔다 (파일은 필요할 때 생성):

```bash
mkdir -p .claude/be-harness/skills .claude/be-harness/agents
```

그리고 안내용 README를 해당 디렉토리에 두되, 이미 존재하면 덮어쓰지 않는다:

```markdown
<!-- .claude/be-harness/README.md -->
# be-harness project overrides

이 디렉토리는 프로젝트별 be-harness 스킬/에이전트 오버라이드를 담는다.
상세 규약은 플러그인 루트 `OVERRIDES.md` 참조.

- `common.md` — 모든 스킬/에이전트에 공통 적용
- `skills/{skill-name}.md` — 특정 스킬 전용
- `agents/{agent-name}.md` — 특정 에이전트 전용

파일은 전부 선택. start-workflow Phase 9 의 보완점이 자동으로 이곳에 append 된다.
```

## Step 8: 최종 결과

```markdown
## Init 완료

| 항목 | 결과 |
|------|------|
| profile | 생성 / 갱신 / 건너뜀 |
| convention-check 설정 | 생성 / 건너뜀 / 이미 존재 |
| .claude/be-harness/ 오버라이드 디렉토리 | 생성 / 이미 존재 |

다음 단계:
- `/be-harness:doctor` — 상태 검증
- `/be-harness:start-workflow` — 워크플로우 시작
```

---

## 주의사항

- 기존 `.claude/be-harness.local.md`가 있으면 overwrite하지 않고, 변경된 필드만 Edit로 반영한다.
- `.claude/` 디렉토리가 없으면 먼저 생성한다.
- Git이 초기화되지 않은 프로젝트도 profile은 생성한다 (Git 관련 필드는 빈 값 허용).
