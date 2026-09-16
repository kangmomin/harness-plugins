# Scope 리뷰 근거와 마감

BE Phase 8.4의 입력·결과 계약이다. 코드 판정과 근거 완료를 별도로 기록하며 읽기 전용 역할의 권한을 확대하지 않는다. Phase 8.8 Read-back에는 이 문서의 Spec·상태·결과 artifact를 전달하지 않는다.

## 호출 전: 변경 자료를 실제 파일로 제공

모든 writer가 종료된 Batch A 시작점에서 오케스트레이터가 [scope-contract.md](scope-contract.md)의 START_SHA·OWNED_FILES로 수집한다. REVIEW_ATTEMPT는 같은 RUN 안에서 증가시키며 기존 디렉터리를 재사용하지 않는다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_scope.py" \
  --cwd "{CWD}" --start-sha "{START_SHA}" --owned-files "{OWNED_FILES}" \
  --patch-dir "{RUN_DIR}/scope-{REVIEW_ATTEMPT}" \
  --out "{RUN_DIR}/scope-{REVIEW_ATTEMPT}/scope.json"
```

exit 0인 이번 수집만 사용한다. JSON의 root/start_sha/head/content_sha256, paths/read/deleted/symlinks/owned_untracked와 **patch_file·index_patch_file 두 파일**을 전달한다. JSON은 목록, diff는 실제 변경 내용이다. stat/파일명/hunk header 요약으로 diff를 대체하지 않는다. 새 파일은 read 목록에서 읽고 삭제는 diff, symlink는 링크 자체를 검토한다. 큰 diff도 파일을 분할해 읽으며 생략한 범위를 기록한다. 자료는 실행 디렉터리에만 보존하고 원문 로그의 비밀값은 노출하지 않는다.

리뷰어에게 다음을 명시적으로 전달한다:

- 검증된 PROJECT_ROOT, START_SHA, 수집 HEAD, scope.json 절대 경로와 파일 SHA-256, content_sha256.
- 승인된 Technical Spec의 위치, 변경 파일 목록 및 두 diff 절대 경로.
- 이미 수행한 관련 검사와 병렬 Phase 8.1 각각의 명령, 실제 exit code, 완주 여부, 로그 절대 경로, tested_tree, QL 회차. 이전 회차 로그로 현재 검사를 대신하지 않는다.
- 첫 검토/보완 검토 구분, REVIEW_ATTEMPT, QL 회차, 앞선 지적의 ID·처분·수정 근거.

검사 로그는 새 `{RUN_DIR}/scope-{REVIEW_ATTEMPT}`의 build.log·unit.log 절대 경로를 BUILD_LOG/UNIT_LOG로 배정한다. REVIEW_ATTEMPT는 QL 재진입에도 초기화하지 않는다. 재실행은 새 미사용 로그 경로나 새 시도 디렉터리를 사용한다. 같은 파일을 덮지 않는다. 실패한 검사도 명령·exit·로그가 있으면 **근거 있음**이며 실패 판정은 그대로 유지한다. 명령 미설정은 해당 검사의 정당한 SKIPPED 사유를 전달한다.

## 병렬 결과 대기와 누락 보완

8.1이 실행 중이어도 코드 검토는 시작할 수 있다. 결과 대기는 `MISSING_EVIDENCE: pending_8.1`로 구분하고 `evidence_complete:false`, `missing_evidence:[구체 항목]`, `verdict:PARTIAL`, `terminal_state:RUNNING`을 남긴다. 아직 실행하지 않는 **후행 8.6/8.7·VERSION·PR은 8.4 필수 입력이 아니다**.

Batch A 합류 후 8.1 결과와 부족한 diff를 같은 독립 리뷰어에게 전달해 필요한 범위만 보완한다. 코드가 바뀌었으면 새 scope를 먼저 수집한다. 부모가 직접 확인한 사실만으로 리뷰어의 누락 항목을 해소하지 않는다. 원래 결과를 수정하지 않고 새 REVIEW_ATTEMPT 이벤트를 추가한다. 이는 QL 회차 증가나 전체 품질 루프 재시작이 아니며 기존 에이전트 재시도 상한을 유지한다.

수집 불가·미확인·리뷰어 사망으로 보완되지 않으면 코드상 문제를 못 찾았어도 `evidence_complete:false`, `verdict:INCONCLUSIVE`, `terminal_state:BLOCKED:REVIEW_SCOPE`다. FAIL(확인한 구현 오류), 근거 부족, 범위 밖 지적을 섞지 않는다. 근거가 완전해도 구현 오류가 남으면 FAIL이다.

## 기록과 마감

[result-contract.md](result-contract.md)의 `kind:scope` 이벤트를 오케스트레이터만 RESULTS_FILE에 append한다. scope의 `iteration`은 REVIEW_ATTEMPT이고, `ql_iteration`은 품질 루프 회차다. 첫/보완 결과와 미확인 이력을 덮지 않는다. scope 객체는 `artifact`, `artifact_sha256`, `root`, `start_sha`, `content_sha256`를 담는다. artifact SHA-256은 실제 scope.json 바이트에서 계산한다. 수집 자체가 실패해 artifact가 없으면 scope:null과 누락 이유를 기록한다.

루프 성공 종료와 Phase 10/최종 반영 전에 다음 **두 검사**를 수행한다:

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_scope.py" \
  --cwd "{CWD}" --start-sha "{START_SHA}" --owned-files "{OWNED_FILES}" \
  --out "{RUN_DIR}/scope-current.json"
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_results.py" check-scope \
  "{RESULTS_FILE}" --run-id "{RUN_ID}" --scope "{RUN_DIR}/scope-current.json" --domain be
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_results.py" check-current \
  "{RESULTS_FILE}" --run-id "{RUN_ID}" --cwd "{CWD}" --require scope
```

