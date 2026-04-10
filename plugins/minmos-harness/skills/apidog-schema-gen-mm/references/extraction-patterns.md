# Ref Extraction Patterns & Edge Cases

## 핵심 원칙

**재사용(2곳 이상)되는 객체만 `$ref`로 분리한다.** 나머지는 필드 수, 중첩 깊이와 관계없이 모두 flat 인라인으로 출력한다. 유저가 스키마를 한 번에 copy 할 수 있어야 한다.

---

## Pattern 1: 중첩 객체 -- 인라인 유지 (기본)

1곳에서만 사용되는 중첩 객체는 필드 수와 관계없이 인라인으로 유지한다.

**Input (OAS):**
```json
{
  "type": "object",
  "properties": {
    "reviewId": { "type": "integer" },
    "memberInfo": {
      "type": "object",
      "properties": {
        "id": { "type": "integer" },
        "name": { "type": "string" },
        "nickname": { "type": "string" },
        "profileImagePath": { "type": "string" },
        "role": { "type": "string" }
      },
      "required": ["id", "name", "nickname"]
    }
  }
}
```

**Output:** 인라인 유지 (1곳에서만 사용 -- 필드 5개여도 분리 안 함)
```json
{
  "type": "object",
  "properties": {
    "reviewId": { "type": "integer" },
    "memberInfo": {
      "type": "object",
      "properties": {
        "id": { "type": "integer" },
        "name": { "type": "string" },
        "nickname": { "type": "string" },
        "profileImagePath": { "type": "string" },
        "role": { "type": "string" }
      },
      "required": ["id", "name", "nickname"]
    }
  }
}
```

---

## Pattern 2: 재사용 객체 -- Ref 분리

동일 구조가 2곳 이상에서 반복되면 `$ref`로 분리한다.

**예시:** `priceInfo`가 physical_book, academic_db, book_db 등 여러 곳에서 동일 구조로 사용

```json
{
  "priceInfo": { "$ref": "#/components/schemas/CartPriceInfo" }
}
```

Ref schema - `CartPriceInfo`:
```json
{
  "type": "object",
  "properties": {
    "regularPrice": { "type": "integer" },
    "currentPrice": { "type": "integer" },
    "discountRate": { "type": "number" },
    "discountEndAt": { "type": "string" }
  }
}
```

> 필드 이름이 같고 구조가 동일하면 같은 ref로 통합한다.
> 필드 이름이 다르지만 구조가 동일하면 유저에게 통합 여부를 확인한다.

---

## Pattern 3: Deeply Nested Objects -- flat 인라인

중첩 깊이가 깊더라도 재사용되지 않으면 전체를 flat 하게 펼친다.

**Input:**
```json
{
  "deliveryInfo": {
    "type": "object",
    "properties": {
      "normal": {
        "type": "object",
        "properties": {
          "carrier": { "type": "string" },
          "deliveryFee": { "type": "integer" }
        }
      },
      "returnExchange": {
        "type": "object",
        "properties": {
          "returnDeliveryFee": { "type": "integer" },
          "exchangeDeliveryFee": { "type": "integer" }
        }
      }
    }
  }
}
```

**Output:** 재사용 없음 -> 전체 인라인 유지 (위 Input과 동일하게 출력)

---

## Pattern 4: Nullable Fields

OAS에서 `"type": "null"`인 필드는 nullable로 변환한다.

**Input:**
```json
{
  "previewPdfPath": { "type": "null" },
  "difficulty": { "type": "null" }
}
```

**Output:**
```json
{
  "previewPdfPath": { "type": ["string", "null"] },
  "difficulty": { "type": ["object", "null"] }
}
```

> OAS 원본에 `type: "null"`만 있는 경우, example 값이나 description에서 실제 타입을 유추한다. 유추 불가 시 `"type": ["string", "null"]`을 기본값으로 사용하되 유저에게 확인한다.

---

## Pattern 5: Pagination Object (인라인 유지)

`pagination` 객체는 프로젝트 공통 wrapper이므로 인라인으로 유지한다.

