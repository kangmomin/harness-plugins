---
name: start-workflow
description: "전체 개발 워크플로우를 자동화한다. Build 모드(기본): 요청 분석 → 구현 → 품질 루프 → PR. Analyze 모드(--analyze): 코드 분석 보고서. Verify 모드(--verify): 보안·성능·버그·안정성 검증. '워크플로우 시작', '기능 구현해줘(전 과정 자동)', '코드 분석/검증해줘' 요청 시 사용."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명> | --analyze [경로] | --verify [경로]
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/start-workflow.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Start Workflow — Orchestrator

전체 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

**플레이스홀더 정의** (본문·references 공통, 값 변경은 여기 한 곳만 수정):

- `{STATE_FILE}` = `/tmp/workflow-state.md`
- `{IMPL_NOTES}` = `/tmp/implementation-notes.md`
- `{REPORT_DIR}` = profile의 `reportDir` (없으면 `.claude/harness-reports`)
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)
- `{buildCommand}` 등 profile 변수 = Pre-flight에서 로드

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. `/common:commit-hard-push` 방식. |
| `--no-tdd` | | Phase 6.1(테스트 우선)을 건너뛰고 곧바로 구현한다. 회귀 baseline도 수집하지 않는다. |
| `--analyze` | `-a` | **Analyze 모드**. 전체 또는 특정 범위의 코드를 분석하여 보고서를 생성한다. |
| `--verify` | `-v` | **Verify 모드**. 보안·성능·잠재 버그·안정성을 검증하고 PASS/WARN/FAIL 판정한다. |

### 모드 판별

| 조건 | 모드 | 실행 경로 |
|------|------|----------|
| `--analyze` 또는 `-a` 포함 | **Analyze** | Phase A1 → A4 |
| `--verify` 또는 `-v` 포함 | **Verify** | Phase V1 → V5 |
| 위 플래그 없음 | **Build** (기본) | Phase 1 → 12 |

- `--analyze`와 `--verify`는 상호 배타적이다. 동시 지정 시 유저에게 하나를 선택하도록 안내한다.
- `--hard`는 Build 모드에서만 유효하다. Analyze/Verify 모드에서는 무시한다. `$ARGUMENTS`에 `--hard`/`-h`가 있으면 `$HARD_MODE = true`.
- `--no-tdd`도 Build 모드 전용이다. `$ARGUMENTS`에 있으면 `$TDD = false` (기본값 `true`). Analyze/Verify 모드는 구현 Phase를 경유하지 않으므로 해당 없음.
- **범위 지정**: 플래그 뒤 경로가 있으면 분석/검증 범위로 사용한다. 없으면 전체 코드베이스 (profile의 `sourceDirs` 기준).
  예: `--analyze src/book`, `--verify src/book/handler.go`

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 5 브랜치 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 10 PR | workflow-pr (PR 생성) | 현재 브랜치에서 바로 push, PR 생략 |

> **Analyze/Verify 모드 진입 시 MUST**: 같은 폴더의 `references/analyze-verify-modes.md`를 Read하고 해당 모드 절차를 따른다. 이하 본문은 Build 모드를 정의한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 상태 추적

워크플로우 시작 시 `{STATE_FILE}`을 새로 만들고, Phase 진입/완료 때마다 갱신한다 (오케스트레이터도 Phase owner로 기록).
상태 파일은 `Current Phase` / `Phase Assignments` / `Remaining Phases` / `Phase Results` 섹션을 항상 포함한다 (템플릿: `references/templates.md`).

- 에이전트 생성 전: 해당 Phase를 `IN_PROGRESS`로 갱신
- 완료 후: `DONE` / `SKIPPED:{사유}` / `BLOCKED:{사유}` 와 결과 기록
- 모든 에이전트 프롬프트에 상태 파일 경로, 현재 Phase, 남은 Phase, 배정 model/effort를 포함

### Model / Effort 선택 규칙

Agent 생성 시 작업 복잡도·난이도·작업량에 맞춰 `model`과 `effort`를 명시한다.
환경별 모델명이 다르면 같은 등급의 사용 가능한 최신 모델로 치환한다.

