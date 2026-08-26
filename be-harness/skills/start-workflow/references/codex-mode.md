> 이 문서는 `start-workflow` 스킬의 오케스트레이터가 **첫 리뷰어/위임 dispatch 직전 1회** Read한다 (재개 포함, 고정 Phase 트리거 없음). 단독 실행 금지.
> `{STATE_FILE}`, `{IMPL_NOTES}`, `{CWD}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다. `{PLUGIN_ROOT}` = `${CLAUDE_PLUGIN_ROOT}`의 절대 경로 (`printf '%s' "$CLAUDE_PLUGIN_ROOT"`로 확인).
> 마커 사이 공통 블록의 **정본은 be-harness**다. `scripts/sync-codex-mode.py`가 fe-harness/common 사본을 생성하므로 사본의 공통 블록을 직접 수정하지 않는다.

# Codex 사용 모드 (`codexMode`)

<!-- codex-mode:common-begin -->
## 1. 모드 정의

| 지점 | `none` | `mix` | `max` |
|------|--------|-------|-------|
| Plan 검증 루프 리뷰어 (입력은 기존대로 Spec·Plan 전문) | **Claude 패널** (§6) | Codex `gpt-5.6-sol`, effort = 난이도 1~6 `xhigh` / 7~10 `max` | mix와 동일 |
| 특화 하네스 품질 리뷰 (오버레이가 삽입하는 Codex 리뷰 단계) | Claude `general-purpose` 1개 = 정규 경로 (상한 불변) | Codex sol, effort 동일 | 동일 |
| 탐색·수집 / 이해·요약 (haiku·sonnet급 작업) | Claude | Claude | `gpt-5.6-luna` `medium`, `read-only` |
| 읽기 전용 판정 (스코프·품질·접근성 리뷰어, 검증기, 통합 스캐너, Read-back 복원, 엣지 케이스 분석) | Claude 등급표 | Claude 등급표 | `gpt-5.6-luna` `xhigh`, `read-only` — **검사만** 수행. 빌드·테스트 명령은 오케스트레이터/러너가 실행해 로그 경로를 전달 |
| 쓰기 (구현, Red 테스트 작성, 빌드·품질·E2E 수정, 문서 동기화, 성찰) | Claude 등급표 | Claude 등급표 | `gpt-5.6-sol` `high`, `workspace-write` (§5 쓰기 안전) |
| 오케스트레이션 — 항상 Claude | ① 오케스트레이터 ② **스킬 러너** (Codex는 Skill tool을 못 부르므로 스킬 실행은 Claude `general-purpose`; `max`면 내부 리프를 이 계약으로 위임) ③ PR 에이전트 (Assumption Gate 유저 확인 + push 네트워크) | 〃 | 〃 |

- 세 모드 모두 **절차·상한·종료 조건·티어 규칙 불변** — 실행 주체와 리뷰어의 모델·effort만 바뀐다. 검증 티어와 직교한다.
- 지점 ↔ 에이전트·Phase 번호·역할 파일 매핑은 이 문서 하단 "플러그인 매핑" 표가 정의한다.
- 질문형 에이전트(엣지 케이스 분석 등)를 Codex로 위임하면 유저 질문 대신 `## 확인 필요 질문`을 반환받아 오케스트레이터가 유저에게 묻고, 답을 붙여 1회 재호출한다 (비대화형이면 `[Assumption]`으로 진행).
- `max`이고 세션 모델이 opus/fable 계열이 아니면 Pre-flight에서 1줄 고지한다 (차단·질문 없음).
- **단일 작성자**: `{STATE_FILE}`은 오케스트레이터(또는 현재 스킬 러너)만 쓴다. Codex 리프는 구조화된 결과만 반환한다. `{IMPL_NOTES}` append는 직렬 쓰기 작업에만 허용하고, 병렬 슬라이스는 결과로 반환해 오케스트레이터가 append한다.

## 2. 저장·resolve

