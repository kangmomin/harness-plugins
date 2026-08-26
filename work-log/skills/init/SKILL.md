---
name: init
description: "work-log 스코프를 설정한다. 전역 vault 또는 저장소별 work-log를 선택하고 최초 인덱싱까지 수행. 플러그인 최초 설정, '초기화해줘', doctor가 미설정을 보고할 때 사용."
allowed-tools: Bash, Read, Write, Edit, Glob, AskUserQuestion
---

# work-log Init

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:init`, Codex에서는 `$work-log:init` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 `wiki_` 로 시작하는 기본 이름을 기준으로 찾는다.

## Step 1: 현재 상태 확인

기본 이름이 `wiki_status` 인 MCP 툴을 먼저 호출한다. 툴이 아직 연결되지 않았다면
`node "<plugin-root>/mcp/lib/config.js"` 로 같은 상태를 확인한다. `<plugin-root>` 는 이
`SKILL.md` 의 `../..` 설치 경로이며, 클라이언트가 `PLUGIN_ROOT` 또는
`CLAUDE_PLUGIN_ROOT` 를 제공하면 그 값을 쓸 수 있다.

이미 설정되어 있으면(`needsInit` 이 없으면) 현재 스코프를 보여주고
**바꿀지 물어본다.** 사용자가 원치 않으면 여기서 끝낸다.

## Step 2: 스코프 선택

현재 클라이언트의 사용자 입력 도구로 묻는다:

| 선택지 | 의미 |
|--------|------|
| **전역 vault** | 모든 프로젝트가 하나의 work-log 를 공유한다. 이미 쌓인 문서가 있다면 이쪽 |
| **프로젝트별** | `<현재 저장소>/work-log/` 에 이 프로젝트 문서만 모은다. 코드와 함께 버전 관리된다 |

각 선택지에 실제 경로를 넣어 보여준다. 전역의 기본 후보는 기존 vault 경로
(현재 설정이 있으면 그 값, 없으면 `~/work-log`)이고, 프로젝트별은 git 루트 기준이다:

```bash
git rev-parse --show-toplevel 2>/dev/null || pwd
```

## Step 3: 루트 검증 (자동 거부 조건)

선택한 경로가 아래에 해당하면 **채택하지 않고 다시 묻는다**:

- 존재하지 않거나 디렉토리가 아님
- **플러그인 소스 디렉토리** — `.claude-plugin/`·`.codex-plugin/`·`mcp/server.js`·`skills/` 를 포함하는 경로.
  플러그인 저장소에서 프로젝트 스코프를 켜면 `<repo>/work-log/` 가 이 플러그인 코드 자신을
  가리키게 된다. `config.js` 가 이 경우를 거부한다

프로젝트별 모드에서 디렉토리가 없으면 만들어도 되는지 묻고 `mkdir -p` 한다.

## Step 4: 설정 파일 작성

| 스코프 | 위치 | 내용 |
|--------|------|------|
| 전역 | `$XDG_CONFIG_HOME/work-log/config.json` (기본 `~/.config/work-log/config.json`) | `{"scope":"global","root":"<절대경로>"}` |
| 프로젝트 | `<repo>/.work-log.json` | `{"scope":"project","root":"./work-log"}` |

전역은 `root` 에 **절대경로가 필수**다. 프로젝트는 설정 파일 위치 기준 상대경로를 쓴다.
기존 `~/.claude/work-log.json` 은 자동 이동하거나 삭제하지 않는다. 그 파일만 있으면 계속
fallback으로 읽고, 사용자가 설정 변경을 승인했을 때만 새 XDG 전역 파일을 만든 뒤 기존
파일이 후순위로 가려진다는 점을 보고한다.

## Step 5: 프로젝트 모드 — 커밋 여부 확인

`.work-log.json` 을 저장소에 커밋할지 묻는다:

- **커밋** — 팀원이 같은 설정을 공유한다 (팀 프로젝트 권장)
- **`.gitignore` 에 추가** — 개인 설정으로 둔다

인덱스는 vault 밖 XDG 캐시(기본 `~/.cache/work-log/`)에 저장되므로 저장소에 인덱스 파일이
생기지 않는다. `.gitignore` 에 인덱스를 넣을 필요는 없다.

문서(`work-log/*.md`) 자체를 커밋할지도 함께 확인한다 — 보통 커밋하는 것이 자연스럽다.

## Step 6: cwd 자동 탐지 확인

프로젝트 스코프는 MCP 서버가 프로젝트 디렉토리에서 실행될 때만 `.work-log.json` 을
자동으로 찾는다. `wiki_status` 를 호출해 `configSource` 를 확인한다:

| `configSource` | 판정 |
|---|---|
| 방금 만든 `.work-log.json` 경로 | 자동 탐지 **동작** — 그대로 두면 된다 |
| `null` 이거나 다른 경로 | 자동 탐지 **불가** → 현재 클라이언트용 fallback 적용 |

Claude Code에서 자동 탐지가 안 되면 프로젝트 루트 `.mcp.json` 에 다음을 추가하라고 안내한다
(이미 있으면 `env` 만 병합):

```json
{ "mcpServers": { "work-log": {
  "command": "node",
  "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.js"],
  "env": { "WORK_LOG_ROOT": "<vault 절대경로>" }
}}}
```

이 경우 변경 반영에 **Claude Code 재시작이 필요하다**고 알린다.

Codex의 번들 MCP는 플러그인 디렉토리에서 시작하므로 프로젝트 설정 자동 탐지가 안 될 수 있다.
이 경우 프로젝트 세션을 다음처럼 다시 시작한다. Codex manifest가 `WORK_LOG_ROOT` 를 번들 MCP로
전달한다.

```bash
WORK_LOG_ROOT="<vault 절대경로>" codex
```

항상 같은 vault를 쓴다면 프로젝트별 실행 환경보다 XDG 전역 설정을 권장한다.

## Step 7: 최초 인덱싱

기본 이름이 `wiki_sync` 인 MCP 툴을 호출한다.

`drift.firstRun` 이 true 이고 `added` 가 전체 문서 수와 같은 것이 정상이다.

결과를 요약해 보고한다:

```
## work-log 설정 완료

- 스코프: 전역 / 프로젝트
- vault: <경로>
- 인덱싱된 문서: 정본 N개 (html 단독 M개)

이제 search 스킬로 찾고, edit 스킬로 기록을 남길 수 있습니다.
```

## 주의

기존 vault 를 전역으로 설정해도 **기존 문서는 전혀 수정되지 않는다.**
인덱스는 vault 밖에 만들어지고, frontmatter 가 없는 문서는 제목·경로에서 메타를 추론해
인덱스에만 기록한다. 이 점을 사용자에게 명확히 알린다.
