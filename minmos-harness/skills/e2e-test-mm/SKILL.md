---
name: e2e-test-mm
description: "기능 추가/수정 후 연관 API E2E 테스트 수행"
user-invocable: true
---

# E2E API 테스트

기능 추가 또는 수정이 완료된 후, 연관된 API들을 실제 요청으로 E2E 테스트한다.

---

## Prerequisites

### 필요 환경
- **Apidog MCP 서버**: Apidog 스펙 참조/비교용 (REST)
- **PostgreSQL MCP 서버** (읽기/쓰기): 테스트 데이터 생성, BASELINE_ID 기록, soft-delete 정리용
- **grpcurl** (선택): gRPC 엔드포인트 테스트용. gRPC 테스트가 필요한 경우에만 필수

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **Apidog MCP 확인**: `.mcp.json`에 `apidog` MCP 등록 여부 확인.
   - 없으면 `/minmos-harness:apidog-schema-gen-mm --init`과 동일한 Apidog 세팅을 안내한다.
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
3. **DB 호스트 검증**: `secret/.env`의 `DB_HOST`가 로컬이 아닌 경우:
   - 사용자에게 해당 DB에서 E2E 테스트를 실행해도 되는지 확인한다.
   - 승인하면 `.e2e-allowed-hosts`에 호스트를 등록하고, `.gitignore`에도 추가한다.
   - 거부하면 로컬 DB로 변경하라고 안내한다.
4. **grpcurl 확인** (선택): `which grpcurl`로 설치 여부를 확인한다.
   - 없으면 안내:
     > "gRPC E2E 테스트를 사용하려면 grpcurl이 필요합니다:"
     > ```bash
     > # macOS
     > brew install grpcurl
     > # Linux (Go)
     > go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
     > ```
   - gRPC 테스트가 불필요하면 건너뛸 수 있다.
