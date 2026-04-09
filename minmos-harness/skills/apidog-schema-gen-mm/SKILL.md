---
name: apidog-schema-gen-mm
description: "This skill should be used when the user asks to \"generate API schema from Apidog\", \"extract request response schema\", \"Apidog에서 스키마 뽑아줘\", \"API 스키마 ��성\", \"엔드포인트 스��마 추출\", \"스키마 파일로 저장\", \"flat schema\", \"Apidog에 푸시\", \"Apidog 동기화\", \"API 문서 업데이트\", or mentions extracting JSON schema from Apidog OAS endpoints or pushing specs to Apidog. Reads Apidog OAS endpoint definitions, cross-references with Go codebase structs to catch missing fields, generates flat inline JSON schemas, and optionally pushes OpenAPI specs to Apidog via Import API."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, WebFetch, mcp__apidog__read_project_oas_w9of5k, mcp__apidog__read_project_oas_ref_resources_w9of5k, mcp__apidog__refresh_project_oas_w9of5k
user-invocable: true
---

# Apidog Schema Generator

Apidog OAS 엔드포인트 정의에서 request/response JSON 스키마를 추출하고, 모든 중첩 객체를 flat 인라인으로 펼쳐서 생성한다.

## Language Rule

유저와의 모든 대화(AskUserQuestion, 안내, 설명, 확인)는 **한국어**로 진행한다.

---

## Prerequisites

### 필요 환경
- **Apidog MCP 서버**: OAS 읽기/쓰시를 위해 필수
- **환경 변수** (Push 기능 사용 시):
  - `APIDOG_ACCESS_TOKEN`: Apidog Personal Access Token
  - `APIDOG_PROJECT_ID`: 대상 프로젝트 ID

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **Apidog MCP 확인**: `.mcp.json` 또는 프로젝트 설정에 `apidog` MCP가 등록되어 있는지 `Glob`/`Read`로 확인한다.
   - 없으면 안내:
     > "Apidog MCP 서버가 설정되어 있지 않습니다. `.mcp.json`에 아래 설정을 추가하세요:"
     > ```json
     > {
     >   "mcpServers": {
     >     "apidog": {
     >       "command": "npx",
     >       "args": ["-y", "apidog-mcp-server@latest", "--project-id=<YOUR_PROJECT_ID>"]
     >     }
     >   }
     > }
     > ```
   - 유저에게 프로젝트 ID를 질문하고, 동의 시 `.mcp.json`에 자동 추가한다.
2. **환경 변수 확인** (Push 용):
   ```bash
   echo "TOKEN=${APIDOG_ACCESS_TOKEN:+set}" "PROJECT=${APIDOG_PROJECT_ID:+set}"
   ```
   - 미설정 시 설정 방법을 안내한다.
