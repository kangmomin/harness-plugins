---
name: e2e-test-loop
description: "E2E 테스트 → 이슈 수정 → 재테스트를 반복한다 (최대 5회). 종료 시 정직한 자기 점검 md 리포트를 스크립트로 생성한다. 기능 구현 후 'E2E 돌려줘', '테스트 통과할 때까지 고쳐줘' 요청 시 사용. start-workflow 품질 루프에서 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill
user-invocable: true
argument-hint: "[--skip-doctor] [--smoke]"
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/e2e-test-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# E2E Test Loop

`/be-harness:e2e-test` 를 실행하고, 실패가 있으면 수정한 뒤 다시 실행한다. 최대 `{MAX_ITER}`회 반복하고, 종료 시 실행 전체를 **정직한 자기 점검 md 리포트**로 남긴다 (렌더링은 스크립트 — Claude 토큰 0).

**플레이스홀더 정의** (본문·assets 공통, 값 변경은 여기 한 곳만 수정):

- `{RUN_REPORT}` = `{E2E_RUN_DIR}/e2e-run-report.md` (루프 중 누적하는 원시 기록)
- `{REPORT_DIR}` = profile의 `reportDir` (없으면 `.claude/harness-reports`)
- `{MAX_ITER}` = 5 (`--smoke` 시 3)
- `{RENDERER}` = `${CLAUDE_PLUGIN_ROOT}/skills/e2e-test-loop/assets/render_e2e_report.py`
- `{CWD}` = 현재 작업 디렉토리 (프로젝트 루트)

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--skip-doctor` | `-sd` | 루프 진입 전 환경 probe를 건너뛴다 (사용자 책임) |
| `--no-lock` | | 하위 `e2e-test` 에 그대로 전달해 실행 락을 건너뛴다 (단독 실행/디버깅 전용) |
| `--smoke` | | 하위 `e2e-test --smoke` 전달(`BASE-01` + `EC-*` 전수만) + `{MAX_ITER}` = 3. 실효 수준은 e2e-test가 Step 2에서 확정한다 (0건·EC 표 없음이면 full 폴백) |

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
- 하나라도 FAIL → **루프 진입 없이** 즉시 아래 형식으로 종료 (리포트 파일 생성·md 렌더링 없음):
  ```
  ## E2E Test Loop — SKIPPED
  사유: SKIPPED:{REASON}
  누락 항목: {항목}
  복구 방법: `/be-harness:init` 으로 profile 재설정 또는 `/be-harness:doctor` 로 진단
  ```

## Step 2: 실행 리포트 초기화

> Probe를 통과해 **실제 루프에 진입하는 경우에만** 수행한다. Step 1 SKIP 종료 경로에서는 리포트 파일을 만들지 않는다.

루프 동안 수행하는 모든 테스트 케이스의 요청 데이터·기대·실제·판정과 실패→수정 내역을 `{RUN_REPORT}`에 누적한다. 루프 종료 후 이 파일이 Step 4 md 렌더링(스크립트)의 유일한 입력이 된다 — 여기에 적히지 않은 것은 리포트에 없다.

먼저 `${CLAUDE_PLUGIN_ROOT}/skills/e2e-test/references/run-context.md`를 Read하고 이번 루프의 `{E2E_RUN_DIR}`·`{E2E_LOCK_TOKEN}`을 확정한다. 각 iteration의 하위 `e2e-test`에 두 값을 그대로 전달한다.
Write tool로 `{RUN_REPORT}`를 새로 생성한다. 같은 미완료 루프를 계속하는 경우에는 기존 기록에 append하며 덮어쓰지 않는다:

```markdown
# E2E 테스트 실행 리포트 — {브랜치명 또는 작업 요약}

> 생성: {ISO timestamp}
> E2E 메인 플로우: {제공된 메인 플로우 전문 또는 "자동 도출 (git diff 기반)"}
> 수준: {첫 iteration e2e-test의 `- 실행 수준:` 값 그대로 — 기록 전에는 "미정"}

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
- 판정: ✅ 통과 / ❌ 실패 / ⚠️ INCONCLUSIVE({사유}) / ⚠️ PARTIAL({사유})
```

> `{분류}`는 `Happy Path` / `Validation` / `Edge Case` / `인증·권한` / `Status 정합성` 중 하나. `### Iteration {N}` 헤더는 iteration당 1회만 적는다.

