> 이 문서는 `e2e-test` 스킬의 Step 5(Status Code 의미적 정합성 검증)에서 로드된다. 단독 실행 금지.

# Status Code 의미적 정합성 검증

모든 에러 응답에 대해 **상태 코드가 에러의 원인(클라이언트/서버)과 일치하는지** 검증한다.
단순히 "에러가 반환되는가"가 아니라 "올바른 종류의 에러가 반환되는가"를 확인한다.

## REST: HTTP Status Code (`$PROTOCOL`이 `REST` 또는 `MIXED`)

### 분류 기준

| 원인 | 올바른 Status | 예시 |
|------|--------------|------|
| 클라이언트 입력 오류 | 400 Bad Request | 필수 필드 누락, 유효하지 않은 값, 타입 불일치 |
| 인증 없음 | 401 Unauthorized | 토큰 없음, 만료된 토큰 |
| 권한 없음 | 403 Forbidden | 일반 유저가 ADMIN API 호출 |
| 리소스 없음 | 404 Not Found | 존재하지 않는 ID로 조회/수정/삭제, 존재하지 않는 FK 참조 ID |
| 충돌 | 409 Conflict | 중복 생성, 이미 처리된 요청 |
| 서버 내부 오류 | 500 Internal Server Error | DB 연결 실패, 예상치 못한 런타임 에러 |

### 검증 방법

1. **에러코드 매핑 분석**: `errcode.go`의 `errorMap`에서 각 에러코드의 `StatusCode`를 확인한다.
2. **Usecase 에러 흐름 추적**: usecase의 에러 반환 경로를 추적하여, 클라이언트 입력 오류가 `ERR_*` (5XX)로 반환되는 경우를 찾는다.
3. **주요 점검 포인트**:
   - 존재하지 않는 FK 참조 ID 전달 → 404이어야 하는데 500 반환하지 않는가?
   - `RowsAffected` 불일치(일부 ID 미존재) → 404이어야 하는데 500 반환하지 않는가?
   - `domain.ErrNotFound` → 반드시 `WARN_*` (4XX)로 매핑되는가?
   - Repository에서 올라온 에러를 usecase가 원인별로 분기하는가, 일괄 5XX로 처리하는가?

### E2E 실행 시 검증

- 각 에러 케이스에 대해 **기대 status code**와 **실제 status code**를 비교한다.
- 4XX가 기대되는데 5XX가 반환되면 **`[STATUS_MISMATCH]`**로 표기하고, 발견된 이슈에 별도 보고한다.

## gRPC: gRPC Status Code (`$PROTOCOL`이 `GRPC` 또는 `MIXED`)

### 분류 기준

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

### 검증 방법

1. Go 코드에서 `status.Errorf(codes.XXX, ...)` 또는 `status.Error(codes.XXX, ...)` 패턴을 Grep하여 각 에러 경로의 gRPC 코드를 추적한다.
2. 클라이언트 입력 오류가 `codes.Internal`로 반환되는 경우를 찾는다.
3. `domain.ErrNotFound` → 반드시 `codes.NotFound`로 매핑되는지 확인한다.

### E2E 실행 시 검증

- grpcurl 응답에서 gRPC status code를 파싱한다 (에러 시 `ERROR: Code: XXX` 형태로 출력됨).
- 기대 status와 실제 status를 비교한다. 불일치 시 **`[GRPC_STATUS_MISMATCH]`** 표기.
