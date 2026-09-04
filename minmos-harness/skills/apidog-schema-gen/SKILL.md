---
name: apidog-schema-gen
description: "This skill should be used when the user asks to \"generate API schema from Apidog\", \"extract request response schema\", \"Apidog에서 스키마 뽑아줘\", \"API 스키마 생성\", \"엔드포인트 스키마 추출\", \"스키마 파일로 저장\", \"flat schema\", \"Apidog에 푸시\", \"Apidog 동기화\", \"API 문서 업데이트\", or mentions extracting JSON schema from Apidog OAS endpoints or pushing specs to Apidog. Reads Apidog OAS endpoint definitions, cross-references with Go codebase structs to catch missing fields, generates flat inline JSON schemas, and optionally pushes OpenAPI specs to Apidog via Import API."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, WebFetch, mcp__apidog__read_project_oas_w9of5k, mcp__apidog__read_project_oas_ref_resources_w9of5k, mcp__apidog__refresh_project_oas_w9of5k
user-invocable: true
---

# Apidog Schema Generator

Apidog OAS 엔드포인트 정의에서 request/response JSON 스키마를 추출하고, 모든 중첩 객체를 flat 인라인으로 펼쳐서 생성한다.

Apidog MCP 도구는 `mcp__apidog__read_project_oas_*` 패턴으로 세션 도구 목록에서 탐색한다 (이 프로젝트 기본: `..._w9of5k`).

## Language Rule

유저와의 모든 대화(AskUserQuestion, 안내, 설명, 확인)는 **한국어**로 진행한다.

## Prerequisites

### 필요 환경

- **Apidog MCP 서버**: OAS 읽기를 위해 필수
- **환경 변수** (Push 기능 사용 시): `APIDOG_ACCESS_TOKEN`, `APIDOG_PROJECT_ID`

> **MCP 판정**: 실제 MCP tool 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다 (상세: `/minmos-harness:doctor`).

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **Apidog MCP 연결 확인**: `mcp__apidog__read_project_oas_w9of5k` 호출 가능 여부와 응답을 확인한다.
   - 정상 응답이면 OK로 판정한다.
   - 호출 불가/실패면 현재 클라이언트의 MCP 설정 점검을 안내한다:
     > "Apidog MCP 서버에 연결할 수 없습니다. 사용하는 MCP 클라이언트 설정에 아래 서버를 등록하세요 (Claude/Codex는 `.mcp.json`, 일부 클라이언트는 별도 MCP 설정 위치):"
     > ```json
     > { "mcpServers": { "apidog": { "command": "npx", "args": ["-y", "apidog-mcp-server@latest", "--project-id=<YOUR_PROJECT_ID>"] } } }
     > ```
   - 유저에게 프로젝트 ID를 질문하고, `.mcp.json`을 쓰는 환경이면 동의 시 자동 추가, 별도 MCP 설정을 쓰는 환경이면 해당 위치 등록을 안내한다.
2. **환경 변수 확인** (Push 용): `echo "TOKEN=${APIDOG_ACCESS_TOKEN:+set}" "PROJECT=${APIDOG_PROJECT_ID:+set}"` — 미설정 시 설정 방법을 안내한다.
3. 결과를 요약 보고한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Apidog Schema Gen — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 연결 | OK / MISSING / FAIL | 실제 MCP 호출 기준 |
| Apidog MCP 응답 | OK / FAIL / SKIP | OAS 읽기 시도 |
| APIDOG_ACCESS_TOKEN | SET / UNSET | Push 기능용 |
| APIDOG_PROJECT_ID | SET / UNSET | Push 기능용 |
```

문제가 있으면 `--init` 실행을 안내한다.

### 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--init` | | 초기 세팅 후 종료 |
| `--doctor` | | 상태 진단 후 종료 |
| `--skip-doctor` | `-sd` | 실행 전 자동 doctor 점검을 건너뜀 |

(Push 옵션 `--folder`/`--merge`/`--keep`/`--new`/`--branch`/`--status`/`--dry-run`: `references/push-import.md` 참조)

## Step 1: Pre-flight Doctor

`--skip-doctor`/`-sd`가 **없으면** 위 `--doctor`와 동일한 점검을 자동 실행한다.