- profile 필드 `codexMode: none | mix | max` (`init` 질문 기본 `mix`). 모든 입력(`--codex`·profile·질문 응답)은 trim 후 exact 일치만 유효하다.
- **resolve (진입 시 1회)**
  - ① 재개(상태 파일 존재): `## Flags`의 `CODEX`와 `## Codex Runtime`을 함께 읽고 **재초기화하지 않는다**. `CODEX` 없음(구 상태 파일) → profile `codexMode` → 없으면 `mix`로 보완 기록 + 고지. `## Codex Runtime` 없음 → `상태: active`로 보완. `--codex`는 무시 + 고지, profile 미기록.
  - ② 신규: 대화 가능 여부를 먼저 판정 → `--codex` > profile > (대화형) 아래 질문 / (비대화형) `mix` ephemeral.
  - ③ 값 불일치(예: `maximum`, 대문자): 대화형이면 잘못된 값 고지 + 재질문 1회 (유효하면 명시 입력으로 기록·잘못된 값 교체 / 2차 불일치 → profile·상태 파일 불변, 입력 오류로 종료). 비대화형이면 `mix` ephemeral + 경고, profile 불변.
- **profile 기록**: 명시 입력(`--codex` 또는 질문 응답)이 있을 때만, writable `.claude/{harness}.local.md`에만 (레거시 읽기 전용 profile 제외), 시점 = Plan 모드 진입 전(Pre-flight). ephemeral(저장 안 됨) = 레거시 profile만 있는 경우(`init` 안내) · 비대화형 실행.
- 상태 파일: `## Flags`에 `CODEX: {mode}` (불변) + `## Codex Runtime` (`상태: active | fallback({사유})` / `pending` 표). 새 `RUN_ID`에서만 초기화한다.
- 질문 문구 (`AskUserQuestion` 3지선다, 권장 `mix`):
  > "Codex 사용 모드를 선택하세요 (profile `codexMode`에 저장됩니다):
  > 1. `mix` (권장) — Plan 검증 리뷰만 Codex(gpt-5.6-sol)가 수행
  > 2. `max` — mix + 탐색·판정·구현 서브에이전트를 Codex(luna/sol)로 위임해 Claude 토큰 최소화
  > 3. `none` — Codex 미사용, 리뷰는 Claude 다관점 패널"
- doctor: `codexMode ≠ none`이면 Codex MISSING = **WARN**("실행 시 Claude 폴백 예정", 비차단). `none`이면 `N/A(codexMode=none)`.
- Workflow Report §1에 `Codex 모드: {mode}{ · runtime: fallback({사유})}` 1줄을 적는다.

## 3. 호출 계약

단일 경로 `mcp__codex__codex` (CLI 폴백 없음):
- `model`: `gpt-5.6-sol` | `gpt-5.6-luna` · `config`: `{"model_reasoning_effort": "{effort}"}` (`medium` | `high` | `xhigh` | `max`)
- `sandbox`: 읽기 `read-only` / 쓰기 `workspace-write` · `"approval-policy": "never"` · `cwd`: `{CWD}`
- `prompt`: 기존 references의 해당 에이전트 프롬프트 본문 그대로 (+ §4 `required_reads`·결과 상한 문구). "Agent tool" 호출을 이 호출로 치환한다.
- `developer-instructions` 3줄 — ① "역할 정의 `{역할 파일 절대 경로}`를 먼저 Read하고 그 규칙을 따르세요." ② "프로젝트 오버라이드가 있으면 함께 Read하세요: `{CWD}/.claude/{harness}/common.md`, `{CWD}/.claude/{harness}/agents/{name}.md`" (존재하는 것만) ③ "결과는 프롬프트가 지정한 형식으로만 반환하세요." general-purpose 작업은 ①·②를 생략한다.
- 에이전트 정의의 `allowed-tools`는 sandbox로 대체한다.

## 4. 토큰 계약

절감 대상은 **Claude가 직렬화하는 프롬프트·결과(오케스트레이터 컨텍스트)**다. Codex 측 입력 토큰·총비용은 보장 대상이 아니다.
- 상태 파일 생성 이후의 위임은 파일 내용 대신 **절대 경로 + `required_reads`(파일·섹션 목록)**를 전달한다 — 상태 파일·역할 정의·스킬 규칙은 Codex가 직접 읽는다.
- 결과 상한: 기존 보고 형식 유지 + 요약 ≤ 15줄 · 근거 `파일:줄` ≤ 5건 · 실패 로그 ≤ 20줄. diff·로그 전문 반환 금지 (상세는 파일에 남긴다).
- Plan 검증 루프 리뷰는 예외 — 상태 파일 이전 단계이므로 기존대로 Spec·Plan 전문을 전달한다.

