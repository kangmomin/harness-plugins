---
name: search
description: "work-log 문서를 검색해 관련 문서를 찾고 인용한다. '이전에 이거 정리한 문서 있나?', 'work-log 에서 찾아줘', '그 회의록 어디 있지?', 지난 작업 기록을 참조해야 할 때 사용. 후보 랭킹 → 본문 1개만 읽기의 2단 절차로 토큰을 아낀다."
allowed-tools: Bash, Read, Grep, Glob
---

# work-log 검색

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:search`, Codex에서는 `$work-log:search` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 접두사에 의존하지 말고 `wiki_` 로 시작하는
기본 이름을 기준으로 찾는다.

## 핵심 원칙 — 2단 조회를 반드시 지킨다

work-log 에는 수백 개 문서가 있다. 전부 읽으면 컨텍스트가 터진다.

```
① wiki_resolve  → 본문 없이 후보 랭킹 (토큰 거의 0)
② 후보 검토      → 사용자에게 제시하거나 스스로 1개 선택
③ wiki_read     → 선택한 문서 하나만 본문 조회
```

**`wiki_read` 를 여러 문서에 연속 호출하지 않는다.** 정말 여러 문서가 필요하면
각각 `section`·`token_budget` 으로 범위를 좁혀 읽는다.

## Step 0: 실제 root 확인

MCP의 cwd가 아닌 실제 프로젝트 절대경로를 확인한다. 그 디렉토리에서
`node "<plugin-root>/mcp/lib/config.js"` 로 해석한 `cfg.root` 와 `wiki_status.root` 가
canonical realpath 기준으로 일치해야 검색·읽기를 진행한다. env가 다른 프로젝트로 고정되어 있지 않은지 실제 checkout의
`.work-log.json` root와도 비교한다. 불일치하면 env 우선순위·MCP cwd(플러그인 경로일 수 있음)를
doctor로 진단하고, 최종 프로젝트 root의 `WORK_LOG_ROOT` fallback 및 재시작 후 확인을 안내한다.
사용자가 기존 flat root로의 전환을 명시적으로 승인했다면 그 root를 `WORK_LOG_ROOT` 로 CLI에도
동일하게 전달하고, `cfg.root`·`wiki_status.root`·승인한 root의 일치를 확인한다. 이 경우에만 기존
checkout 설정과의 차이를 허용하며, 승인 없는 env 불일치는 검색을 중단한다.
`scope: global` 표시만으로 실패로 보지 않는다. 독립 프로젝트 모드의 미등록 checkout/worktree는
init을 안내한다. 분류형 전역 모드는 공유 root 안에서 분류 필터를 사용한다.

검색 결과가 비어도 상위 중앙 vault나 다른 프로젝트·옛 flat 이력으로 자동 확장하지 않는다.
기존 이력은 자동 이동되지 않으므로 필요하면 명시적으로 기존 flat root를 선택한다.

## Step 1: 후보 검색

노출된 MCP 툴 중 기본 이름이 `wiki_resolve` 인 툴을 호출한다.


| 인자 | 용도 |
|------|------|
| `query` | 검색어. 공백으로 여러 단어 (모두 만족하는 문서에 가산점) |
| `type` | 문서 종류 필터 — plan / report / design / note / spec / meeting / decision |
| `tags` | 태그 필터 (모두 만족) |
| `project` | 소유 프로젝트 정확한 키. 공유는 `_shared`, 미분류는 `_unclassified` |
| `category` | history / data / docs 정확 필터 |
| `limit` | 후보 수. 기본 5, 최대 20 |

사용자 입력에서 `--type`·`--tag`·`--project`·`--category` 플래그를 분리하고 나머지를 `query`로 쓴다.
분류 필터 생략은 현재 root의 전체 검색이다. 구조화된 전역 vault는 root를 유지한 채
`projects/<project>/<category>/...`, `_shared`, `_unclassified`를 함께 읽는다. 요청된 프로젝트가
있으면 해당 필터를 사용하되 공유 자료가 필요하면 `_shared`를 별도로 검색한다. 필터 결과가
없다는 이유로 다른 root나 다른 프로젝트로 조용히 전환하지 않는다.
후보·읽기 응답의 project/category는 경로에서 파생되며 원래 frontmatter는 별개로 보존된다.
raw JSON·SQL·CSV·첨부가 필요하면 확인한 vault 내부의 실제 경로를 파일 읽기 도구로 읽고 실행하지 않는다.
0.3.1 서버에는 새 필터가 없으므로 doctor에서 버전·재시작을 확인하고 0.3.2 적용 후 같은 root를 sync한다.

**`emptyResult: true` 가 오면** 응답의 `hintTags` 에 vault 의 주요 태그가 실려 온다.
그 태그로 다시 검색하거나, 사용자에게 어떤 주제인지 되묻는다. 첫 빈 결과로 끝내지 말고, 다시 찾아도 없으면 시도한 검색어와 함께 없다고 보고한다.

## Step 2: 후보 제시

후보를 표로 보여준다. `score` 가 압도적인 1위가 있으면 바로 Step 3 으로 간다.

| # | 제목 | 종류 | 경로 | 점수 |
|---|------|------|------|------|

`companions` 에 html 이 있으면 "같은 내용의 html 리포트도 있음"을 함께 알린다.

## Step 3: 본문 조회

기본 이름이 `wiki_read` 인 MCP 툴로 **하나만** 읽는다.

- 문서가 길 것 같으면 `token_budget` 을 먼저 걸어라 (예: 2000). 잘리면 `truncated: true` 가 온다
- 특정 주제만 필요하면 `section` 에 헤딩 이름 일부를 넣어 그 섹션만 받는다
- `.html` 문서는 본문이 인덱싱되어 있지 않다 — 반환된 절대 경로를 Read 도구로 직접 열어라

## Step 4: 인용

답변에 근거를 밝힐 때 응답의 `citation` 값(`work-log:<경로>`)을 그대로 쓴다.

## MCP 미연결 시 폴백

MCP 미연결로 툴 호출이 실패하면 **조용히 포기하지 말고** 실제 프로젝트에서 해석한
`cfg.root` 안에서만 grep 으로 대체하되, 그 사실을 알린다. root 불일치 오류를 우회하거나
상위 중앙 vault로 넓히지 않는다. 아래 명령은 확인한 실제 프로젝트 디렉토리에서 실행한다:

```bash
ROOT=$(node "<plugin-root>/mcp/lib/config.js" | node -e 'const c=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(c.root||"")')
grep -ril --include='*.md' "<검색어>" "$ROOT" | head -20
```

`<plugin-root>` 는 이 `SKILL.md` 의 `../..` 설치 경로다. 클라이언트가 `PLUGIN_ROOT` 또는
`CLAUDE_PLUGIN_ROOT` 를 제공하면 그 값을 쓸 수 있다. 그리고 doctor 스킬로 원인을 진단한다.

## 인덱스가 없다는 오류가 오면

오류 문구는 `인덱스를 다시 생성해야 합니다 (<reason>)` 다. `INDEX_MISSING` 이면 `wiki_sync` 가 아직 실행되지 않은 것이고, `INDEX_VERSION`·`INDEX_SCHEMA`·`INDEX_ROOT`·`INDEX_INVALID` 이면 기존 인덱스가 현재 서버·vault 와 맞지 않는 것이다. 어느 경우든 sync 스킬을 먼저 실행하라고 안내한다.
