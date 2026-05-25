---
name: e2e-test-loop-mm
description: "E2E 테스트 → 이슈 수정 → 재테스트 반복. 모든 테스트가 통과할 때까지 루프한다. (최대 5회)"
user-invocable: true
---

## Prerequisites

e2e-test와 동일한 환경이 필요하다. 세팅 확인: `/minmos-harness:e2e-test-mm --doctor`

### `--init`

`$ARGUMENTS`가 `--init`이면 `/minmos-harness:e2e-test-mm --init`을 실행하고 종료한다.

### `--doctor`

`$ARGUMENTS`가 `--doctor`이면 `/minmos-harness:e2e-test-mm --doctor`를 실행하고 종료한다.

### 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--init` | | 초기 세팅 후 종료 |
| `--doctor` | | 상태 진단 후 종료 |
| `--skip-doctor` | `-sd` | 실행 전 자동 doctor 점검을 건너뜀 |

---

/minmos-harness:e2e-test-mm 를 실행하고, 발견된 이슈를 수정한 뒤 재테스트하는 과정을 반복해:

## 절차

### 0. Pre-flight Probe (Fast SKIP Gate)

`$ARGUMENTS`에 `--skip-doctor` 또는 `-sd`가 **없으면**, 루프 진입 전 빠른 환경 probe를 실행한다.
**환경 부재가 확정되면 루프를 한 번도 돌지 않고 즉시 `SKIPPED`를 반환한다** — 실패 후 판정이 아니라, 진입 게이트에서 끊어낸다.

**Probe 항목 (e2e-test-mm Step 0과 동일):**
- `secret/.env` 존재 → 없으면 `[SKIPPED:ENV_MISSING]`
- PostgreSQL MCP 연결 → `SELECT 1` 실패 또는 tool 미사용이면 `[SKIPPED:POSTGRES_MCP_UNAVAILABLE]`
- DB 호스트 로컬 전용 → 위반이면 `[SKIPPED:REMOTE_DB_BLOCKED]` (화이트리스트 승인 없으면)

**MCP 판정 원칙**: `.mcp.json` 없음만으로 MCP를 MISSING 처리하지 않는다. OpenCode 등 다른 클라이언트 설정으로 MCP가 연결되어 있을 수 있으므로 실제 PostgreSQL MCP 호출 결과를 기준으로 판정한다.

**처리 규칙:**
- 모두 OK → Step 0.5로 진행
- 하나라도 FAIL → **루프 진입 없이** 즉시 아래 형식으로 종료 (리포트 파일 생성·doc-gen 렌더링 없음):
  ```
  ## E2E Test Loop — SKIPPED
  사유: [SKIPPED:{REASON}]
  누락 항목: {항목}
  복구 방법: `/minmos-harness:e2e-test-mm --init`
  ```
- `--skip-doctor` / `-sd` 지정 시 → probe를 건너뛰고 바로 Step 0.5로 진행 (사용자 책임)

### 0.5. E2E 실행 리포트 초기화

> Probe를 통과해 **실제 루프에 진입하는 경우에만** 수행한다. `--init` / `--doctor` 분기, Step 0 SKIP 종료 경로에서는 리포트 파일을 만들지 않는다.

루프 동안 수행하는 모든 테스트 케이스의 요청 데이터·기대·실제·판정과 실패→수정 내역을 `/tmp/e2e-run-report.md`에 누적한다. 루프 종료 후 이 파일이 Step 6에서 `/doc-gen --html`의 입력이 된다.

Write tool로 `/tmp/e2e-run-report.md`를 생성한다(기존 파일이 있으면 덮어쓴다). doc-gen이 그대로 렌더링할 수 있도록 아래 헤더로 초기화한다:

```markdown
# E2E 테스트 실행 리포트 — {브랜치명 또는 작업 요약}

> 생성: {ISO timestamp}
> E2E 메인 플로우: {제공된 메인 플로우 전문 또는 "자동 도출 (git diff 기반)"}

## 테스트 대상 엔드포인트
<!-- Step 1 첫 iteration에서 e2e-test-mm가 도출한 엔드포인트 목록을 1회 채운다 -->

## Iteration 기록
<!-- 매 iteration 결과를 아래로 append -->
```

