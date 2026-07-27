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
[Spec의 엣지 케이스 표를 **ID·참조 구현 열까지 그대로** 복사. Phase 7.7 Diff 판정의 기준이므로 ID를 생략하거나 다시 매기지 않는다]

## Plan
[확정된 Plan 전문 그대로 복사]

## Config
[.hyeondong-config.json 주요 설정]

## Plan Verification Log
[Phase 3.3 검증 루프의 Iteration Diff Log]

## Readback Diff
[Phase 7.7 결과. Phase 7.7 실행 전에는 `미실행`]

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
| ID | 케이스 | 대응 방법 | 테스트 | Read-back |
|----|--------|----------|--------|-----------|
| EC-01 | [케이스] | [대응] | PASS | 일치 |
| EC-02 | [케이스] | [대응] | 미작성 | A 검증 누락 |

- `Read-back` 열: Phase 7.7 Diff 유형(A~E) 또는 `일치`. Phase 7.7이 SKIP이면 `-`

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| test | N | M |
| scope-review | N | M |
| lint | N | M |

- **Read-back 판정**: [PASS/WARN/FAIL] — A [n]건 / C [n]건 / E [n]건 (소스: 테스트 파일 / 테스트 리포트 / 구현 코드)

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점
| # | 대상 스킬 | 보완 내용 | 적용 여부 |
|---|----------|----------|----------|

### 8. Read-back Diff (유저 결정 필요)
> Phase 7.7이 SKIP이거나 판정이 PASS면 "없음"으로 적고 이 섹션을 비운다.

| 유형 | 항목 | Spec | 실제 보장 | 참조 구현 | 필요한 결정 |
|------|------|------|----------|----------|------------|
| C 기대값 불일치 | 빈 목록 (EC-03) | EmptyState | 스켈레톤 유지 | `OrderList.tsx:52` → EmptyState | 어느 쪽으로 통일할지 |
| A 검증 누락 | 네트워크 오류 (EC-05) | 재시도 버튼 | 테스트 없음 | - | 테스트 추가 / 범위 제외 |
| B Spec 밖 | 입력 300자 제한 | 없음 | maxLength 적용 | - | Spec에 반영 / 제거 |
| E 컨벤션 이탈 | 로딩 상태 (EC-01) | 스피너 | 스피너 | `ProductList.tsx:31` → 스켈레톤 | 기존 패턴 따를지 |
| D 해석 불가 | `waitFor` 단언 (`x.test.tsx:88`) | - | 불명 | - | 의도 확인 |
```
