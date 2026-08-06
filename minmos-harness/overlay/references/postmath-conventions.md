> 이 문서는 `minmos-harness` 오버레이의 `overlay/default-conventions.md`·`overlay/convention-check.md` 에서 로드된다. 단독 실행 금지.
> `/be-harness:default-conventions` 의 범용 가이드라인에 더해 적용되는 **Post-Math 고유 컨벤션**이다.

# Post-Math 백엔드 프로젝트 개발 및 리뷰 가이드라인 (Local Convention)

당신은 Post-Math 백엔드 프로젝트의 코드를 수정하거나 리뷰할 때 반드시 아래의 규칙을 준수해야 하는 전문 개발 파트너입니다.

## 0. 정본(SSOT) 우선 원칙

- Post-Math Go 백엔드 컨벤션의 정본은 **`go-conventions:conventions-guide`** (레이어링·Entity↔VO·repository 계약·PostgreSQL+Gorm·UoW·커서 페이지네이션)이다.
- 본 문서는 정본을 보완하는 로컬 컨벤션이며, **정본과 충돌하면 정본이 우선**한다.
- 단 하나의 예외: **§3.2 트랜잭션 Rollback 패턴**은 문서화된 로컬 예외로 본 문서를 따른다 (해당 절의 `[Local Exception]` 참조).

## 1. 에러 처리 아키텍처 (3-Layer Flow)

### 1.1 Repository -> Usecase
- **예상 가능한 실패는 도메인 센티널 에러로 변환해 반환한다** (정본 `postgres-gorm-conventions`·`entity-repository-contract` 준수):
  - 대상 없음(`gorm.ErrRecordNotFound`, soft-delete `RowsAffected == 0`) → `Err{Module}NotFound`
  - 부분 유니크 충돌(`23505`) → 인덱스명 매칭 후 해당 도메인 에러
- 그 외 예기치 못한 인프라 에러는 가공 없이 반환한다.
- 비즈니스 로직이나 한국어 메시지를 섞지 않는다.

### 1.2 Usecase -> Handler (에러 전파)
- **반환 형식:** `(result VO, err error)` — errCode 튜플 반환은 사용하지 않는다.
- repository 의 도메인 센티널 에러는 `%w` 래핑으로 전파해 `errors.Is` 판별 가능성을 유지한다.
- 컨텍스트 메시지를 붙일 경우 **한국어**로 작성한다.
- *예시:* `return nil, fmt.Errorf("실물책 조회 실패: %w", err)`

### 1.3 Handler -> Client
- `errors.Is` 로 도메인 센티널 에러를 판별해 errCode(`/utils/errcode/errcode.go` `errorMap`)로 매핑한다.
- `cloudKit.RespondWithError(c, errcode.GetResponse(errCode), err)`를 호출한다.
- 최종 응답의 `detail` 필드에 원본 에러가 노출되는지 확인한다.

## 2. VO (Value Object) 및 Validation
- **순서:** Handler(필요 시) -> VO(필수) -> Usecase 순서로 진행한다.
- **검증 일원화:** VO의 `New...()` 생성자 함수에서만 내부 Validation 로직을 수행한다 (정본 `entity-vo-boundary` rule 3).
- **생성자 패턴:** `(*XxxVO, error)` 를 반환하며, 검증 실패 시 `(nil, error)` 를 반환한다. 실패 사유가 소실되는 bare `nil` 단독 반환은 금지한다.
- **중복 검증 금지:** VO로 변환된 데이터는 이미 검증된 것으로 간주하며, 하위 레이어에서 동일한 필드에 대해 중복 Validation을 수행하지 않는다.

## 3. GORM 활용 및 트랜잭션 관리

### 3.1 GORM 사용 원칙
- 불가피한 경우가 아니면 네이티브 쿼리를 지양하고 GORM 체인 메서드(`Select`, `Joins`, `Where` 등)를 사용한다.

### 3.2 트랜잭션 관리 (Unit of Work)

> **[Local Exception]** 정본 `uow-transaction-pattern` rule 1 은 `Begin` 직후 `defer uow.Rollback(ctx)` 를 규정하나, 본 프로젝트군은 **각 에러 시점의 명시적 `Rollback()` 호출**을 유지한다. (결정자: 사용자, 2026-07-23 — go-conventions 정렬 시 유일하게 존치한 항목. 후속 리뷰에서 defer 패턴 미사용이 재지적되면 본 항목을 인용해 종결한다.)

- 트랜잭션 처리 시 각 에러 발생 시점에서 명시적으로 `Rollback()`을 호출한다.
- `committed` 플래그와 `defer` 패턴은 사용하지 않는다.
- **패턴:**
  ```go
  // 1. Begin transaction
  if err = uow.Begin(ctx); err != nil {
      return nil, err
  }

  // 2. 비즈니스 로직 수행 (각 에러 시점에서 명시적 Rollback)
  result, err := repo.SomeOperation(ctx, data)
  if err != nil {
      _ = uow.Rollback(ctx)
      return nil, fmt.Errorf("작업 실패: %w", err)
  }

  // 3. Commit (실패 시 Rollback)
  if err = uow.Commit(ctx); err != nil {
      _ = uow.Rollback(ctx)
      return nil, err
  }

  return result, nil
  ```
### 4. 커밋 및 PR 운영 지침
- **커밋 메시지 형식**: [Prefix]: 간략한 설명
- **작성 언어**: Prefix는 영문으로 유지하고, 설명/본문은 기본적으로 한국어로 작성
- **Prefix**: Add, Fix, Del, Refactor, Doc, Test, Chore, WIP
- **PR 제목**: [commit-prefix]: 작업내용

### 5. 작업 프로세스 (Task Workflow)
- **분석**: 작업 시작 전 현재 코드와 컨벤션의 일치 여부를 먼저 분석한다.
- **구현**: 위 규칙에 따라 코드를 작성한다.
- **최종 코드리뷰**: 작업 종료 전 에러 래핑 및 중복 validation 여부를 스스로 리뷰한다.
- **결과 보고**: 모든 응답의 마지막에 아래 양식으로 보고를 수행한다.

## 최종 작업 보고 (Final Report)
1. **수정 사항 요약**
    - (컨벤션 준수 여부 및 주요 로직 변경점 정리)
2. **예상되는 사이드 이펙트**
    - (인접 모듈 영향도 및 데이터 무결성 리스크 분석)
3. **영향 받는 API 및 데이터 변경점**
    - 대상 API: 메서드 /경로
    - 요청/응답 변경: (필드 추가/삭제 및 에러 코드 변화)
4. **비즈니스 영향 예시**
    - (실제 사용자 시나리오 관점에서의 변화 설명)
