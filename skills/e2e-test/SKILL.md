---
name: e2e-test
description: "기능 추가/수정 후 연관 API E2E 테스트 수행"
user-invocable: true
---

# E2E API 테스트

기능 추가 또는 수정이 완료된 후, 연관된 API들을 실제 요청으로 E2E 테스트한다.

---

## Prerequisites

### 필요 환경
- **Apidog MCP 서버**: Apidog 스펙 참조/비교용
- **PostgreSQL MCP 서버** (읽기/쓰기): 테스트 데이터 생성, BASELINE_ID 기록, soft-delete 정리용

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **Apidog MCP 확인**: `.mcp.json`에 `apidog` MCP 등록 여부 확인.
   - 없으면 `/minmo-s-harness:apidog-schema-gen --init`과 동일한 Apidog 세팅을 안내한다.
2. **PostgreSQL MCP 확인**: `.mcp.json`에 `postgres` MCP 등록 여부 확인.
   - 없으면 안내:
     > "PostgreSQL MCP 서버가 설정되어 있지 않습니다. `.mcp.json`에 아래 설정을 추가하세요:"
     > ```json
     > {
     >   "mcpServers": {
     >     "postgres": {
     >       "command": "npx",
     >       "args": ["-y", "@anthropic/postgres-mcp", "<DATABASE_URL>"]
     >     }
     >   }
     > }
     > ```
   - `secret/.env`에서 DB 접속 정보를 읽어 DATABASE_URL을 자동 구성할 수 있으면 제안한다.
   - 유저 동의 시 `.mcp.json`에 자동 추가한다.
