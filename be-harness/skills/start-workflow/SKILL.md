---
name: start-workflow
description: "전체 개발 워크플로우를 자동화한다. Build 모드(기본): 요청 분석 → 구현 → 품질 루프 → PR. Analyze 모드(--analyze): 코드 분석 보고서. Verify 모드(--verify): 보안·성능·버그·안정성 검증. '워크플로우 시작', '기능 구현해줘(전 과정 자동)', '코드 분석/검증해줘' 요청 시 사용."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명> [--codex none|mix|max] [--codex-models {slot}={provider}/{model}[@{effort}],…] | --analyze [경로] | --verify [경로]
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
- `{WORK_REPORT}` = `/tmp/workflow-report-{run_id}.md` (`run_id` = `## Flags`의 `RUN_ID`)
- `{PLAN_MAX}` = Phase 4.3 상한 (standard 5 / light 2) · `{QL_MAX}` = Phase 8 상한 (standard 3 / light 2)
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)
- `{buildCommand}` 등 profile 변수 = Pre-flight에서 로드

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. `/common:commit-hard-push` 방식. |
| `--no-tdd` | | Phase 6.1(테스트 우선)을 건너뛰고 곧바로 구현한다. 회귀 baseline도 수집하지 않는다. 검증 티어는 standard 강제. |
| `--reflect` | | Phase 11(성찰)을 실행한다. 미지정 시 Phase 11은 `SKIPPED:REFLECT_NOT_REQUESTED` (주기 실행 권장 — 워크플로우 5~10회마다 1회). |
| `--tier standard` | | Phase 2 판정과 무관하게 검증 티어를 standard로 강제한다 (light 축소 비활성). light 강제 플래그는 없다. |
| `--codex {none\|mix\|max}` | | Codex 사용 모드를 지정하고 profile `codexMode`에 저장한다 (모든 모드 공통). 미지정 시 profile → 질문(권장 `mix`). 정의·호출 계약·실패 정책: `references/codex-mode.md` |
| `--codex-models {슬롯}={provider}/{model}[@{effort}] \| default[,…]` | | Codex 위임 모델 슬롯(`review`·`explore`·`judge`·`write`)을 지정하고 profile `codexModels`에 저장한다 (`--codex none`이면 N/A). 문법·병합·검증: `references/codex-mode.md` §2.1 |
| `--analyze` | `-a` | **Analyze 모드**. 전체 또는 특정 범위의 코드를 분석하여 보고서를 생성한다. |
| `--verify` | `-v` | **Verify 모드**. 보안·성능·잠재 버그·안정성을 검증하고 PASS/WARN/FAIL 판정한다. |

### 모드 판별

| 조건 | 모드 | 실행 경로 |
|------|------|----------|
| `--analyze` 또는 `-a` 포함 | **Analyze** | Phase A1 → A4 |
| `--verify` 또는 `-v` 포함 | **Verify** | Phase V1 → V5 |
| 위 플래그 없음 | **Build** (기본) | Phase 1 → 12 |

- `--analyze`와 `--verify`는 상호 배타적이다. 동시 지정 시 유저에게 하나를 선택하도록 안내한다.
- Build 모드 전용 플래그 (Analyze/Verify 모드에서는 무시 — 구현 Phase를 경유하지 않음): `$ARGUMENTS`에 `--hard`/`-h`가 있으면 `$HARD_MODE = true` · `--no-tdd`면 `$TDD = false` (기본값 `true`) · `--reflect`면 `$REFLECT = true` (기본값 `false` — Phase 11 실행 여부) · `--tier standard`면 `$TIER_FORCE = true` (기본값 `false` — Phase 2 게이트에서 standard 강제).
- **범위 지정**: 플래그 뒤 경로가 있으면 분석/검증 범위로 사용한다. 없으면 전체 코드베이스 (profile의 `sourceDirs` 기준).
  예: `--analyze src/book`, `--verify src/book/handler.go`

> **Analyze/Verify 모드 진입 시 MUST**: 같은 폴더의 `references/analyze-verify-modes.md`를 Read하고 해당 모드 절차를 따른다. 이하 본문은 Build 모드를 정의한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 상태 추적

