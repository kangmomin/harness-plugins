---
name: e2e-test-mm
description: "기능 추가/수정 후 연관 API(REST+gRPC)를 실제 요청으로 E2E 테스트한다. 'E2E 테스트 돌려줘', 'API 실제로 검증해줘' 요청 시 사용. 로컬 DB 전용, 테스트 데이터 격리·정리 포함. start-workflow-mm 품질 루프에서 자동 호출됨."
user-invocable: true
---

# E2E API 테스트

기능 추가 또는 수정이 완료된 후, 연관된 API들을 실제 요청으로 E2E 테스트한다.

## Prerequisites

### 필요 환경

- **Apidog MCP 서버**: Apidog 스펙 참조/비교용 (REST)
- **PostgreSQL MCP 서버** (읽기/쓰기): 테스트 데이터 생성, BASELINE_ID 기록, soft-delete 정리용
- **grpcurl** (선택): gRPC 엔드포인트 테스트가 필요한 경우에만 필수
- **Dev PubSub CLI** (선택): PubSub 연동 테스트가 필요한 경우에만 필수. `dev-pubsub-cli` 또는 로컬 clone의 `uv run dev-pubsub-cli`

> **MCP 판정**: 실제 MCP tool 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다 (상세: `/minmos-harness:minmo-doctor-mm`).

### 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--init` | | 초기 세팅 후 종료 |
| `--doctor` | | 상태 진단 후 종료 |
| `--skip-doctor` | `-sd` | 실행 전 자동 probe 점검을 건너뜀 (사용자 책임) |
| `--grpc` | | gRPC 프로토콜 강제 지정 |
| `--rest` | | REST 프로토콜 강제 지정 |

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **Apidog MCP 연결 확인**: `mcp__apidog__read_project_oas_*` 호출 가능 여부 확인. 불가하면 `/minmos-harness:apidog-schema-gen-mm --init`과 동일한 Apidog 세팅을 안내한다.
2. **PostgreSQL MCP 연결 확인**: PostgreSQL MCP로 `SELECT 1` 실행. 불가하면 안내:
   > "PostgreSQL MCP 서버에 연결할 수 없습니다. 사용하는 MCP 클라이언트 설정에 아래 서버를 등록하세요 (Claude/Codex는 `.mcp.json`, 일부 클라이언트는 별도 MCP 설정 위치):"
   > ```json
   > { "mcpServers": { "postgres": { "command": "npx", "args": ["-y", "@anthropic/postgres-mcp", "<DATABASE_URL>"] } } }
   > ```
   - `secret/.env`의 DB 접속 정보로 DATABASE_URL을 자동 구성할 수 있으면 제안한다.
   - `.mcp.json`을 쓰는 환경이면 유저 동의 시 자동 추가, 별도 MCP 설정을 쓰는 환경이면 해당 위치 등록을 안내한다.
3. **DB 호스트 검증**: `secret/.env`의 `DB_HOST`가 로컬이 아니면 사용자 승인을 받아 `secret/.e2e-allowed-hosts`에 등록하거나, 거부 시 로컬 DB로 변경하라고 안내한다.
4. **grpcurl 확인** (선택): `which grpcurl`. 없으면 설치 안내 (macOS: `brew install grpcurl` / Go: `go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest`). gRPC 테스트가 불필요하면 건너뛴다.
5. **Dev PubSub CLI 확인** (선택): `which dev-pubsub-cli`. 없으면 `which uv` 확인 후 설치 안내:
   ```bash
   # Global 설치 (추천)
   uv tool install git+https://github.com/Jiyong-Jeon/dev_pubsub_emulator.git
   # Local 설치: git clone 후 uv sync, 실행은 uv run dev-pubsub-cli
   ```
   PubSub 테스트가 불필요하면 건너뛴다.
