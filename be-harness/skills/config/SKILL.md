---
name: config
description: "be-harness project profile(.claude/be-harness.local.md)의 설정 값을 조회하고 키 단위로 수정한다. '프로필 설정 확인해줘', '설정 값 바꿔줘', '{키} 값 뭐야', '{키}를 {값}으로 바꿔줘' 요청 시, init 재실행 없이 값 하나만 보거나 고칠 때 사용. 파일 생성·환경 진단은 하지 않는다 (init·doctor 담당)."
allowed-tools: Read, Edit, AskUserQuestion
user-invocable: true
argument-hint: "[{키} | {키}={값} …]"
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/config.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# be-harness Config

profile(`.claude/be-harness.local.md`)의 설정 값을 **조회**하고 `{키}={값}` 배치로 **수정**한다. `init`을 다시 돌리지 않고 값 하나를 보거나 바꾸는 경로다.

호출: `/be-harness:config` (전체 조회) · `/be-harness:config {키}` (단일 조회) · `/be-harness:config {키}={값} [{키}={값} …]` (배치 수정)

## 원칙

- 파일을 **생성하지 않는다** — 없으면 `/be-harness:init` 안내. 명령 실행·자동 감지·환경 점검도 하지 않는다 (`doctor` 담당).
- **쓰는 파일은 `{PROFILE}` 하나뿐이다.** 읽는 파일은 `{PROFILE}`·`{PLUGIN_ROOT}/PROFILE.md`·codex-mode.md §2.1(`codexModels` 관련 시)·머리말의 Project Overrides 파일뿐이며 Overrides는 편집하지 않는다. `~/.codex/config.toml`(시크릿)·start-workflow 상태 파일은 읽지도 쓰지도 출력하지도 않는다.
- 수정은 **frontmatter 안**에서, 대상 키의 줄만 바꾼다. 본문(Project Notes)·구분선·키 순서·각 줄의 EOL은 바이트 그대로.
- **중립 주석 줄·꼬리 주석은 어떤 규칙도 삭제·변형하지 않는다.** 삭제가 필요한 변경은 비지원으로 차단하고 직접 편집을 안내한다. 유일한 예외 = 플레이스홀더 활성화(Step 4 ③): 주석 처리된 `# {키}:` 줄의 선두 `# `만 벗긴다.
- `init`이 수용하는 값은 거부하지 않는다. 문서화된 한계 3건 — 배열 원소 안의 쉼표, 따옴표 없는 값 앞뒤 공백(따옴표로 표현: `key=" v"`), codexModels의 provider·model이 YAML에서 문자열로 읽히지 않는 값(Step 2 값 해석 — §2.1 저장 형태를 지키기 위해 거부).
- 알 수 없는 키(점 표기 `codexModels.review`, `--플래그` 포함)는 쓰기 거부, 조회는 `⚠ 알 수 없는 키` 행으로 표시.
- 배치는 전건 검증 후 **한 번의 Edit**로 반영한다 — 전부 `DONE` 아니면 전부 미반영.
- 플레이스홀더(본문에서는 이 이름만 사용):
  - `{PLUGIN_ROOT}` = `${CLAUDE_PLUGIN_ROOT}` (이 플러그인 루트)
  - `{PROFILE}` = `.claude/be-harness.local.md`
  - `{Q_MAX}` = 2 (실행당 AskUserQuestion 예산 — 재입력 질문 포함)

## 전제 조건

| 항목 | 미충족 시 |
|------|----------|
| `{PROFILE}` 존재 | `BLOCKED:NO_PROFILE` — "1. `/be-harness:init`으로 profile 생성(사용자) 2. 종료" |
| `{PLUGIN_ROOT}/PROFILE.md` (스키마 canonical — 키별 허용값·빈 값 의미·프리셋 표) | Step 1에서 MUST Read. 읽기 실패 → `FAIL` (플러그인 설치 이상) |
| `{PLUGIN_ROOT}/skills/start-workflow/references/codex-mode.md` §2.1 | 인자 또는 profile에 `codexModels`가 있으면 Step 1에서 MUST Read (compact 문법·검증·병합) |

## 키

키 분류는 아래 마커 안이 canonical이며 `PROFILE.md` 프론트매터의 키 집합과 양방향으로 일치한다(레포 가드가 검사). 허용값·빈 값의 의미·프리셋 기본값은 `PROFILE.md`를 따른다(구현 시 init 선택지와 동일).