```json
{
  "pagination": {
    "type": "object",
    "properties": {
      "limit": { "type": "integer" },
      "cursor": { "type": "string" },
      "totalItems": { "type": "integer" }
    },
    "required": ["limit", "cursor", "totalItems"]
  }
}
```

---

## Pattern 6: Request Body -- flat 인라인 (기본)

Request body의 중첩 객체도 재사용되지 않으면 인라인으로 유지한다.

**Input (실물책 등록 요청):**
```json
{
  "physicalBookInfo": { "type": "object", "properties": { "..." : "..." } },
  "defaultInfo": { "type": "object", "properties": { "..." : "..." } },
  "priceInfo": { "type": "object", "properties": { "..." : "..." } },
  "deliveryInfo": { "type": "object", "properties": { "..." : "..." } }
}
```

**Output:** 각 객체가 1곳에서만 사용 -> 전체 flat 인라인 유지. `priceInfo`가 다른 스키마에서도 동일 구조로 재사용되는 경우에만 해당 객체를 `$ref`로 분리.

Request에서 재사용 ref의 네이밍은 HTTP method를 반영한다:
- POST -> `Create{Domain}{Object}`
- PATCH -> `Update{Domain}{Object}`

---

## Pattern 7: Polymorphic 필드 -- Apidog schema composition

`interface{}` 또는 `type` discriminator 기반으로 여러 구조가 들어갈 수 있는 필드 처리.

### 식별 기준

- Go 코드에서 필드 타입이 `interface{}`
- 또는 `type` 필드 값에 따라 다른 struct가 할당되는 패턴

### Apidog composition 타입 선택

| Apidog 옵션 | OpenAPI | 의미 | 사용 시점 |
|------------|---------|------|----------|
| **XOR** | `oneOf` | 정확히 하나만 만족 | `type` discriminator 기반 다형성 (**기본 선택**) |
| OR | `anyOf` | 하나 이상 만족 | 여러 형태가 동시 가능한 경우 (드묾) |
| AND | `allOf` | 모두 만족 | 상속/확장 패턴 (Base + Extension) |

> 대부분의 Go `interface{}` 다형성은 discriminator 기반이므로 **XOR (`oneOf`)**를 기본으로 사용한다.

### Apidog 내부 JSON 형식

Apidog에서 실제 저장되는 형식:
```json
{
  "extraInfo": {
    "anyOf": [
      {
        "type": "object",
        "properties": {},
        "x-apidog-orders": []
      },
      {
        "type": "object",
        "properties": {},
        "x-apidog-orders": []
      }
    ]
  }
}
```

- `anyOf` 키는 Apidog UI에서 AND/OR/XOR 선택에 따라 실제로는 `allOf`/`anyOf`/`oneOf` 의미로 동작
- 각 인덱스(0, 1, 2...)에 해당 variant의 full schema를 넣음
- `x-apidog-orders`에 필드 순서를 지정

### 출력 방식

1. Main Schema에서 composition placeholder로 variant 목록 표기:
```json
{
  "extraInfo": {
    "oneOf": [
      { "title": "physical_book" },
      { "title": "academic_db" }
    ]
  }
}
```

2. 각 variant를 인덱스 번호로 별도 섹션에 출력. 각 섹션은 Apidog `oneOf[N]`에 직접 붙여넣을 수 있는 완전한 JSON schema:
```
## extraInfo[0] -- physical_book
(Apidog oneOf[0]에 붙여넣을 full JSON schema)

## extraInfo[1] -- academic_db
(Apidog oneOf[1]에 붙여넣을 full JSON schema)
```

3. variant 내부 중첩 객체도 재사용 기준 동일 적용 -- 재사용이면 `$ref`, 아니면 인라인.

### 장점

- 공통 필드(productItemId, title 등)가 반복되지 않음
- 필요한 variant만 골라 copy -> Apidog composition 인덱스에 바로 붙여넣기 가능
- XOR(`oneOf`)로 타입 관계가 명시적

---

## Edge Cases

### Empty Items
```json
{ "type": "array", "items": {} }
```
-> 그대로 유지. Any type array로 취급.