5. 결과를 요약 보고한다.

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
| DB 호스트 (로컬 전용) | OK / **BLOCKED** | DB_HOST가 localhost/127.0.0.1인지 확인 |
| MCP DB 호스트 (로컬 전용) | OK / **BLOCKED** / SKIP | .mcp.json postgres URL 호스트 확인 |
| grpcurl 설치 (선택) | OK / MISSING | grpcurl --version |
| GRPC_PORT (선택) | OK / MISSING / SKIP | secret/.env 확인 |
```

- **BLOCKED** 항목이 하나라도 있으면 E2E 테스트를 실행할 수 없다고 경고하고, 해당 DB를 허용할지 사용자에게 질문한다. 승인하면 `.e2e-allowed-hosts`에 등록한다.
- 문제가 있으면 `--init`을 실행하라고 안내한다.

---

## 핵심 원칙: 로컬 DB 전용 실행 (절대 원칙)

> **E2E 테스트는 반드시 localhost DB에서만 실행한다. 이 원칙에는 예외가 없다.**

### 허용되는 DB 호스트

아래 호스트만 E2E 테스트 대상으로 허용한다:
- `localhost`
- `127.0.0.1`
- `0.0.0.0`
- `host.docker.internal` (Docker 내부에서 로컬 접근)
- `.e2e-allowed-hosts` 파일에 사용자가 등록한 호스트 (아래 "사용자 승인 화이트리스트" 참조)

### 사용자 승인 화이트리스트

프로젝트 루트의 `.e2e-allowed-hosts` 파일에 호스트를 한 줄에 하나씩 등록하면 해당 호스트도 허용된다.
이 파일은 `--init` 또는 게이트 차단 시 **사용자가 명시적으로 승인한 경우에만** 자동 생성/추가된다.

```
# .e2e-allowed-hosts 예시 (주석 및 빈 줄 무시)
dev-db.internal.example.com
10.0.1.50
```

- 이 파일은 `.gitignore`에 추가하여 커밋되지 않도록 한다.
- Claude가 스스로 이 파일을 생성하거나 수정하지 않는다. 반드시 사용자 승인 절차를 거친다.

### 절대 금지 사항

1. **무단 원격 DB 접근 금지**: 화이트리스트에 없는 원격 DB에 대한 모든 읽기/쓰기를 금지한다.
2. **PostgreSQL MCP를 통한 우회 금지**: PostgreSQL MCP 서버가 원격 DB에 연결되어 있더라도, 화이트리스트에 없으면 E2E 테스트 목적의 INSERT/UPDATE/DELETE SQL을 실행하지 않는다.
3. **"테스트 데이터니까 괜찮다"는 논리 금지**: 테스트 데이터라도 승인되지 않은 DB에 생성/수정/삭제하는 것은 금지다.
4. **.env 외 DB 접속 정보 사용 금지**: `secret/.env`에 정의된 DB 접속 정보만 사용한다.
5. **자동 화이트리스트 등록 금지**: Claude가 사용자 승인 없이 `.e2e-allowed-hosts`에 호스트를 추가하지 않는다.

### 위반 시 처리 (차단 → 승인 요청 → 화이트리스트 등록)

DB 호스트가 허용 목록(기본 + 화이트리스트)에 없으면:

1. **즉시 테스트를 중단**한다.
2. 사용자에게 경고와 함께 **승인 여부를 질문**한다:
   > ⚠️ **E2E 테스트 차단**: DB 호스트 `{호스트}`는 허용 목록에 없습니다.
   > 이 DB에서 E2E 테스트를 실행하면 테스트 데이터가 생성/수정/삭제됩니다.
   >
   > 이 DB를 E2E 테스트 대상으로 허용하시겠습니까? (허용하면 `.e2e-allowed-hosts`에 등록됩니다)
3. **사용자가 승인하면**:
   - `.e2e-allowed-hosts` 파일에 해당 호스트를 추가한다 (파일이 없으면 생성).
   - `.gitignore`에 `.e2e-allowed-hosts`가 없으면 추가한다.
   - 게이트 검증을 재실행하여 통과시킨다.
4. **사용자가 거부하면**: 어떤 SQL도 실행하지 않고 종료한다.

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

#### 1-1. 프로토콜 분류

변경된 파일 목록에서 프로토콜을 자동 감지한다:

| 감지 패턴 | 프로토콜 |
|----------|---------|
| `internal/handler/`, `internal/route/` 변경 | REST |
| `grpc_*_repository.go` 변경 | gRPC |
| proto import 경로 변경 (`BE.protobuf-definitions`) | gRPC |
| `*_vo.go`에 proto 관련 타입 추가/변경 | gRPC |
| REST + gRPC 모두 감지 | MIXED |

- `$ARGUMENTS`에 `--grpc`가 있으면 gRPC를 강제 지정한다.
- `$ARGUMENTS`에 `--rest`가 있으면 REST를 강제 지정한다.
- 감지 결과를 `$PROTOCOL` 변수에 저장한다: `REST` / `GRPC` / `MIXED`

**gRPC 엔드포인트 도출** (`$PROTOCOL`이 `GRPC` 또는 `MIXED`인 경우):
- `grpc_*_repository.go`에서 변경된 메서드명을 추출한다.
- 해당 서비스의 proto 정의에서 `{service}.v1.{ServiceName}/{MethodName}` 형태의 완전한 RPC 경로를 도출한다.
- `go-grpc-tools` 플러그인의 `find-proto.sh`를 사용하여 proto 소스 위치를 확인한다:
  ```bash
  bash ${go-grpc-tools plugin root}/skills/proto-gen/scripts/find-proto.sh {service}
  ```

### 2. 스펙 참조

#### REST 엔드포인트 (`$PROTOCOL`이 `REST` 또는 `MIXED`): Apidog 문서 참조
- `mcp__apidog__read_project_oas_n7eawf`로 OAS 전체 경로를 확인한다.
- `mcp__apidog__read_project_oas_ref_resources_n7eawf`로 각 엔드포인트의 상세 스펙(request/response schema)을 읽는다.
- 코드의 실제 request/response 구조체와 Apidog 스펙을 비교하여 차이점을 보고한다.

#### gRPC 엔드포인트 (`$PROTOCOL`이 `GRPC` 또는 `MIXED`): Proto 스펙 참조
- Step 1-1에서 확인한 `.proto` 파일에서 서비스/메시지 정의를 읽는다.
- **메시지 분석**:
  - 각 필드의 타입, `optional` 여부, `repeated` 여부
  - `oneof` 그룹과 소속 필드
  - `enum` 정의와 허용 값 목록
  - nested message 구조
- **Go 코드 교차 검증**: `grpc_*_repository.go`와 `*_vo.go`의 실제 구현과 proto 정의를 비교한다.
- **RPC 유형 분류**:
  | 유형 | 정의 | 테스트 지원 |
  |------|------|-----------|
  | Unary | `rpc Method(Req) returns (Res)` | 지원 |
  | Server Streaming | `rpc Method(Req) returns (stream Res)` | 지원 |
  | Client Streaming | `rpc Method(stream Req) returns (Res)` | `[SKIP:STREAMING]` |
  | Bidirectional | `rpc Method(stream Req) returns (stream Res)` | `[SKIP:STREAMING]` |

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

**엣지 케이스 카테고리 (공통):**
- **경계값**: 빈 문자열, 0, 음수, 매우 큰 값, 최대 길이 문자열
- **타입 불일치**: 숫자 필드에 문자열, 배열 필드에 단일 값
- **Null/Missing**: nullable 필드에 null vs 필드 자체 생략
- **중복/충돌**: 동일 ID로 재생성, 이미 삭제된 리소스 수정
- **소유권 경계값**: 아래 템플릿 참조

#### 소유권 경계값 테스트 케이스 템플릿

리소스에 소유자(owner)가 있는 API는 반드시 아래 케이스를 포함한다:

| # | 케이스 | 요청 조건 | 기대 결과 |
|---|--------|----------|----------|
| 1 | 본인 리소스 접근 | `Authorization: 소유자 토큰` + `리소스 ID` | 200 OK |
| 2 | 타인 리소스 접근 | `Authorization: 비소유자 토큰` + `리소스 ID` | 403 Forbidden |
| 3 | 미인증 접근 | `Authorization` 헤더 없음 + `리소스 ID` | 401 Unauthorized |
| 4 | 관리자 접근 | `Authorization: 관리자 토큰` + `타인 리소스 ID` | 200 OK (관리자 허용 시) 또는 403 |
| 5 | 삭제된 리소스 접근 | `Authorization: 소유자 토큰` + `soft-deleted 리소스 ID` | 404 Not Found |
| 6 | 존재하지 않는 리소스 | `Authorization: 소유자 토큰` + `미존재 ID` | 404 Not Found |

테스트 데이터 준비:
- 소유자 A의 리소스를 생성한다.
- 소유자 B의 토큰으로 A의 리소스에 접근을 시도한다.
- 소유자 구분이 JWT `userId` 기반이면 서로 다른 userId로 JWT를 2개 생성한다.
- **시간**: endAt < startAt, 과거 날짜, 시간대 차이
- **상태 전이**: 허용되지 않는 상태 변경 (e.g., removed → active)
- **관계**: 존재하지 않는 FK 참조, 삭제된 리소스 참조

**gRPC 특화 엣지 케이스** (`$PROTOCOL`이 `GRPC` 또는 `MIXED`인 경우 추가):
- **Proto3 기본값**: `0`, `""`, `false`가 명시적 전송인지 미전송인지 구분 불가 — `optional` 마커 없는 필드에서 서버가 기본값을 어떻게 처리하는지 확인
- **optional 필드**: proto에서 `optional`로 선언된 필드의 null vs 미전송 처리 차이
- **oneof 필드**: 여러 필드 동시 설정(마지막만 유효), 하나도 설정 안 함
- **repeated 필드**: 빈 배열 `[]`, 대량 요소(100+), 단일 요소
- **unknown fields**: proto에 정의되지 않은 필드 전송 시 무시 여부
- **메시지 크기**: gRPC 기본 4MB 제한 초과 시도 (대량 repeated 필드)
- **deadline/timeout**: 매우 짧은 deadline(1ms) 전송 시 `DEADLINE_EXCEEDED` 반환 여부
- **metadata 변조**: `authorization` metadata 누락, Bearer 없이 토큰만, 잘못된 형식

### 3-1. Status Code 의미적 정합성 검증

모든 에러 응답에 대해 **상태 코드가 에러의 원인(클라이언트/서버)과 일치하는지** 검증한다.
단순히 "에러가 반환되는가"가 아니라 "올바른 종류의 에러가 반환되는가"를 확인하는 단계이다.

#### REST 엔드포인트의 HTTP Status Code (`$PROTOCOL`이 `REST` 또는 `MIXED`)

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

#### gRPC 엔드포인트의 gRPC Status Code (`$PROTOCOL`이 `GRPC` 또는 `MIXED`)

| 원인 | 올바른 gRPC Status | 예시 |
|------|-------------------|------|
| 정상 처리 | OK (0) | 성공 응답 |
| 클라이언트 입력 오류 | INVALID_ARGUMENT (3) | 필수 필드 누락, 유효하지 않은 값, 타입 불일치 |
| 인증 없음 | UNAUTHENTICATED (16) | 토큰 없음, 만료된 토큰 |
| 권한 없음 | PERMISSION_DENIED (7) | 일반 유저가 ADMIN RPC 호출 |
| 리소스 없음 | NOT_FOUND (5) | 존재하지 않는 ID로 조회/수정/삭제 |
| 중복/충돌 | ALREADY_EXISTS (6) | 중복 생성, 이미 처리된 요청 |
| 서버 내부 오류 | INTERNAL (13) | 예상치 못한 런타임 에러 |
| 시간 초과 | DEADLINE_EXCEEDED (4) | deadline 초과 |

**검증 방법:**
1. Go 코드에서 `status.Errorf(codes.XXX, ...)` 또는 `status.Error(codes.XXX, ...)` 패턴을 Grep하여 각 에러 경로의 gRPC 코드를 추적한다.
2. 클라이언트 입력 오류가 `codes.Internal`로 반환되는 경우를 찾는다.
3. `domain.ErrNotFound` → 반드시 `codes.NotFound`로 매핑되는지 확인한다.

**E2E 실행 시 검증:**
- grpcurl 응답에서 gRPC status code를 파싱한다 (에러 시 `ERROR: Code: XXX` 형태로 출력됨).
- 기대 status와 실제 status를 비교한다.
- 불일치 시 **[GRPC_STATUS_MISMATCH]** 표기.

### 3-2. Edge Case Analyzer 에이전트 호출

Step 3, 3-1에서 도출한 엣지 케이스를 **비즈니스 로직 관점에서 보완**하기 위해, `edge-case-analyzer` 에이전트를 **엔드포인트별로 1회씩** 호출한다.

**호출 방법 (엔드포인트당 1회):**

Step 1에서 도출한 엔드포인트 목록을 순회하며, 각 엔드포인트마다 아래와 같이 호출한다.

```
Agent tool:
  subagent_type: minmos-harness:edge-case-analyzer
  prompt: |
    아래 API 엔드포인트의 엣지 케이스를 분석해줘.

    ## 대상 API
    {METHOD} {PATH}
    (gRPC인 경우: {service}.v1.{ServiceName}/{MethodName})

    ## 프로토콜
    {$PROTOCOL} (REST / GRPC / MIXED)

    ## gRPC 서비스 (GRPC/MIXED인 경우)
    {service}.v1.{ServiceName}/{MethodName}

    ## 프로젝트 루트
    {현재 작업 디렉토리 또는 worktree 경로}

    ## 모드
    incremental

    ## 이미 도출된 엣지 케이스
    {Step 3, 3-1에서 해당 엔드포인트에 대해 이미 도출한 엣지 케이스 요약}
