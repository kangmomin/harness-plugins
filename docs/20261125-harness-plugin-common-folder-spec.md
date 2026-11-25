# Spec: harness-plugin 공통 폴더 (function · work-log · 문서 저장)

- 상태: 구현 준비 완료
- 유형·도메인: 생성 · backend (플러그인 인프라)
- 작성: 2026-11-25, ready-for-impl 인터뷰 (질문 9회, Spec 수정 1회)

### 작업 계약
- 대상: kangmomin/harness-plugins, worktree `issue--38-work-log-common-function`, 브랜치 `issue/38-work-log-common-function`, 이슈 #38.
  - work-log: `work-log/mcp/lib/config.js`(`resolveConfig`), `work-log/skills/{init,doctor}/SKILL.md`, `work-log/README.md`, MCP manifest env 전달
  - e2e function: `be-harness/skills/e2e-test/`(정본), `fe-harness/skills/e2e-test/`(사본), `minmos-harness/overlay/e2e-test.md`
  - 문서 저장: 저장 helper(정본 + 사본), `common/skills/ready-for-impl`, `common/skills/doc-gen`, `minmos-harness/skills/api-share-note`, `common/skills/submit-feedback`
  - run 폴더: `be-harness/skills/config/assets/profile.py:33`(+fe 사본), `be|fe-harness/skills/start-workflow`, `be-harness/skills/e2e-test-loop`, `common/skills/start-workflow/references/fullstack.md`, `hyeondongs-harness/overlay/start-workflow.md`, `minmos-harness/overlay/e2e-test-loop.md`, `be|fe-harness/PROFILE.md`, run 관련 assets(`workflow_run.py`·`workflow_archive.py`·`risk_facts.py` 등)
  - 공통: `scripts/check-plugins.sh`(pair 등록)
- 기준: 이슈 #38 → 이 인터뷰 결정(D-01~D-29) → Plan 단계 결정(D-30~D-38, 충돌 시 우선) 순. 참조 구현: `config.js:160`(env 절대경로 규칙), `scripts/check-plugins.sh:45`(be↔fe 사본 pair), `be-harness/skills/e2e-test/assets/e2e_lock.py`(스킬 assets Python helper 패턴), `be-harness/skills/config/assets/profile.py:33`(reportDir 기본값).
- 범위: 아래 To-Be 전체 / 제외: function 폴더 work-log 인덱싱, 스크립트 실행 전 승인 단계, 기존 문서·run 폴더 자동 이동, `_shared`와 project 간 자동 병합, 저장 후 `wiki_sync` 자동 실행.
- 완료: 단위 테스트(node `config.test.js`, pytest helper·run 테스트), `scripts/verify.sh`·`check-plugins.sh` 통과, README·SKILL·PROFILE 문서, be·fe·common·minmos·hyeondongs·work-log minor 범프와 변경 이력, Draft PR.
- 승인: 이 Spec 내용 확정까지만. 구현·커밋·push·PR은 start-workflow에서 진행.
- 미결: 없음

## 기능 목표
하네스가 만드는 문서·run 폴더와 e2e 공통 스크립트의 위치를 코드(helper)가 환경변수로 정해야 한다. 설정이 없으면 `~/.harness-plugin/` 아래를 쓴다.

