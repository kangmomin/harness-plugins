> 이 문서는 `start-workflow` 스킬의 Phase 4(상태 파일·라이브 노트 생성)와 Phase 11(HTML 렌더링·최종 보고·보완점 적용)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}`, `{REPORT_DIR}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

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
| 5.1 | unit-test agent (Red) | 난이도 기준 | 난이도 기준 | PENDING |
| 5.2 | workflow-implementer | 난이도 기준 | 난이도 기준 | PENDING |
| 6 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 7 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | component-reviewer/a11y-reviewer | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | workflow-pr/hard push | 난이도 기준 | 난이도 기준 | PENDING |
| 10 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 11 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 5.1: 테스트 우선 (Red)
- Phase 5.2: 구현 (Green)
- Phase 6: 빌드/타입 체크
- Phase 7: 품질 루프
- Phase 8: 컴포넌트/접근성 리뷰
- Phase 9: PR / Push
- Phase 10: 성찰
- Phase 11: 최종 보고

## Acceptance Criteria
[Spec의 정상 흐름 표(`AC-nn`)를 그대로 복사. 없으면 `없음`. Phase 5.1 테스트 근거의 일부다]

## Edge Cases
[Spec의 엣지 케이스 표를 **ID·참조 구현 열까지 그대로** 복사. Phase 7.7 Diff 판정의 기준이므로 ID를 생략하거나 다시 매기지 않는다]

## Test Baseline
[Phase 4에서 수집. TDD SKIP 시 사유만 기록 — 예: `SKIPPED:NO_TEST_COMMAND`]

- 커밋: {SHA}   |   수집 Phase: 4 (자율 실행 진입 전)   |   **불변 — 이후 갱신하지 않는다**

| suite | 명령 | 러너 완주 | 통과 | 실패 | 실패 목록 (식별자 :: 정규화 시그니처) |
|-------|------|----------|------|------|--------------------------------------|
| unit | {testCommand} | Y | 88 | 1 | `ProductList > 빈 목록` :: `unable to find role=list` |

**Tombstone** (Spec이 승인한 테스트 이름 변경·삭제만 기록):
- `{구 식별자}` → `{신 식별자}` 또는 `삭제({근거})`

## TDD Test Map
[Phase 5.1에서 기록. Phase 7 회귀 대조와 Phase 11 보고서의 기준]
> **Phase 7.7 read-back 에이전트에 이 표를 전달하지 않는다** — Spec 역추론으로 격리가 무너진다.

| Spec ID | 테스트 | 파일 | Red | Green |
|---------|--------|------|-----|-------|
| AC-01 | 목록 렌더 | ProductList.test.tsx:12 | red_assertion | PASS |
| EC-01 | 빈 목록 EmptyState | ProductList.test.tsx:40 | already_satisfied | PASS |

## Plan
[확정된 Plan 전문 그대로 복사]

## Config
[.claude/fe-harness.local.md 주요 설정]

## Plan Verification Log
[Phase 3.3 검증 루프의 Iteration Diff Log]

## Readback Diff
[Phase 7.7 결과. Phase 7.7 실행 전에는 `미실행`]

## Phase Results
[Phase 완료 시 결과 append]
```

## Phase 4: Implementation Notes 라이브 파일 초기화

상태 파일과 별개로 `{IMPL_NOTES}`를 Write tool로 생성한다. 기존 파일이 있으면 덮어쓴다.

```markdown
# Implementation Notes — {작업 요약}

> 자율 실행 중 발생한 판단·편차·트레이드오프·미결 질문이 실시간으로 누적됩니다.
> 유저는 언제든 이 파일을 열어 비동기로 피드백할 수 있으며, Phase 11에서 HTML로 일괄 렌더링됩니다.

## 설계 결정
<!-- "- {Phase} | {file:line 또는 범위} — 선택: {택1} (대안: {택2}) — 근거: {1~2줄}" -->

## 편차
<!-- "- {Phase} | {file:line 또는 범위} — Spec: {원래 기대 동작} → 실제: {바뀐 동작} — 사유: {1~2줄}" — [Assumption] 보고와 1:1 대응 -->

## 트레이드오프
<!-- "- {Phase} | {결정} — 채택안: {A} / 기각안: {B,C} — 이유: {1~2줄}" -->

## 미결 질문
<!-- "- [ ] {Phase} | {질문} — 영향: {핵심 동작/주변 영향/판단 보류}" -->
```

> 4개 섹션 헤더(`## 설계 결정`, `## 편차`, `## 트레이드오프`, `## 미결 질문`)는 정확히 이 형태로 유지한다. Phase 11 HTML 렌더링이 헤더 텍스트로 섹션을 식별한다.

## Phase 11: Implementation Notes HTML 렌더링

보고서 작성 직전, 라이브 노트를 HTML 산출물로 변환한다.

1. **출력 디렉토리 보장**: `mkdir -p {REPORT_DIR}`
2. **출력 경로 결정**: `{REPORT_DIR}/{YYYYMMDD}-{task-name-kebab}-impl-notes.html`
   - `YYYYMMDD`: 현재 날짜 (Bash `date +%Y%m%d`)
   - `task-name-kebab`: Phase 4 브랜치명 또는 Spec 제목을 kebab-case로 변환
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
<div class="meta">생성: {ISO timestamp} · 브랜치: {branch} · 워크플로우: fe-harness:start-workflow</div>
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

