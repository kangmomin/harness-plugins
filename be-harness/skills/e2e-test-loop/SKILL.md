---
name: e2e-test-loop
description: "E2E 테스트 → 이슈 수정 → 재테스트를 반복한다 (최대 5회). 종료 시 정직한 자기 점검 HTML 리포트를 생성한다. 기능 구현 후 'E2E 돌려줘', '테스트 통과할 때까지 고쳐줘' 요청 시 사용. start-workflow 품질 루프에서 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill
user-invocable: true
argument-hint: "[--skip-doctor]"
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/e2e-test-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# E2E Test Loop

`/be-harness:e2e-test` 를 실행하고, 실패가 있으면 수정한 뒤 다시 실행한다. 최대 5회 반복하고, 종료 시 실행 전체를 **정직한 자기 점검 HTML 리포트**로 남긴다.

**플레이스홀더 정의** (본문·assets 공통, 값 변경은 여기 한 곳만 수정):

- `{RUN_REPORT}` = `/tmp/e2e-run-report.md` (루프 중 누적하는 원시 기록)
- `{REPORT_DIR}` = profile의 `reportDir` (없으면 `.claude/harness-reports`)
- `{MAX_ITER}` = 5
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--skip-doctor` | `-sd` | 루프 진입 전 환경 probe를 건너뛴다 (사용자 책임) |

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

## Step 1: Pre-flight Probe (Fast SKIP Gate)

`--skip-doctor` / `-sd` 가 **없으면**, 루프 진입 전 빠른 환경 probe를 실행한다.
**환경 부재가 확정되면 루프를 한 번도 돌지 않고 즉시 `SKIPPED`를 반환한다** — 실패 후 판정이 아니라 진입 게이트에서 끊어낸다.

profile(`.claude/be-harness.local.md`)을 읽고 아래를 확인한다:

| 점검 항목 | 실패 시 |
|----------|--------|
| profile 존재 | `SKIPPED:NO_PROFILE` |
| `e2eEnabled: true` | `SKIPPED:DISABLED` |
| `serverUrl` 비어있지 않음 | `SKIPPED:NO_SERVER_URL` |
| `runServerCommand` 비어있지 않음 (또는 기존 서버가 `serverUrl`에 응답) | `SKIPPED:NO_SERVER` |

처리 규칙:
- 모두 OK → Step 2로 진행
- 하나라도 FAIL → **루프 진입 없이** 즉시 아래 형식으로 종료 (리포트 파일 생성·HTML 렌더링 없음):
  ```
  ## E2E Test Loop — SKIPPED
  사유: SKIPPED:{REASON}
  누락 항목: {항목}
  복구 방법: `/be-harness:init` 으로 profile 재설정 또는 `/be-harness:doctor` 로 진단
  ```

## Step 2: 실행 리포트 초기화

> Probe를 통과해 **실제 루프에 진입하는 경우에만** 수행한다. Step 1 SKIP 종료 경로에서는 리포트 파일을 만들지 않는다.

루프 동안 수행하는 모든 테스트 케이스의 요청 데이터·기대·실제·판정과 실패→수정 내역을 `{RUN_REPORT}`에 누적한다. 루프 종료 후 이 파일이 Step 4 HTML 렌더링의 입력이 된다.

Write tool로 `{RUN_REPORT}`를 생성한다(기존 파일이 있으면 덮어쓴다):

```markdown
# E2E 테스트 실행 리포트 — {브랜치명 또는 작업 요약}

> 생성: {ISO timestamp}
> E2E 메인 플로우: {제공된 메인 플로우 전문 또는 "자동 도출 (git diff 기반)"}

## 테스트 대상 엔드포인트
<!-- Step 3 첫 iteration에서 e2e-test가 도출한 엔드포인트 목록을 1회 채운다 -->

## Iteration 기록
<!-- 매 iteration 결과를 아래로 append -->
```

**E2E 메인 플로우 출처 (단일 출처 원칙)**: 호출 컨텍스트(상위 워크플로우 상태 파일의 `## E2E 메인 플로우` 섹션, 또는 사용자 대화)에 메인 플로우가 제공되면 그 텍스트를 **그대로** 헤더에 옮겨 적는다 — 재해석·재가공·요약하지 않는다. 제공되지 않았으면 `자동 도출 (git diff 기반)`으로 기록한다.

