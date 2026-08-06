---
name: simplify-loop
description: "변경 코드의 단순화 후보를 4관점 리뷰 Workflow 루프로 수렴할 때까지 반복 적용한다 (최대 10회, Workflow tool 미지원 시 빌트인 /simplify 반복 폴백). 구현 직후 코드 단순화 정리, '심플리파이 돌려줘', '코드 간소화' 요청 시 사용. start-workflow 품질 루프에서 자동 호출됨."
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/simplify-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Simplify Loop (Workflow 기반)

변경된 코드에서 동작 보존 단순화 후보를 찾아, 4관점(Correctness/Readability/Performance/Stability) 리뷰 → 만장일치 시 Devil's Advocate → Arbiter 판정 → 적용을 **수렴할 때까지 반복**한다. 루프 제어(반복·수렴·상한·분기)는 Workflow tool의 결정적 script 코드가 수행한다.

**플레이스홀더** (본 스킬의 유일한 기본값 정의처 — script는 in-script 기본값을 두지 않는다):

- `{MAX_ITER}` = 10
- `{CANDIDATE_CAP}` = 8
- `{RETRY_LIMIT}` = 1

## Flags

| 플래그 | 효과 |
|--------|------|
| `--dry-run` | 스캔 1회만 수행하고 후보 목록을 보고 (파일 수정 없음, Workflow 불필요). 호출 컨텍스트가 "dry-run 관점"을 지시하는 경우(예: start-workflow 품질 루프의 병렬 스캔 배치)도 이 플래그와 동일하게 해석한다 |
| `--max-iter N` | `{MAX_ITER}` 재정의. N이 양의 정수가 아니면 기본값 유지. 레거시 폴백 경로에도 동일 적용 |

## 전제 조건

- git 저장소 안에서 실행되어야 한다.
- Workflow tool이 있으면 1순위 경로로 실행된다. 없어도 폴백 경로로 동작한다 (Phase 3).

## Phase 1: 범위 판별 (Bash로 직접 수행)

1. `git status --porcelain`이 비어있지 않으면(dirty) → `{DIFF_CMD}` = `git diff HEAD`
2. clean이면 기본 브랜치를 `origin/main` → `main` 순으로 탐색해 `{DIFF_CMD}` = `git diff $(git merge-base {기본브랜치} HEAD)` — **base 대비 작업 트리 diff다. `base..HEAD` 커밋 범위를 쓰지 않는다** (루프가 적용한 변경이 이후 스캔에 반영되어야 다회 패스가 성립).
3. 기본 브랜치 탐색 실패(detached HEAD, shallow clone 등):
   - 대화형: 번호 선택지 제시 — (1) 비교 기준 ref 직접 지정 → 지정 diff로 진행 (2) 중단 → `SKIPPED:BASE_REF_UNRESOLVED` 보고 후 종료
   - 비대화형(서브에이전트): 질문 없이 즉시 `SKIPPED:BASE_REF_UNRESOLVED` 반환 (사유를 상위에 전달)
4. `{DIFF_CMD}` 결과가 비어있으면 → `SKIPPED:NO_CHANGES` 즉시 종료 (Workflow 미호출). 단 dry-run 모드에서는 SKIPPED여도 `후보: 0건` 라인을 병기한다.

`{DIFF_CMD}`는 **범위 식별 전용**이다 — 후보의 current 스니펫은 스캔 에이전트가 작업 트리의 실제 파일을 Read해 추출한다.

## Phase 2: 모드 분기 (dry-run)

dry-run이면: 같은 폴더의 `references/workflow-script.md`를 MUST Read하고, script 내 `SCAN_PROMPT` const를 **그대로** 사용해 스캔을 1회 수행한다 (seen은 빈 목록, `{DIFF_CMD}`·`{CANDIDATE_CAP}` 대입). 결과 JSON을 아래 형식으로 보고하고 종료한다. **파일을 수정하지 않는다.**

```
후보: {N}건
- {file}:{line} — {summary} / 제안: {proposed 한 줄 요약} / 근거: {rationale}
```

