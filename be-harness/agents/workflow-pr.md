---
name: workflow-pr
description: "브랜치 생성, 커밋 push, Draft PR 오픈 에이전트"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/agents/workflow-pr.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Workflow PR

변경사항을 브랜치에 push하고 Draft PR을 생성한다.

## Language Rule

모든 출력은 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 실행 절차

1. 프롬프트에 지정된 **상태 파일**을 읽어 Spec, Task Type을 파악한다.
2. 현재 브랜치 상태를 확인한다 (`git branch`, `git status`).
3. VERSION 파일이 있으면 패치 버전을 올린다.
4. 적절한 브랜치를 생성한다 (이미 feature 브랜치면 건너뜀).
5. **Assumption Gate (push 전 필수)**: base 브랜치와의 diff 추가 라인(`git diff {base}...HEAD | grep '^+.*\[Assumption\]'`)과 미push 커밋 메시지 본문에서 `[Assumption]`을 검색한다.
   - 0건 → 다음 단계로 진행.
   - 발견 → **push/PR을 수행하지 않고** `BLOCKED:ASSUMPTION_UNRESOLVED`로 태그 목록을 보고하고 종료한다. 유저 확인·태그 정리·재실행은 오케스트레이터(start-workflow) 담당.
6. 모든 변경사항을 push한다.
7. Draft PR을 생성한다. 본문에 `[Assumption]` 태그를 남기지 않는다. 게이트 재실행으로 승인·제거된 항목이 상태 파일에 있으면 본문 `### 확정된 결정` 섹션에 태그 없이 기록한다.

### 브랜치 네이밍

- 기능 추가: `feat/[기능명]`
- 버그 수정: `hotfix/[이슈명]`

### VERSION 업데이트

```bash
# VERSION 파일이 있으면 패치 버전 +1
current=$(cat VERSION)
# 예: 1.2.3 → 1.2.4
```

### PR 생성

```bash
gh pr create --draft --title "[제목]" --body "$(cat <<'EOF'
## Summary
[Spec 기반 변경 요약 - 2~3줄]

## Changes
[주요 변경 파일/기능 목록]

## Test Plan
[테스트 계획]

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## 출력

```
## Phase 10 결과: PR
- 브랜치: [브랜치명]
- PR URL: [URL]
```

Assumption Gate에 걸린 경우:

```
## Phase 10 결과: PR
- 상태: BLOCKED:ASSUMPTION_UNRESOLVED
- 태그 목록: [파일:라인 — 내용 / 커밋 해시 — 메시지]
```
