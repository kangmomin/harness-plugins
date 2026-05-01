---
name: minmo-doctor-mm
description: "minmos-harness 플러그인의 모든 의존성 상태를 한 번에 진단한다."
---

# minmos-harness Doctor

플러그인이 정상 동작하기 위한 모든 의존성을 한 번에 점검하고, 문제가 있으면 해결 방법을 안내한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## 점검 항목

### 1. MCP 서버

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| Apidog MCP 연결 | `mcp__apidog__read_project_oas_*` 호출 시도 | apidog-schema-gen, e2e-test |
| Apidog MCP 응답 | OAS 읽기 응답 확인 | apidog-schema-gen |
| PostgreSQL MCP 연결 | PostgreSQL MCP로 `SELECT 1` 쿼리 시도 | e2e-test |
| PostgreSQL MCP DB 호스트 | PostgreSQL MCP로 `SELECT inet_server_addr()` 쿼리 시도 | e2e-test |

**판정 원칙**: `.mcp.json`은 설정 안내용 참고 자료일 뿐, 연결 여부의 단독 기준으로 쓰지 않는다. OpenCode처럼 MCP를 다른 위치에 설정하는 클라이언트도 있으므로 실제 MCP tool 호출이 성공하면 `.mcp.json` 존재 여부와 무관하게 OK로 판정한다.

### 2. 환경 변수

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| APIDOG_ACCESS_TOKEN | `${APIDOG_ACCESS_TOKEN:+set}` | apidog-schema-gen (Push) |
| APIDOG_PROJECT_ID | `${APIDOG_PROJECT_ID:+set}` | apidog-schema-gen (Push) |

### 3. 프로젝트 파일

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| secret/.env | 파일 존재 확인 | e2e-test |
| CLAUDE.md | 파일 존재 확인 | convention-check |
| .convention-check.json | 파일 존재 확인 | convention-check |
| infra/flyway/migrations/ | 디렉토리 존재 확인 | db-gen-committed |

### 4. 외부 플러그인

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| db-tools | `db-tools:db-gen` 스킬 사용 가능 여부 | db-gen-committed |
| Codex (선택) | `mcp__codex__codex` 호출 가능 여부 | start-workflow (난이도 7+) |

### 5. 빌드 환경

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| Go 설치 | `go version` | e2e-test |
| Go 빌드 | `go build ./cmd/main.go` (dry-run) | e2e-test |
| grpcurl 설치 (선택) | `grpcurl --version` | e2e-test (gRPC) |
| GRPC_PORT (선택) | `secret/.env` 확인 | e2e-test (gRPC) |

### 6. PubSub 환경 (선택)

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| uv 설치 | `uv --version` | Dev PubSub 설치/실행 |
| dev-pubsub-cli 설치 | `which dev-pubsub-cli` (Global) 또는 로컬 clone 존재 확인 | e2e-test (PubSub) |
| PubSub Emulator 상태 | `curl -s http://localhost:8086/api/stats` 응답 여부 | e2e-test (PubSub) |

---

## 실행 흐름

1. 모든 항목을 **병렬로** 점검한다 (독립적인 검사는 동시에).
2. 결과를 수집하여 아래 형식으로 출력한다.

---

## 출력 형식

```markdown
## minmos-harness Doctor Report

### MCP 서버
| 항목 | 상태 | 비고 |
|------|------|------|
| Apidog MCP 연결 | OK / MISSING / FAIL | 실제 MCP 호출 기준 |
| Apidog MCP 응답 | OK / FAIL / SKIP | 연결 MISSING이면 SKIP |
| PostgreSQL MCP 연결 | OK / MISSING / FAIL | `SELECT 1` 기준 |
| PostgreSQL MCP DB 호스트 | OK / BLOCKED / UNKNOWN / SKIP | `inet_server_addr()` 기준 |

### 환경 변수
| 항목 | 상태 | 비고 |
|------|------|------|
| APIDOG_ACCESS_TOKEN | SET / UNSET | Push 기능용 (선택) |
| APIDOG_PROJECT_ID | SET / UNSET | Push 기능용 (선택) |

### 프로젝트 파일
| 항목 | 상태 | 비고 |
|------|------|------|
| secret/.env | OK / MISSING | |
| CLAUDE.md | OK / MISSING | |
| .convention-check.json | OK / DEFAULT | 없으면 기본값 사용 |
| infra/flyway/migrations/ | OK / MISSING | |

### 외부 플러그인
| 항목 | 상태 | 비고 |
|------|------|------|
| db-tools | OK / MISSING | |
| Codex | OK / MISSING | 선택 (난이도 7+ 전용) |

### 빌드 환경
| 항목 | 상태 | 비고 |
|------|------|------|
| Go 설치 | OK / MISSING | go version |
| Go 빌드 | OK / FAIL | dry-run |
| grpcurl 설치 | OK / MISSING | 선택 (gRPC 전용) |
| GRPC_PORT | OK / MISSING / SKIP | 선택 (gRPC 전용) |

### PubSub 환경 (선택)
| 항목 | 상태 | 비고 |
|------|------|------|
| uv 설치 | OK / MISSING | uv --version |
| dev-pubsub-cli | OK (Global) / OK (Local) / MISSING | which dev-pubsub-cli |
| PubSub Emulator | RUNNING / STOPPED / MISSING | localhost:8086 응답 확인 |

---

### 종합
- **필수 항목**: [N]개 중 [M]개 OK
- **선택 항목**: [N]개 중 [M]개 OK
- **상태**: ALL CLEAR / ISSUES FOUND

### 해결 필요 (ISSUES FOUND인 경우)
| # | 항목 | 해결 방법 |
|---|------|----------|
| 1 | [항목] | `$minmo-init-mm` 실행 또는 [구체적 안내] |
```

---

## 필수 vs 선택 분류

| 항목 | 분류 | 이유 |
|------|------|------|
| Apidog MCP | **필수** | 스키마 생성, E2E에서 사용 |
| PostgreSQL MCP | **필수** | E2E 테스트 데이터 관리 |
| secret/.env | **필수** | 서버 실행, JWT 생성 |
| Go 설치/빌드 | **필수** | 빌드 및 테스트 |
| CLAUDE.md | **필수** | 컨벤션 기준 |
| db-tools | **필수** | migration 생성 |
| APIDOG_ACCESS_TOKEN | 선택 | Push 기능 전용 |
| APIDOG_PROJECT_ID | 선택 | Push 기능 전용 |
| Codex | 선택 | 난이도 7+ Plan 리뷰 전용 |
| .convention-check.json | 선택 | 없으면 기본값 사용 |
| grpcurl | 선택 | gRPC E2E 테스트 전용 |
| GRPC_PORT | 선택 | gRPC E2E 테스트 전용 |
| uv | 선택 | Dev PubSub 설치/실행 전제 |
| dev-pubsub-cli | 선택 | PubSub E2E 테스트 전용 |
| PubSub Emulator | 선택 | PubSub E2E 테스�� 시 실행 필요 (STOPPED은 경고만) |
