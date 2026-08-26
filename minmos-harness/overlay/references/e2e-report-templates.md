> 이 문서는 `e2e-test` 스킬의 Step 9(결과 보고)에서 로드된다. 단독 실행 금지.
> 보고서의 섹션 머리글은 후속 스킬(e2e-test-loop, e2e-apidog-schema-gen)이 파싱하므로 변경하지 않는다.

# 결과 보고 양식

## REST 결과 보고

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
| ID | 테스트 | HTTP | 기대 | 결과 | 비고 |
|----|--------|------|------|------|------|
| EC-01 | 설명 (Spec 승계) | xxx | xxx | 성공/실패 | 상세 |
| SELF-01 | 설명 (코드/Apidog 자체 도출) | xxx | xxx | 성공/실패 | 상세 |

#### 인증/권한
| # | 테스트 | HTTP | 결과 | 비고 |
|---|--------|------|------|------|
| 1 | 설명 | 4xx | 성공/실패 | 상세 |

#### Status Code 정합성
| # | 테스트 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 에러코드 | 판정 |
|---|----------------|----------|------------|------------|---------|------|
| 1 | 존재하지 않는 FK ID 참조 | 리소스 없음 | 404 | 404/500 | ERR/WARN | OK / [STATUS_MISMATCH] |

### Spec 커버리지
| Spec 엣지 케이스 | 대응 테스트 | 상태 |
|-----------------|------------|------|
| EC-01 | EC-01 | 실행됨 |
| EC-02 | — | `UNCOVERED:외부 결제사 타임아웃 재현 불가` |

- Spec 엣지 케이스 [N]건 중 [M]건 실행, [K]건 미커버 (Spec에 ID가 없으면 `대조 기준 없음`)
- 자체 도출 케이스: [N]건 (`SELF-*`) — 실효 수준 smoke면 `생략(smoke)`
- 판정: [PASS / WARN / FAIL]
- 실행 수준: smoke | full | full(smoke 미적용: {사유})
- 생략 시나리오: `SMOKE_OMITTED` {BASE-nn 목록} (--smoke) / 없음

| 판정 | 조건 |
|------|------|
| `PASS` | 테스트 실패 0건 **AND** 미커버 0건 |
| `WARN` | 테스트 실패 0건 **AND** 미커버 1건 이상 (사유가 명시된 것만) |
| `FAIL` | 테스트 실패 1건 이상 |

미커버는 구현 결함이 아니라 **검증 공백**이므로 수정 루프의 트리거가 아니다. 사유와 함께 남겨 호출자가 판단하게 한다.

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

- 엣지 케이스 분석 에이전트(edge-case-analyzer)가 추가한 케이스는 Edge Cases 테이블에 `[EA]` 태그를 붙인다.

## gRPC 결과 보고 (`$PROTOCOL`이 `GRPC` 또는 `MIXED`)

`MIXED`이면 REST와 gRPC 결과를 **섹션 분리**하여 보고한다. `- 실행 수준:` 줄은 리포트에 **정확히 1회** — `MIXED`는 REST 섹션의 것을 쓰고, `GRPC` 단독이면 아래 템플릿 끝의 줄을 쓴다.

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
| 1 | {ServiceName}/{MethodName} | Client Streaming / Bidirectional | SKIP:STREAMING grpcurl 미지원 |

- 실행 수준: smoke | full | full(smoke 미적용: {사유})   ← `$PROTOCOL`이 `GRPC` 단독일 때만

### gRPC Status Code 오분류 ([GRPC_STATUS_MISMATCH])
| # | RPC | 시나리오 | 에러 원인 | 기대 Status | 실제 Status | 위치 (파일:라인) |
|---|-----|---------|----------|------------|------------|----------------|
| 1 | [{ServiceName}/{Method}] | [시나리오] | [클라이언트/서버] | [NOT_FOUND] | [INTERNAL] | [파일:라인] |

- **수정 방향**: [gRPC handler에서 도메인 에러를 적절한 gRPC status code로 매핑 등]
```
