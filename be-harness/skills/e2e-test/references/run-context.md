# E2E 실행 컨텍스트

E2E 스킬/루프의 실제 실행 진입 시 한 번 수행한다 (`--doctor`·환경 SKIP 제외). 워크플로우가 전달한 `{RUN_DIR}`이 있으면 그 절대 경로를 `{E2E_PARENT_DIR}`로, 단독 실행이면 `${TMPDIR:-/tmp}`를 사용한다.

```bash
E2E_RUN_DIR=$(mktemp -d "{E2E_PARENT_DIR}/harness-e2e.XXXXXXXX")
E2E_LOCK_TOKEN=$(basename "$E2E_RUN_DIR")
```

생성 실패 시 `BLOCKED:LOCK_UNAVAILABLE`로 종료한다. 두 값을 호출 컨텍스트에 보관하고, 이후 별도 Bash 호출에도 **같은 실제 값**을 전달한다. 응답·서버 바이너리·로그·원시 리포트는 `{E2E_RUN_DIR}` 아래에 둔다.
상위 E2E 루프가 두 값을 명시적으로 전달한 **순차 하위 호출**만 재사용한다. 독립 E2E 호출·병렬 BE/FE 실행은 각각 새 디렉토리와 토큰을 만든다. uid·serverUrl로 토큰을 찾거나 전역 환경의 이전 값을 재사용하지 않는다.
같은 미완료 E2E 실행을 계속할 때만 보관한 값을 재사용한다. 경로/토큰을 잃었으면 소유자로 가장하지 말고 새 실행으로 락을 기다린다.

락 스크립트의 `acquire`·`beat`·`release`에 `--token "{E2E_LOCK_TOKEN}"`을 항상 전달한다. profile의 `e2eLockDir`이 있으면 **status 포함 모든 호출**에 `HARNESS_E2E_LOCK_DIR="{e2eLockDir}"`을 동일하게 전달한다. 없으면 실행 중 변하지 않는 기본값을 쓴다.
토큰은 이번 실행의 소유권 ID다 (인증 비밀이 아님). `--no-lock`이어도 응답·리포트 경로 격리는 유지한다.
서버는 이번 실행이 시작한 PID/세션 핸들로만 종료한다. 정리는 모든 프로세스 종료 후 이번 `{E2E_RUN_DIR}`만 대상으로 하며, 생성 리포트는 상위 호출자에게 실제 경로를 전달한다.
