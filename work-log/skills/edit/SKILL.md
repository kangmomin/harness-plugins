---
name: edit
description: "work-log 에 문서를 작성하거나 기존 문서를 수정한다. '작업 기록 남겨줘', 'work-log 에 정리해줘', '이 내용 문서로 저장', 회의록·결정 사항·보고서를 vault 에 남길 때 사용. 기존 문서의 frontmatter 를 보존하고 비파괴 규칙을 지킨다."
allowed-tools: Bash, Read, Grep, AskUserQuestion
user-invocable: true
argument-hint: "[문서 주제 또는 경로]"
---

# work-log 문서 작성 · 수정

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## Step 0: 중복 확인 (건너뛰지 말 것)

새 문서를 만들기 전에 **반드시** `wiki_resolve` 로 같은 주제의 기존 문서를 찾는다.
있으면 사용자에게 "기존 문서를 갱신할지, 새로 만들지" 묻는다. 중복 문서는 wiki 를 망가뜨린다.

## Step 1: 저장 경로 결정

전역 `CLAUDE.md` 규약을 **그대로 존중한다**:

```
<vault>/claude/YYYYMMDD-<kebab-case-이름>-<type>.md
```

`type` 은 `plan` | `report` | `design` | `note` | `spec` | `meeting` | `decision`.
회의록·의사결정처럼 기존 폴더 관례가 뚜렷하면 그 폴더를 따른다(`회의/`, `의사 결정/`).
사용자가 경로를 명시했으면 그 지시가 우선한다.

## Step 2: 쓰기

`mcp__plugin_work-log_work-log__wiki_write` 를 호출한다.

> **툴 이름 주의**: 접두사 `mcp__plugin_work-log_work-log__` 는 `/mcp` 목록 기준이다.
> 목록에 다르게 보이면 **`wiki_` 로 시작하는 이름의 툴**을 찾아 그것을 호출한다.
> 접두사가 달라도 스킬 절차는 동일하다.


| 인자 | 설명 |
|------|------|
| `path` | vault 상대 경로 (`.md` 만) |
| `content` | 본문 (frontmatter 없이 본문만 넘긴다 — 신규 문서면 자동 부여된다) |
| `frontmatter` | 신규 문서의 메타 재정의 (선택) |
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
4. 사람이 그 사이 Obsidian 에서 편집했을 위험이 있으면 `expected_hash` 를 넘겨라
   (불일치하면 거부된다 → 다시 읽고 재시도)

### 이어쓰기

기존 문서 끝에 덧붙이기만 하면 되는 경우 `mode: "append"` 가 가장 안전하다.
기존 내용을 전혀 건드리지 않는다.

## Step 3: 링크 연결

관련 문서가 있으면 본문에 Obsidian 호환 링크를 넣는다:

```markdown
관련: [[claude/20260820-이전-작업-plan]]
```

인덱서가 backlink 로 수집하므로 wiki 가 실제로 연결된 그래프로 자란다.
`wiki_resolve` 로 확인한 **실제 존재하는 경로**만 링크한다 — 없는 경로는 다음 sync 에서
`brokenLinks` 로 잡힌다.

## Step 4: 확인

쓰기가 성공하면 인덱스가 자동 갱신된다. 응답의 `indexed` 에 인덱싱된 제목·종류·태그가 실려 온다.
사용자에게 저장 경로와 함께 보고한다.

## 하지 않는 것

- 기존 문서 대량 정리·일괄 frontmatter 추가 (사용자가 명시적으로 요청해도 문서 단위로 확인받는다)
- 문서 삭제 (MCP 에 삭제 툴이 없다. 사용자가 직접 지운다)
- `.html` 쓰기 (거부된다. html 은 `/common:doc-gen` 이 만든다)
