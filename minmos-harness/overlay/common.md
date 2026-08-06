<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness` 전체 (모든 스킬·에이전트 공통)

## Pre-flight 추가

베이스 Pre-flight 점검 표에 아래 행을 추가한다. 누락 항목이 있으면 **어떤 단계가 SKIP될 것인지 미리 확정**한다 (단계 내부에서 실패 후 판정하지 않는다).

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `secret/.env` | 파일 존재 확인 | E2E 관련 단계 SKIP 예정 — 서버 부팅/JWT 발급 불가 (`SKIPPED:ENV_MISSING`) |
| Apidog MCP 연결 | `mcp__apidog__read_project_oas_*` 패턴을 세션 도구 목록에서 탐색 후 실제 호출 | API 문서 동기화 단계 SKIP 예정 (`SKIPPED:APIDOG_MCP_UNAVAILABLE`) |
| PostgreSQL MCP 연결 | PostgreSQL MCP로 `SELECT 1` 실행 | E2E 부분 SKIP 예정 — DB 시드/정리 경로 제한 (`SKIPPED:POSTGRES_MCP_UNAVAILABLE`) |

> **MCP 판정 원칙**: 실제 MCP tool 호출 성공 = 연결 OK. `.mcp.json` 존재 여부는 단독 기준으로 쓰지 않는다. 판정의 canonical은 `/minmos-harness:doctor`.

누락 시 선택지 (베이스의 profile 누락 안내와 같은 자리에서 함께 제시):

> "⚠️ 환경 누락 감지: `{누락 항목}`. 이번 실행에서 **{영향받는 단계 목록}**는 SKIP됩니다.
> 1. 이대로 진행 — 해당 단계는 `SKIPPED:{사유}`로 기록하고 넘어감
> 2. 중단 — `/minmos-harness:doctor`로 진단 후 `/minmos-harness:init`으로 재설정 권장"

## 추가 규칙

- **로컬 DB 전용 원칙**: DB에 접근하는 모든 단계는 로컬 호스트 DB만 대상으로 한다. 원격 DB 호스트가 감지되면 화이트리스트 승인 없이는 실행하지 않고 `SKIPPED:REMOTE_DB_BLOCKED`로 기록한다. 상세: `references/db-safety.md`.
- **Language**: 유저와의 모든 대화는 한국어로 진행한다 (profile `language` 값과 무관하게 고정).

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/db-safety.md` | DB에 접근하는 단계 진입 시 |
| `references/postmath-conventions.md` | 컨벤션 검사·코드 작성 단계 |
