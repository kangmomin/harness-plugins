---
name: start-workflow
description: "프론트엔드와 백엔드를 분리된 에이전트로 병렬 오케스트레이션한다. 기능 정의 → 통신 계약 → 교차 리뷰 → 병렬 구현 → 통합 검증 → 단일 PR의 애자일 풀스택 워크플로우. 화면과 API가 함께 바뀌는 작업, '풀스택으로 진행해줘' 요청 시 사용."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명 또는 빈 값>
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fs-harness/common.md`와 `.claude/fs-harness/skills/start-workflow.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> 이 스킬이 be/fe 에이전트를 호출할 때 각 에이전트는 **자기 플러그인의 오버라이드**를 별도 로드한다 (`.claude/be-harness/...`, `.claude/fe-harness/...`).

# Start Workflow Full Stack — Agile Orchestrator

프론트엔드와 백엔드를 하나의 큰 구현 덩어리로 취급하지 않는다.
먼저 **기능 단위와 통신 계약**을 고정하고, 그 다음 **프론트/백엔드 전용 에이전트**가 병렬로 구현한 뒤, 마지막에 통합 검증으로 닫는다.

**플레이스홀더 정의** (본문·references 공통, 값 변경은 여기 한 곳만 수정):

- `{STATE_FILE}` = `/tmp/fullstack-workflow-state.md`
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)

## 언제 쓰는가 / 쓰지 않는가

- **사용**: 화면과 API가 함께 바뀌는 기능, 요청/응답 구조·에러 모델·인증 방식이 같이 정리되어야 하는 작업.
- **미사용**: 백엔드만 바뀌면 `/be-harness:start-workflow`, 프론트엔드만 바뀌면 `/fe-harness:start-workflow`.

## 전제 조건

- **be-harness와 fe-harness 플러그인이 모두 설치**되어 있어야 한다 (request, workflow-implementer, scope-reviewer, component-reviewer, a11y-reviewer, workflow-reflection 사용).
- 한쪽 하네스가 없으면 이 스킬로 억지로 진행하지 말고, 단일 도메인 워크플로우로 안내 후 종료한다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | feature 브랜치 생성과 PR 생성을 건너뛰고 현재 브랜치에서 마무리한다. |

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## 호출 방식 규칙

| 대상 | 방식 |
|------|------|
| be/fe의 `request` (Phase 1) | **Skill tool**로 `/be-harness:request`, `/fe-harness:request` 순차 호출 (대화형이므로 병렬 불가) |
| be/fe의 `workflow-implementer` (Phase 6) | **Agent tool**로 `subagent_type: be-harness:workflow-implementer` / `fe-harness:workflow-implementer` 병렬 호출 |
| be/fe의 품질 스킬 (Phase 7) | **Agent tool**(general-purpose)을 만들고 그 안에서 Skill tool로 해당 스킬 호출 |
| 리뷰어 (Phase 3, 8) | **Agent tool**로 읽기 전용 호출 |

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
5. **No Silent Contract Drift**: 계약이 바뀌면 구현을 계속하지 말고 Phase 2(계약)로 되돌아간다.

## Phase 매핑

| Phase | 담당 | 목적 |
|-------|------|------|
| 1 | 오케스트레이터 + `/be-harness:request` + `/fe-harness:request` | 기능 정의 및 도메인 분리 |
| 2 | 오케스트레이터 | 통신 계약 초안 작성 |
| 3 | 읽기 전용 리뷰 에이전트 2개 이상 | 계약/분업 리뷰 |
| 4 | 오케스트레이터 | 프론트/백엔드 Plan 분리 + 검증 루프 |
| 5 | 오케스트레이터 | 브랜치 + 상태 파일 |
| 6 | BE/FE workflow-implementer | 병렬 구현 |
| 7 | 각 도메인 품질 루프 | 영역별 안정화 |
| 8 | 읽기 전용 리뷰 에이전트 | 통합 검증 |
| 9 | 오케스트레이터 + PR 스킬 | 최종 커밋/PR |
| 10 | workflow-reflection | 회고 및 정리 |

## 상태 추적

워크플로우 시작 시 `{STATE_FILE}`을 새로 만들고, Phase 진입/완료 때마다 갱신한다 (템플릿: `references/contract-templates.md`).
에이전트 생성 전 `IN_PROGRESS`, 완료 후 `DONE` / `SKIPPED:{사유}` / `BLOCKED:{사유}`와 결과를 기록한다.
모든 에이전트 프롬프트에 상태 파일 경로, 현재 Phase, 남은 Phase, 배정 model/effort를 포함한다.

