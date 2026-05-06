---
name: start-workflow
description: "전체 프론트엔드 개발 워크플로우를 자동화. 요청 분석 → 난이도 산정 → Plan 리뷰 → 구현 → 품질 루프 → 컴포넌트/접근성 리뷰 → PR → 성찰까지 일관된 파이프라인으로 실행한다."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명 또는 빈 값>
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/start-workflow.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Start Workflow — Orchestrator

전체 프론트엔드 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. PR 생략. |

`$ARGUMENTS`에 `--hard` 또는 `-h`가 포함되어 있으면 `$HARD_MODE = true`로 설정한다.

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 3.5 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 4 커밋 | 동일 | 동일 |
| Phase 7 PR | workflow-pr (브랜치 생성 + PR) | **현재 브랜치에서 바로 push, PR 생략** |

---

```
[유저 대화] Phase 0~3  : 직접 실행 (Spec, Plan, 리뷰)
[상태 저장] Phase 3.5  : 상태 파일 생성
[자율 실행] Phase 4~8  : 서브 에이전트 순차 위임
[유저 대화] Phase 9    : 최종 보고 + 보완점 적용
```

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## Phase Agent Assignment / State Tracking

워크플로우 시작 시 `/tmp/workflow-state.md`를 새로 만들고, Phase 진입/완료 때마다 갱신한다.
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
| Simple | 난이도 1-3, 1-3개 파일, 문서/단순 UI 수정 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 난이도 4-6, 일반 컴포넌트/API 연동/테스트 수정 | sonnet | gpt-5.3-codex | medium |
| Complex | 난이도 7-8, 다중 화면/상태/API/a11y 영향 | opus | gpt-5.4 | high |
| Critical | 난이도 9-10, 대규모 리팩토링/복잡 상태/릴리즈 위험 | opus | gpt-5.5 | xhigh |

읽기 전용 리뷰는 기본 `Standard`로 시작하되, 접근성/상태 정합성/계약 변경 검토는 `Complex` 이상으로 올린다.
코드 수정 에이전트는 담당 파일 수와 실패 반복 횟수에 따라 한 단계 높일 수 있다.

### Build Mode 기본 Phase 할당

| Phase | 담당 agent | 기본 model/effort |
|-------|------------|-------------------|
| 0-3 | orchestrator + review agents | 난이도 기준 |
| 3.5 | orchestrator | 현재 세션 설정 |
| 4 | workflow-implementer | 난이도 기준 |
| 4.5 | orchestrator build/typecheck, 실패 시 build-fix agent | Standard, 반복 실패 시 Complex |
| 5 | simplify/convention/test/scope/lint agents | Standard, 결함 심각도에 따라 Complex |
| 6 | component-reviewer + a11y-reviewer | Standard/Complex |
| 7 | workflow-pr 또는 hard push | Simple/Standard |
| 8 | workflow-reflection | Standard |
| 9 | orchestrator | 현재 세션 설정 |

## 자율 실행 규칙

- Phase 0~3: 유저와 대화하며 Spec 확인, Plan 리뷰 피드백 반영
- **Phase 3.5 이후 ~ Phase 8 완료까지**: 서브 에이전트를 순차 호출하며 **묻지 않고 자동 실행**
- Phase 9: 최종 보고에서 보완점 반영 여부만 유저에게 질문

### Spec 외 변경 금지 원칙

자율 실행 중 Spec에 명시되지 않은 동작 변경이 필요하다고 판단되면:
1. **코드를 수정하지 않고** 해당 사항을 기록한다.
2. Phase 9 보고서에 `[Assumption]` 태그로 표기하여 유저에게 가시화한다.
3. 유저 승인 후에만 해당 변경을 적용한다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- **유저 응답을 기다리거나, 진행 여부를 묻거나, 중간 보고 후 멈추는 것은 금지**
- 유일한 정지 지점은 **Phase 9 (최종 보고)** 뿐이다

---

## Phase 0: 작업 범위 수집 (Plan 모드 진입)

