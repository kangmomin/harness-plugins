> 이 문서는 `start-workflow` 스킬의 Phase 4(상태 파일·라이브 노트 생성)와 Phase 11(최종 보고·md 아카이브·보완점 적용)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}`, `{REPORT_DIR}`, `{WORK_REPORT}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 템플릿 모음

## Phase 4: 상태 파일 템플릿

`RUN_ID`는 Pre-flight 결과를 사용한다. 신규 실행의 구현 직전에 `START_SHA`만 1회 수집하며, 재개 시 두 값과 기존 상태/노트를 보존한다:

```bash
START_SHA=$(git rev-parse HEAD 2>/dev/null || echo 없음)
```

Write tool로 `{STATE_FILE}`을 생성한다:

```markdown
# Workflow State

## Run
- CWD: {CWD}
- MODE: fe
- RUN_ID: {RUN_ID}
- RUN_DIR: {RUN_DIR}

## Flags
- MODE: fe
- HARD_MODE: {true|false}
- TDD: {true|false}
- REFLECT: {true|false}
- TIER: {light|standard}
- CODEX: {none|mix|max}
- CODEX_MODELS: {review={provider}/{model}@{effort},explore=…,judge=…,write=… | N/A} — 4슬롯 고정 순서·확정 effort(`-` = 키 생략), `CODEX: none`이면 `N/A` (`references/codex-mode.md` §2.1)
- RUN_ID: {RUN_ID}
- START_SHA: {START_SHA}

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]

## Difficulty
[N]/10

## Verification Tier
- 계산 티어: {light|standard} — A [a]/10, B [b]/10
- 최종 티어: {light|standard} ({사유: 해당 없음 | 금지 조건 {항목} | TDD off | --tier standard})
- 근거: {요소별 밴드 요약 + risk_facts.py 출력 요약}
- 시작 커밋: {START_SHA}
- 축소 항목: {3.2 1에이전트 / PLAN_MAX 2 / QL_MAX 2 / 7.2 SKIP / 7.4 smoke / 7.7 SKIP / 8 a11y만 | 없음}

| 시점 | 트리거 | 근거 | 조치 |
|------|--------|------|------|
[승격 발생 시 append — 예: `5.2 완료 직후` | `② 변경 소스 파일 5 > 3` | `A.tsx, B.tsx, …` | `standard 전환, 미재실행: 3.2`]

## Related E2E Specs
[Plan 3.1의 "관련 E2E spec 파일 경로 목록"을 그대로 복사. 없으면 `없음`. light의 `test-loop --smoke`가 이 목록만 실행한다 — 파일이 하나라도 없으면 test-loop이 전체 실행으로 폴백한다]

## Codex Runtime
- 상태: {active | fallback({global:{사유} | provider:{id}:{사유} | slot:{슬롯}:{사유}, …})} — 생성 시 `$CODEX_RUNTIME` 값 그대로 (`references/codex-mode.md` §7 직렬화). `CODEX: none`이면 `N/A`

| 호출 ID | 사용 종류 | 범위 | S0 | 핸들 |
|---------|----------|------|----|------|
[§5 쓰기 안전 `pending` 표 — Codex 쓰기 호출 dispatch 전에 행 기록, `VERIFIED`/종료 조건 도달 시 삭제. 재개 시 행이 남아 있으면 마지막 호출 사망으로 판정]

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
| 10 | workflow-reflection | 난이도 기준 | 난이도 기준 | PENDING (`--reflect` 미지정 시 SKIPPED:REFLECT_NOT_REQUESTED) |
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
[Phase 3.3 검증 루프의 Iteration Diff Log — Phase 4 ①에서 복사]

## Readback Diff
[Phase 7.7 결과. Phase 7.7 실행 전에는 `미실행`, light면 `SKIPPED:TIER_LIGHT`]

## Final Decisions
[Phase 11 ②~④에서 받은 유저 결정을 받는 즉시 append. 재개 시 기록된 항목은 다시 묻지 않는다]

| 항목 | 결정 | 시각 |
|------|------|------|

## Artifacts
- workflow-report: {아카이브 경로 | 미생성}

## Phase Results
[Phase 완료 시 아래 표에 행 append. `Status`는 상태 코드(7.2/7.4처럼 Phase Assignments에 개별 행이 없는 하위 단계도 여기에 기록).
`진단` 열은 발생 시에만 — `tier_escalated({트리거})` / `script_fallback({스크립트}:{사유})` / `codex_fallback({단계}:{사유})`, 없으면 `-`]

| Phase | Status | 결과 요약 | 진단 |
|-------|--------|----------|------|
```