**케이스 블록 형식** — Step 3에서 매 테스트 케이스를 `## Iteration 기록` 아래에 이 형식으로 append 한다:

```markdown
### Iteration {N}

#### {분류} — {케이스명}
- 요청: `{METHOD} {PATH}` · body: `{request body 전문, 없으면 "(없음)"}`
- 기대: {기대 status / 응답}
- 실제: {실제 status / 응답 요약}
- 판정: ✅ 통과 / ❌ 실패
```

> `{분류}`는 `Happy Path` / `Validation` / `Edge Case` / `인증·권한` / `Status 정합성` 중 하나. `### Iteration {N}` 헤더는 iteration당 1회만 적는다.

**실패→수정 블록 형식** — Step 3의 수정 단계에서 실패한 케이스마다 해당 케이스 블록 끝에 이 형식으로 append 한다:

```markdown
**실패 → 수정 ({케이스명})**
- 실패 원인: {root cause}
- 수정: {file:line — 변경 요약}
- 재빌드/재시작: 예 / 아니오
```

**최종 요약 블록 형식** — Step 4에서 리포트 하단에 1회 append 한다:

```markdown
## 최종 요약
- 총 iteration: {N}회
- 총 테스트: {M}건 (통과 {X} / 실패 {Y})
- 미해결 이슈: {목록 또는 "없음"}
```

> 누적 규칙: 모든 기록은 **append-only**. 이전 iteration 블록이나 이미 적힌 케이스 블록을 수정하지 않는다. 마크다운만 작성한다(HTML 직접 작성 금지 — Step 4 렌더링이 깨진다).

## Step 3: 루프 (최대 {MAX_ITER}회)

1. `/be-harness:e2e-test` 를 실행한다.
   - 헤더의 E2E 메인 플로우가 `자동 도출 (git diff 기반)`이 아니면, 해당 플로우를 Happy Path 필수 시나리오로 포함하도록 e2e-test에 전달한다.
   - 첫 iteration이면 e2e-test가 도출한 엔드포인트 목록을 리포트의 `## 테스트 대상 엔드포인트` 섹션에 채운다.
   - 하위 스킬이 `SKIPPED:*`를 반환하면 루프를 추가 진행하지 않는다. 빈 리포트 파일을 삭제(`rm -f {RUN_REPORT}`)하고 동일 SKIP 사유로 보고한다. **Step 4(HTML 렌더링)는 건너뛴다.**
   - 정상 실행되면, 이번 iteration의 **모든 테스트 케이스**(통과·실패 무관)를 Step 2의 "케이스 블록 형식"으로 append 한다.
2. 결과를 확인한다:
   - **판정 `PASS`** (모든 시나리오 통과 + 미커버 0건) → 루프 종료 → Step 4
   - **판정 `WARN`** (실패 0건 + `UNCOVERED:{사유}` 1건 이상) → 루프 종료 → Step 4. 미커버는 검증 공백이지 구현 결함이 아니므로 수정 루프를 돌리지 않고, 사유를 리포트에 남긴 채 상위에 전달한다.
   - **판정 `FAIL`** → 3번으로 진행
3. 발견된 이슈를 수정한다. `general-purpose` 에이전트에 위임한다:
   ```
   아래 E2E 실패를 수정하세요. 프로젝트 루트: {CWD}.
   failures: {실패 목록 전체}
   - 원인 추적: 서버 로그 / 코드 흐름 / Spec 차이 중 무엇인지 먼저 특정하고 수정.
   - 파일 수정 후 {buildCommand} (비어있지 않으면) 로 빌드 통과 확인.
   - 서버를 재시작하지 마세요 (기존 서버 유지 — 루프가 관리합니다).
   - 수정 후 "수정: N건, 파일: [목록]" 형식으로 보고.
   ```
   - 수정 후 서버를 재빌드/재시작한다 (오케스트레이터가 수행).
   - 실패한 각 케이스에 대해 Step 2의 "실패→수정 블록 형식"으로 append 한다.
   - 커밋: `git add [수정 파일] && git commit -m "Fix: E2E 실패 수정 (반복 {iteration})"`
4. iteration 카운트를 1 증가시키고 1번으로 돌아간다.

