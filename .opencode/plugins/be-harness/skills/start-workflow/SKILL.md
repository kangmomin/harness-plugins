---
name: start-workflow
description: "전체 개발 워크플로우를 자동화. Build 모드(기본): 요청 분석 → 구현 → 품질 루프 → PR. Analyze 모드(--analyze): 코드 분석 보고서. Verify 모드(--verify): 보안·성능·버그·안정성 검증."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명> | --analyze [경로] | --verify [경로]
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/start-workflow.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Start Workflow — Orchestrator

전체 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. `commit-hard-push` 사용. |
| `--analyze` | `-a` | **Analyze 모드**. 전체 또는 특정 범위의 코드를 분석하여 보고서를 생성한다. |
| `--verify` | `-v` | **Verify 모드**. 보안·성능·잠재 버그·안정성을 검증하고 Pass/Fail 판정한다. |

`$ARGUMENTS`에 `--hard` 또는 `-h`가 포함되어 있으면 `$HARD_MODE = true`로 설정한다.

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 3.5 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 4 커밋 | 동일 | 동일 |
| Phase 7 PR | workflow-pr (브랜치 생성 + PR) | **commit-hard-push** (현재 브랜치에서 바로 push, PR 생략) |

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
- `--analyze src/book` → `src/book` 디렉토리 분석
- `--verify src/book/usecase` → 해당 디렉토리 검증
- `--analyze` (경로 없음) → 전체 코드베이스 (profile의 `sourceDirs` 기준)
- `--verify src/book/handler.go` → 특정 파일만 검증

---

```
[유저 대화] Phase 0~1.5: 직접 실행 (Spec, 난이도, 실행 전략)
[유저 대화] Phase 2~3  : 직접 실행 (Plan, 리뷰)
[상태 저장] Phase 3.5  : 상태 파일 생성
[자율 실행] Phase 4~8  : 서브 에이전트 순차/병렬 위임
[유저 대화] Phase 9    : 최종 보고 + 보완점 적용
```

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

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

### 1. Project Profile 로드

`.claude/be-harness.local.md` 를 Read하여 아래 값을 변수로 추출한다:

- `{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{makeTestCommand}`
- `{runServerCommand}`, `{serverUrl}`, `{e2eEnabled}`, `{apiDocsPath}`
- `{sourceDirs}`, `{testDirs}`, `{mainBranch}`
- `{featureBranchPrefix}`, `{hotfixBranchPrefix}`
- `{commitPrefixes}`, `{commitCoAuthor}`
- `{projectConventions}` (파일 경로 배열)
- `{language}`

profile이 없으면:
> "`.claude/be-harness.local.md` 가 없습니다. 먼저 `/be-harness:init`을 실행하세요."

그리고 워크플로우를 종료한다.

### 2. SKIP 예정 Phase 사전 경고

profile 값을 근거로 **누락 항목이 있으면 어떤 Phase가 SKIP될 것인지** 사전 경고한다.

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `{buildCommand}` | 비어있지 않음 | Phase 4.5 빌드 체크 SKIP (위험: 컴파일 에러 조기 차단 불가) |
| `{testCommand}` | 비어있지 않음 | Phase 5.0 테스트 SKIP |
| `{lintCommand}` | 비어있지 않음 | Phase V1 정적 분석 일부 SKIP |
| `{e2eEnabled}` & `{runServerCommand}` & `{serverUrl}` | 모두 유효 | **Phase 5.3 (e2e-test-loop) SKIP 예정** |
| `{apiDocsPath}` | 파일 존재 | **Phase 6 (문서 동기화) SKIP 예정** |
| `{makeTestCommand}` | 비어있지 않음 | Phase 5.5 통합 테스트 SKIP |

**처리 규칙**:
- 모두 OK → 점검 결과 한 줄 요약 후 다음 단계 진행
- 누락 있음 → 아래 사전 경고를 출력한다:

  > ⚠️ profile 누락 필드: `{누락 목록}`. 이번 워크플로우에서 **{영향받는 Phase 목록}**는 SKIP됩니다.
  > 정상 실행을 원하면 `/be-harness:doctor` 로 진단 후 `/be-harness:init` 으로 재설정하세요. 이대로 진행하시겠습니까?

  - 사용자가 진행하면 해당 Phase에서는 `SKIPPED` 플래그를 붙여 넘긴다.
  - 사용자가 중단하면 여기서 종료한다.