`--reflect` 미지정 시(기본): 생성 시점에 Phase 10 행의 Status를 `SKIPPED:REFLECT_NOT_REQUESTED`로 기록하고, `Remaining Phases`에서 "Phase 10: 성찰"을 제외한다.
light 티어: `Phase Results`에 7.2·7.7 행을 `SKIPPED:TIER_LIGHT`로 미리 기록하지 않는다 — 승격으로 실행될 수 있으므로 해당 단계 도달 시점에 기록한다.

## Phase 4: Implementation Notes 라이브 파일 초기화

상태 파일과 별개로 `{IMPL_NOTES}`를 Write tool로 생성한다. 기존 파일이 있으면 덮어쓴다.

```markdown
# Implementation Notes — {작업 요약}

> 자율 실행 중 발생한 판단·편차·트레이드오프·미결 질문이 실시간으로 누적됩니다.
> 유저는 언제든 이 파일을 열어 비동기로 피드백할 수 있으며, Phase 11에서 Workflow Report 부록 C로 원문이 보존됩니다.

## 설계 결정
<!-- "- {Phase} | {file:line 또는 범위} — 선택: {택1} (대안: {택2}) — 근거: {1~2줄}" -->

## 편차
<!-- "- {Phase} | {file:line 또는 범위} — Spec: {원래 기대 동작} → 실제: {바뀐 동작} — 사유: {1~2줄}" — [Assumption] 보고와 1:1 대응 -->

## 트레이드오프
<!-- "- {Phase} | {결정} — 채택안: {A} / 기각안: {B,C} — 이유: {1~2줄}" -->

## 미결 질문
<!-- "- [ ] {Phase} | {질문} — 영향: {핵심 동작/주변 영향/판단 보류}" -->
```

> 4개 섹션 헤더(`## 설계 결정`, `## 편차`, `## 트레이드오프`, `## 미결 질문`)는 정확히 이 형태로 유지한다. Phase 11의 `workflow_archive.py`가 헤더 텍스트로 섹션을 검증하고, 오케스트레이터는 `## 미결 질문`만 읽어 보고서 상단에 표면화한다.

## Phase 11 실행 절차

> SKILL.md Phase 11의 "절차 요약" ①~⑤의 상세 규칙이다. 순서를 바꾸지 않는다.

1. **Workflow Report 초안 작성**: Phase 5~10 결과를 종합해 아래 템플릿(섹션 머리글 변경 금지)으로 `{WORK_REPORT}`를 Write tool로 작성하고, 최종 결정 반영 후 갱신한다. 최종 경로·파일명은 5의 스크립트가 정한다 — Claude는 `{REPORT_DIR}` 아래에 직접 쓰지 않는다.
   표 복제 금지: §2는 2~3줄 + "상세: 부록 A", §4의 단계별 건수는 "부록 B `Phase Results`"로 대신한다. §3·§4.1·§8은 유저 결정 근거이므로 그대로 채운다.
   `{IMPL_NOTES}`는 `## 미결 질문` 섹션만 읽는다 — 1건 이상이면 보고서 최상단에 "사용자 확인 필요" 블록을 삽입한다 (다른 섹션은 읽지 않는다. 원문은 부록 C로 보존된다).
   채팅에는 `{WORK_REPORT}` 경로 + §1 + 유저 결정이 필요한 항목(4.1, 8, 미결 질문, `[Assumption]`)만 출력한다. 보고서 전문을 채팅에 복제하지 않는다.
2. **TDD 미해결 항목 처리** (보고서 4.1 섹션이 비어있지 않을 때만): 자율 실행 중 이연된 `BLOCKED:*`·`[TestConflict]`·`[Breaking]`·`cannot_compile`을 각각 제시하고 결정을 받는다. Phase 5~7에서 유저 질문이 금지되어 이연된 항목들이므로 **여기가 첫 결정 지점**이다.
   - 결정에 따른 수정이 필요하면 적용한 뒤 5의 재검증·commit/push 절차를 따른다. 승인 전에는 수정하지 않는다. "이번 범위 외" 판단 항목은 보고서에 `보류`로 남긴다.