<!-- config:keys-begin — scripts/check-plugins.sh §7 parity 대상 -->
| 타입 | 키 | 값 규칙 |
|------|----|--------|
| enum | `preset` (go \| node \| custom) · `language` (ko \| en) · `codexMode` (none \| mix \| max) | trim 후 exact — 빈 값 무효 |
| bool | `e2eEnabled` | true \| false exact |
| string | `buildCommand` `testCommand` `lintCommand` `typeCheckCommand` `makeTestCommand` `runServerCommand` `serverUrl` `apiDocsPath` `e2eLockDir` `reportDir` `mainBranch` `featureBranchPrefix` `hotfixBranchPrefix` `commitCoAuthor` | 자유 문자열 — 빈 문자열 유효 |
| array | `sourceDirs` `testDirs` `commitPrefixes` `projectConventions` | 쉼표 구분 (원소 안의 쉼표 비지원) — 빈 배열 유효 |
| block | `codexModels` | codex-mode.md §2.1 compact — 슬롯별 레코드 |
<!-- config:keys-end -->

문서 기본값(파일에 없을 때 조회에 표시 — 출처 병기):

| 키 | 기본값 | 출처 |
|----|-------|------|
| language | ko | init |
| codexMode | mix | codex-mode.md §2 |
| codexModels | 기본 4슬롯 | codex-mode.md §1 기본값 표 |
| reportDir | .claude/harness-reports | PROFILE.md |
| e2eLockDir | 자동 해석 | PROFILE.md |
| e2eEnabled | true | init |
| projectConventions | ["CLAUDE.md"] | init |

그 외 키: `preset: go|node`면 PROFILE.md 프리셋 표 값(출처 `preset`), 아니면 `미설정`.

## Step 1: 로드·구조 판정

1. `{PLUGIN_ROOT}/PROFILE.md`를 Read한다 (MUST — 키별 허용값·빈 값 의미·프리셋 표의 canonical). 인자 원문 또는 profile에 `codexModels`가 있으면 `{PLUGIN_ROOT}/skills/start-workflow/references/codex-mode.md` §2.1도 MUST Read한다 (레코드 패턴·effort enum — Step 2·3 검증과 조회의 `⚠ INVALID_SLOT` 판정에 필요).
2. `{PROFILE}`을 Read한다. 없으면 `BLOCKED:NO_PROFILE` + 선택지 "1. `/be-harness:init`으로 profile 생성(사용자) 2. 종료".
3. **EOL·구분선**: EOL은 각 줄의 LF 또는 CRLF(줄별, 혼합 허용). 1행이 `---`(뒤 공백·탭 허용) + EOL이고, 그 다음으로 `---`(뒤 공백·탭 허용) + EOL **또는 파일 끝**이 처음 나오는 줄이 닫는 구분선이다. 본문(닫는 구분선 뒤)은 불투명 — 본문의 `---`는 무시. 여는/닫는 구분선이 없거나 루트 키가 중복되면 `BLOCKED:INVALID_PROFILE`(전역 — 수정은 전부 차단. 조회: 닫는 구분선이 없으면 표 없이 종료, 루트 키 중복이면 그 키 행의 값 대신 `⚠ 중복 키(N회)` 표시. 선택지: "1. 직접 편집 후 재호출 2. `/be-harness:init` 실행(사용자)").
4. **줄 분류**(frontmatter 안. 각 줄의 EOL은 분류와 무관하게 그 줄에 붙은 채 보존):

