---
name: test-loop
description: "하네스별 테스트 반복 루프(테스트 → 수정 → 재실행)로 위임하는 라우터. '테스트 통과할 때까지 고쳐줘', '테스트 루프 돌려줘' 요청 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--fe]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/test-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Test Loop (라우터)

프론트엔드 하네스의 `test-loop` 스킬로 위임한다. **이 문서에 루프 규칙은 없다** — 상한과 종료 조건은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 설정 출처 |
|--------|----------|----------|
| `--fe` | `/fe-harness:test-loop` | `.claude/fe-harness.local.md` |

## 특이사항

- 이 루프는 **단위/통합 테스트** 대상이다. 브라우저 E2E 반복은 `/common:e2e-test` 를, 백엔드 HTTP E2E 반복은 `/common:e2e-test-loop` 를 쓴다.
