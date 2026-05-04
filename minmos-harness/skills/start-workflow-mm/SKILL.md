---
name: start-workflow-mm
description: "전체 개발 워크플로우를 자동화. Build 모드(기본): 요청 분석 → 구현 → 품질 루프 → PR. Analyze 모드(--analyze): 코드 분석 보고서. Verify 모드(--verify): 보안·성능·버그·안정성 검증."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명> | --analyze [경로] | --verify [경로]
user-invocable: true
---

# Start Workflow — Orchestrator

전체 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. `commit-hard-push-mm` 사용. |
| `--analyze` | `-a` | **Analyze 모드**. 전체 또는 특정 범위의 코드를 분석하여 보고서를 생성한다. |
| `--verify` | `-v` | **Verify 모드**. 보안·성능·잠재 버그·안정성을 검증하고 Pass/Fail 판정한다. |

`$ARGUMENTS`에 `--hard` 또는 `-h`가 포함되어 있으면 `$HARD_MODE = true`로 설정한다.

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 3.5 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 4 커밋 | 동일 | 동일 |
| Phase 7 PR | workflow-pr (브랜치 생성 + PR) | **commit-hard-push-mm** (현재 브랜치에서 바로 push, PR 생략) |

### 모드 판별

`$ARGUMENTS`를 파싱하여 실행 모드를 결정한다:

| 조건 | 모드 | 실행 경로 |
|------|------|----------|
| `--analyze` 또는 `-a` 포함 | **Analyze** | Phase A0 → A3 |
| `--verify` 또는 `-v` 포함 | **Verify** | Phase V0 → V4 |
| 위 플래그 없음 | **Build** (기본) | Phase 0 → 9 |

> `--analyze`와 `--verify`는 상호 배타적이다. 동시 지정 시 유저에게 하나를 선택하도록 안내한다.
> `--hard`는 Build 모드에서만 유효하다. Analyze/Verify 모드에서 `--hard`가 포함되면 무시한다.

**범위 지정**: 플래그 뒤에 경로가 있으면 분석/검증 **범위**로 사용한다.
- `--analyze internal/book` → `internal/book` 디렉토리 분석
- `--verify internal/book/usecase` → 해당 디렉토리 검증
- `--analyze` (경로 없음) → 전체 코드베이스
- `--verify internal/book/handler.go` → 특정 파일만 검증

---

```
[유저 대화] Phase 0~1.5: 직접 실행 (Spec, Codex Spec 리뷰, 난이도, 실행 전략)
[유저 대화] Phase 2~3  : 직접 실행 (Plan, 리뷰, Codex Plan 리뷰)
[상태 저장] Phase 3.5  : 상태 파일 생성
[자율 실행] Phase 4~8  : 서브 에이전트 순차/병렬 위임
[유저 대화] Phase 9    : 최종 보고 + 보완점 적용
```

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

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
| Simple | 난이도 1-3, 1-3개 파일, 문서/단순 수정 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 난이도 4-6, 일반 구현/리뷰/테스트 수정 | sonnet | gpt-5.3-codex | medium |
| Complex | 난이도 7-8, 다중 레이어/API/DB/계약 영향 | opus | gpt-5.4 | high |
| Critical | 난이도 9-10, 보안/데이터 마이그레이션/대규모 리팩토링 | opus | gpt-5.5 | xhigh |

읽기 전용 리뷰는 기본 `Standard`로 시작하되, 보안/데이터 정합성/계약 변경 검토는 `Complex` 이상으로 올린다.
코드 수정 에이전트는 담당 파일 수와 실패 반복 횟수에 따라 한 단계 높일 수 있다.

### Build Mode 기본 Phase 할당

| Phase | 담당 agent | 기본 model/effort |
|-------|------------|-------------------|
| 0-1.5 | orchestrator | 현재 세션 설정 |
| 2-3 | orchestrator + review agents | 난이도 기준 |
| 4 | workflow-implementer 또는 slice별 general-purpose | 난이도/슬라이스 기준 |
| 4.5 | orchestrator Bash, 실패 시 build-fix agent | Standard, 반복 실패 시 Complex |
| 5 | simplify/convention/e2e/scope agents | Standard, 결함 심각도에 따라 Complex |
| 6 | workflow-doc-sync | Standard, 계약 변경 크면 Complex |
| 7 | workflow-pr 또는 commit-hard-push-mm | Simple/Standard |
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

> 기술적으로 올바른 수정이라도, 유저가 방향을 결정하기 전에 코드를 건드리지 않는다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- Phase 4 완료 → 즉시 Phase 5 시작 (같은 턴)
- Phase 5 내 각 단계(5.0~5.5)도 이전 단계 완료 즉시 다음 단계 시작
- Phase 5 완료 → 즉시 Phase 6 시작 (같은 턴)
- Phase 6~8도 동일: 완료 즉시 다음 Phase 시작
- **유저 응답을 기다리거나, 진행 여부를 묻거나, 중간 보고 후 멈추는 것은 금지**
- 유일한 정지 지점은 **Phase 9 (최종 보고)** 뿐이다

---

## Pre-flight: 세션 환경 점검

모드 실행 전, 대화 이력을 확인하여 세션 환경을 점검한다.

### 1. Effort Level

대화 이력에 `/effort max` 실행 흔적이 없으면 `AskUserQuestion`으로 질문한다:
> "워크플로우 최대 성능을 위해 `/effort max` 설정을 권장합니다. 설정할까요?"

- 동의하면 → "`/effort max`를 입력해주세요." 안내 후, 실행 확인 뒤 진행
- 거부하면 → 현재 설정으로 진행

