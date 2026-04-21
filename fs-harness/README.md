# fs-harness

풀스택 오케스트레이터 하네스. `be-harness` 와 `fe-harness` 를 병렬 사용하여 애자일 풀스택 워크플로우를 실행한다.

## 설치

```
/plugin marketplace add kangmomin/mimo-s-harness
/plugin install be-harness@harness-plugins
/plugin install fe-harness@harness-plugins
/plugin install fs-harness@harness-plugins
```

> **전제**: `be-harness` 와 `fe-harness` 가 **모두** 설치되어 있어야 한다.
> 한쪽만 있으면 단일 도메인 하네스(`/be-harness:start-workflow` 또는 `/fe-harness:start-workflow`) 를 사용하라.

## 초기 세팅

각 하네스의 profile을 먼저 생성해야 한다.

```bash
/be-harness:init       # .claude/be-harness.local.md
/fe-harness:init       # .claude/fe-harness.local.md
```

## 스킬 목록

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/fs-harness:start-workflow` | 풀스택 애자일 워크플로우 — 기능 정의 → 통신 계약 → 교차 리뷰 → FE/BE 병렬 구현 → 통합 검증 → 단일 PR |

## Phase 개요

```
Phase 0: /be-harness:request + /fe-harness:request → Feature Matrix
Phase 1: Integration Contract 초안 (요청/응답, 에러 모델, 인증)
Phase 2: 읽기 전용 리뷰 (계약/분업 리뷰)
Phase 3: Backend Plan / Frontend Plan / Shared Ownership
Phase 3.5: feature 브랜치 + 상태 파일 생성 → 자율 실행 시작
Phase 4: be-harness:workflow-implementer + fe-harness:workflow-implementer 병렬
Phase 5: 도메인별 품질 루프 (BE: simplify/convention/e2e, FE: simplify/lint/test/e2e)
Phase 6: 통합 검증 (계약 diff, scope, a11y, component)
Phase 7: 단일 PR
Phase 8: 회고
```

## 핵심 원칙

1. **Feature First** — 기능 단위 정의 먼저.
2. **Contract First** — 구현 전에 통신 계약 고정.
3. **Review Before Code** — 계약/분업 리뷰 후에만 구현.
4. **Split By Ownership** — FE/BE 파일 소유권 분리, 공용 산출물은 owner 지정.
5. **No Silent Contract Drift** — 계약이 바뀌면 Phase 1으로 복귀.

## 언제 쓰지 말아야 하는가

- 백엔드만 바뀌는 작업 → `/be-harness:start-workflow`
- 프론트엔드만 바뀌는 작업 → `/fe-harness:start-workflow`
