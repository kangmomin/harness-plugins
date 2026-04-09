---
name: e2e-apidog-schema-gen
description: "E2E 테스트 결과(요청/응답)를 기반으로 Apidog 명세의 응답 케이스를 추가하고 스키마를 보정한다."
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

`$ARGUMENTS`가 `--init`이면 `/minmo-s-harness:apidog-schema-gen --init`과 동일한 절차를 실행하고 종료한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## E2E Apidog Schema Gen — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 등록 | OK / MISSING | .mcp.json 확인 |
| Apidog MCP 응답 | OK / FAIL | OAS 읽기 시도 |
| APIDOG_ACCESS_TOKEN | SET / UNSET | Push 기능용 |
| APIDOG_PROJECT_ID | SET / UNSET | Push 기능용 |
```

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
> 2. 아직 테스트를 실행하지 않았다면, 먼저 `/minmo-s-harness:e2e-test`를 실행해주세요."

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
- **`/minmo-s-harness:apidog-schema-gen`의 flat 인라인 원칙을 따른다**

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
- `enum`: 잘못된 값 시 400이 반환된 필드의 허용 ��� 목록
- nullable: null 전송 시 정상 처리된 필드 → `["type", "null"]`

---

## Phase 4: 출력

### 4.1 변경 요약 테이블

```markdown
### Apidog 명세 변경 요약

#### 성공 응답 (2xx)
| 항목 | 변경 | 상세 |
|------|------|------|
| 필드 ��가 | `fieldName` | E2E/코드에서 확인, 명세에 누락 |
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

`/minmo-s-harness:apidog-schema-gen`과 동일한 형식으로 출력한다:

1. **Response Schema (성공)** — flat 인라인 JSON Schema
2. **Response Schema (에러 케이스별)** — status code별 JSON Schema + 예시
3. **Request Schema (보정 반영)** — 해당 시
4. **OAS vs E2E 비교 테이블** — 명세와 실측의 차이
5. **Query Parameters CSV** — GET 엔드포인트 해당 시

### 4.3 에러 ���이스 상세 출력

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
3. 푸시는 `/minmo-s-harness:apidog-schema-gen`의 Phase 6 (Apidog Push) 절차를 따른다.
4. 푸시 완료 후 결과를 보고한다.

---

## 핵심 원칙

1. **실측 데이터가 최우선** — E2E에서 관찰된 실제 ���답이 스키마의 근거다.
2. **코드로 보완** — 실측에서 커버하지 못한 케이스는 코드 분석으로 보충한다.
3. **기존 명세를 존중** — 기존 명세에 이미 올바르게 정의된 부분은 건드리지 않는다.
4. **flat 인라인 원칙 유지** — apidog-schema-gen과 동일한 출력 규칙을 따른다.
5. **에러 케이스�� 개별 복사 가능하게** — 각 케이스를 독립적으로 Apidog에 붙여넣을 수 있어야 한다.
