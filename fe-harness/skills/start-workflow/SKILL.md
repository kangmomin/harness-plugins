---
name: start-workflow
description: "전체 프론트엔드 개발 워크플로우를 자동화한다. 요청 분석 → 난이도 산정 → Plan 리뷰 → 구현 → 품질 루프 → 컴포넌트/접근성 리뷰 → PR → 성찰까지 일관된 파이프라인. '워크플로우 시작', '화면/컴포넌트 만들어줘(전 과정 자동)' 요청 시 사용."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: "<작업 설명 또는 빈 값> [--hard] [--no-tdd] [--reflect] [--tier standard]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/start-workflow.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.

# Start Workflow — Orchestrator

전체 프론트엔드 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

**플레이스홀더 정의** (본문·references 공통, 값 변경은 여기 한 곳만 수정):

- `{STATE_FILE}` = `/tmp/workflow-state.md`
- `{IMPL_NOTES}` = `/tmp/implementation-notes.md`
- `{REPORT_DIR}` = profile의 `reportDir` (없으면 `.claude/harness-reports`)
- `{WORK_REPORT}` = `/tmp/workflow-report-{run_id}.md` (`run_id` = `## Flags`의 `RUN_ID`)
- `{PLAN_MAX}` = Phase 3.3 상한 (standard 5 / light 2) · `{QL_MAX}` = Phase 7 상한 (standard 3 / light 2)
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)
- `{buildCommand}` 등 profile 변수 = `.claude/fe-harness.local.md`에서 로드

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. PR 생략. |
| `--no-tdd` | | Phase 5.1(테스트 우선)을 건너뛰고 곧바로 구현한다. 회귀 baseline도 수집하지 않는다. 검증 티어는 standard 강제. |
| `--reflect` | | Phase 10(성찰)을 실행한다. 미지정 시 Phase 10은 `SKIPPED:REFLECT_NOT_REQUESTED` (주기 실행 권장 — 워크플로우 5~10회마다 1회). |
| `--tier standard` | | Phase 2 판정과 무관하게 검증 티어를 standard로 강제한다 (light 축소 비활성). light 강제 플래그는 없다. |

`$ARGUMENTS`에 `--hard`/`-h`가 있으면 `$HARD_MODE = true`, `--no-tdd`가 있으면 `$TDD = false` (기본값 `true`), `--reflect`가 있으면 `$REFLECT = true` (기본값 `false`), `--tier standard`가 있으면 `$TIER_FORCE = true` (기본값 `false`).

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 4 브랜치 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 9 PR | workflow-pr (PR 생성) | 현재 브랜치에서 바로 push, PR 생략 |

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 상태 추적

워크플로우 시작 시 `{STATE_FILE}`을 새로 만들고, Phase 진입/완료 때마다 갱신한다 (템플릿: `references/templates.md`).
상태 파일은 `Flags` / `Current Phase` / `Phase Assignments` / `Remaining Phases` / `Verification Tier` / `Related E2E Specs` / `Phase Results` 섹션을 항상 포함한다.

- 에이전트 생성 전: 해당 Phase를 `IN_PROGRESS`로 갱신
- 완료 후: `DONE` / `SKIPPED:{사유}` / `BLOCKED:{사유}` 와 결과 기록
- 모든 에이전트 프롬프트에 상태 파일 경로, 현재 Phase, 남은 Phase, 배정 model/effort 포함
- `## Flags`(MODE·HARD_MODE·TDD·REFLECT·TIER·RUN_ID·START_SHA)는 컨텍스트 요약·세션 재개로 CLI 인자를 잃은 뒤 이어갈 때 **유일한 기준** — CLI 인자와 충돌하면 기록값 우선 + 고지. `RUN_ID`는 Phase 4에서 1회 생성하며 재생성하지 않는다.

### Model / Effort 선택 규칙

Agent 생성 시 작업 복잡도·난이도·작업량에 맞춰 `model`과 `effort`를 명시한다.
환경별 모델명이 다르면 같은 등급의 사용 가능한 최신 모델로 치환한다.

| 등급 | 기준 | Claude 계열 | Codex 계열 | effort |
|------|------|-------------|------------|--------|
| Simple | 난이도 1-3, 1-3개 파일, 문서/단순 UI 수정 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 난이도 4-6, 일반 컴포넌트/API 연동/테스트 수정 | sonnet | gpt-5.3-codex | medium |
| Complex | 난이도 7-8, 다중 화면/상태/API/a11y 영향 | opus | gpt-5.4 | high |
| Critical | 난이도 9-10, 대규모 리팩토링/복잡 상태/릴리즈 위험 | opus | gpt-5.5 | xhigh |