```

> 엔드포인트가 여러 개이면 **병렬로 호출**하여 시간을 단축한다.

**질문 처리:**

에이전트는 `incremental` 모드에서 직접 질문하지 않고, `질문 및 확인 사항` 섹션에 기록만 반환한다.
- 에이전트 결과에 질문이 있으면, **e2e-test 스킬이 사용자에게 대신 질문**한다.
- 답변을 받으면 해당 답변을 반영하여 테스트 케이스를 보완한다.
- 답변이 없어도 `[답변 필요]` 태그가 붙은 케이스는 보고서에 조건부로 기록한다.

**결과 병합:**

에이전트가 반환한 증분 엣지 케이스를 테스트 케이스에 추가한다.

- 에이전트의 중복 판정 기준(endpoint + trigger condition + expected status/errcode + affected entity)으로 이미 필터링되어 반환되므로, 증분 케이스는 그대로 채택한다.
- `E2E 실행 가능 = Yes`인 **Critical/High** 항목은 반드시 E2E 테스트에 포함한다.
- `E2E 실행 가능 = Yes`인 **Medium** 항목은 테스트 가능한 경우 포함한다.
- `E2E 실행 가능 = No`인 항목 (동시성, 외부 연동 실패 등)은 **보고서에만 기록**하고 E2E 실행은 생략한다.
- **Low** 항목은 보고서에만 기록하고 테스트는 생략할 수 있다.

**에이전트에서 추가된 엣지 케이스는 결과 보고의 Edge Cases 테이블에 `[EA]` 태그를 붙여 구분한다.**

### 4. 테스트 환경 준비

#### 4-0. DB 호스트 안전 검증 (Gate — 통과 필수)

테스트 환경을 준비하기 **전에** 반드시 DB 호스트가 로컬인지 검증한다. 이 게이트를 통과하지 못하면 이후 모든 단계를 실행하지 않는다.

```bash
# 1. secret/.env에서 DB_HOST 추출
DB_HOST=$(grep -E '^DB_HOST=' secret/.env | head -1 | cut -d'=' -f2 | tr -d '[:space:]"'"'"'')

