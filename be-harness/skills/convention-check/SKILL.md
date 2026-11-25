---
name: convention-check
description: "프로젝트 컨벤션 위배 사항을 검사하고 보고한다 (보고 전용 — 코드를 수정하지 않음). 커밋/PR 전 점검, '컨벤션 검사해줘' 요청 시 사용. --init으로 적용 컨벤션 선택, --doctor로 설정 진단."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/convention-check.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

실행 전에 [작업 계약과 실행 원칙](../start-workflow/references/execution-policy.md)을 읽는다.


## Prerequisites

### 설정 파일
- **`.conventions.json`** (프로젝트 루트): 적용할 컨벤션 목록을 저장한다.
- 이 파일이 없으면 기본값 (`default-conventions` + profile의 `projectConventions`)으로 동작한다.

### `--init` (컨벤션 선택)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **사용 가능한 컨벤션 목록 제시**: 플러그인 내 컨벤션 스킬과 프로젝트의 CLAUDE.md / projectConventions를 탐색하여 목록을 구성한다.

   > "어떤 컨벤션을 적용할까요? (복수 선택 가능, 쉼표 구분)"
   >
   > **플러그인 내장:**
   > 1. `default-conventions` — 개인 개발 컨벤션 (변경 범위, Assumption, 에러 일관성 등)
   >
   > **프로젝트:**
   > 2. `CLAUDE.md` — 프로젝트 아키텍처/레이어/에러 처리 컨벤션 (존재 시)
   > 3. profile의 `projectConventions` 에 나열된 파일들
   >
   > 예: `1,2` (기본 + CLAUDE.md) 또는 `1` (기본만)

2. **유저 선택 수집**: `AskUserQuestion`으로 선택을 받는다.

3. **설정 파일 생성**: 선택 결과를 `.conventions.json`으로 저장한다.
   ```json
   {
     "conventions": [
       { "name": "default-conventions", "source": "plugin", "skill": "be-harness:default-conventions" },
       { "name": "CLAUDE.md", "source": "project", "path": "CLAUDE.md" }
     ]
   }
   ```

4. **결과 보고**:
   > "`.conventions.json` 생성 완료. 적용 컨벤션: [선택 목록]"

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Convention Check — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .conventions.json | OK / MISSING | 없으면 기본값 사용 |
| default-conventions 스킬 | OK / MISSING | 플러그인 스킬 확인 |
| 프로젝트 컨벤션 파일 | 파일별 OK / MISSING | projectConventions 각 항목 |
| 적용 컨벤션 목록 | [목록] | 현재 설정 표시 |
```

---

## 공통 변경 범위

`../start-workflow/references/scope-contract.md`를 먼저 읽고 workflow_scope.py의 START_SHA→현재 tree+index 및 소유 untracked 결과를 사용한다. 아래 변경 파일/추가 라인 분석의 입력은 이 `paths`·`patch`·`index_patch`다. dirty 여부로 HEAD 기준을 선택하거나 일반 git diff로 재계산하지 않는다. 범위 오류는 BLOCKED이고, 파일이 없다고 전체 프로젝트로 자동 확대하지 않는다. 명시 custom 검증 명령은 원래 범위를 유지하되 그 명령의 출처를 보고한다.

## Execution

### 설정 파일 로드

1. 프로젝트 루트에서 `.conventions.json`을 읽는다.
2. 없으면 기본값으로 진행: `default-conventions` + profile의 `projectConventions` 파일들.

### 결정적 사전 검사 (LLM 검사보다 먼저)

기계적으로 판정되는 항목은 스크립트가 판정한다. LLM은 같은 항목을 다시 검사하지 않는다.

```bash
python3 -I -B "${CLAUDE_PLUGIN_ROOT}/skills/convention-check/assets/convention_facts.py" \
  --scope "{SCOPE_JSON}" --checks new-dependency,sql-in-literal
```

- `{SCOPE_JSON}`은 공통 변경 범위의 scope JSON 파일 경로다. stdout으로만 받았다면 `--scope -`로 stdin에 전달한다. 범위를 다시 계산하지 않는다.
- exit 0: `findings`를 그대로 보고서에 채택한다 (태그·심각도·`path:line` 유지). `unchecked_manifests`만 아래 LLM 절차로 확인한다.
- exit 2 (`BLOCKED:CONVENTION_FACTS`): 아래 LLM 절차 전체로 폴백하고, 보고서에 폴백 사유 1줄을 남긴다. 실패를 위반 0건으로 바꾸지 않는다.

주석 스타일도 스크립트가 판정한다. 새로 추가한 줄만 보고 테스트·생성 파일은 제외한다.

```bash
python3 -I -B "${CLAUDE_PLUGIN_ROOT}/skills/convention-check/assets/check_new_comments.py" \
  --scope "{SCOPE_JSON}" --json
