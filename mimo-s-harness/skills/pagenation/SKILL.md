---
name: pagenation
description: "커서 기반 페이지네이션 구현 컨벤션"
user-invocable: true
---

# 커서 기반 페이지네이션 구현 컨벤션

> 본 문서는 프로젝트 내에서 GORM 및 `cloudKit` 패키지를 활용하여 일관된 **Cursor-based Pagination**을 구현하기 위한 표준 가이드를 정의합니다.

---

## 1. API 공통 매개변수 (Request Parameters)

|**매개변수**|**타입**|**필수 여부**|**설명**|
|---|---|---|---|
|`order`|`string`|선택|정렬 기준 (예: `createdAt:desc,id:asc`). 생략 시 기본값 적용.|
|`cursor`|`string`|선택|이전 응답의 `nextCursor`. 첫 페이지 요청 시 빈 값.|
|`limit`|`int`|**필수**|한 페이지에 노출할 데이터 개수.|

---

## 2. 구현 단계별 가이드라인

### 2.1 커서 디코딩 및 검증 (Decoding & Validation)

- **커서 존재 시**: `cloudKit.CursorDecode(cursor)`를 통해 `OrderSpec`을 추출합니다.

- **정렬 일관성 체크**: 요청된 `order` 파라미터가 있다면, 커서 내부에 저장된 정렬 정보와 일치하는지 `cloudKit.EqualOrderSpecs`로 반드시 검증합니다.

    - _주의: 정렬 조건이 바뀌면 기존 커서는 무효화됩니다._

- **커서 미존재 시**: `order` 파라미터를 파싱하여 새로운 정렬 기준을 생성합니다.


### 2.2 쿼리 구성 (Query Building)

- **정렬 적용**: 모든 필드명은 `snake_case`로 변환하여 **SQL Injection을 방지**하고 DB 컨벤션을 따릅니다.

- **고유성 보장 (Tie-breaking)**: 정렬 조건에 `id`가 포함되지 않은 경우, 결과의 순서가 매번 동일하도록 반드시 마지막에 `id desc` (혹은 `asc`)를 추가합니다.

- **필터링 로직**: 다중 정렬 시, 이전 정렬 컬럼들은 `=` 조건으로, 현재 컬럼은 방향(`>` 또는 `<`) 조건을 적용하여 `OR`로 결합합니다.


### 2.3 다음 커서 생성 (Next Cursor Generation)

- 조회된 결과 리스트의 **마지막 요소**를 기준으로 `OrderSpec` 값을 추출합니다.

- `cloudKit.CursorEncode`를 사용하여 다음 요청에 사용할 문자열을 생성합니다.

- 더 이상 결과가 없거나 마지막 페이지인 경우 빈 문자열(`""`)을 반환합니다.


---

## 3. 표준 코드 템플릿 (Go Reference)

```go
func (r *repository) GetList(ctx context.Context, order, cursor string, limit int) ([]*VO, string, error) {
    var entities []*Entity
    query := r.db.WithContext(ctx).Table("table_name")

    // 1. 정렬 스펙 결정 (커서 우선)
    var orderSpecs []cloudKit.OrderSpec
    if cursor != "" {
        specs, err := cloudKit.CursorDecode(cursor)
        if err != nil {
            return nil, "", fmt.Errorf("invalid cursor: %w", err)
        }
        orderSpecs = specs
    } else {
        orderSpecs = cloudKit.ParseOrderParam(order)
    }

    // 2. 쿼리 빌딩 (Order & Where)
    for i, spec := range orderSpecs {
        col := toSnakeCase(spec.Column) // 유틸리티 함수
        query = query.Order(fmt.Sprintf("%s %s", col, spec.Direction))

        if cursor != "" {
            if i == 0 {
                query = query.Where(fmt.Sprintf("%s %s ?", col, cloudKit.Operator(spec.Direction)), spec.Value)
            } else {
                // 다중 컬럼 필터링 로직 구현 (OR 조건 결합)
                query = query.Or(buildComplexCondition(orderSpecs, i))
            }
        }
    }

    // 3. ID Tie-breaking (결과 일관성 보장)
    if !hasIdSpec(orderSpecs) {
        query = query.Order("id desc")
    }

    // 4. 실행 및 결과 처리
    if err := query.Limit(limit).Find(&entities).Error; err != nil {
        return nil, "", err
    }

    // 5. 다음 커서 인코딩
    nextCursor := ""
    if len(entities) > 0 {
        last := entities[len(entities)-1]
        nextCursor = cloudKit.CursorEncode(extractNextSpecs(orderSpecs, last))
    }

    return vos, nextCursor, nil
}
```

---

## 4. 주의 사항

> **성능과 정확도를 위한 체크리스트**
>
> - **시간대(Timezone)**: `created_at` 등 시간 필드 정렬 시, 애플리케이션과 DB의 시간대 설정(UTC 등)이 일치하는지 확인하십시오.
>
> - **인덱스 활용**: 커서 기반 페이지네이션의 성능을 위해 정렬에 사용되는 컬럼들(예: `created_at`, `id`)은 반드시 **복합 인덱스**로 구성되어야 합니다.
>
> - **컬럼 매핑**: API의 `CamelCase` 필드명이 DB의 `snake_case` 컬럼명과 정확히 매핑되는지 검증 로직을 포함하십시오.
