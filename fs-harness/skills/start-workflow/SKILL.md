---
name: start-workflow
description: "프론트엔드와 백엔드를 분리된 에이전트로 병렬 오케스트레이션한다. 기능 정의 → 통신 계약 정의 → 교차 리뷰 → 영역별 구현 → 통합 검증 → PR 순서의 애자일 풀스택 워크플로우."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명 또는 빈 값>
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fs-harness/common.md` — 플러그인 공통
- `.claude/fs-harness/skills/start-workflow.md` — 본 스킬 전용
- 또한 이 스킬이 be/fe 에이전트를 호출할 때 각 에이전트는 **자기 플러그인의 오버라이드** 를 별도 로드한다 (`.claude/be-harness/...`, `.claude/fe-harness/...`)

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Start Workflow Full Stack — Agile Orchestrator

프론트엔드와 백엔드를 하나의 큰 구현 덩어리로 취급하지 않는다.
먼저 **기능 단위와 통신 계약**을 고정하고, 그 다음 **프론트/백엔드 전용 에이전트**가 병렬로 구현한 뒤, 마지막에 통합 검증으로 닫는다.

## 언제 쓰는가

- 화면과 API가 함께 바뀌는 기능
- 요청/응답 구조, 에러 모델, 인증 방식이 같이 정리되어야 하는 작업
- 프론트와 백엔드가 서로를 기다리며 흔들리기 쉬운 작업

## 언제 쓰지 않는가

- 백엔드만 바뀌는 작업: `be-harness:start-workflow`
- 프론트엔드만 바뀌는 작업: `fe-harness:start-workflow`

## 전제 조건

- `be-harness:request`, `fe-harness:request`
- `workflow-implementer`
- `scope-reviewer`, `component-reviewer`, `a11y-reviewer`
- `workflow-reflection`
- 프론트 하네스와 백엔드 하네스가 모두 사용 가능해야 한다.

한쪽 하네스가 없으면 이 스킬로 억지로 진행하지 말고, 단일 도메인 워크플로우로 내린다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | feature 브랜치 생성과 PR 생성을 건너뛰고 현재 브랜치에서 마무리한다. |

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## Advisor / Executor 원칙

- 구현을 수정하는 에이전트는 **백엔드 구현 에이전트**와 **프론트엔드 구현 에이전트**뿐이다.
- 리뷰 에이전트는 모두 **읽기 전용 advisor**다.
- 프론트는 프론트 파일만, 백엔드는 백엔드 파일만 수정한다.
- 공용 산출물(OpenAPI, generated client, shared DTO, mock schema)은 **한 명의 owner를 Plan에서 먼저 지정**한다.
- 계약이 얼어붙은 뒤 임의로 필드/에러/인증 규칙을 바꾸지 않는다.

## 핵심 원칙

1. **Feature First**: 먼저 기능을 사용자 흐름 단위로 정의한다.
2. **Contract First**: 구현 전에 통신 규약을 먼저 확정한다.
3. **Review Before Code**: 계약과 분업 계획을 리뷰한 뒤에만 구현한다.
4. **Split By Ownership**: 프론트와 백엔드는 파일 소유권이 명확해야 한다.
5. **No Silent Contract Drift**: 계약이 바뀌면 구현을 계속하지 말고 계약 단계로 되돌아간다.

## Phase 매핑

| Phase | 담당 | 목적 |
|-------|------|------|
| 0 | 오케스트레이터 + `be-harness:request` + `fe-harness:request` | 기능 정의 및 도메인 분리 |
| 1 | 오케스트레이터 | 통신 계약 초안 작성 |
| 2 | 읽기 전용 리뷰 에이전트 2개 이상 | 계약/분업 리뷰 |
| 3 | 오케스트레이터 | 프론트/백엔드 Plan 분리 |
| 4 | 백엔드 구현 에이전트 + 프론트 구현 에이전트 | 병렬 구현 |
| 5 | 각 도메인 품질 루프 | 영역별 안정화 |
| 6 | 읽기 전용 리뷰 에이전트 | 통합 검증 |
| 7 | 오케스트레이터 + PR 스킬 | 최종 커밋/PR |
| 8 | `workflow-reflection` | 회고 및 정리 |

## Phase Agent Assignment / State Tracking

워크플로우 시작 시 `/tmp/fullstack-workflow-state.md`를 새로 만들고, Phase 진입/완료 때마다 갱신한다.
오케스트레이터도 Phase owner agent로 간주해 상태 파일에 기록한다.

상태 파일은 항상 아래 섹션을 포함한다:

```markdown
## Current Phase
[현재 Phase, 담당 agent, model, effort]

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|

