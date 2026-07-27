---
name: start-workflow-mm
description: "전체 개발 워크플로우를 자동화한다. Build 모드(기본): 요청 분석 → 구현 → 품질 루프 → Codex 리뷰 → Apidog 동기화 → PR. Analyze 모드(--analyze): 코드 분석 보고서. Verify 모드(--verify): 보안·성능·버그·안정성 검증. '워크플로우 시작', '기능 구현해줘(전 과정 자동)' 요청 시 사용."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명> | --analyze [경로] | --verify [경로]
user-invocable: true
---

# Start Workflow — Orchestrator

전체 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

**플레이스홀더 정의** (본문·references 공통, 값 변경은 여기 한 곳만 수정):

- `{STATE_FILE}` = `/tmp/workflow-state.md`
- `{IMPL_NOTES}` = `/tmp/implementation-notes.md`
- `{WORKLOG_DIR}` = `/workspace/work-log/claude`
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. PR 생략. |
| `--analyze` | `-a` | **Analyze 모드**. 전체 또는 특정 범위의 코드를 분석하여 보고서를 생성한다. |
| `--verify` | `-v` | **Verify 모드**. 보안·성능·잠재 버그·안정성을 검증하고 PASS/WARN/FAIL 판정한다. |

### 모드 판별

| 조건 | 모드 | 실행 경로 |
|------|------|----------|
| `--analyze` 또는 `-a` 포함 | **Analyze** | Phase A1 → A4 |
| `--verify` 또는 `-v` 포함 | **Verify** | Phase V1 → V5 |
| 위 플래그 없음 | **Build** (기본) | Phase 1 → 14 |

- `--analyze`와 `--verify`는 상호 배타적이다. 동시 지정 시 유저에게 하나를 선택하도록 안내한다.
- `--hard`는 Build 모드에서만 유효. `$ARGUMENTS`에 있으면 `$HARD_MODE = true`.
- **범위 지정**: 플래그 뒤 경로가 있으면 분석/검증 범위로 사용 (예: `--analyze internal/book`).

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 6 브랜치 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 12 PR | workflow-pr (PR 생성) | 현재 브랜치에서 바로 push, PR 생략 |

> **Analyze/Verify 모드 진입 시 MUST**: 같은 폴더의 `references/analyze-verify-modes.md`를 Read하고 해당 모드 절차를 따른다. Pre-flight(모든 모드 공통 — be-harness 폴백 규칙 포함)까지는 전 모드에 적용되며, 그 이후 `Build Mode` 섹션이 Build 모드 정의다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## 상태 추적

워크플로우 시작 시 `{STATE_FILE}`을 새로 만들고, Phase 진입/완료 때마다 갱신한다 (템플릿: `references/templates.md`).

