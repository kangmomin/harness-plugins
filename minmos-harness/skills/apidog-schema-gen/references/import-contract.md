# Apidog 대상·페이로드·결과 계약 (canonical)

`apidog-schema-gen` Step 8, deprecated 분기, `e2e-apidog-schema-gen` Phase 5가 모두 사용한다. `--skip-doctor`는 선택 probe만 생략하며 실제 도구 발견·대상 검증·schema 검증·freeze·read-back은 생략하지 않는다. 이 문서는 이미 요청된 push의 실행 경계다. 읽기/추출 요청 자체를 원격 쓰기 권한으로 해석하지 않는다.

## 실제 도구와 대상 고정

1. 세션의 실제 callable metadata에서 Apidog read/ref/refresh 도구를 찾는다. suffix·설치 prefix를 만들거나 예시 이름을 그대로 호출하지 않는다. 실제 읽기 성공과 서버 설정/응답 근거로 project 및 branch를 확인한다. OAS의 제목/경로가 비슷하다는 이유만으로 같은 프로젝트라 하지 않는다.
2. 최초 확정한 `{project_id,branch_id,method,path,folder_id,mode,schema_mode}`를 실행 상태에 고정한다. path와 method를 함께 비교한다. `main`은 해당 프로젝트의 실제 branch ID로 resolve하고, 신규 폴더 ID도 같은 project/branch에서 확인한다. 기존 API 수정은 `folder_id:null`로 위치를 보존한다. target ID를 확인할 수 없으면 BLOCKED다.
3. `assets/apidog_contract.py tools INPUT.json` 입력은 `{project_id,branch_id,mcp_args?,tools:[{name,operation,project_id,branch_id,verified}]}`다. operation은 read/refs/refresh. 실제 관측으로 verified=true인 도구가 각각 하나여야 한다. 반환 `callables`를 doctor부터 추출·refresh·read-back까지 그대로 전달한다. 필요한 기능이 없거나 여러 후보가 남으면 `BLOCKED:CALLABLE_*_UNRESOLVED`; 임의 첫 도구를 고르지 않는다.
4. MCP args는 `--project=<ID>`, `--project-id=<ID>`, 각 split 형식을 지원한다. 여러 선언이 다르면 BLOCKED다. 환경의 대상 A와 MCP 대상 B가 다르면 B의 토큰/도구를 fallback에 쓰지 않는다. 인증 수단 교체도 같은 대상임을 검증하고 target/폴더/mode는 변경하지 않는다. 토큰은 helper JSON·로그·상태 파일·argv에 넣지 않는다.

## 원본 계약을 보존하는 schema 생성

- `assets/apidog_contract.py select` 입력 `{document,path,method}`는 원본에서 한 operation과 path-level 설정, 필요한 local component 참조의 전체 의존성을 선택한다. `securitySchemes` 이름 참조와 `discriminator.mapping`도 포함하고 순환 `$ref`는 유한한 local 참조로 보존한다. 다른 operation을 가리키는 미해결 참조·외부 ref는 BLOCKED이며 읽기 전용으로 먼저 resolve해야 한다.
- 모든 `responses`의 실제 status(201/202/204/오류/default), headers/links/media type, 모든 위치의 parameters, requestBody의 존재/부재·content, security, servers를 유지한다. GET/POST 같은 method로 body/parameter 위치나 성공 status를 추측하지 않는다. 204에 임의 JSON body를 추가하지 않는다.
- 변경은 확인된 schema/status 필드만 반영한다. 기존 응답이나 component를 통째로 생성물로 바꾸지 않는다. 실측하지 않은 응답은 기존 계약을 유지한다. 최종 diff에 operation뿐 아니라 import할 모든 shared component의 변경도 포함한다. 공유 schema 수정은 다른 operation에 영향을 줄 수 있으므로 그 범위까지 요청된 경우에만 덮어쓴다. 읽어 온 그대로의 component는 `schema_mode:KEEP_EXISTING`; 필요한 신규/변경 component 처리 정책은 freeze 전에 확정한다.
- dialect/nullable/순환 참조 규칙은 `schema-contract.md`다. `normalize {document,dialect}`의 dialect는 `3.0` 또는 `3.1`; 기본 새 문서는 OAS 3.0.3. 기존 dialect를 바꾸는 경우 변환 차이도 review한다. deprecated 보존 분기는 **normalize하지 않고** 기존 OAS 버전·선택된 정의를 보존하며 operation의 status/deprecated 두 필드 외 차이는 BLOCKED다.

## 검증된 bytes freeze와 전송

