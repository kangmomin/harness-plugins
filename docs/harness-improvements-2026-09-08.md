## 📋 Task Report: 하네스 검증 신뢰성과 재개 개선

### 1. Pre-Review (Plan)

- **Orchestrator Feedback**: 앞선 분석의 R1~R8에 대한 변경 요청과 계속 요청을 근거로, 원본 BE/FE/common과 Codex 포트의 관련 소스·테스트·실행 지침을 수정했다.
- **독립 리뷰어 Feedback**: fresh-context 리뷰어가 v2 비교의 단일화, 실제 파일 집합, 통합 결과의 루프·아카이브 연결, 리터럴의 원래 바이트 해시, Verify 재개 helper 검증을 요구했다. 외부 CLI 리뷰어는 사용하지 않았다.
- **Refinement**: legacy 근거를 자동 변환하지 않고, 기록된 HEAD 의존성을 약화하지 않는다. 후보 탐색과 커버리지 판정을 분리하고, 불완전한 저장 상태는 보존한 채 차단한다.
- **Task Breakdown**: 검증 진입점·FE 설치(R2/R4, 중) → 파일 지문·재사용(R1/R5, 상) → 통합 결과(R3, 상) → 리터럴·테스트 후보·Verify 보존(R6/R7/R8, 중) → 독립 행동 검증·동기화·정리(중).

### 2. Implementation Details

- **Assumptions**: 없음. 분석에서 제안한 R1~R8과 사용자의 변경 승인을 적용했다.
- **대상 기준**: 원본 main `80366fe`, Codex 포트 main `21b15a5`를 기준으로 구현했다. 후속 commit-hard-push 요청에 따라 BE 1.5.6·FE 1.4.5·common 0.14.4와 Codex 0.6.2로 게시할 내용을 확정했다.

| 분석 항목 | 변경과 완료 근거 |
|---|---|
| R1 / R5: 지문과 검증 재사용 | [workflow_results.py](../be-harness/skills/start-workflow/assets/workflow_results.py)에 실제 파일 집합 기반 v2 지문과 공통 비교 함수를 적용했다. textconv·assume-unchanged·skip-worktree에 숨겨진 바이트 변경은 stale, staging·add/delete commit·빈 commit의 내용 불변은 재사용된다. 실행 비트·symlink·특수 파일·submodule도 검증했다. |
| R2: 실제 테스트 진입점 | Codex에 `scripts/verify.sh`와 CI를 추가하고 AGENTS/README를 연결했다. Python 실패와 Node 실패를 각각 주입한 fixture에서 명령 실패가 전달됐고, 정상 상태는 통과했다. 미응답 승인·구 schema 자동 변환·아카이브 덮어쓰기 폴백에 관한 오래된 시나리오 기대값도 정리했다. |
| R3: 통합 결과 보존 | `integration` kind와 최신 unit/integration 합산을 추가했다. [Phase 8.7](../be-harness/skills/start-workflow/references/quality-loop.md), [baseline 비교](../be-harness/skills/start-workflow/references/tdd.md), [아카이브](../be-harness/skills/start-workflow/assets/workflow_archive.py), 필수 검증 목록을 연결했다. 최신 unit PASS가 integration FAIL·회귀 수를 대체하지 않는다. |
| R4: 깨끗한 FE 설치 | [FE lockfile](../tests/fixtures/fe-components/package-lock.json)의 @emnapi 의존성 배치를 정상화하고 [CI](../.github/workflows/verify.yml)에 npm 11.6.2를 명시했다. Node 24.11.0/npm 11.6.2의 빈 node_modules·캐시에서 npm ci가 성공했으며 설치 후 package/lock 바이트가 소스와 같다. |
| R6: 태그 리터럴 오탐 | [git_checks.py](../common/skills/commit/assets/git_checks.py)에 선택적 `--literal-tags` 입력을 추가했다. 검토한 정확한 경로·줄·원래 바이트 해시·이유만 제외 기록으로 남긴다. 실제 미해결 태그와 commit message는 계속 차단되고, 내용 변경·잘못된 JSON은 예외를 승계하지 않는다. |
| R7: 테스트 후보 탐색 | [risk_facts.py](../be-harness/skills/start-workflow/assets/risk_facts.py)가 같은 Go 패키지와 지정 testDirs의 후보를 `candidate`로 구분한다. 파일명만 바뀌어도 후보가 유지되고 무관한 테스트를 커버리지로 인정하지 않는다. |
| R8: Verify 명령 보존 | [workflow_run.py](../be-harness/skills/start-workflow/assets/workflow_run.py)가 최초 명령 4종·실행 ID·CWD·profile 출처를 배타 저장하고 resume에서 검증한다. 변경된 live profile을 다시 해석하지 않으며 누락·손상·다른 실행의 스냅샷은 차단한다. |

