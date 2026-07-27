---
name: e2e-test
description: "하네스별 E2E 테스트 스킬로 위임하는 라우터. 'E2E 돌려줘', 'API 실제로 테스트해줘', 구현 검증이 필요할 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm] <대상 설명 또는 시나리오 ID>"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/e2e-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# E2E Test (라우터)

하네스별 `e2e-test`로 위임한다. **이 문서에 절차는 없다** — 시나리오 구성·실행·리포트는 위임 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 검증 방식 |
|--------|----------|----------|
| `--be` | `/be-harness:e2e-test` | 서버 기동 + curl 실제 HTTP 요청 |
| `--fe` | `/fe-harness:e2e-test` | Playwright 브라우저 시나리오 |
| `--mm` | `/minmos-harness:e2e-test-mm` | REST/gRPC + Apidog 스펙 대조 + status code 정합성 |

## 특이사항

- 네 대상은 **검증 매체가 서로 다르다** (curl / 브라우저 / gRPC 포함). 후보가 2개 이상이면 선택지에 위 "검증 방식" 열을 함께 제시한다.
- `--doctor`, `--skip-server`, `--tag <ID>` 등 대상 고유 플래그는 해석하지 않고 그대로 전달한다.
- 반복 실행(실패 → 수정 → 재테스트)이 필요하면 `/common:e2e-test-loop` 를 쓴다.