## 5. 쓰기 안전 상태 머신 (Codex `workspace-write` 호출과 그 Claude 폴백에만 적용)

단위 = 쓰기 단계 1회 (구현 · Red · 빌드 수정 · 품질 수정 …). 호출 ID = `{단계}-{슬라이스 ID | single}`.

- **스냅샷 `S`** (sequential만) = `HEAD` + 임시 인덱스 트리 해시. 실제 인덱스·호출 셸 환경은 불변:
  ```bash
  ( d=$(mktemp -d) && trap 'rm -rf "$d"' EXIT && export GIT_INDEX_FILE="$d/index" && git read-tree HEAD && git add -A && printf '%s %s\n' "$(git rev-parse HEAD)" "$(git write-tree)" )
  ```
  비0 종료·빈 출력 = 닫힌 실패 (S 불명 → "진행"으로 간주). `{STATE_FILE}`·`{IMPL_NOTES}`가 오버라이드로 작업 트리 안에 있을 때만 `git add -A -- . ':(exclude){경로}'`로 제외한다.
- **호출 전 영속**: `## Codex Runtime`의 `pending` 표에 행 `| {호출 ID} | {사용 종류 목록} | {범위 all \| slice:{id}} | {S0 \| -} | {핸들 \| -} |`을 dispatch **전에** 기록한다 (병렬 슬라이스는 모든 행을 기록한 뒤 한 메시지로 동시 dispatch). 논리 호출당 행 1개 — 재호출 전 같은 행의 사용 종류·핸들을 갱신한다. 행은 `VERIFIED` 또는 종료 조건 도달 시에만 삭제한다.
- **실행**: 120초 초과 시 Claude Code가 백그라운드 태스크로 전환한다 → 핸들을 행에 기록하고 완료 알림을 **최대 30분** 대기 (대기 중 재호출·Claude 폴백·다음 쓰기 단계 시작 금지). 완료 → 결과 형식 검증 → `VERIFIED` / `FAILED(invalid_result)`.
- **선행 호출 종료 확인** = 아래 모든 전이의 공통 전제. 오류·완료 종료는 그 자체로 확인. 대기 상한 초과 시 `TaskStop`(핸들) → 정지 확인 → `FAILED(no_result)`. 정지·조회를 확인할 수 없으면 재호출 금지 → 즉시 종료 조건 (동일 트리에 두 writer 금지).
- **재개**: `pending` 행이 남아 있으면 마지막 종류의 호출이 사망한 것으로 보고 아래 매트릭스를 적용한다 (핸들은 세션 종료로 소멸 = 종료 확인됨).
- `FAILED` 사유 = `tool_error` (MCP 오류·타임아웃·5xx) / `no_result` (빈 결과·대기 상한 초과·핸들 소실) / `invalid_result` (형식 검증 실패). 셋 다 동일 매트릭스 — 각 종류 최대 1회, 모든 경로가 4회 이내에 끝난다:

| 실패한 종류 | sequential 무진행 (`S == S0`) | sequential 진행 (`S != S0`, 닫힌 실패 포함) | parallel-slices (판정 없음) |
|---|---|---|---|
| `initial` | `retry` (Codex 동일 조건) | `continue` (Codex 이어서) | `continue` |
| `retry` | `fallback` (Claude 처음부터) | `continue` | — |
| `continue` | `fallback` (Claude 이어서) | `fallback` (Claude 이어서) | `fallback` (Claude 이어서) |
| `fallback` | 종료 조건 | 종료 조건 | 종료 조건 |

