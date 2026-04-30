---
name: start-workflow-fs
description: "프론트엔드와 백엔드를 분리된 에이전트로 병렬 오케스트레이션한다. 기능 정의 → 통신 계약 정의 → 교차 리뷰 → 영역별 구현 → 통합 검증 → PR 순서의 애자일 풀스택 워크플로우."
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: <작업 설명 또는 빈 값>
user-invocable: true
---

# Start Workflow Full Stack — Agile Orchestrator

프론트엔드와 백엔드를 하나의 큰 구현 덩어리로 취급하지 않는다.
먼저 **기능 단위와 통신 계약**을 고정하고, 그 다음 **프론트/백엔드 전용 에이전트**가 병렬로 구현한 뒤, 마지막에 통합 검증으로 닫는다.

## 언제 쓰는가

- 화면과 API가 함께 바뀌는 기능
- 요청/응답 구조, 에러 모델, 인증 방식이 같이 정리되어야 하는 작업
- 프론트와 백엔드가 서로를 기다리며 흔들리기 쉬운 작업

## 언제 쓰지 않는가

- 백엔드만 바뀌는 작업: `start-workflow-mm`
- 프론트엔드만 바뀌는 작업: `start-workflow-hd`

## 전제 조건

- `request-mm`, `request-hd`
- `workflow-implementer`
- `scope-reviewer`, `component-reviewer`, `a11y-reviewer`
- `workflow-reflection`
- 프론트 하네스와 백엔드 하네스가 모두 사용 가능해야 한다.

한쪽 하네스가 없으면 이 스킬로 억지로 진행하지 말고, 단일 도메인 워크플로우로 내린다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | feature 브랜치 생성과 PR 생성을 건너뛰고 현재 브랜치에서 마무리한다. |

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

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
5. **No Silent Contract Drift**: 계약이 바뀌면 구현을 계속하지 말고 계약 단계로 되돌아간다.

## Phase 매핑

| Phase | 담당 | 목적 |
|-------|------|------|
| 0 | 오케스트레이터 + `request-mm` + `request-hd` | 기능 정의 및 도메인 분리 |
| 1 | 오케스트레이터 | 통신 계약 초안 작성 |
| 2 | 읽기 전용 리뷰 에이전트 2개 이상 | 계약/분업 리뷰 |
| 3 | 오케스트레이터 | 프론트/백엔드 Plan 분리 |
| 4 | 백엔드 구현 에이전트 + 프론트 구현 에이전트 | 병렬 구현 |
| 5 | 각 도메인 품질 루프 | 영역별 안정화 |
| 6 | 읽기 전용 리뷰 에이전트 | 통합 검증 |
| 7 | 오케스트레이터 + PR 스킬 | 최종 커밋/PR |
| 8 | `workflow-reflection` | 회고 및 정리 |

## 자율 실행 규칙

- Phase 0~3: 유저와 기능/계약/Plan을 합의한다.
- **Phase 3.5 이후 ~ Phase 8 완료까지**는 자동 실행한다.
- 멈춰야 하는 지점은 계약 불일치, 권한 부족, 테스트 불가, 또는 유저 승인 없이는 바꿀 수 없는 요구사항뿐이다.

## Spec 외 변경 금지 원칙

Spec 또는 계약에 없는 변경이 필요하면:

1. 코드를 먼저 바꾸지 않는다.
2. `/tmp/fullstack-workflow-state.md`의 `Assumptions` 섹션에 `[Assumption]`으로 기록한다.
3. 계약 리뷰를 다시 거친 뒤에만 반영한다.

## Phase 0: 기능 정의 + Feature Matrix

상세 명세가 이미 충분하면 그 내용을 정리해서 시작한다.
부족하면 `request-mm`로 백엔드 관점 질문을, `request-hd`로 프론트엔드 관점 질문을 각각 수행해 아래 표를 만든다.

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

이 결과가 한쪽 도메인만 필요하면 풀스택 워크플로우를 중단하고 단일 도메인 스킬로 전환한다.

## Phase 1: 통신 계약 정의

구현 전에 반드시 **Integration Contract**를 작성한다.

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

계약에는 아래가 빠지면 안 된다:

- 인증/인가
- 페이지네이션/커서 규칙
- 날짜/금액/enum 포맷
- 정렬/필터 파라미터
- 캐시 무효화 또는 재조회 규칙
- 하위 호환성 여부

## Phase 2: 계약 리뷰

계약 초안이 나오면 읽기 전용 리뷰를 병렬로 수행한다.

### Batch 1

- 백엔드 리뷰어 역할의 advisor: 데이터 정합성, 비즈니스 규칙, 에러 모델 검토
- 프론트엔드 리뷰어 역할의 advisor: 화면 상태, 사용자 흐름, 소비 가능성 검토

### Batch 2