### 2. Advisor

대화 이력에 `/advisor opus` 실행 흔적이 없으면 사용자에게 실행을 요청한다:
> "워크플로우 시작 전 `/advisor opus`를 실행해주세요."

실행 확인 후 다음 단계로 진행한다.

### 3. 프로젝트 환경 점검

아래 항목을 Bash/Glob으로 빠르게 확인한다. **누락 항목이 있으면 어떤 Phase가 SKIP될 것인지 사전 경고**한다.

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `secret/.env` | 파일 존재 확인 | **Phase 5.3 (e2e-test-loop) SKIP 예정** — 서버 부팅/JWT 발급 불가 |
| Apidog MCP 연결 | `mcp__apidog__read_project_oas_*` 호출 가능 여부 | **Phase 6 (Apidog 동기화) SKIP 예정** |
| PostgreSQL MCP 연결 | PostgreSQL MCP로 `SELECT 1` 실행 | **Phase 5.3 (e2e-test-loop) 부분 SKIP 예정** — DB 시드/정리 경로 제한 |

**MCP 판정 원칙**: `.mcp.json`은 설정 안내용 fallback으로만 확인한다. OpenCode 등 클라이언트별 MCP 설정 위치가 다를 수 있으므로 실제 MCP tool 호출이 성공하면 OK로 판정한다.

**처리 규칙**:
- 모두 OK → 점검 결과 한 줄 요약 후 다음 단계 진행
- 누락 있음 → 아래 사전 경고를 출력한다:

  > ⚠️ 환경 누락 감지: `{누락 항목}` 없음. 이번 워크플로우에서 **{영향받는 Phase 목록}**는 SKIP됩니다.
  > 정상 실행을 원하면 `/minmos-harness:minmo-doctor-mm`으로 진단 후 재시작하세요. 이대로 진행하시겠습니까?

  - 사용자가 진행하면 해당 Phase에서는 `SKIPPED` 플래그를 붙여 넘긴다.
  - 사용자가 중단하면 여기서 종료한다.

> 이 사전 경고는 Phase 5.3 / Phase 6 내부에서 실패 후 판정하지 않고, Phase 0에서 **미리 SKIP 예정 스테이지를 확정**하기 위함이다.

---

## Analyze Mode (`--analyze`)

> 코드를 분석하여 아키텍처·품질·의존성·패턴·기술 부채를 보고한다. **코드 수정은 하지 않는다.**

### Phase A0: 범위 및 초점 수집

1. **범위 확인**: `$ARGUMENTS`에서 플래그 뒤 경로가 지정되었으면 해당 범위를 사용. 없으면 유저에게 확인한다.
   > "분석 범위를 지정해주세요. (전체 / 디렉토리 경로 / 파일 경로)"

2. **초점 선택**: 유저에게 분석 초점을 묻는다 (복수 선택 가능).
   > "분석 초점을 선택해주세요:"
   > 1. 아키텍처 (레이어 구조, 모듈 결합도, 인터페이스)
   > 2. 코드 품질 (복잡도, 중복, Dead Code, 코드 스멜)
   > 3. 의존성 (외부 패키지, 내부 의존 그래프, 순환 의존)
   > 4. 패턴 & 기술 부채 (안티패턴, TODO/FIXME, 일관성)
   > 5. 전체 (기본값)
   >
   > 예: `5` (전체) 또는 `1,2` (아키텍처 + 품질)

3. **추가 컨텍스트**: `$ARGUMENTS`나 대화에 특정 관심사가 포함되어 있으면 함께 전달한다.

### Phase A1: 상태 파일 생성

Write tool로 `/tmp/workflow-state.md`를 생성한다:

```markdown
# Workflow State — Analyze Mode

## Mode
analyze

## Scope
{범위}

## Focus
{선택된 초점 목록}

## Context
{추가 컨텍스트 또는 "없음"}
```

출력: **"코드 분석을 시작합니다."**

### Phase A2: 코드 분석

```
Agent tool:
  subagent_type: minmos-harness:code-analyzer
  model: [분석 범위 기준 선택]
  effort: [분석 범위 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 코드 분석을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase A2
    남은 Phase: Phase A3
    배정 model/effort: {model}/{effort}
    
    분석 범위: {scope}
    분석 초점: {focus}
    추가 컨텍스트: {context}
    
    분석 완료 후 출력 형식에 따라 보고서를 작성하세요.
```

### Phase A3: 분석 보고서

code-analyzer 에이전트의 결과를 종합하여 유저에게 보고한다.

```markdown
## Code Analysis Report

### 분석 개요
- **모드**: Analyze
- **범위**: {scope}
- **초점**: {focus}

{code-analyzer 보고서 전문}

### 추가 조치
```

> "발견된 이슈를 수정할까요? (전체/선택/건너뛰기)"

- **전체**: general-purpose 에이전트를 생성하여 즉시 수정 가능한 모든 이슈를 수정한다.
- **선택**: 유저가 번호로 선택한 항목만 수정한다.
- **건너뛰기**: 보고서만 출력하고 종료한다.

수정 후 커밋 여부를 유저에게 확인한다.

정리:
상태 파일의 `Remaining Phases`를 `없음`으로 갱신하고 기본은 보관한다. 사용자가 정리를 요청한 경우에만 삭제한다.

```bash
rm -f /tmp/workflow-state.md
```

---

## Verify Mode (`--verify`)

> 코드를 검증하여 보안·성능·잠재 버그·안정성 관점에서 **Pass/Fail 판정**을 내린다.

