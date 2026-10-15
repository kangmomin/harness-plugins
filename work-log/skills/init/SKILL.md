---
name: init
description: "work-log 스코프를 설정한다. projects/<project>/{history,data,docs} 분류형 전역 vault(권장), 독립 프로젝트 vault 또는 기존 flat·저장소 내 방식을 선택하고 최초 인덱싱까지 수행. 플러그인 최초 설정, '초기화해줘', doctor가 미설정을 보고할 때 사용."
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

MCP의 `cwd` 를 실제 프로젝트로 간주하지 않는다(플러그인 경로일 수 있다). 실제 프로젝트
절대경로를 확인하고, git이면 현재 checkout의 `git rev-parse --show-toplevel`, nonGit이면
사용자가 확인한 실제 디렉토리를 설정 위치로 쓴다. 그 위치에서 `config.js` 를 실행한
`cfg.root` 와 `wiki_status.root` 를 비교한다. 환경변수가 우선하며 `scope: global` 표시만으로
실패라고 판단하지 않는다. Git 명령으로 checkout을 확인할 때는 helper처럼 상속된 `GIT_*`
환경변수를 제거한다. `--project-dir` 에는 Git 환경변수가 가리키는 경로가 아닌 세션 cwd 또는
사용자가 확인한 실제 프로젝트 경로를 전달하고, 설정 위치는 helper의 `configDir` 로 확정한다.

이미 설정되어 있으면(`needsInit` 이 없으면) 현재 스코프·실제 root·설정 출처를 보여주고
**바꿀지 물어본다.** 사용자가 원치 않으면 여기서 끝내되, root 불일치를 완료로 보고하지 않는다.
전역 설정이 있다는 이유로 독립 프로젝트 root를 선택한 checkout의 최초 init을 생략하지 않는다.

## Step 2: 스코프 선택

현재 클라이언트의 사용자 입력 도구로 묻는다:

| 선택지 | 의미 |
|--------|------|
| **분류형 전역 vault (권장)** | 기존 vault root를 유지해 projects/<project>/{history,data,docs}, _shared, _unclassified를 함께 읽고 소유·분류별 작성 |
| **독립 중앙 프로젝트별** | 중앙 base의 `<projectKey>/`에 이 프로젝트 문서만 모은다. 현재 checkout마다 최초 init 필요 |
| **기존 전역 flat vault** | 모든 프로젝트가 기존 root를 공유한다. 기존 flat 관례를 그대로 사용 |
| **저장소 내 work-log** | 기존 `<현재 저장소>/work-log/` 방식. 코드와 함께 버전 관리할 때 선택 |

각 선택지에 실제 경로를 넣어 보여준다. 분류형 전역 모드는 기존 global root(예: `/workspace/work-log`)를
그대로 채택하며, `projects/` 또는 개별 프로젝트 폴더를 root로 쓰지 않는다. 신규 쓰기의 소유·분류는
edit 규칙으로 확인한다. `_shared`와 `_unclassified`도 같은 root에 둔다. 정리된 기존 폴더·Properties를
다시 만들거나 hash 폴더로 대체하지 않는다. 없던 프로젝트 키는 사용자 확인 없이 생성하지 않는다.

명시된 `AGENTS.md`·`CLAUDE.md` 저장 경로가 일반 기본값보다 우선한다. 아래 중앙 base/helper 절차는
**독립 중앙 프로젝트별을 선택한 경우에만** 적용한다. 기존 global root는
중앙 base 후보로 제시하고, 일반 기본 후보는 `<기존 vault>/projects` 다. base가 없으면
자동 생성하지 않고 경로·생성을 승인받는다. 전역 후보는 기존 vault(없으면 `~/work-log`)다.

중앙 프로젝트별 root는 직접 이름을 조합하지 말고 read-only helper로 계산한다:

```bash
node '<plugin-root>/mcp/lib/config.js' --project-vault '<existing central base>' --project-dir '<actual project absolute dir>'
```