3. **Read-back Diff 처리** (Phase 7.7 판정이 `WARN`/`FAIL`일 때만): 보고서 8번 섹션의 각 항목을 유저에게 제시하고 결정을 받는다. 보완점 질문보다 **먼저** 처리한다.
   - 결정에 따른 코드/Spec 수정이 필요하면 적용한 뒤 5의 재검증·commit/push 절차를 따른다. 유저가 승인하기 전에는 수정하지 않는다 (Spec 외 변경 금지 원칙). "이번 범위 외" 항목은 `보류`로 남긴다.
4. **보완점 적용** (Phase 10이 `DONE`일 때만): 반영 방식을 질문한다: ① 로컬에만 저장 (기본) ② 로컬 저장 + `/common:submit-feedback`으로 PR ③ 건너뛰기. 적용 절차·append 규칙은 아래 "보완점 적용 상세"를 따른다. 플러그인 원본은 절대 수정하지 않는다.
   Phase 10이 `SKIPPED:*`면 이 단계를 건너뛰고 보고서 §6에 **실제 상태 코드**로 스킵 사유를 기입한다 (`REFLECT_NOT_REQUESTED`: "`--reflect`로 주기 실행 권장(워크플로우 5~10회마다 1회)").

   2~4의 각 결정은 받는 즉시 상태 파일 `## Final Decisions`에 한 줄 append한다 (항목 / 결정 / 시각). 컨텍스트 요약·재개 후에는 기록된 항목을 다시 묻지 않는다.
5. **재검증·반영 + 정리 + md 아카이브**: 먼저 `finalization.md`를 Read하여 승인 수정 → 관련 검증 → 기존 브랜치 commit/push → 보고서 갱신을 완료한다. 미해결 항목이 없을 때만 상태를 마감하고 아래 "md 아카이브"를 실행한다.
   기본은 상태 파일과 라이브 노트를 **보관**. 사용자가 정리를 요청한 경우에만 `rm -f {STATE_FILE} {IMPL_NOTES} {WORK_REPORT}`. 아카이브 산출물(`*-workflow-report.md`)은 자동 삭제하지 않는다.

## Phase 11: md 아카이브

`{WORK_REPORT}`(슬림 보고서)에 실행 요약·상태 파일 전문·Implementation Notes를 부록으로 붙여 `{REPORT_DIR}`에 md 1개로 영구 저장한다. Claude 토큰을 쓰지 않는 결정적 단계이므로 스크립트가 수행한다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/workflow_archive.py report \
  --src {WORK_REPORT} --state {STATE_FILE} --run-id {RUN_ID} --impl-notes {IMPL_NOTES} \
  --report-dir {REPORT_DIR} --task {task-name-kebab} --start-sha {START_SHA} \
  --require-headings "1. 작업 요약,2. 구현 내역,3. 엣지 케이스 대응,4. 품질 루프 결과,5. 컴포넌트/접근성 리뷰,6. 성찰,7. 보완점,8. Read-back Diff"
```

- `task-name-kebab`: Phase 4 브랜치명 또는 Spec 제목을 kebab-case로 (스크립트가 다시 슬러그화한다). `START_SHA`가 `없음`이면 `--start-sha`를 생략한다.
- 출력 파일: `{REPORT_DIR}/{YYYYMMDD}-{task}-{RUN_ID}-workflow-report.md` — frontmatter(`title / type: report / tags / status: active / created / updated` + 파싱 가능 시 `run_id / tier / escalated / regression_count / touched_paths`) + 보고서 본문 + `## 부록 A: 실행 요약` + `## 부록 B: 상태 파일 전문`(헤딩 1단계 강등) + `## 부록 C: Implementation Notes`(원문 verbatim). 같은 `RUN_ID`의 파일이 이미 있으면(재시도) 재생성하지 않고 그 경로를 출력한다.
- stdout 두 줄 `경로: …` / `상태: OK|DEGRADED({사유})`. `경로`를 `## Artifacts`의 `workflow-report`에 기록하고 채팅에 출력한다. `DEGRADED`면 파일은 생성된 것이므로 `Phase Results` 11행 진단에 `script_fallback(workflow_archive:{사유})`만 기록한다.
- **폴백** (exit ≠ 0 — python3 부재·인자 오류·쓰기 실패): 감지 = exit code → `{WORK_REPORT}`·`{STATE_FILE}`·`{IMPL_NOTES}`를 `cat`으로 이어붙여 `{REPORT_DIR}/{YYYYMMDD}-{task}-{RUN_ID}-workflow-report.md`로 직접 저장(frontmatter는 `title/type/tags/status/created/updated`만) → 고지: "md 아카이브 스크립트 실패({사유}) — 원문 3개를 수동 결합해 저장했습니다." 진단 `script_fallback(workflow_archive:exit {code})`.

