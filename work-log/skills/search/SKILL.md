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

## Step 1: 후보 검색

노출된 MCP 툴 중 기본 이름이 `wiki_resolve` 인 툴을 호출한다.


| 인자 | 용도 |
|------|------|
| `query` | 검색어. 공백으로 여러 단어 (모두 만족하는 문서에 가산점) |
| `type` | 문서 종류 필터 — plan / report / design / note / spec / meeting / decision |
| `tags` | 태그 필터 (모두 만족) |
| `limit` | 후보 수. 기본 5, 최대 20 |

사용자 입력에서 `--type`·`--tag` 플래그를 분리하고 나머지를 `query` 로 쓴다.

**`emptyResult: true` 가 오면** 응답의 `hintTags` 에 vault 의 주요 태그가 실려 온다.
그 태그로 다시 검색하거나, 사용자에게 어떤 주제인지 되묻는다. 절대 "없습니다"로 끝내지 않는다.

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

MCP 툴 호출이 실패하면 **조용히 포기하지 말고** grep 으로 대체하되, 그 사실을 알린다:

```bash
ROOT=$(node "<plugin-root>/mcp/lib/config.js" | node -e 'const c=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(c.root||"")')
grep -ril --include='*.md' "<검색어>" "$ROOT" | head -20
```

`<plugin-root>` 는 이 `SKILL.md` 의 `../..` 설치 경로다. 클라이언트가 `PLUGIN_ROOT` 또는
`CLAUDE_PLUGIN_ROOT` 를 제공하면 그 값을 쓸 수 있다. 그리고 doctor 스킬로 원인을 진단한다.

## 인덱스가 없다는 오류가 오면

`wiki_sync` 가 한 번도 실행되지 않은 상태다. sync 스킬을 먼저 실행하라고 안내한다.