각 명령은 앞 명령 exit 0일 때만 계속한다. check-current의 기존 필수 kind도 함께 전달한다. check-scope exit 0은 최신 독립 검토가 PASS/WARN·DONE이고 근거가 완전하며, 보존 artifact·diff의 해시와 현재 범위가 일치한다는 뜻이다. content_sha256에는 index가 포함되므로 staged 내용만 바뀐 경우도 재검토가 필요하다. tested_tree 해시와 혼용하지 않는다. 내용 동일 commit의 재사용도 **두 검사 모두** 통과한 경우에만 가능하다.

FAIL이나 근거 부족이 남으면 기존 QL 상한 안에서 해당 검토를 보완한다. 상한을 늘리거나 필수 검토를 SKIPPED로 바꾸지 않는다. 상한 도달 시 테스트 미통과는 기존 BLOCKED:TEST_NOT_GREEN, scope 미완료는 BLOCKED:REVIEW_SCOPE로 구분해 기록한다. 후속 보고 단계는 진행하되 push/PR과 DONE 마감은 보류한다. 구 schema v1 결과는 읽을 수 있지만 scope가 없는 과거 Build를 새 마감 근거로 사용하는 경우 독립 검토부터 보완한다. FE/Analyze/Verify/단독 E2E의 필수 kind를 이 문서만으로 늘리지 않는다.

## 지적 처분

기존 상태/보고서의 `## Review Findings`에 아래 열을 append하고 재지적은 같은 ID를 사용한다. E2E 전용 JSON fixes에 섞지 않는다.

| finding ID | review ID / 첫·보완 | 지적·file:line | 처분 | 근거·수정 commit·후속 issue | 확인 시점 |
|---|---|---|---|---|---|

처분은 `fixed`, `false_positive`, `out_of_scope`, `accepted_risk`, `deferred`, `unknown`이다. 무응답은 unknown, 미반영은 자동 false_positive가 아니다. false_positive에는 지적을 반박하는 코드/명세 근거가 필요하다. 중간 수정은 당시 commit을 남기고 최종 교체·머지 존속 확인을 별도 행으로 기록한다. 보고서는 최초 판정의 작업 수와 재검토 횟수를 구분하며 판정 없는 결과를 PASS/REJECT 분모에 넣지 않는다.