- 에이전트 생성 전: 해당 Phase를 `IN_PROGRESS`로 갱신
- 완료 후: `DONE` / `SKIPPED:{사유}` / `BLOCKED:{사유}` 와 결과 기록
- 모든 에이전트 프롬프트에 상태 파일 경로, 현재 Phase, 남은 Phase, 배정 model/effort 포함

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
[유저 대화] Phase 1~5 : Spec, 난이도, 전략, E2E 플로우, Plan+리뷰
[상태 저장] Phase 6   : 브랜치 + 상태 파일 + 라이브 노트 생성
[자율 실행] Phase 7~13: 서브 에이전트 순차/병렬 위임 — 묻지 않고 자동 실행
[유저 대화] Phase 14  : 최종 보고 + 보완점 적용
```

### Spec 외 변경 금지 원칙

자율 실행 중 Spec에 명시되지 않은 동작 변경이 필요하다고 판단되면:
1. **코드를 수정하지 않고** 해당 사항을 기록한다.
2. Phase 14 보고서에 `[Assumption]` 태그로 표기하여 유저에게 가시화한다.
3. 유저 승인 후에만 해당 변경을 적용한다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- Phase 7 완료 → 즉시 Phase 8 (같은 턴). Phase 9 내 각 단계도 완료 즉시 다음 단계. Phase 10~13 동일.
- **유저 응답 대기, 진행 여부 질문, 중간 보고 후 멈춤은 금지.**
- 유일한 정지 지점은 **Phase 14 (최종 보고)** 뿐이다.

### Implementation Notes (라이브 판단 기록)

자율 실행 중 발생하는 **설계 결정·편차·트레이드오프·미결 질문**을 코드와 분리하여 `{IMPL_NOTES}`에 실시간으로 누적한다.
유저는 자율 실행 중에도 파일을 직접 열어 비동기로 피드백할 수 있고, Phase 14에서 HTML로 일괄 렌더링된다.

핵심 규칙 (파일 초기화 템플릿·4-섹션 구조: `references/templates.md`):

- 자율 실행 에이전트(Phase 7·8·9.5·9.6·11·12·13)는 4종 사건 발생 시 **코드 수정 전에** 해당 섹션에 한 줄 append.
- 읽기 전용 스캔 에이전트(9.1~9.4)는 직접 쓰지 않는다 — 이슈 보고서에 포함하면 통합 수정(9.5)이 대신 기록.
- `[Assumption]` 보고와 동일한 항목은 `## 편차` 섹션에 동시 기록 (보고서와 라이브 노트 동기화).
- **append-only** — 기존 줄 수정·삭제 금지. 마크다운만 작성 (HTML/JSON 금지 — Phase 14 렌더링이 깨진다).

## Pre-flight: 프로젝트 환경 점검 (모든 모드 공통)

아래 항목을 Bash/Glob으로 빠르게 확인한다. **누락 항목이 있으면 어떤 Phase가 SKIP될 것인지 미리 확정**한다.

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `secret/.env` | 파일 존재 확인 | Phase 9.6 (e2e-test-loop) SKIP 예정 — 서버 부팅/JWT 발급 불가 |
| Apidog MCP 연결 | `mcp__apidog__read_project_oas_*` 호출 가능 여부 | Phase 11 (Apidog 동기화) SKIP 예정 |
| PostgreSQL MCP 연결 | PostgreSQL MCP로 `SELECT 1` 실행 | Phase 9.6 부분 SKIP 예정 — DB 시드/정리 경로 제한 |
| be-harness 에이전트 | 세션 available agent types 목록에 `be-harness:*` 존재 확인 | 미설치 시 SKIP이 아닌 **폴백 모드**로 진행 (아래 "be-harness 폴백" 참조) |

> **MCP 판정**: 실제 MCP tool 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다 (상세: `/minmos-harness:minmo-doctor-mm`).

처리 규칙:
- 모두 OK → 점검 결과 한 줄 요약 후 진행.
- 누락 있음 → 사전 경고 후 선택지:
  > "⚠️ 환경 누락 감지: `{누락 항목}` 없음. 이번 워크플로우에서 **{영향받는 Phase 목록}**는 SKIP됩니다.
  > 1. 이대로 진행 — 해당 Phase는 `SKIPPED:{사유}`로 기록하고 넘어감
  > 2. 중단 — `/minmos-harness:minmo-doctor-mm`으로 진단 후 재시작 권장"

### be-harness 폴백 (미설치 시)

**일반 규칙**: 본 스킬(references 포함)의 모든 `be-harness:*` subagent_type 호출 지점은, be-harness 미설치 시 `general-purpose` + **동일 프롬프트**로 대체한다.