### Phase V0: 범위 및 초점 수집

1. **범위 확인**: `$ARGUMENTS`에서 플래그 뒤 경로가 지정되었으면 해당 범위를 사용. 없으면 유저에게 확인한다.
   > "검증 범위를 지정해주세요. (전체 / 디렉토리 경로 / 파일 경로)"

2. **초점 선택**: 유저에게 검증 초점을 묻는다 (복수 선택 가능).
   > "검증 초점을 선택해주세요:"
   > 1. 보안 (SQL Injection, XSS, 인증/인가, 데이터 노출)
   > 2. 성능 (N+1 쿼리, 메모리 누수, 리소스 관리)
   > 3. 잠재 버그 (Nil 역참조, 동시성, 에러 처리, 로직 결함)
   > 4. 안정성 (리소스 관리, 장애 복원력, 테스트 커버리지)
   > 5. 전체 (기본값)
   >
   > 예: `5` (전체) 또는 `1,3` (보안 + 잠재 버그)

### Phase V1: 상태 파일 생성 + 정적 분석

#### 상태 파일 생성

Write tool로 `/tmp/workflow-state.md`를 생성한다:

```markdown
# Workflow State — Verify Mode

## Mode
verify

## Scope
{범위}

## Focus
{선택된 초점 목록}
```

#### 정적 분석 도구 실행

Bash로 Go 내장 정적 분석을 먼저 실행한다:

```bash
go vet ./... 2>&1
go build ./cmd/main.go 2>&1
```

테스트 커버리지가 초점에 포함된 경우 (`전체` 또는 `안정성`):
```bash
go test -cover ./internal/... 2>&1
```

결과를 상태 파일에 append한다.

출력: **"코드 검증을 시작합니다."**

### Phase V2: 코드 검증

```
Agent tool:
  subagent_type: minmos-harness:code-verifier
  model: [검증 범위/초점 기준 선택]
  effort: [검증 범위/초점 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 코드 검증을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase V2
    남은 Phase: Phase V3, V4
    배정 model/effort: {model}/{effort}
    
    검증 범위: {scope}
    검증 초점: {focus}
    정적 분석 결과:
    [go vet 결과]
    [go build 결과]
    [go test -cover 결과 (실행한 경우)]
    
    검증 완료 후 출력 형식에 따라 보고서를 작성하세요.
```

### Phase V3: 컨벤션 검사 (선택적)

검증 초점에 `전체`가 포함되어 있을 때만 실행한다.

```
Agent tool:
  subagent_type: general-purpose
  model: [컨벤션 검사 범위 기준 선택]
  effort: [컨벤션 검사 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /minmos-harness:convention-check-mm 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase V3 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    결과를 "위반: N건" 형식으로 보고하세요.
```

### Phase V4: 종합 검증 보고서

code-verifier 에이전트 결과 + 정적 분석 결과 + 컨벤션 검사 결과를 종합하여 보고한다.

```markdown
## Code Verification Report

### 검증 개요
- **모드**: Verify
- **범위**: {scope}
- **초점**: {focus}

### 정적 분석 결과
| 도구 | 판정 | 비고 |
|------|------|------|
| go vet | PASS/FAIL | {요약} |
| go build | PASS/FAIL | {요약} |
| go test -cover | {커버리지 %}% | 실행한 경우만 |

### 코드 검증 결과
{code-verifier 보고서 전문}

### 컨벤션 검사 결과
{convention-check 결과 또는 "미실행"}

### 종합 판정
| 항목 | 판정 |
|------|------|
| 정적 분석 | PASS/FAIL |
| 보안 | PASS/WARN/FAIL |
| 성능 | PASS/WARN/FAIL |
| 잠재 버그 | PASS/WARN/FAIL |
| 안정성 | PASS/WARN/FAIL |
| 컨벤션 | PASS/WARN/FAIL (실행 시) |
| **종합** | **PASS/WARN/FAIL** |

### 즉시 수정 권고 (Critical + High)
{이슈 목록}
```

> "발견된 이슈를 수정할까요? (Critical+High 전체 / 선택 / 건너뛰기)"

- **전체**: general-purpose 에이전트를 생성하여 Critical+High 이슈를 모두 수정한다.
- **선택**: 유저가 번호로 선택한 항목만 수정한다.
- **건너뛰기**: 보고서만 출력하고 종료한다.

수정 후 커밋 여부를 유저에게 확인한다.

정리:
상태 파일의 `Remaining Phases`를 `없음`으로 갱신하고 기본은 보관한다. 사용자가 정리를 요청한 경우에만 삭제한다.

```bash
rm -f /tmp/workflow-state.md
```

---

## Build Mode (기본)

> 플래그 없이 실행하거나 `--hard`만 지정하면 기본 Build 모드로 동작한다.

## Phase 0: 작업 범위 수집

### 분기: 이미 상세 Spec이 제공된 경우

`$ARGUMENTS` 또는 대화 컨텍스트에 다음 조건을 **모두** 충족하는 상세 설명이 이미 포함되어 있으면 `/request` 호출을 **생략**한다:
- 작업 유형이 명확 (생성/수정/검토/디버깅)
- 대상 API/기능이 특정됨
- 핵심 요구사항이 구체적으로 기술됨

이 경우, 제공된 내용을 Technical Spec으로 직접 정리하고 유저 확인을 받는다.

### 기본: /request 호출

위 조건을 충족하지 않으면 `/minmos-harness:request-mm`를 호출하여 Technical Spec을 생성한다.

