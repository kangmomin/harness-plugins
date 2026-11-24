# CodeAct(Code Mode) 적용 검토 (#27)

결론: **이번에는 구현하지 않는다.** 현재 mod 는 Code Mode 에서도 그대로 동작한다. 적용 후보와 보류 이유를 남긴다.

기준: Claude Code 2.1.331 의 plugin API 타입(`plugin-authoring` 스킬의 `claude-code.d.ts`).

## 1. 무엇인가

- CodeAct: 모델이 도구를 하나씩 부르지 않고, **코드(스크립트)로 여러 도구 호출을 묶어 실행**하는 방식.
- Claude Code 에서는 **Code Mode** 가 이 방식이다. 세션 opt-in 기능이며, 모델이 `REPL` 도구로 스크립트를 실행하고 스크립트가 도구를 호출한다.

## 2. 현재 mod 에 주는 영향

| 항목 | Code Mode 에서 | 판정 |
|------|----------------|------|
| common 진행 표시 (`session.append` 감시) | 모델의 `Bash` tool_use 행과 그 tool_result 행으로 `workflow_run.py create/resume` 를 감지한다. 스크립트 안에서 부른 Bash 는 대화 행에 `Bash` tool_use 로 남지 않는다 (`REPL` 행 하나만 남는다) | **한계**: 스크립트 안에서 실행을 만들면 band 가 뜨지 않는다. 상태 파일·워크플로우 동작에는 영향 없음 |
| 상태 파일 갱신 감지 | tool_result 행이 올 때마다 상태 파일을 다시 읽는다. `REPL` 결과 행도 tool_result 이므로 갱신된다 | 영향 없음 |
| `tool.call` hook | 쓰지 않는다. `tool.call` hook 이 매칭되면 그 도구의 백그라운드 전환·실시간 출력·Code Mode 의 "중지된 결과 대기"가 꺼진다. 그래서 진행 표시는 저장되는 행만 읽는다 | 영향 없음 |
| `tool.list` | Code Mode 의 자체 도구(`REPL` 등)는 `next(e)` 에서 빠지고 제거할 수 없다 | 사용 안 함 |

> 첫 행의 한계를 없애려면 `{ tool: "REPL" }` 결과 행에서 JSON 을 찾는 처리를 더한다. Code Mode 가 opt-in 인 동안은 보류한다.

## 3. 적용 후보 (보류)

### A. 반복 python 호출을 mod 도구로 노출

- 대상: `workflow_run.py`(create·resume), `harness_config.py`(resolve), `profile.py`(resolve·edit).
- 방법: `$.tool.register` 로 `mcp__<plugin>__workflow_run` 같은 도구를 등록하고 `tool.run` 에서 `$.process.run` 으로 실행한다.
- 장점: 모델이 셸 인용·경로를 만들 필요가 없다. 입력이 JSON 스키마로 고정된다. Code Mode 스크립트에서 함수처럼 부를 수 있다.
- 보류 이유:
  - 스킬 문서가 Bash 명령을 정본으로 쓴다. Codex 등 mod 가 없는 호스트에서도 같은 스킬이 동작해야 한다. 도구로 바꾸면 경로가 2개가 된다.
  - `profile.py`·`workflow_run.py` 는 POSIX 전용(`fcntl`)이다. 도구로 감싸도 Windows 문제는 남는다.
  - 등록 도구는 기본적으로 ToolSearch 뒤에 있다. 항상 보이게 하면(`isDeferred: false`) 모든 요청의 프롬프트가 커진다.

### B. 품질 루프를 스크립트 1개로 실행

- lint → build → test 를 Code Mode 스크립트로 묶어 왕복 횟수를 줄이는 안.
- 보류 이유: 품질 루프는 단계마다 판정·기록(`RESULTS_FILE`)·실패 분기가 있다. 스크립트로 묶으면 단계별 근거 기록 계약(`result-contract.md`)과 충돌한다. Code Mode 는 opt-in 이라 모든 사용자에게 같은 동작을 보장할 수 없다.

## 4. 다시 볼 조건

- Code Mode 가 기본값이 되었을 때.
- 스킬이 mod 전용 호스트(Claude Code)만 지원하게 되었을 때.
- `profile.py`·`workflow_run.py` 가 Windows 를 지원하게 되었을 때 (A 안의 실익이 커진다).
