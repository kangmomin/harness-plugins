# mimo-s-harness

Post-Math 개발 워크플로우를 위한 Claude Code 플러그인.

## 설치

```bash
claude plugin add kangmomin/mimo-s-harness
```

## 스킬 목록

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/mimo-s-harness:request` | 작업 유형별(생성/수정/검토/디버깅) 단계적 질문 → Technical Spec 생성 |
| **commit** | `/mimo-s-harness:commit` | 변경사항을 논리적 단위별로 나눠서 커밋 |
| **commit-push** | `/mimo-s-harness:commit-push` | commit + push |
| **commit-pr** | `/mimo-s-harness:commit-pr` | commit + push + 브랜치 생성 + draft PR 오픈 |

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **convention-check** | `/mimo-s-harness:convention-check` | 프로젝트 컨벤션 위반 검사 및 보고 |
| **simplify-loop** | `/mimo-s-harness:simplify-loop` | `/simplify` 반복 실행 (수정 없을 때까지, 최대 10회) |
| **e2e-test** | `/mimo-s-harness:e2e-test` | 변경된 API 대상 E2E 테스트 수행 |
| **e2e-test-loop** | `/mimo-s-harness:e2e-test-loop` | E2E 테스트 → 이슈 수정 → 재테스트 반복 (최대 5회) |

### 컨벤션 레퍼런스

| 스킬 | 호출 | 설명 |
|------|------|------|
| **default-conventions** | `/mimo-s-harness:default-conventions` | 에러 처리, VO 패턴, 트랜잭션 등 개발 가이드라인 |
| **pagenation** | `/mimo-s-harness:pagenation` | 커서 기반 페이지네이션 구현 컨벤션 |

### 코드 생성

| 스킬 | 호출 | 설명 |
|------|------|------|
| **db-gen-committed** | `/mimo-s-harness:db-gen-committed` | Liquibase migration 파일 생성 (committed 상태) |
| **apidog-schema-gen** | `/mimo-s-harness:apidog-schema-gen` | Apidog OAS에서 flat JSON 스키마 추출 + 코드 교차 검증 |

## 일반적인 워크플로우

```
/mimo-s-harness:request          # 1. 작업 정의 (생성/수정/검토/디버깅)
  ↓ (구현)
/mimo-s-harness:convention-check # 2. 컨벤션 검사
  ↓
/mimo-s-harness:simplify-loop    # 3. 코드 간소화
  ↓
/mimo-s-harness:e2e-test-loop    # 4. E2E 테스트 + 수정 반복
  ↓
/mimo-s-harness:commit-pr        # 5. 커밋 + PR
```