### Model / Effort 선택 규칙

| 등급 | 기준 | Claude 계열 | Codex 계열 | effort |
|------|------|-------------|------------|--------|
| Simple | 단일 도메인에 가까운 보조 작업, 문서/단순 리뷰 | sonnet | gpt-5.3-codex-spark | low |
| Standard | 일반 FE+BE 계약/구현/검증 | sonnet | gpt-5.3-codex | medium |
| Complex | 다중 API, shared artifact, 상태/DB/권한 영향 | opus | gpt-5.4 | high |
| Critical | 대규모 계약 변경, 보안/데이터 마이그레이션, 릴리즈 위험 | opus | gpt-5.5 | xhigh |

FE/BE 구현 에이전트는 각 도메인의 작업량으로 등급을 따로 산정한다.
통합 계약 리뷰와 contract drift 판정은 기본 `Complex` 이상.

## 자율 실행 규칙

- Phase 1~4: 유저와 기능/계약/Plan을 합의한다.
- **Phase 5 이후 ~ Phase 10 완료까지** 자동 실행한다.
- 멈춰야 하는 지점은 계약 불일치, 권한 부족, 테스트 불가, 또는 유저 승인 없이는 바꿀 수 없는 요구사항뿐이다.

### Spec 외 변경 금지 원칙

Spec 또는 계약에 없는 변경이 필요하면: ① 코드를 먼저 바꾸지 않는다 ② `{STATE_FILE}`의 `Assumptions` 섹션에 `[Assumption]`으로 기록한다 ③ 계약 리뷰를 다시 거친 뒤에만 반영한다.

---

## Phase 1: 기능 정의 + Feature Matrix (Plan 모드 진입)

> **Plan 모드 활성화**: Phase 1 시작 시 `EnterPlanMode`를 활성화한다.
> Spec(Feature Matrix), 통신 계약, BE/FE/공용 Plan은 모두 같은 Plan 모드 컨텍스트에서 발전하는 단일 산출물이며, `ExitPlanMode`는 Phase 4.4 검증 루프 종료 시 단 한 번만 호출한다.

상세 명세가 이미 충분하면 그 내용을 정리해서 시작한다.
부족하면 `/be-harness:request`로 백엔드 관점 질문을, `/fe-harness:request`로 프론트엔드 관점 질문을 각각 수행한다.

> Phase 1 진입 시 MUST: `references/contract-templates.md`를 Read하고 "Feature Matrix 템플릿"대로 표를 작성한다.

이 결과가 한쪽 도메인만 필요하면 풀스택 워크플로우를 중단하고 단일 도메인 스킬로 전환한다.

## Phase 2: 통신 계약 정의

구현 전에 반드시 **Integration Contract**를 작성한다 (`references/contract-templates.md`의 "Integration Contract 템플릿" 준수 — 인증/페이지네이션/포맷/캐시/호환성 필수 항목 포함).

## Phase 3: 계약 리뷰

계약 초안이 나오면 읽기 전용 리뷰를 병렬로 수행한다 (출력 형식·REJECT 기준: `references/contract-templates.md`).

- **Batch 1 (병렬)**: 백엔드 advisor (데이터 정합성·비즈니스 규칙·에러 모델) + 프론트엔드 advisor (화면 상태·사용자 흐름·소비 가능성)
- **Batch 2 (병렬)**: 프론트가 계약을 소비하는 데 빠진 필드가 없는지 + 백엔드가 프론트 요구를 과도하게 책임지지 않는지 교차 리뷰

REJECT가 있으면 계약을 수정하고 재리뷰한다.

## Phase 4: 분리 Plan 작성

Spec(Feature Matrix)과 통신 계약 아래에 **BE/FE/공용 Plan을 추가**하여 단일 통합 산출물로 발전시킨다.

### Phase 4.1: 백엔드 Plan
변경 파일 / 핸들러·서비스·리포지토리 범위 / 테스트 전략 / 계약 산출물 owner 여부

### Phase 4.2: 프론트엔드 Plan
변경 파일 / 페이지·컴포넌트·훅 범위 / 화면 상태 처리 전략 / 타입·클라이언트 연동 전략

### Phase 4.3: 공용 Plan
feature 브랜치 전략 / shared artifact owner / 통합 테스트 순서 / 롤백 조건 / `[Assumption]` 목록

Plan 규칙:
- 한 파일의 owner는 한쪽만 가진다. 생성 코드나 shared schema도 owner를 지정한다.
- 프론트는 계약 확정 전 mock shape를 임의로 만들지 않는다.
- 백엔드는 프론트 화면 로직을 추측해서 응답 필드를 늘리지 않는다.

