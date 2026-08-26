# 검증 티어 (Verification Tier)

> 이 문서는 `start-workflow` 스킬의 Phase 2(티어 판정), Phase 4·5·6·8(승격 판정)에서 로드된다. 단독 실행 금지.
> 플레이스홀더(`{STATE_FILE}`·`{PLAN_MAX}`·`{QL_MAX}` 등)는 SKILL.md 본문 정의를 따른다.

Spec 직후 **코드 복잡도(A)** 와 **영향 범위·회귀 리스크(B)** 를 점수화해, 저위험·저복잡도 작업에서만 추가 리뷰 레이어·루프 상한·E2E 범위를 줄인다(`light`).
그 외는 전부 `standard`(= 기존 절차 무변경). Spec이 정의한 검증(AC/EC 전수, TDD Red, scope-reviewer, 빌드, 통합 테스트)은 어떤 티어에서도 축소하지 않는다.

## 1. 점수 산정 (Phase 2)

**산정 규칙**
- 각 축 점수 = 요소별 밴드 점수의 **최댓값**(평균 금지). 종합 난이도 = `max(A, B)` (Model/Effort 등급표 입력).
- 판정 근거가 없는 요소는 `UNKNOWN` = **높음 밴드**로 취급한다(fail-safe).
- 근거 자료: Spec `참조 구현` 열의 경로로 아래를 실행해 출력(존재·최근 변경 커밋 수·동반 테스트·과거 워크플로우 이력)을 B축 `변경 영역 기존 테스트`·`기존 동작 변경 범위`의 근거로 쓴다. 경로가 없거나 스크립트가 exit ≠ 0이면 해당 행은 `UNKNOWN`.
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/risk_facts.py --paths {참조 구현 경로들} --report-dir {REPORT_DIR}
  ```

### A. 코드 복잡도

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 레이어 | 단일 | 2개 | 3개 전체 |
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

## 2. 게이트 (Phase 2 판정, Phase 4.4 재점검)

`light` ⇔ 아래 **전부** 충족. 하나라도 어긋나면 `standard`.

| 조건 | 기준 |
|------|------|
| 점수 | A ≤ 3 **그리고** B ≤ 3 (= 모든 요소가 `낮음` 밴드, `UNKNOWN` 0건) |
| 금지 조건 | 0건 (아래 표) |
| TDD | `$TDD = true` (`--no-tdd`는 회귀 안전망이 없어 standard 강제) |
| 실행 전략 | `parallel-slices`가 아님 (파일 ≥ 6 → A ≥ 4) |
| 플래그 | `--tier standard` 미지정 |
| 풀스택 | `--fs` 전환 시 항상 standard (계약 변경 = B축 높음) |

**금지 조건** — 어떤 방법으로도 우회 불가. Phase 4.4에서 Plan의 파일 목록으로 재점검하고, 발견 즉시 standard.

| 금지 조건 |
|----------|
| 기존 테이블 스키마 변경 · 데이터 마이그레이션 |
| 인증 · 인가 · 암호화 · 개인정보 처리 |
| 결제 · 정산 |
| 공유 미들웨어 · 인터셉터 · DI wiring |
| Breaking change (API 계약) |
| 외부 서비스 연동 변경 |

- `light` 강제 플래그는 없다. 점수는 Plan 모드 대화에서 유저가 근거를 제시하면 재산정할 수 있으나 게이트 조건 자체는 불변.
- 출력: `검증 티어: light|standard — A [a]/B [b], 금지 조건 [해당 없음|{항목}], [TDD off|parallel-slices|--tier standard 로 standard]` — Plan과 함께 `ExitPlanMode`에서 승인.
- 상태 파일 `## Verification Tier`(템플릿: `references/templates.md`)에 계산 티어 / 최종 티어 / 근거 / 축소 항목 / 승격 이력을 기록하고, `## Flags`의 `TIER`에 최종 티어를 적는다.

