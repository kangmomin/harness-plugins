# minmos-harness

Post-Math 개발 워크플로우를 위한 Claude Code 플러그인.

## 의존 플러그인

minmos-harness 는 다음 플러그인의 에이전트/스킬을 호출한다.

- `common` (필수) — `commit`, `commit-push`, `commit-pr`, `commit-hard-push` 등 커밋/PR 워크플로우 + `doc-gen`. 반드시 함께 설치해야 한다.
- `be-harness` (권장 의존) — `code-analyzer`, `code-verifier`, `edge-case-analyzer`, `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection` 에이전트. 미설치 시 start-workflow-mm·e2e-test-mm이 동일 프롬프트의 `general-purpose` 폴백으로 진행한다 (품질 상한은 be-harness 설치 시).

## 설치

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install be-harness@harness-plugins
/plugin install minmos-harness@harness-plugins
```

## 초기 세팅

```bash
/minmos-harness:minmo-init-mm     # 전체 환경 한 번에 세팅
/minmos-harness:minmo-doctor-mm   # 전체 환경 한 번에 진단
```

## 스킬 목록

### 세팅

| 스킬 | 호출 | 설명 |
|------|------|------|
| **minmo-init** | `/minmos-harness:minmo-init-mm` | 모든 의존성 한 번에 세팅 (MCP, 환경 변수, 컨벤션) |
| **minmo-doctor** | `/minmos-harness:minmo-doctor-mm` | 모든 의존성 한 번에 진단 (필수/선택 분류) |

### 자동화 파이프라인

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/minmos-harness:start-workflow-mm` | **전체 워크플로우 자동화** — 요청→난이도→Plan 리뷰→구현→품질 루프→문서→PR→성찰 |
| **start-workflow-fs** | `/minmos-harness:start-workflow-fs` | **풀스택 애자일 워크플로우** — 기능 정의→통신 계약→교차 리뷰→FE/BE 병렬 구현→통합 검증→PR |

### 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **request** | `/minmos-harness:request-mm` | 작업 유형별(생성/수정/검토/디버깅) 단계적 질문 → Technical Spec 생성 |

> 커밋/Push/PR 워크플로우(`commit`, `commit-push`, `commit-pr`, `commit-hard-push`)는 [`common` 플러그인](../common/README.md)으로 이전되었습니다. `/common:commit`, `/common:commit-push`, `/common:commit-pr`, `/common:commit-hard-push` 로 호출합니다.

### 품질 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **convention-check** | `/minmos-harness:convention-check-mm` | 프로젝트 컨벤션 위반 검사 및 보고 |
| **simplify-loop** | `/minmos-harness:simplify-loop-mm` | 4관점 리뷰 Workflow 루프로 코드 단순화 반복 적용 (수렴까지, 최대 10회; Workflow 미지원 시 빌트인 `/simplify` 반복 폴백) |
| **e2e-test** | `/minmos-harness:e2e-test-mm` | 변경된 API 대상 E2E 테스트 수행 |
| **e2e-test-loop** | `/minmos-harness:e2e-test-loop-mm` | E2E 테스트 → 이슈 수정 → 재테스트 반복 (최대 5회) |

### 컨벤션 레퍼런스

| 스킬 | 호출 | 설명 |
|------|------|------|
| **default-conventions** | `/minmos-harness:default-conventions-mm` | 에러 처리, VO 패턴, 트랜잭션 등 개발 가이드라인 |
| **pagenation** | `/minmos-harness:pagenation-mm` | 커서 기반 페이지네이션 구현 컨벤션 |

### 코드 생성 / 문서 동기화

| 스킬 | 호출 | 설명 |
|------|------|------|
| **db-gen-committed** | `/minmos-harness:db-gen-committed-mm` | Liquibase migration 파일 생성 (committed 상태) |
| **apidog-schema-gen** | `/minmos-harness:apidog-schema-gen-mm` | Apidog OAS에서 flat JSON 스키마 추출 + 코드 교차 검증 |
| **e2e-apidog-schema-gen** | `/minmos-harness:e2e-apidog-schema-gen-mm` | E2E 실측 결과 기반으로 Apidog 응답 케이스 추가 + 스키마 보정 |

### 에이전트

| 에이전트 | 설명 |
|---------|------|
| **workflow-doc-sync** | E2E 테스트 결과 기반 Apidog 스키마 동기화 (start-workflow에서 자동 호출) |

> 그 외 `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection`, `code-analyzer`, `code-verifier`, `edge-case-analyzer` 에이전트는 [`be-harness`](../be-harness/README.md) 의 것을 사용한다. **권장 의존** — 미설치 시 start-workflow-mm·e2e-test-mm이 동일 프롬프트의 `general-purpose` 폴백으로 진행한다 (품질 상한은 be-harness 설치 시).

## 워크플로우

### 전체 자동화 (`/minmos-harness:start-workflow-mm`)

Build 모드(기본):

```
Pre-flight: 환경 점검 (.env / Apidog MCP / PostgreSQL MCP / be-harness 에이전트)
Phase 1: Spec 수집 (/request-mm, Plan 모드)
Phase 2: 난이도 산정 (1-10)
Phase 3: 실행 전략 판정 (sequential / parallel-slices / fullstack)
Phase 4: E2E 메인 플로우 수집
Phase 5: Plan 작성 + 리뷰
  ├─ 5.2 Claude 다관점 보강 (1회)
  └─ 5.3 Codex 검증 루프 (최대 5회)
Phase 6: 브랜치 + 상태 파일 생성 → 자율 실행 시작
Phase 7~13: 자율 실행 (묻지 않고 완주)
  구현 → 빌드 체크 → 품질 루프(E2E 포함) → Codex 리뷰 → Apidog 동기화 → PR → 회고
Phase 14: 최종 보고
```

> `--analyze` / `--verify` 모드는 `references/analyze-verify-modes.md`로 분리되어 있다 (Phase A1~A4 / V1~V5).

### 풀스택 자동화 (`/minmos-harness:start-workflow-fs`)

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
/minmos-harness:request-mm          # 1. 작업 정의
  ↓ (구현)
/minmos-harness:simplify-loop-mm    # 2. 코드 간소화
  ↓
/minmos-harness:convention-check-mm # 3. 컨벤션 검사
  ↓
/minmos-harness:e2e-test-loop-mm    # 4. E2E 테스트 + 수정 반복
  ↓
/minmos-harness:e2e-apidog-schema-gen-mm # 5. Apidog 동기화
  ↓
/common:commit-pr                      # 6. PR
```