**E2E 메인 플로우 출처 (단일 출처 원칙)**: 호출 컨텍스트(상위 워크플로우 상태 파일 `/tmp/workflow-state.md`의 `## E2E 메인 플로우` 섹션, 또는 사용자 대화)에 메인 플로우가 제공되면 그 텍스트를 **그대로** 헤더에 옮겨 적는다 — 재해석·재가공·요약하지 않는다. 제공되지 않았으면 `자동 도출 (git diff 기반)`으로 기록한다.

**케이스 블록 형식** — Step 1에서 매 테스트 케이스를 `## Iteration 기록` 아래에 이 형식으로 append 한다:

```markdown
### Iteration {N}

#### {분류} — {케이스명}
- 요청: `{METHOD} {PATH}` · body: `{request body 전문, 없으면 "(없음)"}`
- 기대: {기대 status / 응답}
- 실제: {실제 status / 응답 요약}
- 판정: ✅ 통과 / ❌ 실패
```

> `{분류}`는 `Happy Path` / `Validation` / `Edge Case` / `인증·권한` / `Status 정합성` 중 하나. gRPC는 status를 gRPC code로 표기한다. `### Iteration {N}` 헤더는 iteration당 1회만 적는다.

**실패→수정 블록 형식** — Step 3에서 실패한 케이스마다 해당 케이스 블록 끝에 이 형식으로 append 한다:

```markdown
**실패 → 수정 ({케이스명})**
- 실패 원인: {root cause}
- 수정: {file:line — 변경 요약}
- 재빌드/재시작: 예 / 아니오
```

**최종 요약 블록 형식** — Step 6에서 리포트 하단에 1회 append 한다:

```markdown
## 최종 요약
- 총 iteration: {N}회
- 총 테스트: {M}건 (통과 {X} / 실패 {Y})
- 미해결 이슈: {목록 또는 "없음"}
```

> 누적 규칙: 모든 기록은 **append-only**. 이전 iteration 블록이나 이미 적힌 케이스 블록을 수정하지 않는다. 마크다운만 작성한다(HTML 직접 작성 금지 — Step 6 렌더링이 깨진다).

1. `/minmos-harness:e2e-test-mm` 를 실행한다.
   - 헤더의 E2E 메인 플로우가 `자동 도출 (git diff 기반)`이 아니면, 해당 플로우를 Happy Path 필수 시나리오로 포함하도록 e2e-test-mm에 전달한다.
   - 첫 iteration이면 e2e-test-mm가 도출한 엔드포인트 목록을 리포트의 `## 테스트 대상 엔드포인트` 섹션에 채운다.
   - 하위 스킬이 `[SKIPPED:*]`를 반환하면 루프를 추가 진행하지 않는다. 빈 리포트 파일을 삭제(`rm -f /tmp/e2e-run-report.md`)하고 동일 SKIP 사유로 "종료 시 출력"의 SKIPPED 형식으로 보고한다. **Step 6(HTML 렌더링)은 건너뛴다.**
   - 정상 실행되면, 이번 iteration의 **모든 테스트 케이스**(통과·실패 무관)를 Step 0.5의 "케이스 블록 형식"으로 `/tmp/e2e-run-report.md`의 `## Iteration 기록` 아래에 append 한다.
2. 결과를 확인한다:
   - **이슈 없음** (모든 테스트 통과, STATUS_MISMATCH 없음) → 루프를 종료하고 Step 6으로 진행한다.
   - **이슈 발견** → 3번으로 진행한다.
3. 발견된 이슈를 수정한다:
   - 코드 수정 후 서버를 재빌드/재시작한다.
   - 수정 내용을 기록한다.
   - 이번 iteration에서 **실패한 각 케이스**에 대해, Step 0.5의 "실패→수정 블록 형식"으로 `/tmp/e2e-run-report.md`의 해당 케이스 블록 끝에 append 한다.
4. iteration 카운트를 1 증가시키고 1번으로 돌아간다.
5. **최대 5회** iteration 후에는 미해결 이슈와 함께 루프를 종료하고 Step 6으로 진행한다.

### 6. E2E 리포트 HTML 렌더링 (정직한 자기 점검 형식 — v2)

