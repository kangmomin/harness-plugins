---
name: doctor
description: "work-log 플러그인 상태를 진단한다. MCP 연결·스코프 설정·인덱스 신선도를 점검. '진단해줘', 'work-log 왜 안 돼', 검색이 실패하거나 설정이 의심될 때 사용."
allowed-tools: Bash, Read
---

# work-log Doctor

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:doctor`, Codex에서는 `$work-log:doctor` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 `wiki_` 로 시작하는 기본 이름을 기준으로 찾는다.

## 판정 원칙

**실제 MCP 툴 호출 성공이 유일한 연결 판정 기준이다.**
`.mcp.json` 존재 여부는 설정 안내용 참고 자료일 뿐 단독 근거로 쓰지 않는다
(클라이언트에 따라 MCP 설정 위치가 다르다).

## Step 1: MCP 프로브

기본 이름이 `wiki_status` 인 MCP 툴을 호출한다. 이 한 번의 호출이 대부분을 진단한다.


| 결과 | 판정 |
|------|------|
| 응답 옴 | MCP **OK** |
| 툴 자체가 없음 | MCP **MISSING** → Step 4 |
| 응답에 `needsInit: true` | MCP OK, 스코프 **미설정** → init 스킬 안내 |

## Step 2: 응답 해석

| 필드 | 점검 |
|------|------|
| `scope` / `root` | 의도한 vault를 가리키는가. 구조화된 전역 vault는 전체 root를 유지하는가 |
| `server` | 새 project/category 기능은 0.3.2부터 지원. 소스 수정만으로 설치본이 갱신됐다고 판단하지 않는다 |
| `configSource` | 어느 설정이 이겼는가 — 환경변수 / 프로젝트 / XDG 전역 / legacy 설정 |
| `cwd` | MCP 서버의 작업 디렉토리. 프로젝트 스코프 자동 탐지가 되는지 판단하는 근거 |
| `indexExists` | false 면 sync 스킬 필요 |
| `indexAgeSeconds` | 24시간(86400) 초과면 "오래됨" 경고 + sync 권장 |
| `counts` | 문서 수가 예상과 크게 다르면 excludes 설정 확인 |
| `indexState` / `errors` | `INDEX_*`면 재생성 필요, `DEGRADED`면 경로별 읽기/파싱 오류를 먼저 해결한다 |
| `safeIO` | `available:false`면 이유를 보고하고 Python 3.9+/Linux·macOS API를 점검한다. 캐시 읽기와 쓰기/sync 지원을 구별한다 |
| `scan` | 읽은 파일·bytes·소요 ms·오류 수. 실행별 규모와 시간을 함께 비교한다 |

### cwd 해석 (중요)

`configSource` 가 `.work-log.json` 경로면 walk-up 탐지가 **동작 중**이다.
`cwd` 가 현재 프로젝트와 무관한 경로인데 프로젝트 스코프를 쓰고 싶다면 다음처럼 처리한다.

- 실제 프로젝트 절대경로를 먼저 확인한다. 미등록 checkout/worktree는 최초 init을 안내한다.
- Claude Code: 프로젝트 `.mcp.json` 의 `WORK_LOG_ROOT` 에 **최종 프로젝트 root** 절대경로를 넣도록 안내한다(중앙 base가 아님).
- Codex: `WORK_LOG_ROOT="<최종 프로젝트 root 절대경로>" codex` 로 실행해 번들 MCP에 전달한다.
- env가 프로젝트 config보다 우선한다. 기존 env가 다른 root면 변경/해제를 승인받아 안내하고, 프로젝트 전환 시에도 root를 바꾸고 재시작한다.
- 재시작 후 `wiki_status.root` 가 의도한 root와 일치하기 전까지 미완료다. 검색·쓰기·sync를 실행하지 않는다.
- 기존 flat root로의 전환을 명시적으로 승인받았다면 CLI에도 같은 `WORK_LOG_ROOT` 를 전달하고, `cfg.root`·`wiki_status.root`·승인한 root가 같을 때 기존 checkout 설정과의 차이를 허용한다. 승인 없는 env 불일치는 허용하지 않는다.
- 같은 분류형 전역 vault 또는 기존 flat vault를 함께 읽는 경우에는 중립 전역 설정을 사용한다.
  분류형 전역 root를 프로젝트 하위 폴더로 바꾸면 공유·다른 프로젝트 자료가 가려진다.

## Step 3: 스킬 관점 점검 (Bash)

```bash
node "<plugin-root>/mcp/lib/config.js"
```

`<plugin-root>` 는 이 `SKILL.md` 의 `../..` 설치 경로다. 클라이언트가 `PLUGIN_ROOT` 또는
`CLAUDE_PLUGIN_ROOT` 를 제공하면 그 값을 쓸 수 있다.
위 명령은 확인한 **실제 프로젝트 디렉토리**에서 실행한다. `cfg.root` 와 MCP의
`wiki_status.root` 가 **같아야 한다**. 스코프 라벨보다 실제 root의 canonical realpath를 비교하며,
fallback이 `scope: global` 로 표시된다는 이유만으로 실패로 보지 않는다. 다르면 cwd 차이뿐
아니라 env 우선순위·설정 출처·재시작 여부도 점검한다. env가 의도와 다른 프로젝트로 고정되어
있으면 root 일치만으로 정상이라 하지 말고 실제 checkout `.work-log.json` 의 root도 확인한다.
중앙 모드의 예상 경로는 init의 `--project-vault`·`--project-dir` read-only helper로 확인한다.
상위 중앙 vault로 자동 검색 확장하거나 기존 flat 이력을 자동 이동하지 않는다.
옛 이력이 새 프로젝트 검색에 안 나오는 것은 정상이며 필요하면 명시적으로 flat root를 선택한다.

### 분류형 vault · 버전 확인

전역 분류형 구조는 root를 유지한 채 project/category 필터로 검색한다. 기존 독립 프로젝트 root에
현재 전역 root를 자동 덮어쓰지 않는다. `wiki_status.server`가 0.3.1이면 새 필터·Properties 기본값은
미적용이다. 소스 버전과 실행 버전을 구분한다. GitHub marketplace의 update는 미커밋 로컬 소스를
배포하지 않으며 cache 수동 편집은 금지한다. Claude 로컬 개발본은 지원되는 `--plugin-dir`로
새 세션을 시작하고, 같은 vault의 구버전 서버를 종료한 뒤 버전·root 확인과 sync를 수행한다.
Codex는 지원되는 소스 설치/연결 절차를 확인하고 재시작을 안내한다. 확인 전에는 완료로 보고하지 않는다.

## Step 4: MCP 미연결 시

1. `node --version` 으로 Node 18 이상인지 확인 (캐시 읽기용 서버). 쓰기/sync는 `python3 -I -B "<plugin-root>/mcp/lib/io_worker.py" --probe`로 진단한다. 진단 중 패키지를 다운로드하지 않는다
2. 서버를 직접 실행해 응답을 확인:
   ```bash
   printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
     | node "<plugin-root>/mcp/server.js"
   ```
   툴 5개가 나오면 서버는 정상이고 **클라이언트 배선 문제**다
3. 플러그인 설치 여부와 현재 클라이언트 재시작 필요 여부를 안내한다
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
| 안전한 쓰기/sync | available / unavailable | Python >=3.9, Linux/macOS; safeIO.reason |

권장 조치: ...
```
