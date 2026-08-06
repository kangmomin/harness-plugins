# be-harness

범용 백엔드 개발 워크플로우 하네스. `minmos-harness`에서 Post-Math 특화 요소를 걷어내고 **Go/Node 프리셋 + 프로젝트 profile** 기반으로 재구성한 범용판.

## 설치

commit/push/PR 워크플로우가 common 스킬에 위임되므로 `common`을 선행 설치해야 한다.

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install be-harness@harness-plugins
```

## 초기 세팅

```bash
/be-harness:init       # 프로젝트 profile(.claude/be-harness.local.md) 생성
/be-harness:doctor     # 환경 진단
```

## 스킬 목록

### 세팅

| 스킬 | 호출 | 설명 |
|------|------|------|
| **init** | `/be-harness:init` | profile 생성/갱신 (Go/Node 프리셋 또는 custom) |
| **doctor** | `/be-harness:doctor` | profile·명령·Git 상태 진단 |

### 자동화

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/be-harness:start-workflow` | 전체 워크플로우 자동화 — 요청→난이도→Plan 리뷰→구현→품질 루프→PR |

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/be-harness:request` | 작업 유형별(생성/수정/검토/디버깅) 단계적 질문 → Technical Spec |

> 커밋/Push/PR 워크플로우(`commit`, `commit-push`, `commit-pr`, `commit-hard-push`)는 [`common` 플러그인](../common/README.md)으로 이전되었습니다. `/common:commit`, `/common:commit-push`, `/common:commit-pr`, `/common:commit-hard-push` 로 호출합니다.

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **convention-check** | `/be-harness:convention-check` | 컨벤션 검사 (`.convention-check.json`) |
| **simplify-loop** | `/be-harness:simplify-loop` | 4관점 리뷰(Correctness/Readability/Performance/Stability) → Devil's Advocate → Arbiter 판정을 수렴까지 반복 (최대 10회, Workflow 미지원 시 빌트인 `/simplify` 폴백) |
| **unit-test** | `/be-harness:unit-test` | Spec 추적 ID(AC/EC/RC) 기반 단위 테스트 작성·실행. `--red`로 실패 테스트 선작성 |
| **e2e-test** | `/be-harness:e2e-test` | profile 기반 HTTP API E2E 테스트 |
| **e2e-test-loop** | `/be-harness:e2e-test-loop` | E2E → 수정 → 재테스트 반복 (최대 5회). 종료 시 정직한 자기 점검 HTML 리포트 생성 |

### 컨벤션 레퍼런스

| 스킬 | 설명 |
|------|------|
| **default-conventions** | 언어/프레임워크 독립적 개발 가이드라인. 프로젝트 특화는 `CLAUDE.md` 또는 profile의 `projectConventions`에서 로드. |

### 에이전트

| 에이전트 | 설명 |
|---------|------|
| **workflow-implementer** | Plan 기반 구현 + 커밋 |
| **workflow-pr** | PR 생성 |
| **workflow-reflection** | 워크플로우 성찰 |
| **scope-reviewer** | Spec 기반 구현 검증 |
| **code-analyzer** | 코드 분석 (architecture/quality/dependency/pattern) |
| **code-verifier** | 코드 검증 (security/performance/bugs/stability) |
| **edge-case-analyzer** | API 엣지 케이스 도출 |

## Project Profile

모든 스킬이 `.claude/be-harness.local.md` (YAML frontmatter) 에서 빌드/테스트/소스 경로를 읽는다.
구체 스펙은 `PROFILE.md` 참조.

## Project Overrides (로컬 피드백)

플러그인 원본을 수정하지 않고 프로젝트별로 스킬/에이전트 동작을 조정할 수 있다:

```
.claude/be-harness/
├── common.md                 # 모든 스킬/에이전트 공통
├── skills/{name}.md          # 특정 스킬 전용
└── agents/{name}.md          # 특정 에이전트 전용
```

- 각 파일은 선택. 존재하면 플러그인 기본 동작에 **추가 규칙/예외/변경점** 으로 흡수됨.
- `start-workflow` Phase 12 의 보완점이 자동으로 이곳에 append 된다.
- 상세 규약: `OVERRIDES.md`.

## Community Feedback (플러그인 레포 PR)

범용성 있는 보완점은 플러그인 레포에 PR로 제출해 다른 사용자와 공유할 수 있다:

- 제출 스킬: `/common:submit-feedback`
- 대상: `kangmomin/harness-plugins` 의 `be-harness/community-feedback/{skills,agents,common}/...`
- `start-workflow` Phase 12 에서 "로컬 저장 + PR" 옵션을 선택하면 자동 호출됨
- 플러그인 원본 SKILL.md 는 PR 로도 변경되지 않음 (수집 레이어만 커짐, 유지보수자 큐레이션 후 별도 PR 로 승격)
- 전제: `gh` CLI 설치 및 인증. 실패 시 로컬 저장으로 fallback

상세: `community-feedback/README.md`.

## 파생 관계

- `minmos-harness` → Post-Math 내부용 (Apidog, PostgreSQL MCP, Liquibase, 특정 컨벤션 포함)
- **`be-harness`** → 외부 의존/특정 컨벤션 제거 + Go/Node 프리셋화된 범용판