## Remaining Phases
[아직 남은 Phase 목록]

## Phase Results
[완료된 Phase 결과를 append]
```

에이전트를 생성하기 전에는 해당 Phase를 `IN_PROGRESS`로 갱신하고, 완료 후 `DONE/SKIPPED/BLOCKED`와 결과를 기록한다.
모든 에이전트 프롬프트에는 상태 파일 경로, 현재 Phase, 남은 Phase, 배정된 model/effort를 포함한다.

### Model / Effort 선택 규칙

Agent 생성 시 작업 복잡도, 난이도, 작업량에 맞춰 `model`과 `effort` 또는 `reasoning_effort`를 명시한다.
환경별 모델명이 다르면 같은 등급의 사용 가능한 최신 모델로 치환한다.

| 등급 | 기준 | Claude 계열 | Codex 계열 | effort |
|------|------|-------------|------------|--------|
| Simple | 단일 도메인에 가까운 보조 작업, 문서/단순 리뷰 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 일반 FE+BE 계약/구현/검증 | sonnet | gpt-5.3-codex | medium |
| Complex | 다중 API, shared artifact, 상태/DB/권한 영향 | opus | gpt-5.4 | high |
| Critical | 대규모 계약 변경, 보안/데이터 마이그레이션, 릴리즈 위험 | opus | gpt-5.5 | xhigh |

FE/BE 구현 에이전트는 각 도메인의 작업량으로 등급을 따로 산정한다.
통합 계약 리뷰와 contract drift 판정은 기본 `Complex` 이상으로 둔다.

## 자율 실행 규칙

- Phase 0~3: 유저와 기능/계약/Plan을 합의한다.
- **Phase 3.5 이후 ~ Phase 8 완료까지**는 자동 실행한다.
- 멈춰야 하는 지점은 계약 불일치, 권한 부족, 테스트 불가, 또는 유저 승인 없이는 바꿀 수 없는 요구사항뿐이다.

## Spec 외 변경 금지 원칙

Spec 또는 계약에 없는 변경이 필요하면:

1. 코드를 먼저 바꾸지 않는다.
2. `/tmp/fullstack-workflow-state.md`의 `Assumptions` 섹션에 `[Assumption]`으로 기록한다.
3. 계약 리뷰를 다시 거친 뒤에만 반영한다.

## Phase 0: 기능 정의 + Feature Matrix

상세 명세가 이미 충분하면 그 내용을 정리해서 시작한다.
부족하면 `be-harness:request`로 백엔드 관점 질문을, `fe-harness:request`로 프론트엔드 관점 질문을 각각 수행해 아래 표를 만든다.

```markdown
## Feature Matrix
| ID | 사용자 흐름 | 프론트 책임 | 백엔드 책임 | 완료 조건 |
|----|------------|------------|------------|----------|
```

반드시 정리할 항목:

- 어떤 사용자가 어떤 화면에서 어떤 행동을 하는가
- 그 행동에 대응하는 API/이벤트/쿼리 키가 무엇인가
- 프론트의 화면 상태: loading, empty, success, error
- 백엔드의 비즈니스 규칙, 권한, 저장소 변경
- 테스트 완료 조건

이 결과가 한쪽 도메인만 필요하면 풀스택 워크플로우를 중단하고 단일 도메인 스킬로 전환한다.

## Phase 1: 통신 계약 정의

구현 전에 반드시 **Integration Contract**를 작성한다.

```markdown
## Integration Contract
### Surface
- REST / GraphQL / gRPC / Event 중 무엇인지