### Mixed Required
OAS 원본에 `required` 배열이 있으면 그대로 유지. 없으면 `required` 필드를 생략한다 (추가하지 않음).

### Array of Objects
배열 아이템이 객체인 경우에도 재사용 기준을 동일하게 적용한다. 1곳에서만 사용되면 인라인, 2곳 이상이면 ref.

### Query Parameters (GET)
GET 엔드포인트의 query parameters는 ref 분리 대상이 아니다. **CSV 형태**로 정리한다.

#### CSV 형식 규칙

- **컬럼 헤더 없이** 데이터만 출력한다.
- 컬럼 순서: `이름, 유형, 예시, 설명`
- 중간 필드가 비어도 쉼표(`,`)는 반드시 유지한다.
- 값에 쉼표가 포함되면 해당 값을 큰따옴표로 감싼다.

```csv
cursor,string,W3siY29sdW1uIjoi....,페이지네이션 커서
limit,string,,조회 건수
order,string,created_at:desc,정렬 기준
keyword,string,그립,검색 키워드
```

#### Query Parameter JSON Schema 옵션

CSV 출력 후, 유저에게 각 파라미터별 JSON Schema도 함께 출력할지 옵션을 제공한다:

- **옵션 A**: CSV만 출력 (기본)
- **옵션 B**: CSV + 각 파라미터별 JSON Schema 출력

옵션 B 선택 시 각 파라미터의 JSON Schema를 개별적으로 출력한다. **description만이 아닌, 실질적인 validation이 가능한 properties를 포함**해야 한다:

- `type` (필수) — OAS 원본이 실제 용도와 맞지 않으면 올바른 타입으로 보정한다 (e.g., limit이 `string`으로 정의되었지만 실제 정수값이면 `integer`로 보정)
- `description` (있는 경우)
- `enum` (OAS에 명시된 경우 또는 context에서 유추 가능한 경우)
- `minLength`, `maxLength` (문자열 제약이 있는 경우)
- `minimum`, `maximum` (숫자 제약이 있는 경우)
- `format` (date-time, uri 등 표준 포맷이 해당되는 경우)
- `default` (기본값이 있는 경우)

> OAS 원본에 명시된 제약만 포함하되, example이나 description에서 명확히 유추 가능한 제약(e.g., enum 값 목록, 포맷, 타입 보정)도 추가한다. 유추한 항목은 JSON Schema 출력 후 별도 줄에 `> inferred: ...` 형태로 주석을 남긴다. **JSON 내부에 주석(`//`)을 절대 넣지 않는다.**

```markdown
### cursor
```json
{
  "type": "string",
  "description": "페이지네이션 커서",
  "format": "byte"
}
```
> inferred: format — base64 encoded

### limit
```json
{
  "type": "integer",
  "description": "조회 건수",
  "minimum": 1
}
```
> inferred: type — OAS 원본은 string이나 실제 정수값

### order
```json
{
  "type": "string",
  "description": "정렬 기준"
}
```
```

**옵션 선택 후 출력이 완료되면**, 선택하지 않은 다른 옵션의 파라미터 리스트도 출력할지 유저에게 안내한다:
- 옵션 A를 선택했었다면 → "각 파라미터별 JSON Schema도 출력할까요?"
- 옵션 B를 선택했었다면 → "CSV만 별도로 출력할까요?"

---

## Ref Naming Convention Summary

| Context | Pattern | Example |
|---------|---------|---------|
| 재사용 응답 객체 | `{Domain}{ObjectName}` | `CartPriceInfo` |
| 재사용 Request POST 객체 | `Create{Domain}{ObjectName}` | `CreatePhysicalBookPriceInfo` |
| 재사용 Request PATCH 객체 | `Update{Domain}{ObjectName}` | `UpdatePhysicalBookPriceInfo` |

Domain은 엔드포인트의 리소스명에서 유추한다:
- `/physical-books` -> `PhysicalBook`
- `/reviews` -> `Review`
- `/v1/carts` -> `Cart`
- `/online-courses/partner-instructors` -> `PartnerInstructor`