읽기 전용 리뷰는 기본 `Standard`, 접근성/상태 정합성/계약 변경 검토는 `Complex` 이상.
코드 수정 에이전트는 담당 파일 수와 실패 반복 횟수에 따라 한 단계 높일 수 있다.

## 자율 실행 규칙

```
[유저 대화] Phase 1~3 : Spec, 난이도, Plan+리뷰
[상태 저장] Phase 4   : 브랜치 + 상태 파일 + 회귀 baseline 수집
[자율 실행] Phase 5~10: 서브 에이전트 순차 위임 — 묻지 않고 자동 실행
[유저 대화] Phase 11  : 최종 보고 + 보완점 적용
```

### Spec 외 변경 금지 원칙

자율 실행 중 Spec에 명시되지 않은 동작 변경이 필요하다고 판단되면:
1. **코드를 수정하지 않고** 해당 사항을 기록한다.
2. Phase 11 보고서에 `[Assumption]` 태그로 표기하여 유저에게 가시화한다.
3. 유저 승인 후에만 해당 변경을 적용한다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- **유저 응답 대기, 진행 여부 질문, 중간 보고 후 멈춤은 금지.**
- 유일한 정지 지점은 **Phase 11 (최종 보고)** 뿐이다.

### Implementation Notes (라이브 판단 기록)

자율 실행 중 발생하는 **설계 결정·편차·트레이드오프·미결 질문**을 코드와 분리해 `{IMPL_NOTES}`에 실시간으로 누적한다.
유저는 자율 실행 중에도 파일을 직접 열어 비동기로 피드백할 수 있고, Phase 11에서 Workflow Report 부록 C로 원문이 보존된다.

핵심 규칙 (파일 초기화 템플릿·4-섹션 구조: `references/templates.md`):

- 파일을 수정하는 자율 실행 에이전트는 4종 사건 발생 시 **코드 수정 전에** 해당 섹션에 한 줄 append.
- 읽기 전용 스캔 에이전트는 직접 쓰지 않는다 — 이슈 보고서에 포함하면 통합 수정 단계가 대신 기록.
- `[Assumption]` 보고와 동일한 항목은 `## 편차` 섹션에 동시 기록 (보고서와 라이브 노트 동기화).
- **append-only** — 기존 줄 수정·삭제 금지. 마크다운만 작성 (HTML/JSON 금지 — 아카이브 부록에 원문 그대로 삽입된다).

---

## Phase 1: 작업 범위 수집 (Plan 모드 진입)

> **Plan 모드 활성화**: Phase 1 시작 시 `EnterPlanMode`를 활성화한다.
> Spec과 Plan은 같은 Plan 모드 컨텍스트에서 통합 산출물로 발전하며, `ExitPlanMode`는 Phase 3.4에서 단 한 번만 호출한다.

**분기 — 이미 상세 Spec이 제공된 경우**: `$ARGUMENTS` 또는 대화 컨텍스트가 아래를 **모두** 충족하면 `/request` 호출을 생략하고, 제공된 내용을 Technical Spec으로 직접 정리해 유저 확인을 받는다:
- 작업 유형이 명확 (화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정)
- 대상 컴포넌트/페이지/API가 특정됨
- 핵심 요구사항이 구체적으로 기술됨

**기본**: `/fe-harness:request`를 호출하여 Technical Spec을 생성한다. 완료 후 Spec 전문과 엣지 케이스 목록을 보관한다.

> 어느 경우든 Spec을 유저에게 보여주고 확인을 받는다.

### 풀스택 판정

Spec 확정 시 **백엔드 변경이 함께 필요한지** 판정한다. 아래 중 하나라도 해당하면 `fullstack`이다:

- 신규 API 엔드포인트가 필요하다 (기존 API 조합으로 해결 불가)
- 기존 API의 요청/응답 구조·에러 코드·인증 방식 변경이 필요하다
- 화면이 요구하는 데이터가 현재 백엔드에 존재하지 않는다

| 감지 | 행동 | 고지 문구 |
|------|------|----------|
| `/common:start-workflow` 가 세션에 존재 | Skill tool로 `--fs` 와 함께 호출 후 현재 워크플로우 종료 | "FE+BE 동시 변경이 필요합니다. `/common:start-workflow --fs`로 전환합니다." |
| common 미설치 | 선택지 제시 후 대기 | "FE+BE 동시 변경이 필요하지만 풀스택 오케스트레이션을 제공하는 `common` 이 설치되어 있지 않습니다.<br>1. `common` 설치 후 재시작 (권장) — `/plugin install common@harness-plugins`<br>2. 프론트엔드만 진행 — 백엔드 변경은 별도 작업으로 분리<br>3. 중단" |