## 현재 상황 (As-Is)
| 파일 | 역할 | 수정 필요 |
|------|------|----------|
| `work-log/mcp/lib/config.js:155-191` | root 해석. 설정 없으면 `needsInit` | O — 5번 앞에 fallback 추가 |
| `work-log/skills/{init,doctor}/SKILL.md` | 스코프 설정·진단 | O |
| `be|fe-harness/skills/e2e-test/SKILL.md` | e2e. 공통 스크립트 탐색 없음 | O — helper 호출 |
| `minmos-harness/overlay/e2e-test.md` | be e2e 오버레이 | O — 상속 명시 |
| `common/skills/ready-for-impl/SKILL.md` Step 7 | `--out` → specDir → work-log:edit 위임 → 경로 질문 | O — 3·4를 저장 helper로 교체 |
| `common/skills/doc-gen/SKILL.md:62` | `<프로젝트>/docs`에 저장 | O — 저장 위치를 helper가 결정 |
| `minmos-harness/skills/api-share-note/SKILL.md:98-104` | wiki_write → 전역 규약 경로 | O — helper 저장 |
| `common/skills/submit-feedback/SKILL.md` | 로컬 보존본 | O — helper 저장 |
| `be-harness/skills/config/assets/profile.py:33` | `reportDir` 기본값 `.claude/harness-reports` | O — 미지정 시 helper 경로 |
| `be|fe-harness/skills/start-workflow/SKILL.md:22` 외 | `{REPORT_DIR}`·`{RUN_DIR}` 사용 | O — helper 결과 사용 |
| `scripts/check-plugins.sh:45` | be↔fe 사본 일치 검사 | O — helper pair 등록 |

### 참조 구현
- `config.js:160` → env는 trim 후 절대경로일 때만 유효.
- `scripts/check-plugins.sh:45` → be 정본, fe 동일 사본 검사.
- `be-harness/skills/e2e-test/assets/e2e_lock.py` → assets helper를 SKILL.md가 호출.

## 변경 사항 (To-Be)

### 구현 원칙 (사용자 지시, D-21)
규약은 지시서가 아닌 코드로 만든다. 경로 해석·manifest 검증·이름 충돌·문서 저장·run 폴더 결정은 helper 코드와 테스트가 보장한다. SKILL.md는 helper 호출과 결과 사용만 적는다.

### 경로 규칙 (코드로 구현)
| 대상 | 우선순위 |
|------|---------|
| base | `$HARNESS_PLUGIN_HOME` → `~/.harness-plugin` |
| function root | `$HARNESS_FUNCTION_DIR` → `<base>/function` |
| work-log root (MCP) | 기존 순서 → 마지막 fallback `<base>/work-log` |
| 문서 저장 위치 `<doc root>` | `$WORK_LOG_ROOT` → `<base>/work-log/docs` |
| 문서 파일·REPORT_DIR | `<doc root>/<project>/<파일명>` (profile `reportDir` 명시 시 REPORT_DIR = 그 값) |
| RUN_DIR 부모 | `<doc root>/.harness-runs/<project>/` (profile `reportDir` 명시 시 시스템 temp) (D-35) |
| feedback 보존본 | `<base>/feedback-submissions/<project>/<plugin>/` (vault 밖, D-36) |

- 모든 env는 trim 후 절대경로일 때만 유효 (EC-01).
- `<project>` = `remote.origin.url` 마지막 부분(`.git` 제거) → 없으면 git common-dir 이름(`.git`이면 부모) → git이 아니면 cwd 폴더 이름 (D-34·D-31). worktree도 같다. 해시 없음(D-30). URL 원본은 출력하지 않는다.
- 필요한 폴더는 helper가 만든다 (권한 0700). 자동 생성은 첫 쓰기 때만 한다 (D-38).

### work-log (`config.js`)
- `resolveConfig` 5번 fallback: `<base>/work-log`, `configSource: 'default:harness-plugin'`. 조회(`wiki_status`·`wiki_resolve`·`wiki_read`·CLI 기본)는 폴더를 만들지 않고 `pending: true`·`root`를 보고한다. 첫 `wiki_write`·`wiki_sync`(CLI `--create`)가 만든다 (D-38). 생성 실패·파일이면 오류.
- MCP 실행 환경(Claude `.mcp.json`, Codex manifest)에 `HARNESS_PLUGIN_HOME` 전달.
- init은 이 경로를 제안, doctor는 fallback 사용을 표시. README "없는 base는 승인 후 생성" 규칙에 예외 반영.