3. 결과를 요약 보고한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Apidog Schema Gen — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 등록 | OK / MISSING | .mcp.json 확인 |
| Apidog MCP 응답 | OK / FAIL | OAS 읽기 시도 |
| APIDOG_ACCESS_TOKEN | SET / UNSET | Push 기능용 |
| APIDOG_PROJECT_ID | SET / UNSET | Push 기능용 |
```

- **MCP 응답 확인**: `mcp__apidog__read_project_oas_w9of5k`를 한 번 호출하여 정상 응답이 오는지 확인한다.
- 문제가 있으면 `--init`을 실행하라고 안내한다.

---

## Execution Flow

### Phase 1: Endpoint Selection

1. 유저가 인자로 경로와 method를 제공한 경우 → 바로 Phase 2로 진행한다.
2. 인자가 없거나 불완전한 경우 → 유저에게 "API 경로와 HTTP method를 알려주세요 (예: `GET /v1/carts`)" 라고 요청한다.
3. 경로만 있고 method가 없는 경우 → OAS를 읽어 해당 경로의 method 목록만 확인하고, 복수이면 유저에게 선택을 요청한다.

> **전체 API 목록을 나열하지 않는다.** 유저가 경로를 모르는 경우에만 OAS를 읽어 관련 키워드로 검색하여 후보를 좁혀 안내한다.

### Phase 1.5: 경로 미존재 처리

OAS에서 해당 경로를 찾을 수 없는 경우 (신규 API이거나 아직 Apidog에 등록되지 않은 경우):

1. 유저에게 알린다:
   > "Apidog에 `[METHOD] [PATH]` 경로가 존재하지 않습니다.
   > 코드베이스 기반으로 스키마를 생성하여 파일로 저장할까요?"
2. 유저가 동의하면 저장 경로를 질문한다:
   > "스키마 파일을 어디에 저장할까요?
   > 1. `docs/schemas/[endpoint-slug].json` (기본)
   > 2. 직접 경로 지정"
3. 유저 선택에 따라 파일 경로를 확정한다.
4. **Phase 2를 건너뛰고** Phase 2.5 (코드베이스 교차 검증)로 직접 진행한다. OAS 스키마 없이 코드만으로 스키마를 생성한다.
5. Phase 4 출력 완료 후, 확정된 경로에 스키마 파일을 저장한다.

> 유저가 거부하면 스킬을 종료한다.

### Phase 2: Read Endpoint OAS

1. 해당 경로의 `$ref` 값을 확인한다.
2. `mcp__apidog__read_project_oas_ref_resources_w9of5k`로 상세 스키마를 가져온다.
3. 선택한 HTTP method의 `requestBody.content.application/json.schema`와 `responses.{statusCode}.content.application/json.schema`를 추출한다.

### Phase 2.5: Codebase Cross-Reference

OAS 스키마를 가져온 후, Go 코드베이스의 실제 struct 정의와 교차 검증하여 OAS에 누락된 필드를 보완한다.

#### 절차

1. **Handler struct 탐색**: 해당 엔드포인트의 handler 함수를 찾고, request/response에 바인딩되는 Go struct를 식별한다.
   - `Grep`으로 경로 패턴 또는 handler 함수명��� 검색한다.
   - request struct: `json:"fieldName"` 태그가 있는 struct
   - response struct: handler 함수 내에서 응답으로 반환되는 struct
2. **필드 비교**: Go struct의 `json` 태그 필드 목록과 OAS 스키마의 `properties` 키를 비교한다.
3. **누락 필드 보완**: Go struct에는 존재하지만 OAS에 없는 필드를 스키마에 추가한다.
   - Go 타입 → JSON Schema 타입 매핑: `string` → `"string"`, `int/int64` → `"integer"`, `float64` → `"number"`, `bool` → `"boolean"`, `[]T` �� `"array"`, struct → `"object"`
   - 포인터 타입(`*string` 등)은 optional 필드로 간주한다.
   - `enum` 값이 있는 경우 (코드 내 validation 함수 등에서 확인) `enum` 배열을 추가한다.
   - 스키마에는 `[코드 기준 추가]` 같은 태그를 붙이지 않는다. 대신 **별도 비교 테이블**(Phase 4.1.1)에서 출처를 정리한다.
4. **불일치 보고**: OAS와 코드 간 타입 불일치나 필드 차이가 있으면 스키마 출력 시 별도로 안내한다.

> **우선순위**: 코드베이스가 OAS보다 우선한다. OAS에 없는 필드라도 코드에 존재하�� 스키마에 포함한다. 타입 불일치 시에도 코드 기준으로 출력한다.

### Phase 3: Schema Analysis

OAS에서 읽어온 raw schema를 코드베이스 교차 검증 결과와 병합하여 분석한다.

#### 출력 원칙: 항상 Flat

**모든 중첩 객체는 예외 없이 flat 인라인으로 출력한다.** `$ref` 분리를 하지 않는다. 동일 구조가 여러 곳에서 반복되더라도 매번 전체 필드를 펼쳐서 출력한다.

> **핵심**: 유저가 스키마를 **한 번에 copy → Apidog에 붙여넣기** 할 수 있어야 한다. 외부 참조 없이 각 섹션이 완전한(self-contained) JSON schema여야 한다.

### Phase 4: Schema Output

유저에게 최종 결과를 아래 형식으��� 출력한다. 각 섹션은 독립적으로 copy 가능해야 한다.

#### 4.1 Main Schema

Response Schema 1개 + (해당 시) Request Schema 1개를 출력한다. **코드 기준으로 완전한 스키마**를 구성한다. OAS에만 있든 코���에만 있든 관계없이 코드에 존재하는 모��� 필드를 포함한다. 스키마 내부에 `[코드 기�� 추가]` 같은 태그는 붙이지 않는다.

#### 4.1.1 OAS vs 코드 비교 테이블

Main Schema 하단에 **OAS와 코드 간 차이**를 별도 테이블로 정리한다. 유저가 Apidog OAS를 업���이트할 때 참고할 수 있도록 한다.

**출력 형식:**

```
### OAS vs 코드 비교

