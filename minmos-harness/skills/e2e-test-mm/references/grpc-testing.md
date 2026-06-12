> 이 문서는 `e2e-test-mm` 스킬에서 `$PROTOCOL`이 `GRPC` 또는 `MIXED`일 때 Step 3(스펙 참조)·4(엣지 케이스)·7(환경 준비)·8(테스트 실행)에서 로드된다. 단독 실행 금지.

# gRPC 테스트 상세

## Step 3: Proto 스펙 참조

- Step 2에서 확인한 `.proto` 파일에서 서비스/메시지 정의를 읽는다.
- **메시지 분석**: 각 필드의 타입·`optional`·`repeated` 여부, `oneof` 그룹, `enum` 정의와 허용 값, nested message 구조.
- **Go 코드 교차 검증**: `grpc_*_repository.go`와 `*_vo.go`의 실제 구현과 proto 정의를 비교한다.
- **RPC 유형 분류**:

| 유형 | 정의 | 테스트 지원 |
|------|------|-----------|
| Unary | `rpc Method(Req) returns (Res)` | 지원 |
| Server Streaming | `rpc Method(Req) returns (stream Res)` | 지원 |
| Client Streaming | `rpc Method(stream Req) returns (Res)` | `SKIP:STREAMING` |
| Bidirectional | `rpc Method(stream Req) returns (stream Res)` | `SKIP:STREAMING` |

## Step 4: gRPC 특화 엣지 케이스

- **Proto3 기본값**: `0`, `""`, `false`가 명시적 전송인지 미전송인지 구분 불가 — `optional` 마커 없는 필드에서 서버가 기본값을 어떻게 처리하는지 확인
- **optional 필드**: proto에서 `optional`로 선언된 필드의 null vs 미전송 처리 차이
- **oneof 필드**: 여러 필드 동시 설정(마지막만 유효), 하나도 설정 안 함
- **repeated 필드**: 빈 배열 `[]`, 대량 요소(100+), 단일 요소
- **unknown fields**: proto에 정의되지 않은 필드 전송 시 무시 여부
- **메시지 크기**: gRPC 기본 4MB 제한 초과 시도 (대량 repeated 필드)
- **deadline/timeout**: 매우 짧은 deadline(1ms) 전송 시 `DEADLINE_EXCEEDED` 반환 여부
- **metadata 변조**: `authorization` metadata 누락, Bearer 없이 토큰만, 잘못된 형식

## Step 7.3: gRPC 환경 준비

1. **grpcurl 검증**: `which grpcurl` — 없으면 설치 안내 후 gRPC 테스트를 중단한다 (`MIXED`이면 REST 테스트만 계속).
2. **gRPC 포트 확인**:
   ```bash
   GRPC_PORT=$(grep -E '^GRPC_PORT=' secret/.env | head -1 | cut -d'=' -f2 | tr -d '[:space:]"'"'"'')
   echo "GRPC_PORT: ${GRPC_PORT:-50051}"
   ```
   `GRPC_PORT`가 없으면 기본값 `50051`을 사용하되, 사용자에게 확인한다.
3. **gRPC 대상 주소 결정**:

   | 환경 | 주소 형식 | 예시 |
   |------|----------|------|
   | 로컬 서버 | `localhost:${GRPC_PORT}` | `localhost:50051` |
   | Docker 내부 (dev gRPC) | `{service}-grpc.{service}.svc.cluster.local:9032` | `mim-grpc.mim.svc.cluster.local:9032` |

   테스트 대상 서비스가 로컬인지 Docker인지에 따라 결정한다. 불확실하면 사용자에게 질문한다.
4. **외부 gRPC 서비스 의존성 점검**: 로컬 서버가 다른 서비스를 gRPC로 호출하는 경우(예: BMS → MIM), 해당 서비스가 접근 가능해야 한다.
   ```bash
   grep -rn 'svc.cluster.local\|grpc.Dial\|grpc.NewClient' internal/ --include='*.go'
   ```
   - 의존 서비스 발견 → Docker 환경 실행 중 + 접근 가능 여부 확인. 접근 불가 시:
     > "이 서비스는 `{service}` gRPC에 의존합니다. Docker 환경 재시작이 필요할 수 있습니다. 담당자에게 문의하거나 Docker 환경을 재시작해주세요."
