---
name: commit-push-hd
description: "커밋 후 원격 저장소에 push. 브랜치가 없거나 컨벤션에 맞지 않으면 브랜치 생성부터 진행."
---

## Step 0: 브랜치 확인 및 생성

push 전에 현재 브랜치 상태를 확인하고, 필요하면 브랜치를 먼저 생성한다.

```bash
git branch --show-current
```

### 판정 로직

| 현재 브랜치 | 조건 | 행동 |
|------------|------|------|
| `main`, `master`, `dev`, `develop`, `rc-*` | 보호 브랜치 | **브랜치 생성 후 push** (Step 0.1로) |
| `feat/*`, `hotfix/*` | 컨벤션 매칭 | **그대로 push 진행** (Step 1로) |
| 그 외 (`worktree-*`, 임의 이름 등) | 컨벤션 불일치 | **브랜치 이름 변경 후 push** (Step 0.2로) |

### Step 0.1: 보호 브랜치 → 새 브랜치 생성

1. `git diff`의 변경 파일과 내용을 읽고 핵심 변경 내용을 2~4 단어로 요약한다.
2. 사용자에게 prefix를 질문한다:
   > "현재 보호 브랜치(`{브랜치명}`)에 있습니다. 새 브랜치를 생성합니다.
   > 브랜치 prefix를 선택해주세요:"
   > 1. `feat` — 기능 추가/변경
   > 2. `hotfix` — 긴급 버그 수정
3. kebab-case로 브랜치명을 생성하고 사용자에게 확인을 받는다:
   > "브랜치명: `feat/login-form-component` — 이대로 생성할까요? (Y/수정)"
4. 브랜치를 생성한다:
   ```bash
   git checkout -b {브랜치명}
   ```
5. Step 1로 진행한다.

### Step 0.2: 컨벤션 불일치 → 브랜치 이름 변경

1. `git diff` 기반으로 적절한 브랜치명을 제안한다.
2. 사용자에게 확인을 받는다:
   > "현재 브랜치(`{현재 이름}`)가 컨벤션에 맞지 않습니다.
   > `feat/xxx`로 변경할까요? (Y/수정)"
3. 브랜치 이름을 변경한다:
   ```bash
   git branch -m {새 브랜치명}
   ```
4. Step 1로 진행한다.

### 브랜치 이름 규칙

```
^(feat|hotfix)/[a-z][a-z0-9-]{1,40}$
```

| 규칙 | 올바른 예 | 잘못된 예 |
|------|----------|----------|
| 영문 소문자 + 하이픈만 | `feat/dark-mode-toggle` | `feat/DarkMode` |
| 2~4 단어 | `feat/user-profile-card` | `feat/a` |
| prefix 뒤 `/` 필수 | `feat/user-auth` | `feat-user-auth` |

---

## Step 1: 커밋

`$commit-hd` 을 실행하여 변경사항을 논리적 단위별로 커밋한다.

## Step 2: Push

```bash
git push -u origin {현재 브랜치}
```

push 실패 시 원인을 분석하고 유저에게 안내한다.
