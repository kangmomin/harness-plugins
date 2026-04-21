---
name: e2e-test-loop
description: "E2E 테스트 → 이슈 수정 → 재테스트를 반복한다. 모든 테스트가 통과하거나 최대 5회에 도달할 때까지."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/e2e-test-loop.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# E2E Test Loop

`/be-harness:e2e-test` 를 실행하고, 실패가 있으면 수정한 뒤 다시 실행한다. 최대 5회 반복.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 루프 규칙

```
for iteration in 1..5:
  run /be-harness:e2e-test
  if result == PASS (모든 시나리오 통과):
    break
  if result starts with "[SKIPPED:":
    return result   # 오케스트레이터가 상위에서 판단하도록 그대로 전달
  # FAIL 처리
  collect failures
  delegate to general-purpose agent to fix:
    Agent tool:
      subagent_type: general-purpose
      prompt: |
        아래 E2E 실패를 수정하세요. 프로젝트 루트: {CWD}.
        failures:
        {실패 목록 전체}
        - 원인 추적: 서버 로그 / 코드 흐름 / Spec 차이 중 무엇인지 먼저 특정하고 수정.
        - 파일 수정 후 `{buildCommand}` (비어있지 않으면) 로 빌드 통과 확인.
        - 수정 후 "수정: N건, 파일: [목록]" 형식으로 보고.
  commit:
    git add [수정 파일]
    git commit -m "Fix: E2E 실패 수정 (iteration {iteration})"
```

## 종료 조건

| 조건 | 반환값 |
|------|-------|
| 모든 시나리오 PASS | `"이슈: 0건, 수정: N (iter 1..k)"` |
| `[SKIPPED:*]` | SKIPPED 그대로 전달 |
| 5회 도달했는데 여전히 실패 | `"이슈: N건 미해결, 수정: M"` |

## 루프 판정 세부

- iter 1이 PASS면 수정 없음, 즉시 종료.
- iter 1이 FAIL → 수정 1회 → iter 2 실행. iter 2 PASS면 수정 1건으로 종료.
- 같은 실패 시나리오가 iter N과 iter N+1에서 동일 에러로 반복되면 **같은 파일을 두 번 연속 같은 방향으로 수정 중**임을 뜻한다. 즉시 중단하고 미해결로 보고.

## 주의사항

- `e2e-test` 스킬이 서버 기동/종료를 책임지므로, 이 루프에서는 서버 상태를 건드리지 않는다.
- 수정 에이전트가 서버를 재시작하지 않도록 명시한다 (기존 서버 유지).
- `buildCommand` 가 비어있으면 빌드 체크는 SKIP.
