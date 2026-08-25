---
name: api-share-note
description: "This skill should be used when the user asks to \"API 변경 공유용으로 정리해줘\", \"변경된 API 요약해줘\", \"API 변경 공유 노트 만들어줘\", \"어제부터 바뀐 API 정리\", \"share API changes\", \"api change summary\", or mentions summarizing created/modified APIs over a period for sharing with other teams. Scans git route deltas between a baseline and current work (merged + unmerged branches), classifies changes as replaced/behavior-changed/new/pending-merge, attaches Apidog endpoint links, and produces a fixed-format share note saved to work-log."
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion, mcp__apidog__read_project_oas_w9of5k, mcp__apidog__refresh_project_oas_w9of5k, mcp__plugin_work-log_work-log__wiki_write, mcp__plugin_work-log_work-log__wiki_resolve
argument-hint: "[기간 예: 어제부터 | 8/24-8/25 | <baseline-commit>] [--no-save]"
user-invocable: true
---

# API Share Note

특정 기간에 수정·생성된 API 를 git 델타에서 수집해 **대체(구→신) · 동작 변경 · 신규 · 미머지** 로 분류하고, Apidog 엔드포인트 링크를 달아 **디테일 없는 공유용 요약 노트**를 생성한다. 요청/응답 필드·에러코드 같은 wire-level 상세는 넣지 않는다 — 그건 별도 스펙 문서의 몫이다.

Apidog MCP 도구는 `mcp__apidog__read_project_oas_*` 패턴으로 세션 도구 목록에서 탐색한다 (이 프로젝트 기본: `..._w9of5k`. 프로젝트마다 suffix 가 다르므로 실제 세션 도구 목록 기준으로 찾는다).

## Language Rule

유저와의 모든 대화(AskUserQuestion, 안내, 설명, 확인)는 **한국어**로 진행한다.

## Prerequisites

- **git 저장소**: 델타 수집의 원천. 필수.
- **Apidog MCP 서버**: 엔드포인트 링크 매핑용. 권장 — 없으면 링크 없이 경로만 표기하고 계속 진행한다.
- **work-log 플러그인** (`wiki_write`/`wiki_resolve`): 결과 저장용. 선택 — 없으면 전역 규약 경로에 파일로 저장한다.

> **MCP 판정**: 실제 MCP tool 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다 (상세: `/minmos-harness:doctor`).

## 절차

### 1. 범위·baseline 확정

1. `$ARGUMENTS` 에서 기간 또는 baseline 커밋을 파싱한다. 미지정이면 **어제 00:00 ~ 현재** 를 기본값으로 하되, 모호하면 AskUserQuestion 으로 확인한다.
2. 통합 브랜치를 판별한다: `git symbolic-ref refs/remotes/origin/HEAD` (오프라인 동작) 또는 관례상 `dev` > `main` 순. **브랜치명을 하드코딩하지 말 것** — repo 마다 다르다.
3. baseline = 범위 시작 이전 통합 브랜치의 마지막 커밋:
   ```bash
   git log --first-parent origin/<통합브랜치> --before=<범위시작> -1 --format=%H
   ```
4. 비교 대상: baseline ↔ `origin/<통합브랜치>` 최신 + 기간 내 커밋이 있는 **미머지 feature 브랜치** (`git branch -a --sort=-committerdate` + `git log <브랜치> --since=<범위시작> --oneline` 으로 선별).

### 2. 라우트 델타 수집

Go/Gin 전제의 라우트 등록 패턴으로 각 ref 를 grep 해 엔드포인트 집합을 뽑고 diff 한다:

```bash
git grep -E '\.(GET|POST|PATCH|PUT|DELETE)\(' <ref> -- '*.go'
```

- 라우트 등록 파일 위치는 repo 마다 다르다. 경로를 가정하지 말고 grep 결과로 찾는다.
- 분류: baseline 에 없고 통합 브랜치에 있으면 **신규**, 그 반대는 **제거**(신규와 짝지어지면 **대체**), feature 브랜치에만 있으면 **미머지**.
- worktree 격리 세션에서는 `for`/파이프 조합 git 명령이 거부될 수 있다 — ref 별로 **단순 명령을 개별 실행**한다.

