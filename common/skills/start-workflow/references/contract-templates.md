> 이 문서는 `/common:start-workflow` 의 **풀스택 경로**(`references/fullstack.md`)에서 Phase 1(Feature Matrix), 2(계약), 3(계약 리뷰), 5(상태 파일), 10(최종 보고)에 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 `fullstack.md` 를 따른다.

# 계약·템플릿 모음

## Phase 1: Feature Matrix 템플릿

```markdown
## Feature Matrix
| ID | 사용자 흐름 | 프론트 책임 | 백엔드 책임 | 완료 조건 |
|----|------------|------------|------------|----------|
| F-01 | | | | |
```

**ID 규칙**: `F-01`부터 2자리 순번. 확정 후 재배열·재사용하지 않는다 — Phase 6.1 테스트 근거와 Phase 8.1 대조가 이 ID로 매칭한다. 행 삭제 시 번호를 당기지 않는다.

반드시 정리할 항목:

- 어떤 사용자가 어떤 화면에서 어떤 행동을 하는가
- 그 행동에 대응하는 API/이벤트/쿼리 키가 무엇인가
- 프론트의 화면 상태: loading, empty, success, error
- 백엔드의 비즈니스 규칙, 권한, 저장소 변경
- 테스트 완료 조건

## Phase 2: Integration Contract 템플릿

```markdown
## Integration Contract
### Surface
- REST / GraphQL / gRPC / Event 중 무엇인지

### Endpoint Or Event
- Method / Path / Event Name
- Auth / Role
- Query / Path / Header / Body 필드

### Success Response
- 필드명 / 타입 / nullable / 기본값

### Error Contract
- 에러 코드
- 사용자 노출 메시지 여부
- 프론트 fallback 동작

### UI State Contract
- loading / empty / disabled / retry / optimistic update

### Ownership
- Backend owner
- Frontend owner
- Shared artifact owner
- **공용 계약 테스트 owner**: 오케스트레이터 (도메인 에이전트 수정 금지)

### 검증 조항 (`CT-nn`)
| ID | 조항 | 검증 방법 | 담당 도메인 |
|----|------|----------|------------|
| CT-01 | | | BE / FE / 양쪽 |
```

**`CT-nn`이 Phase 6.1 계약 테스트의 근거다.** 필드·status·에러 코드·상태 전이 중 **외부에서 검증 가능한 것**에만 부여한다.
"올바르게 동작한다" 같은 검증 불가 문장은 조항이 아니다. 계약이 바뀌면 번호를 유지한 채 내용만 갱신하고, 연결된 테스트를 다시 Red로 되돌린다.

계약에 빠지면 안 되는 항목:

- 인증/인가
- 페이지네이션/커서 규칙
- 날짜/금액/enum 포맷
- 정렬/필터 파라미터
- 캐시 무효화 또는 재조회 규칙
- 하위 호환성 여부

## Phase 3: 계약 리뷰 출력 형식 + REJECT 기준

리뷰 출력 형식:

```markdown
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [목록 또는 "없음"]
**Suggestions**: [목록 또는 "없음"]
**Next Action**: [오케스트레이터가 바로 수행할 1개 액션]
```

다음 중 하나라도 있으면 **REJECT**다:

- 필수 필드 정의 누락
- 성공/실패 응답 해석이 양쪽에서 다름
- 인증/권한 책임이 불명확함
- shared artifact owner가 없음
- 프론트 완료 조건과 백엔드 완료 조건이 서로 다름

## Phase 5: 상태 파일 템플릿

`RUN_ID`는 Pre-flight 결과를 사용한다. 신규 실행의 구현 직전에 `START_SHA`만 1회 수집하며, 재개 시 기존 상태를 보존한다:

```bash
START_SHA=$(git rev-parse HEAD 2>/dev/null || echo 없음)
```

Write tool로 `{STATE_FILE}`을 작성한다:

```markdown
# Fullstack Workflow State

## Run
- CWD: {CWD}
- MODE: fs
- RUN_ID: {RUN_ID}
- RUN_DIR: {RUN_DIR}

## Flags
- MODE: fs
- HARD_MODE: {true|false}
- TDD: {true|false}
- REFLECT: {true|false}
- TIER: standard(고정)
- CODEX: {none|mix|max}
- CODEX_MODELS: {review={provider}/{model}@{effort},explore=…,judge=…,write=… | N/A} — 4슬롯 고정 순서·확정 effort(`-` = 키 생략), `CODEX: none`이면 `N/A` (`codex-mode.md` §2.1)
- RUN_ID: {RUN_ID}
- START_SHA: {START_SHA}

## Spec
[합쳐진 Technical Spec]

## Feature Matrix
[Phase 1 결과]

## Integration Contract
[Phase 2 결과]

## Codex Runtime
- 상태: {active | fallback({global:{사유} | provider:{id}:{사유} | slot:{슬롯}:{사유}, …})} — 생성 시 `$CODEX_RUNTIME` 값 그대로 (`codex-mode.md` §7 직렬화). `CODEX: none`이면 `N/A`

| 호출 ID | 사용 종류 | 범위 | S0 | 핸들 |
|---------|----------|------|----|------|
[§5 쓰기 안전 `pending` 표 — Codex 쓰기 호출 dispatch 전에 행 기록, `VERIFIED`/종료 조건 도달 시 삭제. 재개 시 행이 남아 있으면 마지막 호출 사망으로 판정]

## Current Phase
Phase 5 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 1 | orchestrator + be/fe request | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | contract review agents | 계약 복잡도 기준 | 계약 복잡도 기준 | DONE |
| 4 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 5 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 6.1 | BE/FE Red 에이전트 + 오케스트레이터 배리어 | 도메인별 기준 | 도메인별 기준 | PENDING |
| 6.2 | BE workflow-implementer + FE workflow-implementer | 도메인별 기준 | 도메인별 기준 | PENDING |
| 7 | BE/FE quality agents | 도메인별 기준 | 도메인별 기준 | PENDING |
| 8 | integration review agents | 계약 복잡도 기준 | 계약 복잡도 기준 | PENDING |
| 9 | orchestrator + PR skill | PR 복잡도 기준 | PR 복잡도 기준 | PENDING |
| 10 | workflow-reflection | 변경량 기준 | 변경량 기준 | PENDING (`--reflect` 미지정 시 SKIPPED:REFLECT_NOT_REQUESTED) |
| 11 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 6.1: 계약 테스트 우선 (Red)
- Phase 6.2: 프론트/백엔드 병렬 구현 (Green)
- Phase 7: 도메인별 품질 루프
- Phase 8: 통합 검증
- Phase 9: 커밋/PR
- Phase 10: 회고 (`--reflect` 미지정 시 목록에서 제외)
- Phase 11: 최종 보고 + 정리

## Test Baseline (도메인별)
[Phase 5에서 수집. TDD SKIP 도메인은 사유만 기록. **불변 — 이후 갱신하지 않는다**]

- 커밋: {SHA}   |   수집 Phase: 5 (자율 실행 진입 전)

| 도메인 | suite | 명령 | 러너 완주 | 통과 | 실패 | 실패 목록 (식별자 :: 정규화 시그니처) |
|--------|-------|------|----------|------|------|--------------------------------------|
| BE | unit | {testCommand} | Y | 142 | 0 | 없음 |
| FE | unit | {testCommand} | Y | 88 | 1 | `ProductList > 빈 목록` :: `unable to find role=list` |

## TDD Test Map (도메인별)
[Phase 6.1에서 오케스트레이터가 기록. Phase 7 회귀 대조와 Phase 11 보고의 기준]
> **Phase 8.1 계약 복원 에이전트에 이 표를 전달하지 않는다** — 계약 역추론으로 격리가 무너진다.

| 근거 ID | 도메인 | 테스트 | 파일 | Red | Green |
|---------|--------|--------|------|-----|-------|
| CT-01 | BE | example.com/app/handler::Test_Create_201 | handler_test.go:20 | red_assertion | PASS |
| CT-01 | FE | 생성 성공 시 목록 갱신 | useCreate.test.ts:14 | red_assertion | PASS |
| CT-02 | 공용 | 응답 스키마 일치 | contract.test.ts:8 | red_assertion | PASS |
| F-02 | BE | — | — | N/A(영향 없음) | - |

## Backend Plan
[Phase 4.1]

## Frontend Plan
[Phase 4.2]

## Shared Ownership
[공용 산출물 owner]

## Assumptions
[없으면 "없음"]

## Plan Verification Log
[Phase 4.4 검증 루프의 Iteration Diff Log — Phase 5 상태 파일 생성 시 복사]

## Phase Results
[Phase 완료 시 결과 append]

## Final Decisions
[Phase 11 ②에서 받은 유저 결정을 받는 즉시 append. 재개 시 기록된 항목은 다시 묻지 않는다]

| 항목 | 결정 | 시각 |
|------|------|------|

## Artifacts
- workflow-report: {아카이브 경로 | 미생성}
```