**정직성 규칙 (append 시점에 판정한다 — 렌더러는 기록된 마커만 믿는다)**:
- 응답이 본 변경 유무와 무관하게 같다면 ✅ 대신 `⚠️ INCONCLUSIVE(응답이 본 변경과 무관)`. 입력의 일부만 커버했다면 `⚠️ PARTIAL({커버한 범위})`.
- `- 요청:` `- 기대:` `- 실제:` `- 판정:` 네 줄은 **필수** — 하나라도 빠진 케이스는 렌더러가 `INCONCLUSIVE(필수 필드 결여)`로 집계한다.
- **케이스명은 iteration 간 동일하게 유지**한다 — TC 식별 키는 `{분류} + {케이스명}`이다. 이름을 바꾸면 다른 케이스로 집계된다.

**실패→수정 블록 형식** — Step 3의 수정 단계에서 실패한 케이스마다 해당 케이스 블록 끝에 이 형식으로 append 한다:

```markdown
**실패 → 수정 ({케이스명})**
- 실패 원인: {root cause}
- 수정: {file:line — 변경 요약}
- 귀속: 본 변경 코드 | 검증 인프라 | 혼합
- 재빌드/재시작: 예 / 아니오
```

> `- 귀속:` 줄은 선택 — 생략하면 렌더러가 `- 수정:` 줄의 경로로 추정한다(테스트·mock·fixture·env·docker·헬퍼·scripts → 검증 인프라, 그 외 → 본 변경 코드). 수정 블록은 반드시 **해당 케이스 블록 직후**에 둔다.

**최종 요약 블록 형식** — Step 4에서 리포트 하단에 1회 append 한다:

```markdown
## 최종 요약
- 총 iteration: {N}회
- 총 테스트: {M}건 (통과 {X} / 실패 {Y})
- 미해결 이슈: {목록 또는 "없음"}
- 커버리지: UNCOVERED {ID}({사유}) … / SMOKE_OMITTED {IDs} / 없음
```

> `- 커버리지:` 줄은 마지막 e2e-test 리포트의 커버리지·생략 시나리오를 한 줄로 옮긴다 (렌더러의 GAP 입력 — 1회만).

> 누적 규칙: 모든 기록은 **append-only**. 이전 iteration 블록이나 이미 적힌 케이스 블록을 수정하지 않는다. 마크다운만 작성한다(HTML 직접 작성 금지 — Step 4 스크립트 파싱이 깨진다).

## Step 3: 루프 (최대 {MAX_ITER}회)

1. `/be-harness:e2e-test` 를 실행한다 (`--smoke`면 `--smoke`를 그대로 전달).
   - 첫 iteration이면 e2e-test 리포트의 `- 실행 수준:` 값을 헤더 `> 수준:`에 옮겨 적는다.
   - 헤더의 E2E 메인 플로우가 `자동 도출 (git diff 기반)`이 아니면, 해당 플로우를 Happy Path 필수 시나리오로 포함하도록 e2e-test에 전달한다.
   - 첫 iteration이면 e2e-test가 도출한 엔드포인트 목록을 리포트의 `## 테스트 대상 엔드포인트` 섹션에 채운다.
   - 하위 스킬이 `SKIPPED:*`를 반환하면 루프를 추가 진행하지 않는다. 빈 리포트 파일을 삭제(`rm -f {RUN_REPORT}`)하고 동일 SKIP 사유로 보고한다. **Step 4(md 렌더링)는 건너뛴다.**
   - 하위가 `BLOCKED:LOCK_UNAVAILABLE`을 반환하면 동일하게 루프를 진행하지 않고 `rm -f {RUN_REPORT}` 후 Step 4를 생략하며, 종료 상태 `BLOCKED:LOCK_UNAVAILABLE`과 `E2E 리포트: 없음 (BLOCKED:LOCK_UNAVAILABLE)`을 보고한다(SKIPPED 출력 블록과 같은 구조, 사유 줄만 `BLOCKED:LOCK_UNAVAILABLE`).
   - 정상 실행되면, 이번 iteration의 **모든 테스트 케이스**(통과·실패 무관)를 Step 2의 "케이스 블록 형식"으로 append 한다.
