---
name: e2e-test-loop
description: "E2E 테스트 → 이슈 수정 → 재테스트 반복. 모든 테스트가 통과할 때까지 루프한다. (최대 5회)"
user-invocable: true
---

## Prerequisites

e2e-test와 동일한 환경이 필요하다. 세팅 확인: `/minmo-s-harness:e2e-test --doctor`

### `--init`

`$ARGUMENTS`가 `--init`이면 `/minmo-s-harness:e2e-test --init`을 실행하고 종료한다.

### `--doctor`

`$ARGUMENTS`가 `--doctor`이면 `/minmo-s-harness:e2e-test --doctor`를 실행하고 종료한다.

---

/minmo-s-harness:e2e-test 를 실행하고, 발견된 이슈를 수정한 뒤 재테스트하는 과정을 반복해:

## 절차

1. `/minmo-s-harness:e2e-test` 를 실행한다.
2. 결과를 확인한다:
   - **이슈 없음** (모든 테스트 통과, STATUS_MISMATCH 없음) → 루프를 종료한다.
   - **이슈 발견** → 3번으로 진행한다.
3. 발견된 이슈를 수정한다:
   - 코드 수정 후 서버를 재빌드/재시작한다.
   - 수정 내용을 ��록한다.
4. iteration 카운트를 1 증가시키고 1번으로 돌아간다.
5. **최대 5회** iteration 후에는 미해결 이슈와 함께 종료한다.

## 종료 시 출력

```
E2E Test Loop 완료
- 총 iteration: N회
- 발견된 이슈: M건
- 수정된 이슈: X건
- 미해결 이슈: Y건 (있으면 목록)
```