# 2. PostgreSQL MCP 서버의 연결 URL에서도 호스트 추출 (이중 검증)
MCP_DB_HOST=$(grep -oP '(?<=@)[^:/]+' .mcp.json 2>/dev/null | head -1)

# 3. 사용자 승인 화이트리스트 로드
ALLOWED_HOSTS="localhost 127.0.0.1 0.0.0.0 host.docker.internal"
if [ -f .e2e-allowed-hosts ]; then
  EXTRA_HOSTS=$(grep -v '^\s*#' .e2e-allowed-hosts | grep -v '^\s*$' | tr '\n' ' ')
  ALLOWED_HOSTS="$ALLOWED_HOSTS $EXTRA_HOSTS"
fi

echo "DB_HOST from .env: ${DB_HOST}"
echo "DB_HOST from MCP:  ${MCP_DB_HOST}"
echo "Allowed hosts:     ${ALLOWED_HOSTS}"
```

**검증 조건 (두 값 모두 통과해야 함):**

| 값 | 허용 | 차단 |
|----|------|------|
| `DB_HOST` | 기본 허용 목록 + `.e2e-allowed-hosts` + 빈 값(기본=localhost) | 그 외 모든 값 |
| `MCP_DB_HOST` | 위와 동일 | 그 외 모든 값 |

- 하나라도 허용 목록에 없으면 **즉시 중단**하고 "위반 시 처리" 절차(승인 요청)를 실행한다.
- `.mcp.json`이 없거나 postgres MCP가 미등록이면 MCP 검증은 건너뛴다 (MCP 없이 curl만으로 테스트하는 경우).
- **이 게이트를 우회하는 어떤 논리("읽기만 하겠다", "테스트 데이터만 건드리겠다" 등)도 허용하지 않는다. 반드시 사용자 승인을 거쳐 화이트리스트에 등록해야 한다.**

#### 4-1. 환경 파일 및 서버 준비

- `secret/.env`에서 포트와 DB 접속 정보를 확인한다.
- `secret/.env`와 `secret/gcp-sa-key.json`이 worktree에 존재하는지 확인하고, 없으면 원본 repo에서 복사한다.
- `go build -o /tmp/pms-test-server ./cmd/main.go`로 명시적 빌드 후 `/tmp/pms-test-server &`로 서버 실행한다.
  - **중요**: `go run`이 아닌 명시적 빌드된 바이너리를 실행해야 이전 프로세스와 혼동이 없다.
- JWT 토큰을 생성한다 (ADMIN role: `role_id=1`, 충분한 exp).
  - JWT_SECRET은 `secret/.env`의 `JWT_SECRET` 값을 사용한다.
  - Claims: `{"member_id":1,"member_old_id":1,"role_id":1,"is_staff":true,"uuid":"e2e-test","company_id":1,"exp":1900000000}`
  - **JWT_SECRET에 특수문자(`$`, `#`, `?` 등)가 포함된 경우** bash 기반 토큰 생성이 실패할 수 있다. 이 경우 Python 기반 생성을 기본으로 사용한다.
  - **주의: Go godotenv와 Python python-dotenv는 `$` 등 특수문자 해석이 다르다.** Go 서버가 godotenv로 로딩하므로, Python에서도 동일한 값을 사용해야 한다. `.env` 파일을 직접 파싱하여 raw 값을 추출한다:
    ```bash
    python3 -c "
    import jwt, re
    # python-dotenv 대신 직접 파싱 (godotenv와 동일한 raw 값 보장)
    secret = None
    with open('secret/.env') as f:
        for line in f:
            m = re.match(r'^JWT_SECRET=(.+)$', line.strip())
            if m:
                secret = m.group(1)
                # 따옴표 감싸진 경우 제거
                if len(secret) >= 2 and secret[0] == secret[-1] and secret[0] in ('\"', \"'\"):
                    secret = secret[1:-1]
                break
    if not secret:
        raise ValueError('JWT_SECRET not found in secret/.env')
    token = jwt.encode({'member_id':1,'member_old_id':1,'role_id':1,'is_staff':True,'uuid':'e2e-test','company_id':1,'exp':1900000000}, secret, algorithm='HS256')
    print(token)
    "
    ```
    - `pip install PyJWT`가 필요할 수 있다. 없으면 자동 설치 후 재시도한다.