| 종료 조건 | 결과 |
|----------|------|
| 판정 `PASS` | 루프 탈출 → Step 4 |
| 판정 `WARN` (미커버만) | 루프 탈출 → Step 4, 미커버 사유를 상위에 전달 |
| `e2e-test`가 `SKIPPED:*` 반환 | 루프 미진행, SKIPPED 그대로 보고 (Step 4 생략) |
| `{MAX_ITER}`회 도달, 이슈 잔존 | `BLOCKED:MAX_ITERATIONS` — 미해결 이슈 목록과 함께 Step 4로 강제 진행 |
| 같은 실패 시나리오가 연속 2회 동일 에러로 반복 | `BLOCKED:NO_PROGRESS` — 즉시 중단하고 Step 4로 진행 (같은 파일을 같은 방향으로 반복 수정 중) |

## Step 4: 리포트 HTML 렌더링 (정직한 자기 점검 형식)

루프가 종료되면(전체 통과로 탈출 / 상한 도달 무관) `{RUN_REPORT}`를 **정직한 자기 점검(self-check) 형식의 HTML**로 렌더링한다. 핵심은 (1) verdict 5종 세분화, (2) **시도별 raw 기록(attempt block)** 강제, (3) "본 변경 코드 vs 검증 인프라" 결함 구분이다. 단순 결과 나열이 아니라, "아무 의심 없이 성공인가?"에 정직하게 답하는 보고서를 만든다.

> **건너뛰는 경우**: Step 1 Probe SKIP, 또는 Step 3에서 `e2e-test`가 `SKIPPED:*`를 반환해 **테스트가 한 번도 실행되지 않은 경우**. e2e-test가 1회 이상 정상 실행됐다면 통과/실패와 무관하게 항상 렌더링한다.

**원칙 — `/common:doc-gen` 호출 금지**: doc-gen은 PR/refactor designer 프롬프트가 강제되어 본 보고서의 의도(정직한 자기 점검, GAP 명시, verdict 다운그레이드)와 충돌한다. doc-gen을 거치지 않고 아래 자산 프롬프트를 직접 적용해 단일 standalone HTML을 작성한다.

1. 리포트 하단에 Step 2의 "최종 요약 블록 형식"으로 `## 최종 요약`을 append 한다.
2. 출력 디렉토리를 보장한다: `mkdir -p {REPORT_DIR}`
3. 출력 경로를 결정한다: `{REPORT_DIR}/{YYYYMMDD-HHMMSS}-{branch}-e2e-report.html`
   - `{YYYYMMDD-HHMMSS}`: `date +%Y%m%d-%H%M%S` (실행마다 별개 스냅샷이므로 덮어쓰지 않는다)
   - `{branch}`: `git branch --show-current`의 슬래시(`/`)를 `-`로 치환. 못 구하면 `e2e`.
   - **파일명 컨벤션은 고정**: 상위 워크플로우가 `*-e2e-report.html` 패턴에 의존한다.