JSON `{root,baseRoot,projectDir,projectKey,identity,configDir}` 을 확인한다. `baseRoot` 는
존재하는 canonical base이며 `root` 는 그 아래 단일 `projectKey` 폴더다. 아직 없는 root도
계산만 하며 helper는 생성하지 않는다. `projectKey` 는 common-dir identity에서 도출한 안전한
repo 이름 + `-` + common-dir realpath SHA256 앞 16자리다. 같은 저장소의 worktree는 같은 key,
다른 clone은 다른 key를 쓴다. nonGit identity는 사용자가 확인한 디렉토리의 realpath이며,
`.git` 이 있는데 Git 조회가 실패하면 nonGit으로 대체하지 않고 오류로 처리한다.
`configDir` 는 현재 checkout의 git show-toplevel이고 nonGit은 확인한 실제 디렉토리다.
base 자체의 symlink는 canonical 경로로 허용하지만 기존 root의 symlink는 거부한다.
예를 들어 `/workspace/work-log/claude/projects/<projectKey>` 를 root로 쓰려면 먼저 base인
`/workspace/work-log/claude/projects` 의 생성을 승인받고 존재하는 상태에서 helper를 호출한다.
모든 미등록 repo를 자동 분류하는 기능이 아니다.

## Step 3: 루트 검증 (자동 거부 조건)

선택한 경로가 아래에 해당하면 **채택하지 않고 다시 묻는다**:

- 존재하지 않거나 디렉토리가 아님. 아직 없는 중앙 root·저장소 내 root만 아래 승인 생성 절차로 처리한다
- 중앙 프로젝트별 모드에서 기존 root가 symlink임 — 명시적인 vault 재연결은 기존 flat 방식으로 선택한다
- **플러그인 소스 디렉토리** — `.claude-plugin/`·`.codex-plugin/`·`mcp/server.js` 중 하나를 포함하거나, `skills/` 와 `.mcp.json` 을 함께 포함하는 경로.
  플러그인 저장소에서 프로젝트 스코프의 저장소 내 방식을 켜면 `<repo>/work-log/` 가 이 플러그인 코드 자신을
  가리키게 된다. `config.js` 가 이 경우를 거부한다

중앙 모드는 helper가 계산한 root를 보여주고 **사용자 승인 → `mkdir -p` → 같은 인자의
helper 재호출 → root·baseRoot·configDir 일치 및 위 플러그인 소스 검사** 순서로 검증한다.
base 생성도 별도 승인이 선행되어야 한다. 저장소 내 모드도 없는 디렉토리 생성은 승인받고,
생성 뒤 실제 경로와 플러그인 소스 여부를 다시 검사한다. 실패하면 설정을 쓰지 않는다.

## Step 4: 설정 파일 작성

| 스코프 | 위치 | 내용 |
|--------|------|------|
| 분류형 전역 / 기존 flat | `$XDG_CONFIG_HOME/work-log/config.json` (기본 `~/.config/work-log/config.json`) | `{"scope":"global","root":"<vault 전체 절대경로>"}` |
| 중앙 프로젝트별 | `<configDir>/.work-log.json` | `{"scope":"project","root":"<helper root 절대경로>"}` |
| 저장소 내 프로젝트 | `<현재 checkout>/.work-log.json` | `{"scope":"project","root":"./work-log"}` |

전역·중앙 프로젝트별은 `root` 에 **절대경로가 필수**다. 저장소 내 모드만 설정 파일 위치
기준 상대경로를 쓴다. 중앙 모드는 현재 checkout의 `configDir` 에만 쓰고 global 설정은
그대로 둔다. worktree마다 최초 init으로 각 checkout에 설정을 만든다.
기존 `~/.claude/work-log.json` 은 자동 이동하거나 삭제하지 않는다. 그 파일만 있으면 계속
fallback으로 읽고, 사용자가 설정 변경을 승인했을 때만 새 XDG 전역 파일을 만든 뒤 기존
파일이 후순위로 가려진다는 점을 보고한다.
기존 프로젝트 설정이 있으면 XDG 전역 설정만 바꿔도 프로젝트 root가 우선한다. 기존 flat root로
전환을 승인받은 경우에는 프로젝트 설정을 자동 삭제하지 않고, 승인한 flat root를 `WORK_LOG_ROOT`
로 명시하는 fallback을 사용한다. 프로젝트 설정 자체를 변경하려면 별도 승인을 받는다.

