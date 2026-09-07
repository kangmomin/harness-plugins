# 전체 하네스 감사 보고서

감사 시작: 2026-09-05 · 최종 정리: 2026-09-06 (Asia/Seoul)

기준 저장소: `/workspace/harness-plugins` · 브랜치 `main` · HEAD `f9ce681427ccfbfd9194d3c3f204a445ae6f45dd`

## 1. 결과와 우선순위

구체적인 결함·실행 계약 불일치 **41건(P1 8건, P2 31건, P3 2건)**과 별도 설계·운영 개선 **30건(I01–I18, D01–D12)**을 정리했다. 문서형 스킬의 계약 불일치와 실제 실행 재현을 각 항목에 구분했다. 41건 모두가 운영 환경에서 발생한 장애나 실제 모델이 재현한 버그라는 뜻은 아니다.

기존 Python 32개·Node 23개 테스트는 모두 통과했다. 구조 검사와 6개 플러그인 manifest 검증도 통과했지만 아래 결함을 차단하지 못했다. 감사 중 제품 소스는 수정하지 않았으며, 산출물은 이 보고서와 [검증 근거 JSON](/workspace/harness-plugins/docs/harness-audit-2026-09-05-evidence.json)이다.

P1은 데이터·원격 대상·커밋 범위 또는 검증 결과의 신뢰성에 직접 영향을 주어 우선 수정할 항목이다. P2는 조건부 동작 오류와 중요한 계약 공백, P3는 진단·정리·문서 개선이다. 별도 개선 목록의 I01도 검토한 merge SHA를 고정하는 P1 예방 조치다. 우선순위는 발생 가능성과 영향을 함께 본 판단이며 보안 취약점 점수는 아니다.