| 위치 | 필드명 | OAS | 코드 | 비고 |
|------|--------|-----|------|------|
| data[] | publishedStatus | 없음 | string | 코드에만 존재 |
| data[] | discountRate | integer | number (float64) | 타입 ���일치 |
| data[] | type -> productType | type (string) | productType (string) | 키 이름 불일치 |
| query | publishedStatus | 없음 | string | 코드��만 존재 |
```

- **코드에만 존재**: OAS에 없지만 코드에서 응답/요청에 포함하는 필드
- **OAS에만 존재**: 코드에서 사용하지 않지만 OAS에 정의된 필드 (deprecated 가능성)
- **타입 불일치**: 양쪽 모두 존재하나 타입이 다른 경우 (스키마는 코드 기준으로 출력)
- **키 이름 불일치**: 양쪽 모두 존재하�� 키 이름이 다른 경우

#### 4.2 Query Parameters (GET 엔드포인트)

GET 엔드포인트의 query parameters는 **CSV 형태**로 출력한���. **헤더 행 없이 데이터만 출력한다.**

**CSV 컬럼 순서 (고정, 헤더 미출력):**
```
이름,유형,필수,예시,고정 파라미터,설명
```

- **이름**: 파라미터 이름 (camelCase)
- **유형**: JSON Schema 타입 (`string`, `integer`, `number`, `boolean`)
- **필수**: `true` / `false`
- **예시**: 대표 값 1개 (enum이면 첫 번째 값)
- **고정 파라미터**: enum 값이 있으면 쉼표 구분으로 나열, 없으면 빈 칸
- **설명**: 한글 설명

출력 후 유저에게 옵션을 제시한다:

1. CSV 출력 완료 후 → "각 파라미터별 JSON Schema도 출력할까요?" 를 물어본다.
2. 유저가 JSON Schema 출력을 선택하면 → 각 파라미터별 JSON Schema를 개별 출력한다.
3. 선택한 옵션의 출력이 완료되면 → 선택하지 않은 다른 옵션의 리스트도 출력할지 안내한다.

> 상세 형식은 `references/extraction-patterns.md`의 "Query Parameters (GET)" 섹션 참���.

#### 4.3 Polymorphic 필드 처리 (Apidog schema composition)

응답에 `interface{}` 또는 `type` discriminator 기반 다형성 필드가 있는 경우, Apidog의 schema composition을 활용���다.

**Apidog composition 타입 선택 기준:**

| Apidog 옵션 | OpenAPI | 의미 | 사용 시점 |
|------------|---------|------|----------|
| XOR | `oneOf` | 정확히 하나만 만족 | `type` discriminator 기반 다형성 (**기본 선택**) |
| OR | `anyOf` | 하나 이상 만족 | 여러 형태가 동시 가능한 경우 (드묾) |
| AND | `allOf` | 모두 만족 | 상속/확장 패턴 |

**출력 방식:**

1. Main Schema에서 해당 필드를 composition placeholder로 표기한다. 각 variant 내부에 full schema를 포함한다:
   ```json
   "extraInfo": {
     "oneOf": [
       { "title": "variant_name", "type": "object", "properties": { ... } },
       { "title": "variant_name", "type": "object", "properties": { ... } }
     ]
   }
   ```
2. Main Schema 하단에 `extraInfo[0] — variant_name` 형태로 각 variant의 full schema를 **별도 섹션**에 flat 인라인으로 출력한다. 이 섹션은 Apidog에서 해당 `oneOf` 인덱스에 직접 붙여넣을 수 있는 형태이다.
3. variant 내부의 중첩 객체도 재사용되지 않으면 인라인으로 펼친다.

> **핵심**: 공통 필드는 Main Schema에 1번만, variant별 차이는 인덱스 섹션에 분리하여 필요한 것만 copy → Apidog composition 인덱스에 바��� 붙여넣기 가능하게 한다.

### Phase 5: Confirmation

결���를 유저에게 보여주고 확인 받는다:
- ref 분리 대상이 적절한지
- ref 네이밍이 적절한지
- 누락된 필드가 없는지

유저 피드백 반영 후 최종 스키마를 확정한다.

### Phase 6: Apidog Push (선택)

스키마 확정 후, 유저에게 "Apidog에 자동 푸시할까��?" 를 물어본다. 유저가 동의하면 아래 절차를 수행한다.

> 유저가 처음부터 "Apidog에 푸시해줘", "Apidog 동기화" 등을 요청한 경우, Phase 1~5를 모두 수행한 후 자동으로 Phase 6을 진행한다.

#### 6.1 환경 변수 확인

필요한 환경 변수 2개:
- `APIDOG_ACCESS_TOKEN`: Apidog Personal Access Token
- `APIDOG_PROJECT_ID`: 대상 프로젝��� ID

확인 방법:
```bash
echo "TOKEN=${APIDOG_ACCESS_TOKEN:+set}" "PROJECT=${APIDOG_PROJECT_ID:+set}"
```

미설정 시 유저에게 안내:
> "Apidog Push에 필��한 환경 변수가 설정되어 있지 않��니다.
> 1. Apidog → Settings → API Access Token에서 토큰 생성
> 2. 아래 명령으로 설정:
> ```
> export APIDOG_ACCESS_TOKEN='your-token'
> export APIDOG_PROJECT_ID='your-project-id'
> ```"

#### 6.2 OpenAPI Spec 생성

코드 기준 최종 스키마를 단일 엔드포인트 OpenAPI 3.0 YAML로 변환한다.

**생성 규칙:**
- `openapi: "3.0.0"` 고��
- `info.title`: 프로젝트명 또는 서비스명
- `paths`: 해당 ���드포인트 1개만 포함
- `parameters`: GET이면 query params 포함
- `requestBody`: POST/PUT/PATCH이면 request schema 포함
- `responses.200`: response schema 포함
- 모든 스키마는 flat 인라인 (Phase 3 원칙 유지)

**파일 저장**: `/tmp/apidog-push-{endpoint-slug}.yaml`

#### 6.3 Apidog Import API 호출

```bash
curl -s -X POST \
  "https://api.apidog.com/v1/projects/${APIDOG_PROJECT_ID}/import-openapi" \
  -H "Authorization: Bearer ${APIDOG_ACCESS_TOKEN}" \
  -H "X-Apidog-Api-Version: 2024-03-28" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": $(cat /tmp/apidog-push-{endpoint-slug}.yaml | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
    \"options\": {
      \"endpointOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"schemaOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"updateFolderOfChangedEndpoint\": false,
      \"prependBasePath\": false
    }
  }"