- 모두 OK → 한 줄 요약 후 Step 2로 진행
- BLOCKED 있음 → 누락 항목 안내 후 진행 여부를 사용자에게 질문
- `--skip-doctor`/`-sd` → 건너뛰고 바로 Step 2로 진행

## Step 2: Endpoint Selection

1. 유저가 인자로 경로와 method를 제공한 경우 → 바로 Step 3으로 진행한다.
2. 인자가 없거나 불완전한 경우 → "API 경로와 HTTP method를 알려주세요 (예: `GET /v1/carts`)" 라고 요청한다.
3. 경로만 있고 method가 없는 경우 → OAS를 읽어 해당 경로의 method 목록만 확인하고, 복수이면 유저에게 선택을 요청한다.

> **전체 API 목록을 나열하지 않는다.** 유저가 경로를 모르는 경우에만 OAS를 읽어 관련 키워드로 검색하여 후보를 좁혀 안내한다.

### Step 2.1: 경로 미존재 처리

OAS에서 해당 경로를 찾을 수 없는 경우 (신규 API 등):

1. 유저에게 알린다:
   > "Apidog에 `[METHOD] [PATH]` 경로가 존재하지 않습니다.
   > 코드베이스 기반으로 스키마를 생성하여 파일로 저장할까요?"
2. 동의하면 저장 경로를 질문한다:
   > "1. `docs/schemas/[endpoint-slug].json` (기본) 2. 직접 경로 지정"
3. **Step 3을 건너뛰고** Step 4(코드베이스 교차 검증)로 직접 진행한다 — 코드만으로 스키마를 생성한다.
   - Step 4에서 handler 를 찾으면 신규 구현 → push 시 status 추론값은 `developing` (Step 8.2.5).
   - handler 도 찾지 못하면 OAS·코드 어디에도 정의가 없어 **스키마를 만들 근거가 없다**. 이때는 사용자가 설계 스키마를 직접 제공한 경우에만 `designing` 으로 push 하고, 제공이 없으면 push 하지 않고 안내한 뒤 종료한다.
4. Step 6 출력 완료 후, 확정된 경로에 스키마 파일을 저장한다.
5. 유저가 거부하면 스킬을 종료한다.

## Step 3: Read Endpoint OAS

1. 해당 경로의 `$ref` 값을 확인한다.
2. `mcp__apidog__read_project_oas_ref_resources_w9of5k`로 상세 스키마를 가져온다.
3. 선택한 method의 `requestBody.content.application/json.schema`와 `responses.{statusCode}.content.application/json.schema`를 추출한다.
4. **현재 status 캡처**: 같은 operation 의 `x-apidog-status` 값을 함께 읽어 보관한다 (없으면 `developing` 으로 간주). Step 7의 status 확인과 Step 8.2.5의 "현재 status 유지"·다운그레이드 금지 판정이 이 값을 근거로 한다 — 여기서 읽지 않으면 뒤에서 확인할 방법이 없다.

## Step 4: Codebase Cross-Reference

OAS 스키마를 Go 코드베이스의 실제 struct 정의와 교차 검증하여 누락 필드를 보완한다.

1. **Handler struct 탐색**: 해당 엔드포인트의 handler 함수를 찾고, request/response에 바인딩되는 Go struct를 식별한다.
   - `Grep`으로 경로 패턴 또는 handler 함수명을 검색한다.
   - request struct: `json:"fieldName"` 태그가 있는 struct / response struct: handler에서 응답으로 반환되는 struct
2. **필드 비교**: Go struct의 `json` 태그 필드 목록과 OAS `properties` 키를 비교한다.
3. **누락 필드 보완**: Go struct에는 있지만 OAS에 없는 필드를 스키마에 추가한다.
   - 타입 매핑: `string`→`"string"`, `int/int64`→`"integer"`, `float64`→`"number"`, `bool`→`"boolean"`, `[]T`→`"array"`, struct→`"object"`
   - 포인터 타입(`*string` 등)은 optional로 간주한다.
   - 코드 내 validation 함수 등에서 enum 값이 확인되면 `enum` 배열을 추가한다.
   - 스키마에 `[코드 기준 추가]` 같은 태그를 붙이지 않는다 — 출처는 Step 6.2 비교 테이블에서 정리한다.