### Phase 4.4: Plan Verification Loop (Codex 검증, 최대 5회)

통신 계약 + BE/FE/공용 Plan에 대해 Codex 검증 루프를 통과해야 확정된다.

```
for iteration in 1..5:
  ① Codex Plan 리뷰 (Architect 관점) — stateless 보완을 위해 매회 전달:
     Spec / 통신 계약 v최신 / BE·FE·공용 Plan v최신
     / (N≥2) 이전 iteration Diff 요약 + 기각 피드백·사유
     리뷰 관점: 계약-Plan 추적성, 파일 소유권 충돌, shared artifact owner 명확성,
               책임 전가 여부, 통합 테스트·롤백 조건 누락, 더 단순한 구현 경로
  ② 판정: APPROVE → 탈출 / CONCERN → 타당한 항목 반영(또는 기각 사유 기록) / REJECT → 수정
  ③ Iteration Diff Log를 상태 파일 `Plan Verification Log`에 append
     (Verdict / 반영 / 기각+사유 / 변경 요약)
```

| 종료 조건 | 결과 |
|----------|------|
| Codex `APPROVE` | **PROCEED** → ExitPlanMode로 Plan 확정 |
| 사용자가 명시적으로 루프 종료 지시 | **USER-INTERRUPTED** → 잔존 이슈 기록 후 진행 |
| Codex 사용 불가 환경 | **CODEX-UNAVAILABLE** → 사유 기록 후 진행 |
| 5회 도달, 미APPROVE | **BLOCKED:MAX_ITERATIONS** → 아래 선택지 제시 |

5회 도달 시 선택지:
> "Plan 검증 루프가 5회에 도달했습니다. 미해결 이슈: {요약}
> 1. 현재 Plan으로 진행 2. 루프 계속 (5회 추가) 3. 중단"

안전장치: 동일 이슈 3회 반복 지적 → 사용자 판단 위임 / 변경 0건 iteration → 즉시 중단·보고.

루프 종료 후 `ExitPlanMode`로 Plan을 확정하고, 상태 파일에 `Plan Verification Summary`(Total Iterations / Convergence / 잔존 이슈)를 기록한다.

## Phase 5: 브랜치 + 상태 파일

`--hard`가 아니면 feature 브랜치를 만든다: `git checkout -b feat/{작업-요약-kebab-case}`

> Phase 5 진입 시 MUST: `references/contract-templates.md`의 "상태 파일 템플릿"대로 `{STATE_FILE}`을 작성한다.

## Phase 6: 프론트/백엔드 병렬 구현

> Phase 6 진입 시 MUST: 같은 폴더의 `references/agent-prompts.md`를 Read하고 BE/FE 구현 에이전트를 **같은 메시지에서 병렬 호출**한다.

구현 중 계약 변경이 필요하면 즉시 Phase 2로 돌아간다 (No Silent Contract Drift).

## Phase 7: 도메인별 품질 루프 (최대 3회)

Phase 7 시작 전 `{STATE_FILE}`의 상태를 갱신한다. 각 도메인 루프의 서브 에이전트는 도메인별 실패 심각도에 맞는 model/effort를 명시한다.

- **백엔드 루프**: ① `/be-harness:simplify-loop` ② `/be-harness:convention-check` ③ `/be-harness:e2e-test-loop` ④ API 계약 변경 + `apiDocsPath` 존재 시 문서 동기화
- **프론트엔드 루프**: ① build + type-check ② `/fe-harness:simplify-loop` ③ `/fe-harness:convention-check` ④ `/fe-harness:test-loop` ⑤ `/fe-harness:lint-check`

| 규칙 | 내용 |
|------|------|
| 독립 반복 | 각 도메인은 자기 루프만 다시 돈다 |
| 계약 위협 | 한쪽 루프 결과가 계약을 흔들면 둘 다 멈추고 Phase 2로 복귀 |
| 상한 | 최대 3회. 도달 시 미해결 사항 보고 후 Phase 8로 강제 진행 |

## Phase 8: 통합 검증

### Phase 8.1: 계약 격리 Read-back

통합 검증에 들어가기 전에, **계약을 모르는 에이전트 2개**가 각각 백엔드·프론트엔드 구현만 읽고 "이 코드가 실제로 주고받는 계약"을 복원한다.
Phase 8.2는 frozen contract를 **보면서** 코드를 검증하므로 "대충 맞네"로 통과하기 쉽다. 계약을 가린 상태에서 복원한 뒤 대조해야 실제 이탈이 드러난다.

