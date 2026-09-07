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

## 실제 점유 자원과 잠금 v2

락 키 입력은 클라이언트 URL 대신 **실제 bind 주소와 port**인 `{E2E_BIND_ENDPOINT}`다. 기동 설정/코드에서 listener 주소를 확인한다. 주소를 확정할 수 없지만 포트가 확인되면 `[::]:{port}`로 두 주소 계열을 보수적으로 예약하고 그 사유를 기록한다. 외부 서버(`--skip-server`)는 확인한 대상 주소를 사용하되, 서로 다른 client namespace 사이의 원격 서버/DB 상호 배제까지 이 로컬 socket 잠금이 보장하지 않는다.

기본 root는 `/tmp/harness-e2e-locks`이며 WORK_LOG_ROOT·work-log 설정·프로젝트 cwd에 따라 바뀌지 않는다. profile의 e2eLockDir을 쓰면 같은 실제 자원에 접근하는 모든 실행에서 동일한 절대 경로를 사용해야 한다. 별도 root는 독립 잠금 영역이므로 저장소마다 다른 경로로 지정하지 않는다.

스크립트는 Linux의 실제 network namespace inode(macOS는 host 범위), TCP port, 해석한 주소 집합을 사용한다. localhost·IPv4-mapped IPv6와 IPv4 별칭의 겹침, wildcard 주소와 구체 주소의 겹침을 검사한다. HTTP/HTTPS의 생략 포트는 80/443이다. bare host/gRPC는 port가 필수다. IPv6 wildcard는 dual-stack 가능성을 고려해 IPv4도 예약한다.

`ACQUIRED`/`ALREADY_HELD` 출력의 `key=resource:{hash}`를 `{E2E_RESOURCE_KEY}`로 보관한다. 이후 beat/release는 이 값을 사용해 DNS 변화로 다른 lease를 만지지 않는다. 키를 셸 코드로 eval하지 않는다. REST와 gRPC가 별도 포트이면 각각 획득하고 획득한 모든 키를 같은 토큰으로 heartbeat/release한다. 여러 포트의 획득 순서는 정렬해 고정하고, 하나가 실패하면 앞서 획득한 자기 lease를 해제한 뒤 기동을 중단한다.

잠금 v2는 Python 3.9+/POSIX를 사용한다. 업그레이드 전에 같은 자원의 v1 E2E 실행을 모두 종료한다. 메타데이터 guard는 kernel flock으로 짧게 보호하며 `.metadata.lock`을 삭제해 풀지 않는다. E2E 실행 lease는 여러 툴 프로세스에 걸친 heartbeat+TTL 계약을 유지하므로 heartbeat 실패 후 기존 실행이 계속 쓰기를 수행하면 안 된다. TTL을 프로세스 사망 증거로 해석하지 않는다.