4. **불일치 보고**: OAS와 코드 간 타입/필드 차이는 출력 시 별도 안내한다.

> **우선순위**: 코드베이스가 OAS보다 우선한다. OAS에 없어도 코드에 있으면 포함하고, 타입 불일치 시에도 코드 기준으로 출력한다.

> **handler 를 찾지 못한 경우** — **OAS 에 해당 경로가 존재할 때만** 이 규칙을 적용한다 (코드에서 제거된 API). OAS 에도 없으면 Step 2.1의 안내를 따른다. 스키마를 새로 만들지 않는다. **deprecated 후보**로 판정하고 사용자에게 확인한다 — "코드에서 handler 를 찾지 못했습니다. 제거된 API 라면 Apidog 에서 삭제하는 대신 `deprecated` 로 표시합니다. 진행할까요?" 동의하면 Step 8에서 `references/push-import.md` 의 **deprecated push 특칙**(기존 정의 재발행 + status 만 변경)을 따른다.

## Step 5: Schema Analysis

OAS raw schema를 교차 검증 결과와 병합하여 분석한다.

**출력 원칙 — 항상 Flat**: 모든 중첩 객체는 예외 없이 flat 인라인으로 출력한다. `$ref` 분리를 하지 않는다. 동일 구조가 반복되더라도 매번 전체 필드를 펼친다.

> **핵심**: 유저가 스키마를 **한 번에 copy → Apidog에 붙여넣기** 할 수 있어야 한다. 각 섹션이 self-contained JSON schema여야 한다.

## Step 6: Schema Output

각 섹션은 독립적으로 copy 가능해야 한다.

### Step 6.1: Main Schema

Response Schema 1개 + (해당 시) Request Schema 1개. **코드 기준으로 완전한 스키마** — 코드에 존재하는 모든 필드 포함, 태그 없음.

### Step 6.2: OAS vs 코드 비교 테이블

Main Schema 하단에 OAS와 코드 간 차이를 별도 테이블로 정리한다 (Apidog OAS 업데이트 참고용):

```
### OAS vs 코드 비교

| 위치 | 필드명 | OAS | 코드 | 비고 |
|------|--------|-----|------|------|
| data[] | publishedStatus | 없음 | string | 코드에만 존재 |
| data[] | discountRate | integer | number (float64) | 타입 불일치 |
| data[] | type -> productType | type (string) | productType (string) | 키 이름 불일치 |
| query | publishedStatus | 없음 | string | 코드에만 존재 |
```

분류: **코드에만 존재** / **OAS에만 존재** (deprecated 가능성) / **타입 불일치** (스키마는 코드 기준) / **키 이름 불일치**

### Step 6.3: Query Parameters (GET 엔드포인트)

query parameters는 **CSV 형태, 헤더 행 없이** 출력한다. 컬럼 순서 (고정):

```
이름,유형,필수,예시,고정 파라미터,설명
```

- 이름(camelCase) / 유형(JSON Schema 타입) / 필수(`true`/`false`) / 예시(enum이면 첫 값) / 고정 파라미터(enum 값 쉼표 나열, 없으면 빈 칸) / 설명(한글)

출력 후: ① "각 파라미터별 JSON Schema도 출력할까요?" 질문 ② 선택 시 개별 출력 ③ 완료 후 선택하지 않은 옵션 안내.

> 상세 형식은 `references/extraction-patterns.md`의 "Query Parameters (GET)" 섹션 참조.

### Step 6.4: Polymorphic 필드 처리 (Apidog schema composition)

응답에 `interface{}` 또는 `type` discriminator 기반 다형성 필드가 있는 경우:

| Apidog 옵션 | OpenAPI | 의미 | 사용 시점 |
|------------|---------|------|----------|
| XOR | `oneOf` | 정확히 하나만 만족 | `type` discriminator 기반 다형성 (**기본 선택**) |
| OR | `anyOf` | 하나 이상 만족 | 여러 형태가 동시 가능한 경우 (드묾) |
| AND | `allOf` | 모두 만족 | 상속/확장 패턴 |