| 등급 | 기준 | Claude 계열 | Codex 계열 | effort |
|------|------|-------------|------------|--------|
| Simple | 난이도 1-3, 1-3개 파일, 문서/단순 수정 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 난이도 4-6, 일반 구현/리뷰/테스트 수정 | sonnet | gpt-5.3-codex | medium |
| Complex | 난이도 7-8, 다중 레이어/API/DB/계약 영향 | opus | gpt-5.4 | high |
| Critical | 난이도 9-10, 보안/데이터 마이그레이션/대규모 리팩토링 | opus | gpt-5.5 | xhigh |

읽기 전용 리뷰는 기본 `Standard`, 보안/데이터 정합성/계약 변경 검토는 `Complex` 이상.
코드 수정 에이전트는 담당 파일 수와 실패 반복 횟수에 따라 한 단계 높일 수 있다.

## 자율 실행 규칙

```
[유저 대화] Phase 1~4 : Spec, 난이도, 전략, Plan+리뷰
[상태 저장] Phase 5   : 브랜치 + 상태 파일 + 회귀 baseline 수집
[자율 실행] Phase 6~11: 서브 에이전트 순차/병렬 위임 — 묻지 않고 자동 실행
[유저 대화] Phase 12  : 최종 보고 + 보완점 적용
```

### Spec 외 변경 금지 원칙

자율 실행 중 Spec에 명시되지 않은 동작 변경이 필요하다고 판단되면:
1. **코드를 수정하지 않고** 해당 사항을 기록한다.
2. Phase 12 보고서에 `[Assumption]` 태그로 표기하여 유저에게 가시화한다.
3. 유저 승인 후에만 해당 변경을 적용한다.

> 기술적으로 올바른 수정이라도, 유저가 방향을 결정하기 전에 코드를 건드리지 않는다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- Phase 6 완료 → 즉시 Phase 7 (같은 턴). Phase 8 내 각 단계도 완료 즉시 다음 단계. Phase 9~11 동일.
- **유저 응답 대기, 진행 여부 질문, 중간 보고 후 멈춤은 금지.**
- 유일한 정지 지점은 **Phase 12 (최종 보고)** 뿐이다.

### Implementation Notes (라이브 판단 기록)

자율 실행 중 발생하는 **설계 결정·편차·트레이드오프·미결 질문**을 코드와 분리해 `{IMPL_NOTES}`에 실시간으로 누적한다.
유저는 자율 실행 중에도 파일을 직접 열어 비동기로 피드백할 수 있고, Phase 12에서 HTML로 일괄 렌더링된다.

핵심 규칙 (파일 초기화 템플릿·4-섹션 구조: `references/templates.md`):

- 파일을 수정하는 자율 실행 에이전트는 4종 사건 발생 시 **코드 수정 전에** 해당 섹션에 한 줄 append.
- 읽기 전용 스캔 에이전트는 직접 쓰지 않는다 — 이슈 보고서에 포함하면 통합 수정 단계가 대신 기록.
- `[Assumption]` 보고와 동일한 항목은 `## 편차` 섹션에 동시 기록 (보고서와 라이브 노트 동기화).
- **append-only** — 기존 줄 수정·삭제 금지. 마크다운만 작성 (HTML/JSON 금지 — 렌더링이 깨진다).

## Pre-flight: 세션 환경 점검 (모든 모드 공통)

### 1. Project Profile 로드

`.claude/be-harness.local.md`를 Read하여 아래 값을 변수로 추출한다:

`{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{makeTestCommand}`,
`{runServerCommand}`, `{serverUrl}`, `{e2eEnabled}`, `{apiDocsPath}`,
`{sourceDirs}`, `{testDirs}`, `{mainBranch}`, `{featureBranchPrefix}`, `{hotfixBranchPrefix}`,
`{commitPrefixes}`, `{commitCoAuthor}`, `{projectConventions}`, `{language}`

profile이 없으면 안내 후 종료한다:
> "`.claude/be-harness.local.md` 가 없습니다. 먼저 `/be-harness:init`을 실행하세요."

### 2. SKIP 예정 Phase 사전 경고