워크플로우 시작 시 `{STATE_FILE}`을 새로 만들고, Phase 진입/완료 때마다 갱신한다 (오케스트레이터도 Phase owner로 기록).
상태 파일은 `Flags` / `Current Phase` / `Phase Assignments` / `Remaining Phases` / `Verification Tier` / `Codex Runtime` / `Phase Results` 섹션을 항상 포함한다 (템플릿: `references/templates.md`).

- 에이전트 생성 전: 해당 Phase를 `IN_PROGRESS`로 갱신
- 완료 후: `DONE` / `SKIPPED:{사유}` / `BLOCKED:{사유}` 와 결과 기록
- 모든 에이전트 프롬프트에 상태 파일 경로, 현재 Phase, 남은 Phase, 배정 model/effort를 포함
- `## Flags`(MODE·HARD_MODE·TDD·REFLECT·TIER·CODEX·CODEX_MODELS·RUN_ID·START_SHA)는 컨텍스트 요약·세션 재개로 CLI 인자를 잃은 뒤 이어갈 때 **유일한 기준** — CLI 인자와 충돌하면 기록값 우선 + 고지. `RUN_ID`는 Phase 5에서 1회 생성하며 재생성하지 않는다.

### Model / Effort 선택 규칙

Agent 생성 시 작업 복잡도·난이도·작업량에 맞춰 `model`과 `effort`를 명시한다.
환경별 모델명이 다르면 같은 등급의 사용 가능한 최신 모델로 치환한다.

등급표 적용 전 **작업 성격을 먼저 판정**한다 — 탐색·이해 작업에 상위 모델을 쓰지 않는 것이 컨텍스트 절감의 핵심이다:

| 작업 성격 | 예 | model / effort |
|----------|-----|----------------|
| 탐색·수집 | 파일/심볼 위치 찾기, 사용처 나열, 패턴 grep, 설정값 수집 | haiku / low |
| 이해·요약 | 모듈 동작 요약, 코드 흐름 설명, Phase 8.8 복원 | sonnet / medium |
| 판단·구현 | 코드 수정, 리뷰 판정(Phase 8.4 scope 등), 설계 결정 | 아래 등급표 적용 |

| 등급 | 기준 | model | effort |
|------|------|-------|--------|
| Simple | 난이도 1-3, 1-3개 파일, 문서/단순 수정 | sonnet | low |
| Standard | 난이도 4-6, 일반 구현/리뷰/테스트 수정 | sonnet | medium |
| Complex | 난이도 7-8, 다중 레이어/API/DB/계약 영향 | opus | high |
| Critical | 난이도 9-10, 보안/데이터 마이그레이션/대규모 리팩토링 | opus | xhigh |

읽기 전용 리뷰는 기본 `Standard`, 보안/데이터 정합성/계약 변경 검토는 `Complex` 이상.
코드 수정 에이전트는 담당 파일 수와 실패 반복 횟수에 따라 한 단계 높일 수 있다.
검증·리뷰의 **판정**을 탐색·이해 작업으로 분류해 강등하지 않는다 (검출력 보존. 유일한 예외: 사망 복구 2차 재시도의 1단계 강등 — "축소 실행 내역"으로 고지).
등급표는 Claude 경로에만 적용한다 — `codexMode: max`의 실행 주체·모델(Codex 슬롯 — 기본 OpenAI luna·sol)과 리뷰어 effort는 `references/codex-mode.md`가 정의한다.

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

### 탐색 위임 규칙 (오케스트레이터 컨텍스트 규율)

탐색·수집 작업(위치/사용처/패턴 grep/설정값 확인)이 3건 이상 쌓이면 오케스트레이터가 직접 실행하지 않고, **탐색 에이전트 1개에 3~10개 질문을 묶어** 위임한다 (haiku/low — 부팅 고정 비용 때문에 1질문 1에이전트 금지).
반환 계약(프롬프트에 명시): 답변 = `file:line` + 핵심 스니펫 최대 5줄 + 한 줄 결론. 파일 전문 붙여넣기 금지. **'없음' 답변은 검색한 패턴·경로 목록을 반드시 동반**한다 (부재 주장을 검증 가능하게).
예외: ① 부재 여부가 Plan을 바꾸는 결정적 질문은 sonnet 이상 위임 또는 오케스트레이터 직접 확인 ② 단발 1~2건은 직접 실행이 더 싸다. 탐색 결과의 **채택 판단은 항상 오케스트레이터**가 한다.

