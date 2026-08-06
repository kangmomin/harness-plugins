<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:e2e-test`

베이스는 HTTP(curl) 전용이다. Post-Math 백엔드는 REST + gRPC + PubSub 를 함께 쓰고, 로컬 DB 시드/정리가 필요하므로 오버레이가 이를 보강한다.

## Pre-flight 추가

| 점검 항목 | 확인 방법 | 누락 시 |
|----------|----------|--------|
| `secret/.env` | 파일 존재 | `SKIPPED:ENV_MISSING` |
| PostgreSQL MCP 연결 | `SELECT 1` 실행 성공 | `SKIPPED:POSTGRES_MCP_UNAVAILABLE` |
| DB 호스트가 로컬 | 연결 문자열 호스트 검사 | `SKIPPED:REMOTE_DB_BLOCKED` (화이트리스트 승인 없을 때) |

베이스의 profile 기반 SKIP 조건(`NO_PROFILE`·`DISABLED`·`NO_SERVER_URL`·`NO_SERVER`·`NO_AUTH`·`NO_CHANGED_API`)은 그대로 유지한다.

## Phase 삽입

| 앵커 | 위치 | 삽입 단계 | 절차 |
|------|------|----------|------|
| `Step 1 (대상 API 수집)` | 직후 | **프로토콜 분류** — 변경 범위를 `REST` / `GRPC` / `MIXED` 로 분류 | `references/e2e-test-postmath.md` 의 "Step 2.1: 프로토콜 분류" |
| `Step 2 (시나리오 구성)` | 직후 | **Status Code 의미적 정합성 검증** | `references/status-code-validation.md` |
| `Step 2 (시나리오 구성)` | 직후 | **Edge Case Analyzer 호출** — `be-harness:edge-case-analyzer` 에이전트로 엣지 케이스 보강 | `references/e2e-test-postmath.md` 의 "Step 6" |
| `Step 4 (서버 기동)` | 직후 | **gRPC 환경 준비** (분류가 `GRPC`/`MIXED`일 때만) | `references/grpc-testing.md` |

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| `Step 5 (요청 실행)` | 분류가 `GRPC`/`MIXED` 면 gRPC 호출 절차를 함께 사용한다 (`references/grpc-testing.md`). REST 부분은 베이스 그대로. |
| `Step 6 (서버 종료)` | 서버 종료에 더해 **테스트 데이터 정리**를 수행한다 (`references/db-safety.md` 의 격리·정리 규칙) |
| `Step 7 (리포트)` | 리포트 템플릿을 `references/e2e-report-templates.md` 로 치환. 판정 기준(`PASS`/`WARN`/`FAIL`)과 `UNCOVERED:{사유}` 표기는 베이스와 동일하게 유지한다 |

## 추가 규칙

- **로컬 DB 전용 실행 (절대 원칙)**: 원격 DB 호스트 대상 실행 금지. 상세·화이트리스트 절차는 `references/db-safety.md`.
- **테스트 데이터 격리**: 생성한 데이터는 실행 종료 시 반드시 정리한다. 정리 실패는 리포트에 명시한다.
- gRPC 응답 status는 HTTP status가 아니라 **gRPC code**로 표기한다.

> 전체 Post-Math E2E 절차의 원문은 `references/e2e-test-postmath.md` 다. 위 앵커 표와 원문이 충돌하면 **앵커 표가 우선**한다 (원문은 베이스 통합 전 작성된 독립 절차라, 베이스와 겹치는 부분이 있다).

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/e2e-test-postmath.md` | 오버레이 적용 시 항상 |
| `references/db-safety.md` | Pre-flight, Step 6+ (정리) |
| `references/grpc-testing.md` | 분류가 `GRPC`/`MIXED` 일 때 |
| `references/status-code-validation.md` | Step 2+ (정합성 검증) |
| `references/e2e-report-templates.md` | Step 7 (리포트) |