profile 값을 근거로 누락 항목이 있으면 어떤 Phase가 SKIP될 것인지 **미리 확정**한다 (Phase 내부에서 실패 후 판정하지 않는다).

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `{buildCommand}` | 비어있지 않음 | Phase 7 빌드 체크 SKIP (위험: 컴파일 에러 조기 차단 불가) |
| `{testCommand}` | 비어있지 않음 | Phase 6.1 TDD·회귀 baseline SKIP + Phase 8.1 테스트 SKIP (위험: 회귀 탐지 불가) |
| `{lintCommand}` | 비어있지 않음 | Phase V2 정적 분석 일부 SKIP |
| `{e2eEnabled}` & `{runServerCommand}` & `{serverUrl}` | 모두 유효 | Phase 8.6 (e2e-test-loop) SKIP 예정 |
| `{apiDocsPath}` | 파일 존재 | Phase 9 (문서 동기화) SKIP 예정 |
| `{makeTestCommand}` | 비어있지 않음 | Phase 8.7 통합 테스트 SKIP |

- 모두 OK → 점검 결과 한 줄 요약 후 진행.
- 누락 있음 → 사전 경고 후 선택지:
  > "⚠️ profile 누락 필드: `{누락 목록}`. 이번 워크플로우에서 **{영향받는 Phase 목록}**는 SKIP됩니다.
  > 1. 이대로 진행 — 해당 Phase는 `SKIPPED:{사유}`로 기록하고 넘어감
  > 2. 중단 — `/be-harness:doctor`로 진단 후 `/be-harness:init`으로 재설정 권장"

---

# Build Mode (Phase 1 ~ 12)

## Phase 1: 작업 범위 수집 (Plan 모드 진입)

> **Plan 모드 활성화**: Phase 1 시작 시 `EnterPlanMode`를 활성화한다.
> Spec과 Plan은 같은 Plan 모드 컨텍스트에서 통합 산출물로 발전하며, `ExitPlanMode`는 Phase 4.4에서 단 한 번만 호출한다.

**분기 — 이미 상세 Spec이 제공된 경우**: `$ARGUMENTS` 또는 대화 컨텍스트가 아래를 **모두** 충족하면 `/request` 호출을 생략하고, 제공된 내용을 Technical Spec으로 직접 정리해 유저 확인을 받는다:
- 작업 유형이 명확 (생성/수정/검토/디버깅)
- 대상 API/기능이 특정됨
- 핵심 요구사항이 구체적으로 기술됨

**기본**: `/be-harness:request`를 호출하여 Technical Spec을 생성한다 (`$ARGUMENTS` 전달). 완료 후 Spec 전문과 엣지 케이스 목록을 보관하고, 작업 유형을 확인한다.

> 어느 경우든 Spec을 유저에게 보여주고 확인을 받는다.

## Phase 2: 난이도 산정

Technical Spec을 분석하여 1~10 난이도를 산정한다. **종합 난이도 = max(A, B)**.

### A. 코드 복잡도

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 레이어 | 단일 | 2개 | 3개 전체 |
| DB 변경 | 없음 | 컬럼 추가 | 신규 테이블 |
| 외부 연동 | 없음 | 기존 gRPC | 신규 gRPC |
| 비즈니스 복잡도 | 단순 CRUD | 조건 분기 3개 이하 | 상태 머신 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

### B. 영향 범위 리스크

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 기존 API 호환성 | Breaking change 없음 | 선택 필드 추가 | 필수 필드/응답 구조 변경 |
| DB 데이터 영향 | 신규 테이블만 | 기존 테이블 컬럼 추가 | 기존 데이터 마이그레이션 필요 |
| 공유 모듈 수정 | 없음 | 유틸리티/공통 함수 | 미들웨어/인터셉터/DI |
| 다른 서비스 의존 | 독립적 | 같은 repo 내 참조 | 외부 서비스 연동 변경 |
| 롤백 용이성 | 즉시 가능 | 마이그레이션 롤백 필요 | 데이터 복구 필요 |

출력: `난이도: 코드 [A]/10 + 리스크 [B]/10 — [근거]`

## Phase 3: 실행 전략 판정 (Batch Eligibility Gate)

아래 **5가지 조건을 모두 충족**해야 `parallel-slices`로 판정한다:

| # | 조건 | 확인 방법 |
|---|------|----------|
| 1 | Spec이 2~3개의 **수직 슬라이스**를 포함 | 각 슬라이스가 독립 endpoint/feature이며 각각 handler+usecase+repository를 가짐 |
| 2 | 슬라이스 간 **파일 겹침 없음** | 공유 VO, DTO, middleware, DI wiring 변경이 없음 |
| 3 | **DB migration/공통 계약 변경 없음** | 신규 테이블은 가능, 기존 테이블 수정·공유 인터페이스 변경은 불가 |
| 4 | 각 슬라이스가 **독립 빌드·테스트 가능** | 한 슬라이스만 구현해도 빌드가 깨지지 않음 |
| 5 | **순서 의존 없음** | A 완료 후에야 B 시작 가능한 관계가 없음 |

