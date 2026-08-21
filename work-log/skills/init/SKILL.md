---
name: init
description: "work-log 스코프를 설정한다. 전역 vault 를 쓸지 프로젝트별(<repo>/work-log/)로 쓸지 선택하고 최초 인덱싱까지 수행. 플러그인 최초 설정, '초기화해줘', doctor 가 미설정을 보고할 때 사용."
allowed-tools: Bash, Read, Write, Edit, Glob, AskUserQuestion
user-invocable: true
---

# work-log Init

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## Step 1: 현재 상태 확인

```bash
node ${CLAUDE_PLUGIN_ROOT}/mcp/lib/config.js
```

이미 설정되어 있으면(`needsInit` 이 없으면) 현재 스코프를 보여주고
**바꿀지 물어본다.** 사용자가 원치 않으면 여기서 끝낸다.

## Step 2: 스코프 선택

AskUserQuestion 으로 묻는다:

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
- **플러그인 소스 디렉토리** — `.claude-plugin/`·`mcp/server.js`·`skills/` 를 포함하는 경로.
  플러그인 저장소에서 프로젝트 스코프를 켜면 `<repo>/work-log/` 가 이 플러그인 코드 자신을
  가리키게 된다. `config.js` 가 이 경우를 거부한다

프로젝트별 모드에서 디렉토리가 없으면 만들어도 되는지 묻고 `mkdir -p` 한다.

## Step 4: 설정 파일 작성

| 스코프 | 위치 | 내용 |
|--------|------|------|
| 전역 | `~/.claude/work-log.json` | `{"scope":"global","root":"<절대경로>"}` |
| 프로젝트 | `<repo>/.work-log.json` | `{"scope":"project","root":"./work-log"}` |

전역은 `root` 에 **절대경로가 필수**다. 프로젝트는 설정 파일 위치 기준 상대경로를 쓴다.

## Step 5: 프로젝트 모드 — 커밋 여부 확인

`.work-log.json` 을 저장소에 커밋할지 묻는다:

- **커밋** — 팀원이 같은 설정을 공유한다 (팀 프로젝트 권장)
- **`.gitignore` 에 추가** — 개인 설정으로 둔다

인덱스는 vault 밖 캐시(`~/.cache/work-log/`)에 저장되므로 저장소에 인덱스 파일이
생기지 않는다. `.gitignore` 에 인덱스를 넣을 필요는 없다.

문서(`work-log/*.md`) 자체를 커밋할지도 함께 확인한다 — 보통 커밋하는 것이 자연스럽다.

## Step 6: cwd 자동 탐지 확인

프로젝트 스코프는 MCP 서버가 프로젝트 디렉토리에서 실행될 때만 `.work-log.json` 을
자동으로 찾는다. `wiki_status` 를 호출해 `configSource` 를 확인한다:

| `configSource` | 판정 |
|---|---|
| 방금 만든 `.work-log.json` 경로 | 자동 탐지 **동작** — 그대로 두면 된다 |
| `null` 이거나 다른 경로 | 자동 탐지 **불가** → 프로젝트 `.mcp.json` 에 절대경로를 명시해야 한다 |

자동 탐지가 안 되면 프로젝트 루트 `.mcp.json` 에 다음을 추가하라고 안내한다
(이미 있으면 `env` 만 병합):

```json
{ "mcpServers": { "work-log": {
  "command": "node",
  "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.js"],
  "env": { "WORK_LOG_ROOT": "<vault 절대경로>" }
}}}
```

이 경우 변경 반영에 **Claude Code 재시작이 필요하다**고 알린다.

## Step 7: 최초 인덱싱

`mcp__plugin_work-log_work-log__wiki_sync` 를 호출한다.

> **툴 이름 주의**: 접두사 `mcp__plugin_work-log_work-log__` 는 `/mcp` 목록 기준이다.
> 목록에 다르게 보이면 **`wiki_` 로 시작하는 이름의 툴**을 찾아 그것을 호출한다.
> 접두사가 달라도 스킬 절차는 동일하다.

`drift.firstRun` 이 true 이고 `added` 가 전체 문서 수와 같은 것이 정상이다.

결과를 요약해 보고한다:

```
## work-log 설정 완료

- 스코프: 전역 / 프로젝트
- vault: <경로>
- 인덱싱된 문서: 정본 N개 (html 단독 M개)

이제 `/work-log:search <검색어>` 로 찾고, `/work-log:edit` 로 기록을 남길 수 있습니다.
```

## 주의

기존 vault 를 전역으로 설정해도 **기존 문서는 전혀 수정되지 않는다.**
인덱스는 vault 밖에 만들어지고, frontmatter 가 없는 문서는 제목·경로에서 메타를 추론해
인덱스에만 기록한다. 이 점을 사용자에게 명확히 알린다.