> 이 사전 경고는 각 Phase 내부에서 실패 후 판정하지 않고, Phase 0에서 **미리 SKIP 예정 스테이지를 확정**하기 위함이다.

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
  subagent_type: be-harness:code-analyzer
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 코드 분석을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    
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

#### 정적 분석 실행

profile 값을 사용해 순차 실행한다 (비어있는 명령은 SKIP). 실행할 명령이 실제로 존재하는지는 `doctor` 결과에 의존한다.

```bash
{lintCommand}      # 비어있으면 SKIP
{buildCommand}     # 비어있으면 SKIP
{typeCheckCommand} # 비어있으면 SKIP
```

테스트 커버리지가 초점에 포함된 경우 (`전체` 또는 `안정성`):
```bash
{testCommand}      # 프로젝트가 coverage 플래그를 지원하면 init에서 testCommand에 포함
```

결과를 상태 파일에 append한다. SKIP된 명령은 `SKIPPED: (profile empty)` 로 기록.

출력: **"코드 검증을 시작합니다."**

### Phase V2: 코드 검증

```
Agent tool:
  subagent_type: be-harness:code-verifier
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 코드 검증을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}

    검증 범위: {scope}
    검증 초점: {focus}
    정적 분석 결과:
    [lint 결과]
    [build 결과]
    [typecheck 결과]
    [test/coverage 결과 (실행한 경우)]

    검증 완료 후 출력 형식에 따라 보고서를 작성하세요.
```

### Phase V3: 컨벤션 검사 (선택적)

검증 초점에 `전체`가 포함되어 있을 때만 실행한다.

```
Agent tool:
  subagent_type: general-purpose
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /be-harness:convention-check 를 실행하세요.
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
| lint | PASS/FAIL/SKIPPED | {요약} |
| build | PASS/FAIL/SKIPPED | {요약} |
| typecheck | PASS/FAIL/SKIPPED | {요약} |
| test/coverage | PASS/FAIL/SKIPPED ({%}) | 실행한 경우만 |

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

위 조건을 충족하지 않으면 `/be-harness:request`를 호출하여 Technical Spec을 생성한다.

- `$ARGUMENTS`가 있으면 request 스킬에 전달한다.
- request 스킬이 완료되면 생성된 **Technical Spec** 전문을 보관한다.
- Spec에서 **작업 유형** (생성/수정/검토/디버깅)을 확인한다.

> 어느 경우든 Spec을 유저에게 보여주고 확인을 받는다.

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

> 난이도 7+: Phase 3에서 Codex 리뷰 추가.

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
| `fullstack` | FE+BE 동시 변경 | `/fs-harness:start-workflow`로 리다이렉트 후 종료 |

> **대부분의 작업은 `sequential`이다.** `parallel-slices`는 명확히 독립적인 수직 슬라이스가 존재할 때만 적용한다.
> 판단이 애매하면 `sequential`을 선택한다 — 병렬화의 이점보다 잘못된 분리의 비용이 훨씬 크다.

출력: `실행 전략: [sequential/parallel-slices/fullstack] — [근거]`

`fullstack` 판정 시:
> "FE+BE 동시 변경이 필요합니다. `/fs-harness:start-workflow`로 전환합니다."
> → `Skill tool`로 `/fs-harness:start-workflow`를 호출하고 현재 워크플로우를 종료한다.

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
당신은 [관점명] 리뷰어입니다.
아래 Plan을 [관점] 관점에서만 리뷰하세요.

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

### 3.3 Codex 리뷰 (난이도 7+)

Codex 사용 가능 시 Architect 관점으로 Plan 리뷰를 위임한다.
불가 시 건너뛴다.

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

## Execution Strategy
[sequential/parallel-slices]

## Edge Cases
[엣지 케이스 목록]

## Plan
[확정된 Plan 전문 그대로 복사]
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

### Phase 4: 구현

#### sequential 모드 (기본)

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    
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
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고, 아래 슬라이스만 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    
    ## 담당 슬라이스
    제목: {Slice N 제목}
    파일 범위: {Slice N 파일 목록}
    설명: {Slice N 설명}
    
    ## 제한사항 (CRITICAL)
    - **위 파일 범위에 해당하는 파일만 수정하세요.** 범위 밖 파일은 절대 수정하지 않습니다.
    - **git commit을 하지 마세요.** 코드 구현만 수행합니다. 커밋은 오케스트레이터가 처리합니다.
    - **빌드 명령을 실행하지 마세요.** 빌드 검증은 오케스트레이터가 처리합니다.
    
    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.
    
    구현 완료 후 변경 파일 목록, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

모든 슬라이스 에이전트 완료 후, 오케스트레이터가 일괄 커밋:

```bash
git add [전체 변경 파일]
git commit -m "Add: [작업 요약] (병렬 슬라이스 구현)"
```

(profile의 `commitCoAuthor` 가 비어있지 않으면 `Co-Authored-By` 라인을 본문에 추가한다)

완료 후 유저에게 간략 보고: "Phase 4 완료: [N]개 슬라이스 병렬 구현, [변경 파일 수]개 파일"

### Phase 4.5: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

구현 에이전트 완료 즉시, 품질 루프 진입 전에 **반드시 빌드 체크를 실행**한다.
컴파일/타입 오류를 조기에 잡아 핫픽스를 방지한다.

profile의 `{buildCommand}` 가 비어있지 않으면:

```bash
{buildCommand} 2>&1
```

비어있으면 이 Phase를 `SKIPPED`로 기록하고 Phase 5로 진행한다.

- **성공** → Phase 5로 진행.
- **실패** → general-purpose 에이전트를 생성하여 빌드 에러를 수정한다:
  ```
  Agent tool:
    subagent_type: general-purpose
    prompt: |
      프로젝트 루트 {CWD}에서 `{buildCommand}` 빌드 에러를 수정하세요.
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

  [Batch B — 순차] 5.3 e2e-test-loop → 5.5 통합 테스트
      └─ 서버 점유 / 환경 자원이 걸리므로 순차 유지

  수정 있음? → 커밋 후 다음 iteration
  수정 없음? → 루프 탈출