- **감지 한정**: ① Pre-flight에서 available agent types에 `be-harness:*` 부재 ② 호출 시 "unknown agent type" 즉시 실패 — 이 두 경우만 폴백한다. 에이전트가 작업 도중 실패한 경우(부분 커밋 등)는 폴백 대상이 아니라 기존 에러 처리 경로다 (중복 구현·중복 커밋 방지).
- **예외 1 — Phase 7 (workflow-implementer)**: 커밋/빌드가 에이전트 정의에 내장돼 있으므로, 폴백 시 구현 에이전트 완료 후 **오케스트레이터가 직접 빌드 확인·커밋**한다 (parallel-slices 모드의 오케스트레이터 일괄 커밋 방식 준용).
- **예외 2 — Phase 12 (workflow-pr)**: 자율 실행 구간(유저 응답 대기 금지)이므로 인터랙티브 스킬 호출 없이 **오케스트레이터가 무질문으로 직접 PR을 생성**한다. Phase 12 프롬프트의 본문 요건을 유지한다: {STATE_FILE} 기반 PR 본문 + {IMPL_NOTES} 미결 질문의 "리뷰어 확인 필요" 블록. VERSION 범프는 base 브랜치(= PR 대상 브랜치 — 현재 브랜치의 분기 원점) 대조 방식으로 직접 수행한다 — `git fetch origin {base}` 후 `origin/{base}`의 VERSION과 로컬 중 큰 쪽 기준 patch +1 (조회 실패 시 로컬 기준 +1). `gh pr create --draft ...`를 직접 실행한다.
- **고지 문구**: "be-harness 미설치 — 동일 프롬프트의 general-purpose 폴백으로 진행합니다 (권장: be-harness 설치)."

---

# Build Mode (Phase 1 ~ 14)

## Phase 1: 작업 범위 수집 (Plan 모드 진입)

> **Plan 모드 활성화**: Phase 1 시작 시 `EnterPlanMode`를 활성화한다.
> Spec과 Plan은 같은 Plan 모드 컨텍스트에서 통합 산출물로 발전하며, `ExitPlanMode`는 Phase 5.4에서 단 한 번만 호출한다.
> Spec/Plan 검토는 Phase 5.3 검증 루프에서 **Spec+Plan 통합 산출물**에 대해 단일 Codex 루프로 수행한다 (별도 Codex Spec 리뷰 없음).

**분기 — 이미 상세 Spec이 제공된 경우**: `$ARGUMENTS` 또는 대화 컨텍스트가 아래를 **모두** 충족하면 `/request` 호출을 생략하고, 제공된 내용을 Technical Spec으로 직접 정리해 유저 확인을 받는다:
- 작업 유형이 명확 (생성/수정/검토/디버깅)
- 대상 API/기능이 특정됨
- 핵심 요구사항이 구체적으로 기술됨

**기본**: `/minmos-harness:request-mm`을 호출하여 Technical Spec을 생성한다 (`$ARGUMENTS` 전달). 완료 후 Spec 전문과 엣지 케이스 목록을 보관하고, 작업 유형을 확인한다.

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

> 난이도와 무관하게 Phase 5에서 Codex Plan 리뷰를 항상 수행한다.

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
| `sequential` | 위 조건 미충족 (기본값) | Phase 7 순차 실행 |
| `parallel-slices` | 5가지 조건 모두 충족, 슬라이스 2~3개 | Phase 7에서 슬라이스별 병렬 구현 |
| `fullstack` | FE+BE 동시 변경 | `/minmos-harness:start-workflow-fs`로 리다이렉트 후 종료 |

> **대부분의 작업은 `sequential`이다.** 판단이 애매하면 `sequential` — 병렬화의 이점보다 잘못된 분리의 비용이 훨씬 크다.

출력: `실행 전략: [sequential/parallel-slices/fullstack] — [근거]`

## Phase 4: E2E 메인 플로우 수집

Phase 9.6 E2E 테스트가 **검증해야 할 핵심 시나리오**를 사용자에게 직접 묻는다. git diff 기반 자동 도출만으로는 의도한 주 사용 흐름이 누락될 수 있다.

**모든 Build 모드 작업에서 항상 질문한다** (작업 유형과 무관). 아직 Plan 모드 대화 중이므로 평문으로 묻는다:

> "E2E 테스트 메인 플로우를 알려주세요. 이 작업의 핵심 사용자 시나리오 또는 주요 API 호출 순서를 서술해주세요.
> 예: `진단지 생성 → 목록 조회 → 단건 수정 → 삭제`
> 자동 도출(git diff 기반)에 맡기려면 `자동`이라고 답해주세요."

- 시나리오를 서술하면 그 텍스트를 **그대로** 보관한다 (재해석·요약 금지).
- `자동`이라 답하거나 응답하지 않으면 `자동 도출 (git diff 기반)`으로 보관한다.
- 보관 값은 Phase 6에서 상태 파일 `## E2E 메인 플로우` 섹션에 **한 번만** 저장한다 (단일 출처). 이후 Phase 9.6은 상태 파일에서 읽는다.

## Phase 5: Plan 작성 + 리뷰

### Phase 5.1: Plan 작성

Spec 아래에 구현 계획을 추가하여 **Spec+Plan 단일 산출물**로 발전시킨다. Plan에 포함할 내용:

- 구현 순서 (파일 단위), 각 파일 변경 내용 요약
- **최종 코드 구조**: 중복 로직이 예상되면 최종 구조(테이블 드리븐, 공통 함수 추출 등)를 Plan 단계에서 확정 — 구현 후 리팩토링 커밋 방지
- 의존 관계, 예상 리스크

**parallel-slices 추가 요구사항**: Plan에 `## Slices` 섹션을 명시한다 (Slice별 제목/파일 범위/설명, 최대 3개).
슬라이스 간 파일 범위가 겹치면 `sequential`로 전략을 변경한다.

### Phase 5.2: 다관점 Plan 보강 (Claude, 1회)

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

### Phase 5.3: Plan Verification Loop (Codex 검증, 최대 5회)

```
for iteration in 1..5:
  ① Codex Plan 리뷰 (Architect 관점) — stateless 보완을 위해 매회 전달:
     Spec 전문 / Plan vN 전문 / 실행 전략 / 난이도 근거
     / (N≥2) 이전 iteration Diff 요약 + 기각 피드백·사유
     리뷰 관점: Spec-Plan 추적성, 레이어 책임 분리, 파일 소유권 충돌,
               테스트/검증 누락, 더 단순한 구현 경로
  ② 판정: APPROVE → 탈출 / CONCERN → 타당한 항목 반영(또는 기각 사유 기록) / REJECT → 수정
  ③ Iteration Diff Log를 상태 파일 `Plan Verification Log`에 append
     (Verdict / 반영 / 기각+사유 / Plan 변경 요약)
```

**Codex 호출 실패 처리** (매 iteration의 Codex 호출에 적용):

| 감지 패턴 | 분류 | 행동 |
|----------|------|------|
| CLI/MCP 부재 (command not found, 도구 미존재) | 환경 부재 | 종료조건 표의 `CODEX-UNAVAILABLE` — 사유 기록 후 진행 |
| quota/rate-limit (429, "usage limit", "rate limit", "quota", "try again at") | quota 차단 | **Claude 다관점 패널로 리뷰어 대체** + 상태 파일에 `SKIPPED:CODEX_QUOTA_BLOCKED` 기록 (Phase가 아닌 Codex 호출 항목에 대한 기록 — 검증 루프 자체는 계속 실행된다) |
| 기타 일시 오류 (타임아웃, 5xx) | 모호 | 1회 재시도 → 재실패 시 quota 차단과 동일 취급 |

**Claude 다관점 패널 (대체 리뷰어)**: Logic / Architecture / Edge Cases 3관점 `general-purpose` 에이전트 병렬 실행.

| 패널 판정 | 처리 |
|----------|------|
| 3인 전원 APPROVE | Codex APPROVE와 동일 — 수렴 |
| REJECT 1개 이상 | 지적 반영 후 다음 iteration |
| CONCERN | 기존 Phase 5.3의 CONCERN 처리 규칙 준용 |

패널 대체 시에도 **루프 카운터는 승계**한다 (리셋 없음, 최대 반복 상한 동일).

