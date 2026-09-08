# 최종 결정 이후 검증과 반영

최종 보고 Phase에서 결정을 받은 뒤, 상태 마감·아카이브 **전에 반드시** 이 절차를 수행한다. 최초 보고는 결정용 초안이다. 기록된 `## Final Decisions`는 재개 시 다시 묻지 않는다.

1. 승인한 코드·Spec·테스트 수정만 적용한다. 변경 이유와 경로를 상태/구현 노트에 기록한다. Baseline 원본은 갱신하지 않는다.
2. 수정 범위에 필요한 빌드·타입 체크·관련 단위/E2E 테스트·컨벤션 검증을 다시 실행한다 (BE Phase 7~9, FE Phase 6~8, 풀스택 Phase 7~8의 해당 검증). 동작/계약 수정은 해당 Read-back 대조도 갱신한다. 최종 검증 결과를 result-contract.md의 RESULTS_FILE에 새 iteration으로 기록하고 검증한 tested_tree를 함께 보관한다. 실패하면 승인 범위 안에서 수정·재검증하고, 미해결이면 해당 Phase를 `BLOCKED:{사유}`로 유지한다.
3. `entry-contract.md`의 상태 `PUBLISH_POLICY`를 읽고 검증된 소유 수정만 기존 브랜치에서 논리별 커밋한다. 정책별 후속 처리는 아래 표대로 수행한다. 완료된 branch/VERSION/PR을 중복 실행하지 않는다. 모든 새 commit/amend/rebase 뒤 Gate를 다시 통과해야 원격 반영한다. 검증되지 않은 tree의 옛 PASS는 재사용하지 않는다.

   | PUBLISH_POLICY | 최종 수정/재개 시 반영 |
   |----------------|----------------------|
   | local (FS --hard 또는 그 도메인 전환) | 로컬 commit만. push/PR/원격 SHA 일치 검증을 실행하지 않음 |
   | push (BE/FE --hard) | common:commit-hard-push의 commit → Gate → 같은 원격 브랜치 push, 원격 SHA 확인 |
   | pr | common:commit-pr의 미완료 단계 또는 기존 PR 갱신, Gate → 같은 브랜치 push, PR/원격 SHA 확인 |
   | none (Analyze/Verify) | 분석/검증 보고만. Build 커밋/원격 절차를 실행하지 않음 |

   FS는 Phase 7~8의 테스트/계약/필수 overlay hook BLOCKED가 남으면 Phase 9를 재개하지 않고 Phase 11 보고·결정을 유지한다. 승인된 수정 후 영향 hook과 최신 검증을 통과하면 Phase 9 미완료 작업을 실행한다. 사용자 범위 제외는 사유를 기록하며 과거 실패 이벤트를 PASS로 바꾸지 않는다.
4. `{WORK_REPORT}`의 검증 표는 RESULTS_FILE의 마지막 결과에서 작성하고, 최종 수정·검증·commit/push·잔존 항목에 맞게 갱신한다. 코드 수정 없이 보류 결정만 받았어도 보고서에는 그 결정을 반영한다. 로컬 전용 보완점은 기존 결정 범위를 따르며 push 대상에 임의로 포함하지 않는다.
5. 필요한 검증·반영이 모두 끝난 경우에만 최종 Phase를 `DONE`, `Remaining Phases`를 `없음`으로 마감하고 아카이브한다. 필수 검증·반영의 미해결 `BLOCKED`/`FAIL`을 일괄 `DONE`/`SKIPPED`로 바꾸지 않는다. 사용자가 범위 밖으로 명시 승인한 보류 항목은 `Final Decisions`와 보고서에 사유를 남기고 완료 대상에서 제외할 수 있다 (이전 실패 기록은 보존). 필수 작업이 남으면 현재 보고서와 상태를 보관하고 미완료 Phase를 남긴다. 완료 전에는 같은 RUN_ID의 영구 아카이브를 생성하지 않는다.

## 최종 트리와 검증 재사용

`workflow_results.py check-current`는 `--require` 목록뿐 아니라 **모든 최신 non-pr 이벤트**의 검증 입력을 대조한다. v2 내용 지문이 같고 HEAD 의존성이 없으면 일반/빈 commit 뒤에도 원래 이벤트를 재사용한다. 실제 파일 내용·모드·경로가 바뀌거나 head_sensitive 검증의 HEAD가 바뀌면 stale인 종류/케이스를 실제 재실행해 새 iteration으로 기록한다. 구 지문은 v2로 자동 변환하지 않는다. 원래 SKIP 조건이 적용되는 항목만 현재 근거로 다시 판정하며, 미해결 실패를 SKIP으로 바꾸거나 과거 이벤트의 해시만 교체하지 않는다.
Read-back의 “루프 밖 1회”는 최초 품질 검증 횟수다. 최종 수정 또는 HEAD 의존 검증의 commit 변경으로 기존 결과가 stale인 경우에는 이 마감 절차에서 격리를 유지해 재검증한다. 검증할 트리가 더 바뀌지 않도록 문서·버전·로컬 커밋을 먼저 마무리하고, 현재 트리의 필수 근거가 모두 갖춰진 뒤에는 새 근거 없는 추가 리뷰를 돌리지 않는다. 재검증 불가 시 미완료와 남은 stale 항목을 보고한다.
