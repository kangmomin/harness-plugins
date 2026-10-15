---
name: sync
description: "work-log vault 를 재스캔해 문서 인덱스를 갱신하고 drift 리포트를 보고한다. '인덱스 갱신해줘', 'work-log 동기화', 새 문서를 추가한 뒤 검색이 안 될 때, 문서 정리 상태를 점검할 때 사용. 기존 문서 파일은 절대 수정하지 않는다."
allowed-tools: Bash, Read
---

# work-log 동기화

vault 를 전체 재스캔해 인덱스를 다시 만들고, 무엇이 바뀌었는지 보고한다.

쓰기/sync는 Linux/macOS의 Python 3.9 이상을 사용한다. `wiki_status.safeIO`가 unavailable이면 원인을 보고한다. 인덱스 잠금은 mtime으로 탈취하지 않으며, timeout을 풀기 위해 `index.lock`을 삭제하지 않는다. 업그레이드 전 같은 vault의 구버전 MCP 서버를 모두 종료한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:sync`, Codex에서는 `$work-log:sync` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 `wiki_` 로 시작하는 기본 이름을 기준으로 찾는다.

## 안전 보장 (사용자에게 안심시켜도 되는 사실)

- **sync 는 vault 에 0 바이트를 쓴다.** 인덱스는 vault 밖(`$XDG_CACHE_HOME/work-log/<vault해시>/index.json`, 기본 `~/.cache`)에 저장된다
- 기존 문서에 frontmatter 를 주입하지 않는다. 없는 문서는 제목·경로에서 메타를 **추론**해 인덱스에만 기록한다
- 기본 제외 목록은 `.obsidian`·`.trash`·`.git`·`node_modules`·`.wiki`다. 설정의 비어 있지 않은 `excludes` 배열은 기본 목록을 대체하고, 생략/빈 배열은 기본 목록을 사용한다

## Step 1: 실제 root 확인 · 동기화 실행

MCP의 cwd가 아닌 실제 프로젝트 절대경로를 확인한다. 그 디렉토리에서
`node "<plugin-root>/mcp/lib/config.js"` 로 해석한 `cfg.root` 와 `wiki_status.root` 가
canonical realpath 기준으로 일치하기 전에는 sync를 실행하지 않는다. env가 다른 프로젝트로 고정되어 있지 않은지
실제 checkout `.work-log.json` root와도 비교한다. `<plugin-root>` 는 이 `SKILL.md` 의 `../..` 설치 경로다.
불일치하면 doctor/init으로 env 우선순위·MCP cwd(플러그인 경로일 수 있음)를 진단하고,
최종 프로젝트 root의 `WORK_LOG_ROOT` fallback 및 재시작 후 확인을 안내한다.
사용자가 기존 flat root로의 전환을 명시적으로 승인했다면 그 root를 `WORK_LOG_ROOT` 로 CLI에도
동일하게 전달하고, `cfg.root`·`wiki_status.root`·승인한 root의 일치를 확인한다. 이 경우에만 기존
checkout 설정과의 차이를 허용하며, 승인 없는 env 불일치는 sync를 중단한다.
`scope: global` 표시만으로 실패로 보지 않는다. 독립 프로젝트 모드의 미등록 checkout/worktree는
최초 init이 필요하다. 분류형 전역 모드는 확인한 공유 root 전체를 동기화한다.
상위 중앙 vault로 스캔·검색을 자동 확장하거나 기존 flat 이력을 자동 이동하지 않는다.
옛 이력이 필요하면 명시적으로 기존 flat root를 선택한다.

구조화된 전역 vault는 root를 프로젝트 하위 폴더로 축소하지 않는다. `projects/`, `_shared/`,
`_unclassified/`와 유지된 기존 문서를 함께 스캔하며 분류 메타는 인덱스에만 반영한다.
0.3.2의 index v3는 구캐시 재생성이 필요하다. 설치본 재시작 뒤 `wiki_status.server`와 실제 root를
확인하고 같은 root를 sync한다. 아직 살아 있는 0.3.1 서버의 sync는 v3 적용 확인을 대신하지 않는다.

일치가 확인된 같은 root에 기본 이름이 `wiki_sync` 인 MCP 툴을 호출한다 (인자 없음).


전체 스캔 + 전체 해시 방식이다. 응답의 `scan.filesRead`·`bytesRead`·`durationMs`로 실제 비용을 확인한다.
크기와 수정시각이 같아도 내용이 바뀌었으면 잡아낸다.

## Step 2: 리포트 해석

응답의 `counts` 와 `drift` 를 한국어 표로 정리한다.
`status == DEGRADED`이면 `errors`의 경로·작업·원인을 함께 보고한다.
읽기/파싱 실패한 문서와 디렉터리 하위의 기존 인덱스는 `stale: true`로 보존되며 삭제로 집계하지 않는다.
실패한 신규 문서는 오류에만 나타난다. 오류를 해결한 뒤 `wiki_sync`로 최신 상태를 복원한다.

### 요약

| 항목 | 값 |
|------|-----|
| vault | `root` |
| 정본 문서(.md) | `counts.canonical` |
| html 단독 | `counts.htmlOnly` |
| html 짝(companion) | `counts.companions` |

### 변경

| 구분 | 건수 | 내용 |
|------|------|------|
| 신규 | `drift.added.length` | 경로 나열 (10건 초과 시 앞 10건 + "외 N건") |
| 변경 | `drift.changed.length` | 동일 |
| 삭제 | `drift.removed.length` | 동일 |

`drift.firstRun` 이 true 면 최초 인덱싱이므로 "신규"가 전체 문서 수와 같다 — 이상이 아니다.

### 점검 항목 (제안만, 자동 수정 금지)

| 항목 | 의미 | 대응 |
|------|------|------|
| `drift.brokenLinks` | `[[링크]]` 가 가리키는 문서가 없음 | 경로를 고칠지 사용자에게 **묻는다** |
| `drift.ambiguousLinks` | 파일명만 쓴 링크에 후보가 여러 개 | `candidates`를 보여주고 의도한 전체 상대 경로로 연결한다. 같은 폴더의 정확한 경로가 있으면 그것이 우선한다 |
| `drift.keyCollisions` | 한글 정규화(NFC) 후 같은 이름이 되는 서로 다른 파일 | 파일명 충돌 — 반드시 보고 |
| `drift.noFrontmatter` | frontmatter 없는 문서 수 | **정상이다.** 기존 문서는 비파괴 원칙상 그대로 둔다. 일괄 주입을 제안하지 말 것 |
| `drift.orphanCount` | 아무도 링크하지 않는 문서 수 | `drift.orphansSuppressed` 가 true 면 목록을 출력하지 않는다 — 링크 사용률(`linkedRatio`)이 낮아 대부분이 고아로 잡히는 상태라 의미가 없다. 개수만 언급하고 넘어간다 |

## Step 3: 마무리

깨진 링크나 키 충돌이 있으면 고칠지 물어보고, 사용자가 원할 때만 edit 스킬로 넘긴다.
**스스로 문서를 고치지 않는다.**

## 오류 대응

| 증상 | 원인 | 대응 |
|------|------|------|
| `스코프가 설정되지 않았습니다` | work-log 설정 없음 | init 스킬 안내 |
| `인덱스 잠금 대기 시간 초과` | 다른 sync·쓰기가 인덱스 잠금을 쥐고 있음 | 잠시 후 재시도 |
| `legacy index owner` | 같은 vault 를 쓰는 구버전 MCP 서버가 실행 중 | 구버전 서버를 모두 종료한 뒤 재시도 |
| MCP 툴 자체가 없음 | 서버 미연결 | doctor 스킬 안내 |
