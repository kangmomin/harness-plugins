# Writer 소유권·종료·범위

Codex write 호출과 그 폴백은 같은 소유권 계약을 쓴다. 핸들 유실·MCP 오류·timeout은 writer 종료 증거가 아니다. 상태가 불명확하면 원래 트리에서 새 writer/폴백/다음 쓰기 단계를 시작하지 않는다.

## 종료 증거

- dispatch 전 `{RUN_DIR}/writers/{호출ID}.json`의 receipt에 run_id, call_id(시도마다 고유), owner_id(실제 host/session), 배정 범위·CWD·시작 SHA를 기록한다. dispatch가 반환한 실제 job_id/핸들을 즉시 추가한다. job_id를 받기 전에 연결이 끊기면 같은 call_id가 포함된 호스트 작업 조회로 복원하며, 못 찾았다고 종료로 단정하지 않는다.
- 실제 local writer PID를 호스트가 제공할 때만 `writer_guard.py process {PID}`로 PID/boot_id/start_ticks를 receipt의 process에 보존한다. CLI launcher PID를 backend writer PID로 대체하지 않는다. PID만 비교하거나 재사용된 PID에 kill하지 않는다. Linux 이외에는 호스트의 작업 ID·종료 조회를 사용한다.
- 오류/대기 상한/재개 시 먼저 실행 소유 job을 조회한다. 살아 있으면 기다리거나 기존 권한 안에서 해당 작업의 stop을 요청한다. **stop 요청의 접수는 종료 확인이 아니다.** 실제 작업/하위 writer가 모두 종료됐다는 호스트 응답을 확인한다. 이를 제공하지 않는 환경이면 BLOCKED:WRITER_UNKNOWN을 유지한다.
- 종료 근거 JSON은 receipt와 같은 run_id/call_id/job_id/owner_id, status=`completed|failed|stopped`, writers_stopped=true, source=실제로 조회한 호스트 도구/이벤트 이름을 담는다. 런처 오류나 핸들 소실에서 이 값을 추론해서 만들지 않는다. raw 근거 경로/조회 시각도 receipt에 보존한다.
- `writer_guard.py check-stop`에 `{receipt:{…},evidence:{…}}`를 전달한다. STOP_CONFIRMED일 때만 재시도/이어서/폴백 상태 머신으로 진행한다. 실제 같은 PID가 살아 있거나 ID/근거가 불명확하면 BLOCKED다. PID가 사라진 것만으로도 충분하지 않다(자식/원격 writer가 남을 수 있음).
- `pending`은 STOP_CONFIRMED와 결과/변경 검증 완료 후에만 해소한다. 유실된 핸들 대신 null을 적되 행·receipt를 지우지 않는다. 과거 상태에 ID가 없으면 호스트 실행 이력에서 복구하거나 BLOCKED로 보고한다. 사용자 추가 정보 없이 해소할 수 없을 때만 그 실제 누락을 알린다.

helper는 읽기 전용 판정기다. evidence는 오케스트레이터가 실제 호스트 응답에서 만든 기록이며 위조를 막는 보안 토큰은 아니다. 살아 있는 실제 Codex/MCP 세션 종료의 통합 검증은 호스트별로 수행해야 한다.

## 병렬 slice 격리

1. 오케스트레이터는 각 writer에 실행 소유의 **별도 Git worktree/checkout**과 정확한 root-relative `allow_files`를 배정한다. 부모 작업 트리의 현재 tracked 내용과 명시된 구현 입력/실행 소유 새 파일을 반영한 같은 시작 snapshot을 사용하고 worker의 시작 commit SHA를 receipt에 저장한다. 부모 HEAD·index·사용자 변경은 바꾸지 않는다. 작업 트리 밖의 상태/Spec은 읽기 경로로만 전달한다.
2. 도구의 실제 cwd/sandbox writable root를 worker checkout으로 지정한다. worker CWD를 바꿀 수 없거나 스냅샷을 정확히 준비할 수 없으면 병렬 쓰기를 시작하지 않고, 기존 writer 종료 확인 뒤 한 명씩 순차 실행한다. 기본적으로 같은 CWD라는 이유로 병렬 쓰기를 강행하지 않는다.
3. writer는 배정 파일만 수정하고 Git commit/index·다른 checkout·공유 상태를 건드리지 않는다. shared artifact는 지정된 단일 owner만 수정한다. 종료 배리어 전에는 부모로 변경을 가져오지 않는다.
4. 종료가 확인되면 `writer_guard.py scope`에 `{cwd:worker절대경로,parent_cwd:부모root,start_sha:worker시작commit,allow_files:[…]}`를 전달한다. 시작 SHA부터의 tracked/index 변경과 **모든 nonignored 새 파일**을 검사한다. 범위 밖 경로/HEAD 이동은 BLOCKED:SLICE_SCOPE이며 patch 적용을 막는다. 부모 하위 디렉터리는 별도 checkout으로 인정하지 않는다.
5. 위반을 발견해도 다른 writer 파일을 자동으로 되돌리지 않는다. 위반 worker의 결과와 원본을 보존해 오케스트레이터가 해당 checkout에서만 해결하고 재검사한다. PASS의 tracked patch와 **new_files payload 둘 다** 부모 시작 내용과 대조해 오케스트레이터가 순차 반영한다. untracked 파일은 Git patch가 비어도 new_files에 path/bytes_base64/sha256/mode(링크는 target)가 있으므로 누락하지 않는다. 새 경로가 부모에 아직 없는지 확인하고 배정 경로에만 exclusive 생성하며 bytes hash와 실행 권한을 대조한다. symlink는 링크 자체를 검토·생성하고 대상을 따라 읽거나 쓰지 않는다. 새 파일·삭제·rename을 포함한 반영 목록이 scope.paths와 일치해야 한다. 충돌·사용자 동시 편집은 덮어쓰지 않는다. 모든 반영 뒤 부모에서 빌드/테스트/tree를 다시 검증한다.
6. 임시 worktree는 모든 소유 writer 종료와 반영/보고가 확인된 뒤에만 정상 제거한다. 강제 제거·reset으로 다른 작업을 정리하지 않는다. BLOCKED worker의 receipt와 checkout은 경로를 보고하고 보존한다.

Git worktree는 일반 경로의 우발적 교차 수정을 분리하지만 OS 보안 경계는 아니며 `.git` 객체/refs를 공유한다. helper는 ignored 빌드 산출물이나 Git 밖의 쓰기까지 전역 감시하지 않는다. 구현 소스를 ignored 경로에 쓰지 않고, 호스트가 제공하는 writable-root 제한을 함께 사용한다.
