# hyeondongs-harness (Codex CLI)

React 프론트엔드 개발 워크플로우 자동화 지침.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## 사용 가능한 스킬 (`$스킬명`으로 호출)

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow-hd** | `$start-workflow-hd` | 전체 워크플로우 자동화 (request→구현→품질 루프→PR→성찰) |
| **request-hd** | `$request-hd` | 작업 유형별 질문 + 레이아웃 컨펌 → Technical Spec 생성 |
| **commit-hd** | `$commit-hd` | 변경사항을 논리적 단위별로 나눠서 커밋 |
| **commit-push-hd** | `$commit-push-hd` | commit + push |
| **commit-pr-hd** | `$commit-pr-hd` | commit + push + 브랜치 생성 + draft PR |
| **component-hd** | `$component-hd` | 컴포넌트 보일러플레이트 자동 생성 |
| **convention-check-hd** | `$convention-check-hd` | 프론트엔드 컨벤션 위반 검사 |
| **lint-check-hd** | `$lint-check-hd` | ESLint + TypeScript + 접근성(a11y) 검사 |
| **simplify-loop-hd** | `$simplify-loop-hd` | 코드 단순화 반복 (최대 10회) |
| **unit-test-hd** | `$unit-test-hd` | Vitest/Jest 단위 테스트 |
| **e2e-test-hd** | `$e2e-test-hd` | Playwright E2E 테스트 |
| **test-loop-hd** | `$test-loop-hd` | 테스트 + 수정 반복 (최대 5회) |
| **default-conventions-hd** | `$default-conventions-hd` | React/Next.js/TypeScript 가이드라인 |
| **hyeondong-init-hd** | `$hyeondong-init-hd` | 환경 초기 설정 |
| **hyeondong-doctor-hd** | `$hyeondong-doctor-hd` | 환경 진단 |
| **how-to-use-hd** | `$how-to-use-hd` | 스킬 사용법 안내 |

## 작업 유형 (request-hd)

| # | 유형 | 레이아웃 컨펌 |
|---|------|-------------|
| 1 | 화면 생성 | ASCII 레이아웃 → 컨펌 |
| 2 | 화면 수정 | As-Is / To-Be 비교 → 컨펌 |
| 3 | 컴포넌트 생성 | 내부 레이아웃 + 상태별 → 컨펌 |
| 4 | 컴포넌트 수정 | As-Is / To-Be 비교 → 컨펌 |
| 5 | API 연동 | 레이아웃 없음 |
| 6 | API 연동 수정 | 레이아웃 없음 |

## 서브에이전트

| 에이전트 | 역할 |
|---------|------|
| **scope-reviewer** | Spec 기반 UI 구현/엣지 케이스 검증 |
| **workflow-implementer** | Plan 기반 코드 구현 + 논리적 단위 커밋 |
| **workflow-pr** | 브랜치 생성, push, draft PR |
| **workflow-reflection** | 커밋 로그 분석 → 성찰 + 스킬 보완점 |
| **a11y-reviewer** | WAI-ARIA, 키보드, 색상 대비 접근성 검증 |
| **component-reviewer** | Props 설계, 재사용성, 렌더링 성능 검증 |

## 커밋 컨벤션

| Prefix | 사용 시점 |
|--------|----------|
| Add | 새로운 기능 또는 파일 추가 |
| Fix | 버그 수정 및 오류 해결 |
| Del | 불필요한 코드나 리소스 삭제 |
| Refactor | 기능 변화 없이 코드 구조 개선 |
| Style | 스타일/레이아웃 변경 (기능 무관) |
| Doc | 문서 수정 |
| Test | 테스트 코드 추가 또는 수정 |
| Chore | 빌드/설정/의존성 업데이트 |
| WIP | 진행 중인 작업 임시 저장 |