6. 결과를 요약 보고한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## E2E Test — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 연결 | OK / MISSING / FAIL | 실제 MCP 호출 기준 |
| Apidog MCP 응답 | OK / FAIL / SKIP | OAS 읽기 시도 |
| PostgreSQL MCP 연결 | OK / MISSING / FAIL | `SELECT 1` 시도 |
| secret/.env 존재 | OK / MISSING | JWT_SECRET, DB 접속 정보 |
| Go 빌드 | OK / FAIL | go build 시도 |
| DB 호스트 (로컬 전용) | OK / **BLOCKED** | DB_HOST가 localhost/127.0.0.1인지 확인 |
| MCP DB 호스트 (로컬 전용) | OK / **BLOCKED** / UNKNOWN / SKIP | PostgreSQL MCP `inet_server_addr()` 확인 |
| grpcurl 설치 (선택) | OK / MISSING | grpcurl --version |
| GRPC_PORT (선택) | OK / MISSING / SKIP | secret/.env 확인 |
| gRPC Docker 연결 (선택) | OK / FAIL / SKIP | `{service}-grpc.{service}.svc.cluster.local:9032` 접근 가능 여부 |
| gRPC 외부 서비스 의존성 (선택) | OK / FAIL / SKIP | 코드에서 외부 gRPC 호출 감지, 해당 서비스 접근 가능 여부 |
| Dev PubSub CLI (선택) | OK (Global) / OK (Local) / MISSING | which dev-pubsub-cli |
| PubSub Emulator (선택) | RUNNING / STOPPED | curl localhost:8086/api/stats |
```

- **BLOCKED** 항목이 하나라도 있으면 E2E 테스트를 실행할 수 없다고 경고하고, 해당 DB를 허용할지 질문한다. 승인하면 `secret/.e2e-allowed-hosts`에 등록한다.
- 문제가 있으면 `--init` 실행을 안내한다.

## 핵심 원칙

### 로컬 DB 전용 실행 (절대 원칙)

> **E2E 테스트는 반드시 localhost DB에서만 실행한다. 이 원칙에는 예외가 없다.**

- 허용 호스트: `localhost` / `127.0.0.1` / `0.0.0.0` / `host.docker.internal` / `secret/.e2e-allowed-hosts`에 **사용자가 명시적으로 승인 등록한** 호스트만.
- 무단 원격 DB 접근 금지. PostgreSQL MCP를 통한 우회 금지. "테스트 데이터니까 괜찮다"는 논리 금지. `secret/.env` 외 DB 접속 정보 사용 금지. 사용자 승인 없는 화이트리스트 자동 등록 금지.
- 검증 게이트·차단 시 승인 절차·화이트리스트 형식의 canonical: `references/db-safety.md`.

### 테스트 데이터 격리

**기존 데이터를 절대 수정/삭제하지 않는다.** 모든 테스트 데이터는 E2E 전용으로 생성하고, 종료 시 정리한다.

- 수정/삭제 테스트: 먼저 테스트용 데이터를 생성 → 생성된 ID로 수정/삭제 → 검증
- 기존 데이터의 ID를 하드코딩하여 수정/삭제하지 않는다.

## Step 1: Pre-flight Probe (Fast SKIP Gate)

`--skip-doctor`/`-sd`가 **없으면** 테스트 실행 전 빠른 환경 probe를 실행한다.
**실패가 확정된 환경에서는 테스트를 시도하지 않고 즉시 SKIPPED를 반환한다** — 부분 실행 후 실패 판정이 아니라, 진입 게이트에서 끊어낸다.

| # | 확인 항목 | 확인 방법 | FAIL 시 반환 |
|---|----------|----------|-------------|
| 1 | `secret/.env` 존재 | 파일 존재 확인 | `SKIPPED:ENV_MISSING` — 서버 부팅 불가 |
| 2 | PostgreSQL MCP 연결 | `SELECT 1` | `SKIPPED:POSTGRES_MCP_UNAVAILABLE` — DB 시드/정리 불가 |
| 3 | DB 호스트 로컬 전용 | `DB_HOST` + MCP `inet_server_addr()` | 화이트리스트 승인 절차로 이동, 거부 시 `SKIPPED:REMOTE_DB_BLOCKED` |
| 4 | Go 빌드 | `go build ./cmd/main.go` | `FAIL:BUILD` — 코드 문제, 빌드 에러 보고 (SKIP 아님) |

처리 규칙:
- 모두 OK → 한 줄 요약 후 Step 2로 진행.
- #1~#2 FAIL → 즉시 SKIP 반환 후 종료 (테스트 실패가 아닌 환경 미충족):
  ```
  ## E2E Test — SKIPPED
  사유: SKIPPED:{코드}
  누락 항목: {항목}
  복구 방법: /minmos-harness:e2e-test-mm --init
  ```
- 선택 항목(Apidog MCP, grpcurl, Dev PubSub CLI)은 probe의 SKIP 트리거가 아니다 — 해당 프로토콜 테스트 시작 시 개별 판정한다.

## Step 2: 변경 범위 파악

- `git diff` 또는 현재 대화 컨텍스트에서 변경된 파일을 파악한다.
- 변경된 handler/route 기반으로 **영향받는 API 엔드포인트 목록**을 도출한다.
- 직접 변경된 API뿐 아니라, 같은 도메인의 연관 API(예: POST 변경 시 GET 조회도 포함)를 리스트업한다.

### Step 2.1: 프로토콜 분류

**직접 감지 (파일 경로 기반)**:

| 감지 패턴 | 프로토콜 |
|----------|---------|
| `internal/handler/`, `internal/route/` 변경 | REST |
| `grpc_*_repository.go` 변경 | gRPC |
| proto import 경로 변경 (`BE.protobuf-definitions`) | gRPC |
| `*_vo.go`에 proto 관련 타입 추가/변경 | gRPC |
| REST + gRPC 모두 감지 | MIXED |

**역추적 감지** — 직접 감지 0건이지만 usecase/repository/domain이 변경된 경우:

1. `git diff`에서 변경된 함수명을 추출한다.
2. 호출자를 Grep으로 역추적한다:
   ```bash
   grep -rn '{변경된함수명}' internal/handler/ internal/route/ --include='*.go'
   grep -rn '{변경된함수명}' internal/*/infra/grpc_*_repository.go
   ```
3. 호출자가 발견되면 해당 handler/grpc_repository에서 엔드포인트를 역으로 도출한다.
4. 호출자가 REST handler이면 REST, grpc_repository이면 gRPC, 둘 다이면 MIXED.

> **핵심**: usecase만 변경해도 그 usecase를 호출하는 엔드포인트는 E2E 테스트 대상이다.

- `--grpc` / `--rest` 플래그가 있으면 해당 프로토콜을 강제 지정한다.
- 감지 결과를 `$PROTOCOL`에 저장: `REST` / `GRPC` / `MIXED`.
- **gRPC 엔드포인트 도출** (GRPC/MIXED): 변경/역추적된 grpc_repository 메서드명에서 `{service}.v1.{ServiceName}/{MethodName}` RPC 경로를 도출한다. proto 소스 위치는 `go-grpc-tools` 플러그인의 find-proto.sh 사용:
  ```bash
  bash ${go-grpc-tools plugin root}/skills/proto-gen/scripts/find-proto.sh {service}
  ```

## Step 3: 스펙 참조

**REST** (`REST`/`MIXED`): Apidog 문서 참조.
- `mcp__apidog__read_project_oas_*` 패턴 도구로 OAS 전체 경로를 확인한다 (기본: `mcp__apidog__read_project_oas_n7eawf`).
- `mcp__apidog__read_project_oas_ref_resources_*`로 각 엔드포인트의 상세 스펙(request/response schema)을 읽는다 (기본: `..._n7eawf`).
- 코드의 실제 request/response 구조체와 Apidog 스펙을 비교하여 차이점을 보고한다.

**gRPC** (`GRPC`/`MIXED`):

> MUST: 같은 폴더의 `references/grpc-testing.md`를 Read하고 "Step 3: Proto 스펙 참조" 절차를 따른다.

## Step 4: 엣지 케이스 분석

코드베이스와 Apidog 스펙을 기반으로 엣지 케이스를 도출한다.

**코드베이스 분석:**
- handler request DTO의 `binding` 태그 (`required`, `dive`, `min`, `max`, `oneof` 등)
- domain command/VO 생성 함수의 validation 로직 (nil 반환 조건 전부 추출)
- usecase의 비즈니스 validation (존재 여부, 상태, 권한 체크)
- DB check constraint, enum 값, FK 관계
- 포인터 필드(*type)는 null 허용 → null 전송 테스트
- 배열 필드는 빈 배열/단일/다수 케이스 테스트

**Apidog 스펙 분석:**
- `required` 필드 목록 ↔ 코드 `binding:"required"` 비교
- `enum` 값 목록 ↔ 코드 validation enum 비교
- `nullable` 타입(`["string", "null"]`) → null 전송 테스트
- `format` (date-time, email 등) → 잘못된 포맷 전송 테스트

**공통 카테고리:** 경계값(빈 문자열/0/음수/최대 길이) · 타입 불일치 · Null vs Missing · 중복/충돌 · 시간(endAt < startAt, 과거 날짜, 시간대) · 상태 전이(비허용 전이) · 관계(미존재 FK, 삭제된 리소스 참조) · 소유권 경계값(아래 표)

### 소유권 경계값 테스트 케이스 템플릿

리소스에 소유자(owner)가 있는 API는 반드시 아래 케이스를 포함한다:

| # | 케이스 | 요청 조건 | 기대 결과 |
|---|--------|----------|----------|
| 1 | 본인 리소스 접근 | 소유자 토큰 + 리소스 ID | 200 OK |
| 2 | 타인 리소스 접근 | 비소유자 토큰 + 리소스 ID | 403 Forbidden |
| 3 | 미인증 접근 | Authorization 헤더 없음 | 401 Unauthorized |
| 4 | 관리자 접근 | 관리자 토큰 + 타인 리소스 ID | 200 OK (관리자 허용 시) 또는 403 |
| 5 | 삭제된 리소스 접근 | 소유자 토큰 + soft-deleted ID | 404 Not Found |
| 6 | 존재하지 않는 리소스 | 소유자 토큰 + 미존재 ID | 404 Not Found |

테스트 데이터 준비: 소유자 A의 리소스 생성 → 소유자 B의 토큰으로 접근 시도. 소유자 구분이 JWT `userId` 기반이면 서로 다른 userId로 JWT 2개 생성.

**gRPC 특화 엣지 케이스** (`GRPC`/`MIXED`): `references/grpc-testing.md`의 "Step 4" 섹션을 따른다.

## Step 5: Status Code 의미적 정합성 검증

> MUST: 같은 폴더의 `references/status-code-validation.md`를 Read하고 분류 기준·검증 방법을 따른다.

- REST: 에러 원인(클라이언트/서버)과 HTTP status 일치 검증. 불일치는 `[STATUS_MISMATCH]`.
- gRPC: gRPC status code 일치 검증. 불일치는 `[GRPC_STATUS_MISMATCH]`.

## Step 6: Edge Case Analyzer 에이전트 호출

Step 4~5에서 도출한 엣지 케이스를 비즈니스 로직 관점에서 보완하기 위해, `edge-case-analyzer` 에이전트를 **엔드포인트별로 1회씩** 호출한다 (엔드포인트가 여러 개이면 병렬 호출).

```
Agent tool:
  subagent_type: be-harness:edge-case-analyzer
  prompt: |
    아래 API 엔드포인트의 엣지 케이스를 분석해줘.

    ## 대상 API
    {METHOD} {PATH}
    (gRPC인 경우: {service}.v1.{ServiceName}/{MethodName})

    ## 프로토콜
    {$PROTOCOL} (REST / GRPC / MIXED)

    ## 프로젝트 루트
    {현재 작업 디렉토리 또는 worktree 경로}

    ## 모드
    incremental

    ## 이미 도출된 엣지 케이스
    {Step 4~5에서 해당 엔드포인트에 대해 이미 도출한 엣지 케이스 요약}
```

**질문 처리**: 에이전트는 `incremental` 모드에서 직접 질문하지 않고 `질문 및 확인 사항` 섹션에 기록만 반환한다. 질문이 있으면 본 스킬이 사용자에게 대신 질문하고, 답변을 반영한다. 답변이 없으면 `[답변 필요]` 태그 케이스는 보고서에 조건부로 기록한다.

**결과 병합**:
- 에이전트가 중복 필터링(endpoint + trigger condition + expected status + affected entity)을 거쳐 반환하므로 증분 케이스는 그대로 채택한다.
- `E2E 실행 가능 = Yes`인 **Critical/High** → 반드시 포함. **Medium** → 가능하면 포함.
- `E2E 실행 가능 = No`(동시성, 외부 연동 실패 등) / **Low** → 보고서에만 기록, 실행 생략.
- 에이전트 추가 케이스는 보고서 Edge Cases 테이블에 `[EA]` 태그로 구분한다.

## Step 7: 테스트 환경 준비

> Step 7 진입 시 MUST: 같은 폴더의 `references/db-safety.md`를 Read하고
> ① Step 7.1 DB 호스트 안전 검증(Gate)을 먼저 통과 ② Step 7.4 BASELINE 기록 ③ Step 7.5 시드 데이터 준비를 따른다.

### Step 7.2: 환경 파일 및 서버 준비

- `secret/.env`에서 포트와 DB 접속 정보를 확인한다.
- `secret/.env`와 `secret/gcp-sa-key.json`이 worktree에 존재하는지 확인하고, 없으면 원본 repo에서 복사한다.
- `go build -o /tmp/pms-test-server ./cmd/main.go`로 명시적 빌드 후 `/tmp/pms-test-server &`로 실행한다.
  - **중요**: `go run`이 아닌 명시적 빌드 바이너리를 실행해야 이전 프로세스와 혼동이 없다.
- JWT 토큰을 생성한다 (ADMIN role: `role_id=1`, 충분한 exp).
  - JWT_SECRET은 `secret/.env`의 값을 사용. Claims: `{"member_id":1,"member_old_id":1,"role_id":1,"is_staff":true,"uuid":"e2e-test","company_id":1,"exp":1900000000}`
  - **JWT_SECRET에 특수문자(`$`, `#`, `?` 등)가 있으면** bash 기반 생성이 실패할 수 있다 → Python 기반 생성을 기본 사용.
  - **주의: Go godotenv와 Python python-dotenv는 `$` 등 특수문자 해석이 다르다.** `.env`를 직접 파싱하여 raw 값을 추출한다:
    ```bash
    python3 -c "
    import jwt, re
    secret = None
    with open('secret/.env') as f:
        for line in f:
            m = re.match(r'^JWT_SECRET=(.+)$', line.strip())
            if m:
                secret = m.group(1)
                if len(secret) >= 2 and secret[0] == secret[-1] and secret[0] in ('\"', \"'\"):
                    secret = secret[1:-1]
                break
    if not secret:
        raise ValueError('JWT_SECRET not found in secret/.env')
    token = jwt.encode({'member_id':1,'member_old_id':1,'role_id':1,'is_staff':True,'uuid':'e2e-test','company_id':1,'exp':1900000000}, secret, algorithm='HS256')
    print(token)
    "
    ```
    `PyJWT`가 없으면 자동 설치 후 재시도한다.
- 필요 시 USER 토큰도 생성한다 (`role_id=2`).

### Step 7.3: gRPC 환경 준비 (`GRPC`/`MIXED`)

> MUST: `references/grpc-testing.md`의 "Step 7.3" 절차를 따른다 (grpcurl 검증, 포트/대상 주소, 외부 의존성 점검, Reflection, JWT metadata).

## Step 8: E2E 테스트 실행

각 엔드포인트에 대해 실제 요청을 수행한다.

**데이터 격리 규칙**: 수정/삭제 테스트는 **반드시 이번 테스트에서 생성한 데이터만** 대상으로 한다 (생성 → ID 캡처 → 수정/삭제 → 검증).

**필터/검색 API 테스트 원칙** — 임의 값으로는 "0건 = 필터 작동"인지 "0건 = 깨짐"인지 구분 불가:

1. **유효한 필터 값 사전 조회**: `SELECT DISTINCT {filter_column} FROM {table} WHERE status != 'removed' LIMIT 5;` — 없으면 시드 생성 (`references/db-safety.md`).
2. **대조 테스트**: A(필터 없음, total_count) vs B(유효 ID 필터, filtered_count) — `filtered_count == total_count`이면 `[FILTER_INEFFECTIVE]`. C(미존재 ID 999999) → 0건 아니면 `[FILTER_BROKEN]`.
3. **복합 필터**도 동일 대조 테스트.

**REST 테스트 케이스 구성** (`REST`/`MIXED`):

- **A. Happy Path**: 생성 → status/구조 확인 → 조회로 반영 확인 → 생성한 ID로 수정 → 변경 확인 → 생성한 ID로 삭제 → 삭제 확인
- **B. Validation**: 필수 필드 하나씩 누락 / 잘못된 enum / 빈 required 배열 / 잘못된 타입 → 400
- **C. 엣지 케이스** (Step 4 도출): domain validation nil 조건 전부, DB constraint 위반, 경계값, Null/Missing, 시간 엣지, 미존재 리소스 참조(999999 등)
- **D. 인증/권한**: 토큰 없음 → 401, USER 역할로 ADMIN API → 403
- **E. Status Code 정합성** (Step 5 식별 케이스): 미존재 FK 참조 → 404 (500이면 `[STATUS_MISMATCH]`), 삭제된 리소스 → 404, RowsAffected 불일치 → 404, `domain.ErrNotFound` 경로 → 404

각 요청마다 기록: HTTP method + path / Request body 요약 / Response status + body 요약 / 기대값 일치 여부.

**gRPC 테스트 실행** (`GRPC`/`MIXED`):

> MUST: `references/grpc-testing.md`의 "Step 8" 절차를 따른다 (grpcurl 실행 형식, 케이스 구성 A~E, 기록 항목).

## Step 9: 결과 보고

> MUST: 같은 폴더의 `references/report-templates.md`의 양식대로 보고한다 (REST / gRPC 섹션 분리, 섹션 머리글 변경 금지).

## Step 10: 정리

**테스트 데이터 정리** (우선순위):
1. **삭제 API 호출**: DELETE API가 있으면 테스트에서 생성한 ID로 삭제 요청
2. **DB soft-delete**: 없으면 `UPDATE {table} SET status = 'removed' WHERE id > {BASELINE_ID};`
3. **연관 데이터 정리**: FK 하위 테이블도 함께:
   ```sql
   UPDATE {child_table} SET status = 'removed' WHERE {parent_fk} IN (
     SELECT id FROM {parent_table} WHERE id > {BASELINE_ID}
   );
   ```

정리 확인: `SELECT COUNT(*) FROM {table} WHERE id > {BASELINE_ID} AND status != 'removed'` → 0건 확인 후 보고에 포함.

**서버 정리**:
- `pkill -f pms-test-server && rm -f /tmp/pms-test-server`
- gRPC 별도 서버를 실행한 경우: `pkill -f grpc-test-server && rm -f /tmp/grpc-test-server`

## 상태 코드

| 코드 | 의미 |
|------|------|
| `SKIPPED:ENV_MISSING` | secret/.env 없음 — 환경 미충족 (실패 아님) |
| `SKIPPED:POSTGRES_MCP_UNAVAILABLE` | PostgreSQL MCP 연결 불가 |
| `SKIPPED:REMOTE_DB_BLOCKED` | 원격 DB — 화이트리스트 미승인 |
| `FAIL:BUILD` | 빌드 실패 — 코드 문제 (SKIP 아님) |
| `SKIP:STREAMING` | Client/Bidirectional Streaming RPC — grpcurl 미지원 |
| `[STATUS_MISMATCH]` / `[GRPC_STATUS_MISMATCH]` | 상태 코드 오분류 발견 |
| `[FILTER_INEFFECTIVE]` / `[FILTER_BROKEN]` | 필터 미작동/오작동 발견 |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/db-safety.md` | Step 7 진입 시 (DB 게이트·시드 준비 canonical) |
| `references/status-code-validation.md` | Step 5 진입 시 |
| `references/grpc-testing.md` | `$PROTOCOL`이 GRPC/MIXED일 때 (Step 3/4/7/8) |
| `references/report-templates.md` | Step 9 진입 시 |
