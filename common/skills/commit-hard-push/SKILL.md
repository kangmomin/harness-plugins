---
name: commit-hard-push
description: "보호 브랜치 제한 없이 /commit 진행 후 현재 브랜치에 그대로 push한다. main 등 보호 브랜치에 직접 push해야 할 때, '그냥 현재 브랜치에 올려줘' 요청 시 사용."
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit-hard-push.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Commit & Hard Push

`/common:commit-push`와 달리 **브랜치 판정·생성·네이밍 검증을 모두 생략**하고, 어떤 브랜치에서든 현재 브랜치에 그대로 push한다.

## Step 1: 커밋

`/common:commit` 절차를 수행해 변경사항을 논리 단위별로 커밋한다.

## Step 2: Assumption Gate

`/common:commit-push`의 Step 3(Assumption Gate) 절차를 수행한다. `[Assumption]` 태그가 모두 해소되기 전에는 push하지 않는다.
코드 base와 미push 메시지 기준을 구분한다. 보호 브랜치 직접 push는 fetch한 해당 원격 브랜치를 코드 기준으로 쓸 수 있다. feature upstream을 PR base로 임의 대체하지 않는다. 명시 upstream/base 미존재나 Git 오류는 BLOCKED다. 커밋 이후 검사한 HEAD를 기록하고 push 직전 동일성을 확인한다.

## Step 3: Push

```bash
git push -u origin {현재 브랜치}
```

실패 시: 에러 원문과 원인 분석을 보고하고 중단한다 (커밋은 로컬에 보존됨).
