> 이 문서는 `apidog-schema-gen` 스킬의 Step 8(Apidog Push)에서 로드된다. 단독 실행 금지.

# Apidog Push 상세 + Import API 레퍼런스

## Step 8.1: 환경 변수 확인

필요한 환경 변수 2개: `APIDOG_ACCESS_TOKEN` (Personal Access Token), `APIDOG_PROJECT_ID` (대상 프로젝트 ID)

```bash
echo "TOKEN=${APIDOG_ACCESS_TOKEN:+set}" "PROJECT=${APIDOG_PROJECT_ID:+set}"
```

미설정 시 유저에게 안내:
> "Apidog Push에 필요한 환경 변수가 설정되어 있지 않습니다.
> 1. Apidog → Settings → API Access Token에서 토큰 생성
> 2. 아래 명령으로 설정:
> ```
> export APIDOG_ACCESS_TOKEN='your-token'
> export APIDOG_PROJECT_ID='your-project-id'
> ```"

## Step 8.2: 대상 폴더 결정

Push 전에 Apidog 프로젝트에서 해당 API 경로의 **기존 존재 여부**를 확인하고 폴더를 결정한다.

1. `mcp__apidog__read_project_oas_*`로 OAS 전체를 읽어 기존 경로 목록을 확인한다.
2. **경로가 이미 존재** → `updateFolderOfChangedEndpoint: false`로 기존 위치에서 수정 (폴더 이동 안 함).
3. **경로가 없음 (신규 API)** → 유사 경로를 탐색하여 가장 가까운 폴더에 배치한다:
   - 유사 경로 판별 기준: **경로 prefix가 가장 많이 일치하는 기존 엔드포인트의 폴더**
   - 유사 경로도 없으면 Root 폴더에 배치 (기본값)

| 신규 경로 | 기존 경로 | prefix 일치 | 폴더 |
|----------|----------|------------|------|
| `POST /v1/reviews` | `GET /v1/reviews` | `/v1/reviews` (완전 일치) | 같은 폴더 |
| `GET /v1/products/{id}/options` | `GET /v1/products/{id}` | `/v1/products/{id}` | 같은 폴더 |
| `POST /v1/cart/items` | `GET /v1/cart` | `/v1/cart` | 같은 폴더 |
| `POST /v1/notifications` | (없음) | 없음 | Root |

## Step 8.2.5: 엔드포인트 status 결정

Apidog 은 엔드포인트를 **삭제**하는 import 옵션을 제공하지 않는다. 그래서 이 스킬은 제거된 API 를 지우는 대신 **`deprecated` status 로 표시**하고, 그 밖의 API 도 수명주기 status 를 함께 push 한다.

status 는 **항상 명시한다** — 생략하지 않는다. import 시 `x-apidog-status` 를 빠뜨리면 기존 status 가 유지되는지 초기화되는지 Apidog 문서에 명시가 없어, 값을 반드시 실어 보내 결과를 결정론적으로 만든다.

### 결정 우선순위

위에서 먼저 정해지면 아래는 보지 않는다.

**1순위 — `--status {값}` 플래그**
아래 10종 literal 로만 검증한다. 불일치하면 목록을 제시하고 다시 묻는다 (임의로 교정하지 않는다).

**2순위 — 컨텍스트 추론**

| 상황 | status | 근거 |
|------|--------|------|
| OAS 에 없는 신규 경로 + 코드에 handler 존재 | `developing` | Apidog 의 신규 엔드포인트 기본값과 일치 |
| OAS 에 없는 신규 경로 + handler 없음 + **사용자가 설계 스키마를 직접 제공** | `designing` | 구현 전 설계 단계 |
| **OAS 에 이미 존재하는** 경로인데 코드에 handler 없음 (제거된 API) | **`deprecated`** | 삭제 불가 → 지원 중단 표시 |
| 기존 엔드포인트 단순 수정 | **현재 status 유지** | OAS 의 `x-apidog-status` 를 읽어 **그 값을 그대로 재기입**한다. 값이 없으면 `developing` |
| E2E 실측 후 push (`/minmos-harness:e2e-apidog-schema-gen`) | `tested` / `testing` | 그 스킬의 Phase 5.0.5 참조 |

