---
name: default-conventions
description: "하네스별 개발 가이드라인 문서로 위임하는 라우터. '컨벤션 알려줘', '이 프로젝트 규칙이 뭐야', 코드 작성 기준이 필요할 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/default-conventions.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Default Conventions (라우터)

하네스별 `default-conventions`로 위임한다. **이 문서에 규칙은 없다** — 실제 가이드라인은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 범위 |
|--------|----------|------|
| `--be` | `/be-harness:default-conventions` | 범용 백엔드 가이드라인 |
| `--fe` | `/fe-harness:default-conventions` | 범용 프론트엔드 가이드라인 |
| `--mm` | `/minmos-harness:default-conventions-mm` | minmos 로컬 컨벤션 (Go/Gorm/UoW, go-conventions SSOT 참조) |

## 특이사항

- Go 백엔드의 **정본(SSOT)** 은 `go-conventions` 플러그인이다. `--mm`은 그 정본을 참조하는 로컬 문서이므로, 정본과 어긋나 보이면 `go-conventions:conventions-guide` 를 우선한다.
