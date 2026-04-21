---
name: e2e-test
description: "기능 추가/수정 후 연관 HTTP API를 실제 요청으로 E2E 테스트한다. profile의 runServerCommand/serverUrl 기반 범용 API 테스트."
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
argument-hint: <대상 API 설명 또는 엣지 케이스 ID>
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/e2e-test.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# E2E API 테스트

프로젝트 profile에 지정된 서버를 기동하고, 변경된 API에 실제 HTTP 요청을 보내 응답을 검증한다.
외부 MCP/전용 CLI에 의존하지 않고 **Bash + curl + profile** 조합만 사용한다.

## Language Rule

유저와의 모든 대화는 **한국어** (profile의 `language` 기준).

---

## Prerequisites

- profile(`.claude/be-harness.local.md`)의 아래 필드가 유효해야 한다:
  - `e2eEnabled: true`
  - `serverUrl: "http://..."`
  - `runServerCommand`: 로컬 서버 기동 명령 (이미 서버가 떠 있으면 비워도 됨)
- profile이 없거나 `e2eEnabled: false`면 **`[SKIPPED:PROFILE]`** 을 반환하고 종료한다.

## 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--doctor` | | prerequisite 상태 진단 후 종료 |
| `--skip-server` | `-ss` | 서버 기동/종료를 건너뛰고 이미 떠있는 서버를 사용 |
| `--tag <id>` | | 특정 엣지 케이스 ID만 실행 |

### `--doctor`

1. profile 읽고 `e2eEnabled`, `serverUrl`, `runServerCommand` 유효성 확인
2. `curl --version` 확인
3. 포트 충돌 여부 (`ss -tlnp` 또는 `lsof -i :PORT`) 확인
4. 결과 표 출력 후 종료

---

## Step 1: 대상 API 수집

사용자의 요청 또는 현재 브랜치의 `git diff`에서 변경된 API를 추출한다:

1. `git diff --name-only main...HEAD` 로 변경 파일 목록.
2. profile의 `sourceDirs` 중 handler/route 계층에서 HTTP 엔드포인트(Method + Path) 변경을 찾는다.
3. 각 엔드포인트에 대해 아래를 정리한다:
   - Method, Path
   - Request 형태 (JSON body / query / path param)
   - Response 형태 (status code, 주요 필드)
   - 인증 필요 여부

## Step 2: 시나리오 구성

각 API에 대해 다음 시나리오를 구성한다.

1. **Happy Path** — 정상 입력 → 2xx 응답
2. **Required field 누락** — 필수 필드 빠뜨림 → 4xx
3. **타입 불일치** — 문자열 자리에 숫자 등 → 4xx
4. **권한 부족** — 토큰 없이 / 다른 권한으로 → 401/403
5. **존재하지 않는 리소스** — 잘못된 ID → 404
6. **Spec 엣지 케이스** — workflow Phase 0의 엣지 케이스 테이블 각 항목

`$ARGUMENTS` 에 엣지 케이스 ID가 있으면 해당 시나리오만 실행.

## Step 3: 인증 토큰 확보

프로젝트마다 방식이 다르므로 **profile/프로젝트에 정의된 방식**을 따른다. 순위:

1. 환경 변수 (`$E2E_AUTH_TOKEN` 등)가 있으면 사용
2. profile 본문에 토큰 발급 절차가 적혀 있으면 그에 따름
3. 프로젝트 `Makefile` 또는 `scripts/` 디렉토리에 토큰 발급 스크립트가 있으면 실행
4. 위 어느 것도 없으면 사용자에게 한 번 묻는다:
   > "E2E 테스트용 인증 토큰을 어떻게 발급받나요? 명령을 알려주거나 토큰을 직접 입력해 주세요."

입력받은 방법은 `projectNotes` 업데이트를 제안한다 (사용자 승인 시에만).

## Step 4: 서버 기동

`--skip-server`가 아니고 `runServerCommand` 가 있으면 백그라운드로 기동:

```bash
run_in_background:
  {runServerCommand}
```

기동 후 `serverUrl` 이 응답할 때까지 대기 (최대 30초). `curl -sf {serverUrl}/healthz` 또는 루트 경로에 대한 HEAD 요청으로 확인.

30초 내 응답이 없으면 로그를 읽고 실패 원인을 보고하고 `[SKIPPED:SERVER_START_FAIL]` 반환.

## Step 5: 요청 실행

각 시나리오에 대해:

```bash
curl -sS -o /tmp/be-harness-e2e-response.json \
  -w "HTTP %{http_code}\nTime %{time_total}s\n" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"  \  # 해당 시만
  -X {Method} \
  -d '{body json}' \
  "{serverUrl}{path}"
```

응답을 파일에 저장한 뒤 읽어서 검증한다.

### 응답 검증

| 검증 항목 | 방법 |
|----------|------|
| HTTP status | 기대값과 비교 |
| Content-Type | `application/json` 등 기대 타입 |
| 필수 필드 존재 | `jq`로 키 추출 후 null/빈 체크 (`jq`가 없으면 Python/Read로 파싱) |
| 값 제약 | ID 포맷, 범위, 길이 등 |
| 시간 | 500ms 초과 시 warn |

`apiDocsPath` 에 OpenAPI 스펙이 있으면 해당 엔드포인트의 response schema와 구조를 비교한다 (초과 필드 / 누락 필드). 스펙이 없으면 이 단계는 생략.

## Step 6: 서버 종료

Step 4에서 기동한 프로세스를 종료한다. `--skip-server`면 skip.

## Step 7: 리포트

```markdown
## E2E Test Report

### 환경
- serverUrl: {serverUrl}
- 실행 시나리오: N개
- 경과 시간: {total_time}

### 결과 요약
| # | 시나리오 | Method | Path | 기대 | 실제 | 판정 |
|---|----------|--------|------|------|------|------|
| 1 | Happy path | POST | /v1/users | 201 | 201 | PASS |
| 2 | Required field 누락 | POST | /v1/users | 400 | 500 | FAIL |

### 실패 상세
- 2번: 서버가 500을 반환. 로그 발췌: [...]

### 수정 제안
- [파일:라인, 제안 수정]
```

실패가 있으면 호출자(start-workflow 또는 e2e-test-loop)가 수정 루프를 돌 수 있도록 `"이슈: N건, 수정: Y/N"` 형식 요약을 마지막 줄에 포함한다.

## SKIP 조건

| 조건 | 반환 |
|------|------|
| profile 없음 | `[SKIPPED:NO_PROFILE]` |
| `e2eEnabled: false` | `[SKIPPED:DISABLED]` |
| `serverUrl` 없음 | `[SKIPPED:NO_SERVER_URL]` |
| `runServerCommand` 없고 `--skip-server`도 아님, 기존 서버도 응답 없음 | `[SKIPPED:NO_SERVER]` |
| 인증 토큰 확보 실패 | `[SKIPPED:NO_AUTH]` |
| 변경된 HTTP API 없음 | `[SKIPPED:NO_CHANGED_API]` |

SKIP은 오케스트레이터의 루프 재시작 트리거가 아니다.

## 주의사항

- DB 시드/정리는 **프로젝트의 기존 스크립트**를 그대로 호출한다. be-harness는 DB를 직접 조작하지 않는다.
- gRPC 테스트는 `grpcurl` 등 전용 도구가 필요하므로 이 스킬에서 다루지 않는다 (프로젝트에서 별도 스크립트로 처리).
- PubSub/큐 메시지 검증도 범위 밖이다.
