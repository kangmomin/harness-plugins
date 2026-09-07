# Schema dialect와 순환 참조 (canonical)

추출·화면 복사·E2E 보정·push 모두 출력 dialect를 명시한다. 기본 import는 OAS 3.0.3이다. raw JSON Schema/OAS 3.1 UI 출력은 별도 표기하고 OAS 3.0 import에 그대로 재사용하지 않는다.

| 의미 | OAS 3.0 | OAS 3.1 / JSON Schema |
|------|---------|----------------------|
| nullable string | `type: string, nullable: true` | `type: [string, 'null']` |
| nullable array | `type: array, nullable: true, items: {...}` | `type: [array, 'null'], items: {...}` |
| nullable object | `type: object, nullable: true, properties: {...}` | `type: [object, 'null'], properties: {...}` |
| null만 허용 | `type: string, nullable: true, enum: [null]` | `type: 'null'` |

`assets/apidog_contract.py normalize`가 지원하는 변환은 위 nullable 형태와 3.0 boolean exclusiveMinimum/exclusiveMaximum의 3.1 numeric 변환, 재귀적인 schema 위치에 한정된다. 3.1 numeric exclusive bound를 3.0으로 되돌리는 변환은 BLOCKED다. 여러 non-null type union, 동적/외부 schema scope, 다른 dialect의 미지원 keyword는 임의 축약하지 않고 명시적 변환 경계와 개별 Schema Object의 dialect check_schema에서 BLOCKED다. 전체 OAS 문서 validator만으로 모든 schema keyword를 검사했다고 하지 않는다. 변환 중 examples/default/enum/vendor data를 스키마로 재해석하지 않는다.

null의 관측만으로 string/object를 발명하지 않는다. 실제 타입은 코드/기존 명세에서 확인한다. OAS 3.0의 nullable은 다른 enum/조합 제약을 지우지 않는다. `oneOf: [{type: null}, {type: string, enum: [A]}]`를 `enum:[A], nullable:true`로 합치면 null이 사라지므로 branch를 유지한다. 전체 문서 validator에 더해 null·허용/거절 비null 값의 의미도 확인한다. required(필드 존재)와 nullable(값 허용)은 별도이며 Go 포인터만으로 required를 바꾸지 않는다.

**인라인/참조 정책은 하나다.** 비순환 중첩은 읽기 편의를 위해 인라인으로 표시할 수 있다. 재사용·자기 참조·순환 객체는 local `$ref`와 필요한 정의를 함께 보존한다. 반복 확장하거나 깊이 상한에서 `{}`로 바꾸지 않는다. import는 `#/components/schemas/...`, 독립 JSON Schema 출력은 local `$defs`로 올바르게 재작성한 하나의 완결 문서를 사용한다. 순환 스키마는 ref 없는 한 블록 출력이 불가능하므로 필요한 정의를 포함한 전체 문서를 전달한다.

참조 의존성은 schema `$ref`뿐 아니라 parameters/responses/headers/examples/requestBodies/securitySchemes와 discriminator mapping도 포함한다. 예시/벤더 확장 값 안의 literal `$ref`는 참조가 아니다. 도구의 `select`는 사용하지 않는 component를 제외하고 필요한 의존성만 남긴다. 공유 component 변경 영향은 별도 diff로 보여준다.

[OAS 3.0](https://spec.openapis.org/oas/v3.0.3.html#schema-object)과 [OAS 3.1](https://spec.openapis.org/oas/v3.1.1.html#schema-object)을 기준으로 하며, Apidog UI가 관대하게 수용했다는 이유로 잘못된 dialect를 통과시키지 않는다.