| 전략 | 조건 | 동작 |
|------|------|------|
| `sequential` | 위 조건 미충족 (기본값) | Phase 6 순차 실행 |
| `parallel-slices` | 5가지 조건 모두 충족, 슬라이스 2~3개 | Phase 6에서 슬라이스별 병렬 구현 |
| `fullstack` | FE+BE 동시 변경 | `/common:start-workflow --fs`로 전환 후 종료 |

> **대부분의 작업은 `sequential`이다.** 판단이 애매하면 `sequential` — 병렬화의 이점보다 잘못된 분리의 비용이 훨씬 크다.

출력: `실행 전략: [sequential/parallel-slices/fullstack] — [근거]`

`fullstack` 판정 시:

| 감지 | 행동 | 고지 문구 |
|------|------|----------|
| `/common:start-workflow` 가 세션에 존재 | Skill tool로 `--fs` 와 함께 호출 후 현재 워크플로우 종료 | "FE+BE 동시 변경이 필요합니다. `/common:start-workflow --fs`로 전환합니다." |
| common 미설치 | 선택지 제시 후 대기 | "FE+BE 동시 변경이 필요하지만 풀스택 오케스트레이션을 제공하는 `common` 이 설치되어 있지 않습니다.<br>1. `common` 설치 후 재시작 (권장) — `/plugin install common@harness-plugins`<br>2. 백엔드만 진행 — 프론트엔드 변경은 별도 작업으로 분리<br>3. 중단" |

## Phase 4: Plan 작성 + 리뷰

### Phase 4.1: Plan 작성

Spec 아래에 구현 계획을 추가하여 **Spec+Plan 단일 산출물**로 발전시킨다. Plan에 포함할 내용:

- 구현 순서 (파일 단위), 각 파일 변경 내용 요약
- **최종 코드 구조**: 중복 로직이 예상되면 최종 구조(테이블 드리븐, 공통 함수 추출 등)를 Plan 단계에서 확정 — 구현 후 리팩토링 커밋 방지
- 의존 관계, 예상 리스크

**parallel-slices 추가 요구사항**: Plan에 `## Slices` 섹션을 명시한다 (Slice별 제목/파일 범위/설명, 최대 3개).
슬라이스 간 파일 범위가 겹치면 `sequential`로 전략을 변경한다.

### Phase 4.2: 다관점 Plan 보강 (Claude, 1회)

검증 루프 진입 전 Claude 측 다관점 리뷰로 명백한 결함을 1회 보강한다. **이 단계는 검증 루프가 아니다.**

최대 3개 서브에이전트(`general-purpose`) 병렬 × 2배치:
- Batch 1: 유지보수성 + 성능 + 엣지 케이스
- Batch 2: 데이터 정합성 + 보안 + 기존 코드 영향

각 에이전트 프롬프트에 Spec 전문 + Plan 전문을 전달하고 아래 형식으로 받는다:

```
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [문제 목록 또는 "없음"]
**Suggestions**: [개선 제안 또는 "없음"]
```

종합: REJECT 1개+ → 해당 이슈를 Plan에 반영. CONCERN → 타당한 항목만 자동 반영.
→ 보강된 Plan을 **Plan v1 (검증 루프 입력)**으로 확정.

### Phase 4.3: Plan Verification Loop (Codex 검증, 최대 5회)

Plan은 Codex 검증 루프를 통과해야 확정된다.

```
for iteration in 1..5:
  ① Codex Plan 리뷰 (Architect 관점) — stateless 보완을 위해 매회 전달:
     Spec 전문 / Plan vN 전문 / 실행 전략 / 난이도 근거
     / (N≥2) 이전 iteration Diff 요약 + 기각 피드백·사유
     리뷰 관점: Spec-Plan 추적성, 레이어 책임 분리, 파일 소유권 충돌,
               테스트/검증 누락, 더 단순한 구현 경로
  ② 판정 처리:
     APPROVE → 루프 탈출
     CONCERN → 타당한 항목 반영 (또는 사유 기록 후 기각) → 다음 iteration
     REJECT  → Plan 수정 → 다음 iteration
  ③ Iteration Diff Log를 상태 파일 `Plan Verification Log`에 append:
     Verdict / 반영 / 기각+사유 / Plan 변경 요약
```