3. 결과를 요약 보고한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## E2E Test — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 등록 | OK / MISSING | .mcp.json 확인 |
| Apidog MCP 응답 | OK / FAIL | OAS 읽기 시도 |
| PostgreSQL MCP 등록 | OK / MISSING | .mcp.json 확인 |
| PostgreSQL MCP 연결 | OK / FAIL | SELECT 1 시도 |
| secret/.env 존재 | OK / MISSING | JWT_SECRET, DB 접속 정보 |
| Go 빌드 | OK / FAIL | go build 시도 |
```

- 문제가 있으면 `--init`을 실행하라고 안내한다.

---

## 핵심 원칙: 테스트 데이터 격리

**기존 데이터를 절대 수정/삭제하지 않는다.** 모든 테스트 데이터는 E2E 테스트 전용으로 생성하고, 테스트 종료 시 정리한다.

- 수정(Update) 테스트: 먼저 테스트용 데이터를 생성 → 생성된 ID로 수정 → 검증
- 삭제(Delete) 테스트: 먼저 테스트용 데이터를 생성 → 생성된 ID로 삭제 → 검증
- 기존 데이터의 ID를 하드코딩하여 수정/삭제하지 않는다.

## 절차

### 1. 변경 범위 파악
- `git diff` 또는 현재 대화 컨텍스트에서 변경된 파일을 파악한다.
- 변경된 handler/route를 기반으로 **영향받는 API 엔드포인트 목록**을 도출한다.
- 직접 변경된 API뿐 아니라, 같은 도메인의 연관 API(예: POST 변경 시 GET 조회도 포함)를 리스트업한다.

### 2. Apidog 문서 참조
- `mcp__apidog__read_project_oas_n7eawf`로 OAS 전체 경로를 확인한다.
- `mcp__apidog__read_project_oas_ref_resources_n7eawf`로 각 엔드포인트의 상세 스펙(request/response schema)을 읽는다.
- 코드의 실제 request/response 구조체와 Apidog 스펙을 비교하여 차이점을 보고한다.

### 3. 엣지 케이스 분석
코드베이스와 Apidog 스펙을 기반으로 엣지 케이스를 도출한다.

**코드베이스 분석:**
- handler의 request DTO에서 `binding` 태그 확인 (`required`, `dive`, `min`, `max`, `oneof` 등)
- domain의 command/VO 생성 함수에서 validation 로직 분석 (nil 반환 조건 전부 추출)
- usecase에서 비즈니스 validation 확인 (존재 여부 체크, 상태 체크, 권한 체크 등)
- DB check constraint, enum 값, FK 관계 확인
- 포인터 필드(*type)는 null 허용 → null 전송 테스트
- 배열 필드는 빈 배열/단일/다수 케이스 테스트

**Apidog 스펙 분석:**
- `required` 필드 목록과 코드의 `binding:"required"` 비교
- `enum` 값 목록과 코드의 validation enum 비교
- `nullable` 타입(`["string", "null"]`) 식별 → null 전송 테스트
- `format` (date-time, email 등) → 잘못된 포맷 전송 테스트

**엣지 케이스 카테고리:**
- **경계값**: 빈 문자열, 0, 음수, 매우 큰 값, 최대 길이 문자열
- **타입 불일치**: 숫자 필드에 문자열, 배열 필드에 단일 값
- **Null/Missing**: nullable 필드에 null vs 필드 자체 생략
- **중복/충돌**: 동일 ID로 재생성, 이미 삭제된 리소스 수정
- **시간**: endAt < startAt, 과거 날짜, 시간대 차이
- **상태 전이**: 허용되지 않는 상태 변경 (e.g., removed → active)
- **관계**: 존재하지 않는 FK 참조, 삭제된 리소스 참조

### 3-1. HTTP Status Code 의미적 정합성 검증

모든 에러 응답에 대해 **HTTP 상태 코드가 에러의 원인(클라이언트/서버)과 일치하는지** 검증한다.
단순히 "에러가 반환되는가"가 아니라 "올바른 종류의 에러가 반환되는가"를 확인하는 단계이다.

**분류 기준:**

| 원인 | 올바른 Status | 예시 |
|------|--------------|------|
| 클라이언트 입력 오류 | 400 Bad Request | 필수 필드 누락, 유효하지 않은 값, 타입 불일치 |
| 인증 없음 | 401 Unauthorized | 토큰 없음, 만료된 토큰 |
| 권한 없음 | 403 Forbidden | 일반 유저가 ADMIN API 호출 |
| 리소스 없음 | 404 Not Found | 존재하지 않는 ID로 조회/수정/삭제, 존재하지 않는 FK 참조 ID |
| 충돌 | 409 Conflict | 중복 생성, 이미 처리된 요청 |
| 서버 내부 오류 | 500 Internal Server Error | DB 연결 실패, 예상치 못한 런타임 에러 |

**검증 방법:**

1. **에러코드 매핑 분석**: `errcode.go`의 `errorMap`에서 각 에러코드의 `StatusCode`를 확인한다.
2. **Usecase 에러 흐름 추적**: usecase의 에러 반환 경로를 추적하여, 클라이언트 입력 오류가 `ERR_*` (5XX)로 반환되는 경우를 찾는다.
3. **주요 점검 포인트:**
   - 존재하지 않는 FK 참조 ID 전달 → 404이어야 하는데 500 반환하지 않는가?
   - `RowsAffected` 불일치(일부 ID 미존재) → 404이어야 하는데 500 반환하지 않는가?
   - `domain.ErrNotFound` → 반드시 `WARN_*` (4XX)로 매핑되는가?
   - Repository에서 올라온 에러를 usecase가 원인별로 분기하는가, 일괄 5XX로 처리하는가?

**E2E 실행 시 검증:**
- 각 에러 케이스에 대해 **기대 status code**와 **실제 status code**를 비교한다.
- 4XX가 기대되는데 5XX가 반환되면 **[STATUS_MISMATCH]** 로 표기하고, 발견된 이슈에 별도 보고한다.

### 4. 테스트 환경 준비
- `secret/.env`에서 포트와 DB 접속 정보를 확인한다.
- `secret/.env`와 `secret/gcp-sa-key.json`이 worktree에 존재하는지 확인하고, 없으면 원본 repo에서 복사한다.
- `go build -o /tmp/pms-test-server ./cmd/main.go`로 명시적 빌드 후 `/tmp/pms-test-server &`로 서버 실행한다.
  - **중요**: `go run`이 아닌 명시적 빌드된 바이너리를 실행해야 이전 프로세스와 혼동이 없다.
- JWT 토큰을 생성한다 (ADMIN role: `role_id=1`, 충분한 exp).
  - JWT_SECRET은 `secret/.env`의 `JWT_SECRET` 값을 사용한다.
  - Claims: `{"member_id":1,"member_old_id":1,"role_id":1,"is_staff":true,"uuid":"e2e-test","company_id":1,"exp":1900000000}`
- 필요 시 USER 토큰도 생성한다 (`role_id=2`).

#### 테스트 데이터 추적 준비
- 테스트 시작 전, 관련 테이블의 현재 최대 ID를 기록한다.
  ```sql
  SELECT COALESCE(MAX(id), 0) FROM {table_name};
  ```
- 이 ID를 `BASELINE_ID`로 저장하여, 테스트 종료 시 이후 생성된 데이터를 식별한다.

### 5. E2E 테스트 실행
각 엔드포인트에 대해 실제 curl 요청을 수행한다.

**데이터 격리 규칙:**
- 수정/삭제 테스트 시 **반드시 이번 테스트에서 생성한 데이터만** 대상으로 한다.
- 테스트 흐름: 생성 → (생성된 ID 캡처) → 수정/삭제 → 검증
- 기존 데이터의 ID를 테스트에 사용하지 않는다.

**테스트 케이스 구성:**

#### A. Happy Path
- 생성 → 기대 status code 및 response 구조 확인
- 생성한 데이터를 조회하여 반영 확인
- **생성한 데이터의 ID로** 수정 → 변경 반영 확인
- **생성한 데이터의 ID로** 삭제 → 삭제 확인 (해당 시)

#### B. Validation (필수 필드/타입)
- 필수 필드 하나씩 누락 → 400
- 잘못된 enum 값 → 400
- 빈 배열 (required array) → 400
- 잘못된 타입 (문자열 → 숫자 필드) → 400

#### C. 엣지 케이스 (Step 3에서 도출)
- Domain validation에서 nil 반환하는 모든 조건 테스트
- DB constraint 위반 케이스
- 경계값 테스트
- Null/Missing 필드 테스트
- 시간 관련 엣지 (endAt < startAt 등)
- 존재하지 않는 리소스 참조 (하드코딩 999999 등 확실히 없는 ID 사용)

#### D. 인증/권한
- 토큰 없이 요청 → 401
- USER 역할로 ADMIN 전용 API 호출 → 403 (필요 시)

#### E. Status Code 정합성
Step 3-1에서 식별한 케이스를 실제 요청으로 검증한다.
- 존재하지 않는 FK 참조 ID로 생성/수정 → **404**가 반환되는지 확인 (500이면 [STATUS_MISMATCH])
- 삭제된 리소스 참조 → **404** 확인
- `RowsAffected` 불일치 유발 (일부 ID 미존재) → **404** 확인
- `domain.ErrNotFound` 경로 → **404** 확인
- 실제 DB/서버 에러와 구분되는 5XX가 아닌지 확인

**각 요청마다 기록:**
- HTTP method + path
- Request body (요약)
- Response status code
- Response body (요약)
- 기대값과 일치 여부

### 6. 결과 보고

아래 형식으로 보고한다:

```markdown
## E2E 테스트 결과

