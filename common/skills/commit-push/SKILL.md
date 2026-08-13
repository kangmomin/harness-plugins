---
name: commit-push
description: "브랜치 검증/생성 후 /common:commit 절차로 커밋하고 push까지 수행한다. '커밋하고 푸시해줘', '올려줘' 요청 시 사용. 보호 브랜치에 있으면 새 브랜치를 먼저 생성하고, 브랜치명이 컨벤션에 맞지 않으면 재생성한다."
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit-push.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Commit & Push

브랜치 상태를 검증·정비한 뒤 커밋하고 push한다.
**브랜치 판정·명명 규칙의 canonical은 본 스킬이다** (commit-pr이 이 절차를 위임받는다).

## Step 1: 브랜치 판정

```bash
git branch --show-current
```

| 현재 브랜치 | 판정 | 행동 |
|------------|------|------|
| `main`, `master`, `dev`, `rc*` | 보호 브랜치 | Step 1.2 (새 브랜치 생성) |
| `feat/*`, `hotfix/*` | 컨벤션 매칭 | Step 1.1 (네이밍 적합성 검증) |
| 그 외 (`worktree-*`, 임의 이름 등) | 컨벤션 불일치 | Step 1.3 (브랜치 이름 재생성) |

### Step 1.1: 네이밍 적합성 검증

`feat/*`·`hotfix/*`에 매칭되더라도 브랜치명이 실제 작업 내용을 반영하는지 검증한다.

1. `git diff --name-only`와 `git diff --stat`으로 변경 파일·내용을 파악하고, 핵심 변경을 2~4 단어로 요약한다.
2. 브랜치명의 설명부(prefix 뒤)와 요약을 비교한다 — **핵심 도메인/기능 키워드가 겹치면 일치, 전혀 다른 작업이면 불일치**:
   - `feat/add-review-api`인데 실제로는 장바구니 작업 중 → 불일치
   - `feat/cart-feature`인데 실제로도 장바구니 작업 중 → 일치
3. **일치** → Step 2로 진행.
4. **불일치** → 사용자에게 선택지를 제시한다:
   > "현재 브랜치명 `{현재 이름}`이 실제 작업 내용({요약})과 맞지 않는 것 같습니다.
   > 1. 그대로 유지 → Step 2로 진행
   > 2. `{제안 브랜치명}`으로 변경 → `git branch -m` 후 Step 2로 진행
   > 3. 직접 입력 → 입력값을 이름 규칙으로 검증 후 `git branch -m`, Step 2로 진행"

### Step 1.2: 보호 브랜치 → 새 브랜치 생성

1. `git diff`의 변경 파일·내용을 읽고 핵심 변경을 2~4 단어로 요약한다.
2. 사용자에게 prefix를 질문한다 (diff 분석 기반 추천 표시):
   > "현재 보호 브랜치(`{브랜치명}`)에 있습니다. 새 브랜치를 생성합니다. prefix를 선택해주세요:
   > 1. `feat` — 기능 추가/변경
   > 2. `hotfix` — 긴급 버그 수정
   > (추천: `{추천값}`)"
3. 요약을 kebab-case 브랜치명으로 변환하고 확인을 받는다:
   > "브랜치명: `feat/add-grpc-support` — 이대로 생성할까요? (Y/수정할 이름 입력)"
   사용자가 다른 이름을 입력하면 그 이름을 쓰되 이름 규칙 검증은 동일하게 수행한다.
4. `git checkout -b {브랜치명}` 후 Step 2로 진행한다.

### Step 1.3: 컨벤션 불일치 → 브랜치 이름 재생성

1. Step 1.2의 1~3과 동일하게 새 이름을 만들고 확인을 받는다:
   > "현재 브랜치(`{현재 이름}`)가 컨벤션에 맞지 않습니다. `{새 이름}`으로 변경할까요? (Y/수정할 이름 입력)"
2. `git branch -m {새 브랜치명}` 후 Step 2로 진행한다.

### 브랜치 이름 규칙 (canonical)

```
^(feat|hotfix)/[a-z][a-z0-9-]{1,40}$
```

| 규칙 | 올바른 예 | 잘못된 예 |
|------|----------|----------|
| 영문 소문자 + 하이픈만 | `feat/add-grpc-support` | `feat/Add_gRPC_Support` |
| 2~4 단어로 간결하게 | `feat/grpc-e2e-test` | `feat/add-grpc-e2e-test-automation-for-all` |
| 구체적 의미 포함 | `feat/cursor-pagination` | `feat/update-code` |
| prefix 뒤 `/` 필수 | `feat/user-auth` | `feat-user-auth` |
| 숫자 허용, 선행 숫자 금지 | `feat/oauth2-login` | `feat/2nd-attempt` |

이름 생성 시: 한글 요약은 영문으로 번역, 공백·특수문자는 `-`로 치환, 연속 `-`와 앞뒤 `-` 제거.
생성/변경 직후 위 패턴에 매칭되는지 검증하고, 실패 시 이름을 1회 재생성한다. 재생성도 실패하면 사용자에게 직접 입력을 요청한다 (입력값도 동일 패턴으로 검증).

### 브랜치 모델 (선택 — 오버라이드 선언 시에만)

프로젝트 오버라이드 **`.claude/common/common.md`** 에 브랜치 모델 표(선언 형식은 플러그인 루트 `OVERRIDES.md` 참조)가 선언돼 있으면:

