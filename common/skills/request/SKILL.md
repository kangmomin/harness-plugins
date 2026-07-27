---
name: request
description: "하네스별 Technical Spec 생성 스킬로 위임하는 라우터. 'API 만들어줘', '스펙 정리해줘', 요구사항이 모호해 명세가 필요할 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm|--hd] <기능 설명 또는 요청>"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/request.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Request (라우터)

하네스별 `request`로 위임한다. **이 문서에 절차는 없다** — 질문 시퀀스와 Spec 템플릿은 위임 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 적용 |
|--------|----------|------|
| `--be` | `/be-harness:request` | 범용 백엔드 — API 생성/수정/검토/디버깅 |
| `--fe` | `/fe-harness:request` | 범용 프론트엔드 — 화면/컴포넌트/API 연동 |
| `--mm` | `/minmos-harness:request-mm` | minmos 백엔드 |
| `--hd` | `/hyeondongs-harness:request-hd` | hyeondongs 프론트엔드 |

## 특이사항

- 백엔드 계열(`--be`, `--mm`)과 프론트엔드 계열(`--fe`, `--hd`)은 **Spec 템플릿이 근본적으로 다르다** (엔드포인트·엣지 케이스 표 vs ASCII 레이아웃·Props). 후보에 양쪽이 모두 있으면 선택지에서 이 차이를 한 줄로 밝힌다.
- 프론트/백엔드를 동시에 명세해야 하면 `/common:start-workflow --fs` 로 안내한다 (풀스택은 Feature Matrix + 통신 계약으로 다룬다).
