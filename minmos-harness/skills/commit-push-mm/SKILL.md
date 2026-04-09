---
name: commit-push-mm
description: "/commit 진행 후 push 까지 수행"
user-invocable: true
---

## 보호 브랜치 확인

push 전에 현재 브랜치를 확인하고, 아래 보호 브랜치에 해당하면 **push를 중단**하고 사용자에게 경고하세요.

### 보호 브랜치 목록
- `main`
- `master`
- `rc` (rc로 시작하는 브랜치 포함, 예: `rc1.0.0`)
- `dev`

### 확인 방법
```bash
git branch --show-current
```

현재 브랜치가 보호 브랜치(`main`, `master`, `dev`, 또는 `rc`로 시작하는 브랜치)에 해당하면:
- 커밋은 정상 진행하되 **push는 하지 마세요**
- 사용자에게 `"보호 브랜치(${브랜치명})에는 직접 push할 수 없습니다. /commit-hard-push 를 사용하세요."` 라고 안내하세요

보호 브랜치가 아니면 아래 단계를 정상 수행하세요.

## 수행 단계

/minmos-harness:commit-mm 진행 후 push 까지 해
