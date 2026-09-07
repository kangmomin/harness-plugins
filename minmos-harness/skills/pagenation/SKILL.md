---
name: pagenation
description: "커서 기반 페이지네이션 구현 컨벤션 (참조 문서). 목록 API에 페이지네이션을 구현하거나 '페이지네이션 어떻게 해?'를 물을 때, convention-check 검사 기준으로 사용."
user-invocable: true
---

# 커서 기반 페이지네이션 구현 컨벤션

정본은 세션에 제공된 `go-conventions:conventions-guide`의 `cursor-pagination-spec`·`entity-repository-contract`다. 이 문서는 정본의 repository 계약을 유지하면서 정렬/seek/cursor를 같은 정규 목록으로 구성하는 실행 가능한 참조를 제공한다.

## API와 repository 계약

| 매개변수 | 의미 |
|----------|------|
| `order` | API 허용 키와 asc/desc. 예: `createdAt:desc|id:asc`. 확인한 CloudKit parser의 구분자는 `|`다. |
| `cursor` | 첫 페이지는 빈 문자열. 이후 opaque nextCursor를 그대로 전달한다. |
| `limit` | 참조 구현은 1..100. 서비스의 기존 명세 범위가 다르면 그 범위로 명시적으로 조정한다. |

정본 시그니처의 **인수 순서와 4-tuple**을 유지한다:

```go
GetAllCursor(ctx context.Context, cursor string, limit int, order string) ([]*domain.ModuleVO, int, string, error)
```

첫 페이지에서만 COUNT를 실행하고 totalItems를 포함한다. 이후 totalCount=0으로 생략하며 response에도 totalItems를 넣지 않는다. 기본 조회는 `status = 'active'`를 유지한다.

## 참조 구현 사용

`assets/pagination.go`는 실제 컴파일/SQL fixture로 검증하는 정렬 계획·다음 커서 helper다. SQL/GORM 호출이나 서비스 VO 변환을 수행하는 완성 repository라고 표시하지 않는다. 기존 서비스에 적용할 때는 다음 연결을 구현하고 해당 서비스 테스트를 실행한다.

1. 코드에서 API 정렬 키→DB 컬럼·타입 allowlist를 만든다. 예: `createdAt → created_at(int64)`, `id → id(int64)`. map 자체를 요청에서 받지 않는다. `id`는 실제 고유 키여야 한다. 참조는 안정적인 non-null int64/string 정렬값만 지원하며 nullable/임의 expression 정렬은 추가 계약 없이 허용하지 않는다.
2. `Build(order, cursor, limit, fields, codec)`가 만든 **같은 Terms**를 ORDER BY, seek predicate, 다음 cursor에 사용한다. 신규 요청에 id가 없으면 Terms에 `id:desc`를 추가한다. SQL ORDER에만 따로 추가하지 않는다.
3. cursor가 있으면 서명 검증 후 key/direction/value/버전을 다시 검증한다. 요청 order가 있으면 id를 포함해 정규화한 목록과 완전히 같아야 한다. order 생략 시 검증된 cursor order를 유지한다. 기존 cursor에 id/value가 없으면 자동 추정하지 않고 첫 페이지 재시작을 안내한다.
4. `query := db.WithContext(ctx).Table(actualTable).Where("status = ?", "active")`에 기존 tenant/권한/검색 필터를 유지한다. FirstPage일 때만 이 base query로 Count한다. 그 뒤 `query.Where(plan.WhereSQL, plan.Args...).Order(plan.OrderSQL).Limit(plan.FetchLimit)`로 조회한다. 첫 페이지의 빈 WhereSQL은 적용하지 않는다.
5. helper의 seek는 괄호로 묶인 OR-of-AND다. base filter 아래에 **한 번의 Where**로 결합한다. 항목별 `query.Or(...)`를 붙여 status/tenant 조건을 우회하지 않는다. 값은 반드시 Args로 bind한다.
6. FetchLimit은 limit+1이다. 조회 entities를 `Finish(plan, entities, value, codec)`에 전달한다. value callback은 정렬 키의 실제 값을 정확한 `json.RawMessage`로 반환하며 int64를 float64로 변환하지 않는다. Finish가 sentinel을 자르고 마지막 **유지된 행**으로만 cursor를 만든다. 마지막 페이지는 정확히 limit개여도 더 읽을 행이 없으면 빈 cursor다.
7. 반환된 page entities만 기존 converter로 VOs에 옮긴 후 `vos, totalCount, nextCursor, err`를 반환한다. encode/변환 오류는 정상 페이지로 숨기지 않는다. 정렬값이 같은 행·혼합 방향·마지막 페이지와 base filter 보존을 실제 repository에서 검증한다.

## 식별자와 값 검증

snake_case 변환은 이름 스타일이며 SQL Injection 방어가 아니다. [GORM Security](https://gorm.io/docs/security.html)는 Order 문자열 등 SQL 구조에 요청 입력을 직접 넣지 않도록 설명한다. 참조 helper는 코드 소유 allowlist의 컬럼만 인용하고 direction을 asc/desc로 제한하며 값은 placeholder 인수로 분리한다. 서명된 cursor도 이 검증을 생략하지 않는다.

잘못된 컬럼/방향/중복 키/문법/limit는 SQL 생성 전에 실패한다. cursor의 null/빈 terms/누락 값/중복 JSON key/중복 정렬 키/미지원 버전도 거부한다. 시간 필드를 추가한다면 DB와 애플리케이션의 타입·UTC 표현·정렬 의미가 맞는지 별도로 확인한다. 활성 부분 인덱스는 기존 것을 우선 사용하고 새 인덱스는 실행계획으로 필요가 확인된 경우에만 추가한다.

## CloudKit codec 연결과 지원 범위

확인한 CloudKit 실제 소스 계약과 측정 근거는 `references/cloudkit-contract.md`에 있다. ParseOrderParam은 allowlist/direction 검증을 대신하지 않는다. CursorDecode의 interface{} 숫자는 큰 int64를 잃을 수 있으므로 그 결과를 정밀한 seek 값이라고 가정하지 않는다.

참조의 `SignedJSONCodec`은 **새 hp1 서명 형식**이며 기존 CloudKit cursor와 호환되지 않는다. 기존 서비스를 조용히 이 형식으로 교체하지 않는다. 적용 시 버전 전환/기존 cursor 재시작 정책을 명시하거나 서명을 먼저 검증하고 typed 값을 보존하는 기존 호환 codec adapter를 제공한다. 서명을 우회하여 원시 JSON을 읽는 fallback은 금지다. Codec.Encode는 error를 반환해야 하므로 panic하는 기존 encode 경계도 확인한다.

이 저장소는 참조 Go 코드를 컴파일하고 그 SQL을 로컬 SQLite fixture에 실행한다. 전체 CloudKit/GORM 소비 서비스의 배포·보안 검증을 완료했다고 주장하지 않는다.