- 종료 조건 = 기존 사망 규약의 종료 조건 (구현·수정류 `BLOCKED:AGENT_DIED`). 이어서 프롬프트에는 변경 파일 목록·HEAD 이동과 "다른 슬라이스 allowlist 파일 수정 금지 — 수정했다면 되돌리고 보고"를 포함한다.
- 교차 슬라이스 소유권은 기존과 동일한 **프롬프트 수준 규칙**("위 파일 범위에 해당하는 파일만 수정하세요. 범위 밖 파일은 절대 수정하지 않습니다.")이다 — git 수준 귀속·격리는 하지 않는다. 다음 쓰기 단계는 `pending` 표가 비어야 시작한다.
- 커밋: sequential 구현 에이전트의 논리 단위 커밋은 기존 규칙 유지 (HEAD 이동 = 진행). parallel-slices는 Codex의 커밋·빌드·테스트 명령 실행 금지 (테스트 파일·스텁 **작성**은 허용), 배리어에서 오케스트레이터가 단독 수행한다.

## 6. Claude 패널 (`none`의 정규 리뷰 경로 · `mix`/`max`의 리뷰 폴백)

- **Plan 검증 루프 패널**: Logic / Architecture / Edge Cases 3관점 `general-purpose` 병렬 (난이도 ≤ 6 sonnet, ≥ 7 opus, effort는 등급표). 입력·출력 형식·판정 이후 처리(CONCERN/REJECT·상한·카운터·티어)는 기존 루프와 동일하다.
  - 슬롯 사망 → 사망 규약(동일 조건 → 강등 재시도) → 그래도 없으면 오케스트레이터가 그 관점을 축소 수행(`degraded_fallback`) → 세션 한계로 불가하면 슬롯 무효. 응답은 왔지만 verdict 누락·범위 밖(APPROVE/CONCERN/REJECT 외)도 슬롯 사망과 동일하게 처리한다.
  - 종합 (우선순위): ① 유효 REJECT ≥ 1 → **REJECT** ② 유효 verdict 3개 전원 APPROVE → **APPROVE** ③ 유효 3개·REJECT 없음 → **CONCERN** ④ REJECT 없이 유효 3개 미달 → **패널 실패 = `CODEX-UNAVAILABLE`** (light 승격 ⑤는 이때만 발동).
- **특화 하네스 품질 리뷰 패널**: `general-purpose` 1개 (리뷰 관점 전체를 한 프롬프트로). 유효 verdict 1개 = 최종값. 사망·무효 verdict → 사망 규약 → `degraded_fallback` (오케스트레이터 축소 리뷰 — 읽기 전용 작업이라 항상 verdict를 낸다). 기존 Verdict 처리·상한 불변.

## 7. 실패 정책 (진단 = `Phase Results`의 `진단` 셀, Status는 표준 코드)

| 사유 | 감지 | 범위 | 조치 |
|------|------|------|------|
| `mcp_missing` | 도구 목록에 `mcp__codex__codex` 없음 — Pre-flight와 **모든 dispatch(병렬 묶음 포함) 직전**에 존재만 확인 (호출 없이). 러너는 자기 도구 목록을 재확인 | 실행 전체 latch | Claude 경로, `상태: fallback(mcp_missing)`, 고지. profile 불변 |
| `quota_exhausted` | 응답에 429·"usage limit"·"rate limit"·"quota"·"try again at" **문구 확인 시만** | 실행 전체 latch | 남은 위임·리뷰 전부 Claude (리뷰 = §6), `상태: fallback(quota_exhausted)` 즉시 기록 |
| `auth_failed` / `model_unavailable` | 인증 오류 / 모델·effort 미지원 | 실행 전체 latch | 동일 |
| `tool_error` / `no_result` / `invalid_result` | 그 외 MCP 오류(타임아웃·5xx 포함) / 빈 결과·대기 상한 초과·핸들 소실 / 결과 형식 검증 실패 | 해당 작업 | 읽기: 1회 재시도 → Claude 폴백. 쓰기: §5 매트릭스. 진단 `codex_fallback({단계}:{사유})` |