**3순위 — 확인**
추론값을 Step 7(확인) 에서 함께 보여주고 사용자가 바꿀 수 있게 한다. 별도 질문 단계를 새로 만들지 않는다.

> **`designing` 과 `deprecated` 의 전제**:
> - `designing` 은 OAS 에도 코드에도 없는 경로다 — 스키마를 만들 근거가 없으므로 **사용자가 설계 스키마를 직접 제공한 경우에만** push 한다. 제공이 없으면 push 하지 않고 안내한다: "OAS 와 코드 어디에도 정의가 없어 push 할 스키마가 없습니다. 설계 스키마를 제공해주세요."
> - `deprecated` 는 **OAS 에 이미 존재하는 경로에만** 적용한다. OAS 에 없는 경로는 애초에 지울 대상이 아니다.

### 안전 규칙

- **`released` 는 자동 추론하지 않는다.** `--status released` 또는 사용자의 명시 선택으로만 설정된다 — 릴리즈 판정은 코드 상태로 유추할 수 있는 것이 아니다.
- **다운그레이드 금지.** 현재 status 가 `released`·`deprecated`·`obsolete` 인데 추론값이 그보다 이른 단계(`designing`~`tested`)면 **현재 값을 유지**하고 경고만 남긴다:
  > "기존 status 가 `{현재값}` 이라 추론값 `{추론값}` 을 적용하지 않고 유지했습니다. 바꾸려면 `--status {값}` 을 지정하세요."
  플래그로 명시한 경우에는 그대로 따른다 (사용자 의도가 우선).

### deprecated push 특칙

`deprecated` 로 표시하는 대상은 **코드에 handler 가 없다** — 코드 기준 스키마를 만들 수 없다. 이때 빈 스텁을 `OVERWRITE_EXISTING` 으로 밀어넣으면 Apidog 에 남아 있던 기존 문서가 파괴된다.

**이 분기는 종결 분기다** — Step 8.3의 "코드 기준 스키마 재구성"을 수행하지 않는다. 8.3의 flat 재생성을 그대로 적용하면 보존해야 할 기존 정의가 코드 기준 스키마로 대체되어 특칙의 목적이 무너진다.

1. `mcp__apidog__read_project_oas_ref_resources_*` 로 해당 엔드포인트의 **기존 정의를 그대로 읽는다** (참조하는 스키마 의존까지 함께).
2. 그 정의를 **변경 없이** 재발행하고, operation 에 두 필드만 추가한다:
   - `x-apidog-status: deprecated`
   - `deprecated: true` (OpenAPI 표준 필드 — Apidog 외 도구에서도 인식된다)
3. Step 4(코드베이스 교차 검증)와 Step 8.3(스키마 재구성)은 건너뛴다 — 대조할 코드가 없고, 재구성은 보존과 상충한다.
4. **재발행 전 차이 검증**: 생성한 YAML 과 원본 정의를 비교해 **위 두 필드 외에 달라진 곳이 없는지** 확인한다. 다른 차이가 있으면 push 하지 않고 보고한다 — "기존 정의를 그대로 보존하지 못해 중단했습니다."
5. **검증한 페이로드를 저장한다** — Step 8.4가 읽는 경로와 동일해야 한다:
   ```bash
   # 보존 + 두 필드만 추가한 결과를 저장
   /tmp/apidog-push-{endpoint-slug}.yaml
   ```
   이 분기는 Step 8.3을 건너뛰므로, 여기서 저장하지 않으면 Step 8.4가 파일을 찾지 못하거나 **이전 실행이 남긴 낡은 파일**을 읽어 엉뚱한 스펙을 push 한다. 저장 후 파일이 방금 만든 내용인지(대상 경로·method·`x-apidog-status: deprecated`·`deprecated: true`) 확인하고 Step 8.4로 넘어간다.