1. Step 1 판정표의 "컨벤션 매칭" 행과 이름 규칙 정규식의 prefix 부분(`(feat|hotfix)`)을 **선언된 prefix 집합으로 대체**한다 — 예: `release/*`가 선언된 프로젝트에서 release 브랜치는 Step 1.3 재생성 대상이 아니다.
2. Step 1.2의 prefix 선택지를 선언된 prefix 집합으로 제한한다.
3. `{prefix} → {허용 base}` 매핑은 `/common:commit-pr`의 base 결정과 PR 조합 검증에 사용된다.

선언 위치는 스킬별 파일이 아닌 **공통 레이어(`common.md`)여야 한다** — 이 정책은 commit-push와 commit-pr이 함께 소비하는데, 각 스킬은 자기 스킬별 오버라이드만 읽기 때문이다.
미선언 프로젝트는 본 섹션을 무시한다 (동작 불변).

## Step 2: 커밋

`/common:commit` 절차를 수행해 변경사항을 논리 단위별로 커밋한다.

## Step 3: Assumption Gate (push 전 필수)

**추론/추측의 원격 유출 차단이 목적** — `[Assumption]` 태그는 로컬 개발 단계의 기록이며, 원격에 올라가는 시점에는 모두 사용자 확인을 거쳐 제거되어야 한다. **태그가 남아 있으면 push하지 않는다.**
**Assumption Gate의 canonical은 본 섹션이다** (commit-hard-push, commit-pr, 각 하네스의 workflow-pr이 이 절차를 따른다).

### Step 3.1: 스캔

| 대상 | 범위 | 처리 |
|------|------|------|
| 코드 태그 | 브랜치 전체 diff(`{base}...HEAD`)의 **추가된 라인** | 하드 게이트 — 해소 전 push 금지 |
| 커밋 메시지 태그 | **미push 커밋**(`@{upstream}..HEAD`, upstream 없으면 `{base}..HEAD`)의 본문 | 하드 게이트 — 해소 전 push 금지 |
| 이미 push된 커밋 메시지의 태그 | 재작성 불가 (force-push 금지) | WARN 보고만 |

```bash
# 코드 태그: 브랜치 전체 diff의 추가 라인
git diff {base}...HEAD | grep -n '^+.*\[Assumption\]'
# 커밋 메시지 태그: 미push 커밋 본문
git log @{upstream}..HEAD --format='%h %s%n%b' | grep -B1 '\[Assumption\]'
```

- `{base}`는 이미 알려진 값이 있으면 재사용한다 — 기존 open PR의 `baseRefName`, `/common:commit-pr` Step 2에서 결정한 base. 없으면 `@{upstream}`, 그것도 없으면 기본 브랜치(`origin/HEAD`)와의 merge-base.
- 브랜치 diff 밖(이 브랜치가 만들지 않은 라인)의 레거시 태그는 검사하지 않는다 — surgical 원칙.
- **모두 0건이면 조용히 통과**하고 Step 4로 진행한다.

### Step 3.2: 항목별 사용자 확인

발견 시 push를 중단하고, 전체 목록(`파일:라인 — 내용` / `커밋 해시 — 메시지`)을 보여준 뒤 항목별로 확인을 받는다:

> `[Assumption]` {N}건이 남아 있습니다. 모두 해소되어야 push/PR이 가능합니다.
> `{파일:라인}` — "{추측 내용}"
> 1. 승인 — 추측이 맞음. 태그 제거 후 진행
> 2. 수정 — 추측이 틀림. 지시받은 방향으로 코드 수정 후 재검사
> 3. 중단 — push 없이 종료 (`BLOCKED:ASSUMPTION_UNRESOLVED`)

### Step 3.3: 태그 제거

- **코드 주석**: `[Assumption]` 마커를 제거한다. 사유 설명이 코드 이해에 필요하면 태그 없는 일반 주석으로 전환하고, 아니면 라인을 삭제한다. "수정" 항목은 지시에 따라 코드를 고친다.
- **커밋 메시지** (미push 한정): 마지막 커밋이면 `git commit --amend`, 그 이전 커밋이면 `git reset --soft {범위 시작}` 후 `/common:commit` 절차로 재커밋한다.
- 제거/수정 변경은 관련 논리 단위 커밋에 amend하거나 `Chore: 확인된 Assumption 태그 정리`로 커밋한다.
- 승인된 항목은 **확정된 결정**으로 기록을 이관한다 — PR 흐름(`/common:commit-pr`)이면 PR 본문의 "확정된 결정" 섹션, 아니면 최종 보고에 포함한다.

### Step 3.4: 재검사

Step 3.1을 다시 수행한다. **코드 태그 0건 + 미push 메시지 태그 0건**이 될 때까지 반복하며, 그 전에는 Step 4로 진행하지 않는다.

## Step 4: Push

```bash
git push -u origin {현재 브랜치}
```

실패 시 (인증 실패, push 거부, 원격 충돌 등): 에러 원문과 원인 분석을 보고하고 선택지를 제시한다.
> 1. 안내된 조치(예: `git pull --rebase`, `gh auth login`) 후 재시도
> 2. 중단 — 현재 상태 그대로 종료 (커밋은 로컬에 보존됨)

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | push 완료 |
| `BLOCKED:ASSUMPTION_UNRESOLVED` | Assumption Gate 미해소 — 사용자 중단 선택 또는 확인 대기 |
