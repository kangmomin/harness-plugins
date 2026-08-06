<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:e2e-test-loop`

베이스가 이미 정직한 자기 점검 HTML 리포트를 생성한다. 오버레이는 **Post-Math 환경 probe**만 보강한다.

## Pre-flight 추가

베이스 Step 1(Pre-flight Probe)의 점검 표에 아래 행을 추가한다. `--skip-doctor` / `-sd` 지정 시 함께 건너뛴다.

| 점검 항목 | 확인 방법 | 실패 시 |
|----------|----------|--------|
| `secret/.env` | 파일 존재 | `SKIPPED:ENV_MISSING` |
| PostgreSQL MCP 연결 | `SELECT 1` 실행 성공 | `SKIPPED:POSTGRES_MCP_UNAVAILABLE` |
| DB 호스트가 로컬 | 연결 문자열 호스트 검사 | `SKIPPED:REMOTE_DB_BLOCKED` |

SKIP 종료 시 복구 안내 문구를 아래로 치환한다:

> 복구 방법: `/minmos-harness:init` 으로 환경 재설정, 또는 `/minmos-harness:doctor` 로 진단

## 스킬 치환 매핑

| 베이스가 호출하는 것 | 적용할 오버레이 |
|---------------------|----------------|
| `/be-harness:e2e-test` | `overlay/e2e-test.md` |

## 추가 규칙

- 리포트 케이스 블록의 `{분류}` 에 gRPC 케이스가 포함되면 status를 **gRPC code**로 표기한다.
- `{REPORT_DIR}` 는 베이스 기본값(`.claude/harness-reports`) 대신 profile의 `reportDir` 설정을 우선한다. Post-Math 프로젝트는 보통 저장소 밖 작업 로그 디렉토리를 쓰므로 `/minmos-harness:init` 이 이 값을 설정한다.

절차·루프 상한·HTML 렌더링 규칙은 **베이스를 그대로 따른다.**
