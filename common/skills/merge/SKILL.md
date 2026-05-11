---
name: merge
description: "현재 브랜치 또는 지정한 PR 을 머지. 머지 전에 doc-gen 으로 PR 요약을 생성해 컨펌하고, 머지 방식(일반/스쿼시/리베이스)을 선택."
allowed-tools: AskUserQuestion, Bash, Read, Skill
argument-hint: "[PR번호]"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/common/common.md` — 플러그인 공통 (모든 스킬에 적용)
- `.claude/common/skills/merge.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

---

# /common:merge — PR 머지

PR 의 변경 사항을 `/common:doc-gen` 으로 요약해 사용자에게 컨펌받고, 선택한 방식으로 머지한다.

## 핵심 원칙

- **doc-gen 컨펌 전 머지 금지** — Phase 2 를 절대 건너뛰지 않는다.
- **머지 방식은 사용자 선택** — 자동 결정하지 않는다.
- **취소는 언제든 가능** — 컨펌 단계에서 "취소" 선택 시 머지하지 않고 종료.
- **브랜치 삭제는 머지 성공 후에만**.

---

## Phase 0: 사전 점검

먼저 `gh` 가용성을 확인한다.

```bash
gh auth status
```

실패 시: "GitHub CLI 가 설치/인증되지 않았습니다. `gh auth login` 후 다시 시도하세요." 안내하고 중단.

---

## Phase 1: PR 식별

`$ARGUMENTS` 를 정리해 PR 번호를 결정한다.

1. `$ARGUMENTS` 에 숫자(예: `42`, `#42`) 가 있으면 그 번호를 사용.
2. 없으면 `gh pr view --json number,headRefName,baseRefName,state,isDraft,title,url,mergeable,additions,deletions,changedFiles` 로 현재 브랜치에 연결된 PR 검색.
3. 둘 다 실패하면 `AskUserQuestion` 으로 "PR 번호를 알려주세요" 질문 → 입력값을 사용.

### PR 상태 검증

`gh pr view <num> --json state,isDraft,mergeable,title,url,baseRefName,headRefName,additions,deletions,changedFiles`

| 상태 | 행동 |
|------|------|
| `state == "MERGED"` | "이미 머지된 PR 입니다." 보고 후 종료 |
| `state == "CLOSED"` | "닫힌 PR 입니다. 다시 열고 진행하려면 `gh pr reopen <num>`." 보고 후 종료 |
| `isDraft == true` | 사용자에게 "draft 상태입니다. ready 로 전환 후 진행할까요? (Y/N)" 질문. N 이면 종료. Y 이면 Phase 2 진입 시 `gh pr ready <num>` 호출 예약 |
| `mergeable == "CONFLICTING"` | "충돌이 있어 머지 불가합니다. 충돌 해결 후 다시 실행하세요." 보고 후 종료 |
| `mergeable == "UNKNOWN"` | 한 번 더 시도(10초 대기 후 재조회). 여전히 UNKNOWN 이면 사용자에게 알리고 계속 진행 (gh 가 머지 시점에 재검사) |

이후 단계에서는 위 메타데이터(`title`, `url`, `headRefName`, `baseRefName`, `additions/deletions/changedFiles`)를 활용한다.

---

## Phase 2: PR 요약 생성 (doc-gen)

`/common:doc-gen` 을 호출해 PR 의 변경 사항을 md 로 요약한다.

### 호출 방법

```
/common:doc-gen -md PR#<번호>
```

doc-gen 이 단계적 질문을 띄우면 다음과 같이 안내한다 (가능하면 사용자 대신 자동 응답):

- **범위 종류**: PR (인자로 이미 분류됨, 확인만 하면 됨)
- **PR 번호**: Phase 1 에서 확정한 번호
- **문서 초점**: **"변경 요약 (review 용)"** — diff 요약·영향 범위·핵심 포인트 중심
- **출력 경로**: 기본값 (`./docs/doc-gen-<unix>.md`) 사용

### 결과 처리

doc-gen 이 생성한 md 파일을 `Read` 로 다시 읽어 다음 핵심 섹션만 사용자에게 인라인으로 출력한다:

- **PR 헤드라인** (제목 / 번호 / base ← head)
- **TL;DR** (3~5줄)
- **변경 카운트** (`additions / deletions / changedFiles`, Phase 1 에서 수집)
- **변경 요약 / Diff 요약** 섹션 본문
- **엣지 케이스 / 주의** 섹션이 있으면 그대로 (위험 신호 강조)

