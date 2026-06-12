> 이 문서는 `apidog-schema-gen-mm` 스킬의 Step 8(Apidog Push)에서 로드된다. 단독 실행 금지.

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

## Step 8.3: OpenAPI Spec 생성

코드 기준 최종 스키마를 단일 엔드포인트 OpenAPI 3.0 YAML로 변환한다.

- `openapi: "3.0.0"` 고정
- `info.title`: 프로젝트명 또는 서비스명
- `paths`: 해당 엔드포인트 1개만 포함
- `parameters`: GET이면 query params 포함
- `requestBody`: POST/PUT/PATCH이면 request schema 포함
- `responses.200`: response schema 포함
- 모든 스키마는 flat 인라인 (Step 5 원칙 유지)

**파일 저장**: `/tmp/apidog-push-{endpoint-slug}.yaml`

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
| `--dry-run` | YAML만 생성하고 실제 푸시하지 않음 | false |

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