| 분류 | 형태 |
|------|------|
| 루트 줄 | 열-0 `키:` — 키는 `[A-Za-z0-9_-]+` (따옴표 키 `"preset":`·앵커·태그는 비지원) |
| 자식 줄 | 들여쓴 `- 항목` 또는 `슬롯: {…}` |
| 플레이스홀더 줄 | 분류표 키 K의 활성 루트 줄이 없을 때 **첫 번째** 열-0 `# K:` 줄(정확히 `# ` 한 칸 뒤 키·콜론 — `#   review:`처럼 들여쓴 줄은 아님). 구조 줄이며 중립 줄이 아니다. 잔여부(`# K:` 뒤)는 활성 줄과 같이 구분 공백 + 값 렉심 + 꼬리 주석으로 읽는다 |
| 중립 줄 | 그 외 주석만 있는 줄(들여쓰기 무관 — 두 번째 이후의 동명 플레이스홀더, 활성 키가 있는 키의 `# K:`, 분류표 밖 키의 주석 포함)·빈 줄 |

   - **꼬리 주석** = 따옴표(`"…"`·`'…'`) 밖에서 공백이 선행하는 `#`부터 줄 끝 (`release#1`은 값, `release #x`는 값 + 주석, `Bot (team # owner)`는 `Bot (team` + 주석). flow `[…]`·`{…}` 안에서도 같다 — 그런 줄은 flow가 닫히지 않아 비지원 레이아웃이 된다.
   - **값 렉심** = `키:` 뒤 구분 공백을 제외한 곳부터 꼬리 주석/후행 공백을 제외한 곳까지. 구분 공백·후행 공백·꼬리 주석은 바이트 보존.
   - 블록 범위 = 키 줄부터 **연속된** 자식 줄까지. 그 뒤의 중립 줄은 블록 밖. 키 줄과 첫 자식 사이의 중립 줄, 블록 범위 밖에 남는 들여쓴 자식형 줄은 비지원 레이아웃(대상일 때 `BLOCKED:UNSUPPORTED_LAYOUT`).
5. **레이아웃 매트릭스** — 수정 대상 키에만 적용(대상이 아닌 키의 비지원 줄은 바이트 보존, 조회는 ⚠):

| 타입 | 지원 저장 형태 | 그 외 → `BLOCKED:UNSUPPORTED_LAYOUT` |
|------|--------------|------|
| enum·bool·string | 1줄 스칼라: bare / `"…"` / `'…'` / 빈 렉심·`~`·`null`(조회 ⚠, 수정은 렉심 교체 허용) | 블록 스칼라(`\|`·`>`), 여러 줄, 앵커·태그, 따옴표 키 |
| array | 1줄 flow `[…]`(따옴표·이스케이프 인지, 후행 쉼표 허용) / 블록 시퀀스 = `키:` + 연속 자식 `  - 항목` | 여러 줄 flow, 중첩 시퀀스, 자식 사이의 중립 줄 |
| block | `codexModels:` + 연속 자식 `  {슬롯}: { flow 1줄 }` | 루트 flow map `codexModels: {…}`, 중첩 블록 슬롯, 자식 사이의 중립 줄 |

   플레이스홀더 줄의 잔여부에도 같은 매트릭스를 적용한다 — 블록 타입 플레이스홀더는 빈 잔여 렉심만 지원(자식 0개로 취급). 저장된 codexModels 레코드가 무효(알 수 없는 슬롯·중복·필드 누락/초과·패턴 불일치·`tiered`가 `review` 밖)면 조회 `⚠ INVALID_SLOT`, `codexModels`를 대상으로 한 수정만 `BLOCKED:INVALID_PROFILE`.

## Step 2: 인자 해석

`$ARGUMENTS` 원문을 스캐너로 항목 분리 → 디코딩 → 모드 판정.

| 입력 | 모드 |
|------|------|
| (없음) | 전체 조회 → (대화형) 수정 입력 질문 / (비대화형) 조회만 `DONE` |
| 항목 1개, `=` 없음 | 단일 조회 |
| 모든 항목이 `{키}={값}` | 배치 수정 |
| 조회와 할당 혼합 · 조회 항목 2개 이상 | 무효(Step 3.1) |