- 프론트가 백엔드 계약을 소비하는 데 빠진 필드가 없는지 교차 리뷰
- 백엔드가 프론트 요구를 과도하게 책임지지 않는지 교차 리뷰

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

## Phase 3: 분리 Plan 작성

`EnterPlanMode`를 활성화하고 아래 3개를 확정한다.

### 3.1 백엔드 Plan

- 변경 파일
- 핸들러/서비스/리포지토리 범위
- 테스트 전략
- 계약 산출물 owner 여부

### 3.2 프론트엔드 Plan

- 변경 파일
- 페이지/컴포넌트/훅 범위
- 화면 상태 처리 전략
- 타입/클라이언트 연동 전략

### 3.3 공용 Plan

- feature 브랜치 전략
- shared artifact owner
- 통합 테스트 순서
- 롤백 조건
- `[Assumption]` 목록

Plan은 아래를 지켜야 한다:

- 한 파일의 owner는 한쪽만 가진다.
- 생성 코드나 shared schema도 owner를 지정한다.
- 프론트는 계약 확정 전 mock shape를 임의로 만들지 않는다.
- 백엔드는 프론트 화면 로직을 추측해서 응답 필드를 늘리지 않는다.

리뷰가 끝나면 `ExitPlanMode`로 Plan을 확정한다.

## Phase 3.5: 브랜치 + 상태 파일

`--hard`가 아니면 feature 브랜치를 만든다.

```bash
git checkout -b feat/{작업-요약-kebab-case}
```

그다음 `/tmp/fullstack-workflow-state.md`를 작성한다:

```markdown
# Fullstack Workflow State

## Spec
[합쳐진 Technical Spec]

## Feature Matrix
[Phase 0 결과]

## Integration Contract
[Phase 1 결과]

## Backend Plan
[Phase 3.1]

## Frontend Plan
[Phase 3.2]

## Shared Ownership
[공용 산출물 owner]

## Assumptions
[없으면 "없음"]
```

## Phase 4: 프론트/백엔드 병렬 구현

두 구현 에이전트를 **병렬**로 실행한다.

### 백엔드 구현 에이전트

- 입력: 상태 파일 전체
- 책임: 백엔드 Plan의 소유 파일만 수정
- 금지: 프론트 파일 수정, 계약 외 필드 추가

### 프론트엔드 구현 에이전트

- 입력: 상태 파일 전체
- 책임: 프론트엔드 Plan의 소유 파일만 수정
- 금지: 백엔드 파일 수정, 계약 외 필드 가정

두 에이전트 모두 보고해야 할 것:

- 변경 파일 목록
- 계약 대비 차이점
- `[Assumption]` 목록
- 막힌 계약 항목

구현 중 계약 변경이 필요하면 즉시 Phase 1로 돌아간다.

## Phase 5: 도메인별 품질 루프

### 백엔드 루프

1. `simplify-loop-mm`
2. `convention-check-mm`
3. `e2e-test-loop-mm`
4. API 계약이 바뀌었으면 `e2e-apidog-schema-gen-mm`

### 프론트엔드 루프

1. build + type-check
2. `simplify-loop-hd`
3. `convention-check-hd`
4. `test-loop-hd`
5. `lint-check-hd`

규칙:

- 각 도메인은 자기 루프만 다시 돈다.
- 한쪽 루프 결과가 계약을 흔들면 둘 다 멈추고 Phase 1로 복귀한다.
- 최대 3회까지 반복한다.

## Phase 6: 통합 검증

구현이 끝나면 frozen contract와 실제 코드를 다시 맞춘다.

반드시 검증할 항목:

- Method / Path / Event Name
- Request / Response 필드명과 타입
- 에러 코드와 프론트 fallback
- loading / empty / retry / disabled 상태
- 인증/권한
- 페이지네이션/커서
- 캐시 무효화 또는 재조회

권장 리뷰 조합:

- 백엔드 `scope-reviewer`
- 프론트엔드 `scope-reviewer`
- UI 변경이 있으면 `component-reviewer`
- 접근성 영향이 있으면 `a11y-reviewer`

해결되지 않은 contract diff가 하나라도 남아 있으면 PR 단계로 가지 않는다.

## Phase 7: 커밋/PR

둘 다 green이면 단일 PR로 묶는다.

- 커밋은 프론트/백엔드 단위를 분리한다.
- PR 생성은 현재 하네스의 PR 스킬을 사용한다.
- PR 본문은 아래 순서를 따른다:

```markdown
## Feature Summary
## Integration Contract
## Backend Changes
## Frontend Changes
## Verification
## Assumptions
```

`--hard`면 push/PR 단계를 생략하고 현재 브랜치에서 종료한다.

## Phase 8: 회고 + 정리

- `workflow-reflection`으로 회고를 남긴다.
- 임시 상태 파일을 삭제한다.

```bash
rm -f /tmp/fullstack-workflow-state.md
```

최종 보고는 아래 형식을 따른다:

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
