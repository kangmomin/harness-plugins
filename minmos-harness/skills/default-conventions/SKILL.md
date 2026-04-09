---
name: default-conventions
description: "BMad 프로젝트 개발 및 리뷰 가이드라인 (Local Convention)"
user-invocable: true
---

# BMad 프로젝트 개발 및 리뷰 가이드라인 (Local Convention)

당신은 BMad 프로젝트의 코드를 수정하거나 리뷰할 때 반드시 아래의 규칙을 준수해야 하는 전문 개발 파트너입니다.

## 1. 에러 처리 아키텍처 (3-Layer Flow)

### 1.1 Repository -> Usecase
- GORM 에러(예: `gorm.ErrRecordNotFound`)를 가공하지 않고 **있는 그대로(Raw Error)** 반환한다.
- 비즈니스 로직이나 한국어 메시지를 섞지 않는다.

### 1.2 Usecase -> Handler (에러 래핑)
- **반환 형식:** `(errCode string, result VO, err error)`
- **에러 코드:** `/utils/errcode/errcode.go`의 `errorMap`에 정의된 코드를 사용한다.
- **메시지:** 반드시 **한국어**로 작성하며, `%w`를 사용하여 원본 에러를 래핑한다.
- *예시:* `return errcode.WARN_PMS_007, nil, fmt.Errorf("실물책을 찾을 수 없습니다: %w", err)`

### 1.3 Handler -> Client
- `cloudKit.RespondWithError(c, errcode.GetResponse(errCode), err)`를 호출한다.
- 최종 응답의 `detail` 필드에 원본 에러가 노출되는지 확인한다.

## 2. VO (Value Object) 및 Validation
- **순서:** Handler(필요 시) -> VO(필수) -> Usecase 순서로 진행한다.
- **검증 일원화:** VO의 `New...()` 생성자 함수에서만 내부 Validation 로직을 수행한다.
- **생성자 패턴:** 검증 실패 시 `nil`을 반환한다.
- **중복 검증 금지:** VO로 변환된 데이터는 이미 검증된 것으로 간주하며, 하위 레이어에서 동일한 필드에 대해 중복 Validation을 수행하지 않는다.

## 3. GORM 활용 및 트랜잭션 관리

### 3.1 GORM 사용 원칙
- 불가피한 경우가 아니면 네이티브 쿼리를 지양하고 GORM 체인 메서드(`Select`, `Joins`, `Where` 등)를 사용한다.

### 3.2 트랜잭션 관리 (Unit of Work)
- 트랜잭션 처리 시 각 에러 발생 시점에서 명시적으로 `Rollback()`을 호출한다.
- `committed` 플래그와 `defer` 패턴은 사용하지 않는다.
- **패턴:**
  ```go
  // 1. Begin transaction
  if err = uow.Begin(ctx); err != nil {
      return errcode.ERR_SYSTEM_FATAL, err
  }

  // 2. 비즈니스 로직 수행 (각 에러 시점에서 명시적 Rollback)
  result, err := repo.SomeOperation(ctx, data)
  if err != nil {
      _ = uow.Rollback(ctx)
      return errcode.ERR_SYSTEM_FATAL, nil, fmt.Errorf("작업 실패: %w", err)
  }

  // 3. Commit (실패 시 Rollback)
  if err = uow.Commit(ctx); err != nil {
      _ = uow.Rollback(ctx)
      return errcode.ERR_SYSTEM_FATAL, err
  }

  return errcode.ERR_NONE, result, nil
  ```
### 4. 커밋 및 PR 운영 지침
- **커밋 메시지 형식**: [Prefix]: 간략한 설명
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
