---
name: doctor
description: "work-log 플러그인 상태를 진단한다. MCP 연결·스코프 설정·인덱스 신선도를 점검. '진단해줘', 'work-log 왜 안 돼', 검색이 실패하거나 설정이 의심될 때 사용."
allowed-tools: Bash, Read
user-invocable: true
---

# work-log Doctor

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## 판정 원칙

**실제 MCP 툴 호출 성공이 유일한 연결 판정 기준이다.**
`.mcp.json` 존재 여부는 설정 안내용 참고 자료일 뿐 단독 근거로 쓰지 않는다
(클라이언트에 따라 MCP 설정 위치가 다르다).

## Step 1: MCP 프로브

`mcp__plugin_work-log_work-log__wiki_status` 를 호출한다. 이 한 번의 호출이 대부분을 진단한다.

> **툴 이름 주의**: 접두사 `mcp__plugin_work-log_work-log__` 는 `/mcp` 목록 기준이다.
> 목록에 다르게 보이면 **`wiki_` 로 시작하는 이름의 툴**을 찾아 그것을 호출한다.
> 접두사가 달라도 스킬 절차는 동일하다.


| 결과 | 판정 |
|------|------|
| 응답 옴 | MCP **OK** |
| 툴 자체가 없음 | MCP **MISSING** → Step 4 |
| 응답에 `needsInit: true` | MCP OK, 스코프 **미설정** → `/work-log:init` 안내 |

## Step 2: 응답 해석

| 필드 | 점검 |
|------|------|
| `scope` / `root` | 의도한 vault 를 가리키는가 |
| `configSource` | 어느 설정이 이겼는가 — `env:WORK_LOG_ROOT` / `.work-log.json` 경로 / 전역 설정 |
| `cwd` | MCP 서버의 작업 디렉토리. 프로젝트 스코프 자동 탐지가 되는지 판단하는 근거 |
| `indexExists` | false 면 `/work-log:sync` 필요 |
| `indexAgeSeconds` | 24시간(86400) 초과면 "오래됨" 경고 + sync 권장 |
| `counts` | 문서 수가 예상과 크게 다르면 excludes 설정 확인 |

### cwd 해석 (중요)

`configSource` 가 `.work-log.json` 경로면 walk-up 탐지가 **동작 중**이다.
`cwd` 가 현재 프로젝트와 무관한 경로인데 프로젝트 스코프를 쓰고 싶다면,
`WORK_LOG_ROOT` 절대경로를 프로젝트 `.mcp.json` 에 넣는 방식으로 전환해야 한다.
`/work-log:init` 이 이 설정을 대신 해 준다.

## Step 3: 스킬 관점 점검 (Bash)

```bash
node ${CLAUDE_PLUGIN_ROOT}/mcp/lib/config.js
```

스킬이 보는 스코프와 MCP 가 보는 스코프가 **같아야 한다**. 다르면 cwd 차이가 원인이다.
같은 모듈을 쓰므로 값이 다르다면 실행 위치가 다른 것이다.

## Step 4: MCP 미연결 시

1. `node --version` 으로 Node 18 이상인지 확인 (내장 모듈만 쓰므로 설치할 의존성은 없다)
2. 서버를 직접 실행해 응답을 확인:
   ```bash
   printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
     | node ${CLAUDE_PLUGIN_ROOT}/mcp/server.js
   ```
   툴 5개가 나오면 서버는 정상이고 **클라이언트 배선 문제**다
3. 플러그인 설치 여부와 Claude Code 재시작 필요 여부를 안내한다
   (MCP 서버는 설정 변경 후 재시작해야 반영된다)

## Step 5: 보고

```
## work-log 진단

| 항목 | 상태 | 비고 |
|------|------|------|
| MCP 서버 | OK / MISSING | |
| 스코프 | global / project / 미설정 | root 경로 |
| 설정 출처 | | configSource |
| 인덱스 | 있음(N분 전) / 없음 | 문서 수 |
| Node | v24.x | >=18 필요 |

권장 조치: ...
```
