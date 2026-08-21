---
name: sync
description: "work-log vault 를 재스캔해 문서 인덱스를 갱신하고 drift 리포트를 보고한다. '인덱스 갱신해줘', 'work-log 동기화', 새 문서를 추가한 뒤 검색이 안 될 때, 문서 정리 상태를 점검할 때 사용. 기존 문서 파일은 절대 수정하지 않는다."
allowed-tools: Bash, Read
user-invocable: true
---

# work-log 동기화

vault 를 전체 재스캔해 인덱스를 다시 만들고, 무엇이 바뀌었는지 보고한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## 안전 보장 (사용자에게 안심시켜도 되는 사실)

- **sync 는 vault 에 0 바이트를 쓴다.** 인덱스는 vault 밖(`~/.cache/work-log/<vault해시>/index.json`)에 저장된다
- 기존 문서에 frontmatter 를 주입하지 않는다. 없는 문서는 제목·경로에서 메타를 **추론**해 인덱스에만 기록한다
- `.obsidian`·`.trash`·`.git`·`node_modules` 는 스캔하지 않는다

## Step 1: 동기화 실행

`mcp__plugin_work-log_work-log__wiki_sync` 를 호출한다 (인자 없음).

> **툴 이름 주의**: 접두사 `mcp__plugin_work-log_work-log__` 는 `/mcp` 목록 기준이다.
> 목록에 다르게 보이면 **`wiki_` 로 시작하는 이름의 툴**을 찾아 그것을 호출한다.
> 접두사가 달라도 스킬 절차는 동일하다.


전체 스캔 + 전체 해시 방식이다. 수백 개 문서 기준 수백 ms 걸린다.
크기와 수정시각이 같아도 내용이 바뀌었으면 잡아낸다.

## Step 2: 리포트 해석

응답의 `counts` 와 `drift` 를 한국어 표로 정리한다.

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
| `drift.keyCollisions` | 한글 정규화(NFC) 후 같은 이름이 되는 서로 다른 파일 | 파일명 충돌 — 반드시 보고 |
| `drift.noFrontmatter` | frontmatter 없는 문서 수 | **정상이다.** 기존 문서는 비파괴 원칙상 그대로 둔다. 일괄 주입을 제안하지 말 것 |
| `drift.orphanCount` | 아무도 링크하지 않는 문서 수 | `drift.orphansSuppressed` 가 true 면 목록을 출력하지 않는다 — 링크 사용률(`linkedRatio`)이 낮아 대부분이 고아로 잡히는 상태라 의미가 없다. 개수만 언급하고 넘어간다 |

## Step 3: 마무리

깨진 링크나 키 충돌이 있으면 고칠지 물어보고, 사용자가 원할 때만 `/work-log:edit` 로 넘긴다.
**스스로 문서를 고치지 않는다.**

## 오류 대응

| 증상 | 원인 | 대응 |
|------|------|------|
| `스코프가 설정되지 않았습니다` | `.work-log.json` 없음 | `/work-log:init` 안내 |
| `인덱스 락 획득 실패` | 다른 sync 가 진행 중 | 잠시 후 재시도 |
| MCP 툴 자체가 없음 | 서버 미연결 | `/work-log:doctor` 안내 |