> **기존 API로 해결 가능하면 `fullstack`이 아니다.** 판단이 애매하면 유저에게 확인한다 — 풀스택 전환은 계약 확정부터 다시 시작하므로 비용이 크다.

출력: `도메인 판정: [frontend/fullstack] — [근거]`

## Phase 2: 난이도 산정 + 검증 티어 판정

Technical Spec을 분석하여 1~10 난이도를 산정한다. **종합 난이도 = max(A, B)**, 각 축 = 요소별 밴드 점수의 최댓값(평균 금지), 판정 근거가 없는 요소는 `UNKNOWN`(= 높음 밴드, fail-safe).

### A. 코드 복잡도

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 컴포넌트 수 | 1개 | 2-3개 | 4개+ |
| 상태 복잡도 | useState 단순 | 여러 상태 조합 | 전역 상태 + 서버 상태 |
| API 연동 | 없음 | 기존 API | 새 API 연동 |
| 반응형/a11y | 기본 | 반응형 필수 | 반응형 + 접근성 + 애니메이션 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

### B. 영향 범위·회귀 리스크

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 공유 컴포넌트·디자인 시스템 | 미수정 | 내부 구현만 수정 | Props·토큰 변경 |
| 전역·서버 상태 계약 | 없음 | 필드 추가 | 기존 계약 변경 |
| Props 계약 | 신규 컴포넌트만 | 선택 prop 추가 | 필수 prop·타입 변경 |
| 라우팅·레이아웃 | 없음 | 신규 라우트 | 기존 라우트·레이아웃 변경 |
| 기존 동작 변경 범위 | 없음·신규 경로만 | 기존 경로에 분기 추가 | 기존 경로의 동작 변경 |
| 변경 영역 기존 테스트 | 단위 + E2E 있음 | 일부만 있음 | 없음 · `UNKNOWN` |
| 롤백 용이성 | 즉시 가능 | 상태·스토리지 마이그레이션 롤백 필요 | 데이터 복구 필요 |

B축 근거(기본 실행): Spec `참조 구현` 열의 경로로 아래를 실행해 출력(존재·최근 변경 커밋 수·동반 테스트·과거 워크플로우 이력)을 `변경 영역 기존 테스트`·`기존 동작 변경 범위`의 근거로 쓴다. 경로가 없거나 exit ≠ 0이면 해당 행은 `UNKNOWN`.
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/risk_facts.py --paths {참조 구현 경로들} --report-dir {REPORT_DIR}
```

출력: `난이도: 코드 [A]/10 + 리스크 [B]/10 — [근거]`

### 검증 티어

`light` ⇔ A ≤ 3 ∧ B ≤ 3(= 모든 요소 `낮음`, `UNKNOWN` 0건) ∧ 금지 조건 0건 ∧ `$TDD = true` ∧ `$TIER_FORCE = false`. 그 외 `standard`(= 기존 절차 무변경). light 강제 플래그는 없다 — 점수는 유저가 근거를 제시하면 재산정할 수 있으나 게이트 조건은 불변. 풀스택 전환 시 항상 standard.

**금지 조건**(우회 불가, Phase 3.4에서 Plan 파일 목록으로 재점검): 디자인 시스템·전역 레이아웃·전역 스토어 계약 변경 / 인증·인가·개인정보 처리 UI / 결제·정산 화면 / 공유 훅·미들웨어·인터셉터 / Breaking change(Props·API 계약) / 외부 서비스 연동 변경.

| 단계 | standard | light |
|------|----------|-------|
| 3.2 다관점 Plan 보강 | 3에이전트 × 2배치 | **1에이전트 3관점**(엣지 케이스 · 기존 코드 영향 · 더 단순한 경로) |
| 3.3 Codex 루프 `{PLAN_MAX}` | 5 | **2** (2회 소진 시 승격 ①) |
| 7 품질 루프 `{QL_MAX}` | 3 | **2** |
| 7.2 simplify-loop | 실행 | `SKIPPED:TIER_LIGHT` |
| 7.4 test-loop | full | `test-loop --smoke` (단위 테스트 무변경, E2E는 `## Related E2E Specs` 범위) |
| 7.7 Spec 정합 Read-back | 1회 | `SKIPPED:TIER_LIGHT` |
| 8 컴포넌트/접근성 리뷰 | component + a11y 병렬 | a11y-reviewer만 (component-reviewer `SKIPPED:TIER_LIGHT`) |
| 유지(축소 금지) | — | 5.1 TDD Red · 6 · 7.1 · 7.3 convention · 7.5 scope · 7.6 lint · 9 |

