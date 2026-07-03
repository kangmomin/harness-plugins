# hyeondong's harness

프론트엔드 개발 워크플로우를 위한 Claude Code 플러그인.

## 의존 플러그인

hyeondongs-harness 는 다음 세 플러그인의 에이전트/스킬을 호출한다. **반드시 함께 설치해야 한다.**

- `common` — `commit`, `commit-push`, `commit-pr`, `commit-hard-push` 등 커밋/PR 워크플로우 + `doc-gen`
- `fe-harness` — `a11y-reviewer`, `component-reviewer`, `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection` 에이전트
- `minmos-harness` — `request-mm`, `simplify-loop-mm`, `convention-check-mm`, `e2e-test-loop-mm`, `e2e-apidog-schema-gen-mm` 등 백엔드 스킬 (`start-workflow-fs` 전용)

## 설치

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install fe-harness@harness-plugins
/plugin install minmos-harness@harness-plugins
/plugin install hyeondongs-harness@harness-plugins
```

## 초기 세팅

```bash
/hyeondongs-harness:hyeondong-init-hd     # 전체 환경 한 번에 세팅
/hyeondongs-harness:hyeondong-doctor-hd   # 전체 환경 한 번에 진단
```

## 스킬 목록

### 세팅

| 스킬 | 호출 | 설명 |
|------|------|------|
| **hyeondong-init** | `/hyeondongs-harness:hyeondong-init-hd` | 모든 의존성 한 번에 세팅 (프레임워크, UI lib, 상태관리, 테스트 도구) |
| **hyeondong-doctor** | `/hyeondongs-harness:hyeondong-doctor-hd` | 모든 의존성 한 번에 진단 (필수/선택 분류) |
| **how-to-use** | `/hyeondongs-harness:how-to-use-hd` | 플러그인 내 스킬 사용법 안내 (스킬 목록 조회 + 개별 사용법 설명) |

### 자동화 파이프라인

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/hyeondongs-harness:start-workflow-hd` | **전체 워크플로우 자동화** — 요청→난이도→Plan 리뷰→구현→품질 루프→PR→성찰 |
| **start-workflow-fs** | `/hyeondongs-harness:start-workflow-fs` | **풀스택 애자일 워크플로우** — 기능 정의→통신 계약→교차 리뷰→FE/BE 병렬 구현→통합 검증→PR |

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/hyeondongs-harness:request-hd` | 작업 유형별(컴포넌트 생성/페이지 생성/기능 수정/버그 수정) 단계적 질문 → Technical Spec 생성 |

> 커밋/Push/PR 워크플로우는 [`common` 플러그인](../common/README.md)으로 이전되었습니다. `/common:commit`, `/common:commit-push`, `/common:commit-pr`, `/common:commit-hard-push` 로 호출합니다.

### 컴포넌트 생성

| 스킬 | 호출 | 설명 |
|------|------|------|
| **component** | `/hyeondongs-harness:component-hd` | 컴포넌트 보일러플레이트 자동 생성 (.tsx + 스타일 + 테스트 + Storybook) |

### 테스트

| 스킬 | 호출 | 설명 |
|------|------|------|
| **unit-test** | `/hyeondongs-harness:unit-test-hd` | 변경된 컴포넌트/함수 대상 단위 테스트 수행 |
| **e2e-test** | `/hyeondongs-harness:e2e-test-hd` | Playwright 기반 E2E 테스트 수행 |
| **test-loop** | `/hyeondongs-harness:test-loop-hd` | 테스트 → 이슈 수정 → 재테스트 반복 (최대 5회) |

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **lint-check** | `/hyeondongs-harness:lint-check-hd` | ESLint + TypeScript + 접근성(a11y) 종합 검사 |
| **convention-check** | `/hyeondongs-harness:convention-check-hd` | 프론트엔드 컨벤션 위반 검사 및 보고 |
| **simplify-loop** | `/hyeondongs-harness:simplify-loop-hd` | 빌트인 `/simplify` 반복 실행 (수정 없을 때까지, 최대 10회) |

### 컨벤션 레퍼런스

| 스킬 | 호출 | 설명 |
|------|------|------|
| **default-conventions** | `/hyeondongs-harness:default-conventions-hd` | React/Next.js/TypeScript 개발 가이드라인 |

### 에이전트

hyeondongs-harness 자체 에이전트는 없다. 사용되는 에이전트는 모두 [`fe-harness`](../fe-harness/README.md) 의 것을 그대로 호출한다:

- `scope-reviewer` — Spec 기반 UI 구현/비즈니스 로직 검증
- `a11y-reviewer` — WAI-ARIA, 키보드 네비게이션, 색상 대비 등 접근성 검증
- `component-reviewer` — Props 설계, 재사용성, 렌더링 성능, 관심사 분리 검증
- `workflow-implementer`, `workflow-pr`, `workflow-reflection`

## 워크플로우

### 전체 자동화 (`/hyeondongs-harness:start-workflow-hd`)

```
Phase 1: 작업 범위 수집 (Plan 모드 진입)
Phase 2: 난이도 산정
Phase 3: Plan 작성 + 리뷰
Phase 4: 브랜치 + 상태 파일 + 자율 실행 시작
Phase 5: 구현
Phase 6: 빌드/타입 체크 (MANDATORY — 구현 직후 강제 실행)
Phase 7: 품질 루프 (최대 3회)
Phase 8: 컴포넌트/접근성 리뷰 (조건부)
Phase 9: PR / Push
Phase 10: 성찰
Phase 11: 최종 보고
```

### 풀스택 자동화 (`/hyeondongs-harness:start-workflow-fs`)

```
Phase 1: 기능 정의 + Feature Matrix (Plan 모드 진입)
Phase 2: Codex Spec 사전 검토
Phase 3: 통신 계약 정의
Phase 4: 계약 리뷰
Phase 5: 분리 Plan 작성
Phase 6: 브랜치 + 상태 파일
Phase 7: 프론트/백엔드 병렬 구현
Phase 8: 도메인별 품질 루프 (최대 3회)
Phase 9: Codex 품질 리뷰 (항상)
Phase 10: 통합 검증
Phase 11: 커밋/PR
Phase 12: 회고 + 정리
```

### 수동 실행 (개별 스킬)

```
/hyeondongs-harness:request-hd          # 1. 작업 정의
  ↓ (구현)
/hyeondongs-harness:simplify-loop-hd    # 2. 코드 간소화
  ↓
/hyeondongs-harness:convention-check-hd # 3. 컨벤션 검사
  ↓
/hyeondongs-harness:test-loop-hd        # 4. 테스트 + 수정 반복
  ↓
/hyeondongs-harness:lint-check-hd       # 5. 린트 + a11y 검사
  ↓
/common:commit-pr                          # 6. PR
```