```

#### 6.4 결과 보고

API 응답의 `data.counters`를 파싱하여 유저에게 보고:

```
### Apidog Push 결과
| 항목 | 생성 | 수정 | 실패 | 무시 |
|------|------|------|------|------|
| Endpoint | {created} | {updated} | {failed} | {ignored} |
| Schema | {created} | {updated} | {failed} | {ignored} |
```

`errors` 배열이 비어있지 않으면 에러 내용도 함께 출���한다.

#### 6.5 Push 옵션

유저가 커스텀 옵션을 지정할 수 있다:

| ���션 | 설명 | 기본값 |
|------|------|--------|
| `--folder {id}` | 대상 폴더 ID 지정 | Root |
| `--merge` | 기존 API와 병합 (AUTO_MERGE) | OVERWRITE_EXISTING |
| `--keep` | 기존 API 유지, 새 것만 추가 (KEEP_EXISTING) | OVERWRITE_EXISTING |
| `--new` | 항상 새로 생성 (CREATE_NEW) | OVERWRITE_EXISTING |
| `--branch {id}` | 대상 브랜치 ID | main |
| `--dry-run` | YAML만 생성하고 실제 푸시하지 않음 | false |

---

## Apidog REST API Push 레퍼런스

MCP에 write 기능이 없을 때 사용하는 Apidog REST API 스펙. 매번 검색하지 않도록 여기에 기록한다.

### 엔드포인트

```
POST https://api.apidog.com/v1/projects/{projectId}/import-openapi
```

### 헤더

| Header | 값 |
|--------|----|
| `Authorization` | `Bearer ${APIDOG_ACCESS_TOKEN}` |
| `X-Apidog-Api-Version` | `2024-03-28` |
| `Content-Type` | `application/json` |

### Request Body

```json
{
  "input": "<OpenAPI YAML 문자열 (JSON escaped)>",
  "options": {
    "endpointOverwriteBehavior": "OVERWRITE_EXISTING",
    "schemaOverwriteBehavior": "OVERWRITE_EXISTING",
    "updateFolderOfChangedEndpoint": false,
    "prependBasePath": false
  }
}
```

### options 필드

| 필드 | 값 | 설명 |
|------|----|------|
| `endpointOverwriteBehavior` | `OVERWRITE_EXISTING` / `KEEP_EXISTING` / `AUTO_MERGE` / `CREATE_NEW` | 기존 엔드포인트 처리 방식 |
| `schemaOverwriteBehavior` | `OVERWRITE_EXISTING` / `KEEP_EXISTING` / `AUTO_MERGE` / `CREATE_NEW` | 기존 스키마 처리 방식 |
| `updateFolderOfChangedEndpoint` | `false` | 변경된 엔드포인트의 폴더 이동 여부 |
| `prependBasePath` | `false` | basePath를 경로 앞에 추가할지 |
| `targetBranchId` | `number` (선택) | 대상 브랜치 ID |
| `targetFolderId` | `number` (선택) | 대상 폴더 ID |

### Response 구조

```json
{
  "success": true,
  "data": {
    "counters": {
      "endpoint": { "created": 0, "updated": 1, "failed": 0, "ignored": 0 },
      "schema": { "created": 0, "updated": 1, "failed": 0, "ignored": 0 }
    },
    "errors": []
  }
}
```

### 실행 예시 (bash)

```bash
curl -s -X POST \
  "https://api.apidog.com/v1/projects/${APIDOG_PROJECT_ID}/import-openapi" \
  -H "Authorization: Bearer ${APIDOG_ACCESS_TOKEN}" \
  -H "X-Apidog-Api-Version: 2024-03-28" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": $(cat /tmp/apidog-push-{slug}.yaml | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
    \"options\": {
      \"endpointOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"schemaOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"updateFolderOfChangedEndpoint\": false,
      \"prependBasePath\": false
    }
  }"
