# 풀스택 overlay handoff

오케스트레이터는 Pre-flight에서 이 문서와 `assets/fullstack_overlays.json`을 Read하고 `workflow_policy.py overlays`로 hook 계획을 만든다. 이것이 단일 도메인의 앵커를 FS 실행 지점으로 옮기는 명시적 매핑이다. 설치된 overlay 또는 프로젝트의 overlay-source 복사본이 있을 때만 적용하며 전체 start-workflow를 중첩 호출하지 않는다.

## 소스와 실행 기록

1. 세션 스킬/플러그인 메타데이터로 minmos/hyeondongs 설치와 **실제 root·호출명**을 확인한다. 경로를 추측하지 않는다. 프로젝트의 `.claude/{be-harness|fe-harness}/common.md`, `skills/{name}.md`도 확인한다.
2. 같은 overlay-source 마커의 프로젝트 복사본은 해당 파일의 설치본보다 우선한다. 각 hook의 `files`를 모아 `workflow_policy.py sources`에 plugin/절대 plugin_root/cwd/files로 전달한다. 반환된 실제 경로와 project_rules를 읽고 같은 소스를 중복 주입하지 않는다. start-workflow 한 파일에 마커가 있다는 이유로 request/e2e/common 등의 별도 파일까지 생략하지 않는다. 프로젝트 사용자 규칙은 보존하며 `hook.id`당 적용 소스는 하나만 기록한다. 복사본에서 참조한 자료의 위치를 찾지 못하면 `BLOCKED:OVERLAY_SOURCE`를 남긴다.
3. Pre-flight에서는 소스·capability를 읽기 전용으로 확인한다. init/다운로드/import는 진단으로 실행하지 않는다. `facts`는 `request_needed`, `codex_enabled`, `e2e`, `api_change`의 실제 boolean 판정이며 누락을 false로 추측하지 않는다. `capabilities`는 해당 실행에서 확인된 `review`, `http-or-grpc`, `apidog-read`, `apidog-import-authorized` 같은 기능명이다. 실제 tool 이름과 성공/권한 근거를 별도로 기록한다.
4. `workflow_policy.py overlays`에 `selected`(플러그인 식별자 중복 없는 배열), `facts`, `capabilities`를 JSON으로 전달한다. READY hook만 지정 point에서 실행하고, 조건 불일치는 SKIPPED:NOT_APPLICABLE, 필수 기능 누락은 BLOCKED로 기록한다. 누락 영향은 해당 hook에 한정하며 가능한 검증/최종 결정은 계속한다.
5. 각 도메인 에이전트에는 **자기 hook의 실제 소스 경로·절 제목·point·owner·조건·capability·이전 결과**를 전달한다. 성공/실패/생략·근거를 반환받아 오케스트레이터만 `## Overlay Handoff`를 기록한다. 공유 상태/index 쓰기와 commit은 오케스트레이터 소유다.

| hook | FS 실행 지점 | 추가/치환 |
|------|-------------|-----------|
| mm.preflight | Phase 1 전 | env·Apidog·DB 실제 기능 및 DB 안전 규칙 확인 |
| hd.profile / hd.backend | Phase 1 전 | 유효한 FE primary → 실제 부재 시 legacy, 설치된 minmos BE 선택 |
| mm.request | Phase 1 request가 필요할 때 | 계층/Spec 규칙 델타 |
| mm.e2e-flow | Phase 1 Spec 정리 직후 | **request 호출을 생략해도** E2E 메인 플로우를 1회 수집. 이전 사용자 답은 재질문하지 않고 원문 보존 |
| mm.plan-review | Phase 4.4 | Codex 사용 시 실패 폴백 기록, 리뷰 상한 승계 |
| mm.conventions | Phase 6/7 BE | 구현·검사에 Post-Math 컨벤션 적용 |
| mm.e2e | Phase 7 BE E2E | Post-Math 시드/정리·gRPC 확장, DB 작업 전 db-safety 조건도 충족 |
| mm.quality-review | Phase 7 BE 루프 직후 | standard 리뷰 상한 4회; advisor 결과만 반환 |
| mm.doc-sync | Phase 7 BE 문서 동기화 | API 변경이면 Apidog로 **치환**. `apiDocsPath` 존재 조건을 사용하지 않음. 생성/수정/삭제 분기는 doc-sync 역할 파일을 따름 |

## 재검증과 재개

- `valid_for: run/spec/iteration/tested_tree`가 기록의 유효 범위다. E2E 플로우의 기존 답은 run에서 재사용하고, 검증/품질 리뷰/API 문서는 현재 tested_tree가 같고 최신 결과가 유효할 때만 재사용한다.
- 품질 리뷰의 수정 제안은 BE owner가 반영한다. advisor는 구현·공유 노트·index를 수정하지 않는다. CONCERN 반영 후 관련 검증을 갱신하고, REJECT는 수정 → 검증 → 재리뷰한다. 상한은 재개/최종 결정/Phase 8 수정에도 승계하며 새 tree를 옛 APPROVE에 덮어쓰지 않는다. 남은 횟수 없이 필수 리뷰가 필요하면 BLOCKED:CODEX_REVIEW를 보존한다.
- Phase 8 또는 최종 결정에서 코드/계약이 바뀌면 영향 hook도 다시 실행한다. doc-sync는 immutable target/payload 및 read-back 계약을 따른다. 단순 timeout 때문에 import를 다시 실행하지 않는다.
- `PUBLISH_POLICY: local`은 Git push/PR을 금지한다. Apidog 등 외부 문서 쓰기는 별도 실제 권한 확인이 필요하며 local 커밋 권한으로 추론하지 않는다. 권한/기능 누락은 최종 보고에 남기고 사용자가 명시한 제외만 완료 범위에서 뺀다.