- 상태 파일 생성 이전(Plan 모드)의 latch는 세션 변수 `$CODEX_RUNTIME`에 보유하고, 상태 파일 생성 시 그 값을 `## Codex Runtime`에 기록한다 (`active`로 초기화하지 않는다).
- latch는 **dispatch 시점** 판정이다: 확정 이후 신규 dispatch 금지, 이미 진행 중인 호출은 규칙대로 완료·판정한다 (성공 결과는 유효). 병렬 묶음은 dispatch 전에 MCP 확인·latch 확정 후 한 메시지로 보낸다. 러너의 `mcp_missing` 보고 = latch 확정.
- 리뷰 폴백 = §6 패널이 리뷰를 수행한다 (`codex_fallback(plan_review:{사유})`, 승격 ⑤ 미발동). **`CODEX-UNAVAILABLE`은 §6 패널 실패만을 뜻한다.**
- 특화 하네스의 `SKIPPED:CODEX_*`는 "Codex 호출 항목은 건너뛰고 리뷰는 패널이 수행"이다 — latch 사유별 `quota_exhausted` → `SKIPPED:CODEX_QUOTA_BLOCKED`, `mcp_missing`·`auth_failed`·`model_unavailable` → `SKIPPED:CODEX_UNAVAILABLE`. 리뷰 상한·`BLOCKED:*`·재실행 규칙은 불변.
- Codex 위임 실패는 사망 규약 대상이 아니다. Claude 폴백 에이전트부터 사망 규약을 적용한다.
- **`none`**: 이 표를 적용하지 않는다 — Codex 호출·MCP 확인·`SKIPPED:CODEX_*` 기록 없음. 패널이 정상 경로다 (진단 없음).

## 8. 러너·리프 포인터

- `max`에서 스킬 러너 프롬프트에 1줄 추가: "codexMode: max · 위임 계약: `{PLUGIN_ROOT}/skills/start-workflow/references/codex-mode.md` (수정 = sol/high/workspace-write, 리뷰 = luna/xhigh/read-only)". 러너는 자기 도구 목록에 MCP가 없으면 결과에 `mcp_missing`을 보고하고 Claude로 수행한다.
- 리프 스킬은 고정 문단을 복제하지 않고 위 포인터 1줄만 둔다 (대상은 플러그인 매핑의 "러너 대상").
<!-- codex-mode:common-end -->

## 플러그인 매핑 (be-harness)

| 지점 | 대상 | 역할 파일 (`developer-instructions` ①) |
|------|------|------|
| Plan 검증 루프 | Phase 4.3 (난이도 = Phase 2 종합 난이도) | — (Spec·Plan 전문 전달) |
| 특화 하네스 품질 리뷰 | minmos 오버레이 `Phase 8+` | — |
| 탐색·수집 / 이해·요약 | 탐색 위임 에이전트(haiku/low 묶음) · 8.8 Read-back 복원(sonnet) | — (general-purpose) |
| 읽기 전용 판정 | 8.4 `scope-reviewer` · 8.2+8.3 통합 스캐너 · A3 `code-analyzer` · V3 `code-verifier` · `edge-case-analyzer`(워크플로우 밖 직접 호출 시) | `{PLUGIN_ROOT}/agents/{name}.md` (통합 스캐너는 general-purpose) |
| 쓰기 | 6.1 Red(러너 내부 리프) · 6.2 `workflow-implementer` / 병렬 슬라이스 general-purpose · 7 build-fix · 8.5 통합 수정 · 8.6 E2E 수정(러너 내부 리프) · 8.7 통합 테스트 수정 · 9 문서 동기화 · 11 `workflow-reflection` | `{PLUGIN_ROOT}/agents/{name}.md` (general-purpose는 생략) |
| 러너 대상 (항상 Claude — `max`면 §8 포인터 1줄) | 6.1 `/be-harness:unit-test --red` · 8.6 `/be-harness:e2e-test-loop` · V4 `/be-harness:convention-check` | — |
| PR (항상 Claude) | 10 `workflow-pr` | — |

- `max`의 6.1 sequential: Codex sol이 `{PLUGIN_ROOT}/skills/unit-test/SKILL.md` Step 1~4를 직접 읽어 수행한다 (`references/tdd.md`). none·mix는 기존 Skill tool 경로.
- Analyze/Verify 모드: A3·V3은 "읽기 전용 판정" 지점이다. 해당 상태 파일에는 `## Codex` 절(`CODEX: {mode}` / `상태: …`)을 둔다.
- 오버라이드 경로: `{CWD}/.claude/be-harness/common.md` · `{CWD}/.claude/be-harness/agents/{name}.md`.
