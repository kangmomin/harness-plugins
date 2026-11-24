> 이 문서는 `start-workflow` 오케스트레이터가 **Pre-flight의 `codexMode`·`codexModels` resolve 직후 1회** Read한다 (재개 포함). 단독 실행 금지.
> be/fe/common 사본은 byte-identical이다 (`scripts/check_contracts.py`). `{PLUGIN_ROOT}`·`{CWD}`·`{STATE_FILE}`·`{RUN_DIR}`는 호출한 SKILL.md 정의를 따른다.

# 공통 설정 (`.claude/harness.config.json`) · 리뷰 엔진 · 단계 토글

be/fe/common이 함께 읽는 프로젝트 설정 1개. 편집은 `harness-settings` mod(`/harness-settings`) 또는 직접 수정. 하네스 profile(`.claude/{harness}.local.md`)은 그대로 유지되며, 이 파일은 아래 키만 다룬다. 모든 키는 선택이고 없는 키는 기존 동작이다.

```json
{
  "version": 1,
  "review": {
    "enabled": true,
    "engine": "codex",
    "points": { "plan": true, "quality": true },
    "gemini": { "model": "" }
  },
  "steps": { "ocr": true, "e2e": true, "simplifyLoop": true, "reflect": false }
}
```

- `review.engine` = `codex | gemini | claude`. 생략 → `codexMode`가 `none`이면 `claude`, 그 외 `codex`. `codex` 모델은 profile `codexModels.review` 그대로 (codex-mode.md §2.1).
- `review.enabled: false` 또는 `review.points.{plan|quality}: false` = 그 리뷰를 **건너뛰지 않고** Claude 패널(codex-mode.md §6)이 수행한다.
- `review.gemini.model` = `^(?:[A-Za-z0-9][A-Za-z0-9._:/-]*)?$` (첫 글자 영숫자 — `-`로 시작하면 CLI 플래그로 읽힘). 빈 값 = gemini CLI 기본 모델 (`--model` 미전달).
- 이 파일은 **리뷰 지점 실행 주체만** 정한다. `codexMode: max`의 explore·judge·write 위임은 profile 그대로.

## 1. resolve (Pre-flight 1회)

우선순위 = CLI 플래그 > `harness.config.json` > profile > 기본값.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/harness_config.py" resolve --cwd "{CWD}" \
  --codex-mode "{CODEX}" --codex-source "{flag|profile|default}" \
  [--e2e-enabled "{profile e2eEnabled — BE만}"] [--reflect]   # --reflect = 플래그가 있을 때만
```

- `--codex-source flag` = `--codex` 플래그 또는 3지선다 질문 응답(명시 입력). profile 값이면 `profile`, 기본값이면 `default`.
- 출력 `values.codexMode`가 입력과 다르면(config `engine: codex`가 profile `none`을 `mix`로 올림) 그 값으로 `CODEX`를 확정한다 — ephemeral, profile 불변. 이때 codex-mode.md §2.1 슬롯 resolve(`CODEX_MODELS`)와 `mcp__codex__codex` 존재 확인을 **새 값으로 다시 수행**한다 (`N/A`로 남기지 않는다). 명시 `none`(플래그·질문 응답)은 config보다 우선한다(`CODEX_DISABLED_BY_FLAG`).
- 신규 실행에서 config `review.engine`이 있으면 `codexMode` 3지선다 질문의 리뷰 설명은 무의미하다 — 질문은 위임(`max`) 여부 판단용으로만 유지한다.
- `diagnostics`(`PARSE_ERROR`·`INVALID_KEY`·`UNKNOWN_KEY`)는 1회 고지하고 계속한다. `PARSE_ERROR` = 파일 전체 무시, 그 외 = 그 키만 기본값.
- 상태 파일 `## Flags`에 출력 `flags`를 그대로 기록한다: `- REVIEW: plan={engine},quality={engine}` · `- STEPS: ocr=on|off,e2e=on|off,simplify=on|off,reflect=on|off` · (gemini 사용 시) `- GEMINI_MODEL: {model | -}`. 상태 파일 생성 전에는 세션 변수로 보유한다. 불변.
- **재개**: `## Flags` 값이 기준이다 — 파일을 다시 읽지 않는다. 구 상태 파일(`REVIEW` 없음) → `REVIEW`는 `CODEX`가 `none`이면 `claude`, 그 외 `codex`로, `STEPS`는 전부 `on`(reflect = 기존 `$REFLECT`)으로 보완 기록 + 고지.
- Workflow Report §1에 `리뷰: {REVIEW} · 단계: {STEPS}` 1줄을 적는다.

## 2. 리뷰 지점 dispatch

`REVIEW`의 `plan` = Plan 검증 루프, `quality` = 특화 하네스 품질 리뷰 (지점 매핑은 codex-mode.md 하단 "플러그인 매핑").