| 종료 조건 | 결과 |
|----------|------|
| Codex `APPROVE` | **PROCEED** → Phase 4.4 |
| 사용자가 명시적으로 루프 종료 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex 사용 불가 환경 | **CODEX-UNAVAILABLE** → 사유를 상태 파일에 기록하고 진행 |
| 5회 도달, 미APPROVE | **BLOCKED:MAX_ITERATIONS** → 아래 선택지 제시 |

5회 도달 시 선택지:
> "Plan 검증 루프가 5회에 도달했습니다. 미해결 이슈: {요약}
> 1. 현재 Plan으로 진행 — 잔존 이슈를 상태 파일에 기록하고 Phase 4.4로
> 2. 루프 계속 — 5회 추가 반복
> 3. 중단 — 워크플로우 종료"

안전장치:
- **동일 이슈 3회 반복 지적** → 사용자에게 보고하고 판단 위임 (응답 후 재개/종료)
- **변경 0건 iteration 발생** → 즉시 중단하고 사용자에게 보고 (무한 핑퐁 방지)

### Phase 4.4: Plan 확정

루프 종료 후 `ExitPlanMode` 실행. 상태 파일 하단에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 5: 브랜치 + 상태 파일 + Baseline + 자율 실행 시작

**브랜치 생성**:
- `$HARD_MODE = false`: 구현 전 반드시 feature 브랜치 생성 (`git checkout -b feat/{작업 요약 kebab-case}`). 이미 `feat/**`·`hotfix/**`면 건너뜀. main/master에 직접 커밋 금지.
- `$HARD_MODE = true`: 브랜치 생성 건너뜀. 현재 브랜치 그대로 사용.

**상태 파일 생성**:

> Phase 5 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고
> ① "상태 파일 템플릿"대로 `{STATE_FILE}`을 생성한다. Spec 전문, 정상 흐름·엣지 케이스 목록, 확정 Plan 전문, 실행 전략, (parallel-slices 시) Slices를 복사해 넣는다.
> ② "Implementation Notes 라이브 파일 초기화" 템플릿대로 `{IMPL_NOTES}`를 생성한다 (기존 파일 덮어쓰기).

**회귀 Baseline 수집 (TDD 활성 시)**:

> Phase 5 진입 시 MUST: 같은 폴더의 `references/tdd.md`를 Read하고 "TDD 적용 판정"과 "Phase 5: 회귀 Baseline 수집" 절차를 따른다.

여기가 **유저와 대화 가능한 마지막 지점**이다. baseline 수집이 실패하면 자율 실행에 들어가기 전에 선택지를 제시한다 (절차: `references/tdd.md`).
TDD SKIP 판정 시 사유를 `## Test Baseline`에 기록하고, 이후 Phase 6은 기존 단일 구현 흐름으로 진행한다.

출력:
- `sequential`: **"자율 실행을 시작합니다. Phase 6~11을 서브 에이전트로 순차 실행합니다."**
- `parallel-slices`: **"자율 실행을 시작합니다. [N]개 슬라이스를 병렬 구현합니다."**

## Phase 6 ~ 11: 자율 실행

> Phase 6 진입 시 MUST: 같은 폴더의 `references/agent-prompts.md`를 Read한다. Phase 6, 7, 9, 10, 11의 에이전트 프롬프트는 모두 이 문서의 해당 섹션을 사용한다.

각 Phase를 전용 서브 에이전트에 위임하고, 이전 에이전트 완료 후 다음을 실행한다. 각 반환 결과는 기록한다 (Phase 12 보고서에 사용).

### Phase 6: TDD 구현 (Red → Green)

> Phase 6 진입 시 MUST: 같은 폴더의 `references/tdd.md`를 Read한다. Phase 6.1의 프롬프트·판정·배리어는 모두 이 문서를 따른다.

`$TDD = false`이거나 Phase 5에서 `SKIPPED:*` 판정이면 **Phase 6.1을 건너뛰고 6.2만 실행한다** (기존 단일 구현 흐름과 동일).

