# work-log

작업 기록 폴더를 **LLM 이 읽을 수 있는 wiki** 로 관리하는 플러그인.

문서가 쌓일수록 "이전에 이 주제를 다룬 문서가 있었나"를 답하기 어려워진다. grep 은
파일명과 문자열만 볼 뿐 제목·종류·태그·문서 간 관계를 모른다. 이 플러그인은 vault 를
스캔해 인덱스를 만들고, MCP 서버가 그 위에서 **본문 없는 랭킹 → 본문 1개 읽기** 2단
조회를 제공한다. 수백 개 문서를 컨텍스트에 붓지 않고 필요한 하나만 읽는다.

## 지원 클라이언트와 구조

- Claude Code: `.claude-plugin/plugin.json` + `.mcp.json`
- 로컬 Codex 클라이언트(CLI·IDE·desktop): `.codex-plugin/plugin.json` + 번들 stdio MCP

`work-log` 가 스킬·설정 해석·MCP 서버를 직접 소유한다. `codex-be-harness` 는 이 코드를
복사하거나 필수 의존하지 않는다. 필요하면 상위 워크플로우에서 공개된 `wiki_*` 툴을 선택적으로
호출한다.

설치 후에는 현재 클라이언트를 재시작한다. 런타임 의존성은 없고 Node 18 이상이면 동작한다.
로컬 stdio 서버를 사용하므로 ChatGPT web용 공개 remote plugin 지원을 의미하지 않는다.

| 작업 | Claude Code | Codex |
|------|-------------|-------|
| 최초 설정 | `/work-log:init` | `$work-log:init` |
| 검색 | `/work-log:search <검색어>` | `$work-log:search <검색어>` |

## 스코프

| 모드 | vault 위치 | 설정 파일 |
|------|-----------|----------|
| **전역** | 지정한 절대경로 (예: `~/work-log`) | `$XDG_CONFIG_HOME/work-log/config.json` (기본 `~/.config/work-log/config.json`) |
| **프로젝트** | `<repo>/work-log/` | `<repo>/.work-log.json` |

해석 우선순위 (매 호출마다 재해석 — `init` 후 재시작이 필요 없다):

1. `WORK_LOG_ROOT` 환경변수 (절대경로일 때만)
2. cwd 에서 위로 `.work-log.json` 탐색 (`.git` 경계까지)
3. `$XDG_CONFIG_HOME/work-log/config.json` (상대경로면 무시하고 `~/.config` 사용)
4. `~/.claude/work-log.json` (기존 설치 호환 fallback)
5. 없으면 `needsInit`

잘못된 설정은 조용히 무시되지 않는다 — 깨진 JSON·없는 경로는 오류로 멈춘다(fail-closed).
신규 전역 설정은 XDG 경로에 쓰며 기존 Claude 설정은 자동 이동·삭제하지 않는다.

Codex 번들 MCP는 플러그인 디렉토리에서 시작한다. 따라서 프로젝트 `.work-log.json` 이 자동으로
발견되지 않으면 `WORK_LOG_ROOT="<vault 절대경로>" codex` 로 프로젝트 세션을 시작한다.
manifest가 이 환경변수와 XDG 설정·캐시 경로를 MCP 프로세스에 전달한다.

## 스킬

| 스킬 | Claude Code / Codex | 용도 |
|------|---------------------|------|
| search | `/work-log:search` / `$work-log:search` | 후보 랭킹 → 문서 하나만 읽기 |
| sync | `/work-log:sync` / `$work-log:sync` | 재스캔 + 인덱스 갱신 + drift 리포트 |
| edit | `/work-log:edit` / `$work-log:edit` | 문서 작성 · 수정 |
| init | `/work-log:init` / `$work-log:init` | 스코프 설정 |
| doctor | `/work-log:doctor` / `$work-log:doctor` | 연결 · 설정 · 인덱스 진단 |

## MCP 툴

