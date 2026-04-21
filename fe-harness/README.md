# fe-harness

범용 프론트엔드 개발 워크플로우 하네스. `hyeondongs-harness`에서 프로젝트 특화 요소를 걷어내고 **프로젝트 profile** 기반으로 재구성한 범용판.

## 설치

```
/plugin marketplace add kangmomin/mimo-s-harness
/plugin install fe-harness@harness-plugins
```

## 초기 세팅

```bash
/fe-harness:init       # 프로젝트 profile(.claude/fe-harness.local.md) 생성
/fe-harness:doctor     # 환경 진단
```

## 스킬 목록

### 세팅

| 스킬 | 호출 | 설명 |
|------|------|------|
| **init** | `/fe-harness:init` | profile 생성/갱신 (framework, testRunner, e2eRunner 등) |
| **doctor** | `/fe-harness:doctor` | 환경 진단 |

### 자동화

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/fe-harness:start-workflow` | 전체 프론트 워크플로우 자동화 |

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/fe-harness:request` | 화면/컴포넌트/API 연동 유형별 Technical Spec 생성 |
| **component** | `/fe-harness:component` | 컴포넌트 보일러플레이트 자동 생성 |
| **commit** | `/fe-harness:commit` | 변경사항을 논리적 단위로 커밋 |
| **commit-push** | `/fe-harness:commit-push` | commit + push |
| **commit-pr** | `/fe-harness:commit-pr` | commit + push + PR |

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **convention-check** | `/fe-harness:convention-check` | 컨벤션 검사 |
| **simplify-loop** | `/fe-harness:simplify-loop` | 빌트인 `/simplify` 반복 |
| **lint-check** | `/fe-harness:lint-check` | ESLint/Prettier/TypeScript 체크 |
| **unit-test** | `/fe-harness:unit-test` | Vitest/Jest 단위 테스트 |
| **test-loop** | `/fe-harness:test-loop` | 테스트 → 수정 반복 |
| **e2e-test** | `/fe-harness:e2e-test` | Playwright/Cypress E2E |

### 컨벤션 레퍼런스

| 스킬 | 설명 |
|------|------|
| **default-conventions** | FE 개발 가이드라인 템플릿 |

### 에이전트

| 에이전트 | 설명 |
|---------|------|
| **workflow-implementer** | Plan 기반 FE 구현 |
| **workflow-pr** | PR 생성 |
| **workflow-reflection** | 워크플로우 성찰 |
| **scope-reviewer** | Spec 기반 구현 검증 |
| **component-reviewer** | 컴포넌트 구조/재사용성 리뷰 |
| **a11y-reviewer** | 접근성 리뷰 |

## Project Profile

모든 스킬이 `.claude/fe-harness.local.md` (YAML frontmatter) 에서 framework/testRunner/e2eRunner/packageManager 등을 읽는다.

## Project Overrides (로컬 피드백)

플러그인 원본을 수정하지 않고 프로젝트별로 스킬/에이전트 동작을 조정할 수 있다:

```
.claude/fe-harness/
├── common.md                 # 모든 스킬/에이전트 공통
├── skills/{name}.md          # 특정 스킬 전용
└── agents/{name}.md          # 특정 에이전트 전용
```

- 각 파일은 선택. 존재하면 플러그인 기본 동작에 **추가 규칙/예외/변경점** 으로 흡수됨.
- `start-workflow` Phase 9 의 보완점이 자동으로 이곳에 append 된다.
- 상세 규약: `OVERRIDES.md`.

## Community Feedback (플러그인 레포 PR)

범용성 있는 보완점은 플러그인 레포에 PR로 제출해 다른 사용자와 공유할 수 있다:

- 제출 스킬: `/fe-harness:submit-feedback`
- 대상: `kangmomin/harness-plugins` 의 `fe-harness/community-feedback/{skills,agents,common}/...`
- `start-workflow` Phase 9 에서 "로컬 저장 + PR" 옵션을 선택하면 자동 호출됨
- 플러그인 원본 SKILL.md 는 PR 로도 변경되지 않음 (수집 레이어)
- 전제: `gh` CLI 설치 및 인증. 실패 시 로컬 저장으로 fallback

상세: `community-feedback/README.md`.

## 파생 관계

- `hyeondongs-harness` → 팀 내부용
- **`fe-harness`** → 내부 특화 제거 + profile 기반 범용판