> **Plan 모드 활성화**: Phase 0 시작 시 `EnterPlanMode`를 활성화한다.
> Spec과 Plan은 같은 Plan 모드 컨텍스트에서 통합 산출물로 발전하며, `ExitPlanMode`는 Phase 3.4에서 단 한 번만 호출한다.
> Spec/Plan 검토는 Phase 3.3 검증 루프에서 **Spec+Plan 통합 산출물**에 대해 단일 Codex APPROVE 루프로 수행한다(별도 Codex Spec 리뷰 단계는 두지 않는다).

### 분기: 이미 상세 Spec이 제공된 경우

`$ARGUMENTS` 또는 대화 컨텍스트에 다음 조건을 **모두** 충족하는 상세 설명이 이미 포함되어 있으면 `/request` 호출을 **생략**한다:
- 작업 유형이 명확 (화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정)
- 대상 컴포넌트/페이지/API가 특정됨
- 핵심 요구사항이 구체적으로 기술됨

이 경우, 제공된 내용을 Technical Spec으로 직접 정리하고 유저 확인을 받는다.

### 기본: /request 호출

위 조건을 충족하지 않으면 `/fe-harness:request`를 호출하여 Technical Spec을 생성한다.

---

## Phase 1: 난이도 산정

Technical Spec을 분석하여 1~10 난이도를 산정한다.

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 컴포넌트 수 | 1개 | 2-3개 | 4개+ |
| 상태 복잡도 | useState 단순 | 여러 상태 조합 | 전역 상태 + 서버 상태 |
| API 연동 | 없음 | 기존 API | 새 API 연동 |
| 반응형/a11y | 기본 | 반응형 필수 | 반응형 + 접근성 + 애니메이션 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

출력: `난이도: [N]/10 — [근거]`

> 난이도 7+: Phase 3에서 Codex 리뷰 추가.

---

## Phase 2: Scope Reviewer 준비

Phase 5에서 사용할 scope-reviewer 정보를 메모한다:
- Technical Spec 전문
- 엣지 케이스 목록

---

## Phase 3: Plan 작성 + 리뷰

### 3.1 Plan 작성

Plan 모드는 Phase 0에서 이미 활성화되어 있다. Spec을 그대로 두고 그 아래에 구현 계획을 추가하여 **Spec+Plan 단일 산출물**로 발전시킨다. Plan에 포함할 내용:
- 구현 순서 (파일 단위)
- 각 파일 변경 내용 요약
- **최종 코드 구조**: 컴포넌트 분리, 훅 추출, 상태 설계를 Plan 단계에서 확정한다.
- 의존 관계
- 예상 리스크

### 3.2 다관점 Plan 보강 (Claude, 1회)

**목적**: Plan v1을 검증 루프에 진입시키기 전, Claude 측 다관점 리뷰로 명백한 결함을 1회 보강한다.
**이 단계는 검증 루프가 아니다.** 다관점 피드백을 반영해 Plan v1을 정제한 뒤 곧바로 3.3 검증 루프로 진입한다.

**최대 3개 서브에이전트 병렬 실행**, 2배치로 진행:

```
Batch 1 (병렬): 유지보수성 + 성능 + 엣지 케이스
Batch 2 (병렬): 상태 정합성 + 접근성 + 기존 코드 영향
```

각 에이전트(subagent_type: `general-purpose`) 프롬프트:

```
model: [Plan 난이도 기준 선택]
effort: [Plan 난이도 기준 선택]

당신은 [관점명] 리뷰어입니다.
아래 Plan을 [관점] 관점에서만 리뷰하세요.
상태 파일 `/tmp/workflow-state.md`의 Phase 3 상태와 남은 Phase를 참고하세요.
배정 model/effort: {model}/{effort}

## Technical Spec
[Spec 전문]

## Plan
[Plan 전문]

## 리뷰 형식
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [문제 목록 또는 "없음"]
**Suggestions**: [개선 제안 또는 "없음"]
```

리뷰 종합:
- **REJECT 1개+**: 해당 관점 이슈를 Plan에 반영해 수정.
- **CONCERN**: 타당한 항목만 자동 반영.

→ 보강된 Plan을 **Plan v1 (검증 루프 입력)**으로 확정하고 3.3로 진입한다.

### 3.3 Plan Verification Loop (Codex APPROVE까지 반복)

**Plan은 Codex가 APPROVE할 때까지 반복되는 검증 루프를 통과해야 확정된다.** 반복 횟수에 상한은 없다.

#### 루프 구조

