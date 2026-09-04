---
name: e2e-apidog-schema-gen
description: "E2E 테스트 결과(요청/응답 실측)를 기반으로 Apidog 명세의 응답 케이스를 추가하고 스키마를 보정한다. e2e-test 실행 후 'Apidog 명세 보정해줘', 'E2E 결과로 문서 갱신' 요청 시 사용."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, WebFetch, mcp__apidog__read_project_oas_w9of5k, mcp__apidog__read_project_oas_ref_resources_w9of5k, mcp__apidog__refresh_project_oas_w9of5k
argument-hint: <API 경로 또는 'all'>
user-invocable: true
---

# E2E → Apidog Schema Sync

E2E 테스트에서 수집된 **실제 요청/응답 데이터**를 기반으로 Apidog 명세를 보정한다.
테스트에서 관찰된 모든 응답 케이스(성공, 에러)를 명세에 반영하여, 문서와 실제 동작의 괴리를 제거한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## Prerequisites

### 필요 환경
- **Apidog MCP 서버**: OAS 읽기/푸시를 위해 필수
- **환경 변수** (Push 기능 사용 시):
  - `APIDOG_ACCESS_TOKEN`, `APIDOG_PROJECT_ID`

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 `/minmos-harness:apidog-schema-gen --init`과 동일한 절차를 실행하고 종료한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## E2E Apidog Schema Gen — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 연결 | OK / MISSING / FAIL | 실제 MCP 호출 기준 |
| Apidog MCP 응답 | OK / FAIL / SKIP | OAS 읽기 시도 |
| APIDOG_ACCESS_TOKEN | SET / UNSET | Push 기능용 |
| APIDOG_PROJECT_ID | SET / UNSET | Push 기능용 |
```

> **MCP 판정**: 실제 `mcp__apidog__read_project_oas_*` 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다 (상세: `/minmos-harness:doctor`).

### 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--init` | | 초기 세팅 후 종료 |
| `--doctor` | | 상태 진단 후 종료 |
| `--skip-doctor` | `-sd` | 실행 전 자동 doctor 점검을 건너뜀 |
| `--status {값}` | | 엔드포인트 status 를 직접 지정 (10종 literal). 지정 시 Phase 5.0.5의 추론·보호 규칙보다 우선한다 |

---

## 절차

### 0. Pre-flight Doctor

`$ARGUMENTS`에 `--skip-doctor` 또는 `-sd`가 **없으면**, 위 `--doctor`와 동일한 점검을 자동 실행한다.

- 모두 OK → 한 줄 요약 후 Phase 1로 진행
- **BLOCKED** 있음 → 누락 항목 안내 후 진행 여부를 사용자에게 질문
- `--skip-doctor` / `-sd` 지정 시 → 건너뛰고 바로 Phase 1로 진행

---

## Phase 1: E2E 결과 수집

### 1.1 대화 컨텍스트에서 수집

직전 E2E 테스트 결과가 대화에 있으면 해당 데이터를 사용한다.

**수집 대상 (테스트 케이스별):**
- HTTP Method + Path
- Request body (또는 query params)
- Response status code
- Response body
- 테스트 카테고리 (Happy Path / Validation / Edge Case / 인증권한)

### 1.2 대화에 결과가 없는 경우

`AskUserQuestion`으로 다음을 질문한다:

> "E2E 테스트 결과를 기반으로 Apidog 명세를 업데이트합니다.
> 1. 직전에 E2E 테스트를 실행했다면, 대상 API 경로를 알려주세요.
> 2. 아직 테스트를 실행하지 않았다면, 먼저 `/be-harness:e2e-test`를 실행해주세요."

### 1.3 결과 정규화

수집된 응답을 status code 기준으로 그룹핑한다:

```
200 OK          → 성공 응답 (데이터 반환)
201 Created     → 생성 성공
400 Bad Request → 입력 검증 실패
401 Unauthorized→ 인증 실패
403 Forbidden   → 권한 부족
404 Not Found   → 리소스 없음
409 Conflict    → 충돌
500 Internal    → 서버 에러
```

---

## Phase 2: 현재 Apidog 명세 읽기

### 2.1 OAS 읽기

1. `mcp__apidog__read_project_oas_w9of5k`로 해당 경로의 `$ref` 확인
2. `mcp__apidog__read_project_oas_ref_resources_w9of5k`로 상세 스키마 로드
3. 현재 정의된 `responses` 섹션의 status code 목록을 추출

### 2.2 코드베이스 교차 검증