루프가 종료되면(전체 통과로 탈출 / 5회 도달 무관) `/tmp/e2e-run-report.md`를 **정직한 자기 점검(self-check) v2 형식의 HTML**로 렌더링한다. v2의 핵심은 (1) verdict 5종 세분화, (2) **시도별 raw 기록(attempt block)** 강제, (3) "본 PR 코드 vs 검증 인프라" 결함 구분. 단순 결과 나열이 아니라, "아무 의심 없이 성공인가?"에 정직하게 답하는 보고서를 생성한다.

> **건너뛰는 경우**: Step 0 Probe SKIP, `--init`, `--doctor`, 또는 Step 1에서 e2e-test-mm가 `[SKIPPED:*]`를 반환해 **테스트가 한 번도 실행되지 않은 경우**. 렌더링할 내용이 없으므로 이 단계를 생략한다. (e2e-test-mm가 1회 이상 정상 실행됐다면 통과/실패와 무관하게 항상 렌더링한다.)

**원칙 — `/common:doc-gen` 호출 금지**: doc-gen은 PR/refactor designer 프롬프트가 강제되어 본 보고서의 의도(정직한 자기 점검, GAP 명시, verdict 다운그레이드)와 충돌한다. 본 Step은 doc-gen을 거치지 않고, 아래 자산 프롬프트를 직접 적용해 단일 standalone HTML을 작성한다.

1. 리포트 하단에 Step 0.5의 "최종 요약 블록 형식"으로 `## 최종 요약`을 append 한다.
2. 출력 디렉토리를 보장한다: `mkdir -p /workspace/work-log/claude`
3. 출력 경로를 결정한다: `/workspace/work-log/claude/{YYYYMMDD-HHMMSS}-{branch}-e2e-report.html`
   - `{YYYYMMDD-HHMMSS}`: `date +%Y%m%d-%H%M%S` (E2E 실행마다 별개 스냅샷이므로 시각까지 포함해 덮어쓰지 않는다)
   - `{branch}`: `git branch --show-current`의 슬래시(`/`)를 `-`로 치환. 브랜치를 못 구하면 `e2e`.
   - **파일명 컨벤션은 고정**: 자산 프롬프트가 `-api-test-cases.html`을 권장하더라도, start-workflow-mm Phase 5.3/9가 `*-e2e-report.html` 패턴에 의존하므로 본 컨벤션을 우선한다.
4. 자산 프롬프트 `${CLAUDE_PLUGIN_ROOT}/skills/e2e-test-loop-mm/assets/api-test-cases-prompt.md`를 Read 도구로 읽는다. 이 파일은 v2 "API 테스트 케이스 정리 문서 생성기" 프롬프트이며, 본 Step의 시스템 지시로 사용한다.
5. 자산 프롬프트의 지시를 그대로 따라, `/tmp/e2e-run-report.md`의 내용을 입력 데이터로 매핑해 단일 standalone HTML을 작성한다.

   **TC 그룹핑 원칙 (v2 attempt 시퀀스 구성의 핵심)**: 자산 프롬프트는 케이스마다 1차~N차 attempt 시퀀스를 요구한다. e2e-run-report.md는 iteration별로 케이스 블록이 흩어져 있으므로, **`{분류} + {케이스명}` 동일성**으로 묶어 iteration 순으로 정렬해 하나의 TC로 통합한다. TC ID는 케이스 최초 등장 iteration의 등장 순으로 `TC-01`, `TC-02`...

   **입력 매핑 표**:

   | 자산 프롬프트가 요구하는 입력 | `/tmp/e2e-run-report.md`에서의 출처 |
   |--|--|
   | TC id / title | `{분류} + {케이스명}`으로 그룹핑한 단위. id는 그룹 순서대로 `TC-01...`, title은 `{분류} — {케이스명}` |
   | scenario | 분류·케이스명·메서드/경로에서 1~3줄로 도출 (예: "Validation 케이스. POST /products에 status_code=99 전송 시 400 기대") |
   | attempt 시퀀스 (1차, 2차, ...) | 같은 그룹에 속한 케이스 블록을 iteration 오름차순으로 나열. 각 attempt의 raw call은 `- 요청:` 줄, raw response는 `- 실제:` 줄. attempt tag는 `- 판정:` ✅→PASS, ❌→FAIL (단, 마지막 attempt가 아닌 PASS는 통상 없음). |
   | attempt cause (한 줄) | 직후의 `**실패 → 수정**` 블록 `- 실패 원인:` 줄. 없으면 `- 실제:`에서 한 줄 추출. |
   | attempt fix | 직후의 `**실패 → 수정**` 블록 `- 수정:` 줄. 마지막 PASS attempt에는 fix 없음. |
   | caller-verdict 산출 | 그룹 내 attempt 수 / 최종 결과로 계산:<br>• 1개 attempt + PASS → **CLEAN PASS**<br>• N개 attempt + 마지막 PASS → **PASS (after N-1 fixes)**<br>• 모든 attempt FAIL → **FAIL**<br>• 통과지만 응답이 본 PR 변경과 무관 → **INCONCLUSIVE** (생성기 판단)<br>• 일부 입력만 커버 → **PARTIAL** |
   | 본 PR vs 검증 인프라 구분 | `**실패 → 수정**`의 `- 수정:` 줄에서 변경 파일/내용으로 추론:<br>• 테스트 코드·expected·mock·환경변수·publisher 헬퍼·DSN 수정 → **A. "본 PR 코드는 매 시도 정확, 검증 인프라 결함"**<br>• 본 PR 변경 영역(handler/usecase/repository 등)의 코드 수정 → **B. "본 PR 코드 결함이 N차에 드러남"**<br>판단이 모호하면 fix 줄을 callout으로 인용하고 추론 근거 표기. |
   | 변경 대상 요약 | 헤더의 `# E2E 테스트 실행 리포트 — {브랜치명/작업 요약}` 및 `> E2E 메인 플로우:` 줄 |
   | 알려진 GAP / 한계 | `## 최종 요약`의 `미해결 이슈` + 미해결로 남은 FAIL 케이스 + `## 테스트 대상 엔드포인트`에 있으나 한 번도 호출되지 않은 엔드포인트 |
   | 부수 관찰 | 명시 항목이 없으면 "부수 관찰 없음" 카드 1장 출력. 임의 추측 금지. |
   | 이전 단순화 문서 (정정 섹션 트리거) | 호출 컨텍스트(상위 워크플로우 / 사용자 지시)에 명시된 경우에만 정정 섹션 생성. 자동 탐색 금지. |

