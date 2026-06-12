> 이 문서는 `start-workflow` 스킬의 Phase 8(품질 루프)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# Phase 8: 품질 루프 상세 (병렬 스캔 → 통합 수정 → 순차 실행)

루프 구조·상한·판정은 SKILL.md 본문이 canonical이다. 이 문서는 각 단계의 실행 상세와 에이전트 프롬프트를 정의한다.

## Batch A: 병렬 스캔 (Phase 8.1 ~ 8.4)

네 단계를 **하나의 메시지에서 동시에 호출**한다. 모든 서브 에이전트는 **이슈 목록만 반환하며 파일을 수정하지 않는다**.
파일 수정은 Phase 8.5(통합 수정)에서 일괄 처리하여 에이전트 간 파일 편집 경합을 제거한다.

> **CRITICAL**: Batch A의 에이전트는 모두 읽기/분석만 수행한다. 같은 메시지에서 병렬 실행해도 편집 충돌이 발생하지 않는다.
> 만약 에이전트가 파일을 수정했다면 해당 변경을 **무시**하고 이슈 목록만 채택한다 (통합 수정 시 기준 상태에서 다시 편집).

### Phase 8.1: 빌드 + 테스트 — Bash로 직접 실행 (에이전트 아님)

```bash
{buildCommand} && {testCommand} 2>&1
```

둘 중 하나라도 비어있으면 해당 단계 SKIP. 에러 로그를 Batch A 결과에 수집한다. 파일 수정 없음.

### Phase 8.2: Simplify Scan

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 스캔 범위 기준 선택]
  effort: [품질 스캔 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /be-harness:simplify-loop 를 **dry-run** 관점으로 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.2 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    **파일을 수정하지 말고** 단순화 후보 목록만 반환하세요.
    각 항목: {file:line, 현재 코드 요약, 제안 변경, 근거}.
    완료 후 "후보: N건" 형식으로 보고하세요.
```

### Phase 8.3: Convention Check Scan

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 스캔 범위 기준 선택]
  effort: [품질 스캔 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /be-harness:convention-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    **파일을 수정하지 말고** 위반 목록만 반환하세요.
    각 항목: {file:line, 위반 규칙, 제안 수정}.
    완료 후 "위반: N건" 형식으로 보고하세요.
```

### Phase 8.4: Scope Review

```
Agent tool:
  subagent_type: be-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요. 프로젝트 루트: {CWD}.
    현재 Phase: Phase 8.4
    남은 Phase: Phase 8.5~8.7, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}
    누락/불일치 항목만 반환하고 파일은 수정하지 마세요.
```

## Phase 8.5: 통합 수정

Batch A에서 수집된 이슈(빌드/테스트 에러 + simplify 후보 + convention 위반 + scope 누락)가 하나라도 있으면, **단일 `general-purpose` 에이전트**에 일괄 위임한다. 이슈가 없으면 이 단계를 건너뛴다.

```
Agent tool:
  subagent_type: general-purpose
  model: [수정 이슈 심각도 기준 선택]
  effort: [수정 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 이슈 목록을 순서대로 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.5 상태를 갱신하세요.
    남은 Phase: Phase 8.6, 8.7, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}

    ## 이슈 목록
    ### 빌드/테스트 에러 (최우선)
    {build / test 로그}

    ### Scope 누락
    {scope-reviewer 보고서}

    ### Convention 위반
    {convention-check 보고서}

    ### Simplify 후보
    {simplify 후보 목록 — 안전한 변경만 적용, 의심스러우면 생략}

    같은 파일에 여러 이슈가 있으면 한 번의 편집으로 합쳐 처리하세요.
    수정 후 `{buildCommand}` 로 빌드가 통과하는지 확인하세요 (buildCommand가 비어있으면 이 체크는 생략).
    완료 후 "수정: N건, 파일: [목록]" 형식으로 보고하세요.
```

수정 발생 시 `modified = true`.

## Batch B: 순차 실행 (Phase 8.6 → 8.7)

서버/테스트 프로세스가 포트·DB·바이너리를 점유하므로 순차로 실행한다.

### Phase 8.6: E2E Test

```
Agent tool:
  subagent_type: general-purpose
  model: [E2E 범위/실패 심각도 기준 선택]
  effort: [E2E 범위/실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /be-harness:e2e-test-loop 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8.6 상태를 갱신하세요.
    남은 Phase: Phase 8.7, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}
    결과가 `SKIPPED:*`이면 스킵 사유를 그대로 보고하세요.
    완료 후 "이슈: N건, 수정: Y/N, 스킵 사유: {있으면}" 형식으로 보고하세요.
```

- `SKIPPED:*` 반환 시 → `modified`에 영향 주지 않고 다음 단계 진행 (루프 재시작 트리거 아님)
- "수정: Y" → `modified = true`

### Phase 8.7: 통합 테스트 (조건부)

profile의 `{makeTestCommand}`가 비어있지 않으면 Bash로 직접 실행:

```bash
{makeTestCommand}
```

비어있으면 `SKIPPED:PROFILE_EMPTY`로 기록하고 넘어간다.
실패 시 `general-purpose` 에이전트로 수정 위임 (Phase 8.5 프롬프트 형식 재사용, 이슈 목록 = 통합 테스트 실패 로그). 수정 발생 시 `modified = true`.