### Endpoint Or Event
- Method / Path / Event Name
- Auth / Role
- Query / Path / Header / Body 필드

### Success Response
- 필드명 / 타입 / nullable / 기본값

### Error Contract
- 에러 코드
- 사용자 노출 메시지 여부
- 프론트 fallback 동작

### UI State Contract
- loading / empty / disabled / retry / optimistic update

### Ownership
- Backend owner
- Frontend owner
- Shared artifact owner
```

계약에는 아래가 빠지면 안 된다:

- 인증/인가
- 페이지네이션/커서 규칙
- 날짜/금액/enum 포맷
- 정렬/필터 파라미터
- 캐시 무효화 또는 재조회 규칙
- 하위 호환성 여부

## Phase 2: 계약 리뷰

계약 초안이 나오면 읽기 전용 리뷰를 병렬로 수행한다.

### Batch 1

- 백엔드 리뷰어 역할의 advisor: 데이터 정합성, 비즈니스 규칙, 에러 모델 검토
- 프론트엔드 리뷰어 역할의 advisor: 화면 상태, 사용자 흐름, 소비 가능성 검토

### Batch 2

- 프론트가 백엔드 계약을 소비하는 데 빠진 필드가 없는지 교차 리뷰
- 백엔드가 프론트 요구를 과도하게 책임지지 않는지 교차 리뷰

리뷰 출력 형식:

```markdown
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [목록 또는 "없음"]
**Suggestions**: [목록 또는 "없음"]
**Next Action**: [오케스트레이터가 바로 수행할 1개 액션]
```

다음 중 하나라도 있으면 **REJECT**다:

- 필수 필드 정의 누락
- 성공/실패 응답 해석이 양쪽에서 다름
- 인증/권한 책임이 불명확함
- shared artifact owner가 없음
- 프론트 완료 조건과 백엔드 완료 조건이 서로 다름

## Phase 3: 분리 Plan 작성

`EnterPlanMode`를 활성화하고 아래 3개를 확정한다.

### 3.1 백엔드 Plan

- 변경 파일
- 핸들러/서비스/리포지토리 범위
- 테스트 전략
- 계약 산출물 owner 여부

### 3.2 프론트엔드 Plan

- 변경 파일
- 페이지/컴포넌트/훅 범위
- 화면 상태 처리 전략
- 타입/클라이언트 연동 전략

### 3.3 공용 Plan

- feature 브랜치 전략
- shared artifact owner
- 통합 테스트 순서
- 롤백 조건
- `[Assumption]` 목록

Plan은 아래를 지켜야 한다:

- 한 파일의 owner는 한쪽만 가진다.
- 생성 코드나 shared schema도 owner를 지정한다.
- 프론트는 계약 확정 전 mock shape를 임의로 만들지 않는다.
- 백엔드는 프론트 화면 로직을 추측해서 응답 필드를 늘리지 않는다.

### 3.4 Plan Verification Loop (Codex APPROVE까지 반복)

`ExitPlanMode` 전에 통신 계약, 백엔드 Plan, 프론트엔드 Plan, 공용 Plan에 대해 **Codex가 APPROVE할 때까지 반복되는 검증 루프**를 통과해야 한다. 반복 횟수에 상한은 없다.

#### 루프 구조

```
[Plan v1 (BE + FE + 공용 + 계약)]
   ↓
┌──────────────────────────────────────────┐
│ Iteration N                              │
│  ① Codex Plan 리뷰 (Architect 관점)      │
│  ↓                                        │
│  [판정]                                   │
│   - APPROVE  → 루프 탈출                 │
│   - CONCERN/REJECT → Plan/계약 수정      │
└──────────────────────────────────────────┘
   ↓ (CONCERN/REJECT)              ↓ (APPROVE)
