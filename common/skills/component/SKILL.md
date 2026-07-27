---
name: component
description: "하네스별 컴포넌트 생성 스킬로 위임하는 라우터. '컴포넌트 만들어줘', '보일러플레이트 생성' 요청 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--fe] <컴포넌트 설명>"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/component.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Component (라우터)

프론트엔드 하네스의 `component` 스킬로 위임한다. **이 문서에 생성 절차는 없다** — 템플릿과 배치 규칙은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 설정 출처 |
|--------|----------|----------|
| `--fe` | `/fe-harness:component` | `.claude/fe-harness.local.md` |

## 특이사항

- 백엔드 계열에는 대응 스킬이 없다. 컴포넌트 생성은 프론트엔드 하네스 전용이다.