- 필요 시 USER 토큰도 생성한다 (`role_id=2`).

#### 4-2. gRPC 환경 준비 (`$PROTOCOL`이 `GRPC` 또는 `MIXED`인 경우)

1. **grpcurl 검증**:
   ```bash
   which grpcurl || echo "grpcurl not found — gRPC 테스트를 실행할 수 없습니다"
   ```
   없으면 설치 안내 후 gRPC 테스트를 중단한다 (`$PROTOCOL`이 `MIXED`이면 REST 테스트만 계속).

2. **gRPC 포트 확인**:
   ```bash
   GRPC_PORT=$(grep -E '^GRPC_PORT=' secret/.env | head -1 | cut -d'=' -f2 | tr -d '[:space:]"'"'"'')
   echo "GRPC_PORT: ${GRPC_PORT:-50051}"
   ```
   `GRPC_PORT`가 없으면 기본값 `50051`을 사용하되, 사용자에게 확인한다.

3. **gRPC Reflection 확인** (서버 실행 후):
   ```bash
   grpcurl -plaintext localhost:${GRPC_PORT} list 2>&1
   ```
   - 성공 → Reflection 사용. proto import path 불필요.
   - 실패 → `find-proto.sh`로 proto 경로를 확보하여 grpcurl에 `-import-path` / `-proto` 옵션을 사용한다.

4. **gRPC JWT 전달**: REST과 동일한 JWT 토큰을 생성하되, gRPC에서는 metadata로 전달한다:
   ```bash
   -H "authorization: Bearer ${TOKEN}"
   ```

5. **서버 빌드/실행**: 4-1의 서버와 동일 바이너리를 공유한다 (REST + gRPC 동일 프로세스인 경우).
   별도 gRPC 서버 바이너리가 필요한 경우:
   ```bash
   go build -o /tmp/grpc-test-server ./cmd/grpc/main.go
   /tmp/grpc-test-server &
   ```

#### 테스트 데이터 추적 준비
- 테스트 시작 전, 관련 테이블의 현재 최대 ID를 기록한다.
  ```sql
  SELECT COALESCE(MAX(id), 0) FROM {table_name};
  ```
- 이 ID를 `BASELINE_ID`로 저장하여, 테스트 종료 시 이후 생성된 데이터를 식별한다.

#### 테스트 전제 데이터 준비

테스트 실행 **전에**, 모든 테스트 시나리오에 필요한 전제 데이터가 DB에 존재하는지 분석하고, 부족하면 PostgreSQL MCP를 통해 자동 생성한다.

**분석 대상 (Step 3 엣지 케이스 분석 결과 기반):**