1. `freeze` 입력은 `{run_id,target,document,directory?}`. target은 위 일곱 필드를 모두 포함한다. helper는 완전한 OAS 문서를 설치된 `openapi-spec-validator`로 검증한다. 없으면 `BLOCKED:OPENAPI_VALIDATOR_MISSING`; push 중 자동 다운로드하지 않는다. 저장소 fixture의 검증 버전은 `openapi-spec-validator==0.7.2`다.
2. helper가 만드는 `apidog-run-<random>` 디렉터리는 실행별 exclusive 0700, `openapi.json`·`request.json`·`receipt.json`은 exclusive 0600이다. JSON도 OAS import input으로 사용할 수 있다. endpoint slug만 같은 공유 `/tmp` 파일을 만들지 않는다.
3. 반환 receipt의 run/target/payload SHA-256/request SHA-256을 **오케스트레이터 상태/메모리에 보관**한다. 나중에 같은 디렉터리의 receipt를 다시 읽어 원래 검증 증거로 교체하지 않는다. helper는 파일 위변조 방지 서명 시스템이 아니다.
4. `request {receipt,run_id,target}`는 원래 receipt로 파일 권한·hash·target을 재검증하고 `url`, `request_base64`, `request_sha256`을 반환한다. 전송자는 이 반환 값을 한 번 decode한 **동일 메모리 bytes**를 HTTP body로 전송한다. decode 뒤 파일을 다시 읽거나 shell 문자열에 JSON을 끼워 넣지 않는다. `options.targetBranchId`·folder/mode도 고정된 body에 포함된다. 사용자 입력 URL/redirect로 토큰을 전송하지 않고 Apidog origin을 유지한다.
5. MCP write를 쓸 때도 같은 target과 payload/options를 그대로 지원하는 actual callable인지 확인한다. 지원하지 않으면 **첫 전송 전에** REST를 선택한다. MCP 호출 후 실패/timeout이면 아래 UNKNOWN 처리로 넘어가며 REST로 자동 재전송하지 않는다. REST 인증은 메모리 header로만 전달한다.
6. 실제 전송 bytes hash, origin/project/branch/method/path, attempt ID, HTTP/MCP 응답 receipt를 기록한다. helper 자체는 전송하지 않는다. `--dry-run`은 freeze까지만 실행하고 `NOT_SENT`를 보고한다.

## 결과 분류와 재시도

`outcome` 입력은 `{http_status?,body?,transmission_started?,no_write_verified?}`. body는 실제 JSON 응답이다. 2xx/success:true만으로 완료 판정하지 않는다. errors/failed 또는 실패 응답 중 created/updated가 있으면 부분 적용이다. 202, redirect, timeout, 연결 유실, 빈/잘못된 응답은 UNKNOWN이다. `no_write_verified`는 전송 전 실패나 서버의 확정된 무변경 거절 근거가 있을 때만 true다.

`decision` 입력은 `{receipt,run_id,target,state,attempts,no_write_verified?,credential_target?,readback?}`. state는 outcome 결과를 사용한다.

| 상태 | 조치 |
|------|------|
| NOT_SENT / REJECTED_NO_WRITE | 무변경 근거가 있고 attempts=1일 때만 같은 target/request bytes로 1회 재시도 가능. 수정 payload/옵션은 새 diff·검증·freeze가 필요하다. |
| UNKNOWN / PARTIAL | 전송 결과 미확정. 먼저 같은 project/branch에서 cache refresh 후 read-back. 조회 불가/일부 일치/아직 없음은 UNKNOWN 유지, 자동 재전송 금지. |
| ACKNOWLEDGED | 원격 수락으로 기록하고 read-back으로 최종 실제 계약/status를 확인한다. counters만으로 완료하지 않는다. |

readback은 `{target,request_sha256,fresh,after_attempt,complete,matches_expected}`. 원래 request hash의 기대 문서와 같은 대상의 **시도 이후 최신** 전체 operation/참조 component/status/폴더를 비교한 실제 evidence가 필요하다. 서버가 normalization한 필드는 명시적 비교 규칙으로만 처리하며 단순 path 존재/스키마 일부 일치를 MATCH라 하지 않는다. 동일하면 `OBSERVED_MATCH`이며 이 요청이 원인이라는 attribution은 미확정이다. `CREATE_NEW`의 정상 ACKNOWLEDGED는 `creation={before_verified:true,acknowledged_created_count:1,before_ids,after_ids,new_matching_ids}`를 추가로 대조한다. 같은 대상의 시도 전 ID 목록과 최신 read-back 차이가 응답 created count=1 및 새로 일치한 실제 endpoint ID 1개와 같으면 `OBSERVED_NEW_MATCH`다. ID/완전한 snapshot을 확보하지 못하면 UNKNOWN이다. timeout의 단순 일치와 구별한다. `CREATE_NEW`의 timeout은 같은 path가 보인다는 것으로 신규 중복 개수를 알 수 없으므로 UNKNOWN을 유지한다.

UNKNOWN에서 ‘이 파일을 다시 import’라고 안내하지 않는다. target/hash와 미확정 이유, read-back 확인 방법, 보존된 artifact 경로를 보고한다. 확정 거절/미전송 상태에서만 동일 대상의 수동 import 자료로 전달한다. remote 결과를 확인하기 전 임시 자료를 지우지 않는다. 완료 후에는 자신이 만든 디렉터리만 정리한다.

공식 근거: [OpenAPI 3.0 Schema Object](https://spec.openapis.org/oas/v3.0.3.html#schema-object), [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.1.html#schema-object), [Apidog Import/Export API](https://openapi.apidog.io/import-export-1328063f0), [validator](https://github.com/python-openapi/openapi-spec-validator). 로컬 fixture 검증은 실제 Apidog import/read-back과 구별해서 보고한다.
