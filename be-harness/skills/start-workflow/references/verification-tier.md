# 검증 티어 (Verification Tier)

> 이 문서는 `start-workflow` 스킬의 Pre-flight(착수 질문), Phase 2(선언 확인), Phase 4.1(산정·판정·Plan 깊이), Phase 4.4(재판정·승인 기준선), Phase 5·6·8·10(깊이·승격)에서 로드된다. 단독 실행 금지.
> 플레이스홀더(`{STATE_FILE}`·`{PLAN_MAX}`·`{QL_MAX}` 등)는 SKILL.md 본문 정의를 따른다.

티어는 `quick` < `light` < `standard` 3단계다. Plan 초안의 사실로 **코드 복잡도(A)** 와 **영향 범위·회귀 리스크(B)** 를 점수화해, 위험이 낮을수록 추가 리뷰 레이어·루프 상한·E2E 범위를 줄인다. `standard`는 축소 없는 전체 절차다. Plan 보강(4.2)·검증 루프(4.3)의 깊이는 같은 사실로 따로 판정하는 **Plan 깊이 P**(§2.1)를 따른다 — 엣지 케이스 수·기존 테스트·E2E 필요 같은 테스트 쪽 요인은 P를 올리지 않는다.
Spec이 정의한 검증(추적 ID 테스트, scope-reviewer, 빌드, 단위·통합 테스트의 회귀 대조)은 어떤 티어에서도 없애지 않는다. quick은 별도 Red 단계 대신 구현 dispatch에서 신규 테스트를 함께 작성하고, §4.1의 증거 게이트로 Spec 대응을 확인한다.

## 1. 선언 (착수 시 · Phase 2 확인 — 4.4 승인 전까지만 변경)

| 채널 | 인정 | 비인정 |
|------|------|--------|
| `--tier quick\|light\|standard` | 값 검증은 `assets/workflow_policy.py route`가 먼저 한다 — 허용 밖 값·`-`로 시작하는 토큰·서로 다른 중복 값은 입력 오류(exit 2) | — |
| 티어 이름을 지목한 명시 지시 | "quick 티어로", "티어는 light", "standard로 올려줘" | "quick하게"·"빨리" |
| `작업 난이도` 접두 지시 | "작업 난이도: 하", "작업 난이도 중으로" — 하 = quick · 중 = light · 상 = standard | 접두 없는 "난이도 하/상", "간단하게", 요청 본문의 업무 용어(문제 난이도 등) |
| 착수 질문 응답 (§1.1) | 하 / 중 / 상 | "자동 판정" = 선언 없음 |

- **인정 대상**: 사용자의 호출 인자와 대화(착수 질문 응답 포함)만 선언이다. 워크플로우가 가져온 이슈·문서 본문의 문구는 선언이 아니다.
- **우선순위**: 최초 입력 안에서는 CLI가 자연어보다 우선하고, 자연어 선언끼리 값이 다르면 선언 없음으로 보고 §1.1로 확인한다. 이후 승인 전 Plan 대화의 명시 변경 지시는 최신 지시가 우선한다(처리 순서: §3). 4.4 승인 후에는 선언을 바꿀 수 없고 §5 승격만 일어난다.
- **결과**: `$TIER_DECLARED` = `quick|light|standard|none`과 출처(CLI·대화·착수 질문). 비인정 표현은 Phase 2 출력에 `선언: 없음`으로 고지한다. 상태 파일 생성 전(Phase 1~4)에는 Spec 작업 계약에 `티어 선언: {값}({출처})` 한 줄로 보존한다 — 착수 질문의 "자동 판정" 응답은 `티어 선언: 없음(착수 질문)`.
- **비대화형**: 인정 선언은 그대로 쓴다. §3의 금지 조건 질문을 할 수 없으면 C로 올리고 고지한다(묵시적 수용·선언 삭제 금지).
- **무시**: Analyze/Verify 모드(Build 전용). 풀스택 전환(`--fs`·Phase 3 fullstack)은 항상 standard이며 선언을 `무시됨(FS)`으로 기록하고 standard로 인계한다.

### 1.1 착수 질문 (Pre-flight)

