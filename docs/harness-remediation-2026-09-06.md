# 📋 Task Report: 하네스 감사 전체 수정

2026-09-05 감사의 결함 41건과 개선 30건, 총 **71건을 구현**했다. 전체 검증과 독립 최종 리뷰를 완료했으며, 추가 미해결 finding은 없다. 원본 감사 보고서와 증거 JSON은 수정하지 않았다.

원본: [감사 보고서](harness-audit-2026-09-05.md) · [수정별 검증 증거](harness-remediation-2026-09-06-evidence.json)

## 1. Pre-Review (Plan)

- **Orchestrator Feedback**: 상태·소유권·실제 호출 계약을 먼저 고정하고, 감사 ID별 최소 변경과 재현 fixture로 작업을 나눴다.
- **독립 리뷰어 Feedback**: 경합 중 파일 교체, DB 객체 재생성, Apidog 응답 유실, 과대 cursor, agent 권한 상속, legacy feedback 중복, HTML fragment 누락, 구조 검사와 gRPC 검증의 거짓 성공을 추가 확인했다.
- **Refinement**: 재현된 반례를 수정하고 실행 검증에 연결했다. 외부 CLI 모델 리뷰 대신 독립 서브에이전트 리뷰와 로컬 mock host 검증을 사용했다.

## 2. Implementation Details

- **Assumptions**: 기존 제품의 배포 계열을 유지하도록 work-log 외 제품은 patch를 올렸다. work-log는 저장/잠금 계약 변경에 맞춰 이미 계획한 0.3.0을 적용했다.
- **Key Changes**: work-log 파일 I/O·메타데이터·인덱스, 테스트 실패 분류와 실행 소유권, workflow/commit/merge 상태, 프로필과 FE 템플릿, DB/Apidog 경계, worktree hook, 페이지네이션, agent 권한, 피드백·문서·사용법, 필수 CI 검증을 보완했다.

| 제품 | 수정 버전 |
|---|---|
| common | 0.14.2 |
| be-harness | 1.5.4 |
| fe-harness | 1.4.3 |
| minmos-harness | 2.5.2 |
| hyeondongs-harness | 3.0.1 |
| work-log | 0.3.0 |

### 감사 항목 추적

각 행의 상세 변경 파일, 수용 조건, 실제 검증과 한계는 증거 JSON의 같은 ID에서 확인할 수 있다.