2. 결과를 확인한다:
   - **판정 `PASS`** (모든 시나리오 통과 + 미커버 0건) → 루프 종료 → Step 4
   - **판정 `WARN`** (실패 0건 + `UNCOVERED:{사유}` 1건 이상) → 루프 종료 → Step 4. 미커버는 검증 공백이지 구현 결함이 아니므로 수정 루프를 돌리지 않고, 사유를 리포트에 남긴 채 상위에 전달한다.
   - **판정 `FAIL`** → 3번으로 진행
3. 발견된 이슈를 수정한다. `general-purpose` 에이전트에 위임한다 (상위 워크플로우가 `codexMode: max` 위임 계약 포인터를 전달했으면 그 계약대로 — 수정 = Codex `write` 슬롯/workspace-write):
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
| `e2e-test`가 `BLOCKED:LOCK_UNAVAILABLE` 반환 | 루프 미진행, 그대로 보고 (Step 4 생략) |
| `{MAX_ITER}`회 도달, 이슈 잔존 | `BLOCKED:MAX_ITERATIONS` — 미해결 이슈 목록과 함께 Step 4로 강제 진행 |
| 같은 실패 시나리오가 연속 2회 동일 에러로 반복 | `BLOCKED:NO_PROGRESS` — 즉시 중단하고 Step 4로 진행 (같은 파일을 같은 방향으로 반복 수정 중) |

## Step 4: 리포트 md 렌더링 (정직한 자기 점검 형식)

루프가 종료되면(전체 통과로 탈출 / 상한 도달 무관) `{RUN_REPORT}`를 **스크립트로** 정직한 자기 점검(self-check) md로 렌더링한다. Claude가 리포트를 직접 쓰지 않는다 — verdict 5종·시도별 raw 기록·"본 변경 코드 vs 검증 인프라" 귀속·GAP·"아무 의심 없이 성공인가?" 직답은 모두 `{RUN_REPORT}`의 기록에서 결정적으로 계산된다. 정직성은 Step 2의 append 시점 규칙(마커·귀속 줄·케이스명 불변·필수 4줄)이 담보한다.

> **건너뛰는 경우**: Step 1 Probe SKIP, 또는 Step 3에서 `e2e-test`가 `SKIPPED:*`나 `BLOCKED:LOCK_UNAVAILABLE`을 반환해 **테스트가 한 번도 실행되지 않은 경우**. e2e-test가 1회 이상 정상 실행됐다면 통과/실패와 무관하게 항상 렌더링한다.

1. 리포트 하단에 Step 2의 "최종 요약 블록 형식"으로 `## 최종 요약`을 append 한다 (`- 커버리지:` 줄 포함).
2. 렌더러를 실행한다:
   ```bash
   python3 {RENDERER} {RUN_REPORT} --out-dir {REPORT_DIR} --branch "$(git branch --show-current)" \
     --level {smoke|full} [--level-note "{사유}"] --status {DONE|BLOCKED:MAX_ITERATIONS|BLOCKED:NO_PROGRESS}
   ```
   - `--level`: 헤더 `> 수준:` 매핑 — `smoke` → `--level smoke`, `full` → `--level full`, `full(smoke 미적용: X)` → `--level full --level-note "X"`. `--level`·`--status`는 필수 인자다.
   - `--status`: 종료 표의 결과 — 판정 `PASS`/`WARN` 탈출 = `DONE`.
   - 출력 파일: `{REPORT_DIR}/{YYYYMMDD-HHMMSS}-{branch}-e2e-report.md` (스크립트가 결정, 덮어쓰지 않음). **파일명 컨벤션은 고정**: 상위 워크플로우가 `*-e2e-report.md` 패턴에 의존한다.
   - stdout 두 줄 `경로: …` / `상태: OK|DEGRADED({사유})`. `DEGRADED`(필수 필드 결여·파싱 실패·케이스 연속성 위반 의심 등)여도 파일은 생성된다 — 사유를 종료 출력에 병기한다.
3. **폴백** (exit ≠ 0 — python3 부재·인자 오류·쓰기 실패): 감지 = exit code → `mkdir -p {REPORT_DIR} && cp {RUN_REPORT} {REPORT_DIR}/{YYYYMMDD-HHMMSS}-{branch}-e2e-report.md` 로 원시 기록을 그대로 저장 → 고지: "E2E 리포트 렌더링 스크립트 실패({사유}) — 원시 실행 기록을 그대로 저장했습니다." 종료 출력의 `E2E 리포트:` 줄에 `(원시 기록, 렌더링 실패: {사유})`를 병기한다.
4. 생성된 md 절대 경로를 "종료 시 출력"의 `E2E 리포트:` 줄에 기록한다.

