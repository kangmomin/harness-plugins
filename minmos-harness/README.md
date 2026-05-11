# minmos-harness

Post-Math 개발 워크플로우를 위한 Claude Code 플러그인.

## 의존 플러그인

minmos-harness 는 다음 두 플러그인의 에이전트/스킬을 호출한다. **반드시 함께 설치해야 한다.**

- `common` — `commit`, `commit-push`, `commit-pr`, `commit-hard-push` 등 커밋/PR 워크플로우 + `doc-gen`
- `be-harness` — `code-analyzer`, `code-verifier`, `edge-case-analyzer`, `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection` 에이전트

## 설치

```
/plugin marketplace add kangmomin/minmos-harness
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
| **simplify-loop** | `/minmos-harness:simplify-loop-mm` | 빌트인 `/simplify` 반복 실행 (수정 없을 때까지, 최대 10회) |
| **e2e-test** | `/minmos-harness:e2e-test-mm` | 변경된 API 대상 E2E 테스트 수행 |
| **e2e-test-loop** | `/minmos-harness:e2e-test-mm-loop-mm` | E2E 테스트 → 이슈 수정 → 재테스트 반복 (최대 5회) |

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
| **e2e-apidog-schema-gen** | `/minmos-harness:e2e-apidog-schema-gen-mm` | E2E 실측 결과 기반���로 Apidog 응답 케이스 추가 + 스키마 보정 |

### 에이전트

| 에이전트 | 설명 |
|---------|------|
| **workflow-doc-sync** | E2E 테스트 결과 기반 Apidog 스키마 동기화 (start-workflow에서 자동 호출) |

> 그 외 `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection`, `code-analyzer`, `code-verifier`, `edge-case-analyzer` 에이전트는 [`be-harness`](../be-harness/README.md) 의 것을 그대로 사용한다.

## 워크플로우

### 전체 자동화 (`/minmos-harness:start-workflow-mm`)

```
Phase 0: /request → Technical Spec 생성
Phase 1: 난이도 산정 (1-10)
Phase 2: scope-reviewer 에이전트 대기
Phase 3: Plan → 6관점 리뷰 (3+3 병렬) → [난이도 7+: Codex]
Phase 4: 구현 → commit
Phase 5: 품질 루프 (최대 3회)
  ├─ simplify-loop
  ├─ convention-check
  ├─ e2e-test-loop
  └─ scope-review
  → 수정 있으면 재시작, 없으면 탈출
Phase 6: e2e-apidog-schema-gen (API 변경 시만)
Phase 7: /common:commit-pr → PR
Phase 8: 성찰 (커밋 로그 분석)
Phase 9: 최종 보고 + 보완점 스킬 반영
```

### 풀스택 자동화 (`/minmos-harness:start-workflow-fs`)

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
/minmos-harness:request-mm          # 1. 작업 정의
  ↓ (구현)
/minmos-harness:simplify-loop-mm    # 2. 코드 간소화
  ↓
/minmos-harness:convention-check-mm # 3. 컨벤션 검사
  ↓
/minmos-harness:e2e-test-mm-loop-mm    # 4. E2E 테스트 + 수정 반복
  ↓
/minmos-harness:e2e-apidog-schema-gen-mm # 5. Apidog 동기화
  ↓
/common:commit-pr                      # 6. PR
```
