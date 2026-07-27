> 이 문서는 `start-workflow-fs` 스킬의 Phase 1(Feature Matrix), 3(계약), 4(계약 리뷰), 6(상태 파일), 10.1(계약 격리 Read-back), 12(최종 보고)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 계약·템플릿 모음

## Phase 1: Feature Matrix 템플릿

```markdown
## Feature Matrix
| ID | 사용자 흐름 | 프론트 책임 | 백엔드 책임 | 완료 조건 |
|----|------------|------------|------------|----------|
```

반드시 정리할 항목:

- 어떤 사용자가 어떤 화면에서 어떤 행동을 하는가
- 그 행동에 대응하는 API/이벤트/쿼리 키가 무엇인가
- 프론트의 화면 상태: loading, empty, success, error
- 백엔드의 비즈니스 규칙, 권한, 저장소 변경
- 테스트 완료 조건

## Phase 3: Integration Contract 템플릿

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
```

계약에 빠지면 안 되는 항목: 인증/인가 · 페이지네이션/커서 규칙 · 날짜/금액/enum 포맷 · 정렬/필터 파라미터 · 캐시 무효화/재조회 규칙 · 하위 호환성 여부

## Phase 4: 계약 리뷰 출력 형식 + REJECT 기준

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

## Phase 6: 상태 파일 템플릿

Write tool로 `{STATE_FILE}`을 작성한다:

```markdown
# Fullstack Workflow State

## Spec
[합쳐진 Technical Spec]

## Feature Matrix
[Phase 1 결과]

## Integration Contract
[Phase 3 결과]

## Current Phase
Phase 6 - 자율 실행 시작 (agent: orchestrator (이 세션), model/effort: 최상위 고정 — 서브 에이전트는 등급표 기준 별도 명시)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 1 | orchestrator + request agents | 이 세션 (최상위) | 이 세션 (최상위) | DONE |
| 2 | Codex reviewer | 계약 복잡도 기준 (default Complex) | 계약 복잡도 기준 (default Complex) | DONE/SKIPPED |
| 3 | orchestrator | 이 세션 (최상위) | 이 세션 (최상위) | DONE |
| 4 | contract review agents | 계약 복잡도 기준 (default Complex) | 계약 복잡도 기준 (default Complex) | DONE |
| 5 | orchestrator + Codex reviewer | 계약 복잡도 기준 (default Complex) | 계약 복잡도 기준 (default Complex) | DONE |
| 6 | orchestrator | 이 세션 (최상위) | 이 세션 (최상위) | IN_PROGRESS |
| 7 | BE implementer + FE implementer | 도메인별 등급표 (default Standard) | 도메인별 등급표 (default Standard) | PENDING |
| 8 | BE/FE quality agents | 도메인별 등급표 (default Standard) | 도메인별 등급표 (default Standard) | PENDING |
| 9 | Codex reviewer | default Complex | default Complex | PENDING |
| 10 | integration review agents | 계약 복잡도 기준 (default Complex) | 계약 복잡도 기준 (default Complex) | PENDING |
| 11 | orchestrator + PR skill | PR 복잡도 기준 (default Simple/Standard) | PR 복잡도 기준 (default Simple/Standard) | PENDING |
| 12 | workflow-reflection | 변경량 기준 (default Standard) | 변경량 기준 (default Standard) | PENDING |

> "이 세션" = orchestrator 자신 (최상위 고정). 서브 에이전트는 등급표를 따르며 세션 effort를 상속하지 않는다.

## Remaining Phases
- Phase 7: 프론트/백엔드 병렬 구현
- Phase 8: 도메인별 품질 루프
- Phase 9: Codex 품질 리뷰
- Phase 10: 통합 검증
- Phase 11: 커밋/PR
- Phase 12: 회고 + 정리

## Backend Plan
[Phase 5.1]

## Frontend Plan
[Phase 5.2]

## Shared Ownership
[공용 산출물 owner]

## Assumptions
[없으면 "없음"]

## Plan Verification Log
[Phase 5.4 검증 루프 Iteration Diff Log를 시간순으로 기록]

## Plan Verification Summary
- **Total Iterations**: [수렴까지 반복 횟수]
- **Convergence**: [PROCEED / USER-INTERRUPTED / CODEX-UNAVAILABLE]
- **잔존 이슈**: [USER-INTERRUPTED인 경우 미해결 항목, 아니면 "없음"]