## 3. light 축소 항목 (그 외는 standard와 동일)

| 단계 | standard | light |
|------|----------|-------|
| Phase 4.2 다관점 Plan 보강 | 3에이전트 × 2배치 | **1에이전트 3관점** (엣지 케이스 · 기존 코드 영향 · 더 단순한 경로) |
| Phase 4.3 Plan 검증 루프 `{PLAN_MAX}` | 5 | **2** (2회 소진 시 승격 ①) |
| Phase 8 품질 루프 `{QL_MAX}` | 3 | **2** |
| Phase 8.2 simplify | 통합 스캐너 (simplify + convention) | `SKIPPED:TIER_LIGHT` — 통합 스캐너를 **convention 전용 프롬프트**로 호출 (`quality-loop.md`) |
| Phase 8.6 E2E | `e2e-test-loop` (full, 최대 5회) | `e2e-test-loop --smoke` (BASE-01 + EC-* 전수, 최대 3회) |
| Phase 8.8 Spec 정합 Read-back | 1회 | `SKIPPED:TIER_LIGHT` |
| 유지 (축소 금지) | — | 6.1 TDD Red · 7 빌드 · 8.1 · 8.3 convention · 8.4 scope · 8.5 · 8.7 · 9 · 10 |

## 4. 승격 (light → standard, 단방향)

자율 구간의 승격은 **질문 없이 기록하고 진행**한다. 티어 전환은 항상 해당 루프의 **종료 조건·상한 평가보다 먼저** 적용한다.

| # | 시점 | 트리거 | 효과 |
|---|------|--------|------|
| ① | Phase 4.3 | 리뷰어 CONCERN/REJECT로 light 상한 2회 소진 (상한 평가 전에 판정) | `{PLAN_MAX}` = 5 복원, iteration·동일 이슈 카운터 승계(3회차부터). 4.2는 재실행하지 않음 |
| ② | Phase 6.2 완료 직후, Phase 7 진입 전 | 변경 소스 파일 > 3 **또는** 구현 결과에서 금지 조건이 새로 드러남 (집계 규칙: 아래) | 이후 Phase 7·8 전부 standard |
| ③ | Phase 8.1 회귀 대조 | `regression` ≥ 1, 또는 회귀 판정 불가(러너 완주 N / `UNPARSED` 잔존을 오케스트레이터도 분류 못 함) | `{QL_MAX}` = 3 복원. 승격 이후 **시작되는** 단계부터 standard — 같은 iteration의 8.6부터 full E2E. 회귀·판정 불가 = 테스트 판정 FAIL이므로 다음 iteration이 보장되며, 복원된 상한에서도 미PASS면 기존대로 `BLOCKED:TEST_NOT_GREEN`. 루프 후 8.8 Read-back 실행 |
| ④ | Phase 5 baseline 수집 | 수집 실패 (`수집 실패 — regression 판정 불가` 선택) | 회귀 안전망 부재 → standard |
| ⑤ | Phase 4.3 | `CODEX-UNAVAILABLE` = Claude 패널 실패 (유효 verdict 3개 미달 — `references/codex-mode.md` §6) | standard 기록 후 기존 규칙대로 진행. Codex 호출 실패의 패널 폴백(§7)은 리뷰 수행으로 간주(승격 아님) |
| ⑥ | Phase 8.6 E2E | (a) `BLOCKED:MAX_ITERATIONS` · `BLOCKED:NO_PROGRESS` 종료 (b) e2e-test가 `실행 수준: full(smoke 미적용: …)` 보고 (실행 가능 smoke 케이스 0건 · EC 표 없음 = 검증 근거 부족) | standard (`{QL_MAX}` = 3) + **현재 iteration 종료 후 standard iteration을 최소 1회 추가** (탈출 조건 평가는 그 뒤부터 — simplify·full E2E가 반드시 1회 실행됨) |
| ⑦ | 각 품질 루프 iteration 종료 시 + Phase 10 진입 직전 (특화 하네스 Codex 리뷰 수정 반영 후 포함) — **최종 티어가 light인 동안에만 평가** (승격 = latch, 1회) | ②와 동일 집계 재평가 (변경 소스 파일 > 3 또는 금지 조건 발견) | standard + standard iteration 최소 1회 추가. Phase 10 직전이면 Phase 8을 **standard 루프로 재진입** (새 루프, 상한 `{QL_MAX}` = 3, 종료 조건 동일, 미PASS → `BLOCKED:TEST_NOT_GREEN`), 이력 `⑦: Phase 8 재진입`. 재진입 루프 종료 시 `검증 트리: {git rev-parse HEAD} (dirty: Y/N)` 기록. 특화 하네스 Codex 리뷰가 있는 경우: 재진입 루프에서 파일이 1회라도 수정됐으면 그 트리에 대해 리뷰를 1회 재실행(잔여 횟수 내), 수정 없음 → 기존 APPROVE 유효. 이후 Phase 10 — latch라 ⑦ 재평가 없음 |