- **스캐너**(상태 = 밖 / `"…"` 안 / `'…'` 안): 밖에서 공백·탭·CR·LF는 **항상** 항목 구분(`key= v` → `key=`와 `v` = 혼합 → 무효). `"…"` 안은 `\"`·`\\`만 이스케이프(`'`는 문자), `'…'` 안은 모두 문자(`\` 포함). **입력 전체 무효**: 입력 끝에서 따옴표 미종결 · `\` 뒤에 문자 없음 · 탭·CR·LF 외 제어 문자 · 따옴표 안의 탭·CR·LF · 항목 전체 또는 값 전체를 감싸는 위치 이외의 따옴표(`a"b"c`, `key=x"y"`). 유니코드 허용.
- **디코딩(순서 고정)**: ① 항목 전체가 짝 따옴표면 제거(큰따옴표였으면 `\"`→`"`, `\\`→`\` 해제) ② 첫 `=`로 키/값 분리(키 빈 문자열 무효, `=` 없으면 조회 항목) ③ 값 전체가 짝 따옴표면 제거 + 해제(①에서 해제했으면 재해제 없음) ④ 같은 키 중복 무효. 키는 대소문자 exact. 예: `"buildCommand=echo \"x\""` → `echo "x"` · `buildCommand='C:\'` → `C:\` · `commitPrefixes="[Add, Fix:, WIP]"`.
- **값 해석(타입별)**: enum·bool = trim 후 exact(`key=` 무효) / string = 그대로(`key=` → 빈 문자열) / array = 감싼 `[ ]` 선택 제거 → `,` 분리 → 원소 trim → 원소를 감싼 짝 따옴표 제거; 빈 원소(`a,,b`·후행 쉼표) 무효; `key=`·`key=[]` → 빈 배열 (원소 따옴표는 값 전체가 따옴표로 감싸인 경우에만 — `sourceDirs=["a","b"]`는 스캐너 무효, `sourceDirs=a,b` 또는 `sourceDirs='["a","b"]'`) / block = codex-mode.md §2.1 compact `{슬롯}={provider}/{model}[@{effort}]` 쉼표 나열, `default` = 슬롯 삭제, `tiered`는 `review`만. provider·model은 §2.1 저장 형태대로 bare로 기록되므로 YAML이 문자열로 읽지 않는 값(null·true·false·~·숫자로 읽히는 값·`-`, 끝이 `:`)은 무효.
- **기록 형태**: enum·bool bare / string 큰따옴표(내부 `"`·`\` 이스케이프, 빈 문자열은 `""`) / array flow `["a", "b"]`(원소는 string 기록 형태 — 큰따옴표 + 이스케이프) — 기존 블록 시퀀스는 블록 유지(자식 `  - "항목"`도 같은 이스케이프), 빈 배열은 flow `[]` / block = `codexModels:` + `  {슬롯}: { provider: …, model: …[, effort: …] }`.
- **인자 없음**: 조회 표 출력 → (비대화형) `DONE` / (대화형) Q1:
  > "1. 변경 없이 종료 2. 값 변경 — Other에 `{키}={값} …` 전체 입력"
  Other 텍스트 → Step 3. 선택 2(텍스트 없음) → Q2 "1. 취소 / Other에 입력" → 텍스트 없으면 `DONE`. 질문은 실행당 `{Q_MAX}`회까지(Step 3 재입력 포함).

## Step 3: 검증 (판정 순서 고정)

**Step 3.1 입력 오류** — 스캐너 오류·혼합 모드·알 수 없는 키(할당 항목에만 — 조회 항목의 알 수 없는 키는 `⚠ 알 수 없는 키` 행 + `DONE`)·값 불일치·codexModels compact 무효 → 배치 전체 무효(파일 불변).
- 대화형: 항목별 사유 + 허용값을 고지하고 배치 전체 재입력을 묻는다(예산 내 1회): "1. 취소 / Other에 전체 재입력".
- 비대화형: 즉시 `BLOCKED:INVALID_VALUE` + 무효 항목 경고 (codex-mode.md §2.1 "무시 + 경고, profile 불변"과 동등).

| 종료 조건 | 결과 |
|----------|------|
| 재입력이 유효 | Step 3.2로 진행 |
| 재입력도 무효 (재입력은 1회뿐) | `BLOCKED:INVALID_VALUE` — "1. 올바른 값으로 재호출 2. `/be-harness:init`" |
| 재입력 전에 `{Q_MAX}` 소진 (Q1·Q2 사용 후) | `BLOCKED:INVALID_VALUE` — 같은 선택지 |
| 취소 | `DONE` (변경 없음) |

**Step 3.2 대상 키의 구조 오류** — 입력이 유효할 때만 판정. 재입력 없음, 예산 미소모.
- 비지원 레이아웃(활성 줄·플레이스홀더 잔여부) → `BLOCKED:UNSUPPORTED_LAYOUT`
- 저장된 codexModels 블록 무효 → `BLOCKED:INVALID_PROFILE`
- **주석 소실 변경** — 꼬리 주석이 달린 자식 줄이나 키 줄을 삭제해야 하는 경우(슬롯 `default`, 배열 축소, 전 슬롯 삭제) → `BLOCKED:UNSUPPORTED_LAYOUT`

하나라도 있으면 배치 전체 차단(파일 불변) + 해당 줄 인용 + 선택지 "1. 직접 편집 후 재호출 2. `/be-harness:init` 실행(사용자)".

`codexModels` 입력은 Step 1에서 Read한 codex-mode.md §2.1 규칙(레코드 패턴·effort enum·원자성)으로 파싱한 뒤 **슬롯 단위**로 병합한다.

## Step 4: 렌더 + 1회 Edit

먼저 **변경 없음 판정**: 대상 키의 새 값을 기록 형태로 만든 결과가 현재 줄과 바이트 동일하면(codexModels는 병합 결과의 슬롯 집합·레코드가 현재와 같으면 — 없는 슬롯의 `default`, 활성 블록 없이 결과 슬롯 0개 포함) 그 키는 변경 없음이며 어떤 줄도 건드리지 않는다. 모든 대상 키가 변경 없음이면 Edit 없이 Step 5 "변경 없음". 나머지 키만 frontmatter 줄 배열의 사본에서 변환한다. 중립 줄·꼬리 주석은 어떤 규칙도 건드리지 않는다(③이 전환하는 플레이스홀더 줄은 중립 줄이 아니다).

| 규칙 | 조건 | 변환 |
|------|------|------|
| ① | 활성 키 + 1줄 스칼라/flow | 값 렉심만 기록 형태로 교체. 구분 공백·후행 공백·꼬리 주석·EOL 보존. 렉심이 비어 있었으면(`키:` 뒤 공백 전부 = 구분 공백) `키:` + 공백 1 + 새 렉심, 꼬리 주석이 있으면 이어서 (원래 구분 공백에서 1개 뺀 나머지, 없으면 공백 1) + 꼬리 주석, 없으면 아무것도 덧붙이지 않는다 |
| ② | 활성 키 + 블록(시퀀스·codexModels) | 자식 줄을 정규 형태로 재구성 — 시퀀스 `  - "항목"`, codexModels 슬롯 줄. 들여쓰기·구분 공백·꼬리 주석·EOL은 같은 위치(시퀀스 i번째→i번째)/같은 슬롯 이름의 기존 자식에서 유지, 신규 항목·슬롯은 마지막 자식 뒤에 추가(들여쓰기·구분 공백 = 마지막 기존 자식과 동일, 자식 0개면 공백 2·공백 1; 꼬리 주석 없음; EOL = 대상 키 줄). 주석 없는 줄만 삭제(있으면 Step 3.2에서 차단). 슬롯 0개 → 키 줄 제거(꼬리 주석 있으면 차단). 빈 배열 → 자식 삭제 + 키 줄에 `[]` |
| ③ | 키 부재 + 플레이스홀더 줄 | 선두 `# `만 제거해 활성 키 줄로 전환한 뒤 ①(스칼라/flow) 또는 ②(블록: 자식 0개에서 슬롯 줄을 그 줄 바로 뒤에 삽입 — 병합 결과 슬롯 0개면 변경 없음, 플레이스홀더 불변) 적용. 그 줄의 꼬리 주석·EOL 보존. **뒤따르는 주석 줄(예시 레코드·설명)은 손대지 않는다** — 새 자식 줄 뒤에 남아 블록 밖 중립 줄이 된다 |
| ④ | 그 외 | 닫는 구분선 직전에 삽입 — 스칼라 `키: 값`, 배열 flow, codexModels 키 줄 + 슬롯 줄(EOL = 닫는 구분선 줄의 것, 그 줄에 종결자가 없으면 여는 구분선 줄의 것) |

렌더 후 자체 검증: 루트 키 중복 0 · 대상 키 값이 기록 형태와 일치 · 변경 대상 줄 외 바이트 동일. 통과하면(변경 키가 1개 이상일 때만) 여는 구분선부터 닫는 구분선까지 전체를 old_string으로 **한 번의 Edit**. Edit 실패(Read 이후 파일 변경·old_string 비유일) → `FAIL`, 파일 불변.

## Step 5: 보고

수정 결과 표(`키 | 이전 | 이후 | 상태` — 이전/이후 셀은 조회 셀 규칙 그대로, 부재 키는 `(없음)`) — 배치는 전부 `DONE` 또는 전부 `BLOCKED`/`FAIL`. 변경 0건(동일 값) → "변경 없음" `DONE`. 끝에 "`/be-harness:doctor`로 확인" 1줄. `codexMode`/`codexModels`를 바꿨으면 고지: "진행 중·재개되는 워크플로우는 상태 파일 값을 유지하며 새 값은 다음 실행부터 적용".

## 출력 형식

조회(전체/단일):

```markdown
## be-harness Config — `.claude/be-harness.local.md`
| # | 키 | 값 | 출처 | 비고 |
|---|----|----|------|------|
| 1 | preset | go | profile | |
| 2 | typeCheckCommand | "" | profile | 비어 있으면 해당 단계 SKIP (PROFILE.md) |
| 3 | codexModels | (기본) | 기본값 | 4슬롯 기본 — 상세: `config codexModels` · codexMode none이면 N/A |
| 4 | reportDir | (없음) → .claude/harness-reports | 기본값 | |
| — | ⚠ fooBar | x | 알 수 없는 키 | 어떤 스킬도 읽지 않음 |
변경: `/be-harness:config {키}={값} …` · 파일 생성/전체 재설정: `/be-harness:init`
```

- 출처: `profile`(파일 명시 — 빈 문자열도 profile; 비고 = PROFILE.md 해당 키 주석의 빈 값 의미) / `preset`(preset go|node의 PROFILE.md 프리셋 표 값) / `기본값`(문서 기본값 표) / `미설정`(그 외).
- 셀: 값 렉심만(꼬리 주석·구분 공백 제외), `|`는 `\|`, 블록 시퀀스는 flow 표기로 한 셀. `codexModels`는 `(N슬롯 설정)`으로 요약하고 단일 조회 시 슬롯 표(`review` · `explore` · `judge` · `write`; 생략 슬롯 = `기본값`; 모델명은 profile 값만 표시).
- 타입 판정: string 키는 `""` 유효, `~`/`null`/빈 렉심 → `⚠ 타입 불일치`; enum·bool 키는 허용값 밖(따옴표 포함) → `⚠ 타입 불일치`; array 키는 flow/블록 시퀀스 외 → `⚠ 타입 불일치`; 비지원 레이아웃 → `⚠ 비지원 레이아웃(수정 불가)`; 무효 슬롯 → `⚠ INVALID_SLOT`. 전부 읽기 전용 표시.
- `language` 비고: "특화 하네스 오버레이가 고정할 수 있음".

수정:

```markdown
## be-harness Config — 수정 결과
| 키 | 이전 | 이후 | 상태 |
|----|------|------|------|
| codexMode | mix | max | DONE |
| codexModels | (기본) | (1슬롯 설정) review=zai/glm-5.3@high | DONE |
`/be-harness:doctor`로 확인. 진행 중·재개되는 워크플로우는 상태 파일 값을 유지하며 새 값은 다음 실행부터 적용.
```

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 조회 완료 / 수정 반영 / 취소·변경 없음 |
| `BLOCKED:NO_PROFILE` | `{PROFILE}` 없음 → `init` 안내 |
| `BLOCKED:INVALID_PROFILE` | 구분선 없음·루트 키 중복(전역) / 저장된 codexModels 블록 무효(키 범위) |
| `BLOCKED:UNSUPPORTED_LAYOUT` | 대상 키의 저장 형태 비지원 / 주석 소실 변경 |
| `BLOCKED:INVALID_VALUE` | 입력 오류 — 비대화형 즉시 / 대화형 재입력도 무효 또는 `{Q_MAX}` 소진 |
| `FAIL` | Edit 실패(파일 변경·비유일) / PROFILE.md 읽기 실패 |

## References

- `{PLUGIN_ROOT}/PROFILE.md` — Step 1 MUST Read: 키별 허용값·빈 값 의미·프리셋 기본값·읽기 우선순위.
- `{PLUGIN_ROOT}/skills/start-workflow/references/codex-mode.md` §2.1 — 인자 또는 profile에 `codexModels`가 있으면 Step 1에서 MUST Read: compact 문법·레코드 검증·슬롯 병합.
