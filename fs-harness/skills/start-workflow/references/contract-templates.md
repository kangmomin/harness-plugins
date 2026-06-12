> 이 문서는 `start-workflow`(fs-harness) 스킬의 Phase 1(Feature Matrix), 2(계약), 3(계약 리뷰), 5(상태 파일), 10(최종 보고)에서 로드된다. 단독 실행 금지.
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
```

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

Write tool로 `{STATE_FILE}`을 작성한다:

```markdown
# Fullstack Workflow State

## Spec
[합쳐진 Technical Spec]

## Feature Matrix
[Phase 1 결과]

## Integration Contract
[Phase 2 결과]

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
| 6 | BE workflow-implementer + FE workflow-implementer | 도메인별 기준 | 도메인별 기준 | PENDING |
| 7 | BE/FE quality agents | 도메인별 기준 | 도메인별 기준 | PENDING |
| 8 | integration review agents | 계약 복잡도 기준 | 계약 복잡도 기준 | PENDING |
| 9 | orchestrator + PR skill | PR 복잡도 기준 | PR 복잡도 기준 | PENDING |
| 10 | workflow-reflection | 변경량 기준 | 변경량 기준 | PENDING |

## Remaining Phases
- Phase 6: 프론트/백엔드 병렬 구현
- Phase 7: 도메인별 품질 루프
- Phase 8: 통합 검증
- Phase 9: 커밋/PR
- Phase 10: 회고 + 정리

## Backend Plan
[Phase 4.1]

## Frontend Plan
[Phase 4.2]

## Shared Ownership
[공용 산출물 owner]

## Assumptions
[없으면 "없음"]

## Plan Verification Log
[Phase 4.4 검증 루프의 Iteration Diff Log]

## Phase Results
[Phase 완료 시 결과 append]
```

## Phase 9: PR 본문 순서

```markdown
## Feature Summary
## Integration Contract
## Backend Changes
## Frontend Changes
## Verification
## Assumptions
```

## Phase 10: 최종 보고 형식

```markdown
## 📋 Task Report: [작업명]

### 1. Pre-Review (Plan)
- Codex Feedback: ...
- Claude Feedback: ...
- Refinement: ...

### 2. Implementation Details
- Assumptions: ...
- Key Changes: ...

### 3. Final Convention Review
- Layer Analysis: ...
- Simplicity Check: ...

### 4. Status
- Verification: ...
- Cleanup: ...
```

Claude 또는 Codex 교차 리뷰를 실제로 수행할 수 없는 환경이면 그 사실을 적고, 누락을 숨기지 않는다.