| 테스트 시나리오 | 필요한 전제 데이터 | 예시 |
|----------------|------------------|------|
| 생성(Create) 테스트 | FK로 참조할 부모 데이터 | grade_id, publisher_id 등 FK 필드에 넣을 유효한 ID |
| 수정(Update) 테스트 | 수정 대상 데이터 | 테스트 중 Create API로 직접 생성 (시드 불필요) |
| 삭제(Delete) 테스트 | 삭제 대상 데이터 | 테스트 중 Create API로 직접 생성 (시드 불필요) |
| 필터/검색 테스트 | 필터 값별 대조 데이터 | 서로 다른 grade_id를 가진 데이터 2건 이상 |
| 상태 전이 테스트 | 특정 상태의 데이터 | status='active'인 데이터 (전이 출발점) |
| FK 참조 에러 테스트 | (불필요) | 존재하지 않는 ID 999999 사용 |
| 권한 테스트 | 다른 사용자의 데이터 | company_id가 다른 데이터 |

> 수정/삭제 대상 데이터는 Step 5에서 **Create API를 호출하여 직접 생성**한다 (시드가 아닌 API 생성 → ID 캡처 → 수정/삭제 흐름). 여기서는 그 Create API가 성공하기 위한 **전제 조건**만 준비한다.

**판단 절차:**

1. **테스트 대상 API의 request 스키마에서 FK 필드를 추출**한다.
   - handler의 request DTO에서 `*_id`, `*_ids` 패턴의 필드를 찾는다.
   - 해당 필드가 참조하는 테이블을 DB FK constraint 또는 코드 로직에서 확인한다.

2. **각 FK 참조 테이블에 유효한 데이터가 존재하는지 확인**한다.
   ```sql
   SELECT COUNT(*) FROM {referenced_table} WHERE status != 'removed';
   ```
   - 0건이면 → 해당 테이블에 시드 데이터 필요
   - 1건 이상이면 → 기존 데이터의 ID를 **읽기 전용으로 참조** (수정/삭제하지 않음)

3. **필터/검색 테스트용 데이터 존재 여부 확인**한다.
   ```sql
   SELECT DISTINCT {filter_column} FROM {table_name} WHERE status != 'removed' LIMIT 5;
   ```
   - 필터 값이 1종류 이하면 → 대조 테스트를 위해 2종 이상의 값을 가진 시드 데이터 필요

4. **상태 전이 테스트용 특정 상태 데이터 확인**한다.
   - 상태 전이 테스트가 있으면, 출발 상태의 데이터가 존재하는지 확인
   - 없으면 시드로 생성하거나, Step 5에서 Create API로 생성 후 진행

**생성 절차:**