### e2e function helper (`e2e_functions.py`, be 정본 + fe 사본)
- `list --cwd C --harness be|fe` / `run --cwd C --harness H --name N [--timeout S] -- args…` / `add --cwd C --src … --name … --description … --harness … --usage …` (D-37). function root·project는 `harness_store.py resolve`가 보고한다.
- 구조: `<function root>/_shared/` + `<function root>/<project>/`, 각 폴더 `manifest.json`
- manifest:

  ```json
  {
    "version": 1,
    "scripts": [
      {
        "name": "auth-token",
        "path": "auth-token.sh",
        "description": "로그인 후 Bearer 토큰 출력",
        "harness": ["be", "fe"],
        "usage": "auth-token.sh <baseUrl> <user>"
      }
    ]
  }
  ```
- e2e-test: 시나리오 구성 전 `list` → 승인 없이 실행(호스트 권한 프롬프트 유지) → 재사용 후보가 있으면 저장 제안 → 승인 시 `add`. minmos는 be 동작 상속.

### 문서 저장 helper (`harness_store.py`)
- `save-doc --cwd C --name <파일명> [--prefer <파일.md|폴더>]` + 본문 stdin → 경로 규칙으로 저장 → JSON `{path, needsSync: true, warnings}` (D-37, `--kind` 없음)
  - 덮어쓰지 않는다. 같은 이름이 있으면 `-2`, `-3` 접미사. exclusive create.
  - 파일만 직접 쓴다. work-log 인덱스는 다음 `wiki_sync`에 반영.
- `report-dir --cwd C --domain be|fe` → `{reportDir, runDir, source, warnings}` — 워크플로우 밖 단독 e2e 전용. 워크플로우는 `workflow_run.py create`가 같은 규칙으로 정한다 (D-37)
- `resolve --cwd C [--ensure]` → `{base, docRoot, docRootSource, project, projectSource, docDir, functionRoot, functionRootSource, feedbackRoot, warnings}`. `--ensure`면 docDir 생성·검사
- `find-docs --cwd C --contains S` → docDir 안 파일명 목록 (중복 확인용)
- 사용처:
  - ready-for-impl Step 7: **`save-doc [--prefer {--out|specDir}]`** (work-log:edit 위임 제거). `--prefer` 파일이 이미 있거나 폴더가 없어 오류면 기존 "1. 다른 경로 입력 / 2. 대화에 출력만" 질문 유지
  - doc-gen: `resolve --ensure`의 `docDir`을 `docgen.mjs` 출력 디렉터리 인자로 전달
  - api-share-note: 중복 확인 = `wiki_resolve` + `find-docs`, 갱신은 `wiki_resolve` 문서만 `wiki_write`, 신규는 `save-doc`
  - submit-feedback 로컬 보존본: `feedback.py prepare --cwd`가 검사된 `payload.plugin`으로 feedback 폴더를 정한다 (D-36)
  - start-workflow(be/fe/common fullstack/hyeondongs overlay)·e2e-test-loop(be/minmos overlay): `{REPORT_DIR}` = `workflow_run.py create/resume` 출력 (helper가 `--mode`로 profile `reportDir`를 읽음), 단독 e2e는 `report-dir`
- profile.py: `reportDir` 기본값을 `""`로 두고 키는 유지한다. `""` = 미지정(기본 위치), 값 = 명시값.