### 에이전트 사망 처리 (공통 규약)

서브 에이전트가 결과 없이 종료(오류·세션 한계)하면 MUST: `references/agent-prompts.md`의 "공통 규약: 에이전트 사망 처리"를 따른다 (미로드 상태면 해당 섹션을 Read).
요약: Phase당 최대 2회 재시도(동일 조건 1회 → model 1단계 강등 1회) → 그래도 실패 시 구현·수정류는 `BLOCKED:AGENT_DIED` 보고 후 중단, 격리 필수 단계(8.8)는 `SKIPPED:AGENT_DIED`, 그 외는 오케스트레이터 축소 폴백(`degraded_fallback` 기록) 후 계속. 세션 한계 사망 2회 누적 시 검증 위임(8.4·8.8)을 최후 보존한다.
Codex 호출 실패는 이 규약 대상이 아니다 — `references/codex-mode.md` §7 실패 정책(latch·재시도·Claude 폴백)을 따르고, Claude 폴백 에이전트부터 이 규약을 적용한다.

### Implementation Notes (라이브 판단 기록)

자율 실행 중 발생하는 **설계 결정·편차·트레이드오프·미결 질문**을 코드와 분리해 `{IMPL_NOTES}`에 실시간으로 누적한다.
유저는 자율 실행 중에도 파일을 직접 열어 비동기로 피드백할 수 있고, Phase 12에서 Workflow Report 부록 C로 원문이 보존된다.

핵심 규칙 (파일 초기화 템플릿·4-섹션 구조: `references/templates.md`):

- 파일을 수정하는 자율 실행 에이전트는 4종 사건 발생 시 **코드 수정 전에** 해당 섹션에 한 줄 append. **append-only**, 마크다운만 (HTML/JSON 금지 — 아카이브 부록에 원문 그대로 삽입된다). 읽기 전용 스캔 에이전트는 직접 쓰지 않는다 — 이슈 보고서에 포함하면 통합 수정 단계가 대신 기록.
- `[Assumption]` 보고와 동일한 항목은 `## 편차` 섹션에 동시 기록 (보고서와 라이브 노트 동기화).

## Pre-flight: 세션 환경 점검 (모든 모드 공통)

### 1. Project Profile 로드

`.claude/be-harness.local.md`를 Read하여 아래 값을 변수로 추출한다:

`{buildCommand}`, `{testCommand}`, `{lintCommand}`, `{typeCheckCommand}`, `{makeTestCommand}`,
`{runServerCommand}`, `{serverUrl}`, `{e2eEnabled}`, `{apiDocsPath}`,
`{sourceDirs}`, `{testDirs}`, `{mainBranch}`, `{featureBranchPrefix}`, `{hotfixBranchPrefix}`,
`{commitPrefixes}`, `{commitCoAuthor}`, `{projectConventions}`, `{language}`

profile이 없으면 안내 후 종료한다:
> "`.claude/be-harness.local.md` 가 없습니다. 먼저 `/be-harness:init`을 실행하세요."

**Codex 모드 resolve** (`references/codex-mode.md` §2): 재개면 상태 파일 `## Flags`의 `CODEX`가 기준(`--codex` 무시). 신규면 `--codex` > profile `codexMode` > (대화형) 3지선다 질문 / (비대화형) `mix` ephemeral — 명시 입력만 profile에 기록하고, 값은 exact `none|mix|max`로 검증한다. 확정 직후 `--codex-models`도 동형으로 resolve한다 (§2.1 — 재개면 `CODEX_MODELS` 기준·플래그 무시, `none`이면 `N/A`, 명시 입력만 profile `codexModels`에 기록, 슬롯 단위 병합 `플래그 > profile > 기본값`; 결과는 `$CODEX_MODELS`).
`none`이 아니면 도구 목록에 `mcp__codex__codex` 존재를 확인한다 — 없으면 `$CODEX_RUNTIME = fallback(global:mcp_missing)` + 고지(profile 불변). `max`이고 세션 모델이 opus/fable 계열이 아니면 1줄 고지한다.

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