## Phase 11: Workflow Report 템플릿

```markdown
## Workflow Report

### 1. 작업 요약
- **작업 유형**: [화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **검증 티어**: [light | standard | light → standard ({트리거}, 미재실행: 3.2)]
- **Codex 모드**: [none | mix | max] · 모델: [기본 | {CODEX_MODELS}]{ · runtime: fallback({항목}, …)}
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일 / 커밋**: [N]개 / [M]개 — 목록은 부록 A
- **핵심 컴포넌트**: [2~3줄 요약]

### 3. 엣지 케이스 대응
| ID | 케이스 | 대응 방법 | 테스트 | Read-back |
|----|--------|----------|--------|-----------|
| AC-01 | [정상 흐름] | [대응] | PASS | 일치 |
| EC-01 | [케이스] | [대응] | PASS | 일치 |
| EC-02 | [케이스] | [대응] | deferred_e2e | A 검증 누락 |

- `테스트` 열: Phase 5.1 TDD Test Map의 Green 결과 또는 진단 분류. TDD SKIP이면 `-`
- `Read-back` 열: Phase 7.7 Diff 유형(A~E) 또는 `일치`. Phase 7.7이 SKIP이면 `-`

### 4. 품질 루프 결과
- **루프**: [N]회 (상한 `{QL_MAX}`) / 수정 [M]건 — 단계별 건수·상태는 부록 B `Phase Results`
- **E2E 실행 수준**: [smoke | full | full(smoke 미적용: {사유}) | full-command | SKIPPED:{사유}]
- **테스트 판정**: [PASS/WARN/FAIL] — regression [n]건 / new_red [n]건 / flaky [n]건 / pre_existing [n]건(범위 밖)
- **Read-back 판정**: [PASS/WARN/FAIL | SKIPPED:TIER_LIGHT] — A [n]건 / C [n]건 / E [n]건 (소스: 테스트 파일 / 테스트 리포트 / 구현 코드)

### 4.1 TDD 미해결 항목 (유저 결정 필요)
> TDD가 SKIP이거나 미해결 항목이 없으면 "없음"으로 적고 이 섹션을 비운다.

| 유형 | 항목 | 상세 | 필요한 결정 |
|------|------|------|------------|
| `BLOCKED:TEST_NOT_GREEN` | 품질 루프 상한(`{QL_MAX}`회) 후에도 테스트 미통과 | [실패 목록] | 추가 수정 / 범위 제외 |
| `BLOCKED:NO_VALID_RED` | 유효 Red를 만들지 못함 | [사유] | 테스트 재작성 / TDD 없이 유지 |
| `[TestConflict]` | Spec 조항이 모호해 판정 보류 | [테스트 ↔ 조항] | Spec 확정 |
| `[Breaking]` | 기존 테스트의 기대 동작을 변경함 | [테스트명, 변경 내용] | 호환성 검토 |
| `cannot_compile` | 3회 시도 후 되돌린 테스트 | [Spec ID] | 수동 작성 / 범위 제외 |

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약 | SKIPPED:TIER_LIGHT]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과. Phase 10이 `SKIPPED:*`면 "성찰 생략(`{실제 상태 코드}`)" 한 줄만 기입하고 사유별 안내를 덧붙인다 —
`REFLECT_NOT_REQUESTED`: "`--reflect`로 주기 실행 권장(워크플로우 5~10회마다 1회)"]

### 7. 보완점 (프로젝트 오버라이드로 반영)
> Phase 10이 `SKIPPED:*`면 표 대신 "없음 (성찰 생략)"으로 적는다.

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