## Phase Results
[Phase 완료 시 결과 append]
```

## Phase 10.1: 계약 격리 Read-back

두 에이전트를 **같은 메시지 내에서 병렬 호출**한다 (Agent tool × 2). 서로의 결과도, frozen contract도 주지 않는다.

> **격리 규칙 (CRITICAL)**: ① `{STATE_FILE}` 경로를 전달하지 않고 읽지 말라고 명시 ② frozen contract·Plan·Feature Matrix를 프롬프트 본문에 넣지 않음 ③ "상태 파일을 읽고 기록하세요" 지시를 넣지 않음(상태 갱신은 오케스트레이터가 수행).
> 하나라도 빠지면 에이전트가 계약을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 된다.

### 백엔드 계약 복원 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: [계약 복잡도 기준 선택]
  effort: [계약 복잡도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}의 백엔드 코드만 읽고, 이 서버가 **실제로 제공하는 API 계약**을 복원하세요.

    ## 읽을 범위
    이번 브랜치에서 변경된 handler / route / DTO / 에러 매핑 코드
    (`git diff --name-only main...HEAD` 로 확인)

    ## 규칙
    - 프론트엔드 코드는 읽지 마세요.
    - `/tmp/workflow-state.md` 를 비롯한 명세·계약·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 의도를 추측하지 말고, **라우팅 등록·DTO 태그·검증 분기·반환 status code가 실제로 보장하는 것**만 적으세요.
    - 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 엔드포인트
    | Method | Path | Request 필드 (타입, 필수) | Response 필드 (타입) | 에러 status·코드 | 인증 | 출처 |
    |--------|------|--------------------------|---------------------|-----------------|------|------|

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    완료 후 "복원: N개 엔드포인트, 해석 불가: M건" 형식으로 보고하세요.
```

### 프론트엔드 계약 복원 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: [계약 복잡도 기준 선택]
  effort: [계약 복잡도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}의 프론트엔드 코드만 읽고, 이 클라이언트가 **실제로 기대하는 API 계약**을 복원하세요.

    ## 읽을 범위
    이번 브랜치에서 변경된 API 클라이언트 / 쿼리 훅 / 응답 타입 / 에러 처리 코드
    (`git diff --name-only main...HEAD` 로 확인)

    ## 규칙
    - 백엔드 코드는 읽지 마세요.
    - `/tmp/workflow-state.md` 를 비롯한 명세·계약·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 의도를 추측하지 말고, **요청 URL·전송 body·응답 타입 선언·에러 분기가 실제로 기대하는 것**만 적으세요.
    - 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 호출
    | Method | Path | 보내는 필드 (타입) | 기대 Response 필드 (타입) | 처리하는 에러 status·코드 | 인증 헤더 | 출처 |
    |--------|------|-------------------|--------------------------|--------------------------|----------|------|

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    완료 후 "복원: N개 호출, 해석 불가: M건" 형식으로 보고하세요.
```

### 3방향 대조 (오케스트레이터가 직접 수행)

두 복원본과 frozen contract를 대조한다. 계약을 가진 쪽만 할 수 있으므로 **에이전트에 위임하지 않는다**.

| 축 | 확인 | 대표 증상 |
|----|------|----------|
| BE ↔ contract | 서버가 계약에서 이탈 | 계약에 없는 필수 필드 요구, status code 불일치 |
| FE ↔ contract | 클라이언트가 계약에서 이탈 | 계약에 없는 응답 필드 참조, 에러 코드 미처리 |
| **BE ↔ FE** | 양쪽이 서로 어긋남 | 필드명 camelCase/snake_case 불일치, 한쪽만 nullable 가정 |

**BE ↔ FE 축이 이 단계의 고유 가치다.** 양쪽이 계약에서 같은 방향으로 이탈하면 위 두 축은 통과하지만, 서로 다른 방향으로 이탈하면 런타임에서만 드러난다. 병렬 구현에서 가장 흔한 실패 모드다.

불일치 항목을 Phase 10.2 검증 대상 목록의 **우선 항목**으로 넘긴다. Phase 10.1은 코드를 수정하지 않는다.

## Phase 11: PR 본문 순서

```markdown
## Feature Summary
## Integration Contract
## Backend Changes
## Frontend Changes
## Verification
## Assumptions
```

## Phase 12: 최종 보고 형식

```markdown
## 📋 Task Report: [작업명]

### 1. Pre-Review (Plan Verification Loop)
- Total Iterations: N
- Convergence: PROCEED / USER-INTERRUPTED / CODEX-UNAVAILABLE
- Iteration Diff Log 요약: v1→v2, v2→v3 ... 핵심 변경
- Codex Feedback (최종 라운드): ...
- Claude/다관점 Feedback (최종 라운드): ...
- 기각된 피드백 + 사유: ...
- 잔존 이슈 (USER-INTERRUPTED인 경우만): ...

### 2. Implementation Details
- Assumptions: ...
- Key Changes: ...

### 3. Final Convention Review
- Layer Analysis: ...
- Simplicity Check: ...
- Codex Quality Review: ...

### 4. Status
- Verification: ...
- Cleanup: ...
```

Claude 또는 Codex 교차 리뷰를 실제로 수행할 수 없는 환경이면 그 사실을 적고, 누락을 숨기지 않는다.