| 값 | 실행 주체 |
|----|----------|
| `codex` | codex-mode.md §3 `review` 슬롯 (실패 정책 §7) |
| `gemini` | 아래 §3 (실패 정책 §4) |
| `claude` | codex-mode.md §6 패널 — 정규 경로, 진단·`SKIPPED:*` 없음 |

입력·verdict 형식·판정 이후 처리(CONCERN/REJECT·상한·티어)는 엔진과 무관하게 동일하다.

## 3. Gemini 호출 계약 (읽기 전용)

- 오케스트레이터가 codex `review` 슬롯에 보낼 프롬프트 본문과 같은 내용(Plan 루프 = Spec·Plan 전문)을 `{RUN_DIR}/gemini-{plan|quality}-{n}.md`에 쓴다 (`{RUN_DIR}` 생성 전이면 `mktemp -d`). `n` = 그 지점 호출 순번.
- 호출 (cwd = `{CWD}`, Bash timeout 600000ms):
  ```bash
  gemini --skip-trust --approval-mode plan -o json ${GEMINI_MODEL:+"--model=$GEMINI_MODEL"} \
    -p "stdin의 리뷰 요청을 따르고 요청한 형식으로만 답하세요. 파일을 수정하지 마세요." \
    < "{PROMPT_FILE}" > "{PROMPT_FILE%.md}.json" 2> "{PROMPT_FILE%.md}.err"
  ```
  - `GEMINI_MODEL` = `## Flags` 값 (`-`면 빈 값). `--approval-mode plan` = 읽기 전용. 신뢰되지 않은 폴더는 plan 모드가 `default`로 바뀌므로 `--skip-trust`를 함께 준다. `--yolo`·`auto_edit` 금지.
- 결과 = JSON의 `response` 문자열. 그 본문을 codex 결과와 같은 형식 검증에 넣는다 (verdict 누락·범위 밖 = `invalid_result`).

## 4. Gemini 실패 정책

| 사유 | 감지 | 조치 |
|------|------|------|
| `gemini_missing` | Pre-flight·각 dispatch 직전 `command -v gemini` 실패 | latch → 이후 gemini 지점 전부 §6 패널. `SKIPPED:GEMINI_UNAVAILABLE` |
| `auth_failed` | exit≠0 + stderr에 401·403·"authentication"·"login"·"API key" | latch → 패널. `SKIPPED:GEMINI_UNAVAILABLE` |
| `quota_exhausted` | exit≠0 + 429·"RESOURCE_EXHAUSTED"·"quota"·"rate limit" | latch → 패널. `SKIPPED:GEMINI_QUOTA_BLOCKED` |
| `model_unavailable` | exit≠0 + 모델명을 지칭하는 "not found"·"unknown model"·"not supported" | latch → 패널. `SKIPPED:GEMINI_UNAVAILABLE` |
| `tool_error` / `no_result` / `invalid_result` | 그 외 exit≠0·timeout / 빈 출력·`response` 없음 / 형식 검증 실패 | latch 없음. 1회 재시도 → 패널. 진단 `gemini_fallback({단계}:{사유})`만 |

- 판정 순서 = 표의 위에서 아래. 상태 코드 없는 단순 키워드로 latch하지 않는다.
- latch 기록: `## Codex Runtime`에 별도 줄 `- gemini: active | fallback({사유})` (codex `상태` 줄과 섞지 않는다 — codex dispatch 판정에 영향 없음). 상태 파일 생성 전에는 세션 변수.
- `CODEX-UNAVAILABLE`은 여전히 §6 패널 실패만 뜻한다. 리뷰 상한·`BLOCKED:*` 규칙은 불변.
- doctor: `REVIEW`에 gemini가 있을 수 있으면(`review.engine: gemini`) `gemini` 실행 파일 존재만 확인한다 (호출·인증 확인 없음, 비차단 WARN).

## 5. 단계 토글 (`STEPS`)

`off` = 그 단계를 실행하지 않고 Phase Results에 `SKIPPED:CONFIG`를 기록한다. 단 `reflect`는 출처(`sources.steps.reflect`)가 `config`일 때만 `SKIPPED:CONFIG`, 기본값 off면 기존 `SKIPPED:REFLECT_NOT_REQUESTED`. 티어 규칙이 이미 생략하는 단계는 티어 사유를 기록한다. `on` = 기존 규칙 그대로 (강제 실행이 아님).

| 토글 | 생략 대상 |
|------|----------|
| `ocr` | OCR 보조 입력 수집 (`ocr-review.md`) — 리뷰는 기존 입력으로 계속 |
| `e2e` | BE `/be-harness:e2e-test-loop` · FE `test-loop`의 E2E (`--unit-only`로 실행) · minmos E2E 메인 플로우 수집 · 풀스택 E2E 단계 |
| `simplify` | simplify-loop (BE 통합 스캐너의 simplify 항목·적용, FE 7.2, 풀스택 ②) |
| `reflect` | `--reflect` 플래그가 없을 때의 성찰 기본값 (`on` = 성찰 수행) |
