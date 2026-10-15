---
name: edit
description: "work-log 에 문서를 작성하거나 기존 문서를 수정한다. '작업 기록 남겨줘', 'work-log 에 정리해줘', '이 내용 문서로 저장', 회의록·결정 사항·보고서를 vault 에 남길 때 사용. 기존 문서의 frontmatter 를 보존하고 비파괴 규칙을 지킨다."
allowed-tools: Bash, Read, Grep, AskUserQuestion
---

# work-log 문서 작성 · 수정

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:edit`, Codex에서는 `$work-log:edit` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 `wiki_` 로 시작하는 기본 이름을 기준으로 찾는다.

## Step 0: 실제 root · 중복 확인 (건너뛰지 말 것)

MCP의 cwd가 아닌 실제 프로젝트 절대경로를 확인하고, 그 디렉토리에서
`node "<plugin-root>/mcp/lib/config.js"` 로 해석한 `cfg.root` 와 `wiki_status.root` 를 canonical
realpath 기준으로 비교한다.
`<plugin-root>` 는 이 `SKILL.md` 의 `../..` 설치 경로다. env가 다른 프로젝트로 고정되어
있지 않은지 실제 checkout `.work-log.json` root와도 비교한다. 불일치하면 검색·쓰기·sync를 중단하고
doctor/init으로 env 우선순위·MCP cwd를 확인한다. 최종 프로젝트 root의 `WORK_LOG_ROOT`
fallback은 재시작 후 root 일치 확인까지 미완료다. 사용자가 기존 flat root로의 전환을 명시적으로 승인했다면
그 root를 `WORK_LOG_ROOT` 로 CLI에도 동일하게 전달하고, `cfg.root`·`wiki_status.root`·승인한 root의
일치를 확인한다. 이 경우에만 기존 checkout 설정과의 차이를 허용하며, 승인 없는 env 불일치는 계속 중단한다.
`scope: global` 표시만으로 실패로 보지 않는다.
독립 프로젝트 모드의 미등록 checkout/worktree는 최초 init이 필요하다. 분류형 전역 모드는
공유 root를 유지한다. 독립 root에서 상위 중앙 vault로 자동 검색 확장하지 않는다.
기존 flat 이력은 자동 이동하지 않으며 필요하면 명시적으로 기존 flat root를 선택한다.

검색·쓰기·자동 sync 전에 `wiki_status.server`이 **0.3.2**인지 확인한다. 구버전이면
같은 vault를 사용하는 구서버를 종료하고 새 소스로 재시작한 뒤 버전·root를 다시 확인한다.
확인 전에는 `INDEX_MISSING`이어도 sync하거나 적용 완료로 보고하지 않는다.

새 문서를 만들기 전에 **반드시** `wiki_resolve` 로 같은 주제의 기존 문서를 찾는다.
`INDEX_MISSING` 이면 root 일치를 확인한 **같은 root** 에 `wiki_sync` 를 실행한 뒤
중복 검색을 다시 한다. 다른 `INDEX_*` 오류는 sync/doctor 안내 후 재검색하며, 검색 실패를
중복 없음으로 간주해 쓰지 않는다.
있으면 사용자에게 "기존 문서를 갱신할지, 새로 만들지" 묻는다. 중복 문서는 wiki 를 망가뜨린다.

## Step 1: 저장 경로 결정

사용자 명시 경로, 현재 프로젝트의 `AGENTS.md`·`CLAUDE.md`, vault의 기존 폴더 규약을 우선한다.
기존 문서는 `wiki_resolve`가 반환한 원래 경로에서 수정하며 자동 재배치하지 않는다.

`projects/`, `_shared/`, `_unclassified/`로 정리된 전역 vault에서는 root를 프로젝트 폴더로
축소하지 않고 신규 문서의 소유·분류를 확인해 다음 경로를 선택한다:

```
projects/<project>/<category>/YYYYMMDD-<kebab-case-이름>-<type>.md
projects/90_personal/<project>/<category>/YYYYMMDD-<kebab-case-이름>-<type>.md   # 개인 프로젝트
_shared/<category>/YYYYMMDD-<kebab-case-이름>-<type>.md
_unclassified/<category>/YYYYMMDD-<kebab-case-이름>-<type>.md
```

- `<project>`는 문서 주제·명시된 작업 범위·기존 프로젝트 폴더로 확인한다. MCP cwd나
  clone basename만으로 추측하지 않는다. 없던 프로젝트 키나 오타는 사용자 확인 없이 만들지 않는다.
- plan/report/note/meeting/decision 등 작업 기록은 `history`, design/spec 등 지속 참조 문서는
  `docs`, 명시적으로 자료로 분류한 Markdown은 `data`를 기본값으로 한다. 실제 성격과 기존 관례가 우선한다.
- 여러 프로젝트 공통 자료는 `_shared`, 소유를 확인하지 못한 자료는 `_unclassified`에 둔다.
- `project` Properties는 폴더 키(공유는 `_shared`, 미분류는 `_unclassified`), `category`는
  history/data/docs다. 신규 create에는 서버가 경로에서 기본값을 넣으며 명시 불일치는 거부한다.
  기존 overwrite/append에는 추가하거나 강제로 고치지 않는다.

별도 독립 프로젝트 root 또는 기존 flat vault는 그 vault의 관례를 따르며, 별도 규약이 없으면
`YYYYMMDD-<kebab-case-이름>-<type>.md`를 사용한다. 독립 root 안에 `projects/<project>`를 다시
중첩하거나 현재 프로젝트 설정을 자동 변경하지 않는다. `type`은 plan/report/design/note/spec/meeting/decision이다.
원시 JSON·SQL·CSV와 첨부는 `wiki_write` 대상이 아니며 기존 파일을 자동 실행하지 않는다.

## Step 2: 쓰기

기본 이름이 `wiki_write` 인 MCP 툴을 호출한다.


| 인자 | 설명 |
|------|------|
| `path` | vault 상대 경로 (`.md` 만) |
| `content` | 본문 (frontmatter 없이 본문만 넘긴다 — 신규 문서면 자동 부여된다) |
| `frontmatter` | 메타 재정의 (선택) — 신규 문서는 자동 부여값을 덮고, overwrite 는 기존 frontmatter 에 병합한다. append 에는 반영되지 않는다 |
| `mode` | `create`(기본) / `overwrite` / `append` |
| `expected_hash` | 낙관적 잠금 (아래 참조) |

### 신규 문서

`mode` 를 생략하면 `create` 다. **파일이 이미 있으면 실패한다** — 이건 안전장치이지 오류가 아니다.
실패하면 Step 0 으로 돌아가 기존 문서를 갱신할지 판단한다.

신규 문서에는 frontmatter 가 자동으로 붙는다:
```yaml
---
title: 문서 제목
type: plan
tags: [프로젝트, 주제]
status: draft
created: 2026-08-21
updated: 2026-08-21
---
```

### 기존 문서 수정 — 비파괴 규칙

이 규칙들은 서버가 강제한다. 우회하려 하지 말고 그대로 따른다.

1. **frontmatter 가 없는 기존 문서에는 frontmatter 를 주입하지 않는다.**
   `content` 를 `---` 로 시작시키는 것도 차단된다. 본문만 넘겨라
2. **frontmatter 가 있는 문서는 모르는 키가 보존된다** (`share_link` 등 Obsidian 플러그인 키)
3. 덮어쓰기 전에 `wiki_read` 로 현재 내용을 읽고, 응답 내용을 근거로 수정하라
4. 사람이 그 사이 Obsidian 에서 편집했을 위험이 있으면 `expected_hash` 를 넘겨라. 값은 파일 전체 바이트의 SHA-1 앞 12자리이며, 직전 `wiki_write` 응답의 `written.hash` 를 쓰거나 파일에서 직접 계산한다 (`wiki_read` 는 hash 를 주지 않는다)
   (불일치하면 거부된다 → 다시 읽고, 오류 메시지의 `actual` 값으로 재시도)

같은 문서의 work-log 쓰기는 기존/교체 inode의 커널 잠금으로 직렬화된다. 대기 시간 초과는 살아 있거나 중지된 실행이 끝날 때까지 기다린다. 프로세스 종료 시 잠금은 자동 해제된다. 구버전 `.write-lock`이 남았다면 같은 vault의 구버전 서버가 모두 종료된 것을 확인한 뒤 해당 구버전 잠금 디렉터리만 제거한다. 신버전의 cache `index.lock`은 삭제하지 않는다.

`write_state: unknown`은 저장 여부를 확정할 수 없는 응답이다. `wiki_read`로 본문을 확인한 뒤 재시도 여부를 결정한다. `written`이 확인된 뒤 indexing만 실패하면 `wiki_sync`만 호출한다. 쓰기/sync에는 `wiki_status.safeIO.available:true`가 필요하다.

### 이어쓰기

기존 문서 끝에 덧붙이기만 하면 되는 경우 `mode: "append"` 가 가장 안전하다.
기존 내용을 전혀 건드리지 않는다.

## Step 3: 링크 연결

관련 문서가 있으면 본문에 Obsidian 호환 링크를 넣는다:

```markdown
관련: [[projects/ocs/history/20260820-이전-작업-plan]]
```

인덱서가 backlink 로 수집하므로 wiki 가 실제로 연결된 그래프로 자란다.
`wiki_resolve` 로 확인한 **실제 존재하는 경로**만 링크한다 — 없는 경로는 다음 sync 에서
`brokenLinks` 로 잡힌다.

## Step 4: 확인

응답의 `written`은 저장된 경로·hash·bytes이고 `indexing`은 검색 반영 결과다.
`indexing.status == OK`이면 `indexed`의 제목·종류·태그와 저장 경로를 보고한다.
`written`이 있고 인덱싱이 `FAILED`/`DEGRADED`이면 문서는 이미 저장됐다. 오류를 보고하고
`wiki_sync`만 재시도한다. 같은 `wiki_write`/append를 다시 보내지 않는다.
임의의 동일 쓰기 요청 재전송에 대한 멱등성은 제공하지 않는다.

## 하지 않는 것

- 기존 문서 대량 정리·일괄 frontmatter 추가 (사용자가 명시적으로 요청해도 문서 단위로 확인받는다)
- 문서 삭제 (MCP 에 삭제 툴이 없다. 사용자가 직접 지운다)
- `.html` 쓰기 (거부된다. html 은 `/common:doc-gen` 이 만든다)
