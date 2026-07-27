---
name: lint-check
description: "하네스별 린트 검사 스킬로 위임하는 라우터. '린트 돌려줘', 'eslint 확인', 커밋 전 정적 검사가 필요할 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--fe|--hd] [검사 범위]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/lint-check.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Lint Check (라우터)

프론트엔드 하네스의 `lint-check` 스킬로 위임한다. **이 문서에 검사 규칙은 없다** — 린터 설정과 판정은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 설정 출처 |
|--------|----------|----------|
| `--fe` | `/fe-harness:lint-check` | `.claude/fe-harness.local.md` (`lintCommand`) |
| `--hd` | `/hyeondongs-harness:lint-check-hd` | `.hyeondong-config.json` |

## 특이사항

- 백엔드 계열에는 대응 스킬이 없다. Go/Node 린트는 profile의 `lintCommand` 로 워크플로우 품질 루프에서 실행된다.