- Handler의 response struct를 `Grep`/`Read`로 확인
- Usecase의 에러 반환 경로를 추적하여 가능한 에러코드 목록 도출
- `errcode.go`에서 각 에러코드의 HTTP status 매핑 확인

### 2.3 Gap 분석

| 항목 | 현재 명세 | E2E 실측 | 코드 분석 |
|------|----------|----------|----------|
| 200 응답 스키마 | [있음/없음] | [실측 구조] | [코드 struct] |
| 에러 응답 케이스 | [정의된 코드] | [관찰된 코드] | [가능한 코드] |
| 누락된 필드 | - | [실측에서 발견] | [코드에 존재] |

---

## Phase 3: 스키마 생성

### 3.1 성공 응답 스키마 (2xx)

E2E의 Happy Path 응답 body를 기반으로 스키마를 생성한다.

**생성 규칙:**
- 실측 응답 body의 모든 필드를 포함
- 코드의 response struct와 교차 검증하여 누락 필드 보완
- 타입은 실측 값에서 유추하되, 코드 struct가 우선
- **`/minmos-harness:apidog-schema-gen`의 flat 인라인 원칙을 따른다**

### 3.2 에러 응답 케이스

E2E에서 관찰된 각 에러 status code별로 응답 케이스를 생성한다.

**에러 응답 공통 구조 (프로젝트 표준):**
```json
{
  "code": "string (에러코드)",
  "message": "string (에러 메시지)",
  "detail": "string (상세 정보, nullable)"
}
```

**케이스별 생성:**

| Status | 케이스명 | 생성 기준 |
|--------|---------|----------|
| 400 | 입력 검증 실패 | Validation 테스트에서 관찰된 에러코드 |
| 400 | VO 생성 실패 | Edge Case 테스트에서 VO nil 반환 케이스 |
| 401 | 인증 실패 | 토큰 없음 테스트 |
| 403 | 권한 부족 | 권한 테스트 (해당 시) |
| 404 | 리소스 없음 | 존재하지 않는 ID 테스트 |
| 409 | 충돌 | 중복 생성 테스트 (해당 시) |
| 500 | 서버 에러 | 서버 에러 관찰 시 (STATUS_MISMATCH 포함) |

**각 케이스에 포함할 정보:**
- Status code
- 케이스 설명 (한국어)
- 에러코드 예시 (`WARN_PMS_XXX` 또는 `ERR_PMS_XXX`)
- Response body 예시 (E2E 실측값)

### 3.3 Request 스키마 보정

E2E의 Validation 테스트 결과를 기반으로 request 스키마도 보정한다:

- `required` 배열: 필수 필드 누락 시 400이 반환된 필드 목록
- `enum`: 잘못된 값 시 400이 반환된 필드의 허용 값 목록
- nullable: null 전송 시 정상 처리된 필드 → `["type", "null"]`

---

## Phase 4: 출력

### 4.1 변경 요약 테이블

```markdown
### Apidog 명세 변경 요약

#### 성공 응답 (2xx)
| 항목 | 변경 | 상세 |
|------|------|------|
| 필드 추가 | `fieldName` | E2E/코드에서 확인, 명세에 누락 |
| 타입 수정 | `fieldName` | integer → number (코드 기준) |

#### 에러 응답 케이스 추가
| Status | 케이스 | 에러코드 | 출처 |
|--------|--------|---------|------|
| 400 | 필수 필드 누락 | WARN_PMS_001 | Validation 테스트 |
| 404 | 리소스 없음 | WARN_PMS_007 | Edge Case 테스트 |

#### Request 스키마 보정
| 항목 | 변경 | 근거 |
|------|------|------|
| `name` → required | 추가 | 누락 시 400 반환 확인 |
| `status` → enum | ["active","inactive"] | 다른 값 시 400 반환 확인 |
```

### 4.2 스키마 출력

`/minmos-harness:apidog-schema-gen`과 동일한 형식으로 출력한다:

1. **Response Schema (성공)** — flat 인라인 JSON Schema
2. **Response Schema (에러 케이스별)** — status code별 JSON Schema + 예시
3. **Request Schema (보정 반영)** — 해당 시
4. **OAS vs E2E 비교 테이블** — 명세와 실측의 차이
5. **Query Parameters CSV** — GET 엔드포인트 해당 시

### 4.3 에러 케이스 상세 출력

각 에러 케이스를 Apidog에 바로 붙여넣을 수 있는 형태로 출력한다:

```markdown
### 400 Bad Request — 필수 필드 누락

**케이스명**: 필수 필드 누락
**에러코드**: WARN_PMS_001

```json
{
  "type": "object",
  "properties": {
    "code": { "type": "string", "example": "WARN_PMS_001" },
    "message": { "type": "string", "example": "필수 필드가 누락되었습니다" },
    "detail": { "type": ["string", "null"] }
  },
  "required": ["code", "message"]
}
```

**E2E 실측 응답:**
```json
{ "code": "WARN_PMS_001", "message": "...", "detail": "..." }
```
```

---

## Phase 5: 확인 및 Push

1. 유저에게 변경 요약을 보여준다.
2. **변경 사항이 있으면 Apidog에 바로 푸시한다.** 별도 확인을 묻지 않는다.
3. 푸시는 아래 우선순위에 따라 시도한다.
4. 푸시 완료 후 결과를 보고한다.

### 5.0 대상 폴더 결정

Push 전에 해당 API 경로가 Apidog에 이미 존재하는지 확인한다.

- **경로가 이미 존재** → 기존 위치에서 수정 (`updateFolderOfChangedEndpoint: false`).
- **경로가 없음 (신규)** → 기존 경로 중 **prefix가 가장 많이 일치하는 엔드포인트의 폴더**에 배치 (`targetFolderId` 지정).
- **유사 경로도 없음** → Root 폴더에 배치.

상세 판정 로직은 `/minmos-harness:apidog-schema-gen`의 push-import 절차 Step 8.2(폴더 결정)를 따른다.

### 5.0.5 status 결정

E2E 실측 결과를 근거로 엔드포인트 status 를 정하고 push 페이로드에 **반드시 기입**한다 (`x-apidog-status`, operation 레벨).
허용 값 10종·deprecated 특칙의 canonical 은 `/minmos-harness:apidog-schema-gen` 의 `references/push-import.md` **Step 8.2.5** 다. 이 절은 그 우선순위를 E2E 맥락에 맞춰 확정한 것이며, 충돌하면 canonical 이 우선한다.

**결정 순서 — 위에서 정해지면 아래는 보지 않는다:**

1. **`--status {값}` 이 유효한 10종 literal 이면 그 값** — 사용자 명시가 최우선이며, 아래 보호 규칙보다도 우선한다.
2. **기존 status 가 `released`·`deprecated`·`obsolete` 면 그 값을 그대로 유지** — 추론하지 않는다. 릴리즈·지원중단된 API 가 E2E 한 번으로 되돌아가는 것을 막는다. 유지 사실을 5.2 보고에 남긴다.
3. **OAS 에 없는 신규 경로면 `developing`**
4. **그 외에는 E2E 결과로 추론:**

| E2E 결과 | status |
|----------|--------|
| 수집한 전 케이스 통과 (happy path + 에러 케이스 모두 기대대로) | `tested` |
| 실패했거나 확인하지 못한 케이스가 하나라도 있음 | `testing` |

**`released` 로 자동 승격하지 않는다** — 전 케이스를 통과해도 2·3·4 경로의 최대치는 `tested` 다. `released` 는 1번(`--status released`)으로만 설정된다.

기존 status 는 Phase 5.0에서 OAS 를 읽을 때 함께 확인한다 (`x-apidog-status`, 없으면 `developing` 으로 간주).

### 5.0.6 push 페이로드 확정

**전송 수단을 고르기 전에** 최종 operation 페이로드를 만들고 검증한다 — 5.1의 두 경로(MCP write / REST API)가 **같은 페이로드**를 보내야 status 누락이 생기지 않는다.

1. 코드·E2E 기준 스키마에 5.0.5의 status 를 얹어 단일 엔드포인트 OpenAPI 3.0 YAML 을 만든다 (`/tmp/apidog-push-{endpoint-slug}.yaml`).
2. 구조 검증 — 셋 다 만족해야 5.1로 진행한다:
   - `x-apidog-status` 가 **operation 레벨**에 있다 (`responses` 와 같은 깊이. `info` 나 path 레벨이 아니다)
   - 값이 canonical 10종 literal 중 하나다
   - status 가 `deprecated` 면 `deprecated: true` 도 함께 있다
3. 검증 실패 시 push 하지 않고 YAML 생성을 다시 한다.

> **변경 판정 주의**: Phase 5의 "변경 사항이 있으면 push" 판정에 **status 변경도 포함**한다. 스키마가 그대로여도 status 가 기존 값과 다르면 변경으로 보고 push 한다 — 그러지 않으면 status 전이(`testing` → `tested` 등)가 영영 반영되지 않는다.

### 5.1 Push 실행 (MCP → REST API fallback)

두 시도 모두 **5.0.6에서 확정·검증한 페이로드를 그대로** 전송한다. 전송 수단이 달라도 보내는 내용은 동일해야 한다.

