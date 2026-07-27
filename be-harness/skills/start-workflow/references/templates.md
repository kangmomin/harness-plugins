> 이 문서는 `start-workflow` 스킬의 Phase 5(상태 파일 생성)와 Phase 12(최종 보고·보완점 적용)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 템플릿 모음

## Phase 5: 상태 파일 템플릿

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
Phase 5 - 자율 실행 시작 (agent: orchestrator, model: 현재 세션, effort: 현재 세션)

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
| 1 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 2 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 3 | orchestrator | 현재 세션 | 현재 세션 | DONE |
| 4 | review agents + orchestrator | 난이도 기준 | 난이도 기준 | DONE |
| 5 | orchestrator | 현재 세션 | 현재 세션 | IN_PROGRESS |
| 6 | workflow-implementer/general-purpose | 난이도 기준 | 난이도 기준 | PENDING |
| 7 | orchestrator/build-fix agent | 난이도 기준 | 난이도 기준 | PENDING |
| 8 | quality agents | 난이도 기준 | 난이도 기준 | PENDING |
| 9 | doc-sync agent | 난이도 기준 | 난이도 기준 | PENDING |
| 10 | workflow-pr 또는 직접 push(--hard 모드) | 난이도 기준 | 난이도 기준 | PENDING |
| 11 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING |
| 12 | orchestrator | 현재 세션 | 현재 세션 | PENDING |

## Remaining Phases
- Phase 6: 구현
- Phase 7: 빌드 체크
- Phase 8: 품질 루프
- Phase 9: 문서 동기화
- Phase 10: PR / Push
- Phase 11: 성찰
- Phase 12: 최종 보고

## Execution Strategy
[sequential/parallel-slices]

## Edge Cases
[Spec의 엣지 케이스 표를 **ID·참조 구현 열까지 그대로** 복사. Phase 8.6 커버리지 대조와 Phase 8.8 Diff 판정의 기준이므로 ID를 생략하거나 다시 매기지 않는다]

## Plan
[확정된 Plan 전문 그대로 복사]

## Plan Verification Log
[Phase 4.3 검증 루프의 Iteration Diff Log]

## Readback Diff
[Phase 8.8 결과. Phase 8.8 실행 전에는 `미실행`]

## Phase Results
[Phase 완료 시 결과 append]
```

`parallel-slices`인 경우 아래를 추가한다:

```markdown
## Slices
[Plan에서 정의한 Slice 정보 그대로 복사]
```

## Phase 12: Workflow Report 템플릿

```markdown
## Workflow Report

### 1. 작업 요약
- **작업 유형**: [생성/수정/검토/디버깅]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 로직**: [요약]

### 3. 엣지 케이스 대응
| ID | 케이스 | 대응 방법 | E2E | Read-back |
|----|--------|----------|-----|-----------|
| EC-01 | [케이스] | [대응] | PASS | 일치 |
| EC-02 | [케이스] | [대응] | `UNCOVERED:{사유}` | A 검증 누락 |

- `E2E` 열: Phase 8.6 리포트의 해당 ID 판정. 미실행이면 `-`
- `Read-back` 열: Phase 8.8 Diff 유형(A~E) 또는 `일치`. Phase 8.8이 SKIP이면 `-`

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| e2e | N | M |
| scope-review | N | M |

**Read-back 판정**: [PASS/WARN/FAIL] — A [n]건 / C [n]건 / E [n]건 (소스: 테스트 파일 / E2E 리포트 / 구현 코드)