전체 본문은 절대경로로 안내해 사용자가 원하면 직접 열어볼 수 있게 한다.

```
📄 PR 요약 문서 생성 완료
- 경로: <abs path>
- PR: #<번호> "<제목>" (<base> ← <head>)
- 변경: +<add> / -<del> / 파일 <N>개

(인라인 요약 본문)
```

doc-gen 호출이 실패한 경우(예: `gh pr diff` 실패, 권한 부족) 사용자에게 그대로 보고하고 Phase 3 로 넘어가되 "doc-gen 요약 실패. PR 변경 사항을 직접 검토했는지 확인 후 진행하세요." 경고를 표시한다.

---

## Phase 3: 컨펌 + 머지 방식 선택

`AskUserQuestion` 으로 컨펌과 머지 방식 선택을 **한 번에** 받는다.

```
질문: PR #<번호> "<제목>" 을 어떻게 머지할까요?

옵션:
1. 일반 머지 — merge commit 을 생성하고 커밋 이력을 그대로 보존
2. 스쿼시 머지 — 모든 커밋을 하나로 합쳐 main 에 적용
3. 리베이스 머지 — 커밋들을 main 위에 1:1 재적용 (fast-forward)
4. 취소 — 머지하지 않고 종료
```

| 선택 | gh 옵션 |
|------|---------|
| 일반 머지 | `--merge` |
| 스쿼시 머지 | `--squash` |
| 리베이스 머지 | `--rebase` |
| 취소 | (실행 안 함, 종료) |

취소 시: "사용자가 머지를 취소했습니다. doc-gen 요약 파일은 그대로 보존됩니다." 보고 후 종료.

---

## Phase 4: 머지 실행

### Step 4.1: 현재 위치 확인

머지하려는 브랜치가 **현재 체크아웃된 브랜치** 라면 먼저 base 브랜치로 이동한다(아래 Step 4.4 의 main 동기화와 동일한 로직).

```bash
git rev-parse --abbrev-ref HEAD
```

현재 브랜치 == PR 의 `headRefName` 이면:
```bash
git fetch origin
git checkout <baseRefName>
```

### Step 4.2: draft 해제 (필요 시)

Phase 1 에서 ready 전환을 예약했으면:
```bash
gh pr ready <num>
```

### Step 4.3: 머지

```bash
gh pr merge <num> <선택된 옵션> --delete-branch
```

- `--delete-branch`: 머지 성공 시 원격·로컬 브랜치 자동 삭제. 단, 머지하려는 브랜치를 체크아웃한 상태에서는 로컬 삭제가 실패할 수 있으므로 Step 4.1 에서 미리 이동.

머지 실패 시 (충돌, 권한, 보호 규칙 등):
- gh 가 반환한 에러를 그대로 보고
- 가능한 원인 한 줄로 안내 (충돌 / 필수 리뷰 부족 / 상태 체크 실패 등)
- 종료

### Step 4.4: main 동기화

```bash
git checkout <baseRefName>
git pull --ff-only origin <baseRefName>
```

---

## Phase 5: 보고

```
✅ 머지 완료
- PR: #<번호> "<제목>"
- 방식: 일반 머지 | 스쿼시 머지 | 리베이스 머지
- 베이스: <baseRefName> (<merge commit SHA>)
- 변경: +<add> / -<del> / 파일 <N>개
- 브랜치: 자동 삭제됨 (원격 + 로컬)
- 요약 문서: <abs path of doc-gen output>
- URL: <PR URL>
```

머지된 commit SHA 는 `git log -1 --format=%H <baseRefName>` 로 확인.

---

## 호출 예시

```bash
# 현재 브랜치에 연결된 PR 머지
/common:merge

# 특정 PR 번호 지정
/common:merge 42
/common:merge #42
```

## 실패 메시지 모음

| 상황 | 메시지 |
|------|--------|
| gh 미인증 | "GitHub CLI 가 설치/인증되지 않았습니다. `gh auth login` 후 다시 시도하세요." |
| PR 미식별 | "현재 브랜치에서 PR 을 찾지 못했습니다. PR 번호를 인자로 전달하세요. (예: `/common:merge 42`)" |
| 이미 머지됨 | "PR #<번호> 는 이미 머지된 상태입니다." |
| 충돌 | "PR 에 충돌이 있어 머지 불가합니다. 충돌 해결 후 다시 실행하세요." |
| 보호 규칙 위반 | gh 의 원본 메시지 + "필수 리뷰/체크가 충족되지 않은 것으로 보입니다." 안내 |
| 사용자 취소 | "사용자가 머지를 취소했습니다." |
