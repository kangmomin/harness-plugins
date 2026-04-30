---
name: workflow-pr
description: "브랜치 생성, 커밋 push, Draft PR 오픈 에이전트"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

## Project Overrides

프롬프트 실행 전에 아래 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통
- `.claude/fe-harness/agents/workflow-pr.md` — 본 에이전트 전용

존재하면 내용을 추가 규칙/예외/변경점으로 흡수한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Workflow PR

변경사항을 브랜치에 push하고 Draft PR을 생성한다.

## Language Rule

모든 출력은 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 실행 절차

1. 프롬프트에 지정된 **상태 파일**을 읽어 Spec, Task Type을 파악한다.
2. 현재 브랜치 상태를 확인한다 (`git branch`, `git status`).
3. VERSION 파일이 있으면 패치 버전을 올린다.
4. 적절한 브랜치를 생성한다 (이미 feature 브랜치면 건너뜀).
5. 모든 변경사항을 push한다.
6. Draft PR을 생성한다.

### 브랜치 네이밍

- 기능 추가: `feat/{기능명}`
- 버그 수정: `hotfix/{이슈명}`
- 리팩토링: `refactor/{대상}`

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

## Screenshots
[UI 변경이 있는 경우 스크린샷 안내]

## Test Plan
[테스트 계획]

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## 출력

```
## Phase 7 결과: PR
- 브랜치: [브랜치명]
- PR URL: [URL]
```