6. 자산 프롬프트의 **VALIDATION RULES (1~8)** 를 반드시 enforce한다. 특히:
   - **verdict 다운그레이드**: 응답이 본 PR 변경 유무와 무관하게 같다면 ✅ → **INCONCLUSIVE** 강등 + callout. 1차 시도 통과가 아니면 ✅ → **PASS (after N fixes)** 강등.
   - **attempt block 의무**: CLEAN PASS만 attempt 1개, 그 외 모든 verdict는 1차~마지막까지 raw evidence를 모두 카드에 포함. 요약 금지.
   - **fix 명확성**: "수정함" 같은 vague 표현 금지. 실제 변경 파일/식별자가 드러나야 함.
   - **본 PR vs 검증 인프라 구분**: PASS (after N fixes) 결론에는 반드시 A/B 중 하나 명시.
   - **GAP 비어있지 않게**: 빈 경우 최소 1개 현실적 GAP 추론.
   - **정직한 결론 직답**: "아무런 의심 없이 성공인가?"에 한 줄 직답 의무.

7. Write tool로 3에서 결정한 출력 경로에 HTML을 저장한다.
8. 생성된 HTML 절대 경로를 "종료 시 출력"의 `E2E 리포트 HTML:` 줄에 기록한다. 렌더링이 실패하면 `미생성 ({사유})`로 적는다.

## 종료 시 출력

```
E2E Test Loop 완료
- 총 iteration: N회
- 발견된 이슈: M건
- 수정된 이슈: X건
- 미해결 이슈: Y건 (있으면 목록)
- E2E 리포트 HTML: {절대 경로}
```

> `E2E 리포트 HTML:` 줄은 **의무 출력**이다. 상위 워크플로우/오케스트레이터(start-workflow-mm Phase 5.3)가 이 경로를 **유일한 채널**로 전달받아 Phase 9 보고서에 참조한다. 서브 에이전트로 실행될 때도 이 줄이 stdout에 반드시 포함돼야 경로가 오케스트레이터까지 전파된다.

probe SKIP / 테스트 미실행인 경우 (`E2E 리포트 HTML:` 줄 없음):
```
E2E Test Loop — SKIPPED
- 사유: [SKIPPED:{REASON}]
- 총 iteration: 0회
```