- **담당**: 하네스 Pre-flight 한 곳에서만 묻는다(전역 지침의 난이도 질문은 하네스 실행에 적용하지 않는다).
- **조건**: Build 모드 신규 실행 · 대화 가능(`references/codex-mode.md` §2와 같은 판정) · 최초 입력에 인정 선언 없음 · 이번 작업에서 아직 묻지 않음. 재개(상태 파일 기준)·비대화형·풀스택에서는 묻지 않는다.
- **시점**: Codex 모드 resolve에서 Codex 질문 필요 여부와 함께 먼저 판정한다. 둘 다 필요하면 한 AskUserQuestion에 두 질문을 담고, 착수 질문만 필요하면 그 자리에서 묻는다 — SKIP 사전 경고보다 먼저다(선언 quick의 E2E 누락 고지가 이 값을 쓴다).
- **선택지** ("작업 난이도를 정할까요?"): `자동 판정 (권장)` — Plan 초안의 사실로 판정 / `하 (quick)` — Plan 리뷰·E2E 생략 / `중 (light)` — Plan 리뷰 최대 보강 1 + 루프 2, smoke E2E / `상 (standard)` — 전체 테스트 절차, Plan 리뷰는 설계 판정 이내(§2.1).
- **응답**: 하·중·상은 선언(출처 `착수 질문`)이며 §3 충돌 규칙이 그대로 적용된다. "자동 판정"은 선언 없음이고, §1 결과대로 보존해 위임·컨텍스트 복원 뒤 다시 묻지 않는다.

## 2. 산정·판정 (Phase 4.1 Plan 초안 직후 1회 · 4.4 재판정)