**승격(light → standard, 단방향 — 자율 구간은 질문 없이 기록; 전환은 해당 루프의 종료 조건·상한 평가보다 먼저 적용)**:

| # | 시점 | 트리거 | 효과 |
|---|------|--------|------|
| ① | 3.3 | Codex CONCERN/REJECT로 light 상한 2회 소진 | `{PLAN_MAX}` = 5 복원, 카운터 승계(3회차부터). 3.2 재실행 없음 |
| ② | 5.2 완료 직후, Phase 6 전 | 변경 소스 파일 > 3 **또는** 금지 조건 발견 (집계 규칙: 아래) | Phase 6·7 전부 standard |
| ③ | 7.4 회귀 대조 | `regression` ≥ 1, 또는 판정 불가(러너 완주 N / `unparsed` 잔존을 오케스트레이터도 분류 못 함) | `{QL_MAX}` = 3 복원. 다음 iteration의 7.2·7.4가 full. 회귀·판정 불가 = FAIL이라 다음 iteration 보장, 복원 상한에서도 미PASS면 `BLOCKED:TEST_NOT_GREEN`. 루프 후 7.7·component-reviewer 실행 |
| ④ | 4 baseline 수집 | 수집 실패(`regression 판정 불가` 선택) | standard |
| ⑤ | 3.3 | `CODEX-UNAVAILABLE` | standard 기록 후 기존 규칙대로 |
| ⑥ | 7.4 test-loop | 최종 상태 `UNRESOLVED`에 E2E 실패 잔존 (`full(smoke 미적용: …)`은 관련 spec 부재일 뿐이므로 기록만) | standard + 현재 iteration 종료 후 standard iteration 최소 1회 추가 (탈출 평가는 그 뒤부터) |
| ⑦ | 각 iteration 종료 시 + Phase 9 진입 직전 — **light인 동안만 평가(승격 = latch, 1회)** | ②와 동일 집계 재평가 | standard + standard iteration 최소 1회 추가 (Phase 9 직전이면 Phase 7을 standard 루프로 재진입 — 상한 3, 종료 시 `검증 트리: {git rev-parse HEAD} (dirty: Y/N)` 기록, 이력 `⑦: Phase 7 재진입`) |

②·⑦ 집계: `## Flags`의 `START_SHA` 기준 `git cat-file -e {START_SHA} && { git diff --name-only {START_SHA}; git ls-files --others --exclude-standard; } | sort -u` — 커밋·스테이징·작업 트리·untracked 전부, 삭제·이름 변경도 1건. 제외는 **명시 패턴만**(`*.test.*` · `*.spec.*` · `__tests__/` · `e2e/` · `node_modules/` · `*.gen.*` · `mocks/` · `__pycache__/` · `*.md` · `docs/`), 나머지는 전부 소스로 집계하고 목록을 승격 이력에 기록. `START_SHA` 없음·도달 불가 → `## Test Baseline`의 `커밋:` → 그것도 없으면 standard 강제 + 이력 `②: 시작 SHA 판정 불가`(HEAD 대체 금지).
기록: `Phase Results` 진단 셀 `tier_escalated({①..⑦})`, `## Verification Tier` 승격 이력 행(시점 / 트리거 / 근거 / 조치), `## Flags` `TIER` 갱신, 보고서 §1 `검증 티어: light → standard (②, 3.2 light 실행)`. 승격 시 재실행하지 않는 유일한 항목은 3.2 — 이력에 `미재실행: 3.2`로 남긴다.

출력: `검증 티어: light|standard — A [a]/B [b], 금지 조건 [해당 없음|{항목}], [TDD off|--tier standard 로 standard]` — Plan과 함께 `ExitPlanMode`에서 승인.

## Phase 3: Plan 작성 + 리뷰

### Phase 3.1: Plan 작성

Spec 아래에 구현 계획을 추가하여 **Spec+Plan 단일 산출물**로 발전시킨다. Plan에 포함할 내용:

- 구현 순서 (파일 단위), 각 파일 변경 내용 요약
- **최종 코드 구조**: 컴포넌트 분리, 훅 추출, 상태 설계를 Plan 단계에서 확정
- 의존 관계, 예상 리스크
- **관련 E2E spec 파일 경로 목록** (없으면 `없음`) — Phase 4가 `## Related E2E Specs`로 복사하고 light의 `test-loop --smoke`가 이 범위만 실행한다

### Phase 3.2: 다관점 Plan 보강 (Claude, 1회)

검증 루프 진입 전 Claude 측 다관점 리뷰로 명백한 결함을 1회 보강한다. **이 단계는 검증 루프가 아니다.**