```
[Plan v1] (3.2 다관점 보강 결과)
   ↓
┌──────────────────────────────────────────┐
│ Iteration N                              │
│  ① Codex Plan 리뷰 (Architect 관점)      │
│  ↓                                        │
│  [판정]                                   │
│   - APPROVE  → 루프 탈출                 │
│   - CONCERN/REJECT → Plan 수정           │
└──────────────────────────────────────────┘
   ↓ (CONCERN/REJECT)        ↓ (APPROVE)
[Claude가 Plan 수정 → v(N+1)]   [3.4 Plan 확정 → Phase 3.5]
```

#### 종료 조건

| 조건 | 결과 |
|------|------|
| Codex `APPROVE` | **PROCEED** → 다음 Phase 실행 |
| 사용자가 명시적으로 루프 종료를 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex 사용 불가 환경 | **CODEX-UNAVAILABLE** → 사유를 상태 파일에 기록하고 진행 |

> CONCERN/REJECT 자체는 종료 조건이 아니다. APPROVE를 받을 때까지 반복한다.

#### Iteration N 절차

**① Codex 리뷰 호출** — Architect 관점. 매 iteration마다 다음을 입력으로 전달(stateless 보완):

- Technical Spec 전문
- 현재 Plan vN 전문
- 실행 전략(sequential / parallel-slices)
- 난이도 및 리스크 산정 근거
- **이전 iteration Diff 요약** (N≥2)
- **이전 iteration 기각 피드백 + 사유** (N≥2)

리뷰 관점:
- Spec과 Plan의 추적 가능성
- 레이어별 책임 분리
- 컴포넌트/훅 책임 경계 및 상태 정합성
- 테스트/검증 누락
- 더 단순한 구현 경로

**② 판정 처리**

| Codex Verdict | 처리 |
|---------------|------|
| `APPROVE` | 루프 탈출 → 3.4 Plan 확정 |
| `CONCERN` | Claude가 타당한 항목을 Plan에 반영 (또는 사유 기록 후 기각) → 다음 iteration |
| `REJECT` | Claude가 Plan을 수정 → 다음 iteration |

**③ Iteration Diff Log 기록** — 매 iteration 종료 시 상태 파일 `Plan Verification Log`에 append:

```markdown
### Iteration N → N+1
- **Codex Verdict**: APPROVE / CONCERN / REJECT
- **반영**: [수용한 Codex 피드백 요약]
- **기각**: [기각한 피드백 + 사유]
- **Plan 변경 요약**: [vN → v(N+1) 핵심 diff]
```

#### 데드락 / 안전장치

- **동일 이슈 3회 반복 지적**: 사용자에게 보고하고 판단 위임. 응답 후 루프 재개/종료.
- **실질적 진전 확인**: Diff Log에 실제 Plan 변경이 0건인 iteration 발생 시 즉시 중단하고 사용자에게 보고.
- **컨텍스트 누적**: Codex는 stateless이므로 매 호출마다 이전 라운드 Diff/기각 사유를 명시 전달.

### 3.4 Plan 확정

루프 종료(`PROCEED` / `USER-INTERRUPTED` / `CODEX-UNAVAILABLE`) 후 `ExitPlanMode` 실행.
상태 파일 하단에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

---

## Phase 3.5: Feature 브랜치 생성 + 상태 파일 생성 + 자율 실행 시작

### 브랜치 생성

- **`$HARD_MODE = false`** (일반): 구현 시작 전 반드시 feature 브랜치를 생성한다. main/master에 직접 커밋하지 않는다.
- **`$HARD_MODE = true`** (`--hard`): 브랜치 생성을 **건너뛴다**. 현재 브랜치가 무엇이든 그대로 사용한다.

```bash
# 일반 모드: 현재 브랜치가 main/master/dev면 반드시 새 브랜치 생성
git checkout -b feat/{작업 요약 kebab-case}
```

이미 feature 브랜치(`feat/**`, `hotfix/**`)에 있으면 건너뛴다.

### 상태 파일 생성

Write tool로 `/tmp/workflow-state.md`를 생성한다:

