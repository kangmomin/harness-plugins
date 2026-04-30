# hyeondong's harness

프론트엔드 개발 워크플로우를 위한 Claude Code 플러그인.

## 설치

```
/plugin marketplace add kangmomin/hyeondongs-harness
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

### 자동화 파이프라인

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/hyeondongs-harness:start-workflow-hd` | **전체 워크플로우 자동화** — 요청→난이도→Plan 리뷰→구현→품질 루프→PR→성찰 |
| **start-workflow-fs** | `/hyeondongs-harness:start-workflow-fs` | **풀스택 애자일 워크플로우** — 기능 정의→통신 계약→교차 리뷰→FE/BE 병렬 구현→통합 검증→PR |

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/hyeondongs-harness:request-hd` | 작업 유형별(컴포넌트 생성/페이지 생성/기능 수정/버그 수정) 단계적 질문 → Technical Spec 생성 |
| **commit** | `/hyeondongs-harness:commit-hd` | 변경사항을 논리적 단위별로 나눠서 커밋 |
| **commit-push** | `/hyeondongs-harness:commit-hd-push-hd` | commit + push |
| **commit-pr** | `/hyeondongs-harness:commit-hd-pr-hd` | commit + push + 브랜치 생성 + draft PR 오픈 |

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

| 에이전트 | 설명 |
|---------|------|
| **scope-reviewer** | Spec 기반 UI 구현/비즈니스 로직 검증 (start-workflow에서 자동 호출) |
| **a11y-reviewer** | WAI-ARIA, 키보드 네비게이션, 색상 대비 등 접근성 검증 |
| **component-reviewer** | Props 설계, 재사용성, 렌더링 성능, 관심사 분리 검증 |

## 워크플로우

### 전체 자동화 (`/hyeondongs-harness:start-workflow-hd`)

```
Phase 0: /request → Technical Spec 생성
Phase 1: 난이도 산정 (1-10)
Phase 2: scope-reviewer 에이전트 대기
Phase 3: Plan → 6관점 리뷰 (3+3 병렬) → [난이도 7+: Codex]
Phase 4: 구현 → commit
Phase 5: 품질 루프 (최대 3회)
  ├─ build + type-check
  ├─ simplify-loop
  ├─ convention-check
  ├─ test-loop (unit + e2e)
  ├─ scope-review
  └─ lint-check
  → 수정 있으면 재시작, 없으면 탈출
Phase 6: component-reviewer + a11y-reviewer (컴포넌트 변경 시)
Phase 7: commit-pr → PR
Phase 8: 성찰 (커밋 로그 분석)
Phase 9: 최종 보고 + 보완점 스킬 반영
```

### 풀스택 자동화 (`/hyeondongs-harness:start-workflow-fs`)

```
Phase 0: 백엔드/프론트 Spec 수집 → Feature Matrix
Phase 1: Integration Contract 정의
Phase 2: 계약 교차 리뷰 (BE 관점 + FE 관점)
Phase 3: 백엔드 Plan / 프론트 Plan / shared ownership 확정
Phase 4: FE workflow-implementer + BE workflow-implementer 병렬 구현
Phase 5: 도메인별 품질 루프 병렬 실행
Phase 6: contract diff / scope / a11y / component 통합 검증
Phase 7: 단일 PR 생성
Phase 8: 회고 + 정리
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
/hyeondongs-harness:commit-hd-pr-hd        # 6. PR
```