### 5. 문서 동기화
- API 문서 동기화: [Y/N/SKIPPED, 요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점 (프로젝트 오버라이드로 반영)
| # | 대상 스킬/에이전트 | 보완 내용 | 저장 경로 | 적용 여부 |
|---|----------|----------|----------|----------|
| 1 | /be-harness:request | [내용] | `.claude/be-harness/skills/request.md` | Y/N |
| 2 | be-harness:workflow-implementer | [내용] | `.claude/be-harness/agents/workflow-implementer.md` | Y/N |

### 8. Read-back Diff (유저 결정 필요)
> Phase 8.8이 SKIP이거나 판정이 PASS면 "없음"으로 적고 이 섹션을 비운다.

| 유형 | 항목 | Spec | 실제 보장 | 참조 구현 | 필요한 결정 |
|------|------|------|----------|----------|------------|
| C 기대값 불일치 | 중복 리뷰 (EC-05) | 400 | 409 | `order_handler.go:88` → 409 | 어느 쪽으로 통일할지 |
| A 검증 누락 | 일일 5회 제한 (EC-07) | 429 | 검증 없음 | - | 테스트 추가 / 범위 제외 |
| B Spec 밖 | body 길이 2000자 제한 | 없음 | 400 반환 | - | Spec에 반영 / 제거 |
| E 컨벤션 이탈 | `now == startAt` (EC-02) | 예정 | 예정 | `promotion.go:41` → 진행중 | 기존 컨벤션 따를지 |
| D 해석 불가 | `assert.Eventually` (`x_test.go:103`) | - | 불명 | - | 의도 확인 |
```

## Phase 12: 보완점 적용 상세

플러그인 원본(`be-harness/skills/...` 아래 파일)은 **절대 수정하지 않는다**. 보완점 반영 경로는 두 가지다:

| 경로 | 대상 | 적용 범위 |
|------|------|----------|
| **로컬 오버라이드** | `.claude/be-harness/{common,skills,agents}/...` | 현 프로젝트에만 |
| **커뮤니티 피드백 PR** | 플러그인 레포 `be-harness/community-feedback/...` | 큐레이션 후 모든 사용자에게 |

상세 규약: 플러그인 루트 `OVERRIDES.md` + `community-feedback/README.md`.

> "보완점 반영 방식을 선택하세요:
> 1. **로컬에만 저장** (기본값) — `.claude/be-harness/...` 에 append. 이 프로젝트에만 적용.
> 2. **로컬 저장 + 플러그인 레포에 PR** — 로컬 저장 후 `/be-harness:submit-feedback` 호출로 community-feedback 영역에 PR 제출. 범용성 있는 피드백에 권장.
> 3. **건너뛰기** — 보고서만 출력하고 종료."

- 옵션 선택 후 각 보완점마다 Y/N 선택.
- 옵션 2 선택 시 각 보완점에 `generality` 필드(범용 / 특정 조건 / 프로젝트 한정)를 수집. `프로젝트 한정`은 로컬 저장만 하고 PR 대상에서 제외.

### 옵션 2 세부 흐름

1. 로컬 오버라이드에 append 먼저 수행 (옵션 1과 동일).
2. PR 제출 대상 후보(generality: 범용 / 특정 조건)를 정리.
3. `Skill tool`로 `/be-harness:submit-feedback`을 호출하며 후보 리스트 전달.
4. submit-feedback이 `SKIPPED:*` 반환 시(gh 미설치/미인증/네트워크 실패 등) 로컬 저장만 완료된 상태로 워크플로우 정상 종료, 유저에게 fallback 사유를 보고.
5. 성공 시 PR URL을 최종 보고서에 포함.

### append 규칙

| 대상 | 경로 |
|------|------|
| 스킬 | `.claude/be-harness/skills/{skill-name}.md` |
| 에이전트 | `.claude/be-harness/agents/{agent-name}.md` |
| 공통 (여러 스킬에 적용) | `.claude/be-harness/common.md` |

파일이 없으면 새로 생성하고 frontmatter를 헤더로 넣는다:

```markdown
---
scope: skill:{name}          # 또는 agent:{name} / common
applies-to: be-harness@{버전}+
updated: {YYYY-MM-DD}
---

# Project Override: {대상}

## 보완점 (auto-appended {YYYY-MM-DD HH:mm})
- [보완 내용 1]
- [보완 내용 2]
```

파일이 이미 있으면 기존 `## 보완점 (auto-appended ...)` 뒤에 새 섹션을 append (중복 판단은 내용 일치 여부로, 동일 내용이면 건너뜀).

추가 후 해당 파일 경로를 유저에게 보고한다:

> "프로젝트 오버라이드 업데이트 완료:
>  - `.claude/be-harness/skills/request.md` (+2줄)
>  - `.claude/be-harness/agents/workflow-implementer.md` (신규 생성)
> 다음 워크플로우 실행 시 자동으로 로드됩니다. Git에 커밋을 권장합니다."