렌더러가 계산하는 것(참고 — 규칙은 스크립트 상단 주석이 canonical): TC = `{분류} + {케이스명}` 동일성으로 iteration 순 통합(`TC-01`, `TC-02`…) · verdict = `CLEAN PASS` / `PASS (after N fixes)` / `FAIL` / `INCONCLUSIVE({사유})` / `PARTIAL({사유})` (마커 우선, 수정 없이 재시도 통과·수정 후 재검증 기록 없음은 INCONCLUSIVE) · 귀속 = `- 귀속:` 줄 우선, 없으면 `- 수정:` 경로 추정 · GAP = 미해결 이슈 + FAIL TC + 미호출 엔드포인트 + `UNCOVERED`/`SMOKE_OMITTED` (없으면 "기록 없음 — 리포트는 실행된 케이스만 증명한다") · 직답 = 경성 결함 0건 ∧ 수정 후 통과 0건 ∧ `SMOKE_OMITTED` 0건 ∧ `DONE`일 때만 `예`, smoke는 최대 `조건부 예 (smoke 범위)`.

## 종료 시 출력

```
E2E Test Loop 완료
- 총 iteration: N회
- 발견된 이슈: M건
- 수정된 이슈: X건
- 미해결 이슈: Y건 (있으면 목록)
- 종료 상태: DONE | BLOCKED:MAX_ITERATIONS | BLOCKED:NO_PROGRESS | BLOCKED:LOCK_UNAVAILABLE
- 실행 수준: {헤더 `> 수준:` 값 그대로}
- E2E 리포트: {절대 경로} [(원시 기록, 렌더링 실패: {사유})] [/ 상태: DEGRADED({사유})]
```

> `E2E 리포트:` 줄은 **의무 출력**이다. 상위 워크플로우가 이 경로를 **유일한 채널**로 전달받아 최종 보고서에 참조한다. 서브 에이전트로 실행될 때도 이 줄이 stdout에 반드시 포함돼야 경로가 오케스트레이터까지 전파된다.

probe SKIP / 테스트 미실행인 경우 (렌더러를 호출하지 않는다 — 산출물 없음이 정직한 결과):
```
E2E Test Loop — SKIPPED
- 사유: SKIPPED:{REASON}
- 총 iteration: 0회
- E2E 리포트: 없음 (SKIPPED:{REASON})
```

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 루프 정상 종료 |
| `SKIPPED:{사유}` | 환경 미충족으로 루프 미진행 (`NO_PROFILE`, `DISABLED`, `NO_SERVER_URL`, `NO_SERVER`, 하위 스킬 SKIP 전파) |
| `BLOCKED:MAX_ITERATIONS` | 상한 도달, 이슈 잔존 |
| `BLOCKED:NO_PROGRESS` | 같은 실패를 연속 2회 동일 에러로 반복 |
| `BLOCKED:LOCK_UNAVAILABLE` | 락 디렉토리 생성 불가·권한 오류로 루프 미진행 |
| `PASS` / `WARN` / `FAIL` | 하위 `e2e-test` 판정 (그대로 전파) |

## 주의사항

- `e2e-test` 스킬이 서버 기동/종료를 책임지므로, 이 루프에서는 서버 상태를 직접 건드리지 않는다 (수정 후 재시작만 예외).
- **실행 락도 직접 다루지 않는다.** 하위 `e2e-test` 가 회차마다 획득/해제하므로, 수정 단계 동안에는 락이 풀려 다른 에이전트가 순번을 가져갈 수 있다. 루프 전체를 잠그면 수정하는 내내 다른 에이전트가 굶으므로 의도된 동작이다.
- 수정 에이전트가 서버를 재시작하지 않도록 프롬프트에 명시한다.
- `{buildCommand}` 가 비어있으면 빌드 체크는 SKIP.

## References

| 파일 | 로드 시점 |
|------|----------|
| `assets/render_e2e_report.py` | Step 4 (md 렌더링 스크립트 — Read하지 않고 실행만 한다) |
