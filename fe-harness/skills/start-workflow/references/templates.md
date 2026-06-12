> 이 문서는 `start-workflow` 스킬의 Phase 4(상태 파일 생성)와 Phase 11(최종 보고·보완점 적용)에서 로드된다. 단독 실행 금지.
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
[.claude/fe-harness.local.md 주요 설정]

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

### 7. 보완점 (프로젝트 오버라이드로 반영)
| # | 대상 스킬/에이전트 | 보완 내용 | 저장 경로 | 적용 여부 |
|---|----------|----------|----------|----------|
| 1 | /fe-harness:component | [내용] | `.claude/fe-harness/skills/component.md` | Y/N |
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
> 2. **로컬 저장 + 플러그인 레포에 PR** — `/fe-harness:submit-feedback` 호출. community-feedback 영역에 PR.
> 3. **건너뛰기**."

옵션 2 선택 시 각 보완점마다 `generality`(범용 / 특정 조건 / 프로젝트 한정)를 수집. `프로젝트 한정`은 PR 대상에서 제외.

### 옵션 2 세부 흐름

1. 로컬 오버라이드 append 먼저.
2. PR 후보 정리 후 `Skill tool`로 `/fe-harness:submit-feedback` 호출.
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