## Phase 2: 난이도 산정 + 검증 티어 판정

> Phase 2 진입 시 MUST: 같은 폴더의 `references/verification-tier.md`를 Read하고 A/B 점수표·게이트·금지 조건·light 축소 항목·승격 규칙을 따른다.

Technical Spec을 분석하여 1~10 난이도를 산정한다. **종합 난이도 = max(A, B)**, 각 축 = 요소별 밴드 최댓값, 근거 없는 요소는 `UNKNOWN`(= 높음).
B축 근거는 Spec `참조 구현` 경로로 `assets/risk_facts.py`를 실행한 사실(변경 빈도·동반 테스트·과거 워크플로우 이력)로 뒷받침한다.

**검증 티어**: A ≤ 3 ∧ B ≤ 3 ∧ 금지 조건 0건 ∧ `$TDD = true` ∧ 전략 ≠ parallel-slices ∧ `$TIER_FORCE = false` → `light`(추가 리뷰 레이어·루프 상한·E2E 범위만 축소). 그 외 `standard`(기존 절차 무변경).

출력: `난이도: 코드 [A]/10 + 리스크 [B]/10 — [근거]` / `검증 티어: light|standard — A [a]/B [b], 금지 조건 [해당 없음|{항목}], [사유]`

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
- **light**: 배치 없이 `general-purpose` 1개가 3관점(엣지 케이스 · 기존 코드 영향 · 더 단순한 경로)을 한 번에 리뷰한다.

각 에이전트 프롬프트에 Spec 전문 + Plan 전문을 전달하고 아래 형식으로 받는다:

```
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [문제 목록 또는 "없음"]
**Suggestions**: [개선 제안 또는 "없음"]
```

종합: REJECT 1개+ → 해당 이슈를 Plan에 반영. CONCERN → 타당한 항목만 자동 반영.
→ 보강된 Plan을 **Plan v1 (검증 루프 입력)**으로 확정.

### Phase 4.3: Plan Verification Loop (최대 {PLAN_MAX}회)

Plan은 검증 루프를 통과해야 확정된다. **리뷰어 = `codexMode`** (`references/codex-mode.md` §1·§6 — `mix`/`max`: Codex `review` 슬롯(`$CODEX_MODELS`), `none`: Claude 3관점 패널). 첫 dispatch 직전에 codex-mode.md를 Read한다.