```

#### Batch A: 병렬 스캔 (5.0 + 5.1 + 5.2 + 5.4)

네 단계를 **하나의 메시지에서 동시에 호출**한다. 모든 서브 에이전트는 **이슈 목록만 반환하며 파일을 수정하지 않는다**.
파일 수정은 다음 단계인 "통합 수정"에서 일괄 처리하여 에이전트 간 파일 편집 경합을 제거한다.

```
# 같은 메시지에서 4개 병렬 호출

[1] 5.0 빌드 + 테스트 — Bash로 직접 실행 (에이전트 아님)
    {buildCommand} && {testCommand} 2>&1
    (둘 중 하나라도 비어있으면 해당 단계 SKIP)
    → 에러 로그를 Batch A 결과에 수집. 파일 수정 없음.

[2] 5.1 Simplify Scan
    Agent tool:
      subagent_type: general-purpose
      prompt: |
        프로젝트 루트 {CWD}에서 /be-harness:simplify-loop 를 **dry-run** 관점으로 실행하세요.
        **파일을 수정하지 말고** 단순화 후보 목록만 반환하세요.
        각 항목: {file:line, 현재 코드 요약, 제안 변경, 근거}.
        완료 후 "후보: N건" 형식으로 보고하세요.

[3] 5.2 Convention Check Scan
    Agent tool:
      subagent_type: general-purpose
      prompt: |
        프로젝트 루트 {CWD}에서 /be-harness:convention-check 를 실행하세요.
        **파일을 수정하지 말고** 위반 목록만 반환하세요.
        각 항목: {file:line, 위반 규칙, 제안 수정}.
        완료 후 "위반: N건" 형식으로 보고하세요.

[4] 5.4 Scope Review
    Agent tool:
      subagent_type: be-harness:scope-reviewer
      prompt: |
        상태 파일 `/tmp/workflow-state.md`의 Technical Spec을 기준으로
        현재 구현된 코드를 검증하세요. 프로젝트 루트: {CWD}.
        누락/불일치 항목만 반환하고 파일은 수정하지 마세요.
```

> **CRITICAL**: Batch A의 에이전트는 모두 읽기/분석만 수행한다. 같은 메시지에서 병렬 실행해도 편집 충돌이 발생하지 않는다.
> 만약 에이전트가 파일을 수정했다면 해당 변경을 **무시**하고 이슈 목록만 채택한다 (오케스트레이터가 일괄 수정 시 기준 상태에서 다시 편집).

#### 통합 수정

Batch A에서 수집된 이슈(빌드/테스트 에러 + simplify 후보 + convention 위반 + scope 누락)가 하나라도 있으면, **단일 `general-purpose` 에이전트**에 일괄 위임한다:

```
Agent tool:
  subagent_type: general-purpose
  prompt: |
    프로젝트 루트 {CWD}에서 아래 이슈 목록을 순서대로 수정하세요.

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

