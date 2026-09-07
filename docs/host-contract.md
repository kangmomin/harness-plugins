# 호스트 계약 검증

현재 관찰: Claude Code **2.1.261**, Codex CLI **0.153.4**, Linux. 버전 숫자는 이 검증 실행의 관찰값이며 지원 최저 버전이나 미래 버전 보장이 아니다.

## Claude agent loader

[실측 metadata](../tests/fixtures/host-contract/observed.json)는 실제 plugin의 14개 agent를 로드하고 Agent 도구로 위임한 하위 요청에서 도구 이름을 수집한 결과다. 모델 응답은 loopback HTTP mock이 반환했다. 외부 모델·계정·MCP·파일 도구 호출은 없다. 로컬 CLI가 출력한 비용 추정치는 실제 과금 기록이 아니다.

- 읽기 전용 9개: Read/Glob/Grep만 실제 요청에 포함.
- 구현·PR·문서 동기화 5개: Bash와 파일 쓰기 권한 보유. PR과 문서 동기화는 Skill 사용 가능.
- 구 `allowed-tools`만 쓴 음성 대조군은 Bash/Write/Edit를 상속. 정적 YAML 검사만 통과시킨 결과와 구분한다.
- 기본 tool pool은 일부 역할에서 Glob/Grep을 노출하지 않을 수 있다. writer는 Bash로 조회할 수 있으나 읽기 전용 reviewer는 Bash를 허용하지 않는다.

재현은 설치된 Claude CLI가 있을 때 명시적으로 실행한다. 출력은 기존 파일을 덮지 않는 새 경로로 지정한다.

```bash
python3 -B tests/fixtures/host-contract/claude_loader_smoke.py --output /tmp/host-observation-new.json
```

probe는 비밀 없는 env, 임시 CLAUDE_CONFIG_DIR, 비활성 hooks, 빈 strict MCP, dummy key, loopback base URL을 사용한다. `--bare`는 이 버전에서 Agent/Write 도구까지 제거해 위임 검증이 불가능하므로 사용하지 않는다. 고유 하위 prompt marker와 성공한 Agent 결과를 함께 검증하며 예상 밖 요청을 거부한다. stdout에는 agent/tool metadata만 출력하고 임시 설정과 HTTP 서버를 정리한다.

`claude agents --json`은 이 버전에서 실행 세션 목록이다. agent 도구 목록 조회 명령으로 안내하지 않는다. SDK AgentInfo 역시 name/description/model만 제공한다. [공식 SDK 타입](https://code.claude.com/docs/en/agent-sdk/typescript#agentinfo)

배포 전 `python3 -B scripts/agent_contract.py`로 agent 전용 frontmatter를 검사한다. SKILL.md의 allowed-tools까지 agent 필드로 바꾸지 않는다. 호스트 업그레이드 시 실제 probe를 새 artifact로 재실행하고, 읽기 전용 역할에 도구가 추가되면 검증 실패로 취급한다.

## Codex와 MCP

이 저장소의 native Codex manifest는 work-log에 있다. 다른 harness 배포판의 Codex 지원을 이 결과로 보장하지 않는다. 현재 세션의 실제 스킬 metadata와 도구 이름을 발견한 뒤 사용하며 Claude Agent/Skill/Bash 이름을 Codex 도구명으로 가정하지 않는다.

work-log의 `tests/mcp-smoke.test.js`는 실제 stdio 서버를 초기화하고 tools/list와 읽기·쓰기·인덱싱 상태를 검증한다. Apidog 동적 도구 발견은 `test_apidog_contract.py`, 활성 framework/runner 및 codexMode별 의존성은 `test_doctor.py`로 검증한다. 실제 업무 MCP 연결이나 Apidog import를 실행했다는 뜻은 아니다. 진단 중 다운로드는 없으며, 누락된 의존성의 설치는 별도 실행이다.
