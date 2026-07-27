---
name: e2e-test
description: "기능 추가/수정 후 연관 HTTP API를 실제 요청으로 E2E 테스트한다. 'API 실제로 테스트해줘', 구현 검증이 필요할 때 사용. profile의 runServerCommand/serverUrl 기반, Bash+curl만 사용."
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
argument-hint: <대상 API 설명 또는 엣지 케이스 ID>
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/e2e-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


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
- profile이 없으면 `SKIPPED:NO_PROFILE`, `e2eEnabled: false`면 `SKIPPED:DISABLED`를 반환하고 종료한다 (SKIP 조건 표 참조).

## 플래그

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--doctor` | | prerequisite 상태 진단 후 종료 |
| `--skip-server` | `-ss` | 서버 기동/종료를 건너뛰고 이미 떠있는 서버를 사용 |
| `--tag <id>` | | 특정 시나리오 ID(`EC-03`, `BASE-01` 등)만 실행 |

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

각 API에 대해 아래 시나리오를 구성하고, **모든 시나리오에 ID를 부여한다**. ID는 Step 7 리포트와 커버리지 판정의 대조 키다.

### 기본 시나리오 (`BASE-*`)

| ID | 시나리오 | 기대 |
|----|----------|------|
| `BASE-01` | Happy Path — 정상 입력 | 2xx |
| `BASE-02` | Required field 누락 | 4xx |
| `BASE-03` | 타입 불일치 (문자열 자리에 숫자 등) | 4xx |
| `BASE-04` | 권한 부족 (토큰 없이 / 다른 권한으로) | 401/403 |
| `BASE-05` | 존재하지 않는 리소스 (잘못된 ID) | 404 |

해당 API에 적용되지 않는 항목(예: 인증이 없는 공개 엔드포인트의 `BASE-04`)은 제외하고 사유를 리포트에 적는다.

### Spec 엣지 케이스 (`EC-*`)

Spec의 엣지 케이스 표(`/be-harness:request` Phase 4 산출물 — start-workflow에서 호출된 경우 상태 파일의 `## Edge Cases`, 단독 실행이면 사용자가 제공한 Spec)의 **각 행을 빠짐없이** 시나리오로 만든다.
**ID는 Spec의 `EC-nn`을 그대로 승계한다** — 새 번호를 붙이거나 순서를 바꾸지 않는다.

전수 매핑이 원칙이다. 물리적으로 실측 불가능한 케이스(외부 서비스 장애 유발, 동시성 재현 불가, 시간 경과 필요 등)만 예외로 두고, 실행 대신 `UNCOVERED:{사유}`로 리포트에 남긴다.
**"검증이 번거롭다", "코드를 보면 맞는 것 같다"는 예외 사유가 아니다.**

Spec에 엣지 케이스 표가 없거나 ID가 없으면(구버전 Spec) `EC-*` 매핑을 건너뛰고 기본 시나리오만 실행한다. 이 경우 리포트 커버리지 섹션에 `대조 기준 없음`으로 표기한다.

`$ARGUMENTS` 에 ID(`EC-03`, `BASE-01` 등)가 있으면 해당 시나리오만 실행한다.

## Step 3: 인증 토큰 확보

프로젝트마다 방식이 다르므로 **profile/프로젝트에 정의된 방식**을 따른다. 순위:

1. 환경 변수 (`$E2E_AUTH_TOKEN` 등)가 있으면 사용
2. profile 본문에 토큰 발급 절차가 적혀 있으면 그에 따름
3. 프로젝트 `Makefile` 또는 `scripts/` 디렉토리에 토큰 발급 스크립트가 있으면 실행
4. 위 어느 것도 없으면 사용자에게 한 번 묻는다:
   > "E2E 테스트용 인증 토큰을 어떻게 발급받나요?
   > 1. 발급 명령 입력 → 실행해 토큰 확보
   > 2. 토큰 직접 입력 → 그대로 사용
   > 3. 모름/제공 불가 → `SKIPPED:NO_AUTH` 반환 후 종료"

입력받은 방법은 `projectNotes` 업데이트를 제안한다 (사용자 승인 시에만).

## Step 4: 서버 기동

`--skip-server`가 아니고 `runServerCommand` 가 있으면 백그라운드로 기동:

```bash
run_in_background:
  {runServerCommand}
```

기동 후 `serverUrl` 이 응답할 때까지 대기 (최대 30초). `curl -sf {serverUrl}/healthz` 또는 루트 경로에 대한 HEAD 요청으로 확인.

30초 내 응답이 없으면 로그를 읽고 실패 원인을 보고하고 `SKIPPED:SERVER_START_FAIL` 반환.

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
| ID | 시나리오 | Method | Path | 기대 | 실제 | 판정 |
|----|----------|--------|------|------|------|------|
| BASE-01 | Happy path | POST | /v1/users | 201 | 201 | PASS |
| BASE-02 | Required field 누락 | POST | /v1/users | 400 | 500 | FAIL |
| EC-03 | 중복 이메일 가입 | POST | /v1/users | 409 | 409 | PASS |

### 커버리지
| Spec 엣지 케이스 | 대응 시나리오 | 상태 |
|-----------------|--------------|------|
| EC-01 | EC-01 | 실행됨 |
| EC-02 | — | `UNCOVERED:외부 결제사 타임아웃 재현 불가` |
| EC-03 | EC-03 | 실행됨 |

- Spec 엣지 케이스 [N]건 중 [M]건 실행, [K]건 미커버
- 판정: [PASS / WARN / FAIL]

### 실패 상세
- BASE-02: 서버가 500을 반환. 로그 발췌: [...]

### 수정 제안
- [파일:라인, 제안 수정]
```

### 판정 기준

| 판정 | 조건 |
|------|------|
| `PASS` | 시나리오 실패 0건 **AND** 미커버 0건 |
| `WARN` | 시나리오 실패 0건 **AND** 미커버 1건 이상 (사유가 명시된 것만) |
| `FAIL` | 시나리오 실패 1건 이상 |

미커버는 **구현 결함이 아니라 검증 공백**이므로 수정 루프의 트리거가 아니다. 사유와 함께 리포트에 남겨 호출자가 판단하게 한다.

실패가 있으면 호출자(start-workflow 또는 e2e-test-loop)가 수정 루프를 돌 수 있도록 `"이슈: N건, 수정: Y/N, 미커버: K건"` 형식 요약을 마지막 줄에 포함한다 (기존 파서 호환을 위해 앞의 두 필드 순서와 표기는 고정).

## SKIP 조건

| 조건 | 반환 |
|------|------|
| profile 없음 | `SKIPPED:NO_PROFILE` |
| `e2eEnabled: false` | `SKIPPED:DISABLED` |
| `serverUrl` 없음 | `SKIPPED:NO_SERVER_URL` |
| `runServerCommand` 없고 `--skip-server`도 아님, 기존 서버도 응답 없음 | `SKIPPED:NO_SERVER` |
| 인증 토큰 확보 실패 | `SKIPPED:NO_AUTH` |
| 변경된 HTTP API 없음 | `SKIPPED:NO_CHANGED_API` |

SKIP은 오케스트레이터의 루프 재시작 트리거가 아니다.

## 주의사항

- DB 시드/정리는 **프로젝트의 기존 스크립트**를 그대로 호출한다. be-harness는 DB를 직접 조작하지 않는다.
- gRPC 테스트는 `grpcurl` 등 전용 도구가 필요하므로 이 스킬에서 다루지 않는다 (프로젝트에서 별도 스크립트로 처리).
- PubSub/큐 메시지 검증도 범위 밖이다.