> **격리 규칙 (CRITICAL)**: 두 에이전트에게 `{STATE_FILE}` 경로와 frozen contract를 **전달하지 않고, 읽지 말라고 명시**한다. 다른 Phase와 달리 "상태 파일을 읽고 갱신하세요" 문구를 넣지 않으며, 상태 갱신은 오케스트레이터가 대신 수행한다.
> 이 규칙이 빠지면 에이전트가 계약을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 되고, 이 단계는 요식 행위가 된다.

프롬프트: `references/agent-prompts.md`의 "Phase 8.1" 섹션. 두 에이전트를 **병렬 실행**한다.

복원 결과를 받으면 **오케스트레이터가** frozen contract와 3방향 대조한다:

| 축 | 의미 |
|----|------|
| **BE ↔ contract** | 백엔드가 계약에서 이탈했는가 |
| **FE ↔ contract** | 프론트엔드가 계약에서 이탈했는가 |
| **BE ↔ FE** | 계약과 무관하게 양쪽이 서로 어긋났는가 (양쪽이 같은 방향으로 이탈하면 위 두 축은 통과하지만 이 축이 잡는다) |

불일치 항목은 Phase 8.2의 검증 대상 목록에 **우선 항목으로 추가**한다. Phase 8.1 자체는 코드를 수정하지 않는다.

### Phase 8.2: 통합 검증

frozen contract와 실제 코드를 다시 맞춘다. 반드시 검증할 항목:

Method/Path/Event Name · Request/Response 필드명과 타입 · 에러 코드와 프론트 fallback · loading/empty/retry/disabled 상태 · 인증/권한 · 페이지네이션/커서 · 캐시 무효화/재조회

Phase 8.1이 보고한 불일치를 먼저 확인한 뒤 위 항목을 점검한다.

권장 리뷰 조합: 백엔드 `scope-reviewer` + 프론트엔드 `scope-reviewer` (+UI 변경 시 `component-reviewer`, 접근성 영향 시 `a11y-reviewer`).
계약 불일치 가능성이 있으면 `Complex` 이상 model/effort로 생성한다.

**해결되지 않은 contract diff가 하나라도 남아 있으면 Phase 9로 가지 않는다** (수정 → Phase 8.2 재검증).

## Phase 9: 커밋/PR

둘 다 green이면 단일 PR로 묶는다.

- 커밋은 프론트/백엔드 단위를 분리한다.
- PR 본문은 `references/contract-templates.md`의 "PR 본문 순서"를 따른다.
- `--hard`면 push/PR 단계를 생략하고 현재 브랜치에서 종료한다.

## Phase 10: 회고 + 정리

1. `workflow-reflection`으로 회고를 남긴다 (변경량 기준 model/effort, 상태 파일 갱신).
2. 보완점은 **대상 도메인별로** 분류한다: BE → `.claude/be-harness/...`, FE → `.claude/fe-harness/...`, 풀스택(계약·Feature Matrix 등) → `.claude/fs-harness/...`. 플러그인 원본은 수정하지 않는다.
3. 보완점 반영 방식 질문:
   > "1. **로컬에만 저장** (기본값) — 각 도메인의 로컬 오버라이드 파일에 append.
   > 2. **로컬 저장 + 플러그인 레포 PR** — 도메인별 submit-feedback 호출.
   > 3. **건너뛰기**."
4. 옵션 2: 로컬 저장 먼저 → 도메인별(BE/FE/풀스택) 후보 분리 → 각 도메인마다 `/common:submit-feedback`을 대상 플래그(`--be` / `--fe` / `--fs`)와 함께 **따로** 호출. 도메인별로 별도 PR이 생성된다. 각 호출은 독립적 — 한쪽이 `SKIPPED:*`/FAILED여도 다른 쪽은 계속 진행. PR URL과 SKIP 사유를 모두 수집해 최종 보고서에 병기.
5. 최종 보고: `references/contract-templates.md`의 "최종 보고 형식"을 따른다.
6. 정리: `{STATE_FILE}`의 모든 Phase를 `DONE`/`SKIPPED:{사유}`로 갱신, `Remaining Phases`를 `없음`으로. 기본은 보관, 사용자 요청 시에만 `rm -f {STATE_FILE}`.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 (예: `BLOCKED:MAX_ITERATIONS`, 계약 불일치) |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/contract-templates.md` | Phase 1, 2, 3, 5, 9, 10 (템플릿·리뷰 기준) |
| `references/agent-prompts.md` | Phase 6 진입 시 |
