> 이 문서는 `start-workflow-mm` 스킬의 Phase 6(상태 파일·라이브 노트 생성)과 Phase 14(HTML 렌더링·최종 보고)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}`, `{WORKLOG_DIR}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 템플릿 모음

## Phase 6: 상태 파일 템플릿

Write tool로 `{STATE_FILE}`을 생성한다:

```markdown
# Workflow State

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[생성/수정/검토/디버깅]

## Difficulty
[N]/10

## Current Phase
Phase 6 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 1 | orchestrator (EnterPlanMode) | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 4 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 5 | review agents + orchestrator | 난이도 기준 | 난이도 기준 | DONE |
| 6 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 7 | workflow-implementer/general-purpose | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 10 | orchestrator + Codex | Complex 이상 | Complex 이상 | PENDING |
| 11 | workflow-doc-sync | 난이도 기준 | 난이도 기준 | PENDING |
| 12 | workflow-pr 또는 /common:commit-hard-push | 난이도 기준 | 난이도 기준 | PENDING |
| 13 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 14 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 7: 구현
- Phase 8: 빌드 체크
- Phase 9: 품질 루프
- Phase 10: Codex 품질 리뷰
- Phase 11: 문서 동기화
- Phase 12: PR / Push
- Phase 13: 성찰
- Phase 14: 최종 보고

## Execution Strategy
[sequential/parallel-slices]

## Edge Cases
[Spec의 엣지 케이스 목록]

## E2E 메인 플로우
[Phase 4에서 사용자가 서술한 메인 플로우 전문, 또는 "자동 도출 (git diff 기반)"]

## Plan
[확정된 Plan 전문 그대로 복사]

## Plan Verification Log
[Phase 5.3 검증 루프 Iteration Diff Log를 시간순으로 기록]

## Plan Verification Summary
- **Total Iterations**: [수렴까지 반복 횟수]
- **Convergence**: [PROCEED / USER-INTERRUPTED / CODEX-UNAVAILABLE / BLOCKED:MAX_ITERATIONS→사용자 선택]
- **잔존 이슈**: [미해결 항목, 없으면 "없음"]

## Phase Results
[Phase 완료 시 결과 append]
```

`parallel-slices`인 경우 아래를 추가한다:

```markdown
## Slices
[Plan에서 정의한 Slice 정보 그대로 복사]
```

## Phase 6: Implementation Notes 라이브 파일 초기화

상태 파일과 별개로 `{IMPL_NOTES}`를 Write tool로 생성한다. 기존 파일이 있으면 덮어쓴다.

```markdown
# Implementation Notes — {작업 요약}

> 자율 실행 중 발생한 판단·편차·트레이드오프·미결 질문이 실시간으로 누적됩니다.
> 유저는 언제든 이 파일을 열어 비동기로 피드백할 수 있으며, Phase 14에서 HTML로 일괄 렌더링됩니다.

## 설계 결정
<!-- "- {Phase} | {file:line 또는 범위} — 선택: {택1} (대안: {택2}) — 근거: {1~2줄}" -->

## 편차
<!-- "- {Phase} | {file:line 또는 범위} — Spec: {원래 기대 동작} → 실제: {바뀐 동작} — 사유: {1~2줄}" — [Assumption] 보고와 1:1 대응 -->

## 트레이드오프
<!-- "- {Phase} | {결정} — 채택안: {A} / 기각안: {B,C} — 이유: {1~2줄}" -->

## 미결 질문
<!-- "- [ ] {Phase} | {질문} — 영향: {핵심 동작/주변 영향/판단 보류}" -->
```

> 4개 섹션 헤더(`## 설계 결정`, `## 편차`, `## 트레이드오프`, `## 미결 질문`)는 정확히 이 형태로 유지한다. Phase 14 HTML 렌더링이 헤더 텍스트로 섹션을 식별한다.

## Phase 14: Implementation Notes HTML 렌더링

보고서 작성 직전, 라이브 노트를 HTML 산출물로 변환한다.

1. **출력 디렉토리 보장**: `mkdir -p {WORKLOG_DIR}`
2. **출력 경로 결정**: `{WORKLOG_DIR}/{YYYYMMDD}-{task-name-kebab}-impl-notes.html`
   - `YYYYMMDD`: 현재 날짜 (Bash `date +%Y%m%d`)
   - `task-name-kebab`: Phase 6 브랜치명 또는 Spec 제목을 kebab-case로 변환
3. **렌더링**: `{IMPL_NOTES}`를 Read한 뒤, 4개 섹션을 각각 색상 카드로 변환하여 Write tool로 HTML 파일을 생성한다. 권장 템플릿:

```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Implementation Notes — {task}</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:880px;margin:32px auto;padding:0 16px;color:#222;line-height:1.55}
 h1{font-size:1.5rem;margin-bottom:.25rem}
 .meta{color:#666;font-size:.9rem;margin-bottom:1.5rem}
 section{border-left:4px solid;padding:12px 16px;margin:16px 0;border-radius:6px;background:#fafafa}
 section.decision{border-color:#2563eb}
 section.deviation{border-color:#ea580c}
 section.tradeoff{border-color:#16a34a}
 section.open{border-color:#dc2626}
 section h2{margin:0 0 8px;font-size:1.1rem}
 ul{margin:0;padding-left:1.2rem}
 .empty{color:#888;font-style:italic}
 .alert{background:#fef2f2;border:1px solid #fecaca;padding:12px 16px;border-radius:6px;margin-bottom:16px}
</style></head><body>
<h1>Implementation Notes — {task}</h1>
<div class="meta">생성: {ISO timestamp} · 브랜치: {branch} · 워크플로우: start-workflow-mm</div>
{미결 질문이 1건 이상이면 아래 alert 블록 삽입}
<div class="alert"><strong>사용자 확인 필요</strong> — 미결 질문 {N}건이 있습니다. 아래 빨간 카드 참고.</div>
<section class="decision"><h2>설계 결정</h2>{ul 또는 empty}</section>
<section class="deviation"><h2>편차</h2>{ul 또는 empty}</section>
<section class="tradeoff"><h2>트레이드오프</h2>{ul 또는 empty}</section>
<section class="open"><h2>미결 질문</h2>{ul 또는 empty}</section>
</body></html>
```

> 각 섹션이 비어 있으면(헤더 외에 항목 없음) `<p class="empty">기록 없음</p>`로 표기한다.
> `## 미결 질문`의 체크박스(`- [ ]`)는 `<input type="checkbox" disabled>`로 변환해 시각적으로 유지한다.

4. **결과 경로를 메모**: Phase 14 보고서의 `Implementation Notes` 섹션에 절대 경로를 명시.

## Phase 14: Workflow Report 템플릿

```markdown
## Workflow Report

{미결 질문 N≥1 인 경우에만 보고서 최상단에 아래 블록을 자동 삽입}
> ⚠️ **사용자 확인 필요** — Implementation Notes에 미결 질문 {N}건이 있습니다.
> 상세: `{WORKLOG_DIR}/{YYYYMMDD}-{task}-impl-notes.html` (`## 미결 질문` 섹션)
> 항목 목록:
> - [ ] {질문 1 요약}
> - [ ] {질문 2 요약}

### 1. 작업 요약
- **작업 유형**: [생성/수정/검토/디버깅]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 로직**: [요약]

### 3. 엣지 케이스 대응
| # | 케이스 | 대응 방법 |
|---|--------|----------|

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| e2e | N | M |
| scope-review | N | M |

- **E2E 리포트 HTML**: [Phase 9.6 마지막 실행이 보고한 경로 (여러 번 돌렸으면 최종 iteration 산출물). 미생성이면 "미생성 (E2E SKIP 또는 미실행)"]

### 5. 문서 동기화
- Apidog 업데이트: [Y/N, 요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. Codex 리뷰 기록
| 시점 | 수행 여부 | 핵심 피드백 | 반영 여부 |
|------|----------|------------|----------|
| Spec+Plan 통합 (Phase 5.3) | Y/N (Iteration N회) | 요약 | Y/N/사유 |
| 품질 리뷰 (Phase 10) | Y/N | 요약 | Y/N/사유 |

### 7.1 Plan Verification Loop 기록
- **Total Iterations**: N
- **Convergence**: PROCEED / USER-INTERRUPTED
- **Iteration Diff Log 요약**: [v1→v2, v2→v3 ... 핵심 변경]
- **잔존 이슈**: [USER-INTERRUPTED인 경우만, 아니면 "없음"]

### 8. Implementation Notes
- **HTML 산출물**: `{WORKLOG_DIR}/{YYYYMMDD}-{task}-impl-notes.html`
- **설계 결정**: [N]건
- **편차**: [N]건 ([Assumption] 보고와 동기 확인: 일치/불일치 N건)
- **트레이드오프**: [N]건
- **미결 질문**: [N]건 ([N≥1이면 보고서 상단 블록과 일치 확인])

### 9. 보완점
| # | 대상 스킬 | 보완 내용 | 적용 여부 |
|---|----------|----------|----------|
```