#### Phase 6.1: 테스트 우선 (Red)

Spec의 추적 ID(`AC-nn`·`EC-nn`·`RC-nn`)를 근거로 **실패하는 테스트를 먼저 작성**한다. 근거 표 밖의 테스트는 작성하지 않는다.

- `sequential`: `general-purpose` 1개가 `/be-harness:unit-test --red` 실행
- `parallel-slices`: 슬라이스별 에이전트가 테스트·스텁만 작성 → **오케스트레이터가 배리어에서 1회 글로벌 Red 검증 후 기록·커밋**

| 종료 조건 | 결과 |
|----------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` → Phase 6.2 |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID 제외하고 Phase 6.2 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — TDD SKIP 후 Phase 6.2 진행 |
| baseline에 없던 기존 테스트가 실패 | `BLOCKED:REGRESSION_AT_RED` — 기록 후 Phase 6.2 진행 |

`BLOCKED:*`여도 자율 실행은 멈추지 않는다. 선택지 제시는 Phase 12로 이연한다.

#### Phase 6.2: 구현 (Green)

- `sequential`: `be-harness:workflow-implementer` 1개 → 구현 + 커밋
- `parallel-slices`: `general-purpose` 2~3개 병렬 (커밋·빌드 금지) → 완료 후 오케스트레이터가 일괄 커밋

TDD 활성 시 **테스트 파일 수정 금지** 규칙과 `[TestConflict]` 보고 규칙을 프롬프트에 추가한다 (`references/tdd.md`).

프롬프트·커밋 규칙: `references/agent-prompts.md`의 "Phase 6.2" 섹션.

### Phase 7: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

`{buildCommand}`가 비어있으면 `SKIPPED:PROFILE_EMPTY`로 기록하고 Phase 8로.

```bash
{buildCommand} 2>&1
```

| 결과 | 행동 |
|------|------|
| 성공 | Phase 8로 진행 |
| 실패 | build-fix 에이전트로 수정 (`references/agent-prompts.md`의 "Phase 7" 섹션) → 커밋 → 재시도 |
| **3회 시도 후에도 실패** | `BLOCKED:BUILD_FAIL` — 유저에게 에러 요약 보고 후 중단 |

### Phase 8: 품질 루프 (최대 3회)

> Phase 8 진입 시 MUST: 같은 폴더의 `references/quality-loop.md`를 Read하고 각 단계의 프롬프트·실행 상세를 따른다.

```
for iteration in 1..3:
  [Batch A — 병렬 스캔, 읽기 전용] 8.1 빌드+테스트 / 8.2 simplify / 8.3 convention / 8.4 scope
      → 이슈만 수집, 파일 수정 금지
  [Phase 8.5 — 통합 수정] 수집 이슈를 단일 에이전트가 일괄 수정
  [Batch B — 순차, 서버 점유] 8.6 e2e-test-loop → 8.7 통합 테스트

[루프 종료 후 1회] 8.8 Spec 정합 Read-back — 판정만, 코드 수정 없음
```

Phase 8.1 결과는 `## Test Baseline`과 대조해 `regression` / `pre_existing` / `new_red` / `flaky`로 분류한다 (절차: `references/tdd.md`의 "Phase 8: 회귀 대조").

**테스트 판정**: `PASS` = `regression` 0건 + `new_red` 0건 / `WARN` = `flaky`만 / `FAIL` = 그 외

| 종료 조건 | 결과 |
|----------|------|
| `modified == false` **AND** 테스트 판정 `PASS` | 루프 탈출 → Phase 8.8 |
| `modified == false` (TDD SKIP 시) | 루프 탈출 → Phase 8.8 |
| 그 외 | 커밋 후 다음 iteration |
| 3회 도달 & 미PASS | `BLOCKED:TEST_NOT_GREEN` 기록 → 강제 탈출 → Phase 8.8 |

수정이 0건이어도 테스트가 깨져 있으면 탈출하지 않는다 — 얼어붙은 테스트가 실패하는데 소스 수정이 없으면 루프가 "성공"으로 오종료되기 때문이다.
`BLOCKED:TEST_NOT_GREEN`이어도 **자율 실행은 중단하지 않고** 이후 Phase를 계속 진행하며, 선택지는 Phase 12에서 제시한다.

