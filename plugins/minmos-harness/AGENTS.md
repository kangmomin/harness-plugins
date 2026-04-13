# minmos-harness (Codex CLI)

Go 백엔드 개발 워크플로우 자동화 지침.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## 사용 가능한 스킬 (`$스킬명`으로 호출)

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow-mm** | `$start-workflow-mm` | 전체 워크플로우 자동화 (request→구현→품질 루프→PR→성찰) |
| **start-workflow-fs** | `$start-workflow-fs` | 풀스택 애자일 워크플로우 (기능 정의→통신 계약→교차 리뷰→FE/BE 병렬 구현→통합 검증→PR) |
| **request-mm** | `$request-mm` | 작업 유형별 단계적 질문 → Technical Spec 생성 |
| **commit-mm** | `$commit-mm` | 변경사항을 논리적 단위별로 나눠서 커밋 |
| **commit-push-mm** | `$commit-push-mm` | commit + push |
| **commit-pr-mm** | `$commit-pr-mm` | commit + push + 브랜치 생성 + draft PR |
| **commit-hard-push-mm** | `$commit-hard-push-mm` | commit + push (보호 브랜치 제한 없음) |
| **convention-check-mm** | `$convention-check-mm` | 프로젝트 컨벤션 위반 검사 |
| **simplify-loop-mm** | `$simplify-loop-mm` | 코드 단순화 반복 (최대 10회) |
| **e2e-test-mm** | `$e2e-test-mm` | E2E API 테스트 (REST + gRPC) |
| **e2e-test-loop-mm** | `$e2e-test-loop-mm` | E2E 테스트 + 수정 반복 (최대 5회) |
| **apidog-schema-gen-mm** | `$apidog-schema-gen-mm` | Apidog OAS에서 flat JSON 스키마 추출 |
| **e2e-apidog-schema-gen-mm** | `$e2e-apidog-schema-gen-mm` | E2E 실측 → Apidog 명세 보정 |
| **default-conventions-mm** | `$default-conventions-mm` | 에러 처리, VO 패턴, 트랜잭션 가이드라인 |
| **pagenation-mm** | `$pagenation-mm` | 커서 기반 페이지네이션 컨벤션 |
| **db-gen-committed-mm** | `$db-gen-committed-mm` | Liquibase migration 생성 |
| **minmo-init-mm** | `$minmo-init-mm` | 환경 초기 설정 |
| **minmo-doctor-mm** | `$minmo-doctor-mm` | 환경 진단 |
| **how-to-use-mm** | `$how-to-use-mm` | 스킬 사용법 안내 |

## 서브에이전트

| 에이전트 | 역할 |
|---------|------|
| **scope-reviewer** | 읽기 전용 advisor. Spec 기반 비즈니스 로직/엣지 케이스 검증 후 `Verdict/Next Action` 보고 |
| **workflow-implementer** | Plan 기반 코드 구현 + 논리적 단위 커밋 |
| **workflow-pr** | 브랜치 생성, push, draft PR |
| **workflow-reflection** | 읽기 전용 advisor. 워크플로우 성찰 + 스킬 보완점 제안 |
| **workflow-doc-sync** | API 문서 동기화 |
| **edge-case-analyzer** | 다관점 엣지 케이스 분석 |

## 커밋 컨벤션

| Prefix | 사용 시점 |
|--------|----------|
| Add | 새로운 기능 또는 파일 추가 |
| Fix | 버그 수정 및 오류 해결 |
| Del | 불필요한 코드나 리소스 삭제 |
| Refactor | 기능 변화 없이 코드 구조 개선 |
| Doc | 문서 수정 |
| Test | 테스트 코드 추가 또는 수정 |
| Chore | 빌드/설정/의존성 업데이트 |
| WIP | 진행 중인 작업 임시 저장 |