**고지 문구** (패널 대체 시): "Codex quota 차단 감지 — Claude 다관점 패널로 대체해 계속 진행합니다 (`SKIPPED:CODEX_QUOTA_BLOCKED` 기록)."

| 종료 조건 | 결과 |
|----------|------|
| Codex `APPROVE` | **PROCEED** → Phase 5.4 |
| 사용자가 명시적으로 루프 종료 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex CLI/MCP 부재 | **CODEX-UNAVAILABLE** → 사유 기록 후 진행 |
| 5회 도달, 미APPROVE | **BLOCKED:MAX_ITERATIONS** → 아래 선택지 제시 |

5회 도달 시 선택지:
> "Plan 검증 루프가 5회에 도달했습니다. 미해결 이슈: {요약}
> 1. 현재 Plan으로 진행 — 잔존 이슈를 상태 파일에 기록하고 Phase 5.4로
> 2. 루프 계속 — 5회 추가 반복
> 3. 중단 — 워크플로우 종료"

안전장치:
- **동일 이슈 3회 반복 지적** → 사용자에게 보고하고 판단 위임 (응답 후 재개/종료)
- **변경 0건 iteration 발생** → 즉시 중단하고 사용자에게 보고 (무한 핑퐁 방지)

### Phase 5.4: Plan 확정

루프 종료 후 `ExitPlanMode` 실행. 상태 파일 하단에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 6: 브랜치 + 상태 파일 + 라이브 노트 + 자율 실행 시작

**브랜치 생성**:
- `$HARD_MODE = false`: 구현 전 반드시 feature 브랜치 생성 (`git checkout -b feat/{작업 요약 kebab-case}`). 이미 `feat/**`·`hotfix/**`면 건너뜀. main/master에 직접 커밋 금지.
- `$HARD_MODE = true`: 브랜치 생성 건너뜀. 현재 브랜치 그대로 사용.

> Phase 6 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고
> ① "상태 파일 템플릿"대로 `{STATE_FILE}` 생성 (Spec·엣지 케이스·E2E 메인 플로우·Plan·전략·Slices 복사)
> ② "Implementation Notes 라이브 파일 초기화" 템플릿대로 `{IMPL_NOTES}` 생성 (기존 파일 덮어쓰기).

출력:
- `sequential`: **"자율 실행을 시작합니다. Phase 7~13을 서브 에이전트로 순차 실행합니다."**
- `parallel-slices`: **"자율 실행을 시작합니다. [N]개 슬라이스를 병렬 구현합니다."**

## Phase 7 ~ 13: 자율 실행

> Phase 7 진입 시 MUST: 같은 폴더의 `references/agent-prompts.md`를 Read한다. Phase 7, 8, 11, 12, 13의 에이전트 프롬프트는 모두 이 문서의 해당 섹션을 사용한다.

각 Phase 시작 직전 `{STATE_FILE}`의 `Current Phase`, `Phase Assignments.Status`, `Remaining Phases`를 갱신하고, 완료 후 결과를 append한다 (Phase 14 보고서에 사용).

### Phase 7: 구현

- `sequential`: `be-harness:workflow-implementer` 1개 → 구현 + 커밋
- `parallel-slices`: `general-purpose` 2~3개 병렬 (커밋·빌드 금지, 슬라이스 prefix로 노트 기록) → 완료 후 오케스트레이터가 일괄 커밋

### Phase 8: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

```bash
go build ./cmd/main.go 2>&1
```

| 결과 | 행동 |
|------|------|
| 성공 | Phase 9로 진행 |
| 실패 | build-fix 에이전트로 수정 → 커밋 → 재시도 |
| **3회 시도 후에도 실패** | `BLOCKED:BUILD_FAIL` — 유저에게 에러 요약 보고 후 중단 |

### Phase 9: 품질 루프 (최대 3회)

