# minmos-harness

Post-Math 백엔드 개발을 위한 **be-harness 오버레이 플러그인**.

워크플로우 절차 자체는 갖지 않는다. `be-harness` 의 절차 위에 Post-Math 특화 델타(Apidog 문서 동기화, gRPC·PubSub E2E, PostgreSQL MCP 기반 DB 안전 규칙, Post-Math 컨벤션)만 얹는다.

> **v2.0.0 breaking change** — be-harness 와 중복되던 스킬 7종이 **오버레이로 흡수**되고 `-mm` 접미사가 전부 제거되었다. 이관 표는 아래 [마이그레이션](#마이그레이션-v1x--v2) 참조.

## 의존 플러그인

- **`be-harness` (필수)** — 워크플로우·Spec·컨벤션·E2E·단순화 절차의 베이스. 없으면 minmos-harness 는 동작하지 않는다.
- `common` (권장) — 커밋/PR 워크플로우(`commit`, `commit-push`, `commit-pr`, `merge`), `doc-gen`, 풀스택 진입점(`start-workflow --fs`).
- `db-tools` (선택) — `db-gen-committed` 가 호출.

## 설치

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install be-harness@harness-plugins
/plugin install minmos-harness@harness-plugins
```

## 초기 세팅

```bash
/minmos-harness:init      # MCP·환경 변수·컨벤션·오버레이 한 번에 세팅
/minmos-harness:doctor    # 전체 환경 + 오버레이 적용 상태 진단
```

## 오버레이 구조

Post-Math 특화 규칙은 `overlay/` 에 있고, 두 경로로 적용된다 (규약: [`docs/overlay.md`](../docs/overlay.md)).

| 경로 | 적용 시점 | 설정 |
|------|----------|------|
| **A. 플러그인 내장** | `/minmos-harness:start-workflow` 호출 시 | 기본값, 설정 불필요 |
| **B. 프로젝트 복사** | `/be-harness:*` 를 **직접** 호출해도 적용 | `/minmos-harness:init` 의 오버레이 설치 단계 |

오버레이는 베이스의 Phase 번호에 의존하지 않는다. **앵커(Phase 제목)** 로 삽입·치환 위치를 지정하므로, be-harness 가 Phase를 추가해도 깨지지 않는다.

| 오버레이 | 얹는 내용 |
|---------|----------|
| `overlay/common.md` | Pre-flight 추가(`secret/.env` · Apidog MCP · PostgreSQL MCP), 로컬 DB 전용 원칙 |
| `overlay/start-workflow.md` | `Phase 1` 직후 **E2E 메인 플로우 수집** / `Phase 8` 직후 **Codex 품질 리뷰** / `Phase 9` → **Apidog 동기화** 치환 / Codex quota 폴백 |
| `overlay/request.md` | Post-Math 계층 매핑 확정, Go 특화 상태 함수 탐색, 구현 체크리스트 |
| `overlay/e2e-test.md` | 프로토콜 분류(REST/gRPC/MIXED), gRPC 환경, status code 정합성, DB 시드·정리 |
| `overlay/e2e-test-loop.md` | 환경 probe 보강 |
| `overlay/convention-check.md` | 기본 컨벤션에 `pagenation` + Post-Math 컨벤션 추가 |
| `overlay/default-conventions.md` | Post-Math 고유 컨벤션 병합 |

## 스킬 목록

### 워크플로우 (오버레이 위임)

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/minmos-harness:start-workflow` | `be-harness:start-workflow` + minmos 오버레이. 절차는 be-harness 가 정의 |

`/common:start-workflow` 로 진입하면 도메인 판정 후 이 스킬이 자동 선택된다 (오버레이 감지).

### 세팅 / 진단

| 스킬 | 호출 | 설명 |
|------|------|------|
| **init** | `/minmos-harness:init` | MCP·환경 변수·컨벤션·오버레이(경로 B) 한 번에 세팅 |
| **doctor** | `/minmos-harness:doctor` | 의존성·MCP·오버레이 적용 상태 진단 (필수/선택 분류) |

### Post-Math 고유 기능

| 스킬 | 호출 | 설명 |
|------|------|------|
| **apidog-schema-gen** | `/minmos-harness:apidog-schema-gen` | Apidog OAS에서 flat JSON 스키마 추출 + 코드 교차 검증 |
| **e2e-apidog-schema-gen** | `/minmos-harness:e2e-apidog-schema-gen` | E2E 실측 결과 기반 Apidog 응답 케이스 추가 + 스키마 보정 |
| **db-gen-committed** | `/minmos-harness:db-gen-committed` | Liquibase migration 파일 생성 (committed 상태) |
| **pagenation** | `/minmos-harness:pagenation` | 커서 기반 페이지네이션 구현 컨벤션 |

### 에이전트

| 에이전트 | 설명 |
|---------|------|
| **workflow-doc-sync** | E2E 테스트 결과 기반 Apidog 스키마 동기화 (start-workflow Phase 9 치환에서 자동 호출) |

그 외 `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection`, `code-analyzer`, `code-verifier`, `edge-case-analyzer` 는 [`be-harness`](../be-harness/README.md) 의 것을 사용한다.

## 워크플로우

### 전체 자동화 (`/minmos-harness:start-workflow`)

be-harness Phase 구성에 오버레이 델타가 얹힌 실행 흐름:

```
Pre-flight: profile 점검 (be) + .env / Apidog MCP / PostgreSQL MCP (오버레이)
Phase 1 : Spec 수집 (/be-harness:request + request 오버레이, Plan 모드)
Phase 1+: E2E 메인 플로우 수집                          ← 오버레이 삽입
Phase 2 : 난이도 산정 (1-10)
Phase 3 : 실행 전략 판정 (sequential / parallel-slices / fullstack)
Phase 4 : Plan 작성 → Claude 다관점 보강 → Codex 검증 루프  (quota 시 Claude 패널 대체 ← 오버레이)
Phase 5 : 브랜치 + 상태 파일 + implementation-notes + 회귀 baseline → 자율 실행 시작
Phase 6~11: 자율 실행 (묻지 않고 완주)
  6 TDD 구현 → 7 빌드 체크 → 8 품질 루프(E2E 포함)
  8+ Codex 품질 리뷰                                    ← 오버레이 삽입
  9 Apidog 문서 동기화 (workflow-doc-sync)              ← 오버레이 치환
  10 PR → 11 회고
Phase 12: impl-notes HTML 렌더링 → 최종 보고
```

> `--analyze` / `--verify` 모드는 be-harness 의 `references/analyze-verify-modes.md` 를 그대로 따른다.

### 풀스택 (`/common:start-workflow --fs`)

화면과 API가 함께 바뀌면 common 의 풀스택 경로를 쓴다. 계약 확정 → FE/BE 병렬 구현 → 통합 검증 → 단일 PR.

### 수동 실행 (개별 스킬)

```
/be-harness:request                    # 1. 작업 정의 (minmos 오버레이 적용하려면 경로 B 설치)
  ↓ (구현)
/be-harness:simplify-loop              # 2. 4관점 리뷰 기반 단순화
  ↓
/be-harness:convention-check           # 3. 컨벤션 검사
  ↓
/be-harness:e2e-test-loop              # 4. E2E + 수정 반복 + 자기 점검 리포트
  ↓
/minmos-harness:e2e-apidog-schema-gen  # 5. Apidog 동기화
  ↓
/common:commit-pr                      # 6. PR
```

## 마이그레이션 (v1.x → v2)

| 이전 (v1.x) | 현재 (v2) |
|------------|----------|
| `/minmos-harness:start-workflow-mm` | `/minmos-harness:start-workflow` |
| `/minmos-harness:start-workflow-fs` | `/common:start-workflow --fs` |
| `/minmos-harness:request-mm` | `/be-harness:request` (+ `overlay/request.md`) |
| `/minmos-harness:e2e-test-mm` | `/be-harness:e2e-test` (+ `overlay/e2e-test.md`) |
| `/minmos-harness:e2e-test-loop-mm` | `/be-harness:e2e-test-loop` (+ `overlay/e2e-test-loop.md`) |
| `/minmos-harness:convention-check-mm` | `/be-harness:convention-check` (+ `overlay/convention-check.md`) |
| `/minmos-harness:default-conventions-mm` | `/be-harness:default-conventions` (+ `overlay/default-conventions.md`) |
| `/minmos-harness:simplify-loop-mm` | `/be-harness:simplify-loop` (4관점 루프가 be-harness 로 승격됨) |
| `/minmos-harness:minmo-init-mm` | `/minmos-harness:init` |
| `/minmos-harness:minmo-doctor-mm` | `/minmos-harness:doctor` |
| `/minmos-harness:apidog-schema-gen-mm` | `/minmos-harness:apidog-schema-gen` |
| `/minmos-harness:e2e-apidog-schema-gen-mm` | `/minmos-harness:e2e-apidog-schema-gen` |
| `/minmos-harness:db-gen-committed-mm` | `/minmos-harness:db-gen-committed` |
| `/minmos-harness:pagenation-mm` | `/minmos-harness:pagenation` |

**기능 손실은 없다.** 삭제된 스킬의 Post-Math 특화 절차는 `overlay/references/` 로 이관되었고, 범용 절차(4관점 simplify 루프, E2E 자기 점검 HTML 리포트, Implementation Notes)는 be-harness 베이스로 승격되어 be-harness 단독 사용자도 쓸 수 있게 되었다.

**해야 할 일**: `be-harness` 를 설치하고 `/minmos-harness:init` 을 다시 실행한다. `/be-harness:*` 를 직접 호출한다면 오버레이 설치 단계(경로 B)에서 "설치"를 선택한다.