**산정 규칙**
- 입력: Plan의 파일 목록·계약·동작 사실, 그리고 Plan 변경 경로(없으면 Spec `참조 구현` 경로)로 실행한 아래 출력(존재·최근 변경 커밋 수·동반 테스트·과거 워크플로우 이력)을 B축 `변경 영역 기존 테스트`·`기존 동작 변경 범위`의 근거로 쓴다. 경로가 없거나 스크립트가 exit ≠ 0이면 해당 행은 `UNKNOWN`.
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/risk_facts.py --paths {변경 경로들} --report-dir {REPORT_DIR} [--test-dir {설정된 testDir} …]
  ```
- 각 축 점수 = 요소별 밴드 점수의 **최댓값**(평균 금지). 판정 근거가 없는 요소는 `UNKNOWN` = **높음 밴드**(fail-safe).
- **종합 난이도 = `max(A, B)`** 는 4.1에서 **동결**한다. Model/Effort 등급표와 `CODEX_MODELS` `tiered` effort의 입력이며 이후 바꾸지 않는다. 4.4·승격 재판정의 A/B(현재 사실)는 동결값과 별도로 기록한다.

`candidate`는 같은 Go 패키지/testDirs의 탐색 후보다. 실제 단언·실행 범위로 관련성을 확인한 뒤 B축을 판정하고, 미확인은 UNKNOWN으로 유지한다. `Y`도 파일 존재 근거이며 커버리지/티어 자격의 단독 증거가 아니다.

### A. 코드 복잡도

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 레이어 | 단일 | 2~3개 | 4개+ (공유 레이어 포함) |
| DB 변경 | 없음 | 컬럼 추가 | 신규 테이블 |
| 외부 연동 | 없음 | 기존 gRPC | 신규 gRPC |
| 비즈니스 복잡도 | 단순 CRUD | 조건 분기 3개 이하 | 상태 머신 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

### B. 영향 범위·회귀 리스크

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 기존 API 호환성 | Breaking change 없음 | 선택 필드 추가 | 필수 필드/응답 구조 변경 |
| DB 데이터 영향 | 신규 테이블만 | 기존 테이블 컬럼 추가 | 기존 데이터 마이그레이션 필요 |
| 공유 모듈 수정 | 없음 | 유틸리티/공통 함수 | 미들웨어/인터셉터/DI |
| 다른 서비스 의존 | 독립적 | 같은 repo 내 참조 | 외부 서비스 연동 변경 |
| 롤백 용이성 | 즉시 가능 | 마이그레이션 롤백 필요 | 데이터 복구 필요 |
| 기존 동작 변경 범위 | 없음·신규 경로만 | 기존 경로에 분기 추가 | 기존 경로의 동작 변경 |
| 변경 영역 기존 테스트 | 단위 + E2E 있음 | 일부만 있음 | 없음 · `UNKNOWN` |

출력: `난이도: 코드 [A]/10 + 리스크 [B]/10 — [근거]`

### 판정표 (위에서부터 첫 일치 = 계산 티어 C)

| # | 조건 | C |
|---|------|---|
| 1 | 금지 조건 ≥ 1 · 전략 `parallel-slices` · TDD SKIP 예정(`--no-tdd`·`{testCommand}` 없음·관측 가능한 조항 0) | standard |
| 2 | quick 조건 Q-a~Q-f 전부 충족 | quick |
| 3 | A·B 모든 요소 ≤ 중간, `UNKNOWN` 0 | light |
| 4 | 그 외 | standard |

**quick 조건** — 확인할 수 없는 사실은 불충족으로 본다.

| # | 조건 |
|---|------|
| Q-a | A·B에 '높음'·`UNKNOWN` 요소가 없다. 단 B `변경 영역 기존 테스트`의 '없음·`UNKNOWN`'은 허용하고 아래 기본 동작 EC 테스트로 보완한다 |
| Q-b | 변경 소스 ≤ 3 (§5 집계 규칙을 Plan 파일 목록에 적용) |
| Q-c | 스키마·데이터 변경, 신규 외부 연동, 신규 의존성이 모두 0 |
| Q-d | API 계약 변경이 없거나 선택 필드·파라미터 추가뿐이다 |
| Q-e | 기본 동작 불변 — 신규 입력이 없으면 기존 결과와 같다(디버깅은 RC 재현 조건 밖 입력의 결과가 기존과 같다) |
| Q-f | Spec의 관측 가능한 추적 ID 전체(`AC`·`EC`·`RC`)를 단위(또는 설정된 통합) 테스트로 검증할 수 있다 — `deferred_e2e` 예상 0 |

**quick 의무**: Q-e가 성립하면 Spec에 기본 동작 EC(`신규 입력 없음 → 기존 결과 동일`, 디버깅은 `RC 조건 밖 입력 → 기존 결과 동일`)를 추가하고 6.2에서 테스트로 고정한다. Q-e 미충족인데 선언 quick을 유지한 경우(§3)에는 넣지 않는다 — 바뀐 동작은 해당 AC가 검증한다.

**금지 조건** — 자동 판정이나 선언만으로는 낮출 수 없다. 선언 티어를 유지하려면 §3의 승인 전 질문에서 사용자가 항목별로 수용해야 한다.

| 금지 조건 |
|----------|
| 기존 테이블 스키마 변경 · 데이터 마이그레이션 |
| 인증 · 인가 · 암호화 · 개인정보 처리 |
| 결제 · 정산 |
| 공유 미들웨어 · 인터셉터 · DI wiring |
| Breaking change (API 계약) |
| 외부 서비스 연동 변경 |

- 출력(4.1·4.4): `검증 티어: {T} — 선언 {D|없음}({출처}), 계산 {C} (#{판정 행}: {근거}), A [a]/B [b], 금지 조건 [해당 없음|{항목}] · Plan 깊이 {P} (P#{행}[, 선언 상한])` — Plan과 함께 `ExitPlanMode`에서 승인.
- **4.4 재판정**: 최종 Plan으로 판정표와 §3을 다시 적용하고(상향만), **승인 기준선 R0**를 확정한다. R0 = 판정 사실(소스 목록·수, A/B 요소값, 금지 조건, 계약 변경, TDD 적용·SKIP 사유, `deferred_e2e` ID, 실행 전략) + 수용 예외 + 선언 유지 사유. R0는 이후 갱신하지 않는다. P는 §2.1대로 재판정한다.
- 상태 파일 `## Verification Tier`(템플릿: `references/templates.md`)에 선언·C0(4.1)·R0·유효 티어·Plan 깊이·수용 예외·승격 이력을 기록하고, `## Flags`의 `TIER`에 유효 티어를 적는다.

### 2.1 Plan 깊이 P (4.1 · 4.4 — T 확정 직후)

Plan 보강(4.2)·검증 루프(4.3)의 깊이다. §2의 같은 사실로 판정하되 설계 위험과 무관한 테스트 쪽 요인은 쓰지 않는다. 4.2·4.3·`{PLAN_MAX}`·승격 ①·⑤의 조건만 P를 따르고, 나머지 단계는 T를 따른다.

- **쓰지 않는 요인**: A `엣지 케이스`, B `변경 영역 기존 테스트`(두 요소의 `UNKNOWN` 포함), Q-b, Q-f, 판정표 #1의 TDD SKIP.

| # | 조건 (위에서부터 첫 일치) | P_calc |
|---|------|--------|
| P1 | 금지 조건 ≥ 1 · 전략 `parallel-slices` | standard |
| P2 | Q-c·Q-d·Q-e 충족, 나머지 A·B 요소에 '높음'·`UNKNOWN` 없음 | quick |
| P3 | 나머지 A·B 요소에 '높음'·`UNKNOWN` 없음 | light |
| P4 | 그 외 | standard |

- **P2의 Q-e**: 응답 필드 추가도 기존 필드·값·상태 코드가 그대로면 충족으로 본다(P 판정에만 적용 — T의 Q-e·quick 의무는 그대로).
- **P = min(T, P_calc)** — 선언은 Plan 깊이의 상한이다. P1~P3는 판정표 #1·quick·light 조건의 부분 조건이므로 P_calc ≤ C이고, 미선언이면 P = P_calc다.
- 깊이: standard = 4.2 3에이전트 × 2배치 · `{PLAN_MAX}` 5 / light = 1에이전트 3관점 · 2 / quick = 4.2·4.3 `SKIPPED:PLAN_QUICK` · 0.
- 예: 선택 쿼리 파라미터 추가(EC 7개, DB 의미는 E2E로 확인) → T standard(엣지 케이스 '높음'), P quick(P2) — Plan 리뷰 없이 진행하고 테스트는 standard로 한다.
- **4.4 재판정**: P′ = max(P, min(T′, P_calc′)) (상향만). P가 quick에서 올랐으면 건너뛴 4.2·4.3을 새 P로 실행한 뒤 4.4로 돌아온다. 이미 실행해 수렴했으면 재사용하고 `미재실행: 4.2`를 기록한다. T만 오르면 4.2·4.3을 다시 실행하지 않는다.
- **기록**: `SKIPPED:PLAN_QUICK`은 4.4 확정 뒤 Phase 5 상태 파일 생성 때 기록한다(4.4 재판정으로 실행될 수 있으므로). `## Verification Tier`의 `Plan 깊이` 줄에 P·판정 행·4.2 실행·`{PLAN_MAX}`·변경 이력을 적는다.

## 3. 선언과 계산의 충돌 (4.1 직후 · 4.4 재판정)

| 경우 | 유효 티어 T |
|------|------------|
| 미선언 | C |
| D ≥ C | D |
| D < C, 원인에 금지 조건 포함 | AskUserQuestion "D 유지 / C로 상향"(원인 전부 표시). 유지하면 **수용 예외** {금지 항목·정규화 경로·행위·Plan 버전}을 기록한다 |
| D < C, 원인에 금지 조건 없음 (규모·A/B 요소(`UNKNOWN` 포함)·그 밖의 quick 조건 미충족·TDD SKIP·parallel-slices·`deferred_e2e`) | D 유지 + 승인 화면 1줄 고지. TDD SKIP이면 "회귀 대조 없음"을 적고, parallel-slices면 sequential로 실행한다 |

- 4.4 재판정은 계산 결과로 티어를 내리지 않는다(상향만). T가 정해지면 §2.1로 P를 정한다.
- **승인 전 선언 변경**: ① 진행 중 리뷰는 결과를 받아 기록한다 ② 새 D로 이 표를 다시 적용해 T를 정한다 ③ §2.1로 P를 정한다 ④ P가 올랐으면 건너뛴 4.2는 새 P로 실행하고, 4.3은 수렴했으면 재사용(`미재실행: 4.3`)·진행 중이면 카운터를 승계해 새 상한까지 계속한 뒤 4.4로 돌아온다(승인 전이므로 가능) ⑤ P가 내렸으면 새 `{PLAN_MAX}`를 적용하되, 새 P가 quick이거나 이미 새 상한 이상 수행했으면 추가 dispatch 없이 종료한다 — 4.3 수행 이력이 있으면 `USER-INTERRUPTED`(결과·잔존 이슈 보존), 없으면 `SKIPPED:PLAN_QUICK`. 이 종료에는 승격 ①을 적용하지 않는다.
- 선언 quick이고 Pre-flight에서 E2E 전용 설정이 누락됐으면, 4.4 승인 화면에 "승격 시 E2E는 `SKIPPED:{사유}`로 기록" 문구를 포함한다(승인 = 동의).

## 4. 티어별 깊이

| 단계 | standard | light | quick |
|------|----------|-------|-------|
| Pre-flight E2E 전용 누락 | 선택지 | 선택지 | 선언 quick: 선택지 대신 1줄 고지 + 4.4 동의(§3). 미선언은 선택지(티어 미정) |
| 1 Spec | request 또는 직접 | 동일 | 선언 quick: request 생략 — 직접 Spec 분기 계약 + quick 의무 EC + 디버깅 `RC-nn` 표 |
| 4.2 Plan 보강 — **P 기준**(§2.1) | 3에이전트 × 2배치 | **1에이전트 3관점**(엣지 케이스 · 기존 코드 영향 · 더 단순한 경로) | `SKIPPED:PLAN_QUICK` |
| 4.3 `{PLAN_MAX}` — **P 기준** | 5 | **2** (소진 시 승격 ①) | 0 — `SKIPPED:PLAN_QUICK` |
| 5 baseline | unit + integration | 동일 | 동일 |
| 6.1 Red | 실행 | 실행 | `SKIPPED:TIER_QUICK` |
| 6.2 구현 | 구현 | 구현 | **구현 + 신규 테스트 1 dispatch** (§4.1) |
| 7 빌드 | 실행 | 실행 | 실행 |
| 8 `{QL_MAX}` | 3 | **2** | **2** (이슈가 없으면 1회에 탈출) |
| 8.2 simplify | 통합 스캐너 (simplify + convention) | `SKIPPED:TIER_LIGHT` — 통합 스캐너를 **convention 전용 프롬프트**로 호출 | `SKIPPED:TIER_QUICK` |
| 8.3 convention | 실행 | 실행 | `SKIPPED:TIER_QUICK` (스캐너 미호출) |
| 8.4 scope | 실행 | 실행 | 실행 + §4.1 대응 확인 |
| 8.6 E2E | `e2e-test-loop` (full, 최대 5회) | `e2e-test-loop --smoke` (BASE-01 + EC-* 전수, 최대 3회) | `SKIPPED:TIER_QUICK` |
| 8.7 통합 테스트 | 실행 | 실행 | 실행 |
| 8.8 Read-back | 1회 | `SKIPPED:TIER_LIGHT` | `SKIPPED:TIER_QUICK` |
| 9 문서 동기화 | 조건부 | 조건부 | 조건부 |
| 10 PR 필수 kind | §4.2 | §4.2 | §4.2 |

- **P 기준** 행의 열은 Plan 깊이 P 값이다(§2.1). 나머지 행은 유효 티어 T를 따른다.
- 표에 없는 단계(8.1 · 8.5)는 티어와 무관하게 같고, `## Quick Test Evidence`가 있으면 §4.1의 게이트·보완을 더한다. 생략 단계의 `SKIPPED:TIER_*`는 도달 시점에 기록한다 — 승격으로 실행될 수 있으므로 미리 기록하지 않는다.

### 4.1 quick 테스트 동반 (TDD 활성 시만)

TDD SKIP이면 6.2는 구현만 하고 이 절은 적용하지 않는다.

- **작성 (6.2)**: 구현 프롬프트에 quick 테스트 동반 모드 블록(`references/tdd.md` "Phase 6.2")을 추가한다.
  - Spec 추적 ID(`AC`·`EC`·`RC` — unit-test Red 근거 집합과 동일) 근거의 **신규** 테스트만 작성한다.
  - 기존 테스트(케이스·단언·fixture)는 수정하지 않는다. 충돌하면 `[TestConflict]`로 보고한다.
  - 작성한 테스트를 직접 실행해 green을 확인한다.
  - Spec ID ↔ suite(`unit`, 또는 `{makeTestCommand}` 설정 시 `integration`) ↔ 러너 네이티브 정확 ID ↔ 파일 목록을 반환한다(식별자 규칙: `references/tdd.md`).
- **기록**: 오케스트레이터는 반환 목록을 상태 파일 `## Quick Test Evidence`에 기록한다. `## TDD Test Map`에는 등재하지 않는다. `test_failures.py`는 Test Map만 읽으므로 quick 테스트의 실패는 baseline에 없는 식별자 = `regression`(→ 승격 ③)으로 분류된다. flaky는 기존 재실행 규칙을 따른다.
- **종료 증거 게이트**: Evidence 행의 suite에 해당하는 실행 로그 원문(unit = 8.1, integration = 8.7 — `references/tdd.md`의 verbose/JSON 계약, 첫 실행부터 수집)에서 행마다 **정확 ID의 PASS 줄**을 확인한다. 그 실행에서 실패한 ID가 같은 트리 재실행에서 PASS로 명시돼 `flaky`로 분류되면 재실행 로그의 PASS 줄을 증거로 인정한다(판정 WARN — 수정 뒤 실행은 flaky 증거가 아니다).
  - 다음이면 그 suite 결과를 `INCONCLUSIVE`(검증 미완료)로 기록한다: 미출력 · SKIP·pending·todo · 시작만 출력 · 같은 ID의 선언이 2개 이상(중복 제목) · PASS와 SKIP 혼재.
  - `INCONCLUSIVE`는 test-summary에서 FAIL로 집계되므로 기존 종료 규칙·`BLOCKED:TEST_NOT_GREEN`·원격 반영 보류를 그대로 따른다.
  - ③의 "판정 불가"(러너 미완주·`unparsed`)가 아니므로 승격하지 않는다. 테스트 자체의 문제는 `[TestConflict]`로 보고하고 `references/tdd.md` 판정표를 따른다 — 단언이 Spec과 다른 테스트 오류만 오케스트레이터가 수정·Evidence 갱신하고, 그 밖의 동결 테스트 문제는 미해결로 Phase 12 결정에 넘긴다.
- **필수 대응 게이트** (Red 단계가 맡던 Spec ID ↔ 단언 대응을 대신한다)
  - 필수 ID 집합 = 승인 Spec의 관측 가능한 추적 ID 전체(`AC`·`EC`·`RC`) + quick 의무로 넣은 기본 동작 EC. R0가 수용한 `deferred_e2e` ID는 빼고 보고서에 "미검증(E2E 이연)"으로 남긴다.
  - Evidence에 필수 ID마다 테스트가 1개 이상 있어야 한다. 누락·빈 Evidence는 `INCONCLUSIVE`다.
  - 8.4 scope 리뷰가 Evidence의 각 테스트가 해당 ID의 입력·단언(`file:line`)으로 요구를 실제 검증하는지 확인한다(추가 dispatch 없음). 잘못된 대응(예: "결과 동일" EC에 상태 코드만 보는 기존 테스트 연결)은 scope 이슈다.
  - **보완**: Evidence 누락·잘못된 대응 이슈에 한해 8.5가 quick 동반 모드 규칙대로 **신규 테스트 추가만** 할 수 있다(기존 테스트 수정 금지 유지). 결과는 Evidence에 추가하고 다음 iteration에서 다시 확인한다.
  - 최종 성공 = 필수 ID 전체 대응 + scope 대응 확인 + 정확 ID PASS 증거. 상한 안에 충족하지 못하면 `INCONCLUSIVE` → `BLOCKED:TEST_NOT_GREEN` → 원격 반영 보류. 승격·재개·finalization 이후에도 이 의무는 유지된다.
- 위 보완 예외와 오케스트레이터의 `[TestConflict]` 판정 수정을 빼면 6.2 이후 테스트는 동결된다(8.5 "TDD 활성 시 테스트 파일 수정 금지").
- Evidence가 생긴 뒤 승격해도 이 절의 게이트·보완·의무는 그대로 적용한다(6.1 `미재실행`이면 Evidence가 Spec 대응의 유일한 근거다).

### 4.2 필수 kind · 마감

- PR 직전 `check-current`의 필수 kind는 유효 티어와 profile 명령 설정으로 **정적으로** 정한다(실행 이력으로 정하지 않음). quick = `scope` · `unit` · `integration`(`{makeTestCommand}` 설정 시). light·standard = 기존 필수 검증 그대로.
- finalization 재검증은 현재 티어의 검증 집합을 따른다 — 생략 단계를 자동 복원하지 않는다.
- scope는 정상 경로 1회(8.4)다. 이후 트리가 바뀌면(8.5 · 문서 · VERSION) `references/review-evidence.md`의 보완 절차를 따르고, 미완료면 원격 반영을 보류한다.
- 재진입·재실행은 `references/result-contract.md`의 "새 iteration"과 `references/quality-loop.md`의 "새 미사용 로그 경로" 규칙을 그대로 쓴다(새 카운터 없음).

## 5. 승격 (단방향 quick → light → standard, 여러 단계 동시 가능)

자율 구간의 승격은 **질문 없이 기록하고 진행**한다. 티어 전환은 항상 해당 루프의 **종료 조건·상한 평가보다 먼저** 적용한다.

**재판정** (②·⑦ — 유효 티어 T < standard인 동안)
- 현재 사실(실제 diff, 금지 조건, 계약·스키마·의존성, 보고된 `deferred_e2e`)로 판정표를 다시 실행해 C′를 구한다.
- 단 R0에서 **사용자가 수용한 원인**(§3 유지 행)은 승인 값 이내면 원인에서 제외한다. "이내"는 값 유형별로 판정한다.
  - 수치(소스 수, A/B 요소 밴드): 현재 값 ≤ 승인 값
  - 목록(`deferred_e2e` ID): 현재 목록 ⊆ 승인 목록
  - 범주(TDD SKIP 사유, 전략, 불충족 quick 조건): 같은 값
  - 수용 예외: 금지 항목·정규화 경로·승인 행위/대상·Plan 버전이 **모두 일치**할 때만 제외한다. 같은 경로의 다른 행위는 새 원인이다.
  - `UNKNOWN`: R0에서 수용한 같은 요소·대상의 `UNKNOWN`이 그대로 지속되면 제외한다. 새 요소의 `UNKNOWN`, 새 불확실성, 승인 후 새로 확인된 위험은 원인으로 센다.
- **T := max(T, C′)**. 미선언 실행은 제외 대상이 없다. R0는 갱신하지 않고, 사실이 줄어도 강등하지 않는다.

| # | 시점 | 트리거 | 효과 |
|---|------|--------|------|
| ① | Phase 4.3 (P light) | 리뷰어 CONCERN/REJECT로 light 상한 2회 소진 (상한 평가 전에 판정 — 승인 전 선언 하향으로 줄어든 상한은 제외, §3) | P·T standard, `{PLAN_MAX}` = 5 복원, iteration·동일 이슈 카운터 승계(3회차부터). 4.2는 재실행하지 않음 |
| ② | Phase 6.2 완료 직후, Phase 7 진입 전 | 재판정 C′ > T (집계 규칙: 아래) | 새 티어로 Phase 7·8 |
| ③ | Phase 8.1 또는 8.7 회귀 대조 | `regression` ≥ 1, 또는 회귀 판정 불가(러너 완주 N / `UNPARSED` 잔존을 오케스트레이터도 분류 못 함) | standard, `{QL_MAX}` = 3 복원. 승격 이후 **시작되는** 단계부터 standard — 8.1 승격은 같은 iteration의 8.6부터, 8.7 승격은 다음 iteration부터 full E2E. 회귀·판정 불가 = 테스트 판정 FAIL이므로 다음 iteration이 보장되며, 복원된 상한에서도 미PASS면 기존대로 `BLOCKED:TEST_NOT_GREEN`. 루프 후 8.8 Read-back 실행 |
| ④ | Phase 5 baseline 수집 | R0에 없던 TDD SKIP, 또는 수집 실패(`수집 실패 — regression 판정 불가` 선택) | standard. Phase 6 전이므로 TDD 활성이면 6.1을 실행한다 |
| ⑤ | Phase 4.3 (P light) | `CODEX-UNAVAILABLE` = Claude 패널 실패 (유효 verdict 3개 미달 — `references/codex-mode.md` §6) | T standard 기록 후 기존 규칙대로 진행. Codex 호출 실패의 패널 폴백(§7)은 리뷰 수행으로 간주(승격 아님) |
| ⑥ | Phase 8.6 E2E (light) | (a) `BLOCKED:MAX_ITERATIONS` · `BLOCKED:NO_PROGRESS` 종료 (b) e2e-test가 `실행 수준: full(smoke 미적용: …)` 보고 (실행 가능 smoke 케이스 0건 · EC 표 없음 = 검증 근거 부족) | standard (`{QL_MAX}` = 3) + **현재 iteration 종료 후 standard iteration을 최소 1회 추가** (탈출 조건 평가는 그 뒤부터) |
| ⑦ | 각 품질 루프 iteration 종료 시 + Phase 10 진입 직전 + finalization 반영 직전 (특화 하네스 Codex 리뷰 수정 반영 후 포함) — T < standard인 동안 | 재판정 C′ > T | 새 티어 + 새 티어 iteration 최소 1회 추가. Phase 10 직전이면 Phase 8을 **새 티어 루프로 재진입** (새 루프, 상한 = 새 티어 `{QL_MAX}`, 종료 조건 동일, 미PASS → `BLOCKED:TEST_NOT_GREEN`), 이력 `⑦: Phase 8 재진입`. 재진입 루프 종료 시 `검증 트리: {git rev-parse HEAD} (dirty: Y/N)` 기록. 특화 하네스 Codex 리뷰가 있는 경우: 재진입 루프에서 파일이 1회라도 수정됐으면 그 트리에 대해 리뷰를 1회 재실행(잔여 횟수 내), 수정 없음 → 기존 APPROVE 유효 |

**②·⑦ 집계 규칙**
- 기준 = `## Flags`의 `START_SHA` (= `## Verification Tier`의 `시작 커밋`, baseline SHA와 동일).
  ```bash
  git cat-file -e {START_SHA} && { git diff --name-only {START_SHA}; git ls-files --others --exclude-standard; } | sort -u
  ```
  커밋·스테이징·작업 트리·untracked 전부 포함, 삭제·이름 변경도 1건.
- 제외는 **명시 패턴만**: 테스트 `_test.go` · `*.test.*` · `*.spec.*` · `__tests__/` · `testdata/` · `e2e/`, 생성물 `vendor/` · `node_modules/` · `*.pb.go` · `*.gen.*` · `mocks/` · `__pycache__/` · `*.pyc`, 문서 `*.md` · `docs/` · profile `{apiDocsPath}` 파일, 버전 root `VERSION` · `VERSION.txt`. 패턴에 없는 파일은 전부 소스로 집계한다(분류 불가를 제외로 해석하지 않음). 제외 파일도 scope·freshness 검증 대상에는 그대로 포함한다.
- 집계한 파일 목록을 승격 이력 행에 기록한다.
- `START_SHA`가 없거나 `git cat-file -e`로 도달 불가 → `## Test Baseline`의 `커밋:`으로 대체. 그것도 없으면 판정 불가로 **standard 강제** + 이력 `②: 시작 SHA 판정 불가` (사후 HEAD로 대체 금지).

**효과**
- 아직 도달하지 않은 단계는 새 티어대로 실행한다.
- 지난 단계: 승인 후 4.2/4.3은 `미재실행: 4.2`(4.3)으로 기록한다. 6.1은 Phase 6 전(④)이면 실행하고, 그 뒤면 `미재실행: 6.1`로 기록한다.
- 새 티어 iteration을 최소 1회 보장한다(③은 FAIL로 다음 iteration 보장, ⑥·⑦은 1회 추가). 어떤 경로든 light는 convention·smoke E2E, standard는 simplify·full E2E와 루프 후 Read-back이 최소 1회 실행된다.
- 승격 뒤 필요한 E2E의 환경이 없으면 기존 SKIP 코드로 기록한다. 선언 quick은 4.4 승인에서, 미선언은 Pre-flight 선택지에서 이미 동의한 상태다.

**기록**
- `Phase Results` 진단 셀: `tier_escalated({①..⑦})`.
- `## Verification Tier` 승격 이력 행(시점 / 트리거 / 근거 목록 / 조치 / 의무 / 완료)과 `## Flags`의 `TIER`를 **같은 Edit**로 갱신한다. 의무 = 승격으로 생긴 실행 의무(예: `Phase 8 재진입`, `6.1 실행`), 완료 = Y/N.
- 재개 시 완료 N인 의무를 먼저 처리한다. 다단계 승격은 최종 티어의 의무로 합산한다(상위 티어 실행이 하위 의무를 충족). 이력과 Flags가 다르면 높은 티어를 채택하고 그 의무까지 복원한다. Phase 12 마감 전에 모든 의무의 완료를 확인한다.
- Workflow Report §1: `검증 티어: {이전} → {최종} ({트리거}, 미재실행: {목록})`.
- **구 상태 재개**: `TIER: light|standard`는 그대로 쓴다. 신규 필드가 없으면 선언 없음·C0 = TIER로 본다. 의무 열이 없는 구 이력은 조치 열과 `Phase Results`에서 의무·완료를 복원하고, 근거가 없으면 미완료로 본다(예: `⑦: Phase 8 재진입` + 재진입 결과 없음 → 재진입 수행). baseline은 재수집하지 않는다.

## 6. smoke E2E (light)

- Phase 8.6은 `e2e-test-loop --smoke`로 호출한다. e2e-test는 `BASE-01`(Happy Path) + Spec `EC-*` 전수를 필수로 실행하고, Spec 비유래 범용 시나리오 `BASE-02~05`는 `SMOKE_OMITTED`로 기록한다(판정 영향 없음).
- 실행 가능 케이스 0건 또는 Spec에 EC 표가 없으면 e2e-test가 스스로 full로 실행하고 `실행 수준: full(smoke 미적용: {사유})`를 보고 → 승격 ⑥(b).
- e2e-test-loop 종료 출력의 `- E2E 리포트:` 경로와 `실행 수준` 줄을 Phase Results에 기록한다.