### 테스트 대상 API
- [METHOD] /path - 설명

### 테스트 결과

#### Happy Path
| # | 테스트 | HTTP | 결과 | 비고 |
|---|--------|------|------|------|
| 1 | 설명 | 2xx | 성공/실패 | 상세 |

#### Validation
| # | 테스트 | HTTP | 기대 | 결과 | 비고 |
|---|--------|------|------|------|------|
| 1 | 설명 | 4xx | 400 | 성공/실패 | 상세 |

#### Edge Cases
| # | 테스트 | HTTP | 기대 | 결과 | 비고 |
|---|--------|------|------|------|------|
| 1 | 설명 | xxx | xxx | 성공/실패 | 상세 |

#### 인증/권한
| # | 테스트 | HTTP | 결과 | 비고 |
|---|--------|------|------|------|
| 1 | 설명 | 4xx | 성공/실패 | 상세 |

#### Status Code 정합성
| # | 테스트 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 에러코드 | 판정 |
|---|----------------|----------|------------|------------|---------|------|
| 1 | 존재하지 않는 FK ID 참조 | 리소스 없음 | 404 | 404/500 | ERR/WARN | OK / [STATUS_MISMATCH] |

### 테스트 데이터 정리
- 정리 방법: [SQL / API 호출]
- 정리 대상: [테이블명, ID 범위]
- 정리 결과: [성공/실패]

### 발견된 이슈
- (있으면 기술, 이번 변경과 관련 여부 명시)

### Status Code 오분류 ([STATUS_MISMATCH])
| # | API | 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 에러코드 | 위치 (파일:라인) |
|---|-----|---------|----------|------------|------------|---------|----------------|
| 1 | [METHOD /path] | [시나리오] | [클라이언트/서버] | [4XX] | [5XX] | [ERR_PMS_XXX] | [파일:라인] |

- **수정 방향**: [Repository에서 도메인 에러 분리 → Usecase에서 errors.Is()로 분기 등]
```

### 7. 테스트 데이터 정리

테스트 종료 시, 테스트 중 생성된 모든 데이터를 정리한다.

**정리 방법 (우선순위):**
1. **삭제 API 호출**: DELETE API가 있으면 테스트에서 생성한 ID로 삭제 요청
2. **DB soft-delete**: 삭제 API가 없으면 DB에서 직접 `status='removed'`로 업데이트
   ```sql
   UPDATE {table_name} SET status = 'removed' WHERE id > {BASELINE_ID};
   ```
3. **연관 데이터도 정리**: FK 관계가 있는 하위 테이블도 함께 정리
   ```sql
   -- 예: conditions도 함께 정리
   UPDATE {child_table} SET status = 'removed' WHERE {parent_fk} IN (
     SELECT id FROM {parent_table} WHERE id > {BASELINE_ID}
   );
   ```

**정리 확인:**
- 정리 후 `SELECT COUNT(*) FROM {table_name} WHERE id > {BASELINE_ID} AND status != 'removed'`로 잔여 데이터가 없는지 확인한다.
- 정리 결과를 보고에 포함한다.

### 8. 서버 정리
- 서버 프로세스를 종료한다 (`pkill -f pms-test-server`).
- 바이너리를 삭제한다 (`rm -f /tmp/pms-test-server`).