| ID | 수정 대상 | 상태 |
|---|---|---|
| W01 | 문서 잠금 대기 중 디렉터리 교체로 vault 밖 쓰기 | 구현·검증 |
| W02 | title 메타데이터의 타입 오류가 vault 전체 동기화를 중단 | 구현·검증 |
| W03 | 저장 성공 뒤 인덱싱 실패를 전체 쓰기 실패로 응답 | 구현·검증 |
| W04 | append/overwrite가 기존 파일 접근 권한을 완화 | 구현·검증 |
| W05 | 인덱스 잠금을 시간만으로 탈취해 최신 결과를 과거 결과로 덮어씀 | 구현·검증 |
| W06 | 공백·한글 설치 경로에서 설정 CLI가 출력 없이 종료 | 구현·검증 |
| W07 | null/false 설정을 무시하고 다른 vault로 폴백 | 구현·검증 |
| W08 | 코드 블록의 # 줄을 제목으로 처리해 섹션을 잘라냄 | 구현·검증 |
| W09 | 읽기 권한 오류를 삭제로 보고 정상 인덱스로 저장 | 구현·검증 |
| W10 | 잘못된 경로의 위키 링크를 다른 파일에 연결 | 구현·검증 |
| T01 | Vitest 동일 제목의 실패 메시지가 다른 파일의 메시지로 덮임 | 구현·검증 |
| T02 | Jest의 첫 줄만 비교해 실제 단언 값 변화가 회귀에서 빠짐 | 구현·검증 |
| T03 | 다른 파일의 동명 테스트 PASS가 원래 실패를 flaky로 만듦 | 구현·검증 |
| E01 | gRPC 대상이 E2E 보고서 분모에서 사라져 미검증을 성공으로 보고 | 구현·검증 |
| E02 | 동일 포트의 localhost와 127.0.0.1이 서로 다른 E2E 잠금을 획득 | 구현·검증 |
| E03 | E2E 수정 기록이 실패한 케이스가 아니라 마지막 케이스에 붙음 | 구현·검증 |
| Q01 | dirty 상태에서 이미 커밋한 구현이 품질 검사 범위에서 누락 | 구현·검증 |
| Q02 | FE 컴포넌트·접근성 수정 후 빌드/테스트 재검증 단계가 없음 | 구현·검증 |
| Q03 | FE lintCommand 설정을 실제 lint 단계가 사용하지 않음 | 구현·검증 |
| C01 | --bump-only가 기존 staged 파일도 커밋한다 | 구현·검증 |
| C02 | PR base 결정이 VERSION 존재에 종속되고 루트 버전 경로가 cwd에 따라 바뀐다 | 구현·검증 |
| C03 | BE/FE workflow-pr의 커밋·버전·base 계약이 common 절차와 갈라졌다 | 구현·검증 |
| C04 | Read-back의 브랜치 기준 diff가 --hard·FE/FS 비-main 저장소에서 증거를 누락 | 구현·검증 |
| C05 | 아카이브가 다른 Phase와 과거 회귀 건수를 최종 결과로 요약한다 | 구현·검증 |
| C06 | 아카이브 재시도는 DEGRADED를 OK로 바꾸고 입력 run_id 충돌은 중복 파일을 만든다 | 구현·검증 |
| C07 | --fs --analyze/--verify를 막지 않아 읽기 요청이 Build 경로로 갈 수 있다 | 구현·검증 |
| C08 | 이미 queue에 있는 PR을 머지 완료로 오보고하고 base HEAD를 PR merge SHA로 사용 | 구현·검증 |
| C09 | resolve-assumption의 경로 필터가 untracked 검색에 빠져 있다 | 구현·검증 |
| M01 | E2E 정리 SQL이 다른 작업의 새 데이터까지 soft-delete | 구현·검증 |
| M02 | Apidog 재시도에서 대상 프로젝트를 자동으로 바꿔 쓰기 | 구현·검증 |
| M03 | OpenAPI 3.0 payload에 지원되지 않는 nullable type 배열을 생성 | 구현·검증 |
| M04 | API push가 성공 응답을 200으로 고정 | 구현·검증 |
| M05 | worktree 초기화 hook이 공백 경로·설정 파일 없는 첫 설치에서 실패 | 구현·검증 |
| M06 | 페이지네이션 템플릿의 tie-breaker가 다음 커서에 포함되지 않음 | 구현·검증 |
| M07 | snake_case 변환이 SQL Injection을 방지한다는 잘못된 안내 | 구현·검증 |
| M08 | Apidog·Proto 도구 참조가 환경 탐색/현재 설치 구조와 불일치 | 구현·검증 |
| M09 | Apidog 검증 payload가 실행별로 격리되지 않아 다른 실행 내용으로 바뀜 | 구현·검증 |
| F01 | 설정에서 지원하는 Nuxt·JavaScript와 FE 생성 템플릿이 맞지 않음 | 구현·검증 |
| F02 | hyeondongs doctor가 정상 현대 profile·선택 설정을 누락으로 보고 | 구현·검증 |
| A01 | 14개 agent의 도구 제한 frontmatter가 공식 필드와 다름 | 구현·검증 |
| S01 | 구조 검사 cleanup이 자신이 만들지 않은 __pycache__도 삭제 | 구현·검증 |
| I01 | 요약 생성 시 `headRefOid`를 기록하고 `gh pr merge --match-head-commit`으로 검토한 SHA를 고정한다 | 구현·검증 |
| I02 | Git 명령 실패와 grep no-match를 분리해 Gate를 닫힌 실패로 만든다 | 구현·검증 |
| I03 | 문서가 프라이빗 `common.local.md`를 제안하지만 실제 로드 목록은 common.md와 skill.md뿐이다 | 구현·검증 |
| I04 | `--be`/`--fe`는 베이스만 쓰는 플래그라는 안내를 실제 위임 우선순위 표에 명시한다 | 구현·검증 |
| I05 | 풀스택의 minmos/hyeondongs “오버레이 요약 전달”을 파일 경로·추가 단계·스킵 조건으로 구조화한다 | 구현·검증 |
| I06 | TEST_NOT_GREEN 후 Phase 8 강제 진행과 “둘 다 green이면 PR” 사이에서 최종 결정 Phase로 어떻게 넘어가는지 분기를 명시한다 | 구현·검증 |
| I07 | `--hard`가 단일 도메인에서는 직접 push, fs에서는 push 생략이라는 차이를 공용 플래그 표에서 보여준다 | 구현·검증 |
| I08 | 아카이브 명령의 경로들을 shell-quote하고, fallback에서도 reportDir 생성·실패 확인·exclusive create를 유지한다 | 구현·검증 |
| I09 | touched_paths는 Git `-z`로 읽고 문자열을 YAML-safe하게 인코딩한다 | 구현·검증 |
| I10 | 출력 디렉터리 생성/기존 파일 읽기 예외도 exit 2 계약으로 처리한다 | 구현·검증 |
| I11 | 재개 시 핸들 소실을 writer 사망으로 단정하지 말고 실행 소유 PID/작업 ID와 종료 증거를 확인한다 | 구현·검증 |
| I12 | worktree/서브디렉터리에서도 진행 중 rebase 감지는 `git rev-parse --git-path` 사용 | 구현·검증 |
| I13 | merge 전 VERSION/swagger 목록과 merge 결과가 다를 때(추가·rename·삭제) 대상 목록 재검증을 정의한다 | 구현·검증 |
| I14 | `target_type=common`을 Step3에서 commons로 복수화하는 일반식과 Step5의 common/날짜 파일 예외를 한곳에서 정의 | 구현·검증 |
| I15 | 파일명은 epoch 외 충돌 방지 suffix/exclusive write를 사용한다 | 구현·검증 |
| I16 | 플러그인 prefix를 고정 열거하므로 새로운 harness나 Codex 설치 이름 변경을 자동 발견하지 못한다 | 구현·검증 |
| I17 | “남은 Phase” 예시가 10에서 끝나 최종 11이 빠지고, 템플릿 상단도 최종 보고를 Phase10으로 설명한다 | 구현·검증 |
| I18 | “BE/FE가 동일 방향으로 계약을 이탈하면 contract 대조는 통과”라는 설명은 논리적으로 맞지 않는다 | 구현·검증 |
| D01 | CI에서 Python·Node 테스트, 구조 검사, marketplace/manifest 검증을 하나의 필수 job으로 실행한다 | 구현·검증 |
| D02 | 실제 Jest/Vitest reporter 로그를 고정 fixture로 보관하고 지원 runner 버전별 표본으로 파서를 확인한다 | 구현·검증 |
| D03 | 검증 결과의 run_id·mode·phase·iteration·case_id·tested tree·최종 상태를 구조화하고 Markdown은 그 값에… | 구현·검증 |
| D04 | 현재 긴 prose 편집 규칙을 작은 결정적 profile helper로 옮길지 검토한다 | 구현·검증 |
| D05 | 문서 수·읽은 bytes·scan 시간·누락/오류 수·index 생성 시각을 진단에 노출하고 현실적인 vault 크기로 측정한다 | 구현·검증 |
| D06 | cache의 index 버전·루트 일치·손상/이전 schema 처리 규칙을 테스트하고 재생성 경로를 안내한다 | 구현·검증 |
| D07 | Claude plugin 실행, Codex-native work-log, Codex에 대한 작업 위임을 구별하는 지원 표를 둔다 | 구현·검증 |
| D08 | 환경 파일의 허용 DB_HOST 확인과 실제 앱/MCP 연결 대상 확인을 연결한다 | 구현·검증 |
| D09 | grpcurl의 JSON 파싱 거부와 서버가 반환한 gRPC 상태를 구분하고, unknown field/oneof·deadline·streaming… | 구현·검증 |
| D10 | SKILL의 항상 flat 규칙(:130)과 reference의 재사용 객체 $ref 규칙을 하나로 정리한다 | 구현·검증 |
| D11 | worktree hook 설치는 기존 사용자 hook과 settings 권한을 보존하는 병합으로 정의하고 임시 파일을 실행별로 격리한다 | 구현·검증 |
| D12 | 로컬 문서 링크·실제 skill 호출명·Phase 표·canonical/override 우선순위를 함께 검사한다 | 구현·검증 |