1. **스키마 분석**: 대상 테이블의 컬럼, 타입, NOT NULL, FK, CHECK constraint를 확인한다.
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = '{table_name}' ORDER BY ordinal_position;
   ```
   CHECK constraint와 enum 값도 확인한다:
   ```sql
   SELECT conname, pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = '{table_name}'::regclass AND contype = 'c';
   ```

2. **FK 의존 순서 해결 (위상 정렬)**: FK가 참조하는 부모 테이블부터 순서대로 생성한다.
   ```sql
   -- FK 의존 관계 조회
   SELECT
     tc.table_name AS child_table,
     ccu.table_name AS parent_table,
     kcu.column_name AS fk_column
   FROM information_schema.table_constraints tc
   JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
   JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
   WHERE tc.constraint_type = 'FOREIGN KEY'
     AND tc.table_name IN ({테스트 관련 테이블 목록});
   ```
   ```
   예: publishers → grades → textbooks (textbooks가 publishers, grades를 FK 참조)
   생성 순서: publishers → grades → textbooks
   ```

3. **시드 INSERT**: PostgreSQL MCP로 필요한 최소한의 테스트 데이터를 삽입한다.

   **FK 참조용 부모 데이터:**
   - 테스트 API의 FK 필드가 참조하는 테이블에 데이터가 없으면 생성
   - Create/Update API가 성공하기 위한 **최소 1건**
   ```sql
   -- 예: textbook 생성 API 테스트 시, grade와 publisher가 필요
   INSERT INTO publishers (name, status) VALUES ('[E2E] Publisher A', 'active') RETURNING id;
   INSERT INTO grades (name, status) VALUES ('[E2E] Grade A', 'active') RETURNING id;
   ```

   **필터/검색 대조 데이터:**
   - 필터별로 최소 **2종 이상**의 다른 값을 가진 데이터를 생성 (대조 테스트)
   ```sql
   -- 예: grade_id 필터 테스트를 위해 서로 다른 grade에 연결된 데이터
   INSERT INTO grades (name, status) VALUES ('[E2E] Grade A', 'active'), ('[E2E] Grade B', 'active');
   INSERT INTO textbooks (title, grade_id, status) VALUES
     ('[E2E] Book 1', {grade_a_id}, 'active'),
     ('[E2E] Book 2', {grade_b_id}, 'active');
   ```

   **상태 전이 테스트용 데이터:**
   - 특정 상태의 데이터가 필요하면, 해당 상태로 직접 INSERT
   ```sql
   -- 예: 'active' → 'completed' 상태 전이 테스트
   INSERT INTO tasks (title, status) VALUES ('[E2E] Task for transition', 'active') RETURNING id;
   ```

   **권한 테스트용 데이터** (다른 소유자의 리소스):
   - 권한 체크 테스트가 있으면, 테스트 사용자와 다른 company_id/member_id의 데이터를 생성
   ```sql
   -- 예: company_id=999 (테스트 토큰의 company_id=1과 다른 값)
   INSERT INTO resources (title, company_id, status) VALUES ('[E2E] Other company resource', 999, 'active') RETURNING id;
   ```

4. **시드 BASELINE 기록**: 시드로 생성한 데이터도 `BASELINE_ID` 이후이므로, 테스트 종료 시 함께 정리된다.

5. **시드 결과 요약**: 생성된 시드 데이터를 기록하여 Step 5에서 참조할 수 있도록 한다.
   ```
   시드 데이터 요약:
   - publishers: id={id} ('[E2E] Publisher A')
   - grades: id={id_a} ('[E2E] Grade A'), id={id_b} ('[E2E] Grade B')
   - textbooks: id={id_1} (grade_id={id_a}), id={id_2} (grade_id={id_b})
   ```

**원칙:**
- 시드 데이터는 **테스트에 필요한 최소 수량**만 생성한다.
- 기존 데이터와 충돌하지 않도록 유니크 제약이 있는 컬럼은 `[E2E]` 접두사 등으로 구분한다.
- `RETURNING id`를 사용하여 생성된 ID를 즉시 캡처한다.
- 시드 생성이 실패하면 (권한 부족, constraint 위반 등) 에러를 보고하고 해당 테스트를 **SKIP** 처리한다.
- **기존 데이터는 읽기 전용 참조만 허용**한다 (FK 참조용 ID 조회). 수정/삭제하지 않는다.

### 5. E2E 테스트 실행
각 엔드포인트에 대해 실제 curl 요청을 수행한다.

**데이터 격리 규칙:**
- 수정/삭제 테스트 시 **반드시 이번 테스트에서 생성한 데이터만** 대상으로 한다.
- 테스트 흐름: 생성 → (생성된 ID 캡처) → 수정/삭제 → 검증
- 기존 데이터의 ID를 테스트에 사용하지 않는다.

**필터/검색 API 테스트 원칙:**

필터 파라미터(예: `gradeIds`, `locationIds`, `publisherIds` 등)를 테스트할 때, 임의의 값을 사용하면 결과가 0건이어도 필터가 작동하는지 깨졌는지 구분할 수 없다. 반드시 아래 절차를 따른다:

1. **유효한 필터 값 사전 조회**: 테스트 전에 DB에서 실제 데이터가 존재하는 ID를 조회한다.
   ```sql
   -- 예: grade 필터 테스트 시, 실제 연결된 grade_id 확인
   SELECT DISTINCT grade_id FROM {table_name} WHERE status != 'removed' LIMIT 5;
   -- 예: location 필터 테스트 시
   SELECT DISTINCT location_id FROM {table_name} WHERE status != 'removed' LIMIT 5;
   ```
   조회된 ID가 없으면 **테스트용 시드 데이터를 PostgreSQL MCP로 직접 생성**한다 (아래 "테스트 시드 데이터 생성" 참조).

2. **필터 효과 검증 (대조 테스트)**: 필터가 실제로 결과를 좁히는지 확인한다.
   - **A (기준)**: 필터 없이 전체 조회 → `total_count` 기록
   - **B (필터 적용)**: 유효한 ID로 필터 조회 → `filtered_count` 기록
   - **판정**: `filtered_count < total_count`이면 필터 작동 확인. `filtered_count == total_count`이면 필터가 무시되고 있을 가능성 → **[FILTER_INEFFECTIVE]** 표기
   - **C (존재하지 않는 값)**: DB에 없는 ID(예: 999999)로 필터 → 0건이어야 함. 0건이 아니면 **[FILTER_BROKEN]** 표기

3. **복합 필터**: 여러 필터를 동시 적용할 때도 위 대조 테스트를 수행한다.

**테스트 케이스 구성 (REST — `$PROTOCOL`이 `REST` 또는 `MIXED`인 경우):**

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

**각 요청마다 기록 (REST):**
- HTTP method + path
- Request body (요약)
- Response status code
- Response body (요약)
- 기대값과 일치 여부

#### gRPC 테스트 실행 (`$PROTOCOL`이 `GRPC` 또는 `MIXED`인 경우)

**도구**: `grpcurl` (curl 대신 사용)

**Reflection 사용 가능 시:**
```bash
# Unary RPC
grpcurl -plaintext \
  -d '{"field":"value"}' \
  -H "authorization: Bearer ${TOKEN}" \
  localhost:${GRPC_PORT} \
  {service}.v1.{ServiceName}/{MethodName}

# Server Streaming RPC
grpcurl -plaintext \
  -d '{"field":"value"}' \
  -H "authorization: Bearer ${TOKEN}" \
  localhost:${GRPC_PORT} \
  {service}.v1.{ServiceName}/{StreamMethodName}