#### Batch B: 순차 실행 (5.3 → 5.5)

서버/테스트 프로세스가 포트·DB·바이너리를 점유하므로 순차로 실행한다.

##### 5.3 E2E Test

```
Agent tool:
  subagent_type: general-purpose
  prompt: |
    프로젝트 루트 {CWD}에서 /be-harness:e2e-test-loop 를 실행하세요.
    결과가 `[SKIPPED:*]`이면 스킵 사유를 그대로 보고하세요.
    완료 후 "이슈: N건, 수정: Y/N, 스킵 사유: {있으면}" 형식으로 보고하세요.
```
- `SKIPPED` 반환 시 → `modified`에 영향 주지 않고 다음 단계 진행 (루프 재시작 트리거 아님)
- "수정: Y" → `modified = true`

##### 5.5 통합 테스트 (선택)

profile의 `{makeTestCommand}` 가 비어있지 않으면 Bash로 직접 실행:

```bash
{makeTestCommand}
```

비어있으면 이 단계를 `SKIPPED`로 기록하고 넘어간다.

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

### Phase 6: API 문서 동기화 (조건부)

아래 조건을 **모두** 만족할 때만 실행. 하나라도 어긋나면 `SKIPPED`.

- 작업 유형이 API 생성/수정/삭제
- profile의 `{apiDocsPath}` 가 비어있지 않고 파일이 실제로 존재

```
Agent tool:
  subagent_type: general-purpose
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 API 문서({apiDocsPath})를 동기화하세요.
    작업 유형: {Task Type}
    프로젝트 루트: {현재 작업 디렉토리}
    API 문서 파일: {apiDocsPath}

    [규칙]
    - 문서 포맷(OpenAPI/Swagger/Postman 등)을 파일 확장자/내용으로 자동 판정.
    - 새로 추가/변경된 엔드포인트·필드만 반영. 무관한 영역은 건드리지 않음.
    - 문서 생성/푸시 도구(외부 서비스)는 사용하지 않는다. 파일 편집으로 끝낸다.
    - 변경 후 `git diff {apiDocsPath}` 결과를 요약해 보고.
```

외부 API 문서 플랫폼(Apidog, Postman 등) 동기화가 필요하면 **프로젝트 쪽에 별도 스크립트/훅을 두고** 이 Phase 이후에 수동 실행한다.
be-harness는 파일 기반 동기화만 보장한다.

### Phase 7: PR / Push

- **`$HARD_MODE = false`** (일반):
  ```
  Agent tool:
    subagent_type: be-harness:workflow-pr
    prompt: |
      상태 파일 `/tmp/workflow-state.md`를 읽고 PR을 생성하세요.
      프로젝트 루트: {현재 작업 디렉토리}
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
  subagent_type: be-harness:workflow-reflection
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
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
- API 문서 동기화: [Y/N/SKIPPED, 요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점 (프로젝트 오버라이드로 반영)
| # | 대상 스킬/에이전트 | 보완 내용 | 저장 경로 | 적용 여부 |
|---|----------|----------|----------|----------|
| 1 | /be-harness:commit | [내용] | `.claude/be-harness/skills/commit.md` | Y/N |
| 2 | be-harness:workflow-implementer | [내용] | `.claude/be-harness/agents/workflow-implementer.md` | Y/N |
```

### 보완점 적용

플러그인 원본(`be-harness/skills/...` 아래 파일)은 **절대 수정하지 않는다**. 보완점 반영 경로는 두 가지가 있다:

| 경로 | 대상 | 적용 범위 |
|------|------|----------|
| **로컬 오버라이드** | `.claude/be-harness/{common,skills,agents}/...` | 현 프로젝트에만 |
| **커뮤니티 피드백 PR** | 플러그인 레포 `be-harness/community-feedback/...` | 큐레이션 후 모든 사용자에게 |

상세 규약: 플러그인 루트 `OVERRIDES.md` + `community-feedback/README.md`.

> "보완점 반영 방식을 선택하세요:"
>
> 1. **로컬에만 저장** (기본값) — `.claude/be-harness/...` 에 append. 이 프로젝트에만 적용.
> 2. **로컬 저장 + 플러그인 레포에 PR** — 로컬 저장 후 `/be-harness:submit-feedback` 을 호출하여 `kangmomin/harness-plugins` 레포의 community-feedback 영역에 PR 제출. 범용성 있는 피드백에 권장.
> 3. **건너뛰기** — 보고서만 출력하고 종료.