- `$ARGUMENTS`가 있으면 request 스킬에 전달한다.
- request 스킬이 완료되면 생성된 **Technical Spec** 전문을 보관한다.
- Spec에서 **작업 유형** (생성/수정/검토/디버깅)을 확인한다.

> 어느 경우든 Spec을 유저에게 보여주고 확인을 받는다.

### Phase 0.5: Codex Spec 리뷰 (항상)

Technical Spec 확정 직후, 구현 전략을 세우기 전에 **반드시 Codex 리뷰**를 받는다.
Codex가 사용 불가한 환경이면 그 사실을 기록하고, 누락을 숨기지 않는다.

리뷰 관점:
- 비즈니스 요구사항 누락
- 레이어 책임 경계
- 데이터 정합성 및 API 계약 위험
- 과잉 구현 가능성
- `[Assumption]`으로 표기해야 할 유추 사항

리뷰 결과에서 타당한 지적은 Technical Spec에 반영하고, 반영/미반영 사유를 기록한다.

---

## Phase 1: 난이도 산정

Technical Spec을 분석하여 1~10 난이도를 산정한다.

### A. 코드 복잡도 (구현 난이도)

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 레이어 | 단일 | 2개 | 3개 전체 |
| DB 변경 | 없음 | 컬럼 추가 | 신규 테이블 |
| 외부 연동 | 없음 | 기존 gRPC | 신규 gRPC |
| 비즈니스 복잡도 | 단순 CRUD | 조건 분기 3개 이하 | 상태 머신 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

### B. 영향 범위 리스크 (사이드 이펙트 위험도)

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 기존 API 호환성 | Breaking change 없음 | 선택 필드 추가 | 필수 필드/응답 구조 변경 |
| DB 데이터 영향 | 신규 테이블만 | 기존 테이블 컬럼 추가 | 기존 데이터 마이그레이션 필요 |
| 공유 모듈 수정 | 없음 | 유틸리티/공통 함수 | 미들웨어/인터셉터/DI |
| 다른 서비스 의존 | 독립적 | 같은 repo 내 참조 | 외부 서비스 연동 변경 |
| 롤백 용이성 | 즉시 가능 | 마이그레이션 롤백 필요 | 데이터 복구 필요 |

출력: `난이도: 코드 [A]/10 + 리스크 [B]/10 — [근거]`

> 종합 난이도 = max(A, B). 코드는 쉽지만 리스크가 높으면 전체 난이도가 올라간다.

> 난이도와 무관하게 Phase 3에서 Codex Plan 리뷰를 항상 수행한다.

---

## Phase 1.5: 실행 전략 판정 (Batch Eligibility Gate)

Technical Spec을 분석하여 구현 병렬화 가능 여부를 판정한다.

### 판정 기준

아래 **5가지 조건을 모두 충족**해야 `parallel-slices`로 판정한다:

| # | 조건 | 확인 방법 |
|---|------|----------|
| 1 | Spec이 2~3개의 **수직 슬라이스**를 포함 | 각 슬라이스가 독립된 endpoint/feature이며, 각각 handler+usecase+repository를 가짐 |
| 2 | 슬라이스 간 **파일 겹침 없음** | 공유 VO, DTO, middleware, DI wiring 변경이 없음 |
| 3 | **DB migration/공통 계약 변경 없음** | 신규 테이블은 가능하나, 기존 테이블 수정·공유 인터페이스 변경은 불가 |
| 4 | 각 슬라이스가 **독립 빌드·테스트 가능** | 한 슬라이스만 구현해도 빌드가 깨지지 않음 |
| 5 | **순서 의존 없음** | 슬라이스 A가 완료되어야 B를 시작할 수 있는 관계가 없음 |

### 판정 결과

| 전략 | 조건 | 동작 |
|------|------|------|
| `sequential` | 위 조건 미충족 (기본값) | 기존 Phase 4 순차 실행 |
| `parallel-slices` | 5가지 조건 모두 충족, 슬라이스 2~3개 | Phase 4에서 슬라이스별 병렬 구현 |
| `fullstack` | FE+BE 동시 변경 | `/start-workflow-fs`로 리다이렉트 후 종료 |

> **대부분의 작업은 `sequential`이다.** `parallel-slices`는 명확히 독립적인 수직 슬라이스가 존재할 때만 적용한다.
> 판단이 애매하면 `sequential`을 선택한다 — 병렬화의 이점보다 잘못된 분리의 비용이 훨씬 크다.

출력: `실행 전략: [sequential/parallel-slices/fullstack] — [근거]`

`fullstack` 판정 시:
> "FE+BE 동시 변경이 필요합니다. `/start-workflow-fs`로 전환합니다."
> → `Skill tool`로 `/minmos-harness:start-workflow-fs`를 호출하고 현재 워크플로우를 종료한다.

---

## Phase 2: Scope Reviewer 준비

Phase 5에서 사용할 scope-reviewer 정보를 메모한다:
- Technical Spec 전문
- 엣지 케이스 목록

---

## Phase 3: Plan 작성 + 리뷰

### 3.1 Plan 작성

`EnterPlanMode` 활성화. Plan 포함 내용:
- 구현 순서 (파일 단위)
- 각 파일 변경 내용 요약
- **최종 코드 구조**: 중복 로직이 예상되면 최종 구조(e.g. 테이블 드리븐, 공통 함수 추출)를 Plan 단계에서 확정한다. 구현 후 리팩토링 커밋이 발생하지 않도록 한다.
- 의존 관계
- 예상 리스크

#### parallel-slices 추가 요구사항