최대 3개 서브에이전트(`general-purpose`) 병렬 × 2배치:
- Batch 1: 유지보수성 + 성능 + 엣지 케이스
- Batch 2: 상태 정합성 + 접근성 + 기존 코드 영향
- **light**: 배치 없이 `general-purpose` 1개가 3관점(엣지 케이스 · 기존 코드 영향 · 더 단순한 경로)을 한 번에 리뷰한다.

각 에이전트 프롬프트에 Spec 전문 + Plan 전문을 전달하고 아래 형식으로 받는다:

```
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [문제 목록 또는 "없음"]
**Suggestions**: [개선 제안 또는 "없음"]
```

종합: REJECT 1개+ → 해당 이슈를 Plan에 반영. CONCERN → 타당한 항목만 자동 반영.
→ 보강된 Plan을 **Plan v1 (검증 루프 입력)**으로 확정.

### Phase 3.3: Plan Verification Loop (Codex 검증, 최대 {PLAN_MAX}회)

```
for iteration in 1..{PLAN_MAX}:
  ① Codex Plan 리뷰 (Architect 관점) — stateless 보완을 위해 매회 전달:
     Spec 전문 / Plan vN 전문 / 난이도 산정 근거
     / (N≥2) 이전 iteration Diff 요약 + 기각 피드백·사유
     리뷰 관점: Spec-Plan 추적성, 컴포넌트/훅 책임 경계, 상태 정합성,
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
| Codex `APPROVE` | **PROCEED** → Phase 3.4 |
| 사용자가 명시적으로 루프 종료 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex 사용 불가 환경 | **CODEX-UNAVAILABLE** → 사유를 상태 파일에 기록하고 진행 (light면 승격 ⑤ → standard) |
| `{PLAN_MAX}`회 도달, 미APPROVE | **BLOCKED:MAX_ITERATIONS** → 아래 선택지 제시 (light는 상한 평가 전에 승격 ① → `{PLAN_MAX}` = 5로 계속) |

`{PLAN_MAX}`회 도달 시 선택지:
> "Plan 검증 루프가 {PLAN_MAX}회에 도달했습니다. 미해결 이슈: {요약}
> 1. 현재 Plan으로 진행 — 잔존 이슈를 상태 파일에 기록하고 Phase 3.4로
> 2. 루프 계속 — 5회 추가 반복
> 3. 중단 — 워크플로우 종료"

안전장치:
- **동일 이슈 3회 반복 지적** → 사용자에게 보고하고 판단 위임 (응답 후 재개/종료)
- **변경 0건 iteration 발생** → 즉시 중단하고 사용자에게 보고 (무한 핑퐁 방지)

### Phase 3.4: Plan 확정

Plan의 파일 목록으로 금지 조건을 재점검한다(발견 시 즉시 standard). 티어 판정을 Plan과 함께 승인받는다. 루프 종료 후 `ExitPlanMode` 실행. 상태 파일 하단에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 4: 브랜치 + 상태 파일 + Baseline + 자율 실행 시작

**브랜치 생성**:
- `$HARD_MODE = false`: 구현 전 반드시 feature 브랜치 생성 (`git checkout -b feat/{작업 요약 kebab-case}`). 이미 `feat/**`·`hotfix/**`면 건너뜀. main/master에 직접 커밋 금지.
- `$HARD_MODE = true`: 브랜치 생성 건너뜀. 현재 브랜치 그대로 사용.

**상태 파일 생성**:

> Phase 4 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고
> ① "상태 파일 템플릿"대로 `{STATE_FILE}`을 생성한다. Spec 전문, 정상 흐름·엣지 케이스 목록, 확정 Plan 전문, profile 주요 설정을 복사해 넣고, `## Flags`(MODE·HARD_MODE·TDD·REFLECT·TIER·RUN_ID·START_SHA)·`## Verification Tier`·`## Related E2E Specs`(Plan 3.1의 목록)를 기록한다.
> ② "Implementation Notes 라이브 파일 초기화" 템플릿대로 `{IMPL_NOTES}`를 생성한다 (기존 파일 덮어쓰기).

**회귀 Baseline 수집 (TDD 활성 시)**:

> Phase 4 진입 시 MUST: 같은 폴더의 `references/tdd.md`를 Read하고 "TDD 적용 판정"과 "Phase 4: 회귀 Baseline 수집" 절차를 따른다.

여기가 **유저와 대화 가능한 마지막 지점**이다. baseline 수집이 실패하면 자율 실행에 들어가기 전에 선택지를 제시한다. 수집 실패 확정 시 light는 승격 ④로 standard.
TDD SKIP 판정 시 사유를 `## Test Baseline`에 기록하고, Phase 5는 기존 단일 구현 흐름으로 진행한다.

출력: **"자율 실행을 시작합니다. Phase 5~10을 서브 에이전트로 순차 실행합니다."**

## Phase 5 ~ 10: 자율 실행

> Phase 5 진입 시 MUST: 같은 폴더의 `references/agent-prompts.md`를 Read한다. Phase 5~10의 에이전트 프롬프트는 모두 이 문서의 해당 섹션을 사용한다.

각 Phase 시작 직전 `{STATE_FILE}`의 `Current Phase`, `Phase Assignments.Status`, `Remaining Phases`를 갱신하고, 완료 후 결과를 append한다.

### Phase 5: TDD 구현 (Red → Green)

> Phase 5 진입 시 MUST: 같은 폴더의 `references/tdd.md`를 Read한다. Phase 5.1의 프롬프트·판정은 이 문서를 따른다.

`$TDD = false`이거나 Phase 4에서 `SKIPPED:*` 판정이면 **Phase 5.1을 건너뛰고 5.2만 실행한다** (기존 단일 구현 흐름과 동일).

#### Phase 5.1: 테스트 우선 (Red)

Spec의 추적 ID(`AC-nn`·`EC-nn`)를 근거로 **실패하는 테스트를 먼저 작성**한다. 근거 표 밖의 테스트는 작성하지 않는다.
`general-purpose` 에이전트가 `/fe-harness:unit-test --red` 를 실행하고, 오케스트레이터가 Test Map 기록과 Red 커밋을 수행한다.

| 종료 조건 | 결과 |
|----------|------|
| 모든 ID가 `red_assertion` / `already_satisfied` / `deferred_e2e` | `DONE` → Phase 5.2 |
| 일부 ID가 `cannot_compile` | `DONE` — 해당 ID 제외하고 Phase 5.2 |
| 전체 ID가 `cannot_compile` | `BLOCKED:NO_VALID_RED` — TDD SKIP 후 Phase 5.2 진행 |
| baseline에 없던 기존 테스트가 실패 | `BLOCKED:REGRESSION_AT_RED` — 기록 후 Phase 5.2 진행 |

`BLOCKED:*`여도 자율 실행은 멈추지 않는다. 선택지 제시는 Phase 11로 이연한다.

#### Phase 5.2: 구현 (Green)

`fe-harness:workflow-implementer` 에이전트로 구현 + 커밋 (컴포넌트 1개 = 커밋 1개 원칙).
TDD 활성 시 **테스트 파일 수정 금지** 규칙과 `[TestConflict]` 보고 규칙을 프롬프트에 추가한다 (`references/tdd.md`).
완료 직후 **승격 ② 평가**(변경 소스 파일 > 3 또는 금지 조건 발견 — Phase 2 집계 규칙) → light면 standard 전환을 기록하고 Phase 6으로.

### Phase 6: 빌드/타입 체크 (MANDATORY — 구현 직후 강제 실행)

```bash
{buildCommand} 2>&1 | tail -30
{typeCheckCommand} 2>&1 | tail -30
```

각 명령이 비어있으면 해당 단계를 `SKIPPED:PROFILE_EMPTY`로 기록.

| 결과 | 행동 |
|------|------|
| 성공 | Phase 7로 진행 |
| 실패 | build-fix 에이전트로 수정 → 커밋 → 재시도 |
| **3회 시도 후에도 실패** | `BLOCKED:BUILD_FAIL` — 유저에게 에러 요약 보고 후 중단 |

### Phase 7: 품질 루프 (최대 {QL_MAX}회)

```
for iteration in 1..{QL_MAX}:
  7.1 build + type-check      → Bash 직접 실행 (비어있으면 SKIPPED, 실패 시 수정 위임)
  7.2 simplify-loop           → general-purpose 에이전트
  7.3 convention-check        → general-purpose 에이전트
  7.4 test-loop               → general-purpose 에이전트 (TDD 활성 시 frozen 모드, light는 --smoke)
  7.5 scope-reviewer          → scope-reviewer 에이전트
  7.6 lint-check              → general-purpose 에이전트

[루프 종료 후 1회] 7.7 Spec 정합 Read-back — 판정만, 코드 수정 없음
```

**light**: 7.2 = `SKIPPED:TIER_LIGHT`, 7.4 = `test-loop --smoke`, 7.7 = `SKIPPED:TIER_LIGHT`. 승격 ③·⑥·⑦은 Phase 2 승격 표 — 티어 전환은 아래 종료 조건 평가보다 먼저 적용하고, ⑥·⑦은 standard iteration을 최소 1회 추가한다. 각 iteration 종료 시(light만) ⑦을 재평가한다.

7.4의 테스트 실패는 `assets/test_failures.py --baseline {STATE_FILE}`로 `## Test Baseline`과 대조해 `regression` / `pre_existing` / `new_red` / `flaky`로 분류한다 (절차·폴백: `references/tdd.md`의 "Phase 7: 회귀 대조"). `unparsed`·러너 완주 N 잔존 시 PASS 불가.

**테스트 판정**: `PASS` = `regression` 0건 + `new_red` 0건 / `WARN` = `flaky`만 / `FAIL` = 그 외

| 종료 조건 | 결과 |
|----------|------|
| `modified == false` **AND** 테스트 판정 `PASS` | 루프 탈출 → Phase 7.7 |
| `modified == false` (TDD SKIP 시) | 루프 탈출 → Phase 7.7 |
| 그 외 | 커밋 후 다음 iteration |
| `{QL_MAX}`회 도달 & 미PASS | `BLOCKED:TEST_NOT_GREEN` 기록 → 강제 탈출 → Phase 7.7 |

수정이 0건이어도 테스트가 깨져 있으면 탈출하지 않는다 — 얼어붙은 테스트가 실패하는데 소스 수정이 없으면 루프가 "성공"으로 오종료되기 때문이다.
`BLOCKED:TEST_NOT_GREEN`이어도 **자율 실행은 중단하지 않고** 이후 Phase를 계속 진행하며, 선택지는 Phase 11에서 제시한다.

**Phase 7.7은 루프 밖에서 1회만 실행한다** (light: `SKIPPED:TIER_LIGHT`). Spec을 모르는 격리된 에이전트가 테스트·구현 산출물에서 보장 동작을 복원하고, 오케스트레이터가 그것을 Spec·기존 코드와 대조해 이탈을 판정한다. 코드는 수정하지 않으며 결과는 Phase 11에서 유저에게 보고한다. 판정이 `FAIL`이어도 자율 실행은 멈추지 않는다.
프롬프트·Diff 분류·판정 기준: `references/agent-prompts.md`의 "Phase 7.7" 섹션.

### Phase 8: 컴포넌트/접근성 리뷰 (조건부)

작업 유형이 화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정인 경우만 실행. API 연동 유형은 `SKIPPED:TASK_TYPE`.

`component-reviewer` + `a11y-reviewer` 두 에이전트를 **병렬 실행**. Critical 이슈가 있으면 general-purpose 에이전트로 수정 위임.
light: `a11y-reviewer`만 단독 실행, component-reviewer는 `SKIPPED:TIER_LIGHT`.

### Phase 9: PR / Push

진입 직전 light면 승격 ⑦ 재평가(Phase 2 승격 표) — 발화 시 Phase 7을 standard로 1회 재진입한 뒤 돌아온다.

- `$HARD_MODE = false`: `fe-harness:workflow-pr` 에이전트로 PR 생성. PR URL 보고 필수.
- `$HARD_MODE = true`: PR 생략, push 전에 Assumption Gate 스캔(base와의 diff 추가 라인 + 미push 커밋 메시지에서 `[Assumption]` 검색)을 수행한다. 0건이면 `git push origin $(git branch --show-current)` 후
  "Phase 9 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)" 출력. 발견 시 push를 보류하고 아래 BLOCKED 절차를 따른다.
- **Assumption Gate BLOCKED 처리**: workflow-pr이 `BLOCKED:ASSUMPTION_UNRESOLVED`를 보고하면(또는 --hard 스캔에서 발견되면) push/PR 없이 다음 Phase로 진행하고, 최종 보고서에 태그 목록을 포함해 항목별 유저 확인을 받는다. 승인(태그 제거)·수정으로 태그가 모두 제거된 뒤 **Phase 9만 재실행**한다. 태그가 남아 있는 동안 push/PR은 금지.

### Phase 10: 성찰 (조건부 — `--reflect` 시)

`$REFLECT = true`면 `fe-harness:workflow-reflection` 에이전트 실행 (`references/agent-prompts.md`의 "Phase 10" 섹션).
`false`(기본)면 `SKIPPED:REFLECT_NOT_REQUESTED` 기록 후 Phase 11로 — 성찰은 매 실행이 아닌 주기 실행(워크플로우 5~10회마다 1회)을 권장하며, 스킵 사실과 권장 주기는 Phase 11 보고서가 고지한다.

## Phase 11: 최종 보고

> Phase 11 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고 "Phase 11 실행 절차", "Workflow Report 템플릿", "md 아카이브", "보완점 적용 상세"를 따른다.

절차 요약 (각 항목의 상세 규칙: templates.md의 "Phase 11 실행 절차" — 순서 변경 금지):
① `{WORK_REPORT}`에 슬림 Workflow Report 1회 Write(채팅에는 경로·§1·유저 결정 항목만. 미결 질문은 `{IMPL_NOTES}`의 `## 미결 질문`만 읽어 상단 표면화) → ② TDD 미해결 항목 유저 결정 (첫 결정 지점) → ③ Read-back Diff 유저 결정 (보완점보다 먼저 — 코드·Spec에 직접 영향) → ④ 보완점 적용 질문 (Phase 10이 `DONE`일 때만 — `SKIPPED:*`면 생략하고 **실제 상태 코드**와 사유별 문구로 고지: templates §6 분기) → ⑤ 상태 파일 마감 후 `assets/workflow_archive.py`로 `{REPORT_DIR}`에 md 아카이브(부록 A 실행 요약 / B 상태 파일 전문 / C Implementation Notes) 생성.
수정이 필요한 결정은 유저 승인 후에만 수행한다 (Spec 외 변경 금지 원칙). ②~④의 결정은 받는 즉시 `## Final Decisions`에 기록한다 (재개 시 재질문 금지).

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 (예: `SKIPPED:PROFILE_EMPTY`, `SKIPPED:TASK_TYPE`, `SKIPPED:USER_OPT_OUT`, `SKIPPED:REFLECT_NOT_REQUESTED`, `SKIPPED:TIER_LIGHT`) |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 (예: `BLOCKED:BUILD_FAIL`, `BLOCKED:MAX_ITERATIONS`, `BLOCKED:NO_VALID_RED`, `BLOCKED:TEST_NOT_GREEN`) |
| `PASS` / `WARN` / `FAIL` | 테스트 판정, Read-back 판정 |

TDD 진단 분류(`red_assertion`·`already_satisfied`·`cannot_compile`·`deferred_e2e`·`regression`·`pre_existing`·`new_red`·`flaky`·`unparsed`·`rerun_incomplete`)는 **상태 코드가 아니라 데이터**다.
`## TDD Test Map`과 회귀 대조 표의 셀 안에서만 쓰고, 티어 승격 `tier_escalated({트리거})`·스크립트 폴백 `script_fallback({스크립트}:{사유})`은 `Phase Results`·보고서 "축소 실행 내역" 표의 `진단` 셀 안에서만 쓴다. Phase Assignments의 Status 열에는 등장시키지 않는다 (`docs/skill-authoring.md` §5).

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/templates.md` | Phase 4 (상태 파일·라이브 노트), Phase 11 (보고서·md 아카이브·보완점) |
| `references/tdd.md` | Phase 4 (TDD 판정·baseline), Phase 5 진입 시 |
| `references/agent-prompts.md` | Phase 5 진입 시 (Phase 5.2~10 프롬프트 — Phase 10은 `--reflect` 시만) |

## 흐름 요약

```
[유저 대화] — Phase 1~3 전체가 단일 EnterPlanMode 컨텍스트
Phase 1: EnterPlanMode → /request로 Technical Spec (유저 확인) + 풀스택 판정
Phase 2: 난이도 산정 (1-10, A 코드 복잡도 + B 회귀 리스크) + 검증 티어 판정 (light / standard)
Phase 3: Plan 작성 → 다관점 1회 보강 → Codex 검증 루프 (최대 {PLAN_MAX}회) → ExitPlanMode
Phase 4: feature 브랜치 + 상태 파일 + implementation-notes.md + 회귀 baseline → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 5.1: 테스트 우선 (Red) — Spec ID 근거로 실패 테스트 선작성 + 스텁, Red 커밋
Phase 5.2: 구현 (Green) — workflow-implementer, 테스트 파일 수정 금지
Phase 6: {buildCommand}+{typeCheckCommand} 체크 (실패 시 수정 최대 3회)
Phase 7: 품질 루프 최대 {QL_MAX}회 (7.1 빌드 → 7.2 simplify → 7.3 convention → 7.4 test → 7.5 scope → 7.6 lint)
         탈출 조건 = 수정 0건 AND 테스트 판정 PASS (회귀 3분류 대조)
         light: 7.2 SKIP · 7.4 --smoke · 7.7 SKIP — 승격 트리거 발생 시 standard로 전환 (단방향)
Phase 8: component-reviewer + a11y-reviewer (병렬, 컴포넌트 변경 시만 — light는 a11y만)
Phase 9: workflow-pr (--hard: push만)
Phase 10: 성찰 (--reflect 지정 시만 — 기본 SKIPPED:REFLECT_NOT_REQUESTED)

[유저 대화]
Phase 11: 슬림 Workflow Report → 유저 결정 (TDD·Read-back·보완점) → md 아카이브 (부록 A/B/C) → 정리
```