> Phase 9 진입 시 MUST: 같은 폴더의 `references/quality-loop.md`를 Read하고 각 단계의 프롬프트·실행 상세를 따른다.

```
for iteration in 1..3:
  [Batch A — 병렬 스캔, 읽기 전용] 9.1 go build+test / 9.2 simplify / 9.3 convention / 9.4 scope
      → 이슈만 수집, 파일 수정 금지
  [Phase 9.5 — 통합 수정] 수집 이슈를 단일 에이전트가 일괄 수정
  [Batch B — 순차, 서버 점유] 9.6 e2e-test-loop-mm → 9.7 make test

[루프 종료 후 1회] 9.8 Spec 정합 Read-back — 판정만, 코드 수정 없음
```

| 종료 조건 | 결과 |
|----------|------|
| iteration 내 수정 0건 (`modified == false`) | 루프 탈출 → Phase 9.8 |
| `modified == true` | 커밋 후 다음 iteration |
| 3회 도달 | 미해결 사항 보고 후 강제 탈출 → Phase 9.8 |

커밋: `git add [수정 파일들] && git commit -m "Fix: 품질 루프 수정 (반복 N)"`

**Phase 9.8은 루프 밖에서 1회만 실행한다.** Spec을 모르는 격리된 에이전트가 구현·검증 산출물에서 보장 동작을 복원하고, 오케스트레이터가 그것을 Spec·기존 코드와 대조해 이탈을 판정한다. 코드는 수정하지 않으며 결과는 Phase 14에서 유저에게 보고한다. 판정이 `FAIL`이어도 자율 실행은 멈추지 않는다.

완료 후: "Phase 9 완료: [루프 횟수]회, 총 [수정 건수]건 수정 / Read-back [PASS/WARN/FAIL] (A·C·E [N]건)"

### Phase 10: Codex 품질 리뷰 (항상)

> 상세 절차·REJECT 상한(최대 3회)·선택지: `references/quality-loop.md`의 "Phase 10" 섹션.

APPROVE → Phase 11. Codex 호출 실패 시 처리(환경 부재/quota/일시 오류 분류)는 `references/quality-loop.md`의 Phase 10 섹션을 따른다.

### Phase 11: 문서 동기화 (조건부)

**작업 유형이 API 생성/수정/삭제인 경우만 실행.** 그 외는 `SKIPPED:TASK_TYPE`.

MCP tool 호출 전 **1회 호출로 read/write capability를 먼저 확인**하고, 지원하지 않는 기능은 시도하지 않고 수동 안내로 전환한다.
`minmos-harness:workflow-doc-sync` 에이전트 사용.

### Phase 12: PR / Push

- `$HARD_MODE = false`: `be-harness:workflow-pr` 에이전트로 PR 생성 (미결 질문은 PR 본문 "리뷰어 확인 필요" 블록으로). PR URL 보고 필수.
- `$HARD_MODE = true`: PR 생략, `git push origin $(git branch --show-current)` 후
  "Phase 12 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)" 출력.

### Phase 13: 성찰

`be-harness:workflow-reflection` 에이전트 실행.

## Phase 14: 최종 보고

> Phase 14 진입 시 MUST: 같은 폴더의 `references/templates.md`를 Read하고 "Implementation Notes HTML 렌더링"과 "Workflow Report 템플릿"을 따른다.

1. **HTML 렌더링**: `{IMPL_NOTES}` → `{WORKLOG_DIR}/{YYYYMMDD}-{task-name-kebab}-impl-notes.html` (템플릿 준수, 디렉토리 없으면 생성).
2. **보고서 작성**: Phase 7~13 결과를 종합해 Workflow Report 작성 (템플릿 준수 — 섹션 머리글 변경 금지). `## 미결 질문` 1건 이상이면 보고서 최상단에 "사용자 확인 필요" 블록 자동 삽입.
3. **Read-back Diff 처리** (Phase 9.8 판정이 `WARN`/`FAIL`일 때만): 보고서의 Read-back Diff 섹션 각 항목을 유저에게 제시하고 결정을 받는다.
   보완점 질문보다 **먼저** 처리한다 — 코드·Spec에 직접 영향을 주는 결정이기 때문이다.
   - 결정에 따른 코드/Spec 수정이 필요하면 그 자리에서 수행하고 커밋한다. 유저가 승인하기 전에는 수정하지 않는다 (Spec 외 변경 금지 원칙).
   - 유저가 "이번 범위 외"로 판단한 항목은 보고서에 `보류`로 남기고 넘어간다.