## 3. Final Convention Review

- **Layer Analysis**: 사용자 절차/템플릿, 순수 판정 helper, 파일·원격 전송 경계를 분리했다. 상태 기록은 오케스트레이터가 맡고 읽기 전용 agent는 결과를 반환한다.
- **Simplicity Check**: 중복 절차를 검증된 helper로 연결했다. 별도 설치되는 제품의 필요한 사본은 byte parity로 검사하며 제품 간 전역 의존성을 추가하지 않았다. 무관한 원본 감사 자료와 DOT는 보존했다.

## 4. Status

- **Verification**: `scripts/verify.sh` 최종 exit 0. Python 207개(루트 197 + work-log I/O 10), Node 36개(work-log 31 + doc-gen 5), FE build/type와 Vitest 11/Jest 6, 실제 loopback gRPC 5개 시나리오 통과. 별도 Claude loader 14개 + legacy 대조군도 확인했다. [전체 실행 로그](harness-remediation-2026-09-06-verification.log)
- **Cleanup**: 실행 소유 임시 디렉터리, 두 테스트용 node_modules, Chromium/venv cache를 정리했다. 테스트 서버와 브라우저 프로세스는 종료됐고, 원본 문서 6개의 SHA-256은 모두 보존됐다. 관련 없는 사용자 cache는 건드리지 않았다.