커밋: `git add [수정 파일들] && git commit -m "Fix: 품질 루프 수정 (반복 N)"`

**Phase 8.8은 루프 밖에서 1회만 실행한다.** Spec을 모르는 격리된 에이전트가 구현·검증 산출물에서 보장 동작을 복원하고, 오케스트레이터가 그것을 Spec·기존 코드와 대조해 이탈을 판정한다. 코드는 수정하지 않으며 결과는 Phase 12에서 유저에게 보고한다. 판정이 `FAIL`이어도 자율 실행은 멈추지 않는다.

완료 후: "Phase 8 완료: [루프 횟수]회, 총 [수정 건수]건 수정 / Read-back [PASS/WARN/FAIL] (A·C·E [N]건)"

### Phase 9: API 문서 동기화 (조건부)

아래 조건을 **모두** 만족할 때만 실행. 아니면 `SKIPPED:{사유}`:
- 작업 유형이 API 생성/수정/삭제
- `{apiDocsPath}`가 비어있지 않고 파일이 실제로 존재

프롬프트: `references/agent-prompts.md`의 "Phase 9" 섹션.

### Phase 10: PR / Push

- `$HARD_MODE = false`: `be-harness:workflow-pr` 에이전트로 PR 생성 (`references/agent-prompts.md`의 "Phase 10" 섹션). PR URL 보고 필수.
- `$HARD_MODE = true`: PR 생략, push 전에 Assumption Gate 스캔(base와의 diff 추가 라인 + 미push 커밋 메시지에서 `[Assumption]` 검색)을 수행한다. 0건이면 `git push origin $(git branch --show-current)` 후
  "Phase 10 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)" 출력. 발견 시 push를 보류하고 아래 BLOCKED 절차를 따른다.
- **Assumption Gate BLOCKED 처리**: workflow-pr이 `BLOCKED:ASSUMPTION_UNRESOLVED`를 보고하면(또는 --hard 스캔에서 발견되면) push/PR 없이 Phase 11로 진행하고, Phase 12 보고서에 태그 목록을 포함해 항목별 유저 확인을 받는다. 승인(태그 제거)·수정으로 태그가 모두 제거된 뒤 **Phase 10만 재실행**한다. 태그가 남아 있는 동안 push/PR은 금지.

### Phase 11: 성찰

`be-harness:workflow-reflection` 에이전트 실행 (`references/agent-prompts.md`의 "Phase 11" 섹션).

## Phase 12: 최종 보고

> Phase 12 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고 "Implementation Notes HTML 렌더링", "Workflow Report 템플릿", "보완점 적용 상세"를 따른다.

1. **HTML 렌더링**: `{IMPL_NOTES}` → `{REPORT_DIR}/{YYYYMMDD}-{task-name-kebab}-impl-notes.html` (템플릿 준수, 디렉토리 없으면 생성).
   그 다음 Phase 6~11 결과를 종합해 **Workflow Report**를 작성한다 (템플릿 준수 — 섹션 머리글 변경 금지). `## 미결 질문`이 1건 이상이면 보고서 최상단에 "사용자 확인 필요" 블록을 자동 삽입한다.
2. **TDD 미해결 항목 처리** (보고서 4.1 섹션이 비어있지 않을 때만): 자율 실행 중 이연된 `BLOCKED:*`·`[TestConflict]`·`[Breaking]`·`cannot_compile`을 각각 제시하고 결정을 받는다.
   Phase 6~8에서 유저 질문이 금지되어 이연된 항목들이므로 **여기가 첫 결정 지점**이다.
   - 결정에 따른 수정이 필요하면 그 자리에서 수행하고 커밋한다. 승인 전에는 수정하지 않는다.
   - "이번 범위 외" 판단 항목은 보고서에 `보류`로 남긴다.
3. **Read-back Diff 처리** (Phase 8.8 판정이 `WARN`/`FAIL`일 때만): 보고서 8번 섹션의 각 항목을 유저에게 제시하고 결정을 받는다.
   보완점 질문보다 **먼저** 처리한다 — 코드·Spec에 직접 영향을 주는 결정이기 때문이다.
   - 결정에 따른 코드/Spec 수정이 필요하면 그 자리에서 수행하고 커밋한다. 유저가 승인하기 전에는 수정하지 않는다 (Spec 외 변경 금지 원칙).
   - 유저가 "이번 범위 외"로 판단한 항목은 보고서에 `보류`로 남기고 넘어간다.