| 툴 | 역할 |
|----|------|
| `wiki_resolve` | 본문 없이 후보 랭킹 (토큰 레버) |
| `wiki_read` | 문서 1개 본문. `section` · `token_budget` 지원 |
| `wiki_write` | 작성 · 수정 · 이어쓰기 + 인덱스 즉시 갱신 |
| `wiki_sync` | 전체 재스캔 + drift 리포트 |
| `wiki_status` | 스코프 · 인덱스 신선도 · 진단 정보 |

> **툴 이름 접두사**: Claude Code와 Codex가 서로 다른 접두사를 붙일 수 있다. 클라이언트의
> MCP 목록을 기준으로 `wiki_` 로 시작하는 기본 이름을 찾아 쓴다.

> **`wiki_write` 는 내부적으로 전체 sync 를 수행한다.** 엔트리 하나만 patch 하지 않는
> 이유는 새 문서의 링크가 다른 문서의 backlink·brokenLinks·orphans 를 바꾸기 때문이다
> — 그래프는 어차피 전역 재계산이 필요하다. 300개 규모에서 수백 ms 이며, 지연이 실제로
> 관측되면 그때 증분화한다.

## 안전 보장

- **sync 는 vault 에 0 바이트를 쓴다.** 인덱스는 `$XDG_CACHE_HOME/work-log/<vault해시>/index.json`
  (기본 `~/.cache/work-log/...`)
  에 저장된다 — vault 안에 `.wiki/` 같은 폴더를 만들지 않으므로 Obsidian 파일 감시자나
  외부 동기화 클라이언트를 건드리지 않는다
- **기존 문서에 frontmatter 를 주입하지 않는다.** frontmatter 가 없는 문서는 제목(H1)·
  파일명·폴더에서 메타를 추론해 인덱스에만 기록한다. `content` 를 `---` 로 시작시키는
  우회 경로도 차단된다
- 기존 frontmatter 가 있으면 **모르는 키를 전부 보존한다** (Obsidian 공유 플러그인의
  `share_link` 등)
- 쓰기는 vault 루트 안 `.md` 로 제한된다. 경로 판정은 realpath + `path.relative` 기준이라
  `../` 탈출·심볼릭 링크 탈출·형제 디렉토리 접두사 혼동을 모두 막는다
- `create` 는 `wx` 플래그로 원자 생성한다. `overwrite`/`append` 는 `expected_hash` 로
  낙관적 잠금을 걸 수 있어 그 사이 사람이 편집한 내용을 덮어쓰지 않는다

## 인덱싱 규칙

- 대상: `.md`(본문 파싱) + `.html`(제목만). `.json`/`.sql`/`.csv` 는 문서가 아니므로 제외
- **twin 병합**: 같은 디렉토리·같은 이름의 `.md`+`.html` 은 md 를 정본으로 삼고 html 을
  `companions` 로 접는다 (`/common:doc-gen --twin` 산출물이 검색에 두 번 뜨지 않게)
- **전체 스캔 + 전체 해시**: 크기와 수정시각이 같아도 내용이 바뀌면 잡아낸다. 증분
  최적화는 실제 지연이 관측되면 그때 넣는다
- 한글 경로는 원본 바이트(`path`)와 NFC 정규화 키(`key`)를 분리 저장한다. 정규화된 경로로
  파일을 열면 NFD 로 저장된 파일에서 실패하기 때문이다

## frontmatter 스키마 (신규 문서)

```yaml
---
title: 문서 제목
type: plan | report | design | note | spec | meeting | decision
tags: [프로젝트, 주제]
status: draft | active | archived
created: 2026-08-21
updated: 2026-08-21
---
```

문서 간 참조는 Obsidian 호환 `[[상대경로]]` 를 쓴다. Obsidian 에서 그대로 열리고
인덱서가 backlink 로 수집한다.

## 계측 도구

`mcp/probe-cwd.js` 는 MCP 서버 프로세스의 `cwd` 를 확인하는 계측 전용 최소 서버다.
프로젝트 스코프 자동 탐지가 동작하지 않을 때 원인을 확인하는 데 쓴다.
현재 클라이언트의 MCP 서버 `args` 를 이 파일로 바꾸고 재시작한 뒤 `probe` 툴을 호출한다.
