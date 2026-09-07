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

설치 후에는 현재 클라이언트를 재시작한다. 서버·캐시 검색·읽기는 Node 18 이상에서 동작한다. 쓰기와 인덱스 동기화는 Linux/macOS의 Python 3.9 이상과 POSIX descriptor/lock API가 추가로 필요하다. npm 패키지 설치는 필요 없다. `wiki_status.safeIO`로 실제 지원 여부를 확인하며, 미지원 환경에서 안전하지 않은 쓰기로 대체하지 않는다.
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
> — 그래프는 전역 재계산이 필요하다. `scan.filesRead`·`bytesRead`·`durationMs`로 규모와
> 비용을 함께 측정하고, 실제 지연이 확인된 경우 증분화를 검토한다.

`wiki_write` 응답은 저장 결과(`written`: path/hash/bytes)와 인덱싱 결과(`indexing`)를 분리한다.
저장 후 인덱싱이 `FAILED`/`DEGRADED`여도 저장은 완료됐다. 이때는 `wiki_sync`만 재시도하며
동일 append를 재전송하지 않는다. 임의의 반복 쓰기 요청 자체의 멱등성은 제공하지 않는다.

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
- `create` 는 완성된 임시 파일의 exclusive link로 원자 생성한다. `overwrite`/`append` 는 `expected_hash` 로
  쓰기 시 읽은 내용의 해시를 비교하며, 앞서 읽은 내용과 달라졌으면 거부한다
- 쓰기는 Python의 descriptor-relative I/O와 `O_NOFOLLOW`를 사용한다. 경로의 각 부모 inode를 고정하고 잠금 대기·임시 파일 생성·commit에서 교체 여부를 검사한다. 정리는 고정한 디렉터리의 자기 임시 파일에만 적용한다.
- 같은 문서의 work-log 쓰기는 기존 inode와 교체 inode의 `flock`을 교체 완료까지 유지한다. inode가 바뀐 대기자는 새 파일을 다시 열고 해시를 비교한다. cache 경로나 vault 별칭이 달라도 직렬화되며, 5초를 넘기면 시간 초과로 응답한다.
- 인덱스의 `index.lock`은 삭제하지 않는 잠금 파일이다. mtime으로 살아 있는 소유자를 탈취하지 않는다. 프로세스가 죽으면 커널이 잠금을 해제한다. 중지된 프로세스는 계속 소유한다.
- 신규 문서와 임시 파일은 0600이다. append/overwrite는 기존 mode·uid·gid·조회 가능한 xattr 및 ACL을 복사하고 fd로 재확인한다. 적용 또는 확인 실패 시 교체하지 않는다. 숨겨진 privileged 속성까지 보존한다고 보장하지 않는다. Linux 동작은 프로세스 테스트로 검증했으며 macOS ACL 구현은 공식 API에 근거하지만 이 작업의 실행 환경에서는 실측하지 않았다.
- **0.3.0 업그레이드 전 같은 vault를 사용하는 구버전 MCP 서버를 모두 종료한다.** 구버전의 `.write-lock`/mtime 잠금과 혼합 실행은 지원하지 않는다. 남은 구버전 문서 잠금은 해당 실행의 종료를 확인한 뒤 그 디렉터리만 제거한다. 신버전의 `index.lock`을 수동으로 지워 잠금을 풀지 않는다.

잠금은 같은 프로토콜을 사용하는 로컬 writer 사이의 협력 잠금이다. POSIX rename은 source 이름의 검사와 교체를 하나의 CAS로 수행하지 않는다. 게시 전후 inode·내용을 확인하지만, 임의 프로세스가 잠금을 무시하고 이름이나 같은 inode를 계속 바꾸는 것까지 격리하지 않는다. 게시 후 불일치는 성공으로 보고하지 않고 `write_state: unknown`으로 반환한다. 저장 후 응답이 끊겨 `write_state: unknown`이면 `wiki_read`로 현재 본문을 확인하고 재시도 여부를 결정한다. 저장이 확인된 `written` 응답의 인덱싱 실패는 `wiki_sync`만 재시도한다.


## 인덱싱 규칙

- 대상: `.md`(본문 파싱) + `.html`(제목만). `.json`/`.sql`/`.csv` 는 문서가 아니므로 제외
- **twin 병합**: 같은 디렉토리·같은 이름의 `.md`+`.html` 은 md 를 정본으로 삼고 html 을
  `companions` 로 접는다 (`/common:doc-gen --twin` 산출물이 검색에 두 번 뜨지 않게)
- **전체 스캔 + 전체 해시**: 크기와 수정시각이 같아도 내용이 바뀌면 잡아낸다. 증분
  최적화는 실제 지연이 관측되면 그때 넣는다
- 한글 경로는 원본 바이트(`path`)와 NFC 정규화 키(`key`)를 분리 저장한다. 정규화된 경로로
  파일을 열면 NFD 로 저장된 파일에서 실패하기 때문이다
- 코드 펜스(backtick/tilde) 안의 제목과 링크는 인덱싱하지 않는다. 파일명 단독 링크는
  같은 폴더·vault 루트의 정확한 경로를 우선하고, 그 외 후보가 여러 개면 `ambiguousLinks`로 보고한다
- 읽기·파싱 오류는 경로별 `errors`와 `DEGRADED`로 보고한다. 해당 파일/하위 폴더의 이전
  엔트리는 `stale: true`로 유지해 삭제 drift를 만들지 않고, 정상 문서는 계속 갱신한다
- 비어 있지 않은 `excludes` 설정은 기본 제외 목록을 대체한다. 생략/빈 배열은 기본값이다

### 캐시와 진단

캐시는 제목·태그·요약·본문 excerpt를 포함한다. vault별 캐시 디렉터리는 0700,
인덱스/경로 표식은 0600으로 저장한다. 다른 사용자에게 공유할 산출물로 취급하지 않는다.
캐시는 만료 시각 없이 다음 동기화까지 보관되며, 버전·root·schema가 맞지 않거나 손상되면
`wiki_status.indexState`에 원인을 표시하고 `wiki_sync`로 재생성한다.
캐시만 지우려면 해당 vault를 사용하는 MCP 실행을 모두 종료한 후 `wiki_status.indexDir`의
해당 vault 디렉터리만 제거한다. vault 문서나 다른 vault 캐시를 삭제할 필요는 없다.

`scan`의 파일 수·읽은 bytes·오류 수·소요 시간과 `generatedAt`을 함께 확인한다.
Linux/Node 24에서 합성 문서 300개(약 1 MB)는 35 ms, 3,000개(약 10 MB)는 253 ms였다
(2026-09-06, 파일 생성 직후의 warm cache, 스캔 1회). 운영 환경의 성능 보장이나 회귀 임계값은 아니다.

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
