---
name: minmo-init-mm
description: "minmos-harness 플러그인의 모든 사전 세팅을 한 번에 진행한다."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

# minmos-harness Init

플러그인에서 사용하는 모든 외부 의존성을 한 번에 세팅한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## 세팅 대상

| # | 항목 | 관련 스킬 |
|---|------|----------|
| 1 | Apidog MCP 서버 | apidog-schema-gen, e2e-apidog-schema-gen, e2e-test |
| 2 | Apidog 환경 변수 (Push용) | apidog-schema-gen, e2e-apidog-schema-gen |
| 3 | PostgreSQL MCP 서버 | e2e-test, e2e-test-loop |
| 4 | db-tools 플러그인 | db-gen-committed |
| 5 | 컨벤션 선택 | convention-check |
| 6 | grpcurl (선택) | e2e-test (gRPC) |

---

## 실행 흐름

### Step 1: 현재 상태 스캔

먼저 모든 항목의 현재 상태를 조용히 점검한다:

- `.mcp.json` 읽기 → Apidog MCP, PostgreSQL MCP 등록 여부
- 환경 변수 확인 → `APIDOG_ACCESS_TOKEN`, `APIDOG_PROJECT_ID`
- `secret/.env` 존재 여부 → DB 접속 정보 추출 가능 여부
- db-tools 플러그인 설치 여부
- `.convention-check.json` 존재 여부

### Step 2: 상태 요약 보고

스캔 결과를 유저에게 보여준다:

```markdown
## minmos-harness 환경 스캔 결과

| # | 항목 | 상태 | 필요한 스킬 |
|---|------|------|-----------|
| 1 | Apidog MCP | OK / MISSING | apidog-schema-gen, e2e-test |
| 2 | APIDOG_ACCESS_TOKEN | SET / UNSET | apidog-schema-gen (Push) |
| 3 | APIDOG_PROJECT_ID | SET / UNSET | apidog-schema-gen (Push) |
| 4 | PostgreSQL MCP | OK / MISSING | e2e-test |
| 5 | secret/.env | OK / MISSING | e2e-test |
| 6 | db-tools 플러그인 | OK / MISSING | db-gen-committed |
| 7 | 컨벤션 설정 | OK / DEFAULT | convention-check |
| 8 | grpcurl | OK / MISSING | e2e-test (gRPC, 선택) |
```

### Step 2.5: 설정 가이드 / 세팅 선택

상태 요약 보고 후, 유저에게 다음 행동을 선택하게 한다:

> "어떻게 진행할까요?"
>
> **설정 가이드 보기** — 번호를 입력하면 해당 항목의 설정 방법을 안내합니다.
> **세팅 시작** — `all`을 입력하면 MISSING 항목을 순서대로 세팅합니다.
>
> 예: `1` (Apidog MCP 설정 방법 보기), `1,4` (복수 선택), `all` (바로 세팅 시작)

- **번호 입력 시**: 해당 항목의 설정 방법만 출력하고, 다시 선택 프롬프트로 돌아온다.
- **`all` 입력 시**: Step 3으로 진행하여 MISSING 항목을 순서대로 세팅한다.
- **`q` 입력 시**: init을 종료한다.

#### 설정 가이드 내용 (번호 선택 시 표시)

| # | 항목 | 가이드 요약 |
|---|------|-----------|
| 1 | Apidog MCP | Apidog 프로젝트 ID를 `.mcp.json`에 등록. ID는 Apidog 프로젝트 Settings에서 확인 |
| 2 | APIDOG_ACCESS_TOKEN | Apidog → Settings → API Access Token에서 생성 후 `export` |
| 3 | APIDOG_PROJECT_ID | Apidog 프로젝트 URL에서 확인 후 `export` |
| 4 | PostgreSQL MCP | DATABASE_URL을 `.mcp.json`에 등록. `secret/.env`에서 자동 추출 가능 |
| 5 | secret/.env | 프로젝트 담당자에게 요청하거나 `secret/.env.example`에서 복사 |
| 6 | db-tools 플러그인 | `/plugin marketplace add postmath-plugins/db-tools` 실행 |
| 7 | 컨벤션 설정 | 적용할 컨벤션을 선택하여 `.convention-check.json` 생성 |
| 8 | grpcurl | `grpcurl --version` 확인. 없으면 설치 안내 |

### Step 3: 세팅 진행

