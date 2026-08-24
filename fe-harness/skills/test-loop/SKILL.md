---
name: test-loop
description: "단위 테스트 + E2E 테스트를 실행하고, 실패 시 수정 후 재실행을 반복한다 (최대 5회). '테스트 통과할 때까지 고쳐줘' 요청 시 사용. start-workflow 품질 루프에서 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/test-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.


# Test Loop

단위 테스트와 E2E 테스트를 실행하고, 실패 시 코드를 수정한 후 재실행한다.
최대 5회 반복하며, 모든 테스트가 통과하면 조기 종료한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 모드

| 모드 | 진입 조건 | 테스트 파일 | 소스 |
|------|----------|------------|------|
| **기본** | 아래 조건에 해당하지 않을 때 | 수정 허용 | 수정 허용 |
| **frozen** | 프롬프트에 frozen 지시가 있거나, 전달받은 상태 파일에 `## TDD Test Map` 이 존재 | **수정 금지** | 수정 허용 |

**frozen 모드**는 테스트가 구현보다 먼저 작성된 경우(TDD)에만 쓴다. 테스트를 고쳐서 통과시키면 TDD가 무력화되기 때문이다.

- 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고 `[TestConflict]` 태그로 **보고만** 한다.
- 실패를 상태 파일의 `## Test Baseline` 과 대조해 분류한다:

| # | 조건 | 분류 |
|---|------|------|
| 1 | `## TDD Test Map`에 등재된 테스트의 실패 | `new_red` |
| 2 | baseline에 동일 식별자 + **동일** 시그니처 | `pre_existing` |
| 3 | baseline에 동일 식별자 + **다른** 시그니처 | `regression` |
| 4 | baseline에 없는 식별자의 실패 | `regression` |
| 5 | 3·4 판정 전 **1회 재실행**, 결과가 뒤집히면 | `flaky` |

- 수정 우선순위: `regression` → `new_red`. **`pre_existing` 은 이번 범위 밖이므로 손대지 않는다.**
- `flaky`는 수정 대상이 아니며 보고만 한다.

> 진단 분류(`regression`·`pre_existing`·`new_red`·`flaky`)는 상태 코드가 아니라 데이터다. 결과 표의 셀 안에서만 쓴다.

---

## 플래그

| 플래그 | 효과 |
|--------|------|
| `--no-lock` | E2E 단계(Step 2)의 실행 락을 건너뛴다. 단독 실행/디버깅 전용 — 다른 에이전트와 동시에 돌면 dev 서버 포트가 충돌한다 |

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
2. **기본 모드**: 테스트 코드 또는 소스 코드를 수정한다. **frozen 모드**: 소스 코드만 수정한다.
3. `modified = true`로 설정한다.

### Step 2: E2E 테스트 실행

`e2eRunner` 가 `none` 이거나 `e2eCommand` 가 비어있으면 건너뛴다.

**실행 락**: 여러 에이전트가 동시에 E2E를 돌리면 dev 서버 포트가 충돌한다. E2E 명령을 돌리기 전에 락을 잡고, 끝나면(실패해도) 해제한다. `--no-lock` 이면 건너뛴다.

```bash
# 획득 — 이 Bash 호출은 timeout: 600000 으로 실행한다
bash ${CLAUDE_PLUGIN_ROOT}/skills/e2e-test/assets/e2e-lock.sh \
  acquire "{serverUrl}" --label "test-loop iteration {N}"
```

종료 코드 2(`TIMEOUT`)면 E2E 단계만 `SKIPPED:LOCK_TIMEOUT` 으로 기록하고 루프 판정으로 넘어간다 (유닛 테스트 결과는 유효하다).
해제는 매 iteration 의 E2E 실행 직후:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/e2e-test/assets/e2e-lock.sh release "{serverUrl}"
```

수정 단계에서는 락을 놓아 다른 에이전트가 순번을 가져갈 수 있게 한다.

profile의 `e2eCommand` 를 우선 사용:

```bash
{e2eCommand}
```

비어있으면 `e2eRunner` 값에 따라 fallback:
- **playwright**: `npx playwright test --reporter=list`
- **cypress**: `npx cypress run`

실패 시:
1. 에러 메시지를 분석한다.
2. **기본 모드**: 테스트 코드 또는 소스 코드를 수정한다. **frozen 모드**: 소스 코드만 수정한다.
3. `modified = true`로 설정한다.

### 루프 판정

- `modified == false` → 모든 테스트 통과, 루프 탈출
- `modified == true` → 수정사항 있음, 다음 iteration
- 5회 도달 → 미해결 사항 보고 후 강제 탈출

---

## 종료 시 출력

```markdown
## Test Loop 결과

- **모드**: 기본 / frozen
- **총 iteration**: N회
- **단위 테스트 수정**: M건
- **E2E 테스트 수정**: K건
- **최종 상태**: ALL PASS / UNRESOLVED ([미해결 목록])

### frozen 모드일 때 추가
- **분류**: regression [n]건 / new_red [n]건 / pre_existing [n]건(범위 밖) / flaky [n]건
- **`[TestConflict]`**: [테스트 ↔ 의심 사유, 없으면 "없음"]
```
