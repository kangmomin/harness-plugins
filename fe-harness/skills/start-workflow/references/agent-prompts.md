> 이 문서는 `start-workflow` 스킬의 Phase 5(구현), 6(빌드/타입 체크), 7(품질 루프), 8(리뷰), 9(PR), 10(성찰)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 서브 에이전트 프롬프트 모음

## Phase 5: 구현 (workflow-implementer)

```
Agent tool:
  subagent_type: fe-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 5
    남은 Phase: Phase 6, 7, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    [커밋 단위 규칙]
    컴포넌트 1개 = 커밋 1개를 원칙으로 합니다.
    관련 없는 컴포넌트 변경을 하나의 커밋에 묶지 마세요.

    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

완료 후 유저에게 간략 보고: "Phase 5 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

## Phase 6: 빌드 실패 수정 에이전트

빌드/타입 체크 실패 시에만 호출한다.

```
Agent tool:
  subagent_type: general-purpose
  model: [빌드 실패 심각도 기준 선택]
  effort: [빌드 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 `{buildCommand}` / `{typeCheckCommand}` 에러를 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 6 상태를 갱신하세요.
    남은 Phase: Phase 7, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}
    에러 메시지: {빌드 에러 출력}
    수정 후 빌드가 성공하는지 확인하세요.
```

수정 후 커밋: `git add [수정 파일들] && git commit -m "Fix: 빌드 에러 수정 (Phase 6)"`

## Phase 7: 품질 루프 단계별 프롬프트

### Phase 7.2: Simplify

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:simplify-loop 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.2 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    완료 후 "수정: Y/N, N건" 형식으로 보고하세요.
```

### Phase 7.3: Convention Check

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:convention-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    위반 사항이 있으면 수정하세요.
    완료 후 "위반: N건, 수정: Y/N" 형식으로 보고하세요.
```

### Phase 7.4: Test Loop

```
Agent tool:
  subagent_type: general-purpose
  model: [테스트 실패 심각도 기준 선택]
  effort: [테스트 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:test-loop 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.4 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

### Phase 7.5: Scope Review

```
Agent tool:
  subagent_type: fe-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 7.5
    남은 Phase: Phase 7.6, 8, 9, 10, 11
    배정 model/effort: {model}/{effort}
```

### Phase 7.6: Lint Check

```
Agent tool:
  subagent_type: general-purpose
  model: [lint 이슈 심각도 기준 선택]
  effort: [lint 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:lint-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7.6 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    이슈가 있으면 수정하세요.
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

## Phase 8: 컴포넌트/접근성 리뷰 (병렬 2개)

```
Agent tool (병렬 1):
  subagent_type: fe-harness:component-reviewer
  model: [컴포넌트 변경량 기준 선택]
  effort: [컴포넌트 변경량 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8 component review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}

Agent tool (병렬 2):
  subagent_type: fe-harness:a11y-reviewer
  model: [접근성 영향 기준 선택]
  effort: [접근성 영향 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8 a11y review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
```

Critical 이슈가 있으면 general-purpose 에이전트로 수정을 위임한다.

## Phase 9: PR 생성 (workflow-pr)

```
Agent tool:
  subagent_type: fe-harness:workflow-pr
  model: [PR 복잡도 기준 선택]
  effort: [PR 복잡도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 PR을 생성하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 9
    남은 Phase: Phase 10, 11
    배정 model/effort: {model}/{effort}
    PR URL을 반드시 보고하세요.
```

## Phase 10: 성찰 (workflow-reflection)

```
Agent tool:
  subagent_type: fe-harness:workflow-reflection
  model: [워크플로우 변경량 기준 선택]
  effort: [워크플로우 변경량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 10
    남은 Phase: Phase 11
    배정 model/effort: {model}/{effort}
    성찰 결과와 스킬 보완점을 보고하세요.
```