**MISSING인 항목만** 순서대로 세팅을 진행한다. 각 항목마다 유저에게 진행 여부를 확인한다.

#### 3.1 Apidog MCP (MISSING인 경우)

> "Apidog MCP를 설정합니다. Apidog 프로젝트 ID를 알려주세요:"

- 유저 입력을 받아 `.mcp.json`에 추가:
  ```json
  {
    "mcpServers": {
      "apidog": {
        "command": "npx",
        "args": ["-y", "apidog-mcp-server@latest", "--project-id=<ID>"]
      }
    }
  }
  ```
- `.mcp.json`이 없으면 새로 생성, 있으면 기존 내용에 병합

#### 3.2 Apidog 환경 변수 (UNSET인 경우)

> "Apidog Push 기능을 사용하려면 환경 변수가 필요합니다. 지금 설정할까요? (Y/건너뛰기)"

- Y: 토큰 입력 안내
  > "Apidog → Settings → API Access Token에서 토큰을 생성한 뒤 아래 명령을 실행하세요:"
  > ```
  > export APIDOG_ACCESS_TOKEN='your-token'
  > export APIDOG_PROJECT_ID='your-project-id'
  > ```
- 건너뛰기: Push 기능 없이 진행 가능하다고 안내

#### 3.3 PostgreSQL MCP (MISSING인 경우)

> "PostgreSQL MCP를 설정합니다."

1. `secret/.env`가 있으면 DB 접속 정보를 자동으로 읽어 DATABASE_URL을 구성하고 제안:
   > "secret/.env에서 DB 정보를 찾았습니다: `postgres://user:***@host:port/db`
   > 이 정보로 PostgreSQL MCP를 설정할까요?"
2. `secret/.env`가 없으면 직접 입력을 요청:
   > "DATABASE_URL을 입력해주세요 (예: `postgres://user:pass@localhost:5432/dbname`):"
3. `.mcp.json`에 추가:
   ```json
   {
     "mcpServers": {
       "postgres": {
         "command": "npx",
         "args": ["-y", "@anthropic/postgres-mcp", "<DATABASE_URL>"]
       }
     }
   }
   ```

#### 3.4 db-tools 플러그인 (MISSING인 경우)

> "db-tools 플러그인이 설치되어 있지 않습니다. 아래 명령으로 설치하세요:"
> ```
> claude plugin add postmath-plugins/db-tools
> ```

설치는 유저가 직접 해야 하므로 안내만 한다.

#### 3.6 grpcurl (MISSING인 경우, 선택)

> "gRPC E2E 테스트를 사용하려면 grpcurl이 필요합니다. 설치할까요? (Y/건너뛰기)"

- Y: 플랫폼별 설치 안내:
  > ```bash
  > # macOS
  > brew install grpcurl
  > # Linux (Go)
  > go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
  > # Linux (binary)
  > # https://github.com/fullstorydev/grpcurl/releases
  > ```
- 건너뛰기: REST 테스트만으로도 e2e-test 사용 가능하다고 안내.

#### 3.5 컨벤션 선택 (DEFAULT인 경우)

> "convention-check에서 사용할 컨벤션을 설정합니다.
> 어떤 컨벤션을 적용할까요? (복수 선택 가능, 쉼표 구분)"
>
> 1. `default-conventions` — 에러 처리, VO 패턴, 트랜잭션
> 2. `pagenation` — 커서 기반 페이지네이션
> 3. `CLAUDE.md` — 프로젝트 아키텍처 컨벤션
>
> 예: `1,2,3` (전체)

선택에 따라 `.convention-check.json`을 생성한다.

### Step 4: 최종 결과

```markdown
## Init 완료

| # | 항목 | 결과 |
|---|------|------|
| 1 | Apidog MCP | 설정 완료 / 이미 설정됨 / 건너뜀 |
| 2 | Apidog 환경 변수 | 안내 완료 / 이미 설정됨 / 건너뜀 |
| 3 | PostgreSQL MCP | 설정 완료 / 이미 설정됨 / 건너뜀 |
| 4 | db-tools 플러그인 | 안내 완료 / 이미 설치됨 |
| 5 | 컨벤션 선택 | 설정 완료 / 이미 설정됨 / 기본값 사용 |
| 6 | grpcurl | 설치됨 / 안내 완료 / 건너뜀 |

다음 단계: `/minmos-harness:minmo-doctor-mm`로 전체 상태를 검증하세요.
```
