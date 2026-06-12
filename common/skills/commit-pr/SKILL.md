---
name: commit-pr
description: "커밋, 브랜치 생성, push, draft PR 오픈까지 전체 워크플로우를 수행한다. 'PR 올려줘', '커밋하고 PR까지', 작업 완료 후 리뷰 요청 준비 시 사용."
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit-pr.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Commit & PR

커밋부터 draft PR 오픈까지 수행한다.
브랜치 판정·명명·커밋·push는 `/common:commit-push`가 canonical이며, 본 스킬은 그 앞뒤(기존 PR 확인, VERSION 갱신, PR 생성)만 정의한다.

## Step 1: 기존 PR 확인

```bash
gh pr view --json number,state,url
```

현재 브랜치에 이미 열린 PR이 있으면 → `/common:commit-push` 절차만 수행하고 종료한다 (기존 PR에 커밋이 추가됨).

## Step 2: VERSION 갱신

프로젝트 루트에 `VERSION` 파일이 있으면 patch 버전을 올려 이번 커밋에 포함한다.
없으면 건너뛴다 (`SKIPPED:NO_VERSION_FILE`).

## Step 3: 커밋 + Push

`/common:commit-push` 절차를 수행한다.
보호 브랜치에서의 새 브랜치 생성, `worktree-*` 등 컨벤션 불일치 브랜치의 이름 재생성, 논리 단위 커밋, push가 모두 여기에 포함된다.

## Step 4: draft PR 생성

1. 변경사항을 분석해 PR 제목과 본문을 작성한다.
   - 제목: 커밋 메시지 컨벤션과 동일한 `Prefix: 한국어 설명` 형식
   - 본문: 변경 요약, 주요 변경 파일, 테스트/검증 결과
2. base는 현재 브랜치의 바로 상위 브랜치로 한다.
3. draft PR을 연다:
   ```bash
   gh pr create --draft --title "{제목}" --body "{본문}" --base {상위 브랜치}
   ```
4. 생성된 PR URL을 보고한다.

실패 시 (gh 미인증, 권한 부족 등): 에러 원문을 보고하고 선택지를 제시한다.
> 1. 안내된 조치(예: `gh auth login`) 후 Step 4 재시도
> 2. 중단 — 커밋과 push는 완료된 상태로 종료
