---
name: test-loop
description: "단위 테스트 + E2E 테스트를 실행하고, 실패 시 수정 후 재실행을 반복한다. (최대 5회)"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/test-loop.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Test Loop

단위 테스트와 E2E 테스트를 실행하고, 실패 시 코드를 수정한 후 재실행한다.
최대 5회 반복하며, 모든 테스트가 통과하면 조기 종료한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## 실행 흐름

```
for iteration in 1..5:
  1. 단위 테스트 실행
  2. 실패 시 → 원인 분석 → 코드 수정 → modified = true
  3. E2E 테스트 실행 (e2eRunner가 none이 아닌 경우)
  4. 실패 시 → 원인 분석 → 코드 수정 → modified = true
  
  modified == false? → 루프 탈출
  modified == true? → 다음 iteration
```

### Step 1: 단위 테스트 실행

profile의 `testCommand` 를 우선 사용:

```bash
{testCommand}
```

`testCommand` 가 비어있으면 `testRunner` 값에 따라 fallback:
- **vitest**: `npx vitest run --reporter=verbose`
- **jest**: `npx jest --verbose`

실패 시:
1. 에러 메시지를 분석한다.
2. 테스트 코드 또는 소스 코드를 수정한다.
3. `modified = true`로 설정한다.

### Step 2: E2E 테스트 실행

`e2eRunner` 가 `none` 이거나 `e2eCommand` 가 비어있으면 건너뛴다.

profile의 `e2eCommand` 를 우선 사용:

```bash
{e2eCommand}
```

비어있으면 `e2eRunner` 값에 따라 fallback:
- **playwright**: `npx playwright test --reporter=list`
- **cypress**: `npx cypress run`

실패 시:
1. 에러 메시지를 분석한다.
2. 테스트 코드 또는 소스 코드를 수정한다.
3. `modified = true`로 설정한다.

### 루프 판정

- `modified == false` → 모든 테스트 통과, 루프 탈출
- `modified == true` → 수정사항 있음, 다음 iteration
- 5회 도달 → 미해결 사항 보고 후 강제 탈출

---

## 종료 시 출력

```markdown
## Test Loop 결과

- **총 iteration**: N회
- **단위 테스트 수정**: M건
- **E2E 테스트 수정**: K건
- **최종 상태**: ALL PASS / UNRESOLVED ([미해결 목록])
```