### 검증의 적용 범위

- 실제 실행은 Linux에서 수행했다. macOS ACL 코드는 공유된 구현 경계를 유지하지만 macOS 런타임은 여기서 실행하지 않았다.
- PostgreSQL은 새 임시 cluster와 socket, Git은 임시 local repository, Apidog와 Claude 모델 응답은 local mock을 사용했다. 실제 업무 DB·Apidog·원격 배포를 검증한 결과로 확대하지 않는다.
- Claude host loader 14개와 구 allowed-tools 대조군을 관찰했다. Codex CLI/다른 배포판의 모든 조합을 보장하지 않는다.
- FE 검증 범위는 React/Vue 컴포넌트와 명시된 compiler/runner다. Next/Nuxt 전체 앱, SSR, Storybook 브라우저 검증을 수행한 것은 아니다.
- 페이지네이션의 hp1 cursor는 CloudKit 기존 wire format과 다르다. 실제 CloudKit parser/codec의 한계를 확인했고 적용 시 migration/adapter 검증이 필요하다.
- GitHub hosted CI 실행과 보호 브랜치 설정은 수행하지 않았다. 저장소에 추가한 동일 검증 entrypoint의 로컬 실행 결과를 기록한다.
- 파일 경합에서 POSIX의 비협조 writer에 대한 완전한 CAS 보장을 주장하지 않는다. 게시 여부가 불확실한 경우 UNKNOWN으로 구분하고 실패 재시도로 인한 중복을 피한다.