4. 자산 프롬프트 `${CLAUDE_PLUGIN_ROOT}/skills/e2e-test-loop/assets/api-test-cases-prompt.md`를 Read하고, 본 Step의 시스템 지시로 사용한다.
5. 자산 프롬프트의 지시대로 `{RUN_REPORT}`의 내용을 입력 데이터로 매핑해 단일 standalone HTML을 작성한다.

   **TC 그룹핑 원칙**: 자산 프롬프트는 케이스마다 1차~N차 attempt 시퀀스를 요구한다. `{RUN_REPORT}`는 iteration별로 케이스 블록이 흩어져 있으므로, **`{분류} + {케이스명}` 동일성**으로 묶어 iteration 순으로 정렬해 하나의 TC로 통합한다. TC ID는 케이스 최초 등장 iteration의 등장 순으로 `TC-01`, `TC-02`...

   **입력 매핑 표**:

   | 자산 프롬프트가 요구하는 입력 | `{RUN_REPORT}`에서의 출처 |
   |--|--|
   | TC id / title | `{분류} + {케이스명}`으로 그룹핑한 단위. id는 그룹 순서대로 `TC-01...`, title은 `{분류} — {케이스명}` |
   | scenario | 분류·케이스명·메서드/경로에서 1~3줄로 도출 |
   | attempt 시퀀스 (1차, 2차, ...) | 같은 그룹의 케이스 블록을 iteration 오름차순으로 나열. raw call은 `- 요청:` 줄, raw response는 `- 실제:` 줄. attempt tag는 `- 판정:` ✅→PASS, ❌→FAIL |
   | attempt cause (한 줄) | 직후의 `**실패 → 수정**` 블록 `- 실패 원인:` 줄. 없으면 `- 실제:`에서 한 줄 추출 |
   | attempt fix | 직후의 `**실패 → 수정**` 블록 `- 수정:` 줄. 마지막 PASS attempt에는 fix 없음 |
   | caller-verdict 산출 | 그룹 내 attempt 수 / 최종 결과로 계산:<br>• 1개 attempt + PASS → **CLEAN PASS**<br>• N개 attempt + 마지막 PASS → **PASS (after N-1 fixes)**<br>• 모든 attempt FAIL → **FAIL**<br>• 통과지만 응답이 본 변경과 무관 → **INCONCLUSIVE**<br>• 일부 입력만 커버 → **PARTIAL** |
   | 본 변경 vs 검증 인프라 구분 | `- 수정:` 줄의 변경 파일/내용으로 추론:<br>• 테스트 코드·expected·mock·환경변수·헬퍼·연결 문자열 수정 → **A. "본 변경 코드는 매 시도 정확, 검증 인프라 결함"**<br>• 본 변경 영역(handler/usecase/repository 등)의 코드 수정 → **B. "본 변경 코드 결함이 N차에 드러남"**<br>모호하면 fix 줄을 callout으로 인용하고 추론 근거 표기 |
   | 변경 대상 요약 | 헤더의 `# E2E 테스트 실행 리포트 — {...}` 및 `> E2E 메인 플로우:` 줄 |
   | 알려진 GAP / 한계 | `## 최종 요약`의 미해결 이슈 + 미해결 FAIL 케이스 + `## 테스트 대상 엔드포인트`에 있으나 한 번도 호출되지 않은 엔드포인트 |
   | 부수 관찰 | 명시 항목이 없으면 "부수 관찰 없음" 카드 1장. 임의 추측 금지 |

6. 자산 프롬프트의 **VALIDATION RULES**를 반드시 enforce한다. 특히:
   - **verdict 다운그레이드**: 응답이 본 변경 유무와 무관하게 같다면 ✅ → **INCONCLUSIVE** 강등 + callout. 1차 시도 통과가 아니면 ✅ → **PASS (after N fixes)** 강등.
   - **attempt block 의무**: CLEAN PASS만 attempt 1개, 그 외 모든 verdict는 1차~마지막까지 raw evidence를 모두 포함. 요약 금지.
   - **fix 명확성**: "수정함" 같은 vague 표현 금지. 실제 변경 파일/식별자가 드러나야 함.
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

> `E2E 리포트 HTML:` 줄은 **의무 출력**이다. 상위 워크플로우가 이 경로를 **유일한 채널**로 전달받아 최종 보고서에 참조한다. 서브 에이전트로 실행될 때도 이 줄이 stdout에 반드시 포함돼야 경로가 오케스트레이터까지 전파된다.

probe SKIP / 테스트 미실행인 경우 (`E2E 리포트 HTML:` 줄 없음):
```
E2E Test Loop — SKIPPED
- 사유: SKIPPED:{REASON}
- 총 iteration: 0회
```

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 루프 정상 종료 |
| `SKIPPED:{사유}` | 환경 미충족으로 루프 미진행 (`NO_PROFILE`, `DISABLED`, `NO_SERVER_URL`, `NO_SERVER`, 하위 스킬 SKIP 전파) |
| `BLOCKED:MAX_ITERATIONS` | 상한 도달, 이슈 잔존 |
| `BLOCKED:NO_PROGRESS` | 같은 실패를 연속 2회 동일 에러로 반복 |
| `PASS` / `WARN` / `FAIL` | 하위 `e2e-test` 판정 (그대로 전파) |

## 주의사항

- `e2e-test` 스킬이 서버 기동/종료를 책임지므로, 이 루프에서는 서버 상태를 직접 건드리지 않는다 (수정 후 재시작만 예외).
- 수정 에이전트가 서버를 재시작하지 않도록 프롬프트에 명시한다.
- `{buildCommand}` 가 비어있으면 빌드 체크는 SKIP.

## References

| 파일 | 로드 시점 |
|------|----------|
| `assets/api-test-cases-prompt.md` | Step 4 (HTML 렌더링) |