#### 시도 1: MCP write (Apidog MCP에 write 기능이 있는 경우)

MCP tool로 직접 push를 시도한다 — 5.0.6의 페이로드(= `x-apidog-status` 포함)를 그대로 넘긴다. 성공하면 5.2로 진행.

#### 시도 2: Apidog REST API (MCP write 불가 시)

MCP에 write 기능이 없거나 실패하면, **즉시 Apidog REST API로 자동 전환**한다.
반복 디버깅하지 않고 바로 대안을 사용한다.

```bash
# 1. 5.0.6에서 확정·검증한 /tmp/apidog-push-{endpoint-slug}.yaml 를 그대로 사용한다
#    (여기서 스키마를 다시 만들지 않는다 — 재생성하면 status 검증 결과가 무효가 된다)

# 2. Apidog Import API 호출
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

**필요 환경 변수**: `APIDOG_ACCESS_TOKEN`, `APIDOG_PROJECT_ID`
미설정 시 유저에게 설정 안내 후 수동 가이드를 제공한다.

#### 시도 2.5: MCP Scraping Fallback (REST API 실패 시)

REST API 호출이 실패하면 (302, 401, 400, 빈 응답 등), MCP에서 프로젝트 정보를 스크래핑하여 **1회 재시도**한다.

**스크래핑 절차:**

1. **MCP 설정 파싱** — 현재 클라이언트에서 읽을 수 있는 MCP 설정을 확인하여 인증 정보를 추출한다. `.mcp.json`에 한정하지 않는다.
   - **Project ID**: 설정의 `args`에서 `--project-id=` 인자를 찾고 `APIDOG_PROJECT_ID`와 대조, 불일치 시 MCP 설정 값을 우선 사용
   - **Access Token**: 아래 우선순위로 탐색:
     1. 읽을 수 있는 MCP 설정의 `args`에 `--api-key=` 또는 `--access-token=` 인자가 있으면 추출
     2. 읽을 수 있는 MCP 설정의 `env` 섹션에 `APIDOG_ACCESS_TOKEN`이 있으면 추출
     3. 둘 다 없으면 현재 셸의 `APIDOG_ACCESS_TOKEN` 환경 변수 유지

2. **OAS 구조 확인** — `mcp__apidog__read_project_oas_w9of5k`를 호출하여:
   - 프로젝트 접근 가능 여부 확인
   - 대상 경로 존재 여부 및 기존 엔드포인트 경로 목록 확인
   - 유사 경로의 path prefix 매칭으로 folder 배치 후보 파악 (Phase 5.0 로직 재사용)

3. **교정된 파라미터로 1회 재시도:**
   - 교정된 Project ID 및 Access Token 적용
   - 올바른 targetFolderId 지정
   - YAML 호환성 검증 (기존 OAS 구조 참조)

> **핵심**: MCP가 OAS를 정상 조회하고 있어도 인증 정보가 반드시 `.mcp.json`에 있는 것은 아니다. 다른 설정 경로를 쓰는 클라이언트를 고려해 읽을 수 있는 MCP 설정과 현재 환경 변수를 함께 사용한다.

재시도도 실패하면 **반복 시도 없이** 즉시 시도 3으로 전환한다.

#### 시도 3: 수동 안내 (REST API도 실패 시 — 최후 수단)

REST API 호출이 실패(302/redirect, 인증 에러 등)하면 수동 가이드를 제공한다:
> "자동 Push가 실패했습니다. 아래 스키마를 Apidog에서 수동으로 업데이트해주세요."

### 5.2 Push 결과 보고

API 응답의 `data.counters`를 파싱하여 보고:

```markdown
### Push 결과
| 항목 | 생성 | 수정 | 실패 |
|------|------|------|------|
| Endpoint | {created} | {updated} | {failed} |
| Schema | {created} | {updated} | {failed} |

- status: `{값}` ({한국어 라벨}) — {E2E 추론 사유 | 기존 값 유지(다운그레이드 방지)}
```

---

## 핵심 원칙

1. **실측 데이터가 최우선** — E2E에서 관찰된 실제 응답이 스키마의 근거다.
2. **코드로 보완** — 실측에서 커버하지 못한 케이스는 코드 분석으로 보충한다.
3. **기존 명세를 존중** — 기존 명세에 이미 올바르게 정의된 부분은 건드리지 않는다.
4. **flat 인라인 원칙 유지** — apidog-schema-gen과 동일한 출력 규칙을 따른다.
5. **에러 케이스는 개별 복사 가능하게** — 각 케이스를 독립적으로 Apidog에 붙여넣을 수 있어야 한다.