[Claude가 Plan/계약 수정 → v(N+1)]    [Plan 확정 → Phase 3.5]
```

#### 종료 조건

| 조건 | 결과 |
|------|------|
| Codex `APPROVE` | **PROCEED** → 다음 Phase 실행 |
| 사용자가 명시적으로 루프 종료를 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex 사용 불가 환경 | **CODEX-UNAVAILABLE** → 사유를 상태 파일에 기록하고 진행 |

#### Iteration N 입력 (stateless 보완)

매 iteration마다 Codex에 다음을 함께 전달:
- Technical Spec
- 통신 계약 v최신
- 백엔드/프론트엔드/공용 Plan v최신
- **이전 iteration Diff 요약** (N≥2)
- **이전 iteration 기각 피드백 + 사유** (N≥2)

리뷰 관점:
- 계약과 양쪽 Plan의 추적 가능성
- 파일 소유권 충돌
- shared artifact owner 명확성
- 프론트/백엔드 책임 전가 여부
- 통합 테스트 및 롤백 조건 누락
- 더 단순한 구현 경로

#### 판정 처리

| Codex Verdict | 처리 |
|---------------|------|
| `APPROVE` | 루프 탈출 → `ExitPlanMode`로 Plan 확정 |
| `CONCERN` | Claude가 타당한 항목 반영 (또는 사유 기록 후 기각) → 다음 iteration |
| `REJECT` | Claude가 Plan/계약 수정 → 다음 iteration |

#### Iteration Diff Log

매 iteration 종료 시 상태 파일 `Plan Verification Log`에 append:

```markdown
### Iteration N → N+1
- **Codex Verdict**: APPROVE / CONCERN / REJECT
- **반영**: [수용 피드백 요약]
- **기각**: [기각 피드백 + 사유]
- **변경 요약**: [Plan/계약 vN → v(N+1) 핵심 diff]
```

#### 데드락 / 안전장치

- **동일 이슈 3회 반복 지적**: 사용자에게 보고하고 판단 위임. 응답 후 루프 재개/종료.
- **실질적 진전 확인**: Diff Log에 실제 변경이 0건이면 즉시 중단하고 사용자에게 보고.
- **컨텍스트 누적**: 이전 iteration 컨텍스트를 매번 명시 전달.

루프가 종료되면 `ExitPlanMode`로 Plan을 확정하고, 상태 파일에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 3.5: 브랜치 + 상태 파일

`--hard`가 아니면 feature 브랜치를 만든다.

```bash
git checkout -b feat/{작업-요약-kebab-case}
```

그다음 `/tmp/fullstack-workflow-state.md`를 작성한다:

```markdown
# Fullstack Workflow State

## Spec
[합쳐진 Technical Spec]

## Feature Matrix
[Phase 0 결과]

## Integration Contract
[Phase 1 결과]

## Current Phase
Phase 3.5 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 0 | orchestrator + be/fe request | 현재 세션 | 현재 세션 | DONE |
| 1 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 2 | contract review agents | 계약 복잡도 기준 | 계약 복잡도 기준 | DONE |
| 3 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3.5 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 4 | BE workflow-implementer + FE workflow-implementer | 도메인별 기준 | 도메인별 기준 | PENDING |
| 5 | BE/FE quality agents | 도메인별 기준 | 도메인별 기준 | PENDING |
| 6 | integration review agents | 계약 복잡도 기준 | 계약 복잡도 기준 | PENDING |
| 7 | orchestrator + PR skill | PR 복잡도 기준 | PR 복잡도 기준 | PENDING |
| 8 | workflow-reflection | 변경량 기준 | 변경량 기준 | PENDING |

## Remaining Phases
- Phase 4: 프론트/백엔드 병렬 구현
- Phase 5: 도메인별 품질 루프
- Phase 6: 통합 검증
- Phase 7: 커밋/PR
- Phase 8: 회고 + 정리

