# mimo-s-harness

개발 워크플로우 자동화를 위한 Claude Code / Codex CLI / OpenCode 하네스 모음.

Technical Spec 작성, Plan 리뷰, 구현, 품질 루프, 커밋/PR까지 반복되는 개발 절차를 플러그인과 스킬로 묶어 제공한다.

## 설치

### Claude Code

```bash
# 마켓플레이스 등록
/plugin marketplace add kangmomin/mimo-s-harness

# 범용 백엔드 하네스
/plugin install be-harness@harness-plugins

# 범용 프론트엔드 하네스
/plugin install fe-harness@harness-plugins

# 풀스택 오케스트레이터
/plugin install fs-harness@harness-plugins
```

프로젝트 특화 하네스가 필요하면 아래 플러그인을 설치한다.

```bash
/plugin install minmos-harness@harness-plugins
/plugin install hyeondongs-harness@harness-plugins
```

Claude Code marketplace 정의는 `.claude-plugin/marketplace.json` 에 있다.

### Codex CLI

이 repo를 연 상태에서 `/plugins` 를 열면 Codex용 `minmos-harness`, `hyeondongs-harness` 가 노출된다.

repo-local marketplace 정의는 `.agents/plugins/marketplace.json`, 실제 Codex plugin root는 `plugins/` 아래에 있다.
수동 설치 방식은 `codex/README.md` 를 참고한다.

### OpenCode

OpenCode용 출력물은 `.opencode/` 아래에 repo-local adapter 형태로 들어 있다.

```text
.opencode/
├── skills/<plugin>__<skill>/SKILL.md
├── commands/<plugin>__<skill>.md
└── plugins/<plugin>/
```

OpenCode에서 slash command로 호출할 때는 `<plugin>__<skill>` 형식을 사용한다.

```text
/minmos-harness__commit-mm
/minmos-harness__start-workflow-mm
/be-harness__start-workflow
/fe-harness__component
```

원본 기능은 각 하네스의 `skills/*/SKILL.md`가 source of truth이고, `.opencode/` 아래 파일은 `plugin-manager-mcp`가 생성하는 adapter다.

### Plugin Manager MCP

`plugin-manager-mcp`는 Claude Code, Codex, OpenCode용 repo-local plugin adapter를 marketplace allowlist 기반으로 동기화한다.

```bash
npm install -g plugin-manager-mcp
HARNESS_PLUGINS_ROOT=/path/to/mimo-s-harness plugin-manager-mcp --health
```

MCP client에는 stdio server로 등록한다.

```json
{
  "mcpServers": {
    "plugin-manager": {
      "command": "plugin-manager-mcp",
      "env": {
        "HARNESS_PLUGINS_ROOT": "/path/to/mimo-s-harness"
      }
    }
  }
}
```

주요 tool:

- `list_plugins`
- `show_status`
- `sync_to_claude`
- `sync_to_codex`
- `sync_to_opencode`

## 플러그인 목록

| 플러그인 | 대상 | 설명 |
|---------|------|------|
| **be-harness** | 범용 백엔드 | Go/Node 프리셋과 project profile 기반의 Spec→Plan→구현→품질 루프→PR 워크플로우 |
| **fe-harness** | 범용 프론트엔드 | React/Next.js 중심의 컴포넌트 생성, lint/a11y, 단위/E2E 테스트, PR 워크플로우 |
| **fs-harness** | 풀스택 | BE/FE 하네스를 병렬로 사용해 계약 정의, 교차 리뷰, 통합 검증, 단일 PR까지 오케스트레이션 |
| **minmos-harness** | Post-Math 백엔드 | 커밋/PR, 컨벤션 검사, E2E 테스트(REST+gRPC), Apidog 스키마 생성 |
| **hyeondongs-harness** | React 프론트엔드 | 컴포넌트 생성, 커밋/PR, 단위/E2E 테스트, 코드 품질 검사(ESLint, a11y) |

## 빠른 시작

### 백엔드 프로젝트

```bash
/be-harness:init
/be-harness:start-workflow
```

### 프론트엔드 프로젝트

```bash
/fe-harness:init
/fe-harness:start-workflow
```

### 풀스택 프로젝트

```bash
/be-harness:init
/fe-harness:init
/fs-harness:start-workflow
```

`fs-harness` 는 `be-harness` 와 `fe-harness` 가 모두 설치되어 있어야 한다.

## 디렉터리 구조

```text
.
├── be-harness/             # 범용 백엔드 Claude Code 플러그인
├── fe-harness/             # 범용 프론트엔드 Claude Code 플러그인
├── fs-harness/             # 풀스택 Claude Code 오케스트레이터
├── minmos-harness/         # Post-Math 백엔드 Claude Code 플러그인
├── hyeondongs-harness/     # 프로젝트 특화 프론트엔드 Claude Code 플러그인
├── codex/                  # Codex CLI 수동 설치용 스킬/에이전트
├── mcp/plugin-manager/     # plugin-manager-mcp TypeScript MCP 서버
├── plugins/                # Codex CLI repo-local 플러그인
├── .opencode/              # OpenCode repo-local skills/commands/plugin adapters
├── .claude-plugin/         # Claude Code marketplace 정의
└── .agents/plugins/        # Codex CLI repo-local marketplace 정의
```

## 참고 문서

- `be-harness/README.md`: 범용 백엔드 하네스
- `fe-harness/README.md`: 범용 프론트엔드 하네스
- `fs-harness/README.md`: 풀스택 오케스트레이터
- `minmos-harness/README.md`: Post-Math 백엔드 하네스
- `hyeondongs-harness/README.md`: 프로젝트 특화 프론트엔드 하네스
- `codex/README.md`: Codex CLI용 수동 설치 및 호출 방식
- `mcp/plugin-manager/README.md`: MCP 기반 plugin 동기화 서버