| 우선 항목 | 발생 조건과 영향 | 근거 |
|---|---|---|
| [W01](#w01) | 잠금 대기 중 로컬 디렉터리 교체 → vault 밖 파일 쓰기 | 실행 재현·이전 감사 |
| [T01](#t01) | Vitest 다른 파일의 동명 테스트 → 바뀐 실패를 기존 실패로 분류 | 실행 재현 |
| [T02](#t02) | Jest 실제 assertion 값 변화 → regression 0으로 분류 | 실행 재현 |
| [E01](#e01) | REST+gRPC에서 HTTP만 검사 → 미호출 RPC를 빼고 OK 보고 | 실행 재현·이전 감사 |
| [E02](#e02) | 동일 서버의 loopback 별칭 → E2E 실행 두 개가 동시에 잠금 획득 | 실행 재현·이전 감사 |
| [C01](#c01) | 기존 staged 파일+--bump-only → 무관한 파일도 범프 커밋에 포함 | 실행 재현 |
| [M01](#m01) | 테스트 중 다른 writer가 INSERT → cleanup이 그 데이터도 soft-delete | SQL fixture + 계약 검토 |
| [M02](#m02) | Apidog 실패 후 프로젝트 설정 불일치 → 재시도 대상 프로젝트 변경 | 계약 결함 |

## 2. 범위·독립 검토·검증 결과

전체 추적 파일 **176개·27,857줄**, SKILL.md **51개**, agent **14개**를 목록화하고 SHA-256 기준을 보관했다. 모든 제품의 구조·manifest·참조·중복 자산을 검사하고, 주요 실행 경로를 수동으로 교차 검토했다. common 23개 파일은 독립 리뷰어가 전문을 읽었다. 나머지 모든 176개 파일을 동일 깊이로 줄마다 읽거나 모든 스킬을 모델로 실행했다고 주장하지 않는다.

| 범위 | 파일/줄 수 | 수행한 검토 | 실행 범위와 한계 |
|---|---:|---|---|
| 공용 common | 23 / 3,632 | 독립 전문 리뷰: Git·PR·merge·라우터·fullstack·archive·resume·문서 생성 | 로컬 Git/Python 11개 assertion; GitHub 원격·모델 동작 미실행 |
| BE | 43 / 8,335 | workflow·품질 범위·실패 분류·E2E 잠금/renderer·profile·agent 계약 | Python 기본 테스트·실제 JS 로그·로컬 socket; 소비 API 서버 전체 E2E 아님 |
| FE | 41 / 7,323 | BE와의 차이·review 후 재검증·lint·framework/runner·PR 계약 | 공통 helper parity·기본 테스트; 실제 생성 앱/브라우저 미실행 |
| minmos | 27 / 3,814 | overlay·DB 정리·RPC·Apidog 추출/import·hook·페이지네이션 | 로컬 Git/jq/SQLite fixture; 실제 Apidog·PostgreSQL·CloudKit 미실행 |
| hyeondongs | 7 / 551 | 상속/legacy profile·doctor·runner 진단 계약 | 정적 검토·manifest 검사; 사용자 FE 프로젝트 진단 미실행 |
| work-log | 19 / 2,535 | 설정·MCP 쓰기·파일 경계·잠금·스캔/검색·문서/링크 | Node 23개와 별도 파일/MCP fixture; 대규모 성능 실측 없음 |
| scripts/tests | 9 / 676 | 구조 guard·복제본 동기화·테스트가 확인하는 계약 | Python 32개; 구조 검사는 독립 snapshot에서 실행 |
| 루트/기존 docs | 7 / 991 | marketplace·README·기존 문서의 구조·연결 확인 | 역사 문서를 현재 실행 명세로 취급하지 않음 |

작업은 R1 목록/구조(하), R2 실행·호출 계약(상), R3 재현(상), R4 개선안·공백 분류(중), R5 기본 검증(중), R6 독립 대조·보고/정리(중)로 나눴다. 구현 계획 승인이 필요한 제품 변경은 수행하지 않았다.

독립 리뷰는 외부 CLI 리뷰어를 쓰지 않고 fresh-context 서브에이전트 1개로 진행했다. staged/dirty·VERSION 부재·하위 cwd·기존 PR·base 변경을 분리하고, common/BE/FE Phase 상태를 교차 대조하라는 사전 피드백을 반영했다. 오케스트레이터는 C04의 BE가 literal main을 쓰지 않는 점과 FE의 폴백을 반영하고, 실제 모델 미실행인 C04/C07의 영향을 한정해 P2로 조정했다. 최종 독립 대조에서는 표 렌더링과 T02의 Expected/Received 표현을 바로잡고, C08의 queue 조건을 gh 공식 소스에 맞춰 이미 queue에 있는 PR로 한정했다.

| 검증 | 결과 | 해석 |
|---|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` | 32 PASS | 기존 Python 테스트 전체, 약 0.815초 |
| `node --test work-log/tests/*.test.js` | 23 PASS | 기존 Node 테스트 전체, 약 5.625초 |
| `bash scripts/check-plugins.sh` | exit 0 / OK | 추적 파일 독립 snapshot에서 실행. S01의 무관한 파일 삭제도 관찰 |
| `claude plugin validate <plugin-root>` × 6 | 모두 exit 0 | author 누락 경고 전부, BE/FE의 upstream 필드 미지원 경고. agent 도구 제한 검증은 아님 |
| 공용 Git/아카이브 fixture | 11 assertion PASS | 결함 발생을 기대한 재현 assertion이며 결함 수정 PASS가 아님 |
| 실제 JS runner | Vitest 4.1.10, Jest package 30.2.0 | 실패 테스트를 의도적으로 실행해 T01/T02/T03 오분류 재현. Jest CLI 버전 표시는 30.1.3 |

Manifest/marketplace의 이름·경로·버전 연결과 BE/FE/common 복제 자산의 parity를 확인했다. 제품 버전은 common 0.14.1, BE 1.5.3, FE 1.4.2, minmos 2.5.1, hyeondongs 3.0.0, work-log 0.2.2다. `claude plugin validate`는 로컬 manifest 검사이며 외부 모델 리뷰를 호출하지 않았다.

## 3. 발견사항 전체 목록

| ID | 우선순위 | 항목 | 확인 방식 |
|---|---|---|---|
| [C01](#c01) | P1 | --bump-only가 기존 staged 파일도 커밋한다 | 실행 재현 |
| [E01](#e01) | P1 | gRPC 대상이 E2E 보고서 분모에서 사라져 미검증을 성공으로 보고 | 실행 재현·이전 감사 |
| [E02](#e02) | P1 | 동일 포트의 localhost와 127.0.0.1이 서로 다른 E2E 잠금을 획득 | 실행 재현·이전 감사 |
| [M01](#m01) | P1 | E2E 정리 SQL이 다른 작업의 새 데이터까지 soft-delete | SQL fixture + 계약 검토 |
| [M02](#m02) | P1 | Apidog 재시도에서 대상 프로젝트를 자동으로 바꿔 쓰기 | 계약 결함 |
| [T01](#t01) | P1 | Vitest 동일 제목의 실패 메시지가 다른 파일의 메시지로 덮임 | 실행 재현 |
| [T02](#t02) | P1 | Jest의 첫 줄만 비교해 실제 단언 값 변화가 회귀에서 빠짐 | 실행 재현 |
| [W01](#w01) | P1 | 문서 잠금 대기 중 디렉터리 교체로 vault 밖 쓰기 | 실행 재현·이전 감사 |
| [A01](#a01) | P2 | 14개 agent의 도구 제한 frontmatter가 공식 필드와 다름 | 공식 계약 + 전체 agent 대조 |
| [C02](#c02) | P2 | PR base 결정이 VERSION 존재에 종속되고 루트 버전 경로가 cwd에 따라 바뀐다 | 계약 결함 + 실행 재현 |
| [C03](#c03) | P2 | BE/FE workflow-pr의 커밋·버전·base 계약이 common 절차와 갈라졌다 | 계약 결함 + Git 상태 재현 |
| [C04](#c04) | P2 | Read-back의 브랜치 기준 diff가 --hard·FE/FS 비-main 저장소에서 증거를 누락 | 실행 재현 |
| [C05](#c05) | P2 | 아카이브가 다른 Phase와 과거 회귀 건수를 최종 결과로 요약한다 | 실행 재현 |
| [C06](#c06) | P2 | 아카이브 재시도는 DEGRADED를 OK로 바꾸고 입력 run_id 충돌은 중복 파일을 만든다 | 실행 재현 |
| [C07](#c07) | P2 | --fs --analyze/--verify를 막지 않아 읽기 요청이 Build 경로로 갈 수 있다 | 계약 결함 |
| [C08](#c08) | P2 | 이미 queue에 있는 PR을 머지 완료로 오보고하고 base HEAD를 PR merge SHA로 사용 | 공식 CLI 소스 + 계약 검토 |
| [C09](#c09) | P2 | resolve-assumption의 경로 필터가 untracked 검색에 빠져 있다 | 실행 재현 |
| [E03](#e03) | P2 | E2E 수정 기록이 실패한 케이스가 아니라 마지막 케이스에 붙음 | 실행 재현·이전 감사 |
| [F01](#f01) | P2 | 설정에서 지원하는 Nuxt·JavaScript와 FE 생성 템플릿이 맞지 않음 | 계약 결함 |
| [M03](#m03) | P2 | OpenAPI 3.0 payload에 지원되지 않는 nullable type 배열을 생성 | 공식 명세 + 계약 검토 |
| [M04](#m04) | P2 | API push가 성공 응답을 200으로 고정 | 계약 결함 |
| [M05](#m05) | P2 | worktree 초기화 hook이 공백 경로·설정 파일 없는 첫 설치에서 실패 | 실행 재현 |
| [M06](#m06) | P2 | 페이지네이션 템플릿의 tie-breaker가 다음 커서에 포함되지 않음 | SQL fixture + 템플릿 검토 |
| [M07](#m07) | P2 | snake_case 변환이 SQL Injection을 방지한다는 잘못된 안내 | 공식 문서 + 템플릿 검토 |
| [M08](#m08) | P2 | Apidog·Proto 도구 참조가 환경 탐색/현재 설치 구조와 불일치 | 정적 대조·설치 파일 확인 |
| [M09](#m09) | P2 | Apidog 검증 payload가 실행별로 격리되지 않아 다른 실행 내용으로 바뀜 | 계약 결함 |
| [Q01](#q01) | P2 | dirty 상태에서 이미 커밋한 구현이 품질 검사 범위에서 누락 | 실행 재현·이전 감사 |
| [Q02](#q02) | P2 | FE 컴포넌트·접근성 수정 후 빌드/테스트 재검증 단계가 없음 | 계약 결함 |
| [Q03](#q03) | P2 | FE lintCommand 설정을 실제 lint 단계가 사용하지 않음 | 계약 결함 |
| [T03](#t03) | P2 | 다른 파일의 동명 테스트 PASS가 원래 실패를 flaky로 만듦 | 실행 재현 |
| [W02](#w02) | P2 | title 메타데이터의 타입 오류가 vault 전체 동기화를 중단 | 실행 재현·이전 감사 |
| [W03](#w03) | P2 | 저장 성공 뒤 인덱싱 실패를 전체 쓰기 실패로 응답 | 실행 재현·이전 감사 |
| [W04](#w04) | P2 | append/overwrite가 기존 파일 접근 권한을 완화 | 실행 재현·이전 감사 |
| [W05](#w05) | P2 | 인덱스 잠금을 시간만으로 탈취해 최신 결과를 과거 결과로 덮어씀 | 실행 재현·이전 감사 |
| [W06](#w06) | P2 | 공백·한글 설치 경로에서 설정 CLI가 출력 없이 종료 | 실행 재현 |
| [W07](#w07) | P2 | null/false 설정을 무시하고 다른 vault로 폴백 | 실행 재현 |
| [W08](#w08) | P2 | 코드 블록의 # 줄을 제목으로 처리해 섹션을 잘라냄 | 실행 재현 |
| [W09](#w09) | P2 | 읽기 권한 오류를 삭제로 보고 정상 인덱스로 저장 | 실행 재현 |
| [W10](#w10) | P2 | 잘못된 경로의 위키 링크를 다른 파일에 연결 | 실행 재현 |
| [F02](#f02) | P3 | hyeondongs doctor가 정상 현대 profile·선택 설정을 누락으로 보고 | 계약 결함 |
| [S01](#s01) | P3 | 구조 검사 cleanup이 자신이 만들지 않은 __pycache__도 삭제 | 실행 재현 |

이하의 “실행 재현·이전 감사”는 같은 HEAD에서 앞선 감사 중 수행한 실험이다. 이번 최종 보고서 조립 때 반복 실행하지 않았다. W01의 경로 교체는 같은 로컬 사용자의 조작 조건, W05의 6분 경과는 mtime 조정, SQL fixture는 SQLite 조건 검증이라는 한계를 유지한다. 수정 후 검증 항목은 후속 수정의 완료 기준이며 이번에 통과시켰다는 뜻이 아니다.

<a id="c01"></a>

### C01 · P1 · --bump-only가 기존 staged 파일도 커밋한다

근거: [common/skills/commit-pr/SKILL.md:92](/workspace/harness-plugins/common/skills/commit-pr/SKILL.md:92) · **실행 재현**

- 위치: [common/skills/commit-pr/SKILL.md:92](/workspace/harness-plugins/common/skills/commit-pr/SKILL.md:92), 기본 커밋 절차 [common/skills/commit/SKILL.md:29](/workspace/harness-plugins/common/skills/commit/SKILL.md:29).
- 조건: 사용자가 다른 변경을 이미 stage한 상태에서 `--bump-only` 실행.
- 원인: `git add VERSION`은 index의 다른 엔트리를 제외하지 않는다. 이후 일반 `git commit`은 index 전체를 커밋한다.
- 재현: unrelated.txt를 미리 stage → VERSION만 수정/add → 범프 커밋. `git show --name-only HEAD`에 `VERSION`, `unrelated.txt`가 함께 나타났다.
- 영향: “코드 변경 커밋 없이 VERSION만”이라는 범위를 위반하며, 요청하지 않은 staged 코드까지 다음 push에 포함된다.
- 수정: 기존 index 보존·복원 또는 commit pathspec/임시 index로 대상 파일만 커밋하고 결과 tree 범위를 확인한다. `resolve-assumption`의 amend/soft-reset과 논리 단위 commit에도 staged 내용 격리 계약을 공통 적용할 수 있다. clean-tree 선행 조건이 있는 sync-base는 같은 빈도로 발생한다고 주장하지 않는다.

**수정 후 검증:** VERSION 외 staged/unstaged 변경을 함께 준비한다. 범프 커밋은 버전 파일만 포함하고 기존 index/worktree 상태는 보존돼야 한다.

<a id="e01"></a>

### E01 · P1 · gRPC 대상이 E2E 보고서 분모에서 사라져 미검증을 성공으로 보고

근거: [be-harness/skills/e2e-test-loop/assets/render_e2e_report.py:35](/workspace/harness-plugins/be-harness/skills/e2e-test-loop/assets/render_e2e_report.py:35) · **실행 재현·이전 감사**

minmos는 같은 renderer를 쓰지만 REQ_RE는 HTTP method만 인식한다. gRPC-only 대상/통과 케이스는 대상 0건 DEGRADED가 된다. 더 위험하게 GET /healthz와 GRPC user.v1.UserService/GetUser를 대상으로 두고 HTTP만 실행하면 대상 1, 호출 1, 미호출 0, 상태 OK·직답 예가 나온다. RPC 실패를 숨긴 실험이 아니라 RPC를 아예 검증하지 않았는데 분모에서 누락된 실험이다.

**수정 방향:** protocol+operation 구조로 REST/RPC 대상을 저장하고 미지원 프로토콜도 분모에 보존한다. grpc-only, mixed partial, streaming skip을 각각 검증한다.

**수정 후 검증:** REST-only/GRPC-only/MIXED에서 총 대상 수가 입력과 일치해야 한다. 혼합 대상 중 RPC 미호출은 OK/직답 예가 될 수 없어야 한다.

<a id="e02"></a>

### E02 · P1 · 동일 포트의 localhost와 127.0.0.1이 서로 다른 E2E 잠금을 획득

근거: [be-harness/skills/e2e-test/assets/e2e-lock.sh:86](/workspace/harness-plugins/be-harness/skills/e2e-test/assets/e2e-lock.sh:86) · **실행 재현·이전 감사**

호스트 문자열만 파일명으로 정규화해 localhost:PORT와 127.0.0.1:PORT에서 서로 다른 실행 토큰 둘 다 ACQUIRED가 된다. 실제 127.0.0.1 socket에 localhost 연결 성공 및 두 번째 bind의 EADDRINUSE까지 확인했다. 같은 네트워크 namespace·bind 대상이라는 조건에서 서버/바이너리/DB 병렬 충돌을 막지 못한다. FE 사본도 동일하다.

**수정 방향:** 논리 URL 대신 실제 점유 자원(namespace/bind 주소/포트)을 기준으로 lock key를 확정한다. loopback·wildcard·기본 포트·별도 gRPC 포트와 공통 lock root를 함께 설계한다.

**수정 후 검증:** 같은 실제 socket을 가리키는 loopback 별칭 두 개에서는 소유자 하나만 획득해야 한다. 다른 namespace나 실제 독립 서버는 불필요하게 막지 않는지도 확인한다.

<a id="m01"></a>

### M01 · P1 · E2E 정리 SQL이 다른 작업의 새 데이터까지 soft-delete

근거: [minmos-harness/overlay/references/e2e-test-postmath.md:330](/workspace/harness-plugins/minmos-harness/overlay/references/e2e-test-postmath.md:330) · **SQL fixture + 계약 검토**

삭제 API가 없는 경우 WHERE id > BASELINE_ID로 일괄 정리하고 자식 테이블도 같은 부모 집합을 따른다. baseline=10 이후 테스트가 11, 다른 writer가 12를 만들면 둘 다 removed가 된다. SQLite 메모리 fixture로 이 WHERE 조건의 대상을 확인했고 실제 PostgreSQL/업무 DB에는 접근하지 않았다. 호스트별 E2E 잠금은 일반 사용자나 다른 포트의 같은 DB writer를 막지 않는다.

**수정 방향:** INSERT/API 응답에서 얻은 정확한 생성 ID를 run_id별로 추적하고 그 집합만 역 FK 순서로 정리한다. MAX(id)는 참고값으로만 쓰며 소유권 판정에 사용하지 않는다.

**수정 후 검증:** 테스트 writer와 일반 writer를 교차 실행해 cleanup 후 테스트 소유 ID만 removed인지 확인한다. 실제 PostgreSQL에서는 FK·trigger·soft-delete까지 추가 검증한다.

<a id="m02"></a>

### M02 · P1 · Apidog 재시도에서 대상 프로젝트를 자동으로 바꿔 쓰기

근거: [minmos-harness/skills/apidog-schema-gen/references/push-import.md:192](/workspace/harness-plugins/minmos-harness/skills/apidog-schema-gen/references/push-import.md:192) · **계약 결함**

REST 요청이 실패하면 APIDOG_PROJECT_ID와 MCP 설정의 project-id가 다를 때 MCP 값을 우선 사용하도록 지시한다. A 프로젝트를 의도한 환경에서 인증/전송 실패 후 B MCP 설정을 찾으면 같은 schema를 B에 OVERWRITE_EXISTING으로 보낼 수 있다. e2e-apidog-schema-gen:347에도 같은 절차다. 원격 import는 실행하지 않았다.

**수정 방향:** 처음 확정한 project/branch/endpoint를 불변으로 유지한다. 인증 수단을 교체할 때도 같은 대상임을 검증하고, 다른 프로젝트로의 전환은 별도 대상 변경으로 다룬다.

**수정 후 검증:** 대상 A 확정 후 A의 인증·전송 실패와 B의 MCP 설정을 제공한다. 재시도 요청 target은 A로 유지되거나 실패해야 하며 B로 전송되면 안 된다.

<a id="t01"></a>

### T01 · P1 · Vitest 동일 제목의 실패 메시지가 다른 파일의 메시지로 덮임

근거: [be-harness/skills/start-workflow/assets/test_failures.py:214](/workspace/harness-plugins/be-harness/skills/start-workflow/assets/test_failures.py:214) · **실행 재현**

FAIL 헤더에서 파일명(group 1)을 버리고 describe/it 제목만 msgs 키로 쓴다. 실제 Vitest 4.1.10에서 a.test.js와 b.test.js의 같은 제목을 실패시킨 뒤 a의 구현만 변경해도 두 실패가 모두 pre_existing, regression 0, unparsed 0이었다. 이 버전의 verbose 실패 ID에는 파일명이 들어 있으므로 ID 자체가 합쳐졌다는 설명은 잘못이며 메시지 매핑 충돌이 원인이다. FE 사본도 동일하다.

**수정 방향:** 파일명+전체 describe/it 경로를 메시지·baseline·Test Map에 일관되게 사용하고 suffix 추정 매칭을 제거한다. 복수 파일의 동일 제목을 실제 러너 fixture로 검증한다.

**수정 후 검증:** 실제 Vitest의 서로 다른 파일에 같은 전체 테스트 제목을 두고 한 파일의 assertion 결과만 바꾼다. 그 파일만 변경된 시그니처와 regression을 가져야 한다.

<a id="t02"></a>

### T02 · P1 · Jest의 첫 줄만 비교해 실제 단언 값 변화가 회귀에서 빠짐

근거: [be-harness/skills/start-workflow/assets/test_failures.py:183](/workspace/harness-plugins/be-harness/skills/start-workflow/assets/test_failures.py:183) · **실행 재현**

실제 Jest 패키지 30.2.0(CLI --version 출력 30.1.3)에서 expect(value()).toBe(1) 테스트는 유지하고 value 구현만 2→4로 바꿨다. Expected는 1로 같고 Received가 2→4로 달라지지만 수집 시그니처는 expect(received).toBe(expected) // Object.is equality로 동일해 pre_existing 1, regression 0으로 분류됐다. 일반 matcher 실패에서 첫 줄은 실제 오류 값이 아니다.

**수정 방향:** matcher와 Expected/Received 등 의미 있는 오류 본문을 시그니처에 포함한다. 구조화된 JSON reporter의 failureMessages를 활용하고 경로·시간 같은 잡음만 제거한다.

**수정 후 검증:** 테스트 소스는 그대로 둔 채 구현 반환값 2→4, 예외 메시지 변화, matcher 변화 로그를 비교한다. 의미 있는 값 변화는 동일 baseline으로 통과시키지 않는다.

<a id="w01"></a>

### W01 · P1 · 문서 잠금 대기 중 디렉터리 교체로 vault 밖 쓰기

근거: [work-log/mcp/lib/vault.js:557](/workspace/harness-plugins/work-log/mcp/lib/vault.js:557) · **실행 재현·이전 감사**

safeResolve 후 문서 잠금을 기다리는 동안 경로를 다시 검증하지 않는다. 별도 프로세스가 vault/sub를 옮기고 같은 위치를 외부 디렉터리 심볼릭 링크로 바꾸면, 대기 중인 append가 외부 파일에 반영된다. 원본 vault 문서는 그대로이고 외부 파일만 바뀌는 것을 확인했다. 같은 로컬 사용자가 경로를 바꿀 수 있는 조건의 TOCTOU이며, 원격 공격 경로를 재현한 것은 아니다.

**수정 방향:** 잠금 획득 후 및 실제 파일 생성·교체 시점의 경로/inode를 검증하고, 심볼릭 링크를 따르지 않는 안전한 I/O 경계를 사용한다. 단순히 검사 위치만 뒤로 옮기는 것으로 경합 전체가 해결됐다고 보지 않는다.

**수정 후 검증:** 별도 프로세스가 잠금 대기 전후·임시 파일 생성 전후에 디렉터리를 symlink로 바꿔도 외부 파일 해시가 그대로이고 쓰기는 명확히 실패해야 한다.

<a id="a01"></a>

### A01 · P2 · 14개 agent의 도구 제한 frontmatter가 공식 필드와 다름

근거: [be-harness/agents/scope-reviewer.md:4](/workspace/harness-plugins/be-harness/agents/scope-reviewer.md:4) · **공식 계약 + 전체 agent 대조**

BE 7개·FE 6개·minmos 1개 agent가 모두 allowed-tools를 쓰고 tools를 선언하지 않는다. 공식 Claude Code subagent 계약은 tools/disallowedTools이며 tools 부재 시 가능한 도구를 상속한다. 스킬용 allowed-tools를 agent에 사용해 의도한 읽기 전용 제한이 공식 계약상 설정되지 않은 상태다. 실제 에이전트의 무단 쓰기는 실행하지 않았다. [Claude Code subagent frontmatter](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields)

**수정 방향:** agent frontmatter를 tools/disallowedTools로 검증하고 host loader에서 실제 도구 목록을 확인한다. FE 병렬 리뷰 프롬프트의 상태 파일 쓰기는 오케스트레이터로 옮겨 읽기 전용 역할과 맞춘다. Bash를 허용하면 파일 쓰기도 가능하다는 범위도 구별한다.

**수정 후 검증:** 설치된 host에서 실제 로드된 agent의 도구 목록을 확인한다. frontmatter validator로 잘못된 필드를 차단하고 읽기 전용 역할의 쓰기 경로를 점검한다.

<a id="c02"></a>

### C02 · P2 · PR base 결정이 VERSION 존재에 종속되고 루트 버전 경로가 cwd에 따라 바뀐다

근거: [common/skills/commit-pr/SKILL.md:45](/workspace/harness-plugins/common/skills/commit-pr/SKILL.md:45) · **계약 결함 + 실행 재현**

- 위치: [common/skills/commit-pr/SKILL.md:45](/workspace/harness-plugins/common/skills/commit-pr/SKILL.md:45), `:47`, `:51`, `:69`.
- 조건 A: VERSION/VERSION.txt가 없는 일반 프로젝트. Step 2 전체를 SKIP하지만 Step 4는 “Step 2에서 결정한 base”를 요구한다.
- 조건 B: 저장소 하위 디렉터리에서 실행. 대상은 루트 VERSION인데 `git rev-parse --show-prefix`를 붙여 `sub/VERSION`을 조회한다.
- 재현 B: origin/main에는 루트 VERSION=`2.0.0`이 존재했지만 제공된 명령은 `fatal: path 'sub/VERSION' does not exist in 'origin/main'`, exit 128을 반환했다.
- 영향: A는 base 미정/잘못된 기본 브랜치 사용, B는 정상 원격을 조회 실패로 오판하여 로컬 patch 폴백. 배포 브랜치와 VERSION 비교 기준이 달라질 수 있다.
- 수정: 저장소 루트·확정 브랜치 prefix·base resolve를 버전 존재 검사보다 앞선 독립 단계로 두고, 루트 상대 VERSION 경로를 사용한다. base 변경을 허용할 때에는 VERSION 계산도 새 base로 갱신해야 한다.
- 같은 경로의 추가 공백: 기존 open PR 경로(`:39`)는 base VERSION 비교 전에 fetch를 명시하지 않는다. 신규 PR의 “바로 상위 브랜치”에도 결정적인 Git 근거/폴백 순서가 없다. sync-base에는 PR base→origin/HEAD 순서가 있으므로 공통화할 수 있다.

**수정 후 검증:** VERSION 없음·VERSION.txt·하위 cwd·비-main 기본 브랜치·기존 PR·remote 버전 선행을 표로 묶어 같은 base resolver를 검증한다.

<a id="c03"></a>

### C03 · P2 · BE/FE workflow-pr의 커밋·버전·base 계약이 common 절차와 갈라졌다

근거: [be-harness/agents/workflow-pr.md:24](/workspace/harness-plugins/be-harness/agents/workflow-pr.md:24) · **계약 결함 + Git 상태 재현**

- 위치: [be-harness/agents/workflow-pr.md:24](/workspace/harness-plugins/be-harness/agents/workflow-pr.md:24), [fe-harness/agents/workflow-pr.md:24](/workspace/harness-plugins/fe-harness/agents/workflow-pr.md:24) (양쪽 동일 실행 3~7단계), [be-harness/skills/start-workflow/references/agent-prompts.md:209](/workspace/harness-plugins/be-harness/skills/start-workflow/references/agent-prompts.md:209), [fe-harness/skills/start-workflow/references/agent-prompts.md:328](/workspace/harness-plugins/fe-harness/skills/start-workflow/references/agent-prompts.md:328).
- 조건: PR 에이전트가 VERSION을 수정하거나, 품질 단계가 미커밋 변경을 남긴 상태에서 PR 생성. 또는 remote base 버전이 로컬보다 높은 상태/재개 시 이미 PR이 존재하는 상태.
- 원인: VERSION local patch+1 → 브랜치 생성 → `base...HEAD` Assumption Gate → push 순서에 커밋 단계가 없다. common:commit-pr 위임·base 확정·VERSION.txt·기존 PR 처리도 없다. 부모 프롬프트가 이 계약을 보완하지 않는다.
- 재현: fixture에서 미커밋 VERSION/handler의 `[Assumption]`을 두고 문서의 Gate를 실행하면 stdout 0건; `HEAD:handler.go`는 없고 파일은 작업 트리에 남는다. 원격 push는 실행하지 않았다.
- 영향: 문서 순서를 그대로 따르면 VERSION/품질 수정은 원격에 포함되지 않는다. 에이전트가 “모든 변경 push”를 만족하려고 Gate 이후 커밋을 추론하면 검사하지 않은 태그가 커밋될 수 있다. 후자는 실행 위험 추론이며 실제 원격 유출 재현으로 표현하지 않는다.
- 수정: PR 전용 에이전트가 common의 base/버전/커밋/Gate/기존-PR 절차를 명시적으로 재사용하고, `commit → 검증한 HEAD의 Gate → push` 순서를 고정한다. 재개는 이미 완료한 branch/VERSION/PR 단계를 재실행하지 않아야 한다(`finalization.md:7`의 중복 금지와 연결).

**수정 후 검증:** PR 직전 미커밋 변경과 VERSION 수정이 있는 상태에서 commit→Gate→push 순서를 추적한다. 재개 시 기존 branch/버전/PR을 중복 생성하지 않아야 한다.

<a id="c04"></a>

### C04 · P2 · Read-back의 브랜치 기준 diff가 --hard·FE/FS 비-main 저장소에서 증거를 누락

근거: [common/skills/start-workflow/references/fullstack-agent-prompts.md:138](/workspace/harness-plugins/common/skills/start-workflow/references/fullstack-agent-prompts.md:138) · **실행 재현**

- 위치: [common/skills/start-workflow/references/fullstack-agent-prompts.md:138](/workspace/harness-plugins/common/skills/start-workflow/references/fullstack-agent-prompts.md:138), `:170`; FE [fe-harness/skills/start-workflow/references/agent-prompts.md:182](/workspace/harness-plugins/fe-harness/skills/start-workflow/references/agent-prompts.md:182); BE [be-harness/skills/start-workflow/references/quality-loop.md:196](/workspace/harness-plugins/be-harness/skills/start-workflow/references/quality-loop.md:196).
- 조건 A: 기본 브랜치가 master/dev이고 로컬 main이 없음. 조건 B: `--hard`로 현재 main에 커밋. 조건 C: 오래된 main을 기준으로 dev에서 분기한 작업.
- 재현: A는 exit 128로 범위 조회 실패; B는 실제 handler.go 변경이 있어도 stdout이 빈 문자열이다(현재 main=HEAD). START_SHA로 계산하면 handler.go가 나온다.
- 영향: 풀스택 계약 격리 검증이 멈추거나 빈 범위를 정상으로 오해하고 변경을 놓친다. FE도 literal main을 쓰지만 E2E/공개 인터페이스 폴백이 있으므로 우선 테스트 증거가 누락되는 영향이다. BE는 literal main이 아닌 `{mainBranch}`지만 --hard로 그 브랜치에 직접 커밋하면 같은 빈 범위가 된다. C는 이번 작업과 무관한 base 변경까지 들어온다. 이미 알려진 dirty simplify 범위 누락과는 다른 호출자의 검증 범위 결함이다.
- 수정: 오케스트레이터가 START_SHA/작업 allowlist와 현재 tracked·untracked 변경을 반영한 읽기 대상 경로를 계산해 프롬프트에 제공한다. 격리 원칙 때문에 상태 파일은 넘기지 않고 경로 목록만 전달한다. ref 오류와 “변경 0건”을 분리한다.

**수정 후 검증:** 기본 브랜치 master/dev, 현재 main에 직접 커밋한 --hard, 오래된 main을 가진 저장소에서 START_SHA 이후 변경을 모두 읽어야 한다.

<a id="c05"></a>

### C05 · P2 · 아카이브가 다른 Phase와 과거 회귀 건수를 최종 결과로 요약한다

근거: [common/skills/start-workflow/assets/workflow_archive.py:159](/workspace/harness-plugins/common/skills/start-workflow/assets/workflow_archive.py:159) · **실행 재현**

- 위치: [common/skills/start-workflow/assets/workflow_archive.py:159](/workspace/harness-plugins/common/skills/start-workflow/assets/workflow_archive.py:159), `:165`, `:169`, `:218`; BE/FE assets 파일도 바이트 동일.
- 원인: MODE와 무관하게 BE의 8.1·8.6만 읽고, regression_count는 상태 전문의 첫 정규식 매치를 사용한다.
- 재현 1: BE 상태에 `8.1 FAIL regression 2건` 다음 `8.1 PASS regression 0건`을 넣으면 `regression_count: 2`, `최종 테스트 판정(8.1): PASS · regression: 2`를 쓰고 `상태: OK`를 반환한다.
- 재현 2: FE의 7.1 PASS/7.4 E2E PASS를 주면 양쪽 “기록 없음”; 풀스택 Phase 7 BE/FE PASS + 8.1 Read-back WARN을 주면 “최종 테스트 판정: WARN”으로 기록한다.
- 영향: 보존되는 보고서 요약·frontmatter가 실제 마지막 검증 상태와 다르다. 원문 부록은 남지만 사용자가 요약만 읽거나 인덱스에서 집계하면 잘못된 결과를 얻는다.
- 수정: MODE별 명시 결과 필드(가능하면 JSON/구조화된 최종 summary)를 읽고, 마지막 완료 검증 회차의 판정·회귀 수를 함께 추출한다. 테스트·Read-back·E2E는 다른 필드로 유지한다.

**수정 후 검증:** BE 실패 후 성공, FE 최종 테스트, FS Read-back WARN 입력에서 각각 마지막 테스트 수·E2E·Read-back이 독립적으로 정확히 보존돼야 한다.

<a id="c06"></a>

### C06 · P2 · 아카이브 재시도는 DEGRADED를 OK로 바꾸고 입력 run_id 충돌은 중복 파일을 만든다

근거: [common/skills/start-workflow/assets/workflow_archive.py:188](/workspace/harness-plugins/common/skills/start-workflow/assets/workflow_archive.py:188) · **실행 재현**

- 위치: [common/skills/start-workflow/assets/workflow_archive.py:188](/workspace/harness-plugins/common/skills/start-workflow/assets/workflow_archive.py:188), `:190`, `:238`, `:242`; BE/FE 동일.
- 재현 A: 필수 헤더 누락으로 첫 실행은 DEGRADED, 같은 인수로 다시 실행하면 INCOMPLETE 본문 그대로인데 `상태: OK(재사용…)`.
- 재현 B: src frontmatter run_id=old-run, CLI run-id=new-run이면 기존 run_id를 유지한 파일이 생성된다. 동일 호출 재시도는 해당 파일을 같은 실행으로 인식하지 못해 `-2.md`를 추가 생성한다.
- 영향: 재개/재시도 시 미완전 산출물이 정상으로 보이거나 실행당 보고서 1개라는 기대가 깨진다.
- 수정: 입력·상태·CLI run_id 일치를 검증하거나 명시적 소유 필드로 덮어쓰고, 저장된 산출물의 completeness/status를 재사용 때에도 그대로 반환한다. 날짜·task 변경 재시도도 RUN_ID 기준 식별을 검토한다(후자는 개선 제안, 날짜 변경 재현은 하지 않음).

**수정 후 검증:** DEGRADED 산출물을 재사용해도 DEGRADED가 유지돼야 한다. CLI/입력 run_id 불일치는 오류나 명시적 정규화로 처리하고 재시도 산출물은 하나여야 한다.

<a id="c07"></a>

### C07 · P2 · --fs --analyze/--verify를 막지 않아 읽기 요청이 Build 경로로 갈 수 있다

근거: [common/skills/start-workflow/SKILL.md:30](/workspace/harness-plugins/common/skills/start-workflow/SKILL.md:30) · **계약 결함**

- 위치: [common/skills/start-workflow/SKILL.md:30](/workspace/harness-plugins/common/skills/start-workflow/SKILL.md:30), `:52`, `:135`; [common/skills/start-workflow/references/fullstack.md:25](/workspace/harness-plugins/common/skills/start-workflow/references/fullstack.md:25), `:199`, `:296`.
- 조건: explicit `--fs --analyze` / `--fs --verify`, 또는 Analyze 요청을 자동 도메인 판정에서 풀스택으로 선택.
- 원인: 라우터는 대상 고유 플래그를 해석하지 않고 전달하지만, fs 플래그/모드 표에는 analyze/verify 처리나 지원하지 않는 조합 차단이 없다. fs는 Phase 5 브랜치, 6 구현, 9 PR을 수행하는 Build 절차뿐이다.
- 영향: 읽기 전용 분석 의도를 Build로 재해석하거나 불필요한 요구사항/구현 승인을 묻는 비일관성이 생긴다. 실제 모델을 실행해 원격 변경을 재현하지 않았다.
- 수정: 도메인×모드 지원 표로 진입 전에 검증하고, 미지원 조합은 비파괴적으로 종료하거나 지원되는 읽기 전용 BE/FE 작업으로 명시 라우팅한다. FE Flags([fe-harness/skills/start-workflow/SKILL.md:29](/workspace/harness-plugins/fe-harness/skills/start-workflow/SKILL.md:29))에도 analyze/verify가 없다는 루트 교차 검토를 반영한다.

**수정 후 검증:** 도메인×Build/Analyze/Verify 지원 조합을 검사한다. 읽기 요청의 미지원 조합에서 구현·branch·PR 도구 호출이 발생하지 않아야 한다.

<a id="c08"></a>

### C08 · P2 · 이미 queue에 있는 PR을 머지 완료로 오보고하고 base HEAD를 PR merge SHA로 사용

근거: [common/skills/merge/SKILL.md:128](/workspace/harness-plugins/common/skills/merge/SKILL.md:128) · **공식 CLI 소스 + 계약 검토**

- 위치: [common/skills/merge/SKILL.md:128](/workspace/harness-plugins/common/skills/merge/SKILL.md:128), `:143`, `:148`, `:153`.
- 조건 A: 아직 OPEN이면서 이미 merge queue에 들어 있는 PR을 이 스킬로 처리한다. 조건 B: 해당 PR 머지 후 base에 다른 커밋이 추가된다.
- 근거: 설치된 gh 2.89.0의 공식 소스에서 inMergeQueue는 ErrAlreadyInMergeQueue를 반환하고, 최상위 RunE는 이를 nil로 바꿔 성공 종료한다. 이 검사는 canMerge 및 브랜치 삭제보다 앞선다. 스킬은 상태 재조회 없이 머지 완료·원격/로컬 브랜치 삭제를 보고한다. 따라서 A에서는 queue 대기를 완료로 오보고할 수 있다. 이는 공식 코드에서 도출한 계약 결함이며 실제 GitHub queue를 실행한 재현은 아니다. [GitHub CLI v2.89.0 merge 소스](https://github.com/cli/cli/blob/v2.89.0/pkg/cmd/pr/merge/merge.go)
- 범위 교정: 신규 queue 요청은 현재 명령에 고정된 --delete-branch 때문에 gh가 거부한다. 이 경로를 queue 등록 성공 뒤 완료 오보고 사례로 세면 안 된다. 스킬에는 일반적인 명령 실패 보고 절차가 이미 있다.
- 별도 영향: B에서는 git log -1 <baseRefName>가 해당 PR의 mergeCommit이 아닌 뒤따른 커밋을 반환해 보고서의 머지 SHA가 잘못된다.
- 수정: gh pr view의 state/mergedAt/mergeCommit을 재조회하고 MERGED·QUEUED·동기화 실패를 구별한다. queue 지원을 추가한다면 현재 delete-branch 옵션 제약을 반영하고, 실제 브랜치 삭제 여부도 별도로 확인한다.

**수정 후 검증:** 이미 queue에 있는 OPEN PR의 성공 종료와 신규 queue의 delete-branch 오류를 구분한다. base 후속 커밋이 있어도 PR mergeCommit을 기록하고 MERGED/QUEUED·삭제 상태를 실제 응답으로 확인한다.

<a id="c09"></a>

### C09 · P2 · resolve-assumption의 경로 필터가 untracked 검색에 빠져 있다

근거: [common/skills/resolve-assumption/SKILL.md:32](/workspace/harness-plugins/common/skills/resolve-assumption/SKILL.md:32) · **실행 재현**

- 위치: [common/skills/resolve-assumption/SKILL.md:32](/workspace/harness-plugins/common/skills/resolve-assumption/SKILL.md:32), `:42`.
- 조건: 경로/glob를 지정했고 그 밖의 untracked 파일에도 태그가 있음.
- 재현: 요청 범위 src/에 대해 제공된 untracked 명령을 실행하면 `other/out_of_scope.go`, `src/in_scope.go` 모두 출력한다.
- 영향: 요청하지 않은 파일의 태그가 검토 목록에 포함된다. 승인을 받으면 범위 밖 변경으로 이어질 수 있다.
- 수정: tracked와 동일한 pathspec을 `git ls-files … -- {경로}`에 전달하고, glob의 Git pathspec/셸 확장 규칙을 일관되게 한다. 대상 pathname은 NUL로 유지한다.

**수정 후 검증:** 경로와 glob을 지정한 tracked/untracked 혼합 fixture에서 범위 밖 태그가 결과·수정 대상에 나오지 않아야 한다.

<a id="e03"></a>

### E03 · P2 · E2E 수정 기록이 실패한 케이스가 아니라 마지막 케이스에 붙음

근거: [be-harness/skills/e2e-test-loop/assets/render_e2e_report.py:144](/workspace/harness-plugins/be-harness/skills/e2e-test-loop/assets/render_e2e_report.py:144) · **실행 재현·이전 감사**

loop는 모든 케이스를 먼저 append한 후 실패→수정 블록을 append한다(SKILL:138,167). renderer는 **실패 → 수정 (A)**의 A를 읽지 않고 마지막 cur에 붙인다. A 실패, B 통과, A 수정, 다음 회차 둘 다 통과 fixture에서 A는 수정 없는 재시도 INCONCLUSIVE, B는 수정 후 PASS로 기록됐다. 해당 케이스 직후에 넣으라는 규칙(:116)과 append-only(:130)도 충돌한다.

**수정 방향:** 수정 블록에 iteration+case_id를 명시하고 그 키로 연결한다. 순서·표시 이름으로 귀속하지 말고 중복/미상 case_id는 오류로 보고한다.

**수정 후 검증:** A 실패→B 통과→A 수정 기록→다음 회차 모두 통과 순서에서 A에만 수정 이력이 붙고, 모르는 case_id는 명시적으로 거부돼야 한다.

<a id="f01"></a>

### F01 · P2 · 설정에서 지원하는 Nuxt·JavaScript와 FE 생성 템플릿이 맞지 않음

근거: [fe-harness/skills/component/SKILL.md:64](/workspace/harness-plugins/fe-harness/skills/component/SKILL.md:64) · **계약 결함**

init은 nuxt(Vue)를 선택지로 제공하고 component는 framework/typescript를 읽지만 템플릿은 항상 React .tsx/interface, @testing-library/react, @storybook/react다. typescript:false 분기도 없다. vitest 선택에서도 describe/it import나 globals 설정을 확인하지 않고 전역 함수를 사용한다. 실제 모델이 상황에 맞게 보완할 수는 있지만 지원 설정에 대한 실행 계약은 빠져 있다.

**수정 방향:** 지원 framework×언어×runner 조합을 명시하고 조합별 템플릿·전제 조건을 사용한다. 지원하지 않는 조합은 파일 생성 전에 알리고, 생성 예제를 실제 빌드/runner로 검증한다.

**수정 후 검증:** 명시한 지원 조합마다 생성 산출물을 실제 build/typecheck/test로 검사한다. Nuxt·JavaScript·Vitest globals 비활성 조합을 포함한다.

<a id="m03"></a>

### M03 · P2 · OpenAPI 3.0 payload에 지원되지 않는 nullable type 배열을 생성

근거: [minmos-harness/skills/apidog-schema-gen/SKILL.md:223](/workspace/harness-plugins/minmos-harness/skills/apidog-schema-gen/SKILL.md:223) · **공식 명세 + 계약 검토**

추출 규칙은 type:["string","null"]을 만들고 push-import:129는 openapi:3.0.0으로 감싼다. E2E 동기화 예제에도 같은 union type이 있다. OpenAPI 3.0은 type을 단일 문자열로 요구하며 nullable:true를 사용한다. Apidog UI용 JSON Schema와 OpenAPI import 스키마를 변환 없이 공유해서 생기는 형식 충돌이다. 실제 Apidog의 관대한 수용 여부는 미검증이다. [OpenAPI 3.0 Schema Object](https://spec.openapis.org/oas/v3.0.3.html#schema-object)

**수정 방향:** 출력 dialect를 명시하고 OAS 3.0 변환에서는 type:string, nullable:true로 변환한다. 생성한 전체 문서를 해당 버전 schema validator로 검증한 뒤 import한다.

**수정 후 검증:** nullable scalar/array/object와 oneOf를 포함한 생성 문서를 선언한 OAS dialect validator에 통과시킨 뒤 별도 테스트 프로젝트로 import/read-back한다.

<a id="m04"></a>

### M04 · P2 · API push가 성공 응답을 200으로 고정

근거: [minmos-harness/skills/apidog-schema-gen/references/push-import.md:136](/workspace/harness-plugins/minmos-harness/skills/apidog-schema-gen/references/push-import.md:136) · **계약 결함**

원래 OAS의 responses.{statusCode}를 읽지만 push 생성 규칙은 responses.200만 명시한다. 201 생성·204 삭제 등 다른 성공 코드를 갖는 API가 200 문서로 재생성되거나 기존 응답 정의를 잃을 수 있다. GET에만 parameters, POST/PUT/PATCH에만 body를 붙이라는 규칙도 operation별 실제 계약을 충분히 보존하지 못한다.

**수정 방향:** 코드·기존 OAS의 실제 statusCode, 모든 위치의 parameters, body 유무를 그대로 보존한다. 201/204/다중 응답 operation의 생성 전후 차이를 검증한다.

**수정 후 검증:** 201/204/복수 성공·오류 응답, query/header/path parameter를 포함한 OAS의 생성 전후 계약 차이를 검사한다.

<a id="m05"></a>

### M05 · P2 · worktree 초기화 hook이 공백 경로·설정 파일 없는 첫 설치에서 실패

근거: [minmos-harness/skills/init/SKILL.md:264](/workspace/harness-plugins/minmos-harness/skills/init/SKILL.md:264) · **실행 재현**

git worktree list --porcelain를 awk print $2로 읽어 공백 뒤를 버린다. repo with space를 메인 checkout으로 만든 실제 Git fixture에서 hook exit 0이지만 .env가 복사되지 않았다. 또 settings.json이 없는 fixture에서 :288~291 등록 명령은 jq exit 2, settings 미생성이었다.

**수정 방향:** worktree 경로는 NUL 형식 또는 worktree 접두사 전체 제거로 읽는다. 설정 파일이 없으면 빈 객체를 원자 생성하고 기존 JSON/권한을 보존하며 설치 후 등록·복사를 확인한다.

**수정 후 검증:** 공백·한글 main/worktree 경로, settings.json 없음·기존 hooks 있음·유효하지 않은 JSON에서 설치 결과와 실제 복사를 확인한다.

<a id="m06"></a>

### M06 · P2 · 페이지네이션 템플릿의 tie-breaker가 다음 커서에 포함되지 않음

근거: [minmos-harness/skills/pagenation/SKILL.md:109](/workspace/harness-plugins/minmos-harness/skills/pagenation/SKILL.md:109) · **SQL fixture + 템플릿 검토**

id가 없으면 SQL ORDER BY에만 id desc를 추가하고 orderSpecs에는 넣지 않은 채 커서를 만든다. created_at이 같은 3개 행, limit=2 fixture에서 첫 페이지 [3,2], 다음 조건 created_at<100은 빈 목록이 되어 id=1을 놓친다. 별도 helper가 id를 보완하지 않는 문서 그대로의 알고리즘을 검증했으며 CloudKit 실제 구현을 실행한 것은 아니다. order/cursor 일치 검사도 본문과 달리 예제에는 없고, 마지막 페이지에서 항상 nonempty cursor를 만드는 코드와 빈 문자열 규칙도 충돌한다.

**수정 방향:** 정렬·seek predicate·cursor encoding이 같은 정규 OrderSpec을 사용하게 하고 id를 그 배열에 추가한다. limit+1로 마지막 페이지를 판단하고 order 일치/limit 범위도 검사한다. 미정의 vos/helper가 있는 예제를 완성된 정본 템플릿과 대조한다.

**수정 후 검증:** 정렬값이 같은 행을 여러 페이지로 읽어 누락·중복이 없어야 한다. 역순·복합 정렬·마지막 페이지·cursor/order 불일치도 정본 helper로 실행한다.

<a id="m07"></a>

### M07 · P2 · snake_case 변환이 SQL Injection을 방지한다는 잘못된 안내

근거: [minmos-harness/skills/pagenation/SKILL.md:40](/workspace/harness-plugins/minmos-harness/skills/pagenation/SKILL.md:40) · **공식 문서 + 템플릿 검토**

컬럼명을 snake_case로 바꾸면 SQL Injection이 방지된다고 설명하면서 fmt.Sprintf로 Column/Direction을 Order에 넣는다(:95~96). 이름 스타일 변환은 허용 컬럼·정렬 방향 검증과 다르다. GORM 공식 문서도 Order 문자열을 비이스케이프 입력으로 분류한다. 실제 CloudKit parser 내부의 별도 방어 여부는 이번 범위에서 검증하지 않았으므로 소비 서비스의 확정 취약점으로 주장하지 않는다. [GORM Security](https://gorm.io/docs/security.html)

**수정 방향:** 허용 정렬 키→DB 컬럼 매핑과 ASC/DESC enum 검증을 명시하고 검증된 identifier만 SQL 구조에 넣는다. 값은 바인딩하며 잘못된 보안 설명을 제거한다.

**수정 후 검증:** 허용 목록 밖 컬럼·SQL 구문 문자가 포함된 정렬 키·잘못된 방향은 SQL 실행 전에 거부한다. 실제 CloudKit parser의 해당 보장도 별도로 확인한다.

<a id="m08"></a>

### M08 · P2 · Apidog·Proto 도구 참조가 환경 탐색/현재 설치 구조와 불일치

근거: [minmos-harness/skills/e2e-apidog-schema-gen/SKILL.md:113](/workspace/harness-plugins/minmos-harness/skills/e2e-apidog-schema-gen/SKILL.md:113) · **정적 대조·설치 파일 확인**

doctor는 read_project_oas_*를 탐색하지만 실제 실행은 _w9of5k 이름으로 고정된다. suffix가 다른 프로젝트에서는 진단 성공 후 호출이 끊긴다(api-share-note는 이미 동적 탐색을 명시). 재시도는 --project-id=만 읽지만 init:90은 --project=<ID>를 권장한다. gRPC reflection 폴백도 e2e-test-postmath:154에서 go-grpc-tools/skills/proto-gen을 참조하는데, 이 환경의 설치 위치는 go-stack-tools/2.0.1/skills/go-codegen/scripts/find-proto.sh다.

**수정 방향:** 진단에서 찾은 실제 callable/프로젝트 ID를 실행 단계까지 전달하고 신·구 인수 형식을 지원한다. 외부 스크립트 경로는 제공 skill의 계약으로 resolve하며 없는 의존성은 실행 전에 구체적으로 보고한다.

**수정 후 검증:** 서로 다른 MCP suffix와 신·구 project 인수 형식에서 진단이 찾은 도구를 실제 다음 단계가 쓰는지 확인한다. 외부 proto helper의 설치 위치 변경도 포함한다.

<a id="m09"></a>

### M09 · P2 · Apidog 검증 payload가 실행별로 격리되지 않아 다른 실행 내용으로 바뀜

근거: [minmos-harness/skills/apidog-schema-gen/references/push-import.md:151](/workspace/harness-plugins/minmos-harness/skills/apidog-schema-gen/references/push-import.md:151) · **계약 결함**

payload 경로가 /tmp/apidog-push-{endpoint-slug}.yaml로 고정되고 import에서 다시 읽는다(:170). 두 프로젝트/에이전트가 같은 endpoint slug를 처리하면 A가 검증한 파일을 B가 덮어쓴 뒤 A의 대상 프로젝트에 B 내용이 전송되는 interleaving이 가능하다. 재시도·deprecated 경로·E2E 동기화도 같은 파일명을 쓴다. 실제 원격 전송은 실행하지 않았다.

**수정 방향:** run_id별 비공유 디렉터리에 payload를 만들고 project/branch/method/path/hash를 묶어 고정한다. 검증한 bytes 자체를 전송하며 재읽을 경우 hash를 확인한다.

**수정 후 검증:** 같은 endpoint slug에 프로젝트 A/B 두 실행을 교차시킨다. 검증한 hash와 실제 전송 bytes·target이 각 실행에서 일치해야 한다.

<a id="q01"></a>

### Q01 · P2 · dirty 상태에서 이미 커밋한 구현이 품질 검사 범위에서 누락

근거: [be-harness/skills/simplify-loop/SKILL.md:34](/workspace/harness-plugins/be-harness/skills/simplify-loop/SKILL.md:34) · **실행 재현·이전 감사**

BE/FE simplify는 git status에 하나라도 있으면 git diff HEAD를 택한다. 구현 커밋 후 무관한 untracked notes.md만 남은 fixture에서 diff 0→SKIPPED:NO_CHANGES가 된다. FE convention-check:80도 일반 git diff만 사용해 커밋/staged 변경을 놓친다. FE lint-check:27은 빈 diff면 전체로 확대하지만 일부 dirty 파일만 있으면 기존 커밋 범위는 빠진다. 고쳐진 FE Phase 8 리뷰 범위와 별개의 경로다.

**수정 방향:** START_SHA부터 현재 tree까지의 변경과 실행 소유 untracked 목록을 공통 helper로 계산해 모든 검증 단계에 전달한다. clean/dirty 여부로 검사 기준을 바꾸지 않는다.

**수정 후 검증:** 구현 커밋+무관한 untracked 파일, staged-only, dirty 일부 파일, clean branch의 모든 경우에서 실행 소유 변경 집합이 빠지지 않아야 한다.

<a id="q02"></a>

### Q02 · P2 · FE 컴포넌트·접근성 수정 후 빌드/테스트 재검증 단계가 없음

근거: [fe-harness/skills/start-workflow/references/agent-prompts.md:317](/workspace/harness-plugins/fe-harness/skills/start-workflow/references/agent-prompts.md:317) · **계약 결함**

Phase 7 검증 완료 후 Phase 8에서 Critical을 수정하고 바로 Phase 9 PR로 간다. PR 직전 재검증은 light→standard 승격 조건일 때만 정의돼 있다. 이미 standard이거나 소수 파일 수정인 경우, 수정 전 PASS와 Read-back 결과를 그대로 쓴다. 최종 사용자 결정 후의 재검증 규칙은 이 최초 PR 이전 수정 경로를 보완하지 않는다.

**수정 방향:** Phase 8에 코드 변경이 있으면 관련 build/type/unit/E2E와 필요한 Read-back을 다시 실행하고 검증한 tree를 기록한다. 변경 후 검증 완료를 PR 단계의 전제 조건으로 둔다.

**수정 후 검증:** Phase 8에서 단 한 파일만 수정한 standard 실행도 관련 Phase 7 검증을 다시 거쳐야 한다. PR은 재검증한 tree와 일치해야 한다.

<a id="q03"></a>

### Q03 · P2 · FE lintCommand 설정을 실제 lint 단계가 사용하지 않음

근거: [fe-harness/skills/lint-check/SKILL.md:31](/workspace/harness-plugins/fe-harness/skills/lint-check/SKILL.md:31) · **계약 결함**

PROFILE.md는 lintCommand를 자유 문자열로 제공하고 실행에 사용할 것을 요구하지만 lint-check는 npx eslint 명령을 고정한다. 예를 들어 workspace 경로·ESLint 설정·환경변수가 포함된 사용자 lintCommand나 다른 lint runner를 설정해도 그 의미가 적용되지 않는다.

**수정 방향:** 명시 lintCommand를 우선 실행하고 없을 때에만 지원 runner의 기본 명령을 쓴다. 자동 수정 옵션도 runner별로 분리하고 unsupported 명령을 임의 변형하지 않는다.

**수정 후 검증:** workspace·환경변수·다른 runner가 포함된 사용자 lintCommand를 실행 추적으로 확인한다. 기본값과 명시 설정의 분기를 구별한다.

<a id="t03"></a>

### T03 · P2 · 다른 파일의 동명 테스트 PASS가 원래 실패를 flaky로 만듦

근거: [be-harness/skills/start-workflow/assets/test_failures.py:411](/workspace/harness-plugins/be-harness/skills/start-workflow/assets/test_failures.py:411) · **실행 재현**

JS 러너는 재실행 PASS에 leaf/suffix 매칭을 허용한다. 실제 Vitest에서 a와 b가 실패한 뒤 b 파일만 통과하도록 재실행하면, 실행하지 않은 a까지 flaky로 바뀌었다(원본 실패 2개가 모두 flaky). 재실행에서 해당 테스트가 빠졌는데 PASS 증거로 인정한다. Go의 package exact-match 수정은 JS에 적용되지 않았다.

**수정 방향:** runner+파일+전체 테스트 이름의 정확한 ID로 PASS를 확인한다. 원래 실패 ID가 재실행 결과에 없으면 원 분류 유지와 rerun_incomplete로 처리한다.

**수정 후 검증:** B만 PASS한 재실행에서 실행하지 않은 A는 flaky가 될 수 없어야 한다. 파일·suite·parameterized test가 모두 같은 ID인지 확인한다.

<a id="w02"></a>

### W02 · P2 · title 메타데이터의 타입 오류가 vault 전체 동기화를 중단

근거: [work-log/mcp/lib/vault.js:242](/workspace/harness-plugins/work-log/mcp/lib/vault.js:242) · **실행 재현·이전 감사**

wiki_write의 frontmatter 객체 내부에는 타입 검증이 없다. title을 배열로 주면 파일은 생성되지만 이후 nfc(title)의 normalize 호출이 예외를 낸다. 해당 문서가 하나만 있어도 전체 sync가 실패한다. MCP로 전달하지 않아도 외부에서 편집한 동일 YAML이 같은 문제를 만든다.

**수정 방향:** 쓰기 전 메타데이터 스키마를 검증하고, 스캔에서는 문서별 파싱 오류를 경로와 함께 보고한다. 하나의 손상 문서가 전체 인덱스 갱신을 무력화하지 않도록 한다.

**수정 후 검증:** title이 배열·객체·숫자인 문서를 쓰기 전에 거부하고, 외부 편집으로 생긴 손상 문서는 경로별 오류를 내면서 정상 문서의 읽기·검색을 유지한다.

<a id="w03"></a>

### W03 · P2 · 저장 성공 뒤 인덱싱 실패를 전체 쓰기 실패로 응답

근거: [work-log/mcp/server.js:203](/workspace/harness-plugins/work-log/mcp/server.js:203) · **실행 재현·이전 감사**

writeDoc 완료 뒤 syncIndex가 실패하면 wiki_write가 isError:true를 반환한다. W02뿐 아니라 정상 문서에서도 다른 프로세스의 인덱스 잠금을 5초 이상 기다리면 발생한다. 이미 저장된 append를 실패로 보고 재시도하면 내용이 중복된다. 저장과 검색 반영은 서로 다른 완료 상태다.

**수정 방향:** 응답에 written/path/hash와 indexing 상태를 각각 반환한다. 문서 저장 이후의 실패를 미저장 실패와 구별하고, 재시도는 인덱싱만 수행하거나 쓰기 요청 ID로 중복을 막는다.

**수정 후 검증:** 문서 저장 직후 인덱스 잠금 timeout을 주입해 written=true를 확인한다. 같은 append 재시도 뒤 문서에는 내용이 한 번만 있어야 한다.

<a id="w04"></a>

### W04 · P2 · append/overwrite가 기존 파일 접근 권한을 완화

근거: [work-log/mcp/lib/vault.js:641](/workspace/harness-plugins/work-log/mcp/lib/vault.js:641) · **실행 재현·이전 감사**

임시 파일을 기본 mode로 만든 뒤 rename하므로 원본의 권한을 잃는다. 0600 파일이 umask 0002에서 0664로 바뀌었다. 일반적인 0022에서는 0644가 된다. 실제 타 사용자 접근 가능 여부는 상위 디렉터리 권한과 ACL에도 달려 있다.

**수정 방향:** 원본 stat의 mode를 교체 파일에 보존하고, 소유권·ACL·확장 속성의 지원 범위도 정한다. 원본보다 넓은 권한을 갖는 임시 파일을 만들지 않는다.

**수정 후 검증:** 0600/0640 파일을 서로 다른 umask에서 append/overwrite해도 mode가 유지되는지 확인한다. 새 임시 파일이 원본보다 넓은 권한으로 노출되지 않아야 한다.

<a id="w05"></a>

### W05 · P2 · 인덱스 잠금을 시간만으로 탈취해 최신 결과를 과거 결과로 덮어씀

근거: [work-log/mcp/lib/vault.js:451](/workspace/harness-plugins/work-log/mcp/lib/vault.js:451) · **실행 재현·이전 감사**

5분 넘은 index.lock을 살아 있는 소유자인지 확인하지 않고 삭제하며 finally도 소유권 확인 없이 잠금을 지운다. A sync를 임시 인덱스 생성 시 SIGSTOP, 잠금 mtime을 6분 전으로 설정, 문서 변경 후 B sync 성공, A 재개 순서에서 B의 NEW 인덱스가 A의 OLD로 교체됐다. 6분 실제 대기는 하지 않고 mtime으로 경과 조건을 모사했다.

**수정 방향:** 소유 토큰·프로세스 식별·heartbeat 또는 검증 가능한 lease/fencing을 적용한다. 해제도 자기 소유 잠금에만 수행하고 오래된 writer의 commit을 거부한다.

**수정 후 검증:** 정지한 A와 갱신한 B의 실행 순서를 제어해 오래된 A가 B 인덱스를 덮거나 B 잠금을 해제하지 못하는지 확인한다. 죽은 소유자는 안전하게 회수돼야 한다.

<a id="w06"></a>

### W06 · P2 · 공백·한글 설치 경로에서 설정 CLI가 출력 없이 종료

근거: [work-log/mcp/lib/config.js:196](/workspace/harness-plugins/work-log/mcp/lib/config.js:196) · **실행 재현**

import.meta.url은 URL 인코딩되지만 비교 대상 file://${process.argv[1]}은 원시 경로다. config.js를 plain, plugin with space, 플러그인 디렉터리에 복사해 같은 WORK_LOG_ROOT로 실행했다. plain은 JSON을 출력했고 나머지는 exit 0, stdout 0바이트였다. init/doctor의 CLI 폴백이 설정을 받지 못한다.

**수정 방향:** pathToFileURL(path.resolve(process.argv[1])).href 또는 fileURLToPath 기반으로 진입점을 판정한다. 공백·한글·#·% 경로를 CLI 테스트에 포함한다.

**수정 후 검증:** 공백·한글·#·%가 포함된 설치 경로에서 CLI 출력이 모두 유효한 동일 설정 JSON이어야 한다.

<a id="w07"></a>

### W07 · P2 · null/false 설정을 무시하고 다른 vault로 폴백

근거: [work-log/mcp/lib/config.js:99](/workspace/harness-plugins/work-log/mcp/lib/config.js:99) · **실행 재현**

readJson의 파일 부재와 JSON null 값이 같은 값이고 if(!cfg)가 false/0도 함께 무시한다. 프로젝트 .work-log.json에 null, 전역 설정에 유효한 다른 vault를 넣으면 오류 없이 전역 vault를 선택했다. 깨진 우선 설정에서 중단한다는 ConfigError 계약과 다르며 쓰기 대상이 바뀔 수 있다.

**수정 방향:** 부재를 별도 sentinel로 구분하고 JSON 루트가 비어 있지 않은 객체인지 검증한다. scope/root/excludes 타입을 검사하며 잘못된 상위 설정은 하위 설정으로 넘기지 않는다.

**수정 후 검증:** null/false/0/배열 루트인 우선 설정을 모두 오류로 구분한다. 실제 파일 부재일 때만 정상 fallback하며 출력 대상 vault를 확인한다.

<a id="w08"></a>

### W08 · P2 · 코드 블록의 # 줄을 제목으로 처리해 섹션을 잘라냄

근거: [work-log/mcp/lib/search.js:129](/workspace/harness-plugins/work-log/mcp/lib/search.js:129) · **실행 재현**

## Deployment 안의 fenced shell 예제에 # example comment가 있으면 extractSection(Deployment)는 코드 펜스 시작까지만 반환하고 뒤의 본문을 누락한다. example을 검색하면 코드 주석을 실제 제목으로 잡아 다음 정상 섹션까지 섞어 반환했다. 인덱싱의 heading 추출에도 같은 코드 펜스 구분이 필요하다.

**수정 방향:** Markdown heading을 코드 펜스 밖에서만 인식하는 공통 파서를 사용한다. backtick/tilde 펜스와 중첩 제목을 포함한 읽기 결과를 검증한다.

**수정 후 검증:** backtick/tilde 코드 펜스 속 # 주석을 무시하고, 지정 섹션 본문은 다음 동급·상위 제목 직전까지 정확히 반환해야 한다.

<a id="w09"></a>

### W09 · P2 · 읽기 권한 오류를 삭제로 보고 정상 인덱스로 저장

근거: [work-log/mcp/lib/vault.js:270](/workspace/harness-plugins/work-log/mcp/lib/vault.js:270) · **실행 재현**

readdir/read/stat 오류를 모두 잡아 무시한다. private.md를 정상 sync 후 chmod 000으로 바꾸고 같은 사용자로 재동기화하면 성공 응답에 docs=[], drift.removed=[private.md]가 나온다. 파일은 삭제되지 않았다. 폴더 오류는 하위 전체를 누락시킬 수 있다.

**수정 방향:** ENOENT와 EACCES/EIO 등을 구별한다. 불완전 스캔은 오류 목록과 DEGRADED 상태를 남기고 기존 엔트리를 보존하거나 전체 commit을 보류한다.

**수정 후 검증:** EACCES/EIO 주입 시 삭제 drift를 만들지 않아야 한다. ENOENT로 실제 삭제한 경우와 결과·상태가 구분돼야 한다.

<a id="w10"></a>

### W10 · P2 · 잘못된 경로의 위키 링크를 다른 파일에 연결

근거: [work-log/mcp/lib/vault.js:408](/workspace/harness-plugins/work-log/mcp/lib/vault.js:408) · **실행 재현**

[[missing/guide]]가 없고 real/guide.md만 있을 때 basename fallback이 real/guide.md를 선택해 brokenLinks=[]를 반환했다. 파일명만 쓴 링크용 fallback이 명시적 디렉터리 경로에도 적용된다. 중복 파일명도 첫 항목을 임의 선택한다.

**수정 방향:** 디렉터리를 명시한 링크는 그 경로로만 해석하고, 파일명만 쓴 링크도 후보가 하나일 때만 연결한다. 다수 후보는 ambiguous로 보고한다.

**수정 후 검증:** 명시 경로 없음·동일 basename 다수·파일명 단독 유일 후보를 각각 검사해 broken/ambiguous/resolved가 달라야 한다.

<a id="f02"></a>

### F02 · P3 · hyeondongs doctor가 정상 현대 profile·선택 설정을 누락으로 보고

근거: [hyeondongs-harness/skills/doctor/SKILL.md:154](/workspace/harness-plugins/hyeondongs-harness/skills/doctor/SKILL.md:154) · **계약 결함**

머리말은 fe-harness.local.md가 우선이라고 하지만 점검/필수 표는 .hyeondong-config.json을 필수로 둔다. 현대 profile만 있는 정상 설치도 ISSUES FOUND가 된다. typescript:false에서도 TypeScript 필수, Cypress 선택에도 Playwright 실행 검사, codexMode:none과 다른 Plan 검증 루프 상시 문구, 존재하지 않는 /hyeondong-init 안내가 남아 있다. FE doctor/component/unit-test 본문에도 legacy fallback 머리말과 현대 파일 필수 문구가 함께 남은 곳이 있다.

**수정 방향:** 실효 profile resolver와 runner capability 표를 베이스 doctor와 공유하고, 비활성/레거시를 MISSING과 구분한다. 오래된 진단 문구도 구조 검사 범위에 포함한다.

**수정 후 검증:** 현대 profile만 존재·legacy만 존재·typescript:false·Cypress·codexMode:none 조합에서 필수/선택/SKIP 판정과 안내 호출명이 맞아야 한다.

<a id="s01"></a>

### S01 · P3 · 구조 검사 cleanup이 자신이 만들지 않은 __pycache__도 삭제

근거: [scripts/check-plugins.sh:55](/workspace/harness-plugins/scripts/check-plugins.sh:55) · **실행 재현**

py_compile 뒤 저장소 전체의 __pycache__를 rm -rf한다(work-log만 제외). tracked 파일의 독립 snapshot에 unrelated/__pycache__/keep.txt를 만든 뒤 검사했더니 check-plugins: OK, exit 0이면서 sentinel은 삭제됐다. 제품 저장소 원본에서는 이 명령을 실행하지 않았다.

**수정 방향:** PYTHONPYCACHEPREFIX를 임시 디렉터리로 두거나 이 실행이 생성한 경로만 추적해 정리한다. 검사가 소유하지 않은 디렉터리에 손대지 않게 한다.

**수정 후 검증:** 검사 전에 무관한 __pycache__/keep.txt와 기존 bytecode를 만들고 검사 후 해시가 그대로인지 확인한다. 검사 자체 임시 출력만 정리돼야 한다.

## 4. 별도 설계·운영·유지보수 개선 30건

아래 항목은 확인된 결함과 별도인 개선 또는 통합 검증 공백이다. 결함과 연결되는 공통 개선은 해당 ID를 참조하며 새로운 장애 건수로 중복 합산하지 않았다. 우선순위는 권장 적용 순서다. I 목록의 축약 경로는 common/skills 아래를 기준으로 한다.

| ID/우선순위 | 근거 | 개선 제안/검증 공백 |
|---|---|---|
| I01/P1 | merge SKILL.md:41, :128 | 요약 생성 시 `headRefOid`를 기록하고 `gh pr merge --match-head-commit`으로 검토한 SHA를 고정한다. 현재는 컨펌 대기 중 추가 push된 변경도 포함될 수 있다. 도움말에서 해당 옵션 존재 확인; GitHub 동시 push 실험 미실행. |
| I02/P2 | commit-push SKILL.md:105-115; resolve-assumption:38-46 | Git 명령 실패와 grep no-match를 분리해 Gate를 닫힌 실패로 만든다. base/upstream 존재를 먼저 확인하고 오류를 0건으로 취급하지 않는다. stderr만 보여주는 파이프라인 예제는 검사 신뢰성이 약하다. |
| I03/P2 | common/OVERRIDES.md:53; 각 SKILL Override 문단 | 문서가 프라이빗 `common.local.md`를 제안하지만 실제 로드 목록은 common.md와 skill.md뿐이다. 지원 경로·우선순위를 명시하거나 예시를 삭제한다. 숨은 호스트 로드 규칙은 확인되지 않았다. |
| I04/P2 | start-workflow SKILL.md:106-116 | `--be`/`--fe`는 베이스만 쓰는 플래그라는 안내를 실제 위임 우선순위 표에 명시한다. 현재 1순위 오버레이 감지 설명과 별도 안내에 의존한다. |
| I05/P2 | fullstack.md:52, :245 | 풀스택의 minmos/hyeondongs “오버레이 요약 전달”을 파일 경로·추가 단계·스킵 조건으로 구조화한다. Phase 번호가 단일 도메인 기준인 hook이 빠지는지 실제 호출 경로 검증이 없다. 전체 중첩 실행 금지는 유지한다. |
| I06/P2 | fullstack.md:259, :294, :298, :320-323 | TEST_NOT_GREEN 후 Phase 8 강제 진행과 “둘 다 green이면 PR” 사이에서 최종 결정 Phase로 어떻게 넘어가는지 분기를 명시한다. finalization의 재검증·미완료 보존은 올바르지만, PR을 BLOCKED로 둔 채 최종 결정으로 이동하는 표가 fs에 없다. |
| I07/P2 | fullstack.md:28, :302; BE/FE SKILL --hard | `--hard`가 단일 도메인에서는 직접 push, fs에서는 push 생략이라는 차이를 공용 플래그 표에서 보여준다. 현재 계약은 서로 다르며 자동 도메인 전환 시 사용자의 push 기대가 달라진다. |
| I08/P2 | fullstack.md:326-332; BE/FE templates archive fallback | 아카이브 명령의 경로들을 shell-quote하고, fallback에서도 reportDir 생성·실패 확인·exclusive create를 유지한다. 현재 `cat ... > 기존경로`는 원본 helper의 덮어쓰기 금지/원자성 보장을 잃는다. 경로 공백·동시 fallback·출력 경로가 일반 파일인 경우 테스트가 없다. |
| I09/P2 | archive.py:99-104, :209 | touched_paths는 Git `-z`로 읽고 문자열을 YAML-safe하게 인코딩한다. newline/tab/콜론/비ASCII 경로, input frontmatter의 중복 tier/touched_paths를 다루는 테스트가 없다. dirty baseline 영향은 기존 범위 문제와 중복 집계하지 않는다. |
| I10/P2 | archive.py:234, :253-257 | 출력 디렉터리 생성/기존 파일 읽기 예외도 exit 2 계약으로 처리한다. hardlink 미지원 fallback의 exists→replace는 no-overwrite 보장과 맞지 않으므로 파일시스템별 생성 방법을 명시한다. 해당 파일시스템 race는 재현하지 않았다. |
| I11/P2 | codex-mode.md:105, :111, :122 | 재개 시 핸들 소실을 writer 사망으로 단정하지 말고 실행 소유 PID/작업 ID와 종료 증거를 확인한다. 병렬 범위 준수는 문서도 인정하듯 프롬프트 수준이므로 cross-slice 변경 탐지/격리 fixture가 필요하다. 실제 Codex/MCP 세션 사망 통합은 미검증. |
| I12/P3 | sync-base SKILL.md:121, :152 | worktree/서브디렉터리에서도 진행 중 rebase 감지는 `git rev-parse --git-path` 사용. `git stash` 후 untracked 포함 여부/복원할 stash ID/merge 전에 clean 여부를 명시한다. 현행 Git 자체가 위험한 merge를 거부하는 경로는 데이터 손실로 과장하지 않는다. |
| I13/P3 | sync-base SKILL.md:87, :97, :112, :292 | merge 전 VERSION/swagger 목록과 merge 결과가 다를 때(추가·rename·삭제) 대상 목록 재검증을 정의한다. diff3/zdiff3 충돌 표시에서는 현 awk가 공통조상 구역까지 읽어 보수적으로 일반 충돌로 분류할 수 있다. 현재 실제 손실 재현은 없다. |
| I14/P3 | submit-feedback SKILL.md:136, :200, :219, :285 | `target_type=common`을 Step3에서 commons로 복수화하는 일반식과 Step5의 common/날짜 파일 예외를 한곳에서 정의. 중복 skip으로 0개 남을 때 빈 commit/PR을 하지 않는 상태를 추가한다. fork/clone/권한/기존 PR 실패의 로컬 fallback 저장 주체·정리 테스트가 없다. |
| I15/P3 | doc-gen SKILL.md:63, :193-209 | 파일명은 epoch 외 충돌 방지 suffix/exclusive write를 사용한다. HTML은 self-contained를 요구하면서 Mermaid를 CDN에서 가져오므로 “오프라인” 보장 여부를 명시한다. `securityLevel: loose` 기본과 동적 코드/설명 HTML escaping 정책도 검토한다. Mermaid lint는 자체 점검뿐이고 twin 비교도 block 수/헤더만 검사하므로 내용 정합성은 보장하지 않는다. |
| I16/P3 | how-to-use SKILL.md:29-32, :55 | 플러그인 prefix를 고정 열거하므로 새로운 harness나 Codex 설치 이름 변경을 자동 발견하지 못한다. 세션 제공 스킬 메타데이터 기반 기능 탐색·정확한 실제 호출명 예시를 추가하면 안내가 실제 설치와 어긋나는 문제를 줄인다. |
| I17/P3 | fullstack-agent-prompts.md:19,:78,:98; contract-templates.md:1 | “남은 Phase” 예시가 10에서 끝나 최종 11이 빠지고, 템플릿 상단도 최종 보고를 Phase10으로 설명한다. canonical은 11이므로 예시/헤더 상호 검증으로 정리한다. |
| I18/P3 | fullstack.md:279; fullstack-agent-prompts.md:200 | “BE/FE가 동일 방향으로 계약을 이탈하면 contract 대조는 통과”라는 설명은 논리적으로 맞지 않는다. 계약이 명시한 필드/타입과 양쪽이 똑같이 달라도 BE↔contract·FE↔contract가 차이를 잡아야 한다. 3축 검증 필요성은 유지하고 설명만 정확히 고친다. |

다음은 오케스트레이터가 제품별 점검에서 정리한 추가 개선이다.

| ID/우선순위 | 대표 근거 | 개선 제안/검증 공백 |
|---|---|---|
| D01/P2 | [scripts/check-plugins.sh:1](/workspace/harness-plugins/scripts/check-plugins.sh:1) | CI에서 Python·Node 테스트, 구조 검사, marketplace/manifest 검증을 하나의 필수 job으로 실행한다. manifest 검증만으로 agent frontmatter·workflow 상태 계약을 검증했다고 취급하지 않는다. 복제본 parity 검사는 유지하되 공통 결함도 잡는 실행 fixture를 함께 둔다. |
| D02/P2 | [tests/test_test_failures.py:1](/workspace/harness-plugins/tests/test_test_failures.py:1) | 실제 Jest/Vitest reporter 로그를 고정 fixture로 보관하고 지원 runner 버전별 표본으로 파서를 확인한다. 문구 존재 assertion 외에 서로 다른 파일·변한 실패 값·누락된 rerun을 포함한다. 매 테스트에서 package를 새로 설치할 필요는 없다. |
| D03/P2 | [common/skills/start-workflow/assets/workflow_archive.py:159](/workspace/harness-plugins/common/skills/start-workflow/assets/workflow_archive.py:159) | 검증 결과의 run_id·mode·phase·iteration·case_id·tested tree·최종 상태를 구조화하고 Markdown은 그 값에서 출력한다. C05/C06/E03처럼 출력 문장과 Phase 번호를 다시 파싱하는 경로를 줄이는 공통 개선이며 별도 결함으로 중복 집계하지 않는다. |
| D04/P2 | [be-harness/skills/config/SKILL.md:73](/workspace/harness-plugins/be-harness/skills/config/SKILL.md:73) | 현재 긴 prose 편집 규칙을 작은 결정적 profile helper로 옮길지 검토한다. 도입한다면 CRLF/혼합 EOL·인라인 주석·따옴표·중복 키·여러 키 원자 수정·변경 없음의 바이트 보존을 실행으로 검증한다. 지원하지 않는 YAML까지 범위를 넓힐 필요는 없다. |
| D05/P3 | [work-log/mcp/lib/vault.js:295](/workspace/harness-plugins/work-log/mcp/lib/vault.js:295) | 문서 수·읽은 bytes·scan 시간·누락/오류 수·index 생성 시각을 진단에 노출하고 현실적인 vault 크기로 측정한다. 전체 스캔이 문제로 측정된 경우에만 증분 인덱싱을 도입한다. 이번 감사에서 처리량 한계나 성능 저하를 실측한 것은 아니다. |
| D06/P2 | [work-log/mcp/lib/vault.js:417](/workspace/harness-plugins/work-log/mcp/lib/vault.js:417) | cache의 index 버전·루트 일치·손상/이전 schema 처리 규칙을 테스트하고 재생성 경로를 안내한다. 캐시에 남는 제목/excerpt의 권한·보관·삭제 범위도 명시한다. 현재 타 사용자에게 실제 내용이 노출됐다고 주장하는 항목은 아니다. |
| D07/P2 | [README.md:1](/workspace/harness-plugins/README.md:1) | Claude plugin 실행, Codex-native work-log, Codex에 대한 작업 위임을 구별하는 지원 표를 둔다. package/host 버전별 설치·실제 agent 도구·필요 MCP 발견 smoke test를 마련한다. doctor는 선언된 framework/runner/codexMode에 필요한 의존성만 검사하고 진단 중 다운로드 여부도 표시한다. |
| D08/P2 | [minmos-harness/overlay/references/e2e-test-postmath.md:83](/workspace/harness-plugins/minmos-harness/overlay/references/e2e-test-postmath.md:83) | 환경 파일의 허용 DB_HOST 확인과 실제 앱/MCP 연결 대상 확인을 연결한다. 가능하면 DB명·port·schema·서버 식별을 비교하고 터널/컨테이너 별칭의 의미를 명시한다. FK 탐색은 schema를 함께 식별한다. 현재 운영 DB에 연결됐다는 증거는 없으며 M01의 소유 ID cleanup과 함께 검증할 경계다. |
| D09/P2 | [minmos-harness/overlay/references/grpc-testing.md:1](/workspace/harness-plugins/minmos-harness/overlay/references/grpc-testing.md:1) | grpcurl의 JSON 파싱 거부와 서버가 반환한 gRPC 상태를 구분하고, unknown field/oneof·deadline·streaming 지원 여부를 결과에 기록한다. 미지원/미호출은 성공과 분리한다. 실제 서버에 도달하지 않은 요청이 서버 validation을 검증했다고 보고되는지 통합 테스트가 필요하다. |
| D10/P2 | [minmos-harness/skills/apidog-schema-gen/references/extraction-patterns.md:5](/workspace/harness-plugins/minmos-harness/skills/apidog-schema-gen/references/extraction-patterns.md:5) | SKILL의 항상 flat 규칙(:130)과 reference의 재사용 객체 $ref 규칙을 하나로 정리한다. 자기 참조/순환 schema의 유한 표현도 정의한다. import timeout은 서버가 이미 수락했을 가능성을 read-back으로 구분하고 재시도 대상·payload 고정은 M02/M09 수정과 공유한다. 순환 입력/timeout 원격 실험은 미실행이다. |
| D11/P2 | [minmos-harness/skills/init/SKILL.md:264](/workspace/harness-plugins/minmos-harness/skills/init/SKILL.md:264) | worktree hook 설치는 기존 사용자 hook과 settings 권한을 보존하는 병합으로 정의하고 임시 파일을 실행별로 격리한다. .env/secret 복사의 실제 대상과 ignore 상태를 검증한다. M05의 재현 결함 외 기존 설정 동시 수정·중간 실패·민감 파일의 잘못된 추적 여부는 추가 fixture 대상이다. |
| D12/P3 | [scripts/check-plugins.sh:1](/workspace/harness-plugins/scripts/check-plugins.sh:1) | 로컬 문서 링크·실제 skill 호출명·Phase 표·canonical/override 우선순위를 함께 검사한다. 단순 문자열 검색은 폐기된 예시나 상위 overlay가 대체한 경로를 현재 실행 결함으로 오판하므로 실행에서 쓰는 참조를 구분한다. 버전은 제품별 정책에 맞춰 갱신하고 의도적으로 다른 제품 버전을 일괄 통일하지 않는다. |

## 5. 권장 수정 순서와 완료 기준

1. **데이터·대상·작업 범위 보호:** W01/W04/W05, M01/M02/M09, C01, I01. 외부 파일 해시·실행 소유 ID·확정 project와 payload·커밋 파일 목록·검토 SHA를 각각 불변 조건으로 검증한다.
2. **검증 결과의 정확성:** T01/T02/T03, E01/E02/E03, Q01/Q02, C04/C05/C06. 실제 runner 로그와 다중 프로토콜/다중 회차 fixture로 실패 누락 및 오래된 PASS 재사용을 막는다.
3. **워크플로우 계약 정리:** C02/C03/C07/C08/C09, Q03, A01, F01/F02, M03–M08. base/commit/Gate·모드·도구·profile·OAS 계약을 하나의 실행 경로로 맞춘다.
4. **검색/운영 안정성과 유지보수:** 나머지 work-log 항목, S01, I/D 개선 목록. 오류를 성공/삭제와 구분하고 테스트·진단·문서 연결을 CI에서 유지한다.

각 수정은 해당 항목의 재현 fixture를 먼저 실패 테스트로 고정한 뒤 필요한 최소 범위에 적용한다. P1 해소 뒤 전체 기본 테스트·구조 검사를 한 번 실행하고, 실제 GitHub/Apidog/소비 서비스가 필요한 항목은 별도 테스트 환경의 통합 검증을 완료 조건으로 남긴다. 단순 문구/링크 수정에는 구현을 그대로 복사한 테스트를 추가할 필요가 없다.

## 6. 미검증 범위와 제외한 오탐

- GitHub push/PR/merge/queue·Apidog import·소비 서비스 DB 쓰기는 실행하지 않았다. CLI/API 계약 결함과 실제 원격 서비스의 반응을 구별한다.
- CloudKit parser/페이지네이션 helper 내부, 실제 PostgreSQL trigger/FK, 앱/MCP의 실제 DB 연결 일치, 전체 REST/gRPC 서버 E2E는 미검증이다. SQL 예제의 문제를 특정 운영 서비스의 확정 취약점으로 확장하지 않았다.
- 모든 스킬의 실제 모델 대화·사용자 승인·중단/재개·Codex writer 사망·host의 agent 도구 제한·FE 생성물의 build/브라우저 렌더링은 통합 미검증이다. 문서상 지시 누락을 모델이 반드시 같은 방식으로 실패한다는 증거로 쓰지 않았다.
- 대규모 vault 성능, 네트워크 파일시스템·Windows·다른 host/runner 버전 전반은 측정하지 않았다. 전체 목록 점검은 모든 실행 조합의 무결점 보장이 아니다.
- work-log만 Codex-native manifest를 가진 구조는 의도된 구분으로 보았다. 다른 플러그인의 Codex-native manifest 부재를 자동 결함으로 세지 않았다.
- finalization에는 최종 사용자 결정 후 관련 검증·기존 PR 갱신·미완료 상태 보존 규칙이 이미 있다. 이를 누락으로 재보고하지 않았다. Q02는 그보다 앞선 FE Phase 8 수정 경로다.
- Vitest verbose ID에는 파일명이 있다. T01의 원인은 메시지 key에서 파일을 버리는 것이며, FE lint는 빈 diff에서 전체 검사 fallback을 갖는다. Q01은 일부 dirty 상태에서 커밋 범위가 빠지는 조건을 가리킨다.
- FE Read-back에는 E2E/공개 인터페이스 fallback이 있다. C04는 증거/범위 누락이며 모든 검증이 사라진다는 주장이 아니다.
- 폐기된 경로나 overlay의 명시적 override로 대체된 참조는 실행 경로를 확인한 뒤 제외했다. manifest의 author/upstream 경고도 설치 불가 결함으로 부풀리지 않았다.

## 7. 검증 근거 보존과 최종 작업 상태

[검증 근거 JSON](/workspace/harness-plugins/docs/harness-audit-2026-09-05-evidence.json)에 전체 발견사항, 176개 파일의 기준 해시, 기본 검증 결과, 공용 11개 fixture 결과/재현 코드, 실제 Jest/Vitest의 baseline·current·rerun 로그와 fixture 소스, work-log/SQL/hook 결과를 보존했다. `$AUDIT_TMP`는 정리한 임시 경로의 표식이며 현재 존재하는 경로가 아니다. runner 파일은 마지막 fixture 상태이고 baseline→current 변경 순서는 T01/T02/T03 본문을 함께 봐야 한다.

이전 동일 HEAD 감사의 W01–W05/E01–E03/Q01은 관찰 내용과 조건을 보존했으며 원본 임시 fixture 전체를 새로 복원한 것은 아니다. 최종 대조에서 W09/W10과 M05의 settings.json 부재 실험 출력 보존이 빠진 것을 확인해, 해당 로컬 fixture만 다시 실행하고 결과를 근거 JSON에 추가했다. 정적 계약만 검토한 항목에는 실행 로그를 만들어 붙이지 않았다.

대표 재현 관찰은 다음과 같다. 상세 stdout/stderr는 근거 JSON에 있다.

| 항목 | 관찰한 실제 결과 |
|---|---|
| T01 | a의 반환값(Received)이 2→4로 바뀌어도 양쪽 signature는 b의 반환값 3, regression 0/pre_existing 2 |
| T02 | Received 2→4, signature는 동일 matcher 표현식, regression 0/pre_existing 1 |
| T03 | b 파일만 재실행 PASS했는데 a와 b 모두 flaky, flaky 2 |
| C01 | 범프 커밋의 파일: VERSION, unrelated.txt |
| C05 | 마지막 PASS regression 0 입력 → 아카이브 PASS regression 2/상태 OK |
| C06 | 최초 DEGRADED → 재시도 OK, 파일은 계속 INCOMPLETE |
| W06/W07 | 공백·한글 경로 stdout 0바이트/exit 0; 프로젝트 null 설정은 global vault로 fallback |
| M01/M06 | 다른 writer의 id=12도 removed; 첫 페이지 [3,2] 뒤 다음 페이지 [], id=1 누락 |
| M05/S01 | 공백 worktree hook exit 0이나 env 미복사; 구조 검사 OK이나 무관한 sentinel 삭제 |

**Assumptions:** 제품 기능·지원 범위를 새로 유추해 구현한 사항은 없다. 원격/모델 동작과 미검증 helper 보장은 각 항목의 조건·한계로 표시했다. 사용자의 “전체”는 이 저장소의 추적 제품/공용 파일 전체로 해석했고, 외부 소비 서비스 및 DOT 문서의 개정은 포함하지 않았다.

**Final Convention Review:** MCP 인터페이스/스킬 출력, workflow 상태와 판정, 파일·Git·외부 대상 저장 경계를 나눠 검토했다. 이 플러그인 저장소에 Presentation/Service/Repository 웹앱 구조를 강제로 적용하지 않았다. 보고서 외 구현 변경·리팩터링은 없다. 기존 소스 스타일과 사용자 문서는 그대로 보존한다.

**최종 파일/정리 검증:** 추적 파일 176개의 SHA-256과 기존 사용자 문서 2개의 해시가 감사 시작과 동일하다. HEAD/브랜치도 유지됐다. 새 파일은 보고서와 근거 JSON 2개뿐이다. 72개 파일 링크·41개 항목 anchor·7개 표를 검증했고, 감사 전용 임시 디렉터리와 본인이 만든 bytecode를 삭제했다. 진행 중인 실험 프로세스는 없다.

**독립 최종 보고서 검토:** 독립 리뷰어가 집계·중복·common C01–C09·본문/JSON 근거를 대조했다. 표 공백, T02 값 변화 표현, C08 queue 옵션 조건을 수정했고, W09/W10·M05의 추가 출력 보존 권고도 반영했다. 검토 범위 내 나머지 중대한 불일치는 보고되지 않았다.