```markdown
# Workflow State

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]

## Difficulty
[N]/10

## Current Phase
Phase 3.5 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 0 | orchestrator/request | 현재 세션 | 현재 세션 | DONE |
| 1 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | review agents + orchestrator | 난이도 기준 | 난이도 기준 | DONE |
| 3.5 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 4 | workflow-implementer | 난이도 기준 | 난이도 기준 | PENDING |
| 4.5 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 5 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 6 | component-reviewer/a11y-reviewer | 난이도 기준 | 난이도 기준 | PENDING |
| 7 | workflow-pr/hard push | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 4: 구현
- Phase 4.5: 빌드/타입 체크
- Phase 5: 품질 루프
- Phase 6: 컴포넌트/접근성 리뷰
- Phase 7: PR / Push
- Phase 8: 성찰
- Phase 9: 최종 보고

## Edge Cases
[엣지 케이스 목록]

## Plan
[확정된 Plan 전문 그대로 복사]

## Config
[.claude/fe-harness.local.md 주요 설정]

## Phase Results
[Phase 완료 시 결과 append]
```

출력: **"자율 실행을 시작합니다. Phase 4~8을 서브 에이전트로 순차 실행합니다."**

---

## Phase 4~8: 서브 에이전트 순차 실행

**각 Phase를 전용 서브 에이전트에 위임한다.**
각 Phase 시작 직전 `/tmp/workflow-state.md`의 `Current Phase`, `Phase Assignments.Status`, `Remaining Phases`를 갱신한다.
Agent tool 호출에는 선택된 `model`과 `effort`를 함께 지정한다.

### Phase 4: 구현

```
Agent tool:
  subagent_type: fe-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 4
    남은 Phase: Phase 4.5, 5, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}
    
    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.
    
    [커밋 단위 규칙]
    컴포넌트 1개 = 커밋 1개를 원칙으로 합니다.
    관련 없는 컴포넌트 변경을 하나의 커밋에 묶지 마세요.
    
    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

### Phase 4.5: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

구현 에이전트 완료 즉시, 품질 루프 진입 전에 **반드시 빌드 + 타입 체크를 실행**한다.
컴파일 오류(미사용 변수, import 누락, 타입 에러, 무한 루프 등)를 조기에 잡아 핫픽스를 방지한다.

profile(`.claude/fe-harness.local.md`)의 명령을 사용:

```bash
{buildCommand} 2>&1 | tail -30
{typeCheckCommand} 2>&1 | tail -30
```

각 명령이 비어있으면 해당 단계를 `SKIPPED`로 기록하고 Phase 5로 진행한다.

- **성공** → Phase 5로 진행.
- **실패** → general-purpose 에이전트를 생성하여 빌드 에러를 수정한다:
  ```
  Agent tool:
    subagent_type: general-purpose
    model: [빌드 실패 심각도 기준 선택]
    effort: [빌드 실패 심각도 기준 선택]
    prompt: |
      프로젝트 루트 {CWD}에서 `{buildCommand}` / `{typeCheckCommand}` 에러를 수정하세요.
      상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 4.5 상태를 갱신하세요.
      남은 Phase: Phase 5, 6, 7, 8, 9
      배정 model/effort: {model}/{effort}
      에러 메시지: {빌드 에러 출력}
      수정 후 빌드가 성공하는지 확인하세요.
  ```
  수정 후 커밋:
  ```bash
  git add [수정 파일들]
  git commit -m "Fix: 빌드 에러 수정 (단계 4.5)"
  ```
  빌드 재시도 → 성공하면 Phase 5로 진행. **최대 3회 시도** 후에도 실패하면 유저에게 보고하고 중단.

### Phase 5: 품질 루프 (오케스트레이터 직접 관리)

최대 3회 반복.

```
for iteration in 1..3:
  5.0 build + type-check      → Bash 직접 실행
  5.1 simplify-loop           → 서브 에이전트 (general-purpose)
  5.2 convention-check        → 서브 에이전트 (general-purpose)
  5.3 test-loop               → 서브 에이전트 (general-purpose)
  5.4 scope-reviewer          → 서브 에이전트 (scope-reviewer)
  5.5 lint-check              → 서브 에이전트 (general-purpose)

  수정 있음? → 커밋 후 다음 iteration
  수정 없음? → 루프 탈출