출력 방식:
1. Main Schema에서 해당 필드를 composition placeholder로 표기한다 (각 variant 내부에 full schema 포함):
   ```json
   "extraInfo": {
     "oneOf": [
       { "title": "variant_name", "type": "object", "properties": { ... } },
       { "title": "variant_name", "type": "object", "properties": { ... } }
     ]
   }
   ```
2. Main Schema 하단에 `extraInfo[0] — variant_name` 형태로 각 variant의 full schema를 **별도 섹션**에 flat 인라인 출력한다 (Apidog의 해당 `oneOf` 인덱스에 직접 붙여넣기 가능).
3. variant 내부의 중첩 객체도 재사용되지 않으면 인라인으로 펼친다.

## Step 7: Confirmation

결과를 유저에게 보여주고 확인 받는다: ref 분리 대상 적절성 / ref 네이밍 / 누락 필드 여부.

Push 로 이어질 경우 **적용할 status 도 이 단계에서 함께 보여주고** 확인받는다 (별도 질문 단계를 만들지 않는다).

> 이 확인을 하려면 status 가 먼저 정해져 있어야 한다. **Step 7 진입 전에** `references/push-import.md` 의 **Step 8.2.5(status 결정)** 를 읽어 값을 확정한다 — 근거는 Step 3.4에서 캡처한 현재 status 와 Step 4의 handler 탐색 결과다. 여기서 확정한 값을 Step 8로 **그대로** 넘긴다 (재계산하지 않는다).


> "적용할 status: `{값}` ({한국어 라벨}) — {추론 사유}. 이대로 진행할까요? 바꾸려면 값을 지정해주세요 (10종: `references/push-import.md` Step 8.2.5)."

피드백 반영 후 최종 스키마와 status 를 확정한다.

## Step 8: Apidog Push (선택)

스키마 확정 후 "Apidog에 자동 푸시할까요?"를 물어본다.

> 유저가 처음부터 "Apidog에 푸시해줘", "Apidog 동기화" 등을 요청한 경우, Step 1~7을 모두 수행한 후 자동으로 Step 8을 진행한다.

> Step 8 진입 시 MUST: 같은 폴더의 `references/push-import.md`를 Read하고 절차(환경 변수 확인 → 폴더 결정 → **status 결정** → YAML 생성 → Import API 호출 → 실패 시 MCP Fallback 1회 → 결과 보고)를 따른다.

## Key Rules

| 항목 | 규칙 |
|------|------|
| `pagination` 객체 | 인라인 유지 (ref 분리 안 함) |
| `data` wrapper | 인라인 유지 |
| `null` 타입 필드 | nullable로 표기: `"type": ["{inferredType}", "null"]` (상세: `references/extraction-patterns.md` Pattern 4) |
| `required` 배열 | OAS 원본의 required 필드를 그대로 유지 |
| 빈 `items: {}` | 그대로 유지 (any type array) |
| `example` 필드 | 스키마 출력에서 제외 |
| `deprecated` 엔드포인트 | 유저에게 deprecated 경고 표시 |
| 엔드포인트 삭제 요청 | Apidog 은 import 로 삭제할 수 없다. 삭제 대신 `x-apidog-status: deprecated` push 로 대체한다 (기존 정의 재발행 — 빈 스펙 덮어쓰기 금지) |
| Push 시 status | 항상 명시한다. 생략 시 기존 status 보존 여부가 보장되지 않는다 (Step 8.2.5) |
| 코드 vs OAS 불일치 | 코드 기준 우선. 불일치는 출력 하단에 별도 안내 |
| 코드 추가 필드 | 스키마에 태그 없이 포함. 출처는 비교 테이블(Step 6.2)에서 정리 |
| Go 포인터 타입 | optional로 간주 (required에 포함하지 않음) |

## Output Customization

- **File output**: 스키마를 파일로 저장 (경로 지정 가능)
- **Go struct hint**: 각 스키마에 대응하는 Go struct 이름 주석 추가

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/extraction-patterns.md` | Step 5~6 (추출 상세 패턴, 엣지 케이스, 실제 예시) |
| `references/push-import.md` | Step 8 진입 시 (Push 절차 + Import API 레퍼런스) |