실행 전략이 `parallel-slices`인 경우, Plan에 아래를 **추가로** 명시한다:

```markdown
## Slices

### Slice 1: [제목]
- **파일 범위**: [이 슬라이스가 수정하는 파일 목록]
- **설명**: [한 줄 설명]

### Slice 2: [제목]
- **파일 범위**: [이 슬라이스가 수정하는 파일 목록]
- **설명**: [한 줄 설명]

(최대 3개)
```

> 슬라이스 간 파일 범위가 겹치면 안 된다. 겹치는 파일이 발견되면 `sequential`로 전략을 변경한다.

### 3.2 다관점 Plan 리뷰

**최대 3개 서브에이전트 병렬 실행**, 2배치로 진행:

```
Batch 1 (병렬): 유지보수성 + 성능 + 엣지 케이스
Batch 2 (병렬): 데이터 정합성 + 보안 + 기존 코드 영향
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
- **REJECT 1개+**: Plan 수정 → 해당 관점 재리뷰
- **CONCERN만**: 타당한 것 자동 반영

### 3.3 Codex Plan 리뷰 (항상)

Codex 사용 가능 시 Architect 관점으로 Plan 리뷰를 반드시 위임한다.
불가 시 건너뛰되, Phase 9 보고서에 "Codex Plan 리뷰 미수행"과 사유를 남긴다.

리뷰 입력:
- Technical Spec 전문
- Plan 전문
- 실행 전략(sequential/parallel-slices)
- 난이도 및 리스크 산정 근거

리뷰 관점:
- Spec과 Plan의 추적 가능성
- 레이어별 책임 분리
- 병렬 작업 시 파일 소유권 충돌
- 테스트/검증 누락
- 더 단순한 구현 경로

REJECT 또는 타당한 CONCERN이 있으면 Plan을 수정하고, 필요한 관점만 재리뷰한다.

### 3.4 Plan 확정

`ExitPlanMode` 실행.

---

## Phase 3.5: Feature 브랜치 생성 + 상태 파일 생성 + 자율 실행 시작

### 브랜치 생성

- **`$HARD_MODE = false`** (일반): 구현 시작 전 반드시 feature 브랜치를 생성한다. main/master에 직접 커밋하지 않는다.
  ```bash
  git checkout -b feat/{작업 요약 kebab-case}
  ```
  이미 feature 브랜치(`feat/**`, `hotfix/**`)에 있으면 건너뛴다.

- **`$HARD_MODE = true`** (`--hard`): 브랜치 생성을 **건너뛴다**. 현재 브랜치가 무엇이든 그대로 사용한다.

### 상태 파일 생성

Write tool로 `/tmp/workflow-state.md`를 생성한다:

```markdown
# Workflow State

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[생성/수정/검토/디버깅]

## Difficulty
[N]/10

## Current Phase
Phase 3.5 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 0 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 0.5 | Codex reviewer | 난이도 기준 | 난이도 기준 | DONE/SKIPPED |
| 1 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 1.5 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | review agents + orchestrator | 난이도 기준 | 난이도 기준 | DONE |
| 3.5 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 4 | workflow-implementer/general-purpose | 난이도 기준 | 난이도 기준 | PENDING |
| 4.5 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 5 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 6 | workflow-doc-sync | 난이도 기준 | 난이도 기준 | PENDING |
| 7 | workflow-pr/commit-hard-push-mm | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 4: 구현
- Phase 4.5: 빌드 체크
- Phase 5: 품질 루프
- Phase 6: 문서 동기화
- Phase 7: PR / Push
- Phase 8: 성찰
- Phase 9: 최종 보고

## Execution Strategy
[sequential/parallel-slices]

## Edge Cases
[엣지 케이스 목록]

## Plan
[확정된 Plan 전문 그대로 복사]

## Phase Results
[Phase 완료 시 결과 append]
```

`parallel-slices`인 경우, 상태 파일에 아래를 추가한다:

```markdown
## Slices
[Plan에서 정의한 Slice 정보 그대로 복사]
```

출력:
- `sequential`: **"자율 실행을 시작합니다. Phase 4~8을 서브 에이전트로 순차 실행합니다."**
- `parallel-slices`: **"자율 실행을 시작합니다. [N]개 슬라이스를 병렬 구현합니다."**

---

## Phase 4~8: 서브 에이전트 순차 실행

**각 Phase를 전용 서브 에이전트에 위임한다.**
이전 에이전트가 완료된 후 다음 에이전트를 실행한다.
각 에이전트의 반환 결과를 기록해 둔다 (Phase 9 보고서에 사용).
각 Phase 시작 직전 `/tmp/workflow-state.md`의 `Current Phase`, `Phase Assignments.Status`, `Remaining Phases`를 갱신한다.
Agent tool 호출에는 선택된 `model`과 `effort`를 함께 지정한다.

### Phase 4: 구현

#### sequential 모드 (기본)

```
Agent tool:
  subagent_type: minmos-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 4
    남은 Phase: Phase 4.5, 5, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}
    
    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경(예: 필터 추가, 정렬 변경 등)을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.
    
    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

완료 후 유저에게 간략 보고: "Phase 4 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

#### parallel-slices 모드

상태 파일의 Slices에 정의된 2~3개 슬라이스를 **동시에 병렬 구현**한다.
같은 브랜치에서 파일 소유권을 분리하여 충돌을 방지한다.

**중요**: 병렬 에이전트는 **커밋하지 않는다**. 구현만 수행하고, 커밋은 모든 에이전트 완료 후 오케스트레이터가 일괄 처리한다.

> `workflow-implementer`는 커밋/빌드가 내장되어 있어 커밋 유보 지시와 충돌한다.
> 병렬 모드에서는 `general-purpose` 에이전트를 사용한다.

슬라이스 수만큼 Agent를 **하나의 메시지에서 동시에** 호출한다:

```
# 모든 슬라이스를 동일 메시지에서 병렬 호출
Agent tool:  (× 슬라이스 수)
  subagent_type: general-purpose
  model: [슬라이스 난이도 기준 선택]
  effort: [슬라이스 난이도 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고, 아래 슬라이스만 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 4 parallel-slices
    남은 Phase: Phase 4.5, 5, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}
    
    ## 담당 슬라이스
    제목: {Slice N 제목}
    파일 범위: {Slice N 파일 목록}
    설명: {Slice N 설명}
    
    ## 제한사항 (CRITICAL)
    - **위 파일 범위에 해당하는 파일만 수정하세요.** 범위 밖 파일은 절대 수정하지 않습니다.
    - **git commit을 하지 마세요.** 코드 구현만 수행합니다. 커밋은 오케스트레이터가 처리합니다.
    - **go build를 실행하지 마세요.** 빌드 검증은 오케스트레이터가 처리합니다.
    
    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.
    
    구현 완료 후 변경 파일 목록, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

모든 슬라이스 에이전트 완료 후, 오케스트레이터가 일괄 커밋:

```bash
git add [전체 변경 파일]
git commit -m "$(cat <<'EOF'
Add: [작업 요약] (병렬 슬라이스 구현)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

완료 후 유저에게 간략 보고: "Phase 4 완료: [N]개 슬라이스 병렬 구현, [변경 파일 수]개 파일"

### Phase 4.5: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

구현 에이전트 완료 즉시, 품질 루프 진입 전에 **반드시 빌드 체크를 실행**한다.
컴파일 오류(미사용 변수, import 누락, 무한 루프 등)를 조기에 잡아 핫픽스를 방지한다.

```bash
go build ./cmd/main.go 2>&1
```

- **성공** → Phase 5로 진행.
- **실패** → general-purpose 에이전트를 생성하여 빌드 에러를 수정한다:
  ```
  Agent tool:
    subagent_type: general-purpose
    model: [빌드 실패 심각도 기준 선택]
    effort: [빌드 실패 심각도 기준 선택]
    prompt: |
      프로젝트 루트 {CWD}에서 `go build ./cmd/main.go` 빌드 에러를 수정하세요.
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

### Phase 5: 품질 루프 (병렬 스캔 → 통합 수정)

**단일 에이전트가 아닌, 각 품질 단계를 개별 에이전트로 분리하여 실행한다.**
오케스트레이터가 루프를 직접 관리한다. 최대 3회 반복.

루프 1회는 **3단계**로 구성된다:

```
for iteration in 1..3:
  [Batch A — 병렬 스캔] 5.0 + 5.1 + 5.2 + 5.4 동시 실행 (읽기/분석, 파일 수정 금지)
      └─ 모든 이슈를 수집 → 통합 수정 단계에서 일괄 반영

  [통합 수정] Batch A에서 수집된 이슈를 일괄 수정 (단일 general-purpose 에이전트)

  [Batch B — 순차] 5.3 e2e-test-loop → 5.5 make test
      └─ 서버 점유 / 환경 자원이 걸리므로 순차 유지

  수정 있음? → 커밋 후 다음 iteration
  수정 없음? → 루프 탈출
```

#### Batch A: 병렬 스캔 (5.0 + 5.1 + 5.2 + 5.4)

네 단계를 **하나의 메시지에서 동시에 호출**한다. 모든 서브 에이전트는 **이슈 목록만 반환하며 파일을 수정하지 않는다**.
파일 수정은 다음 단계인 "통합 수정"에서 일괄 처리하여 에이전트 간 파일 편집 경합을 제거한다.

```
# 같은 메시지에서 4개 병렬 호출

[1] 5.0 Go 빌드 + 테스트 — Bash로 직접 실행 (에이전트 아님)
    go build ./cmd/main.go && go test ./internal/... 2>&1
    → 에러 로그를 Batch A 결과에 수집. 파일 수정 없음.

[2] 5.1 Simplify Scan
    Agent tool:
      subagent_type: general-purpose
      model: [품질 스캔 범위 기준 선택]
      effort: [품질 스캔 범위 기준 선택]
      prompt: |
        프로젝트 루트 {CWD}에서 /minmos-harness:simplify-loop-mm 를 **dry-run** 관점으로 실행하세요.
        상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.1 상태를 갱신하세요.
        배정 model/effort: {model}/{effort}
        **파일을 수정하지 말고** 단순화 후보 목록만 반환하세요.
        각 항목: {file:line, 현재 코드 요약, 제안 변경, 근거}.
        완료 후 "후보: N건" 형식으로 보고하세요.

[3] 5.2 Convention Check Scan
    Agent tool:
      subagent_type: general-purpose
      model: [품질 스캔 범위 기준 선택]
      effort: [품질 스캔 범위 기준 선택]
      prompt: |
        프로젝트 루트 {CWD}에서 /minmos-harness:convention-check-mm 를 실행하세요.
        상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.2 상태를 갱신하세요.
        배정 model/effort: {model}/{effort}
        **파일을 수정하지 말고** 위반 목록만 반환하세요.
        각 항목: {file:line, 위반 규칙, 제안 수정}.
        완료 후 "위반: N건" 형식으로 보고하세요.

[4] 5.4 Scope Review
    Agent tool:
      subagent_type: minmos-harness:scope-reviewer
      model: [리뷰 범위 기준 선택]
      effort: [리뷰 범위 기준 선택]
      prompt: |
        상태 파일 `/tmp/workflow-state.md`의 Technical Spec을 기준으로
        현재 구현된 코드를 검증하세요. 프로젝트 루트: {CWD}.
        현재 Phase: Phase 5.4
        남은 Phase: Phase 5 통합 수정, 5.3, 5.5, 5.6, 6, 7, 8, 9
        배정 model/effort: {model}/{effort}
        누락/불일치 항목만 반환하고 파일은 수정하지 마세요.
```

> **CRITICAL**: Batch A의 에이전트는 모두 읽기/분석만 수행한다. 같은 메시지에서 병렬 실행해도 편집 충돌이 발생하지 않는다.
> 만약 에이전트가 파일을 수정했다면 해당 변경을 **무시**하고 이슈 목록만 채택한다 (오케스트레이터가 일괄 수정 시 기준 상태에서 다시 편집).

#### 통합 수정

Batch A에서 수집된 이슈(빌드/테스트 에러 + simplify 후보 + convention 위반 + scope 누락)가 하나라도 있으면, **단일 `general-purpose` 에이전트**에 일괄 위임한다:

```
Agent tool:
  subagent_type: general-purpose
  model: [수정 이슈 심각도 기준 선택]
  effort: [수정 이슈 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 아래 이슈 목록을 순서대로 수정하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5 통합 수정 상태를 갱신하세요.
    남은 Phase: Phase 5.3, 5.5, 5.6, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}

    ## 이슈 목록
    ### 빌드/테스트 에러 (최우선)
    {go build / go test 로그}

    ### Scope 누락
    {scope-reviewer 보고서}

    ### Convention 위반
    {convention-check 보고서}

    ### Simplify 후보
    {simplify 후보 목록 — 안전한 변경만 적용, 의심스러우면 생략}

    같은 파일에 여러 이슈가 있으면 한 번의 편집으로 합쳐 처리하세요.
    수정 후 `go build ./cmd/main.go`로 빌드가 통과하는지 확인하세요.
    완료 후 "수정: N건, 파일: [목록]" 형식으로 보고하세요.
```

수정 발생 시 `modified = true`.

#### Batch B: 순차 실행 (5.3 → 5.5)

서버/테스트 프로세스가 포트·DB·바이너리를 점유하므로 순차로 실행한다.

##### 5.3 E2E Test

```
Agent tool:
  subagent_type: general-purpose
  model: [E2E 범위/실패 심각도 기준 선택]
  effort: [E2E 범위/실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 /minmos-harness:e2e-test-loop-mm 를 실행하세요.
    상태 파일 `/tmp/workflow-state.md`를 읽고 Phase 5.3 상태를 갱신하세요.
    남은 Phase: Phase 5.5, 5.6, 6, 7, 8, 9
    배정 model/effort: {model}/{effort}
    결과가 `[SKIPPED:*]`이면 스킵 사유를 그대로 보고하세요.
    완료 후 "이슈: N건, 수정: Y/N, 스킵 사유: {있으면}" 형식으로 보고하세요.
```
- `SKIPPED` 반환 시 → `modified`에 영향 주지 않고 다음 단계 진행 (루프 재시작 트리거 아님)
- "수정: Y" → `modified = true`

##### 5.5 Make Test

Bash로 직접 실행:
```bash
make test
```
실패 시 `general-purpose` 에이전트로 수정 위임. 수정 발생 시 `modified = true`.

#### 루프 판정

- `modified == true` → 변경사항 커밋 후 루프 재시작
- `modified == false` → 루프 탈출
- 3회 도달 → 미해결 사항 보고 후 강제 탈출

커밋:
```bash
git add [수정 파일들]
git commit -m "Fix: 품질 루프 수정 (반복 N)"
```

완료 후: "Phase 5 완료: [루프 횟수]회, 총 [수정 건수]건 수정"

### Phase 5.6: Codex 품질 리뷰 (항상)

품질 루프가 완료되면 Phase 6으로 넘어가기 전에 **반드시 Codex 리뷰**를 받는다.
Codex가 사용 불가한 환경이면 Phase 9 보고서에 사유를 기록한다.

리뷰 입력:
- Technical Spec
- 확정 Plan
- 변경 파일 목록
- Phase 4 구현 결과
- Phase 5 품질 루프 결과 및 남은 이슈

리뷰 관점:
- Spec/Plan 대비 구현 누락
- 비즈니스 로직 결함
- 레이어 구조 위반
- 테스트 및 검증 공백
- 품질 루프가 놓친 단순화/컨벤션 이슈

결과 처리:
- **APPROVE**: Phase 6으로 진행
- **CONCERN**: 타당한 항목만 수정 후 필요한 검증 재실행
- **REJECT**: 수정 후 Phase 5 관련 검증을 재실행하고 Codex 품질 리뷰를 다시 받음

### Phase 6: 문서 동기화 (조건부)

**작업 유형이 API 생성/수정/삭제인 경우만 실행. 그 외는 건너뛴다.**

#### 외부 도구 Capability 선확인

MCP tool이나 외부 서비스를 호출하기 전, **1회 호출로 read/write 권한 및 지원 범위를 먼저 파악**한다.
지원하지 않는 기능(e.g. 읽기 전용 MCP에 쓰기 시도)은 시도하지 않고, 대안(수동 안내 등)을 즉시 제시한다.

```
Agent tool:
  subagent_type: minmos-harness:workflow-doc-sync
  model: [문서/계약 변경 범위 기준 선택]
  effort: [문서/계약 변경 범위 기준 선택]
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 API 문서를 동기화하세요.
    작업 유형: {Task Type}
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 6
    남은 Phase: Phase 7, 8, 9
    배정 model/effort: {model}/{effort}
    
    [외부 도구 규칙]
    MCP tool 호출 전 capability(read/write)를 먼저 확인하세요.
    지원하지 않는 기능은 시도하지 말고 수동 가이드를 제공하세요.
```

### Phase 7: PR / Push

- **`$HARD_MODE = false`** (일반):
  ```
  Agent tool:
    subagent_type: minmos-harness:workflow-pr
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
  subagent_type: minmos-harness:workflow-reflection
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
- **작업 유형**: [생성/수정/검토/디버깅]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 로직**: [요약]

### 3. 엣지 케이스 대응
| # | 케이스 | 대응 방법 |
|---|--------|----------|

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| e2e | N | M |
| scope-review | N | M |

### 5. 문서 동기화
- Apidog 업데이트: [Y/N, 요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. Codex 리뷰 기록
| 시점 | 수행 여부 | 핵심 피드백 | 반영 여부 |
|------|----------|------------|----------|
| Spec | Y/N | 요약 | Y/N/사유 |
| Plan | Y/N | 요약 | Y/N/사유 |
| 품질 리뷰 | Y/N | 요약 | Y/N/사유 |

### 8. 보완점
| # | 대상 스킬 | 보완 내용 | 적용 여부 |
|---|----------|----------|----------|
```

### 보완점 적용

> "위 보완점을 해당 스킬에 반영할까요? (전체/선택/건너뛰기)"

- **전체**: 모든 보완점을 해당 스킬 파일에 반영한다.
- **선택**: 유저가 번호로 선택한 항목만 반영한다.
- **건너뛰기**: 보고서만 출력하고 종료한다.

### 정리

`/tmp/workflow-state.md`의 모든 Phase를 `DONE/SKIPPED`으로 갱신하고 `Remaining Phases`를 `없음`으로 기록한다.
기본은 상태 파일을 보관한다. 사용자가 정리를 요청했거나 보관이 필요 없을 때만 삭제한다:

```bash
rm -f /tmp/workflow-state.md
```

---

## 흐름 요약

### 모드 판별

```
$ARGUMENTS 파싱
  ├─ --analyze / -a  → Analyze Mode
  ├─ --verify  / -v  → Verify Mode
  └─ (없음)          → Build Mode (기본)
```

### Analyze Mode (`--analyze`)

```
[유저 대화]
Phase A0: 범위 + 초점 수집
Phase A1: 상태 파일 생성

[자율 실행]
Phase A2: code-analyzer 에이전트        → 코드 분석

[유저 대화]
Phase A3: 분석 보고서 → 수정 여부 (유저 선택) → 정리
```

### Verify Mode (`--verify`)

```
[유저 대화]
Phase V0: 범위 + 초점 수집
Phase V1: 상태 파일 생성 + 정적 분석 (go vet, go build)

[자율 실행]
Phase V2: code-verifier 에이전트        → 코드 검증
Phase V3: convention-check              → 컨벤션 검사 (전체 초점 시만)

[유저 대화]
Phase V4: 종합 검증 보고서 → 수정 여부 (유저 선택) → 정리
```

### Build Mode (기본)

```
[유저 대화]
Phase 0: /request → Technical Spec (유저 확인)
Phase 0.5: Codex Spec 리뷰 → Spec 보완
Phase 1: 난이도 산정 (1-10)
Phase 1.5: 실행 전략 판정 (sequential / parallel-slices / fullstack)
           fullstack → /start-workflow-fs로 전환 후 종료
Phase 2: scope-reviewer 메모
Phase 3: Plan 작성 → 6관점 리뷰 (3+3 병렬) → Codex Plan 리뷰 → Plan 확정
         parallel-slices → Plan에 Slice 정의 추가
Phase 3.5: 상태 파일 생성 → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 4: 구현
  sequential:       workflow-implementer 1개   → 구현 + 커밋
  parallel-slices:  general-purpose 2~3개      → 병렬 구현 (커밋 유보) → 일괄 커밋
Phase 4.5: go build                    → 빌드 체크 (필수)
Phase 5: 품질 루프 (병렬 스캔 → 통합 수정 → 순차 실행, 최대 3회)
  Batch A [병렬 스캔, 읽기 전용]:
    5.0 go build + go test             → Bash 직접
    5.1 simplify (dry-run 후보)         → general-purpose 에이전트
    5.2 convention-check (위반 목록)    → general-purpose 에이전트
    5.4 scope-reviewer                 → scope-reviewer 에이전트
  통합 수정 [모인 이슈 일괄 반영]:
    general-purpose 1개                → 빌드/scope/convention/simplify 순서로 수정
  Batch B [순차 실행, 서버 점유]:
    5.3 e2e-test-loop                  → general-purpose 에이전트
    5.5 make test                      → Bash 직접
  → 수정 있으면 커밋 후 재시작, 없으면 탈출
Phase 5.6: Codex 품질 리뷰             → APPROVE까지 보완
Phase 6: workflow-doc-sync             → 문서 동기화 (API 변경 시만)
Phase 7: workflow-pr                   → PR 생성
Phase 8: workflow-reflection           → 성찰

[유저 대화]
Phase 9: 최종 보고 → 보완점 적용 (유저 선택) → 정리
```