## 정상 흐름
| ID | 시나리오 | 보장되는 결과 |
|----|---------|--------------|
| AC-01 | env·설정 모두 없음, `~/.harness-plugin/work-log` 없음 | 조회는 `pending: true`·그 root 반환(폴더 생성 안 함). 첫 쓰기(`fallback: 'create'`)가 폴더를 만들고 그 root와 `configSource: 'default:harness-plugin'` 반환 (D-38) |
| AC-02 | `HARNESS_PLUGIN_HOME=/abs/x`, 다른 설정 없음 | work-log root = `/abs/x/work-log` |
| AC-03 | `.work-log.json`·XDG·legacy·WORK_LOG_ROOT 중 하나라도 있음 | 기존과 같은 root (기존 테스트 통과) |
| AC-04 | `harness_store.py resolve`, env 없음 | `functionRoot` = `~/.harness-plugin/function`, `project` = 저장소 이름 (D-34·D-37) |
| AC-05 | `HARNESS_FUNCTION_DIR=/abs/f` | function root = `/abs/f` |
| AC-06 | `_shared`·`<project>`에 유효한 manifest | `list --harness be`가 `be` 항목만 절대경로와 함께 반환 |
| AC-07 | `add`, `<project>/`·manifest 없음 | 폴더·manifest 생성, 파일 복사, 항목 추가 |
| AC-08 | doctor, fallback 사용 중 | fallback 사용 표시 |
| AC-09 | init | 선택지에 `<base>/work-log` 표시 |
| AC-10 | `save-doc`, `WORK_LOG_ROOT` 없음 | `~/.harness-plugin/work-log/docs/<project>/<파일명>` 생성, 절대 경로 출력 |
| AC-11 | `save-doc`, `WORK_LOG_ROOT=/abs/v` | `/abs/v/<project>/<파일명>` 생성 |
| AC-12 | ready-for-impl Step 7, `--out`·specDir 없음 | `save-doc` 결과 경로에 Spec 저장, 질문 없음 |
| AC-13 | doc-gen 실행 | 결과 파일이 `<doc root>/<project>/`에 생성 |
| AC-14 | start-workflow 시작, profile `reportDir` 미지정 | run 폴더가 `<doc root>/.harness-runs/<project>/` 아래 생성, 재개도 같은 경로 사용 |
| AC-15 | profile `reportDir` 명시 | REPORT_DIR = 그 경로(절대화), RUN_DIR = 시스템 temp (기존 동작, D-35) |

## 엣지 케이스
| ID | 케이스 | 기대 동작 | 참조 구현 |
|----|--------|----------|----------|
| EC-01 | env가 빈 문자열·공백·상대경로 | unset 취급 | `config.js:160` |
| EC-02 | fallback·저장 폴더 생성 실패 | 오류 반환, 다른 위치로 대체하지 않음 | `config.js:81` |
| EC-03 | function root·manifest 없음 | `list` 빈 목록, 경고 없음, e2e 계속 | - |
| EC-04 | manifest 깨진 JSON / version 불일치 / 필수 필드 없음 | 해당 manifest·항목 생략, 경고, e2e 계속 | - |
| EC-05 | manifest `path`·`save-doc --name`이 폴더 밖(`../`, 절대경로, symlink) | 거부 | work-log README §안전 보장 |
| EC-06 | `_shared`·`<project>` 같은 `name` | 두 항목 제외, 충돌 경고 | - |
| EC-07 | `add` 같은 name·파일 존재 | 덮어쓰지 않고 오류 | - |
| EC-08 | git 저장소 아님 / git 조회 실패 | git 아님("not a git repository")이면 cwd 폴더 이름을 project로 쓴다(function·save-doc·add 모두). 그 밖의 git 실패(깨진 메타데이터·실행 불가·dubious ownership)는 오류. 단 `list`는 경고 후 `_shared`만 (D-31) | `config.js` nonGit 처리 |
| EC-09 | `harness` 값이 be/fe 외 | 항목 거부, 경고 | - |
| EC-10 | `save-doc` 같은 파일명 존재 | `-2`, `-3` 접미사로 새 파일, 기존 파일 불변 | ready-for-impl Step 7 규칙 |
| EC-11 | 이전 기본 경로(`.claude/harness-reports`)에 진행 중 run 있음 | 자동 이동하지 않음. 재개 시 run 상태에 기록된 경로를 그대로 사용 | - |
| EC-12 | `.harness-runs/` 안 `.md`가 work-log 인덱스에 잡힘 | `.harness-runs`를 custom `excludes`와 관계없이 항상 제외(스캔·MCP 읽기·쓰기 거부) | work-log README §인덱싱 규칙 |