6. **overwrite 모드 제약**: 이 분기는 `OVERWRITE_EXISTING` 으로만 push 한다.
   - `--keep`(KEEP_EXISTING) → status 갱신이 무시된다. 거부하고 안내한다.
   - `--new`(CREATE_NEW) → 엔드포인트가 중복 생성된다. 거부하고 안내한다.
   - `--merge`(AUTO_MERGE) → 병합 결과를 보장할 수 없다. 거부하고 안내한다.
   > "deprecated 처리는 기존 정의를 그대로 덮어써야 하므로 `OVERWRITE_EXISTING` 만 사용합니다. `{지정한 옵션}` 은 적용하지 않았습니다."


기존 정의를 읽지 못하면 push 하지 않고 보고한다:
> "기존 정의를 읽을 수 없어 deprecated 처리를 중단했습니다 — 빈 스펙을 덮어쓰면 기존 문서가 사라집니다. Apidog UI 에서 직접 status 를 변경해주세요."

### status 값 레퍼런스

`x-apidog-status` 는 **operation object** 레벨에 놓는다. 허용 값은 아래 10종이다.

| literal | 한국어 | 의미 |
|---------|--------|------|
| `designing` | 설계중 | 스펙 설계 단계, 구현 전 |
| `pending` | 대기중 | 보류 — 진행이 멈춘 상태 |
| `developing` | 개발중 | 구현 진행 중 (**신규 엔드포인트 기본값**) |
| `integrating` | 연동중 | 프론트/외부 연동 진행 중 |
| `testing` | 테스트중 | 검증 진행 중 |
| `tested` | 테스트완료 | 검증 통과, 릴리즈 전 |
| `released` | 릴리즈 | 배포 완료 (자동 추론 금지) |
| `deprecated` | 지원중단 | 사용 중단 예정/중단됨 — **삭제 대신 쓰는 값** |
| `exception` | 예외 | 비정상 상태 |
| `obsolete` | 폐기 | 완전히 폐기됨 |

출처: <https://docs.apidog.com/x-apidog-status-1981670m0> (literal 목록), <https://docs.apidog.com/endpoint-status-539760m0> (신규 기본값 `developing`)

## Step 8.3: OpenAPI Spec 생성

코드 기준 최종 스키마를 단일 엔드포인트 OpenAPI 3.0 YAML로 변환한다.

> **예외**: Step 8.2.5에서 status 가 `deprecated` 로 결정된 경우 이 단계를 수행하지 않는다 — 그 분기는 "deprecated push 특칙"에서 기존 정의를 그대로 재발행하며 종결되고, **YAML 저장도 그 분기가 직접 수행한다**(같은 `/tmp/apidog-push-{endpoint-slug}.yaml` 경로). 저장까지 마친 뒤 아래 Step 8.4(Import API 호출)로 바로 넘어간다.

- `openapi: "3.0.0"` 고정
- `info.title`: 프로젝트명 또는 서비스명
- `paths`: 해당 엔드포인트 1개만 포함
- **`x-apidog-status`**: Step 8.2.5에서 결정한 값을 **operation 레벨에** 반드시 기입한다 (생략 금지)
- `deprecated: true`: status 가 `deprecated` 일 때만 operation 에 함께 기입한다
- `parameters`: GET이면 query params 포함
- `requestBody`: POST/PUT/PATCH이면 request schema 포함
- `responses.200`: response schema 포함
- 모든 스키마는 flat 인라인 (Step 5 원칙 유지)

배치 위치 예시 (operation 레벨 — `responses` 와 같은 깊이):

```yaml
paths:
  /v1/reviews:
    post:
      summary: 리뷰 생성
      x-apidog-status: developing
      requestBody: { ... }
      responses: { ... }
```

**파일 저장**: `/tmp/apidog-push-{endpoint-slug}.yaml`

