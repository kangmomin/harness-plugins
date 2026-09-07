# 검증 결과 계약 v1

`assets/workflow_results.py`가 검증하는 JSON이 결과의 정본이다. Markdown의 Phase 번호·문장·첫 회귀 건수를 다시 파싱해 최종 성공을 만들지 않는다. 기존 Markdown만 입력한 아카이브는 `DEGRADED` 호환 출력이다.

상위 실행은 `{RESULTS_FILE}={RUN_DIR}/verification-results.json`을 사용한다. 독립 E2E 루프는 `{E2E_RUN_DIR}/e2e-results.json`을 사용하고, 상위 RUN_ID가 있으면 승계한다. 단독 루프는 E2E_LOCK_TOKEN을 RUN_ID로 사용한다. 파일은 저장소 밖 실행 디렉터리에 둔다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/workflow_results.py" init \
  --out "{RESULTS_FILE}" --run-id "{RUN_ID}" --domain "{be|fe|fs}" --mode "{build|analyze|verify}" --cwd "{CWD}"
```

오케스트레이터만 JSON을 순서대로 갱신한다. 하위 에이전트는 자기 결과 객체를 반환하고 공유 파일에 직접 쓰지 않는다. 기존 events/fixes를 덮거나 삭제하지 않는다. 검증 직전·직후 `tree --cwd "{CWD}"` 결과가 같아야 해당 실행의 `tested_tree`로 기록한다. 수정되면 새 iteration으로 재검증한다. head와 content_sha256은 실제 명령으로 얻으며 임의 값으로 채우지 않는다. 이 해시는 Git HEAD·worktree diff·untracked 파일 내용을 포함하므로 staging 여부만으로 검증 범위가 줄지 않는다.

## 필드

| 위치 | 필수 값 |
|------|---------|
| 루트 | `schema_version:1`, `run_id`, `domain:be/fe/fs`, `mode:build/analyze/verify`, `terminal_state`, `tested_tree`, `targets:[]`, `cases:[]`, `events:[]`, `fixes:[]` |
| tested_tree | `head`, `content_sha256` — `tree` 출력 그대로 |
| target | `target_id`, `protocol:HTTP/GRPC/기타`, `operation`, `supported:boolean`; false면 `reason` |
| case | `case_id`, `target_id`, `category`, `name` — 실행 중 ID 불변; FS는 BE/FE 접두사로 충돌 방지 |
| event 공통 | `domain`, `kind`, `phase`, `iteration`(1부터), `verdict`, `terminal_state`, `tested_tree` |
| event kind | `unit`, `e2e`, `readback`, `lint`, `typecheck`, `build`, `pr` |
| event verdict | `PASS`, `WARN`, `FAIL`, `INCONCLUSIVE`, `PARTIAL`, `SKIPPED` |
| unit event | `regression_count` 필수. `case_id`는 없음/null |
| e2e event | `case_id`, `protocol`, `request`, `expected`, `actual`, `server_contact:boolean`, `client_error:boolean` |
| GRPC event | `streaming:unary/server/client/bidi`, `deadline`, `status_origin:server/client/unknown/none`, 관측 `observed_status`; server 기원 증거가 있을 때만 `server_status`; 그 외 `reason`에 미호출/지원 범위를 기록 |
| fix | `domain`, `phase`, `iteration`, `case_id`, `cause`, `change`, `attribution`, `rebuild` |
| e2e 요약 | `e2e:{level:smoke/full,main_flow,unresolved:[],uncovered:[],smoke_omitted:[],stop_reason}` — 세 목록은 문자열 배열 |

HTTP operation은 `GET /healthz`처럼 method+경로다. GRPC operation은 `package.Service/Method`다. 미지원 RPC도 targets/cases에 남기고 supported:false와 사유를 기록한다. 호출하지 않은 대상은 PASS 사례가 없더라도 분모에서 제거하지 않는다.

이벤트 키는 `(domain, kind, case_id, iteration)`이다. 같은 키의 중복·서로 다른 결과는 거부한다. fix는 해당 phase·iteration·case_id의 **FAIL**에만 연결한다. 모든 케이스를 기록한 뒤 fix를 추가해도 귀속은 같다. 최종 결과는 각 `(domain,kind,case_id)`의 가장 큰 iteration에서 판정·회귀 수를 함께 선택한다. Read-back WARN은 unit 테스트 판정을 대체하지 않는다.

PASS는 event terminal_state:DONE과 일치해야 한다. E2E PASS는 지원하는 프로토콜의 실제 서버 호출 증거가 필요하다. `client_error`는 서버 호출 전 요청 구성/파싱 오류를 뜻한다. 호출 후 로컬 deadline은 server_contact:true일 수 있지만 status_origin:client이며 server_status는 null이다. `grpcurl` JSON 파싱 오류는 client_error:true/server_contact:false이며 서버 validation 통과로 바꾸지 않는다. 완료된 실행의 마지막 PASS가 다른 tested_tree를 가리키면 거부한다.

## 소비와 마감

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/start-workflow/assets/workflow_results.py" validate "{RESULTS_FILE}" --run-id "{RUN_ID}"
```

각 검증 완료 후 이 검사를 수행한다. 오류는 기록을 고쳐 해결하거나 `BLOCKED:RESULT_CONTRACT`로 보고한다. 기존 실패를 지워 검사를 통과시키지 않는다. 최종 보고 시점의 본문 표도 이 결과 객체에서 작성한다.

E2E renderer의 입력은 E2E 결과 JSON이며 `--run-id`, `--level`, `--status`가 기록과 같아야 한다. 전체 아카이브에는 `--results "{RESULTS_FILE}"`을 전달한다. 아카이브는 미완료 결과를 DONE으로 바꾸지 않으며, 같은 RUN_ID의 재시도는 저장된 `archive_status`와 진단을 유지한다. 이후 수정이 필요하면 live 결과를 계속 보존하고 필수 검증을 마친 뒤 아카이브한다.

스크립트가 실패하면 기존 원문·JSON의 경로와 실패 이유를 그대로 보고하고 보관한다. 예상 영구 경로로 `cp`, `cat >`, replace 폴백을 수행하지 않는다. 미지원 원자 생성 API에서도 기존 보고서를 덮지 않는다. `.workflow-archive.lock`은 프로세스 종료로 해제되는 협력 잠금 파일이며 삭제해 잠금을 풀지 않는다.

`check-current FILE --run-id ID --cwd DIR [--require KIND …]`는 RUNNING 상태에서도 최신 이벤트와 현재 tested tree의 일치를 검사한다. PR 직전의 freshness gate이며 기존 verdict/필수 케이스 정책을 대체하지 않는다. 코드 수정 후 과거 PASS의 tree만 바꾸지 말고 새 검증 이벤트를 기록한다.