## 결정 로그
| ID | 항목 | 결정 | 근거 |
|----|------|------|------|
| D-01 | 기본 위치 | `~/.harness-plugin/{function,work-log}` | 사용자 답(R1) |
| D-02 | function 사용 주체 | e2e-test가 탐색해 재사용 | 사용자 답(R1) |
| D-03 | 경로 변경 방법 | 환경변수 | 사용자 답(R1) |
| D-04 | work-log 순서 | 맨 끝 fallback | 사용자 답(R2) |
| D-05 | 환경변수 | `HARNESS_PLUGIN_HOME` + `HARNESS_FUNCTION_DIR`, work-log는 `WORK_LOG_ROOT` | 사용자 답(R2) |
| D-06 | function 구조 | `_shared` + `<project>` | 사용자 답(R2) |
| D-07 | 대상 e2e 스킬 | be + fe + minmos | 사용자 답(R2) |
| D-08 | 탐색 방식 | manifest.json | 사용자 답(R3) |
| D-09 | 실행 승인 | 승인 없이 실행 | 사용자 답(R3) |
| D-10 | project 키 | git 저장소 이름 | 사용자 답(R3) |
| D-11 | 스크립트 저장 | 후보 제시 → 승인 후 저장 | 사용자 답(R3) |
| D-12 | helper 위치 | be 정본 + 사본 pair | `scripts/check-plugins.sh:45` |
| D-13 | manifest 필드 | version + name·path·description·harness·usage | 사용자 답(R4) |
| D-14 | name 충돌 | 오류 처리 | 사용자 답(R4) |
| D-15 | 없음/잘못됨 | 조용히 생략 / 경고 후 생략 | 사용자 답(R4) |
| D-16 | 저장 시 폴더 없음 | 같은 승인으로 생성, 덮어쓰기 금지 | 사용자 답(R4) |
| D-17 | env 검증 | 절대경로만 유효 | `config.js:8,160` |
| D-18 | fallback 폴더 없음 | 자동 생성 | 사용자 답(R5) |
| D-19 | init·doctor | 둘 다 반영 | 사용자 답(R5) |
| D-20 | 완료 범위 | 테스트 + 문서 + 범프 + Draft PR | 사용자 답(R6) |
| D-21 | 규약 구현 | 지시서가 아닌 코드 | 사용자 지시 |
| D-22 | 문서 저장 env | `WORK_LOG_ROOT` 있으면 그 위치, 없으면 `~/.harness-plugin/work-log/docs` | 사용자 지시 + 답(수정 1) |
| D-23 | 저장 helper 대상 | 결과 문서 + 실행 상태 파일 | 사용자 답(수정 1) |
| D-24 | doc-gen 기본 위치 | helper 규칙으로 변경 | 사용자 답(수정 1) |
| D-25 | 쓰기 방식 | 직접 쓰기, 덮어쓰기 금지, `-2` 접미사 | 사용자 답(수정 1) |
| D-26 | reportDir | profile 명시값 우선 | 사용자 답(수정 1) |
| D-27 | 옮길 실행 상태 | run 폴더 전체 — **D-35로 대체** (RUN_DIR·REPORT_DIR 분리) | 사용자 답(수정 1) |
| D-28 | 저장소 구분 | `<project>` 하위 폴더 | 사용자 답(수정 1) |
| D-29 | run 폴더 위치 | `<doc root>/.harness-runs/` | 사용자 답(수정 1) |
| D-30 | project 이름 해시 | 해시 없음. 같은 이름 저장소 충돌 수용, README 경고 | Plan 사용자 답 |
| D-31 | git 아님 | "not a git repository"만 cwd 폴더 이름. 그 밖의 git 실패는 오류 | Plan 사용자 답 |
| D-32 | doc root 기준 | `WORK_LOG_ROOT`만 본다. `.work-log.json`·XDG vault와 분리 수용, README 고지 | Plan 사용자 답 |
| D-33 | `.harness-runs` 정리 | 자동 정리 없음 | Plan 사용자 답 |
| D-34 | project 이름 | `remote.origin.url` 마지막 부분 → common-dir 규칙 → 폴더 이름 | Plan 사용자 답 |
| D-35 | run 상태와 리포트 | RUN_DIR(상태·잠금) = `<doc root>/.harness-runs/<project>/…`, REPORT_DIR(리포트 아카이브) = `<doc root>/<project>/` | Plan 사용자 답 |
| D-36 | feedback 보존본 | `<base>/feedback-submissions/<project>/<plugin>/` (vault 밖) | Plan 사용자 답 |
| D-37 | CLI 이름 | `harness_store.py resolve / report-dir / save-doc --prefer / find-docs`, `e2e_functions.py list / run / add` | Plan 사용자 답 |
| D-38 | 자동 생성 시점 | 첫 쓰기 때(`wiki_write`·`wiki_sync`·`save-doc`·`workflow_run create`). doctor·status·검색은 "기본 경로 사용 예정" 보고 | Plan 사용자 답 |