4. **보완점 적용** 질문:
   > "위 보완점을 해당 스킬에 반영할까요?
   > 1. 전체 — 모든 보완점 반영
   > 2. 선택 — 번호로 선택한 항목만 반영
   > 3. 건너뛰기 — 보고서만 출력하고 종료"
4. **정리**: 상태 파일의 모든 Phase를 `DONE`/`SKIPPED:{사유}`로 갱신, `Remaining Phases`를 `없음`으로.
   기본은 상태 파일과 라이브 노트를 **보관** (HTML 산출물은 `{WORKLOG_DIR}`에 영구 저장). 사용자가 정리를 요청한 경우에만:
   ```bash
   rm -f {STATE_FILE} {IMPL_NOTES} /tmp/e2e-run-report.md
   ```
   HTML 산출물(`*-impl-notes.html`, `*-e2e-report.html`)은 자동 삭제하지 않는다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 (예: `SKIPPED:TASK_TYPE`, `SKIPPED:CODEX_UNAVAILABLE`) |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 (예: `BLOCKED:BUILD_FAIL`, `BLOCKED:MAX_ITERATIONS`, `BLOCKED:CODEX_REVIEW`) |
| `PASS` / `WARN` / `FAIL` | Verify 모드 판정 |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/analyze-verify-modes.md` | `--analyze` / `--verify` 모드 진입 시 |
| `references/templates.md` | Phase 6 (상태 파일·라이브 노트), Phase 14 (HTML 렌더링·보고서) |
| `references/agent-prompts.md` | Phase 7 진입 시 (Phase 7/8/11/12/13 프롬프트) |
| `references/quality-loop.md` | Phase 9 진입 시 (Phase 9/10 상세) |

## 흐름 요약 (Build)

```
[유저 대화] — Phase 1~5 전체가 단일 EnterPlanMode 컨텍스트
Phase 1: EnterPlanMode → /request-mm으로 Technical Spec (유저 확인)
Phase 2: 난이도 산정 (1-10)
Phase 3: 실행 전략 판정 (sequential / parallel-slices / fullstack → start-workflow-fs로 전환)
Phase 4: E2E 메인 플로우 수집 (사용자 질문, 모든 Build 작업)
Phase 5: Plan 작성 → 다관점 1회 보강 → Codex 검증 루프 (최대 5회) → ExitPlanMode
Phase 6: feature 브랜치 + 상태 파일 + implementation-notes.md(4-섹션) → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 7: 구현 (sequential: workflow-implementer / parallel: general-purpose × N → 일괄 커밋)
Phase 8: go build 빌드 체크 (실패 시 수정 최대 3회)
Phase 9: 품질 루프 최대 3회 (병렬 스캔 9.1~9.4 → 통합 수정 9.5 → e2e 9.6 → make test 9.7)
         루프 종료 후 9.8 Spec 정합 Read-back 1회 (격리 복원 → Diff 판정, 수정 없음)
Phase 10: Codex 품질 리뷰 (APPROVE까지, REJECT 최대 3회)
Phase 11: workflow-doc-sync → Apidog 동기화 (API 변경 시만)
Phase 12: workflow-pr → PR 생성 (--hard: push만)
Phase 13: workflow-reflection → 성찰

[유저 대화]
Phase 14: impl-notes HTML 렌더링 → 최종 보고 (미결 질문 상단 표면화) → 보완점 적용 → 정리
```