```

**Reflection 미사용 시 (proto import 필요):**
```bash
grpcurl -plaintext \
  -import-path {proto_dir} \
  -proto {service}/v1/{service}.proto \
  -d '{"field":"value"}' \
  -H "authorization: Bearer ${TOKEN}" \
  localhost:${GRPC_PORT} \
  {service}.v1.{ServiceName}/{MethodName}
```

**gRPC 테스트 케이스 구성:**

##### A. Happy Path
- Unary RPC 호출 → gRPC OK (0) 및 response 구조 확인
- 반환된 데이터를 조회 RPC(또는 REST GET)로 반영 확인
- Server Streaming RPC → 스트림 수신 완료, 응답 구조 확인

##### B. Validation (필수 필드/타입)
- 필수 필드 누락 → INVALID_ARGUMENT (3)
- 잘못된 enum 값 → INVALID_ARGUMENT (3)
- 빈 repeated 필드 (required) → INVALID_ARGUMENT (3)
- 잘못된 타입 (문자열 → 숫자 필드) → INVALID_ARGUMENT (3)

##### C. gRPC 특화 엣지 케이스
- Proto3 기본값 전송 (0, "", false) → 서버 처리 확인
- optional 필드 null vs 미전송 → 서버 구분 확인
- oneof 다중 설정 → 마지막만 유효 확인
- 대량 repeated 요소 → 응답 확인 또는 RESOURCE_EXHAUSTED
- deadline 1ms → DEADLINE_EXCEEDED (4): `grpcurl -max-time 0.001 ...`
- metadata 없음 → UNAUTHENTICATED (16)
- metadata 변조 (Bearer 없이 토큰만) → UNAUTHENTICATED (16)

##### D. 인증/권한
- metadata에 authorization 없이 요청 → UNAUTHENTICATED (16)
- USER 역할 토큰으로 ADMIN 전용 RPC 호출 → PERMISSION_DENIED (7)

##### E. gRPC Status Code 정합성
Step 3-1에서 식별한 gRPC status code 케이스를 실제 grpcurl로 검증한다.
- 존재하지 않는 ID → NOT_FOUND (5) 확인 (INTERNAL이면 [GRPC_STATUS_MISMATCH])
- 삭제된 리소스 참조 → NOT_FOUND (5) 확인
- domain.ErrNotFound 경로 → NOT_FOUND (5) 확인
- Client Streaming / Bidirectional RPC → `[SKIP:STREAMING]` 표기, 실행 생략

**각 요청마다 기록 (gRPC):**
- RPC 경로 (`{service}.v1.{ServiceName}/{MethodName}`)
- Request JSON
- gRPC status code + message
- Response JSON (성공 시)
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

#### gRPC 테스트 결과 (`$PROTOCOL`이 `GRPC` 또는 `MIXED`인 경우)

`$PROTOCOL`이 `MIXED`이면 REST와 gRPC 결과를 **섹션 분리**하여 보고한다.

```markdown
### gRPC 테스트 결과

#### 테스트 대상 RPC
- {service}.v1.{ServiceName}/{MethodName} - 설명

#### Happy Path
| # | 테스트 | gRPC Status | 결과 | 비고 |
|---|--------|-------------|------|------|
| 1 | 설명 | OK (0) | 성공/실패 | 상세 |

#### Validation
| # | 테스트 | gRPC Status | 기대 | 결과 | 비고 |
|---|--------|-------------|------|------|------|
| 1 | 설명 | INVALID_ARGUMENT (3) | INVALID_ARGUMENT | 성공/실패 | 상세 |

#### gRPC 특화 Edge Cases
| # | 테스트 | gRPC Status | 기대 | 결과 | 비고 |
|---|--------|-------------|------|------|------|
| 1 | Proto3 기본값 | xxx | xxx | 성공/실패 | 상세 |

#### 인증/권한
| # | 테스트 | gRPC Status | 결과 | 비고 |
|---|--------|-------------|------|------|
| 1 | metadata 없음 | UNAUTHENTICATED (16) | 성공/실패 | 상세 |

#### gRPC Status Code 정합성
| # | 테스트 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 판정 |
|---|----------------|----------|------------|------------|------|
| 1 | 존재하지 않는 ID | 리소스 없음 | NOT_FOUND (5) | NOT_FOUND/INTERNAL | OK / [GRPC_STATUS_MISMATCH] |

#### Streaming RPC (미실행)
| # | RPC | 유형 | 사유 |
|---|-----|------|------|
| 1 | {ServiceName}/{MethodName} | Client Streaming / Bidirectional | [SKIP:STREAMING] grpcurl 미지원 |

### gRPC Status Code 오분류 ([GRPC_STATUS_MISMATCH])
| # | RPC | 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 위치 (파일:라인) |
|---|-----|---------|----------|------------|------------|----------------|
| 1 | [{ServiceName}/{Method}] | [시나리오] | [클라이언트/서버] | [NOT_FOUND] | [INTERNAL] | [파일:라인] |

- **수정 방향**: [gRPC handler에서 도메인 에러를 적절한 gRPC status code로 매핑 등]
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
- gRPC 별도 서버를 실행한 경우: `pkill -f grpc-test-server && rm -f /tmp/grpc-test-server`