## Breaking Changes
- 설정이 없던 사용자: work-log가 `needsInit` 대신 `<base>/work-log`(기본 `~/.harness-plugin/work-log`)를 쓴다. 조회는 `pending`을 보고하고 첫 쓰기 때 폴더를 만든다.
- doc-gen 결과가 `<프로젝트>/docs`가 아닌 `<doc root>/<project>/`에 생긴다.
- profile `reportDir` 값이 비었거나 키가 없는 프로젝트만: 리포트가 `<doc root>/<project>/`, run 상태가 `<doc root>/.harness-runs/<project>/`로 바뀐다. 값이 적힌 프로젝트는 기존과 같다. 진행 중 run은 옮기지 않는다 (EC-11). 새 REPORT_DIR에는 과거 리포트가 없어 `risk_facts` 리포트 이력(티어 B축 근거)이 0부터 시작한다.
- ready-for-impl은 더 이상 work-log:edit에 Spec 저장을 위임하지 않는다.

## Assumption
- [Assumption] helper 이름 `e2e_functions.py`(e2e), `harness_store.py`(문서·run). 정본은 be-harness, fe·common에 동일 사본 — 근거: `e2e_lock.py` 패턴, execution-policy "be 정본, FE/common 동일 사본"
- [Assumption] `HARNESS_FUNCTION_DIR`은 `_shared`·`<project>`를 포함하는 폴더 — 근거: D-05
- [Assumption] 문서 fallback도 `HARNESS_PLUGIN_HOME`을 따른다 (`<base>/work-log/docs`) — 근거: D-05 base 규칙
- [Assumption] run 폴더는 `<doc root>/.harness-runs/<project>/` 순서 — 근거: D-28·D-29 질문 문구
- [Assumption] ready-for-impl의 `--out`·specDir 명시값은 helper보다 우선 유지 — 근거: D-26과 같은 "명시값 우선" 원칙
- [Assumption] minmos는 harness 값 `be`로 필터 — 근거: `minmos-harness/overlay/e2e-test.md`
- [Assumption] 자동 생성 폴더 권한 0700 — 근거: work-log 캐시 디렉터리 0700
- [Assumption] `add`는 항상 `<project>/`에 저장 — 근거: D-16 질문 문구
- [Assumption] 버전은 minor 범프 (be 1.14.0, fe 1.13.0, common 0.23.0, minmos 2.8.0, hyeondongs 3.1.0, work-log 0.7.0) — 근거: 커밋 0763339 패턴

## 미결
- 없음