```

- exit 0·1: `findings`(`[COMMENT_STYLE]` — 연속 3줄 이상인 새 주석 블록, 주석 안의 Spec 추적 ID, `Why:`·`[Assumption]`으로 시작하지 않는 새 주석 — 도구 지시문과 Go exported 선언의 `// Name ...` 문서 주석은 예외)를 그대로 채택한다. 블록 상한은 `COMMENT_MAX_BLOCK_LINES`(기본 2)다.
- exit 2 (`BLOCKED:COMMENT_CHECK`): 같은 세 규칙을 LLM이 새 주석에만 적용하고 폴백 사유 1줄을 남긴다.
- 주석이 코드를 되풀이하는지는 판정하지 않는다. `Why:` 접두사가 그 판정을 대신한다.

### 컨벤션 검사

설정된 각 컨벤션에 대해 위배 사항을 검사하고 보고한다:

- **`source: "plugin"`**: 해당 스킬의 내용을 기준으로 코드를 검사한다.
- **`source: "project"`**: 해당 파일의 내용을 기준으로 코드를 검사한다.

#### SQL 쿼리 패턴 검사

변경된 Repository 코드에서 SQL 조건문 패턴을 검사한다:

| 패턴 | 사용 기준 | 위반 조건 |
|------|----------|----------|
| `WHERE id IN (?)` | 후보 값이 **열거 가능**하고 개수가 유동적일 때 (e.g. 배치 조회, 다중 선택 삭제) | 단일 값 비교에 IN 사용 → `= ?`로 변경 권고 |
| `WHERE value <= ?` | **범위 비교**일 때 (e.g. 가격 이하, 날짜 이전, 재고 수량 조건) | 범위가 아닌 열거 비교에 <= 사용 → IN 또는 = 로 변경 권고 |
| `WHERE id IN (단일값)` | 금지 | `IN (?)`에 단일 값만 전달 → `= ?`로 변경 필수 |

단일 리터럴(`IN ('x')`·`IN (1)`·`IN ($1)`)은 사전 검사가 판정한다. LLM은 그 외만 본다: `IN (?)`에 실제로 단일 값만 전달되는지(sqlx.In·GORM의 슬라이스 확장은 정상), 범위 비교에 `IN`·열거 비교에 `<=`를 쓰는지.

위반 시 `[SQL_PATTERN]` 태그로 보고:
> "`repository.go:42` — `WHERE price IN (?)` → 범위 비교이므로 `WHERE price <= ?`가 적절합니다."

#### `[Assumption]` 태그 누락 검사

Spec(Technical Spec 또는 유저 지시)에 명시되지 않은 동작 변경이 코드에 존재하는지 검사한다:

1. 공통 범위의 `patch`·`index_patch`에서 새로 추가/변경된 비즈니스 로직을 추출한다.
2. 해당 변경이 Spec의 요구사항에 직접 대응하는지 확인한다.
3. 대응하지 않는 변경(e.g. 추가 필터, 정렬 변경, 상태 체크 추가 등)에 `[Assumption]` 주석 또는 커밋 메시지 태그가 없으면 위반으로 보고한다.
4. **예외**: 해당 변경이 PR 본문 또는 워크플로우 보고서의 "확정된 결정" 섹션에 기록되어 있으면 통과다 — Assumption Gate(`/common:commit-push` Step 3)에서 사용자 확인을 거쳐 태그가 제거된 정상 상태다.

#### 외부 패키지 Import 규칙

**프로젝트 최초 도입** 판정은 사전 검사가 한다: `go.mod`·`package.json`에 새로 추가된 직접 의존(또는 indirect → 직접 승격)이 `[NEW_DEPENDENCY]`다 (의도적 도입인지 확인 필요). LLM은 아래만 확인한다:

1. `unchecked_manifests`(스크립트가 파싱하지 않는 매니페스트·파싱 실패)의 새 의존 → `[NEW_DEPENDENCY]`.
2. 공통 범위의 `patch`·`index_patch`에서 새로 추가된 외부 패키지 import가 기존 import 방식(alias 등)과 일치하는지. 표준 라이브러리와 프로젝트 내부 패키지는 제외한다.

### 보고 형식

```markdown
## Convention Check 결과

| # | 파일:라인 | 위반 규칙 | 태그 | 제안 수정 |
|---|----------|----------|------|----------|

위반: N건 (태그별: [SQL_PATTERN] a건, [Assumption] b건, [NEW_DEPENDENCY] c건, [COMMENT_STYLE] d건)
```

- 본 스킬은 **보고만 한다**. 수정은 호출자(start-workflow 통합 수정 단계) 또는 유저 판단에 위임한다.
- 위반 0건이면 "위반: 0건 — 통과" 한 줄로 보고한다.