공유 workflow_results/run/archive helper는 BE·FE·common·Codex 네 사본, risk_facts는 BE·FE·Codex 세 사본, git_checks는 common·Codex 두 사본을 맞췄다. 구현 중에는 실제 작업 트리 해시를 기록하고, 게시 절차에서 Codex의 UPSTREAM-SYNC.json을 원본의 최종 커밋과 파일 해시로 확정한다.

### 3. Final Convention Review

- **Presentation**: 실행 지침·시나리오·보고서가 실제 helper 출력과 일치하도록 연결했다. 구조 검사 성공과 테스트 성공, 테스트 후보와 커버리지를 구분한다.
- **Service**: 통합 테스트 실패가 품질 루프 종료까지 유지된다. 단일 writer·승인 재사용·Read-back 격리·기존 루프 상한을 보존했다.
- **Repository**: 애플리케이션 DB 변경은 없다. Git 지문·결과 JSON·스냅샷·lockfile 저장 계약을 수정했고, 기존 이벤트나 실행 파일을 성공 근거로 덮어쓰지 않는다.
- **Simplicity Check**: 기존 helper와 결과 형식에 필요한 필드·명령만 추가했다. 일반 실행 프레임워크나 파일 전체 예외는 도입하지 않았다. 복제본은 기존 배포 구조에 맞춰 동일하게 반영했다.
- **Style Match**: 기존 Phase·상태 코드·스크립트 방식과 호스트별 경로/역할을 유지했다.

### 4. Status

- **독립 행동 검증**: A — 내용 동일 commit 후 unit PASS를 재실행 없이 재사용하고 최종 결과 사본 검증 성공. B — unit 최신 PASS와 integration FAIL을 합산해 FAIL·회귀 1건 유지. C-valid — 변경된 profile 대신 저장된 `recorded-command`를 실행해 exit 0, 결과 JSON 검증 성공. 최초 C fixture의 필수 메타데이터 누락은 별도 BLOCKED 증거로 보존했다.
- **Verification**: 원본 `bash scripts/verify.sh` exit 0 — 구조/공유 계약, Python 212개, work-log Python 10개·Node 31개, 실제 Chromium doc-gen 5개, FE Jest 6개·Vitest 11개와 build/typecheck, 실제 loopback gRPC fixture 통과. Codex runner exit 0 — 구조 검사, Python 109개, 실제 doc-gen 5개 통과. plugin validator·17개 skill validator·shellcheck도 통과했다. 전체 검사 뒤 추가한 디렉터리↔파일 전환 경계는 두 저장소의 지문 회귀 검사 7개로 재검증했다.
- **호환성 경계**: v2는 ignored 파일·저장소 밖 입력 전체의 지문이 아니다. HEAD 의존 여부가 불명확하면 `--include-head`를 사용한다. 구 지문은 새 검증이 필요하고, 명령 스냅샷이 없는 구 Verify 실행은 새로 시작해야 한다. integration reader와 writer는 함께 갱신한다.
- **실행 범위**: 실제 로컬 helper·Git·브라우저·FE·gRPC fixture와 지정한 독립 행동을 검증했다. 원격 CI나 실제 서비스의 전체 Build→PR, Verify V3~V5, 모델별 시간·비용은 이번 실행 범위에 없다.
- **Integrity**: 구현 완료 시점에 전체 target 해시 78개·선택 source 해시 21개, 공유 helper 사본, 보고서의 로컬 링크 19개를 확인했다. 당시 두 저장소 HEAD·index를 보존했고 git diff --check와 구조 검사가 통과했다.
- **게시 검토**: 후속 독립 리뷰에서 원본 4개·포트 2개 커밋 분할과 리터럴 분류를 확인했다. 태그 정책·회귀 fixture·시나리오 표기만 정확한 줄/바이트 해시에 연결하며, 실제 미해결 항목과 Git 메시지는 예외로 처리하지 않는다. push 직전에 확정 HEAD로 Gate를 검사한다.
- **Cleanup**: 전체 로그·독립 행동 결과·설치 근거를 `/workspace/harness-review-2026-09-08/implementation-evidence.json`과 동반 로그에 보존했다. 소유 프로세스가 없음을 확인한 뒤 이번 작업의 임시 venv·fixture·패키지 캐시를 삭제했다. Git에서 제외된 기존 개발 의존성은 유지했다.