- 전체/선택 세부 반영 여부는 먼저 위 옵션 선택 후 각 보완점마다 Y/N 선택.
- 옵션 2 선택 시, 각 보완점에 대해 `generality` 필드(범용 / 특정 조건 / 프로젝트 한정)를 함께 수집. `프로젝트 한정`은 로컬 저장만 하고 PR 대상에서 제외.

#### 옵션 2 세부 흐름

1. 로컬 오버라이드에 append 먼저 수행 (옵션 1과 동일).
2. PR 제출 대상 후보(generality: 범용 / 특정 조건)를 정리.
3. `Skill tool` 로 `/be-harness:submit-feedback` 을 호출하며 후보 리스트 전달.
4. submit-feedback 이 `[SKIPPED:*]` 반환 시(gh 미설치/미인증/네트워크 실패 등) 로컬 저장만 완료된 상태로 워크플로우 정상 종료, 유저에게 fallback 사유를 보고.
5. 성공 시 PR URL 을 최종 보고서에 포함.

#### append 규칙

대상이 스킬이면: `.claude/be-harness/skills/{skill-name}.md`
대상이 에이전트면: `.claude/be-harness/agents/{agent-name}.md`
공통(여러 스킬에 적용)이면: `.claude/be-harness/common.md`

파일이 없으면 새로 생성하고 frontmatter를 헤더로 넣는다:

```markdown
---
scope: skill:{name}          # 또는 agent:{name} / common
applies-to: be-harness@{버전}+
updated: {YYYY-MM-DD}
---

# Project Override: {대상}

## 보완점 (auto-appended {YYYY-MM-DD HH:mm})
- [보완 내용 1]
- [보완 내용 2]
```

파일이 이미 있으면 기존 `## 보완점 (auto-appended ...)` 뒤에 새 섹션을 append (중복 판단은 내용 일치 여부로, 동일 내용이면 건너뜀).

추가 후 해당 파일 경로를 유저에게 보고한다:

> "프로젝트 오버라이드 업데이트 완료:
>  - `.claude/be-harness/skills/commit.md` (+2줄)
>  - `.claude/be-harness/agents/workflow-implementer.md` (신규 생성)
> 다음 워크플로우 실행 시 자동으로 로드됩니다. Git에 커밋을 권장합니다."

### 정리

상태 파일을 삭제한다:

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
Phase V1: 상태 파일 생성 + 정적 분석 ({lintCommand}, {buildCommand}, {typeCheckCommand})

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
Phase 1: 난이도 산정 (1-10)
Phase 1.5: 실행 전략 판정 (sequential / parallel-slices / fullstack)
           fullstack → /fs-harness:start-workflow로 전환 후 종료
Phase 2: scope-reviewer 메모
Phase 3: Plan 작성 → 6관점 리뷰 (3+3 병렬) → [난이도 7+: Codex] → Plan 확정
         parallel-slices → Plan에 Slice 정의 추가
Phase 3.5: 상태 파일 생성 → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 4: 구현
  sequential:       workflow-implementer 1개   → 구현 + 커밋
  parallel-slices:  general-purpose 2~3개      → 병렬 구현 (커밋 유보) → 일괄 커밋
Phase 4.5: {buildCommand}              → 빌드 체크 (buildCommand 비어있으면 SKIP)
Phase 5: 품질 루프 (병렬 스캔 → 통합 수정 → 순차 실행, 최대 3회)
  Batch A [병렬 스캔, 읽기 전용]:
    5.0 {buildCommand} + {testCommand} → Bash 직접
    5.1 simplify (dry-run 후보)         → general-purpose 에이전트
    5.2 convention-check (위반 목록)    → general-purpose 에이전트
    5.4 scope-reviewer                 → scope-reviewer 에이전트
  통합 수정 [모인 이슈 일괄 반영]:
    general-purpose 1개                → 빌드/scope/convention/simplify 순서로 수정
  Batch B [순차 실행, 서버 점유]:
    5.3 e2e-test-loop                  → general-purpose 에이전트
    5.5 {makeTestCommand}              → Bash 직접 (비어있으면 SKIP)
  → 수정 있으면 커밋 후 재시작, 없으면 탈출
Phase 6: workflow-doc-sync             → 문서 동기화 (API 변경 시만)
Phase 7: workflow-pr                   → PR 생성
Phase 8: workflow-reflection           → 성찰

[유저 대화]
Phase 9: 최종 보고 → 보완점 적용 (유저 선택) → 정리
```