4. **결과 경로를 메모**: Phase 11 보고서의 `Implementation Notes` 섹션에 절대 경로를 명시.

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
| AC-01 | [정상 흐름] | [대응] | PASS | 일치 |
| EC-01 | [케이스] | [대응] | PASS | 일치 |
| EC-02 | [케이스] | [대응] | deferred_e2e | A 검증 누락 |

- `테스트` 열: Phase 5.1 TDD Test Map의 Green 결과 또는 진단 분류. TDD SKIP이면 `-`
- `Read-back` 열: Phase 7.7 Diff 유형(A~E) 또는 `일치`. Phase 7.7이 SKIP이면 `-`

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| test | N | M |
| scope-review | N | M |
| lint | N | M |

- **테스트 판정**: [PASS/WARN/FAIL] — regression [n]건 / new_red [n]건 / flaky [n]건 / pre_existing [n]건(범위 밖)
- **Read-back 판정**: [PASS/WARN/FAIL] — A [n]건 / C [n]건 / E [n]건 (소스: 테스트 파일 / 테스트 리포트 / 구현 코드)

### 4.1 TDD 미해결 항목 (유저 결정 필요)
> TDD가 SKIP이거나 미해결 항목이 없으면 "없음"으로 적고 이 섹션을 비운다.

| 유형 | 항목 | 상세 | 필요한 결정 |
|------|------|------|------------|
| `BLOCKED:TEST_NOT_GREEN` | 품질 루프 3회 후에도 테스트 미통과 | [실패 목록] | 추가 수정 / 범위 제외 |
| `BLOCKED:NO_VALID_RED` | 유효 Red를 만들지 못함 | [사유] | 테스트 재작성 / TDD 없이 유지 |
| `[TestConflict]` | Spec 조항이 모호해 판정 보류 | [테스트 ↔ 조항] | Spec 확정 |
| `[Breaking]` | 기존 테스트의 기대 동작을 변경함 | [테스트명, 변경 내용] | 호환성 검토 |
| `cannot_compile` | 3회 시도 후 되돌린 테스트 | [Spec ID] | 수동 작성 / 범위 제외 |

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점 (프로젝트 오버라이드로 반영)
| # | 대상 스킬/에이전트 | 보완 내용 | 저장 경로 | 적용 여부 |
|---|----------|----------|----------|----------|
| 1 | /fe-harness:component | [내용] | `.claude/fe-harness/skills/component.md` | Y/N |

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

## Phase 11: 보완점 적용 상세

플러그인 원본(`fe-harness/skills/...` 아래 파일)은 **절대 수정하지 않는다**. 보완점 반영 경로는 두 가지다:

| 경로 | 대상 | 적용 범위 |
|------|------|----------|
| **로컬 오버라이드** | `.claude/fe-harness/{common,skills,agents}/...` | 현 프로젝트에만 |
| **커뮤니티 피드백 PR** | 플러그인 레포 `fe-harness/community-feedback/...` | 큐레이션 후 모든 사용자에게 |

상세 규약: 플러그인 루트 `OVERRIDES.md` + `community-feedback/README.md`.

> "보완점 반영 방식을 선택하세요:
> 1. **로컬에만 저장** (기본값) — `.claude/fe-harness/...` 에 append.
> 2. **로컬 저장 + 플러그인 레포에 PR** — `/common:submit-feedback` 호출. community-feedback 영역에 PR.
> 3. **건너뛰기**."

옵션 2 선택 시 각 보완점마다 `generality`(범용 / 특정 조건 / 프로젝트 한정)를 수집. `프로젝트 한정`은 PR 대상에서 제외.

### 옵션 2 세부 흐름

1. 로컬 오버라이드 append 먼저.
2. PR 후보 정리 후 `Skill tool`로 `/common:submit-feedback` 호출.
3. `SKIPPED:*` 반환 시 로컬 저장만 완료 상태로 종료, fallback 사유 보고.
4. 성공 시 PR URL을 최종 보고서에 포함.

### append 규칙

| 대상 | 경로 |
|------|------|
| 스킬 | `.claude/fe-harness/skills/{skill-name}.md` |
| 에이전트 | `.claude/fe-harness/agents/{agent-name}.md` |
| 공통 | `.claude/fe-harness/common.md` |

파일이 없으면 아래 형식으로 생성:

```markdown
---
scope: skill:{name}          # 또는 agent:{name} / common
applies-to: fe-harness@{버전}+
updated: {YYYY-MM-DD}
---

# Project Override: {대상}

## 보완점 (auto-appended {YYYY-MM-DD HH:mm})
- [보완 내용 1]
```

이미 있으면 기존 내용 뒤에 새 `## 보완점 (auto-appended ...)` 섹션을 append. 동일 내용이면 건너뜀.

추가 후 해당 파일 경로를 유저에게 보고한다:

> "프로젝트 오버라이드 업데이트 완료: [경로 목록]. 다음 워크플로우 실행 시 자동 로드. Git 커밋 권장."