**②·⑦ 집계 규칙**
- 기준 = `## Flags`의 `START_SHA` (= `## Verification Tier`의 `시작 커밋`, baseline SHA와 동일).
  ```bash
  git cat-file -e {START_SHA} && { git diff --name-only {START_SHA}; git ls-files --others --exclude-standard; } | sort -u
  ```
  커밋·스테이징·작업 트리·untracked 전부 포함, 삭제·이름 변경도 1건.
- 제외는 **명시 패턴만**: 테스트 `_test.go` · `*.test.*` · `*.spec.*` · `__tests__/` · `testdata/` · `e2e/`, 생성물 `vendor/` · `node_modules/` · `*.pb.go` · `*.gen.*` · `mocks/` · `__pycache__/` · `*.pyc`, 문서 `*.md` · `docs/`. 패턴에 없는 파일은 전부 소스로 집계한다(분류 불가를 제외로 해석하지 않음).
- 집계한 파일 목록을 승격 이력 행에 기록한다.
- `START_SHA`가 없거나 `git cat-file -e`로 도달 불가 → `## Test Baseline`의 `커밋:`으로 대체. 그것도 없으면 판정 불가로 **standard 강제** + 이력 `②: 시작 SHA 판정 불가` (사후 HEAD로 대체 금지).

**기록**
- `Phase Results` 진단 셀: `tier_escalated({①..⑦})`. `## Verification Tier` 승격 이력 행: 시점 / 트리거 / 근거 목록 / 조치. `## Flags`의 `TIER`를 `standard`로 갱신.
- Workflow Report §1: `검증 티어: light → standard (②, 4.2 light 실행)`. 승격 시 재실행하지 않는 유일한 항목은 4.2 — 이력에 `미재실행: 4.2`로 남긴다.
- 승격 후 보장: ②·④·⑤는 Phase 8 진입 전이라 자동, ③은 FAIL로 다음 iteration 보장(같은 iteration 8.6부터 full), ⑥·⑦은 standard iteration 1회 강제 추가. 어떤 경로든 승격 후 simplify·full E2E·Read-back이 최소 1회 실행된다.

## 5. smoke E2E (light)

- Phase 8.6은 `e2e-test-loop --smoke`로 호출한다. e2e-test는 `BASE-01`(Happy Path) + Spec `EC-*` 전수를 필수로 실행하고, Spec 비유래 범용 시나리오 `BASE-02~05`는 `SMOKE_OMITTED`로 기록한다(판정 영향 없음).
- 실행 가능 케이스 0건 또는 Spec에 EC 표가 없으면 e2e-test가 스스로 full로 실행하고 `실행 수준: full(smoke 미적용: {사유})`를 보고 → 승격 ⑥(b).
- e2e-test-loop 종료 출력의 `- E2E 리포트:` 경로와 `실행 수준` 줄을 Phase Results에 기록한다.