## Phase 3: 실행 경로 결정 (graceful degradation)

| 순위 | 감지 | 절차 | 사용자 고지 |
|------|------|------|------------|
| 1 | 세션 도구 목록에 Workflow tool 존재 | Phase 4 진행 | (없음) |
| 2 | Workflow 부재 + Skill tool로 빌트인 `/simplify` 호출 가능 | 레거시 절차 (아래) | "Workflow tool 미지원 환경 — 레거시 /simplify 반복 모드로 진행합니다 (루프 제어가 지시문 기반으로 동작)" |
| 3 | Workflow·빌트인 /simplify 모두 불가 (서브에이전트 등) | 직접 수행 절차 (아래) | "Workflow/빌트인 simplify 모두 불가한 컨텍스트 — 직접 수행 모드(단일 패스)로 진행합니다 (관점 독립성과 Devil's Advocate 단계가 보장되지 않음)" |

**2순위 — 레거시 절차** (v1 동작 보존):

1. 빌트인 `/simplify`를 실행한다 (`skill: "simplify"` — 본 플러그인 스킬 아님).
2. 코드 수정이 적용되면 iteration +1 후 1로 돌아간다. 수정 없음(Applied Changes: 없음 / 전원 KEEP)이면 종료.
3. `{MAX_ITER}`회 도달 시 수정 유무와 무관하게 종료.

**3순위 — 직접 수행 절차** (단일 패스, 반복 없음 — 반복은 상위 호출자의 루프가 담당. 예: start-workflow 품질 루프가 자체 상한으로 반복):

1. `references/workflow-script.md`의 `SCAN_PROMPT` 기준으로 후보를 도출한다 (`{CANDIDATE_CAP}` 상한).
2. 후보마다 4관점(Correctness/Readability/Performance/Stability) 판정을 단일 컨텍스트에서 순차 수행한다. **확신 없으면 KEEP** (보수 기준 — DA/Arbiter 부재 보완).
3. 4관점 모두 CHANGE인 항목만 적용한다 (current 스니펫 정확 일치 확인 후 외과적 수정).
4. 2/2 분할·확신 부족 항목은 "미적용 보류 목록"으로 상위에 반환한다 (질문하지 않는다).

## Phase 4: Workflow 실행

1. 같은 폴더의 `references/workflow-script.md`를 MUST Read한다.
2. script 코드 블록 전문을 Workflow tool `script` 파라미터로, args를 다음과 같이 전달한다:
   `args = { "diffCommand": "{DIFF_CMD}", "maxIterations": {MAX_ITER}, "candidateCap": {CANDIDATE_CAP}, "retryLimit": {RETRY_LIMIT} }`
3. 반환 JSON을 Phase 6에서 보고한다.

## Phase 5: Workflow 실행 실패 처리

Workflow **호출 자체**가 오류/중단으로 끝난 경우(스크립트 런타임 오류, 사용자 kill, 반환값 없음 — tool 부재와 별개 분기):

1. `git diff`로 이미 적용된 변경을 표면화해 보고한다.
2. 번호 선택지를 제시한다:
   - (1) `resumeFromRunId`로 재개 — **크래시 이후 작업 트리를 수정하지 않은 경우에만 제시**. 재개 후 보고서의 STALE 항목에는 "이미 적용되었을 수 있음 — git diff와 대조" 표기
   - (2) 현 상태 보고 후 종료 → 부분 적용 목록 포함 보고
   - (3) 잔여 범위만 레거시/직접 수행 폴백 → 이미 적용된 변경을 제외하고 진행
3. **부분 실행 후 자동 레거시 폴백 금지** (이중 적용 방지).

## Phase 6: 결과 보고

반환 JSON을 아래 출력 형식으로 렌더한다.

