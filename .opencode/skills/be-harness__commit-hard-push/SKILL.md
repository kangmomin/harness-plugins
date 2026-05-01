---
name: be-harness__commit-hard-push
description: "보호 브랜치 제한 없이 /commit 진행 후 push 까지 수행"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/commit-hard-push.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


/be-harness:commit 진행 후 push 까지 해

이 스킬은 보호 브랜치 제한 없이 어떤 브랜치에서든 push를 수행합니다.