```

#### 5.0 Build + Type Check

Bash로 직접 실행. profile의 명령을 사용:

```bash
{buildCommand} && {typeCheckCommand}
```

각 명령이 비어있으면 해당 단계 `SKIPPED`. 실패 시 general-purpose 에이전트를 생성하여 에러 수정을 위임한다.

#### 5.1 Simplify

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:simplify-loop 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.1 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    완료 후 "수정: Y/N, N건" 형식으로 보고하세요.
```

#### 5.2 Convention Check

```
Agent tool:
  subagent_type: general-purpose
  model: [품질 수정 범위 기준 선택]
  effort: [품질 수정 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:convention-check 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.2 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    위반 사항이 있으면 수정하세요.
    완료 후 "위반: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 5.3 Test Loop

```
Agent tool:
  subagent_type: general-purpose
  model: [테스트 실패 심각도 기준 선택]
  effort: [테스트 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:test-loop 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 5.4 Scope Review

```
Agent tool:
  subagent_type: fe-harness:scope-reviewer
  model: [리뷰 범위 기준 선택]
  effort: [리뷰 범위 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 5.4
    남은 Phase: Phase 5.5, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}
```

#### 5.5 Lint Check

```
Agent tool:
  subagent_type: general-purpose
  model: [lint 이슈 심각도 기준 선택]
  effort: [lint 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /fe-harness:lint-check 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.5 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    이슈가 있으면 수정하세요.
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 루프 판정

- `modified == true` → 변경사항 커밋 후 루프 재시작
- `modified == false` → 루프 탈출
- 3회 도달 → 미해결 사항 보고 후 강제 탈출

### Phase 6: 컴포넌트/접근성 리뷰 (조건부)

**작업 유형이 화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정인 경우만 실행. API 연동 유형은 건너뛴다.**

두 에이전트를 **병렬 실행**:

```
Agent tool (병렬 1):
  subagent_type: fe-harness:component-reviewer
  model: [컴포넌트 변경량 기준 선택]
  effort: [컴포넌트 변경량 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 6 component review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}

Agent tool (병렬 2):
  subagent_type: fe-harness:a11y-reviewer
  model: [접근성 영향 기준 선택]
  effort: [접근성 영향 기준 선택]
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 6 a11y review 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
```

Critical 이슈가 있으면 general-purpose 에이전트로 수정을 위임한다.

### Phase 7: PR / Push

- **`$HARD_MODE = false`** (일반):
  ```
  Agent tool:
    subagent_type: fe-harness:workflow-pr
    model: [PR 복잡도 기준 선택]
    effort: [PR 복잡도 기준 선택]
    prompt: |
      상태 파일 `/tmp/workflow-state.md`를 읽고 PR을 생성하세요.
      프로젝트 루트: {현재 작업 디렉토리}
      현재 Phase: Phase 7
      남은 Phase: Phase 8, 9
      배정 model/effort: {model}/{effort}
      PR URL을 반드시 보고하세요.
  ```

- **`$HARD_MODE = true`** (`--hard`):
  PR 생성을 건너뛰고, 현재 브랜치에서 바로 push만 수행한다.
  ```bash
  git push origin $(git branch --show-current)
  ```
  출력: "Phase 7 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)"

### Phase 8: 성찰

```
Agent tool:
  subagent_type: fe-harness:workflow-reflection
  model: [워크플로우 변경량 기준 선택]
  effort: [워크플로우 변경량 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 8
    남은 Phase: Phase 9
    배정 model/effort: {model}/{effort}
    성찰 결과와 스킬 보완점을 보고하세요.
```

---

## Phase 9: 최종 보고

Phase 4~8 에이전트들의 결과를 종합하여 보고서를 작성한다.

```markdown
## Workflow Report

### 1. 작업 요약
- **작업 유형**: [화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 컴포넌트**: [요약]

### 3. 엣지 케이스 대응
| # | 케이스 | 대응 방법 |
|---|--------|----------|

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| test | N | M |
| scope-review | N | M |
| lint | N | M |

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점 (프로젝트 오버라이드로 반영)
| # | 대상 스킬/에이전트 | 보완 내용 | 저장 경로 | 적용 여부 |
|---|----------|----------|----------|----------|
| 1 | /fe-harness:component | [내용] | `.claude/fe-harness/skills/component.md` | Y/N |
```

### 보완점 적용

플러그인 원본(`fe-harness/skills/...` 아래 파일)은 **절대 수정하지 않는다**. 보완점 반영 경로는 두 가지다:

| 경로 | 대상 | 적용 범위 |
|------|------|----------|
| **로컬 오버라이드** | `.claude/fe-harness/{common,skills,agents}/...` | 현 프로젝트에만 |
| **커뮤니티 피드백 PR** | 플러그인 레포 `fe-harness/community-feedback/...` | 큐레이션 후 모든 사용자에게 |

상세 규약: 플러그인 루트 `OVERRIDES.md` + `community-feedback/README.md`.

> "보완점 반영 방식을 선택하세요:"
>
> 1. **로컬에만 저장** (기본값) — `.claude/fe-harness/...` 에 append.
> 2. **로컬 저장 + 플러그인 레포에 PR** — `/fe-harness:submit-feedback` 호출. community-feedback 영역에 PR.
> 3. **건너뛰기**.

옵션 2 선택 시 각 보완점마다 `generality` (범용 / 특정 조건 / 프로젝트 한정) 를 수집, `프로젝트 한정`은 PR 대상에서 제외.

#### 옵션 2 세부 흐름

1. 로컬 오버라이드 append 먼저.
2. PR 후보 정리 후 `Skill tool` 로 `/fe-harness:submit-feedback` 호출.
3. `[SKIPPED:*]` 반환 시 로컬 저장만 완료 상태로 종료, fallback 사유 보고.
4. 성공 시 PR URL 을 최종 보고서에 포함.

#### append 규칙

대상이 스킬이면: `.claude/fe-harness/skills/{skill-name}.md`
대상이 에이전트면: `.claude/fe-harness/agents/{agent-name}.md`
공통이면: `.claude/fe-harness/common.md`

파일이 없으면 아래 형식으로 생성:

```markdown
---
scope: skill:{name}          # 또는 agent:{name} / common
applies-to: fe-harness@{버전}+
updated: {YYYY-MM-DD}
---

# Project Override: {대상}

## 보완점 (auto-appended {YYYY-MM-DD HH:mm})
- [보완 내용 1]
```

이미 있으면 기존 내용 뒤에 새 `## 보완점 (auto-appended ...)` 섹션을 append. 동일 내용이면 건너뜀.

추가 후 해당 파일 경로를 유저에게 보고한다:

> "프로젝트 오버라이드 업데이트 완료: [경로 목록]. 다음 워크플로우 실행 시 자동 로드. Git 커밋 권장."

### 정리

`/tmp/workflow-state.md`의 모든 Phase를 `DONE/SKIPPED`으로 갱신하고 `Remaining Phases`를 `없음`으로 기록한다.
기본은 상태 파일을 보관한다. 사용자가 정리를 요청했거나 보관이 필요 없을 때만 삭제한다:

```bash
rm -f /tmp/workflow-state.md
```

---

## 흐름 요약

```
[유저 대화] — Phase 0~3 전체가 단일 EnterPlanMode 컨텍스트
Phase 0: EnterPlanMode 활성화 → /request로 Technical Spec 작성 (유저 확인)
Phase 1: 난이도 산정 (1-10)
Phase 2: scope-reviewer 메모
Phase 3: Plan을 Spec 아래 추가 → 다관점 1회 보강 → Codex APPROVE 루프 (Spec+Plan 통합) → ExitPlanMode
Phase 3.5: 상태 파일 생성 → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 4: workflow-implementer          → 구현 + 커밋
Phase 5: 품질 루프 (오케스트레이터 관리, 최대 3회)
  5.0 build + type-check               → Bash 직접
  5.1 simplify-loop                    → general-purpose 에이전트
  5.2 convention-check                 → general-purpose 에이전트
  5.3 test-loop                        → general-purpose 에이전트
  5.4 scope-reviewer                   → scope-reviewer 에이전트
  5.5 lint-check                       → general-purpose 에이전트
  → 수정 있으면 커밋 후 재시작, 없으면 탈출
Phase 6: component-reviewer + a11y-reviewer (병렬, 컴포넌트 변경 시만)
Phase 7: workflow-pr                   → PR 생성
Phase 8: workflow-reflection           → 성찰

[유저 대화]
Phase 9: 최종 보고 → 보완점 적용 (유저 선택) → 정리
```