5. **gRPC Reflection 확인** (서버 실행 후):
   ```bash
   grpcurl -plaintext ${GRPC_TARGET} list 2>&1
   ```
   - 성공 → Reflection 사용 (proto import path 불필요)
   - 실패 → `find-proto.sh`로 proto 경로를 확보하여 `-import-path` / `-proto` 옵션 사용
6. **gRPC JWT 전달**: REST와 동일한 JWT를 metadata로 전달한다: `-H "authorization: Bearer ${TOKEN}"`
7. **서버 빌드/실행**: Step 7.2의 서버와 동일 바이너리를 공유한다 (REST + gRPC 동일 프로세스인 경우).
   별도 gRPC 서버가 필요한 경우:
   ```bash
   go build -o /tmp/grpc-test-server ./cmd/grpc/main.go
   /tmp/grpc-test-server &
   ```

## Step 8: gRPC 테스트 실행

**도구**: `grpcurl` (curl 대신 사용)

**Reflection 사용 가능 시:**
```bash
# Unary RPC
grpcurl -plaintext \
  -d '{"field":"value"}' \
  -H "authorization: Bearer ${TOKEN}" \
  ${GRPC_TARGET} \
  {service}.v1.{ServiceName}/{MethodName}

# Server Streaming RPC — 동일 형식 (스트림 수신 완료까지 대기)
```

**Reflection 미사용 시 (proto import 필요):**
```bash
grpcurl -plaintext \
  -import-path {proto_dir} \
  -proto {service}/v1/{service}.proto \
  -d '{"field":"value"}' \
  -H "authorization: Bearer ${TOKEN}" \
  ${GRPC_TARGET} \
  {service}.v1.{ServiceName}/{MethodName}
```

### gRPC 테스트 케이스 구성

**A. Happy Path**
- Unary RPC 호출 → gRPC OK (0) 및 response 구조 확인
- 반환된 데이터를 조회 RPC(또는 REST GET)로 반영 확인
- Server Streaming RPC → 스트림 수신 완료, 응답 구조 확인

**B. Validation (필수 필드/타입)**
- 필수 필드 누락 / 잘못된 enum 값 / 빈 repeated (required) / 잘못된 타입 → INVALID_ARGUMENT (3)

**C. gRPC 특화 엣지 케이스**
- Proto3 기본값 전송 (0, "", false) → 서버 처리 확인
- optional 필드 null vs 미전송 → 서버 구분 확인
- oneof 다중 설정 → 마지막만 유효 확인
- 대량 repeated 요소 → 응답 확인 또는 RESOURCE_EXHAUSTED
- deadline 1ms → DEADLINE_EXCEEDED (4): `grpcurl -max-time 0.001 ...`
- metadata 없음 / Bearer 없이 토큰만 → UNAUTHENTICATED (16)

**D. 인증/권한**
- metadata에 authorization 없이 요청 → UNAUTHENTICATED (16)
- USER 역할 토큰으로 ADMIN 전용 RPC 호출 → PERMISSION_DENIED (7)

**E. gRPC Status Code 정합성** (기준표: `references/status-code-validation.md`)
- 존재하지 않는 ID → NOT_FOUND (5) 확인 (INTERNAL이면 `[GRPC_STATUS_MISMATCH]`)
- 삭제된 리소스 참조 / domain.ErrNotFound 경로 → NOT_FOUND (5) 확인
- Client Streaming / Bidirectional RPC → `SKIP:STREAMING` 표기, 실행 생략

### 각 요청마다 기록 (gRPC)

- RPC 경로 (`{service}.v1.{ServiceName}/{MethodName}`)
- Request JSON
- gRPC status code + message
- Response JSON (성공 시)
- 기대값과 일치 여부
