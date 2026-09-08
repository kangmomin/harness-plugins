## 📋 Task Report: AI 활용성 리뷰 피드백의 하네스 반영

### 1. Pre-Review (Plan)

- **근거**: `work-log:정리된 문서/AI 활용성/20260907-AI 활용성 리뷰.md` §6.1~6.7, §7.1~7.5. work-log MCP 연결과 vault 설정은 정상이었으나 이동 전 문서 경로가 인덱스에 남아 있어 실제 파일을 직접 읽었다.
- **Orchestrator Feedback**: 기존 절차에서 반복 확인·검증을 유발하는 문구와 완료·기준·승인 정보의 인계 누락을 수정한다. Claude BE/FE/common과 별도 Codex BE 저장소를 함께 반영한다.
- **독립 리뷰어 Feedback**: fresh-context 서브에이전트 1개가 계획을 검토했다. 동일 승인만 재사용, 기존 Spec 활용, 직접 Spec·일반 위임 경로 연결, 권한 조건의 AC/EC 승계, Read-back 격리, source/target 출처 구분을 제안했다. 외부 CLI 리뷰는 수행하지 않았다.
- **Refinement**: 새 상태 스키마 대신 Spec의 작업 계약을 사용한다. 필수 검증 이후의 추가 반복만 제한하며 기존 Phase·상한·권한 경계를 보존한다.
- **난이도 분해**: 피드백 매핑 낮음 → Claude 규칙 수정 중간 → Astra 변환·호환성 기록 높음 → 검증 중간.

### 2. Implementation Details

- **Assumptions**: 하네스 범위는 현재 저장소의 BE/FE/common 및 이를 상속하는 오버레이, Codex 대상은 별도 `codex-be-harness` 저장소로 해석했다. Astra 튜닝은 기존 모델 슬롯을 유지하는 행동 지침 개선으로 적용했다.
- **Key Changes**: [작업 계약과 실행 원칙](../be-harness/skills/start-workflow/references/execution-policy.md)을 BE/FE/common에 포함하고 기존 parity 검사로 동일성을 확인한다. request·workflow·단독 검증 스킬과 일반 위임 경로에서 읽도록 연결했다.

| 피드백 | 반영한 동작 |
|---|---|
| §6.1 종료가 열린 검증 | 검사 범위·결함 기준·완료 증거를 고정. 필수 검증 이후 추가 리뷰에 새 근거·미검증 가설·수정 영향 요구. 미해결과 미검증 보존 |
| §6.2 반복 승인 | 계획 공유와 실행 승인을 구분. 유형·코드로 확정한 값·같은 Plan/효과의 승인은 재사용. workflow의 request는 Spec 수집만 수행 |
| §6.3 참조가 바뀌는 경계 | 저장소·worktree·브랜치·정확한 식별자·최신 결정·미완료·승인 근거를 인계. 새 worktree는 기존 RUN을 강제 재사용하지 않음 |
| §6.4 늦은 완료 조건·부적합한 선례 | 작업 계약에 문서·버전·커밋·push·PR 처리 범위와 현재 기준을 명시. 선례는 실제 동작·데이터·권한 적합성으로 선택 |
| §6.5 통과만 맞추는 테스트 | 요구·기준 문서에 따라 기대값 결정. 구현/테스트/환경 오류 구분과 기존 TestConflict 처리. 역할·소유자별 AC/EC, 관리자 성공 대체 금지, 부족한 fixture는 UNCOVERED |
| §6.6 로그의 초점·마스킹 | 환경·재현·기대/실제·관련 로그로 정리. Spec·위임·보고 발췌의 인증·연결 비밀값 마스킹 |
| §6.7 원인 가설의 조기 확정 | 사용자 가설을 지지·반박하는 근거와 대안 비교. 성능 변경 전 실제 쿼리·측정 확인 |
| §7.5 지침 관계 | 현재 설계에는 최종 계약, 과거 결정·기각 이유는 작업 기록. 사용자 지시와 기존 승인의 우선순위 명시 |

Codex는 기존 execution-policy에 필요한 결정 기준을 합치고 Phase 4.4의 승인 재사용, bootstrap/envelope, Spec·상태, 테스트 경로에 연결했다. 모델·effort 슬롯, 단일 writer, 상태 스키마, 필수 Phase·상한은 유지한다. 근거는 2026-09-08 실제 본문을 확인한 [공식 GPT-6 Astra 가이드](https://developers.openai.com/api/docs/guides/latest-model)다. 선택 반영 파일과 해시는 Codex의 COMPATIBILITY.md·UPSTREAM-SYNC.json·SYNC-REPORT.md에 기록한다.

### 3. Final Convention Review

- **Layer Analysis**: 애플리케이션 Presentation/Service/Repository 변경은 없다. 정책은 판단 기준, 기존 스킬은 실행 경로, 기존 helper는 상태·검증·권한 경계를 담당한다.
- **Simplicity Check**: 새 스킬·프로필 키·상태 스키마·위임 단계 없이 기존 Spec과 정책 소비 경로를 사용했다. Claude 정책 사본은 독립 설치를 위한 것이며 동일성 검사를 추가했다.
- **독립 행동 검토**: 별도 fresh-context 리뷰어가 승인된 Plan, 관리자 토큰만 있는 smoke E2E, 설계/테스트 충돌, timeout 가설, 파일명 정정·worktree 인계, 최종 트리 변경의 6개 상황을 양쪽 지침에 적용했다.
- **반영한 발견**: 최종 검증기는 모든 최신 non-pr 이벤트의 tree 일치를 요구한다. 이를 영향 범위 재검증 문구와 연결하고, 마지막 수정·커밋 뒤 stale 이벤트별 실제 재검증 및 격리 Read-back 재검증 예외를 명시했다. 리뷰어 재확인에서 충돌 해소를 확인했다. 검증 엔진·상태 스키마는 변경하지 않았다.

### 4. Status

- **Verification — Claude**: `bash scripts/verify.sh` PASS. 구조·parity, Python 197개, work-log Python 10개·Node 31개, 실제 Chromium 문서 렌더링 5개, FE build/type/Jest 6개·Vitest 11개 및 loopback gRPC fixture 통과.
- **Verification — Codex**: validate_port, plugin validator, 17개 skill validator, Python 93개, 실제 Chromium 문서 렌더링 5개, shellcheck 통과. 전체 76개 target 해시 일치 확인.
- **검증 환경 제약**: 기존 FE fixture의 `npm ci`는 lockfile의 `@emnapi/*` 불일치로 실패했다. lockfile을 수정하지 않고 `npm install --package-lock=false --no-save`로 검증 의존성을 준비한 뒤 전체 스크립트를 통과했다. 따라서 새 환경의 고정 lockfile 설치까지 성공한 결과는 아니다. Python 검증 의존성은 임시 venv, Chromium renderer는 격리 컨테이너에서 `HARNESS_DOCGEN_NO_SANDBOX=1`을 사용했다.
- **검증 한계**: 6개 상황은 독립 모델의 지침 적용 검토이며 실제 업무의 전체 workflow·서비스 API·원격 반영 실행 결과가 아니다. 기존 검증 결과는 전체 tree에 묶이므로 최종 문서/commit 변경도 stale 검증 재실행을 요구할 수 있다.
- **Cleanup**: 검증 프로세스·fixture 자원은 종료했고 임시 검토 자료·venv·로그를 정리했다. 설치한 검증용 node_modules는 Git 제외 개발 의존성으로 유지한다. 후속 커밋·푸시 요청에 따라 두 저장소를 게시하며, 적용 범위와 기존 모델 슬롯 유지 결정을 재사용한다.
