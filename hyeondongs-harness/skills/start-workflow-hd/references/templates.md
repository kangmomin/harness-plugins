> 이 문서는 `start-workflow-hd` 스킬의 Phase 4(상태 파일 생성)와 Phase 11(최종 보고·보완점 적용)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 템플릿 모음

## Phase 4: 상태 파일 템플릿

Write tool로 `{STATE_FILE}`을 생성한다:

```markdown
# Workflow State

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]

## Difficulty
[N]/10

## Current Phase
Phase 4 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 1 | orchestrator/request | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | review agents + orchestrator | 난이도 기준 | 난이도 기준 | DONE |
| 4 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 5 | workflow-implementer | 난이도 기준 | 난이도 기준 | PENDING |
| 6 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 7 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | component-reviewer/a11y-reviewer | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | workflow-pr/hard push | 난이도 기준 | 난이도 기준 | PENDING |
| 10 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 11 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 5: 구현
- Phase 6: 빌드/타입 체크
- Phase 7: 품질 루프
- Phase 8: 컴포넌트/접근성 리뷰
- Phase 9: PR / Push
- Phase 10: 성찰
- Phase 11: 최종 보고

## Edge Cases
[Spec의 엣지 케이스 목록]

## Plan
[확정된 Plan 전문 그대로 복사]

## Config
[.hyeondong-config.json 주요 설정]

## Plan Verification Log
[Phase 3.3 검증 루프의 Iteration Diff Log]

## Phase Results
[Phase 완료 시 결과 append]
```

## Phase 11: Workflow Report 템플릿

```markdown
## Workflow Report

### 1. 작업 요약
- **작업 유형**: [화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 컴포넌트**: [요약]

### 3. 엣지 케이스 대응
| # | 케이스 | 대응 방법 |
|---|--------|----------|

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| test | N | M |
| scope-review | N | M |
| lint | N | M |

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점
| # | 대상 스킬 | 보완 내용 | 적용 여부 |
|---|----------|----------|----------|
```