저장 직후 status 가 실제로 들어갔는지 확인한다 — 누락된 채 push 하면 기존 status 가 어떻게 되는지 보장되지 않는다:

```bash
grep -n 'x-apidog-status' /tmp/apidog-push-{endpoint-slug}.yaml
```

0건이면 push 하지 않고 YAML 생성을 다시 한다.

## Step 8.4: Apidog Import API 호출

```bash
curl -s -X POST \
  "https://api.apidog.com/v1/projects/${APIDOG_PROJECT_ID}/import-openapi" \
  -H "Authorization: Bearer ${APIDOG_ACCESS_TOKEN}" \
  -H "X-Apidog-Api-Version: 2024-03-28" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": $(cat /tmp/apidog-push-{endpoint-slug}.yaml | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
    \"options\": {
      \"endpointOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"schemaOverwriteBehavior\": \"OVERWRITE_EXISTING\",
      \"updateFolderOfChangedEndpoint\": false,
      \"prependBasePath\": false,
      \"targetFolderId\": {folderId 또는 생략}
    }
  }"
```

- `targetFolderId`: Step 8.2에서 결정한 폴더 ID. 기존 경로 수정 시에는 생략한다.

## Step 8.5: MCP Scraping Fallback (REST API 실패 시)

REST API 호출이 실패하면 (302, 401, 400, 빈 응답, timeout 등), MCP에서 프로젝트 정보를 스크래핑하여 **1회 재시도**한다.

**실패 감지:** HTTP status 비 2xx / `"success": false` 응답 / curl 자체 에러 (timeout, connection refused 등)

**스크래핑 절차:**

1. **MCP 설정 파싱** — 현재 클라이언트에서 읽을 수 있는 MCP 설정을 확인하여 인증 정보를 추출한다. `.mcp.json`에 한정하지 않는다.
   - **Project ID**: 설정의 `args`에서 `--project-id=` 인자를 찾고 `APIDOG_PROJECT_ID`와 대조, 불일치 시 MCP 설정 값을 우선 사용
   - **Access Token** 탐색 우선순위:
     1. MCP 설정의 `args`에 `--api-key=` 또는 `--access-token=` 인자
     2. MCP 설정의 `env` 섹션의 `APIDOG_ACCESS_TOKEN`
     3. 둘 다 없으면 현재 셸의 `APIDOG_ACCESS_TOKEN` 환경 변수 유지
2. **OAS 구조 확인** — `mcp__apidog__read_project_oas_*` 호출로 프로젝트 접근 가능 여부 확인, 대상 경로 존재 여부 재확인, 기존 경로 목록으로 folder 배치 후보 파악 (Step 8.2의 prefix 매칭 재사용).
3. **교정된 파라미터로 1회 재시도**: 교정된 Project ID/Access Token 적용, 올바른 targetFolderId 지정, YAML 포맷은 기존 OAS 엔드포인트 구조를 참고하여 호환성 검증.

> **핵심**: MCP가 OAS를 정상 조회하고 있어도 인증 정보가 반드시 `.mcp.json`에 있는 것은 아니다. 읽을 수 있는 MCP 설정과 현재 환경 변수를 함께 사용한다.

재시도도 실패하면 즉시 수동 안내로 전환한다. **2회 이상 반복 시도하지 않는다.**

> 수동 안내: "자동 Push가 실패했습니다. 아래 YAML 파일을 Apidog에서 수동으로 Import 해주세요: `/tmp/apidog-push-{endpoint-slug}.yaml`"

## Step 8.6: 결과 보고

API 응답의 `data.counters`를 파싱하여 유저에게 보고:

```
### Apidog Push 결과
| 항목 | 생성 | 수정 | 실패 | 무시 |
|------|------|------|------|------|
| Endpoint | {created} | {updated} | {failed} | {ignored} |
| Schema | {created} | {updated} | {failed} | {ignored} |
```

적용한 status 도 함께 보고한다:

```
- status: `{값}` ({한국어 라벨}) — {플래그 지정 | 추론: 사유 | 기존 값 유지}
```

`errors` 배열이 비어있지 않으면 에러 내용도 함께 출력한다.

## Step 8.7: Push 옵션

유저가 커스텀 옵션을 지정할 수 있다:

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--folder {id}` | 대상 폴더 ID 지정 | Root |
| `--merge` | 기존 API와 병합 (AUTO_MERGE) | OVERWRITE_EXISTING |
| `--keep` | 기존 API 유지, 새 것만 추가 (KEEP_EXISTING) | OVERWRITE_EXISTING |
| `--new` | 항상 새로 생성 (CREATE_NEW) | OVERWRITE_EXISTING |
| `--branch {id}` | 대상 브랜치 ID | main |
| `--status {값}` | 엔드포인트 status 지정 (10종 literal, Step 8.2.5 표 참조) | 컨텍스트 추론 |
| `--dry-run` | YAML만 생성하고 실제 푸시하지 않음 (생성된 `x-apidog-status` 값도 함께 출력) | false |

---

# Apidog REST API Push 레퍼런스

MCP에 write 기능이 없을 때 사용하는 Apidog REST API 스펙. 매번 검색하지 않도록 여기에 기록한다.

## 엔드포인트

```
POST https://api.apidog.com/v1/projects/{projectId}/import-openapi
```

## 헤더

| Header | 값 |
|--------|----|
| `Authorization` | `Bearer ${APIDOG_ACCESS_TOKEN}` |
| `X-Apidog-Api-Version` | `2024-03-28` |
| `Content-Type` | `application/json` |

## Request Body

```json
{
  "input": "<OpenAPI YAML 문자열 (JSON escaped)>",
  "options": {
    "endpointOverwriteBehavior": "OVERWRITE_EXISTING",
    "schemaOverwriteBehavior": "OVERWRITE_EXISTING",
    "updateFolderOfChangedEndpoint": false,
    "prependBasePath": false
  }
}
```

## options 필드

| 필드 | 값 | 설명 |
|------|----|------|
| `endpointOverwriteBehavior` | `OVERWRITE_EXISTING` / `KEEP_EXISTING` / `AUTO_MERGE` / `CREATE_NEW` | 기존 엔드포인트 처리 방식 |
| `schemaOverwriteBehavior` | `OVERWRITE_EXISTING` / `KEEP_EXISTING` / `AUTO_MERGE` / `CREATE_NEW` | 기존 스키마 처리 방식 |
| `updateFolderOfChangedEndpoint` | `false` | 변경된 엔드포인트의 폴더 이동 여부 |
| `prependBasePath` | `false` | basePath를 경로 앞에 추가할지 |
| `targetBranchId` | `number` (선택) | 대상 브랜치 ID |
| `targetFolderId` | `number` (선택) | 대상 폴더 ID |

## Response 구조

```json
{
  "success": true,
  "data": {
    "counters": {
      "endpoint": { "created": 0, "updated": 1, "failed": 0, "ignored": 0 },
      "schema": { "created": 0, "updated": 1, "failed": 0, "ignored": 0 }
    },
    "errors": []
  }
}
```

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 302 Redirect | URL 오타 또는 프로젝트 ID 오류 | Step 8.5 MCP Fallback → project ID 추출 후 1회 재시도. 재실패 시 수동 안내 |
| 401 Unauthorized | 토큰 만료/잘못됨 | Step 8.5 MCP Fallback → 토큰 추출 후 1회 재시도. 재실패 시 `APIDOG_ACCESS_TOKEN` 재생성 안내 |
| 400 Bad Request | YAML 포맷 오류 | Step 8.5 MCP Fallback → 기존 OAS 구조 참조하여 YAML 검증 후 1회 재시도 |
| `errors` 배열 비어있지 않음 | 스키마 충돌 | 에러 메시지 확인 후 options 조정 |
