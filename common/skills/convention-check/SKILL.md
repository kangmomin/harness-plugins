---
name: convention-check
description: "하네스별 컨벤션 위반 검사 스킬로 위임하는 라우터. '컨벤션 검사해줘', '규칙 위반 확인', 커밋/PR 전 점검 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm] [검사 범위]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/convention-check.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Convention Check (라우터)

하네스별 `convention-check`로 위임한다. **이 문서에 절차는 없다** — 검사 항목과 판정 기준은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 검사 기준 |
|--------|----------|----------|
| `--be` | `/be-harness:convention-check` | 레이어 분리·에러 처리·네이밍 (범용 백엔드) |
| `--fe` | `/fe-harness:convention-check` | 컴포넌트 구조·Props·상태 관리 (범용 프론트엔드) |
| `--mm` | `/minmos-harness:convention-check-mm` | minmos 로컬 컨벤션 (go-conventions SSOT 정렬) |

## 특이사항

- 검사 기준이 하네스마다 다르므로 **대상을 잘못 고르면 무의미한 위반 목록이 나온다.** 후보가 2개 이상이면 위 "검사 기준" 열을 선택지에 함께 제시한다.
