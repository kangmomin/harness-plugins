---
name: e2e-test-loop
description: "하네스별 E2E 테스트 반복 루프(테스트 → 수정 → 재테스트)로 위임하는 라우터. '테스트 통과할 때까지 고쳐줘', 'E2E 루프 돌려줘' 요청 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--mm]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/e2e-test-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# E2E Test Loop (라우터)

하네스별 `e2e-test-loop`으로 위임한다. **이 문서에 절차는 없다** — 루프 상한·종료 조건·수정 위임은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 적용 |
|--------|----------|------|
| `--be` | `/be-harness:e2e-test-loop` | 범용 백엔드 (최대 5회) |
| `--mm` | `/minmos-harness:e2e-test-loop-mm` | minmos — verdict 5종 세분화 + attempt별 raw 기록 + HTML 리포트 |

## 특이사항

- 프론트엔드 계열에는 대응 스킬이 없다. 반복 검증이 필요하면 `/common:test-loop` (단위/통합 테스트 루프)를 안내한다.
- 두 대상은 리포트 형식이 크게 다르다(단순 요약 vs 정직한 자기 점검 v2). 선택지에 이 차이를 한 줄로 밝힌다.