```

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 302 Redirect | URL 오타 또는 프로젝트 ID 오류 | URL/ID 재확인. 반복 디버깅 금지, 즉시 수동 안내로 전환 |
| 401 Unauthorized | 토큰 만료/잘못됨 | `APIDOG_ACCESS_TOKEN` 재생성 안내 |
| 400 Bad Request | YAML 포맷 오류 | `python3 -c 'import yaml; yaml.safe_load(open(f))'`로 검증 |
| `errors` 배열 비어있지 않음 | 스키마 충돌 | 에러 메시지 확인 후 options 조정 |

---

## Key Rules

| 항목 | 규칙 |
|------|------|
| `pagination` 객체 | 인라인 유지 (ref 분리 안 함) |
| `data` wrapper | 인라인 ���지 |
| `null` 타입 필드 | nullable로 표기: `"type": ["{inferredType}", "null"]` (실제 타입은 context에서 유추, 상세는 `references/extraction-patterns.md` Pattern 4 참조) |
| `required` 배열 | OAS 원본의 required 필드를 그대로 ���지 |
| 빈 `items: {}` | `"items": {}` 그대로 유지 (any type array) |
| `example` 필드 | 스키마 출력에서 제외 |
| `deprecated` 엔��포인트 | 유저에게 deprecated 경고 표시 |
| 코드 vs OAS 불일치 | 코드 기준 우선. 불일치 사항은 출력 하단에 별도 안내 |
| 코드 추가 필드 | 스키마에 포함하되 태그 없이 출력. 별도 비교 테이��(4.1.1)에서 출처 정리 |
| Go 포인터 타입 | optional 필드로 간주 (required에 포함하지 않음) |

## Output Customization

유저가 원할 경우 다음 옵션을 제공한다:

- **File output**: 스키마를 파일로 저장 (경로 지정 가능)
- **Go struct hint**: 각 ref 스키마에 대응하는 Go struct 이름 주석 추가

## Additional Resources

### Reference Files

상세 패턴과 엣지 케이스 처리:
- **`references/extraction-patterns.md`** - Ref 추출 상세 패턴, 엣지 ��이스, 실제 예시