`--reflect` 미지정 시(기본): 생성 시점에 Phase 10 행의 Status를 `SKIPPED:REFLECT_NOT_REQUESTED`로 기록하고, `Remaining Phases`에서 "Phase 10: 회고"를 제외한다.

## Phase 9: PR 본문 순서

```markdown
## Feature Summary
## Integration Contract
## Backend Changes
## Frontend Changes
## Verification
## Assumptions
```

## Phase 11: 최종 보고 형식

```markdown
## 📋 Task Report: [작업명]

### 1. Pre-Review (Plan)
- Codex 모드: [none | mix | max] · 모델: [기본 | {CODEX_MODELS}]{ · runtime: fallback({항목}, …)}
- Codex Feedback: ...
- Claude Feedback: ...
- Refinement: ...

### 2. Implementation Details
- Assumptions: ...
- Key Changes: ...

### 3. Final Convention Review
- Layer Analysis: ...
- Simplicity Check: ...

### 4. 테스트 / 회귀
- **BE 테스트 판정**: [PASS/WARN/FAIL] — regression [n] / new_red [n] / flaky [n] / pre_existing [n](범위 밖)
- **FE 테스트 판정**: [PASS/WARN/FAIL] — 동일 형식
- **계약 커버리지**: `CT-nn` 중 테스트로 고정된 비율 [n/m] (`N/A(영향 없음)` 제외)

### 4.1 TDD 미해결 항목 (유저 결정 필요)
> TDD가 SKIP이거나 미해결 항목이 없으면 "없음"으로 적고 이 섹션을 비운다.

| 유형 | 도메인 | 항목 | 필요한 결정 |
|------|--------|------|------------|
| `BLOCKED:TEST_NOT_GREEN` | BE/FE | [실패 목록] | 추가 수정 / 범위 제외 |
| `BLOCKED:NO_VALID_RED` | BE/FE | [사유] | 테스트 재작성 / TDD 없이 유지 |
| `[TestConflict]` (계약) | — | [테스트 ↔ `CT-nn`] | **계약 재정의 (Phase 2 복귀)** |
| `[Breaking]` | BE/FE | [테스트명, 변경 내용] | 호환성 검토 |
| `cannot_compile` | BE/FE | [근거 ID] | 수동 작성 / 범위 제외 |

### 5. Status
- Verification: ...
- Cleanup: ...

### 6. 회고
- [Phase 10 DONE: 보완점 항목 — 도메인 분류 · 반영 방식 결정 · submit-feedback PR URL / SKIP 사유. 없으면 "없음"]
- [그 외: SKIPPED:REFLECT_NOT_REQUESTED]
```

머리글 1~6은 Phase 11 아카이브의 `--require-headings` 검증 대상이다 — 이름을 바꾸지 않는다. `### 6. 회고`는 회고를 건너뛴 경우에도 반드시 존재해야 한다 (회고 결과의 유무가 md 기록에서 누락되지 않게).

Claude 또는 Codex 교차 리뷰를 실제로 수행할 수 없는 환경이면 그 사실을 적고, 누락을 숨기지 않는다.