4. 보완점 반영 방식을 질문한다: ① 로컬에만 저장 (기본) ② 로컬 저장 + `/common:submit-feedback`으로 PR ③ 건너뛰기.
5. 적용 절차·append 규칙은 templates.md의 "보완점 적용 상세"를 따른다. 플러그인 원본은 절대 수정하지 않는다.
6. 정리: 상태 파일의 모든 Phase를 `DONE`/`SKIPPED:{사유}`로 갱신하고 `Remaining Phases`를 `없음`으로 기록.
   기본은 상태 파일과 라이브 노트를 **보관** (HTML 산출물은 `{REPORT_DIR}`에 영구 저장). 사용자가 정리를 요청한 경우에만 `rm -f {STATE_FILE} {IMPL_NOTES}`.
   HTML 산출물(`*-impl-notes.html`, `*-e2e-report.html`)은 자동 삭제하지 않는다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 (예: `SKIPPED:PROFILE_EMPTY`, `SKIPPED:USER_OPT_OUT`, `SKIPPED:NO_TEST_BASIS`) |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 (예: `BLOCKED:BUILD_FAIL`, `BLOCKED:MAX_ITERATIONS`, `BLOCKED:NO_VALID_RED`, `BLOCKED:REGRESSION_AT_RED`, `BLOCKED:TEST_NOT_GREEN`) |
| `PASS` / `WARN` / `FAIL` | Verify 모드 판정, 테스트 판정, Read-back 판정 |

TDD 진단 분류(`red_assertion`·`already_satisfied`·`cannot_compile`·`deferred_e2e`·`regression`·`pre_existing`·`new_red`·`flaky`)는 **상태 코드가 아니라 데이터**다.
`## TDD Test Map`과 회귀 대조 표의 셀 안에서만 쓰고, Phase Assignments의 Status 열에는 등장시키지 않는다 (`docs/skill-authoring.md` §5).

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/analyze-verify-modes.md` | `--analyze` / `--verify` 모드 진입 시 |
| `references/templates.md` | Phase 5 (상태 파일·라이브 노트), Phase 12 (HTML 렌더링·보고서·보완점) |
| `references/tdd.md` | Phase 5 (TDD 판정·baseline), Phase 6 진입 시 |
| `references/agent-prompts.md` | Phase 6 진입 시 (Phase 6.2/7/9/10/11 프롬프트) |
| `references/quality-loop.md` | Phase 8 진입 시 |

## 흐름 요약 (Build)

```
[유저 대화] — Phase 1~4 전체가 단일 EnterPlanMode 컨텍스트
Phase 1: EnterPlanMode → /request로 Technical Spec (유저 확인)
Phase 2: 난이도 산정 (1-10)
Phase 3: 실행 전략 판정 (sequential / parallel-slices / fullstack → /common:start-workflow --fs 로 전환)
Phase 4: Plan 작성 → 다관점 1회 보강 → Codex 검증 루프 (최대 5회) → ExitPlanMode
Phase 5: feature 브랜치 + 상태 파일 + implementation-notes.md + 회귀 baseline → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 6.1: 테스트 우선 (Red) — Spec ID 근거로 실패 테스트 선작성 + 스텁, Red 커밋
Phase 6.2: 구현 (Green) — 테스트 파일 수정 금지, baseline 대비 신규 실패 0건까지
Phase 7: {buildCommand} 빌드 체크 (실패 시 수정 최대 3회)
Phase 8: 품질 루프 최대 3회 (병렬 스캔 8.1~8.4 → 통합 수정 8.5 → e2e 8.6 → 통합 테스트 8.7)
         탈출 조건 = 수정 0건 AND 테스트 판정 PASS (회귀 3분류 대조)
         루프 종료 후 8.8 Spec 정합 Read-back 1회 (격리 복원 → Diff 판정, 수정 없음)
Phase 9: API 문서 동기화 (API 변경 시만)
Phase 10: PR 생성 (--hard: push만)
Phase 11: 성찰

[유저 대화]
Phase 12: impl-notes HTML 렌더링 → 최종 보고 (미결 질문 상단 표면화) → 보완점 적용 → 정리
```