## Step 5: 프로젝트 모드 — 커밋 여부 확인

중앙 absolute `.work-log.json` 은 **개인 설정 유지**를 권장한다. `.gitignore` 변경이나
커밋은 설정 승인과 별개로 물어보고, 각각 명시적으로 승인받은 경우만 수행한다:

- **커밋** — 저장소 내 상대경로 설정을 팀과 공유할 때 선택
- **`.gitignore` 에 추가** — 개인 설정으로 둘 때 별도 승인

인덱스는 vault 밖 XDG 캐시(기본 `~/.cache/work-log/`)에 저장되므로 저장소에 인덱스 파일이
생기지 않는다. `.gitignore` 에 인덱스를 넣을 필요는 없다.

저장소 내 모드는 문서(`work-log/*.md`) 자체를 커밋할지도 별도로 확인한다.
중앙 문서는 저장소 밖에 두며 기존 flat 이력은 자동 이동하지 않는다. 새 프로젝트 root에서는
옛 flat 이력이 검색되지 않는다. 필요하면 사용자가 명시적으로 기존 flat root를 선택한다.

## Step 6: cwd 자동 탐지 확인

프로젝트 스코프는 MCP 서버가 프로젝트 디렉토리에서 실행될 때만 `.work-log.json` 을
자동으로 찾는다. `wiki_status` 를 호출해 실제 프로젝트에서 해석한 `cfg.root` 및 승인한
최종 root와 `root` 가 canonical realpath 기준으로 일치하는지 먼저 확인한다. 기존 flat root로의
명시적인 전환에서는 승인한 `WORK_LOG_ROOT` 를 CLI에도 동일하게 전달해 `cfg.root` 를 확인한다.
이 경우에만 남아 있는 프로젝트 설정과의 차이를 허용하며, 승인 없는 env 불일치는 허용하지 않는다.
**일치하기 전 sync·완료 선언 금지**다.
`configSource` 는 보조 근거다(환경변수 fallback은 `scope: global` 로 보일 수 있다):

| `configSource` | 판정 |
|---|---|
| 방금 만든 `.work-log.json` 경로이고 실제 root 일치 | 자동 탐지 **동작** |
| 환경변수이고 실제 root 일치 | fallback **동작** (global 표시도 허용) |
| 실제 root 불일치 / 미설정 | env 우선순위·cwd 확인 → 현재 클라이언트용 fallback 안내 |

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

fallback의 `WORK_LOG_ROOT` 는 중앙 base가 아니라 **최종 프로젝트 root**다. 이미 설정된 env가
다른 root를 가리키면 프로젝트 config보다 우선하므로 수정/해제를 승인받아 안내한다.
한 프로젝트 root로 고정한 env는 다른 프로젝트로 전환할 때 바꾸고 MCP/클라이언트를 재시작한다.
재시작 뒤 `wiki_status.root` 일치 확인까지 **미완료**로 보고한다. 항상 같은 flat vault를
공유하려는 경우에만 XDG 전역 설정을 권장한다.

## Step 7: 최초 인덱싱

`wiki_status.server`이 **0.3.2**이고 승인한 root와 일치하는지 확인한다. 같은 vault를
사용하는 구서버를 종료하고 새 소스로 재시작하기 전에는 sync하거나 설정 완료를 보고하지 않는다.
재시작 뒤 버전·root를 다시 확인한 후 기본 이름이 `wiki_sync` 인 MCP 툴을 호출한다.

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