```
for iteration in 1..{PLAN_MAX}:
  ① Plan 리뷰 (Architect 관점, 리뷰어 = codexMode) — stateless 보완을 위해 매회 전달:
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
| 리뷰어 `APPROVE` | **PROCEED** → Phase 4.4 |
| 사용자가 명시적으로 루프 종료 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Claude 패널 실패 (유효 verdict 3개 미달 — codex-mode.md §6) | **CODEX-UNAVAILABLE** → 사유를 상태 파일에 기록하고 진행 (light면 승격 ⑤ → standard). Codex 호출 실패 자체는 §7대로 패널 폴백이며 이 코드가 아니다 |
| `{PLAN_MAX}`회 도달, 미APPROVE | **BLOCKED:MAX_ITERATIONS** → 아래 선택지 제시 (light는 상한 평가 전에 승격 ① → `{PLAN_MAX}` = 5로 계속) |

`{PLAN_MAX}`회 도달 시 선택지: "Plan 검증 루프가 {PLAN_MAX}회에 도달했습니다. 미해결 이슈: {요약} — 1. 현재 Plan으로 진행(잔존 이슈를 상태 파일에 기록하고 Phase 4.4로) 2. 루프 계속(5회 추가 반복) 3. 중단(워크플로우 종료)"

안전장치:
- **동일 이슈 3회 반복 지적** → 사용자에게 보고하고 판단 위임 (응답 후 재개/종료)
- **변경 0건 iteration 발생** → 즉시 중단하고 사용자에게 보고 (무한 핑퐁 방지)

### Phase 4.4: Plan 확정

Plan의 파일 목록으로 금지 조건을 재점검한다(발견 시 즉시 standard). 티어 판정을 Plan과 함께 승인받는다. 루프 종료 후 `ExitPlanMode` 실행. 상태 파일 하단에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 5: 브랜치 + 상태 파일 + Baseline + 자율 실행 시작

**브랜치 생성**:
- `$HARD_MODE = false`: 구현 전 반드시 feature 브랜치 생성 (`git checkout -b feat/{작업 요약 kebab-case}`). 이미 `feat/**`·`hotfix/**`면 건너뜀. main/master에 직접 커밋 금지.
- `$HARD_MODE = true`: 브랜치 생성 건너뜀. 현재 브랜치 그대로 사용.

**상태 파일 생성**:

> Phase 5 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고
> ① "상태 파일 템플릿"대로 `{STATE_FILE}`을 생성한다. Spec 전문, 정상 흐름·엣지 케이스 목록, 확정 Plan 전문, 실행 전략, (parallel-slices 시) Slices, **Phase 4.3의 `Plan Verification Log`**를 복사해 넣고, `## Flags`(MODE·HARD_MODE·TDD·REFLECT·TIER·CODEX·CODEX_MODELS·RUN_ID·START_SHA)·`## Verification Tier`·`## Codex Runtime`(`$CODEX_RUNTIME` 값 그대로 — `active`로 초기화하지 않음)을 기록한다 (`CODEX_MODELS` = `$CODEX_MODELS` 확정값 — `tiered`는 Phase 2 난이도로 확정).
> ② "Implementation Notes 라이브 파일 초기화" 템플릿대로 `{IMPL_NOTES}`를 생성한다 (기존 파일 덮어쓰기).

**회귀 Baseline 수집 (TDD 활성 시)**:

> Phase 5 진입 시 MUST: 같은 폴더의 `references/tdd.md`를 Read하고 "TDD 적용 판정"과 "Phase 5: 회귀 Baseline 수집" 절차를 따른다.

여기가 **유저와 대화 가능한 마지막 지점**이다. baseline 수집이 실패하면 자율 실행에 들어가기 전에 선택지를 제시한다 (절차: `references/tdd.md`). 수집 실패 확정 시 light는 승격 ④로 standard.
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

- `sequential`: `general-purpose` 1개가 `/be-harness:unit-test --red` 실행 (`codexMode: max`: 러너 프롬프트에 codex-mode.md §8 포인터 1줄, 테스트·스텁 작성 리프는 Codex `write` 슬롯 — `references/tdd.md`)
- `parallel-slices`: 슬라이스별 에이전트가 테스트·스텁만 작성 → **오케스트레이터가 배리어에서 1회 글로벌 Red 검증 후 기록·커밋**

| 종료 조건 | 결과 |
|----------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` → Phase 6.2 |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID 제외하고 Phase 6.2 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — TDD SKIP 후 Phase 6.2 진행 |
| baseline에 없던 기존 테스트가 실패 | `BLOCKED:REGRESSION_AT_RED` — 기록 후 Phase 6.2 진행 |

`BLOCKED:*`여도 자율 실행은 멈추지 않는다. 선택지 제시는 Phase 12로 이연한다.

#### Phase 6.2: 구현 (Green)

- `sequential`: `be-harness:workflow-implementer` 1개 → 구현 + 커밋 (`codexMode: max`: Codex `write` 슬롯(`workspace-write`), 쓰기 안전 = codex-mode.md §5)
- `parallel-slices`: `general-purpose` 2~3개 병렬 (커밋·빌드 금지) → 완료 후 오케스트레이터가 일괄 커밋 (`max`: 슬라이스별 Codex `write` 슬롯, 실패 시 항상 이어서 — §5)

TDD 활성 시 **테스트 파일 수정 금지** 규칙과 `[TestConflict]` 보고 규칙을 프롬프트에 추가한다 (`references/tdd.md`).

프롬프트·커밋 규칙: `references/agent-prompts.md`의 "Phase 6.2" 섹션.
완료 직후 **승격 ② 평가**(변경 소스 파일 > 3 또는 금지 조건 발견 — `references/verification-tier.md` §4) → light면 standard 전환을 기록하고 Phase 7로.

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

### Phase 8: 품질 루프 (최대 {QL_MAX}회)

> Phase 8 진입 시 MUST: 같은 폴더의 `references/quality-loop.md`를 Read하고 각 단계의 프롬프트·실행 상세를 따른다.

```
for iteration in 1..{QL_MAX}:
  [Batch A — 병렬 스캔, 읽기 전용] 8.1 빌드+테스트(Bash) / 8.2+8.3 품질 스캔(통합 1에이전트) / 8.4 scope
      → 이슈만 수집, 파일 수정 금지
  [Phase 8.5 — 통합 수정] 수집 이슈를 단일 에이전트가 일괄 수정
  [Batch B — 순차, 서버 점유] 8.6 e2e-test-loop → 8.7 통합 테스트

[루프 종료 후 1회] 8.8 Spec 정합 Read-back — 판정만, 코드 수정 없음
```

**light**: 8.2 = `SKIPPED:TIER_LIGHT`(통합 스캐너를 convention 전용으로 호출), 8.6 = `e2e-test-loop --smoke`, 8.8 = `SKIPPED:TIER_LIGHT`. 승격 ③·⑥·⑦(회귀 · E2E BLOCKED/smoke 미적용 · 변경 파일 재집계)은 `references/verification-tier.md` §4 — 티어 전환은 아래 종료 조건 평가보다 먼저 적용하고, ⑥·⑦은 standard iteration을 최소 1회 추가한다.

Phase 8.1 결과는 `assets/test_failures.py --baseline {STATE_FILE}`로 `## Test Baseline`과 대조해 `regression` / `pre_existing` / `new_red` / `flaky`로 분류한다 (절차·폴백: `references/tdd.md`의 "Phase 8: 회귀 대조").

**테스트 판정**: `PASS` = `regression` 0건 + `new_red` 0건 / `WARN` = `flaky`만 / `FAIL` = 그 외

| 종료 조건 | 결과 |
|----------|------|
| `modified == false` **AND** 테스트 판정 `PASS` | 루프 탈출 → Phase 8.8 |
| `modified == false` (TDD SKIP 시) | 루프 탈출 → Phase 8.8 |
| 그 외 | 커밋 후 다음 iteration |
| `{QL_MAX}`회 도달 & 미PASS | `BLOCKED:TEST_NOT_GREEN` 기록 → 강제 탈출 → Phase 8.8 |

수정이 0건이어도 테스트가 깨져 있으면 탈출하지 않는다 — 얼어붙은 테스트가 실패하는데 소스 수정이 없으면 루프가 "성공"으로 오종료되기 때문이다.
`BLOCKED:TEST_NOT_GREEN`이어도 **자율 실행은 중단하지 않고** 이후 Phase를 계속 진행하며, 선택지는 Phase 12에서 제시한다.

커밋: `git add [수정 파일들] && git commit -m "Fix: 품질 루프 수정 (반복 N)"`

**Phase 8.8은 루프 밖에서 1회만 실행한다** (light: `SKIPPED:TIER_LIGHT`). Spec을 모르는 격리된 에이전트가 구현·검증 산출물에서 보장 동작을 복원하고, 오케스트레이터가 그것을 Spec·기존 코드와 대조해 이탈을 판정한다. 코드는 수정하지 않으며 결과는 Phase 12에서 유저에게 보고한다. 판정이 `FAIL`이어도 자율 실행은 멈추지 않는다.

완료 후: "Phase 8 완료: [루프 횟수]회, 총 [수정 건수]건 수정 / Read-back [PASS/WARN/FAIL | SKIPPED:TIER_LIGHT] (A·C·E [N]건) / 티어 [light|standard|light → standard({트리거})]"

### Phase 9: API 문서 동기화 (조건부)

아래 조건을 **모두** 만족할 때만 실행. 아니면 `SKIPPED:{사유}`:
- 작업 유형이 API 생성/수정/삭제
- `{apiDocsPath}`가 비어있지 않고 파일이 실제로 존재

프롬프트: `references/agent-prompts.md`의 "Phase 9" 섹션.

### Phase 10: PR / Push

진입 직전 light면 승격 ⑦ 재평가(`references/verification-tier.md` §4) — 발화 시 Phase 8을 standard로 1회 재진입한 뒤 돌아온다.
- `$HARD_MODE = false`: `be-harness:workflow-pr` 에이전트로 PR 생성 (`references/agent-prompts.md`의 "Phase 10" 섹션). PR URL 보고 필수.
- `$HARD_MODE = true`: PR 생략, push 전에 Assumption Gate 스캔(base와의 diff 추가 라인 + 미push 커밋 메시지에서 `[Assumption]` 검색)을 수행한다. 0건이면 `git push origin $(git branch --show-current)` 후
  "Phase 10 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)" 출력. 발견 시 push를 보류하고 아래 BLOCKED 절차를 따른다.
- **Assumption Gate BLOCKED 처리**: workflow-pr이 `BLOCKED:ASSUMPTION_UNRESOLVED`를 보고하면(또는 --hard 스캔에서 발견되면) push/PR 없이 Phase 11로 진행하고, Phase 12 보고서에 태그 목록을 포함해 항목별 유저 확인을 받는다. 승인(태그 제거)·수정으로 태그가 모두 제거된 뒤 **Phase 10만 재실행**한다. 태그가 남아 있는 동안 push/PR은 금지.

### Phase 11: 성찰 (조건부 — `--reflect` 시)

`$REFLECT = true`면 `be-harness:workflow-reflection` 에이전트 실행 (`references/agent-prompts.md`의 "Phase 11" 섹션).
`false`(기본)면 `SKIPPED:REFLECT_NOT_REQUESTED` 기록 후 Phase 12로 — 성찰은 매 실행이 아닌 주기 실행(워크플로우 5~10회마다 1회)을 권장하며, 스킵 사실과 권장 주기는 Phase 12 보고서가 고지한다.

## Phase 12: 최종 보고

> Phase 12 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고 "Phase 12 실행 절차", "Workflow Report 템플릿", "md 아카이브", "보완점 적용 상세"를 따른다.

절차 요약 (각 항목의 상세 규칙: templates.md의 "Phase 12 실행 절차" — 순서 변경 금지):
① `{WORK_REPORT}`에 슬림 Workflow Report 1회 Write(채팅에는 경로·§1·유저 결정 항목만) → ② TDD 미해결 항목 유저 결정 (첫 결정 지점) → ③ Read-back Diff 유저 결정 (보완점보다 먼저 — 코드·Spec에 직접 영향) → ④ 보완점 적용 질문 (Phase 11이 `DONE`일 때만 — `SKIPPED:*`면 생략하고 **실제 상태 코드**와 사유별 문구로 고지: templates §6 분기) → ⑤ 상태 파일 마감 후 `assets/workflow_archive.py`로 `{REPORT_DIR}`에 md 아카이브(부록 A 실행 요약 / B 상태 파일 전문 / C Implementation Notes) 생성.
수정이 필요한 결정은 유저 승인 후에만 수행한다 (Spec 외 변경 금지 원칙). ②~④의 결정은 받는 즉시 `## Final Decisions`에 기록한다 (재개 시 재질문 금지).

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 (예: `SKIPPED:PROFILE_EMPTY`, `SKIPPED:USER_OPT_OUT`, `SKIPPED:NO_TEST_BASIS`, `SKIPPED:REFLECT_NOT_REQUESTED`, `SKIPPED:TIER_LIGHT`, `SKIPPED:BUDGET_PRESERVED`, `SKIPPED:AGENT_DIED`) |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 (예: `BLOCKED:BUILD_FAIL`, `BLOCKED:MAX_ITERATIONS`, `BLOCKED:NO_VALID_RED`, `BLOCKED:REGRESSION_AT_RED`, `BLOCKED:TEST_NOT_GREEN`, `BLOCKED:AGENT_DIED`) |
| `PASS` / `WARN` / `FAIL` | Verify 모드 판정, 테스트 판정, Read-back 판정 |

TDD 진단 분류(`red_assertion`·`already_satisfied`·`cannot_compile`·`deferred_e2e`·`regression`·`pre_existing`·`new_red`·`flaky`)는 `## TDD Test Map`·회귀 대조 표의 셀 안에서만,
에이전트 사망 처리의 `agent_retry`·`degraded_fallback`, 티어 승격 `tier_escalated({트리거})`, 스크립트 폴백 `script_fallback({스크립트}:{사유})`, Codex 폴백 `codex_fallback({단계}:{사유})`은 `Phase Results` 표·보고서 "축소 실행 내역" 표의 `진단` 셀 안에서만 쓴다.
모두 **상태 코드가 아니라 데이터**다 — Phase Assignments의 Status 열에는 등장시키지 않는다 (`docs/skill-authoring.md` §5).

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/analyze-verify-modes.md` | `--analyze` / `--verify` 모드 진입 시 |
| `references/verification-tier.md` | Phase 2 (점수·게이트), Phase 4·5·6·8·10 (승격 판정) |
| `references/templates.md` | Phase 5 (상태 파일·라이브 노트), Phase 12 (보고서·md 아카이브·보완점) |
| `references/tdd.md` | Phase 5 (TDD 판정·baseline), Phase 6 진입 시 |
| `references/agent-prompts.md` | Phase 6 진입 시 (Phase 6.2/7/9/10/11 프롬프트) + 에이전트 사망 시 (공통 규약 — 미로드면 즉시 Read) |
| `references/quality-loop.md` | Phase 8 진입 시 |
| `references/codex-mode.md` | 첫 리뷰어/위임 dispatch 직전 1회 (재개 포함) — Codex 모드 정의·호출 계약·쓰기 안전·Claude 패널·실패 정책 |

## 흐름 요약 (Build)

```
[유저 대화] — Phase 1~4 전체가 단일 EnterPlanMode 컨텍스트
Phase 1: EnterPlanMode → /request로 Technical Spec (유저 확인)
Phase 2: 난이도 산정 (1-10) + 검증 티어 판정 (light / standard)
Phase 3: 실행 전략 판정 (sequential / parallel-slices / fullstack → /common:start-workflow --fs 로 전환)
Phase 4: Plan 작성 → 다관점 1회 보강 → 검증 루프 (리뷰어 = codexMode: Codex `review` 슬롯 | Claude 패널, 최대 {PLAN_MAX}회) → ExitPlanMode
Phase 5: feature 브랜치 + 상태 파일 + implementation-notes.md + 회귀 baseline → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주. codexMode max: 리프 에이전트를 Codex 슬롯(`explore`/`judge` 읽기 · `write` 쓰기)으로 위임 — codex-mode.md]
Phase 6.1: 테스트 우선 (Red) — Spec ID 근거로 실패 테스트 선작성 + 스텁, Red 커밋
Phase 6.2: 구현 (Green) — 테스트 파일 수정 금지, baseline 대비 신규 실패 0건까지
Phase 7: {buildCommand} 빌드 체크 (실패 시 수정 최대 3회)
Phase 8: 품질 루프 최대 {QL_MAX}회 (병렬 스캔 8.1~8.4 → 통합 수정 8.5 → e2e 8.6 → 통합 테스트 8.7)
         light: 8.2 SKIP · 8.6 --smoke · 8.8 SKIP — 승격 트리거 발생 시 standard로 전환 (단방향)
         탈출 조건 = 수정 0건 AND 테스트 판정 PASS (회귀 3분류 대조)
         루프 종료 후 8.8 Spec 정합 Read-back 1회 (격리 복원 → Diff 판정, 수정 없음)
Phase 9: API 문서 동기화 (API 변경 시만)
Phase 10: PR 생성 (--hard: push만)
Phase 11: 성찰 (--reflect 지정 시만 — 기본 SKIPPED:REFLECT_NOT_REQUESTED)

[유저 대화]
Phase 12: 슬림 Workflow Report → 유저 결정 (TDD·Read-back·보완점) → md 아카이브 (부록 A/B/C) → 정리
```
