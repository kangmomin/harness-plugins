# be-harness

범용 백엔드 개발 워크플로우 하네스. `minmos-harness`에서 Post-Math 특화 요소를 걷어내고 **Go/Node 프리셋 + 프로젝트 profile** 기반으로 재구성한 범용판.

## 설치

```
/plugin marketplace add kangmomin/mimo-s-harness
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
| **commit** | `/be-harness:commit` | 변경사항을 논리적 단위로 커밋 |
| **commit-push** | `/be-harness:commit-push` | commit + push (브랜치 검증 포함) |
| **commit-pr** | `/be-harness:commit-pr` | commit + push + Draft PR |
| **commit-hard-push** | `/be-harness:commit-hard-push` | 보호 브랜치 제한 없이 commit + push |

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **convention-check** | `/be-harness:convention-check` | 컨벤션 검사 (`.convention-check.json`) |
| **simplify-loop** | `/be-harness:simplify-loop` | 빌트인 `/simplify` 반복 실행 (최대 10회) |
| **e2e-test** | `/be-harness:e2e-test` | profile 기반 HTTP API E2E 테스트 |
| **e2e-test-loop** | `/be-harness:e2e-test-loop` | E2E → 수정 → 재테스트 반복 (최대 5회) |

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

## 파생 관계

- `minmos-harness` → Post-Math 내부용 (Apidog, PostgreSQL MCP, Liquibase, 특정 컨벤션 포함)
- **`be-harness`** → 외부 의존/특정 컨벤션 제거 + Go/Node 프리셋화된 범용판