## Backend Plan
[Phase 3.1]

## Frontend Plan
[Phase 3.2]

## Shared Ownership
[공용 산출물 owner]

## Assumptions
[없으면 "없음"]

## Phase Results
[Phase 완료 시 결과 append]
```

## Phase 4: 프론트/백엔드 병렬 구현

두 구현 에이전트를 **같은 메시지 내에서 병렬 호출**한다.

### 백엔드 구현 에이전트

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [백엔드 작업량 기준 선택]
  effort: [백엔드 작업량 기준 선택]
  prompt: |
    상태 파일 `/tmp/fullstack-workflow-state.md`를 읽고, **Backend Plan** 섹션만 구현하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 4 Backend
    남은 Phase: Phase 5, 6, 7, 8
    배정 model/effort: {model}/{effort}
    profile: .claude/be-harness.local.md 를 읽어 빌드/커밋 명령을 결정하세요.
    금지: Frontend Plan 파일 수정, 계약 외 필드 추가.
    보고: 변경 파일, 계약 차이점, [Assumption] 목록, 막힌 계약 항목.
```

### 프론트엔드 구현 에이전트

```
Agent tool:
  subagent_type: fe-harness:workflow-implementer
  model: [프론트엔드 작업량 기준 선택]
  effort: [프론트엔드 작업량 기준 선택]
  prompt: |
    상태 파일 `/tmp/fullstack-workflow-state.md`를 읽고, **Frontend Plan** 섹션만 구현하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 4 Frontend
    남은 Phase: Phase 5, 6, 7, 8
    배정 model/effort: {model}/{effort}
    profile: .claude/fe-harness.local.md 를 읽어 빌드/커밋 명령을 결정하세요.
    금지: Backend Plan 파일 수정, 계약 외 필드 가정.
    보고: 변경 파일, 계약 차이점, [Assumption] 목록, 막힌 계약 항목.
```

두 에이전트 모두 보고해야 할 것:

- 변경 파일 목록
- 계약 대비 차이점
- `[Assumption]` 목록
- 막힌 계약 항목

구현 중 계약 변경이 필요하면 즉시 Phase 1로 돌아간다.

## Phase 5: 도메인별 품질 루프

Phase 5 시작 전 `/tmp/fullstack-workflow-state.md`의 `Current Phase`, `Phase Assignments`, `Remaining Phases`를 갱신한다.
각 도메인 루프에서 서브 에이전트를 생성할 때는 도메인별 실패 심각도에 맞는 `model`과 `effort`를 명시한다.

### 백엔드 루프

1. `be-harness:simplify-loop`
2. `be-harness:convention-check`
3. `be-harness:e2e-test-loop`
4. API 계약이 바뀌었고 `apiDocsPath` 가 지정되어 있으면 Phase 6 문서 동기화 단계로 위임

### 프론트엔드 루프

1. build + type-check
2. `fe-harness:simplify-loop`
3. `fe-harness:convention-check`
4. `fe-harness:test-loop`
5. `fe-harness:lint-check`

규칙:

- 각 도메인은 자기 루프만 다시 돈다.
- 한쪽 루프 결과가 계약을 흔들면 둘 다 멈추고 Phase 1로 복귀한다.
- 최대 3회까지 반복한다.

## Phase 6: 통합 검증

구현이 끝나면 frozen contract와 실제 코드를 다시 맞춘다.

반드시 검증할 항목:

- Method / Path / Event Name
- Request / Response 필드명과 타입
- 에러 코드와 프론트 fallback
- loading / empty / retry / disabled 상태
- 인증/권한
- 페이지네이션/커서
- 캐시 무효화 또는 재조회

권장 리뷰 조합:

- 백엔드 `scope-reviewer`
- 프론트엔드 `scope-reviewer`
- UI 변경이 있으면 `component-reviewer`
- 접근성 영향이 있으면 `a11y-reviewer`