- `총 수정 횟수` 매핑: Workflow = `applied.length` / 레거시 = /simplify Applied Changes 누적 / 직접 수행 = 적용 항목 수
- **`failed[]` 또는 `holds[]`가 비어있지 않으면 status가 DONE이어도 경고 섹션을 반드시 포함한다.**
- status=FAIL + "적용 내역 미확인" note면 Phase 5의 1번 절차(git diff 표면화)를 수행한다.
- `holds[]`는 모든 경로에서 "미적용 보류 목록"으로 보고서에 포함한다. **자동 적용 절대 금지** (무응답 = 미적용이 안전 기본값). 대화형 컨텍스트에서만 이어서 선택지 제시:
  - (1) n번 보류 항목 적용 → 현재 스니펫 재확인 후 Edit로 적용, 결과를 보고서에 추가
  - (2) 전체 미적용 유지 (기본값) → 종료
  - 비대화형(서브에이전트)에서는 선택지 없이 목록만 상위 반환.
- `BLOCKED:*` 상태별 선택지는 아래 종료조건 표를 따른다.

## 종료조건 (Workflow 경로 — script가 코드로 강제)

| 조건 | 결과 |
|------|------|
| 스캔 성공 + 필터 후 신규 후보 0건 && 재처리 대기 소진 (REVIEW_INCOMPLETE 미해당 시) | DONE |
| `{MAX_ITER}` 소진 시점까지 수렴 미확인 | BLOCKED:MAX_ITERATIONS — (1) `--max-iter` 상향 재실행 (2) 현재까지 결과로 종료 |
| 승인 후보가 2회 연속 전부 적용 실패 (STALE 제외) | BLOCKED:NO_PROGRESS — (1) 실패 목록 수동 검토 후 재실행 (2) 실패 항목 제외하고 종료 |
| 적용 0건 + 보류 전원이 인프라 실패 사유(REVIEWER/ARBITER_FAILURE, MISSING_VERDICT) | BLOCKED:REVIEW_INCOMPLETE — (1) 재실행 (2) 레거시/직접 수행 폴백 (3) 종료 |
| Phase 1에서 diff 비어있음 | SKIPPED:NO_CHANGES |
| 기준 ref 미해결 | SKIPPED:BASE_REF_UNRESOLVED |
| Scan agent 재시도 후에도 null, 또는 화해 agent null | FAIL — "적용 내역 미확인" note 시 git diff 수동 검토 안내 |

## 출력 형식

```
Simplify Loop 완료
- 총 iteration: {N}회
- 총 수정 횟수: {M}회
- 상태: {status}

## Simplify Review Report
| # | 파일 | 요약 | Correctness | Readability | Performance | Stability | 판정 |
|---|------|------|------------|-------------|-------------|-----------|------|
| {id} | {file}:{line} | {summary} | {V(C)} | {V(C)} | {V(C)} | {V(C)} | {decision} |

### Devil's Advocate / Arbiter (만장일치 후보만)
- {id}: 반론 강도 {strength} → Arbiter {verdict} — {reasoning 요약}

### 미적용 보류 목록 (holds)
- {id} {file}:{line} — {summary} / 사유: {reason}

### 경고 (failed/holds 존재 시 필수)
- {실패·보류 요약 및 후속 안내}
```

dry-run 모드의 출력은 Phase 2의 `후보: {N}건` 형식을 따른다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 수렴 종료 (신규 후보 없음) |
| `BLOCKED:MAX_ITERATIONS` | 상한 소진 시점까지 수렴 미확인 |
| `BLOCKED:NO_PROGRESS` | 승인 후보 2회 연속 전부 적용 실패 |
| `BLOCKED:REVIEW_INCOMPLETE` | 인프라 실패로 리뷰 미완결 (적용 0건) |
| `SKIPPED:NO_CHANGES` | 변경 코드 없음 |
| `SKIPPED:BASE_REF_UNRESOLVED` | 비교 기준 ref 미해결 |
| `FAIL` | 스캔/화해 에이전트 실패 |

## References

> Phase 2(dry-run)와 Phase 4 진입 시 MUST: 같은 폴더의 `references/workflow-script.md`를 Read하고 script 전문·`SCAN_PROMPT`·args 명세를 사용한다.