### 3. 동작 변경 수집

경로는 그대로인데 계약(상태코드·검증·권한·술어)이 바뀐 것을 찾는다:

1. `git log origin/<통합브랜치> --since=<범위시작> --oneline` 커밋 메시지에서 후보를 추린다 (fix/변경/검증/권한 류 키워드).
2. 후보는 해당 핸들러·에러 매퍼의 diff 를 `git show <commit> -- <파일>` 로 판독해 **실제 계약 변경인지 확인**한다. 커밋 메시지만 믿고 싣지 않는다.

### 4. Apidog 링크 매핑

1. `refresh_project_oas` (또는 `read_project_oas`) 로 프로젝트 OAS 를 가져온다.
   - 응답이 크면 파일로 저장된다 — Read 로 전체를 읽지 말고 스크립트로 파싱한다.
   - 저장 파일의 JSON 루트는 `{"refreshed":..., "oas": {...}}` 래핑일 수 있다 — `data["oas"]` 로 접근한다.
2. 각 operation 의 `x-run-in-apidog` 값에서 **`-run` 접미사를 제거**한 것이 엔드포인트 페이지 링크다:
   - `.../apis/api-<ID>-run` → `.../apis/api-<ID>`
3. OAS 에 없는 엔드포인트(미머지 등)는 **링크 없이 `METHOD /path` 만 표기**한다. 링크를 추측으로 만들지 않는다.

### 5. 공유 노트 생성 (고정 형식)

아래 템플릿을 그대로 따른다. **디테일(필드·스키마·에러코드) 금지**, 항목당 한 줄 설명.

```markdown
# 📢 <서비스명> API 변경 공유 (M/D – M/D)

## 🔄 바뀐 것

| 항목 | 변경 |
|------|------|
| [`METHOD /old`](링크) | → [`METHOD /new`](링크) 로 대체 |
| [`METHOD /path`](링크) | <동작 변경 한 줄 요약> |
| [`METHOD /path`](링크) | 제거됨 (대체 없음) |

## ➕ 추가된 API (<통합브랜치> 반영 완료)

- [`METHOD /path`](링크) — 한 줄 설명

## 🚧 추가 예정 (구현 완료 · <통합브랜치> 머지 대기)

- [`METHOD /path`](링크) — 한 줄 설명 *(브랜치에만 존재, 미반영)*

---

*Apidog 프로젝트: [<프로젝트ID> (<서비스명>)](https://app.apidog.com/web/project/<프로젝트ID>) — 링크는 프로젝트 접근 권한 필요.*
```

- 해당 없는 섹션은 통째로 생략한다.
- **머지/미머지 구분은 필수** — 공유받는 쪽이 "지금 쓸 수 있는가"를 판단하는 기준이다.

### 6. work-log 저장 (기본 동작)

`--no-save` 가 아니면 저장한다. work-log 도구는 접두사가 다르면 **`wiki_` 로 시작하는 툴**을 세션 도구 목록에서 탐색한다:

1. `wiki_resolve` 로 같은 주제의 기존 문서를 먼저 확인한다 (중복 방지). 있으면 갱신/신규 여부를 유저에게 묻는다.
2. `wiki_write` 로 저장: `claude/YYYYMMDD-<서비스>-api-changes-share-note.md`
3. work-log 플러그인이 없으면 전역 규약 경로(`/workspace/work-log/claude/` 등 CLAUDE.md 규약)에 Write 로 저장한다.
4. 상세 스펙 문서가 이미 있으면 `관련: [[...]]` 링크를 넣는다.

저장 경로와 노트 본문을 유저에게 보고하고 종료한다.

## 주의사항

- **요약이 목적**이다. 필드 정의·페이지네이션 형태·에러코드 표가 필요하면 별도 스펙 문서로 안내하고, 이 노트에는 넣지 않는다.
- 라우트 grep 패턴은 Go/Gin 전제다. 다른 프레임워크면 해당 라우트 등록 패턴으로 치환한다.
- Apidog 링크는 반드시 OAS 실측(`x-run-in-apidog`)에서 얻는다. ID 를 추측하지 않는다.