통합 검증 agent는 모두 `/tmp/fullstack-workflow-state.md`를 읽고 현재 Phase, 남은 Phase, 배정된 model/effort를 보고서에 기록한다.
계약 불일치 가능성이 있으면 `Complex` 이상 model/effort로 생성한다.

해결되지 않은 contract diff가 하나라도 남아 있으면 PR 단계로 가지 않는다.

## Phase 7: 커밋/PR

둘 다 green이면 단일 PR로 묶는다.

- 커밋은 프론트/백엔드 단위를 분리한다.
- PR 생성은 현재 하네스의 PR 스킬을 사용한다.
- PR/커밋 agent를 생성하는 경우 `/tmp/fullstack-workflow-state.md`를 읽고 Phase 7 상태를 갱신하며, PR 복잡도에 맞는 model/effort를 명시한다.
- PR 본문은 아래 순서를 따른다:

```markdown
## Feature Summary
## Integration Contract
## Backend Changes
## Frontend Changes
## Verification
## Assumptions
```

`--hard`면 push/PR 단계를 생략하고 현재 브랜치에서 종료한다.

## Phase 8: 회고 + 정리

- `workflow-reflection`으로 회고를 남긴다. agent 생성 시 변경량에 맞는 model/effort를 명시하고 `/tmp/fullstack-workflow-state.md`의 Phase 8 상태를 갱신한다.
- 회고에서 도출된 보완점은 **대상 도메인별로** 분류한다:
  - 백엔드 스킬/에이전트 대상 → `.claude/be-harness/...`
  - 프론트엔드 스킬/에이전트 대상 → `.claude/fe-harness/...`
  - 풀스택 워크플로우 자체(계약, Feature Matrix 등) → `.claude/fs-harness/...`
- 플러그인 원본은 **수정하지 않는다**. 상세 규약: 각 플러그인의 `OVERRIDES.md`.

### 보완점 반영 방식 선택

> "보완점 반영 방식을 선택하세요:"
>
> 1. **로컬에만 저장** (기본값) — 각 도메인의 로컬 오버라이드 파일에 append.
> 2. **로컬 저장 + 플러그인 레포 PR** — 도메인별 `submit-feedback` 을 호출하여 community-feedback 영역에 PR.
> 3. **건너뛰기**.

#### 옵션 2 세부 흐름

1. 로컬 저장 먼저 수행 (모든 도메인).
2. 도메인별로 PR 후보를 분리:
   - BE 후보 → `/be-harness:submit-feedback`
   - FE 후보 → `/fe-harness:submit-feedback`
   - FS 후보(풀스택 계약 관련) → `/fs-harness:submit-feedback`
3. 각 submit-feedback 은 독립적으로 동작. 한쪽이 `[SKIPPED:*]` 나 FAILED 여도 다른 쪽은 계속 진행.
4. 각 PR URL 과 SKIP 사유를 모두 수집해 최종 보고서에 병기.

### 정리

- `/tmp/fullstack-workflow-state.md`의 모든 Phase를 `DONE/SKIPPED`으로 갱신하고 `Remaining Phases`를 `없음`으로 기록한다.
- 기본은 상태 파일을 보관한다. 사용자가 정리를 요청했거나 보관이 필요 없을 때만 삭제한다.

```bash
rm -f /tmp/fullstack-workflow-state.md
```

최종 보고는 아래 형식을 따른다:

```markdown
## 📋 Task Report: [작업명]

### 1. Pre-Review (Plan)
- Codex Feedback: ...
- Claude Feedback: ...
- Refinement: ...

### 2. Implementation Details
- Assumptions: ...
- Key Changes: ...

### 3. Final Convention Review
- Layer Analysis: ...
- Simplicity Check: ...

### 4. Status
- Verification: ...
- Cleanup: ...
```

Claude 또는 Codex 교차 리뷰를 실제로 수행할 수 없는 환경이면 그 사실을 적고, 누락을 숨기지 않는다.
