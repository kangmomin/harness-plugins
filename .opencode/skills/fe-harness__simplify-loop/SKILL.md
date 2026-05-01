---
name: fe-harness__simplify-loop
description: "수정 사항이 없을 때까지 빌트인 /simplify 반복 실행 (최대 10회)"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/simplify-loop.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


아래 절차를 따라 Claude Code **빌트인** `/simplify` 스킬을 반복 실행해:

> **주의**: 여기서 `/simplify`는 Claude Code 빌트인 스킬이다. 본 플러그인(fe-harness)의 스킬이 아니다.
> Skill tool 호출 시 `skill: "simplify"` (빌트인)로 호출해야 하며, `skill: "fe-harness:simplify"`로 호출하면 안 된다.

## 절차

1. 빌트인 `/simplify` 를 실행한다 (`skill: "simplify"`).
2. 리뷰 결과를 확인한다:
   - **코드 수정이 적용된 경우** → iteration 카운트를 1 증가시키고 1번으로 돌아간다.
   - **수정할 사항이 없는 경우** (Applied Changes: 없음, 또는 모든 에이전트가 KEEP 판정) → 루프를 종료한다.
3. **최대 10회** iteration 후에는 수정 사항 유무와 관계없이 종료한다.

## 반복 패턴 감지 규칙

simplify 과정에서 **동일한 에러 핸들링 패턴이 3개 파일 이상**에서 반복 수정되면, 개별 수정 대신 유틸리티 추출을 권고한다:

> "동일한 에러 핸들링 패턴이 [N]개 파일에서 반복됩니다. 공통 유틸리티 함수로 추출하는 것을 권고합니다."
> - 대상 파일: [파일 목록]
> - 반복 패턴: [패턴 설명]

이 권고는 수정 건수에 포함하되, 실제 추출은 유저 승인 후에만 진행한다.

## 종료 시 출력

```
Simplify Loop 완료
- 총 iteration: N회
- 총 수정 횟수: M회
```
