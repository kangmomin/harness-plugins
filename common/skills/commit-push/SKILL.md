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
생성/변경 직후 위 패턴에 매칭되는지 검증하고, 실패 시 이름을 재생성한다.

## Step 2: 커밋

`/common:commit` 절차를 수행해 변경사항을 논리 단위별로 커밋한다.

## Step 3: Push

```bash
git push -u origin {현재 브랜치}
```

실패 시 (인증 실패, push 거부, 원격 충돌 등): 에러 원문과 원인 분석을 보고하고 선택지를 제시한다.
> 1. 안내된 조치(예: `git pull --rebase`, `gh auth login`) 후 재시도
> 2. 중단 — 현재 상태 그대로 종료 (커밋은 로컬에 보존됨)
