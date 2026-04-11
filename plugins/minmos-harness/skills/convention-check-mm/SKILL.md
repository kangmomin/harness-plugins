---
name: convention-check-mm
description: "프로젝트 컨벤션 위배 사항을 검사하고 보고"
---

## Prerequisites

### 설정 파일
- **`.convention-check.json`** (프로젝트 루트): 적용할 컨벤션 목록을 저장한다.
- 이 파일이 없으면 기본값 (`default-conventions` + `pagenation`)으로 동작한다.

### `--init` (컨벤션 선택)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **사용 가능한 컨벤션 목록 제시**: 플러그인 내 컨벤션 스킬과 프로젝트의 CLAUDE.md를 탐색하여 목록을 구성한다.

   > "어떤 컨벤션을 적용할까요? (복수 선택 가능, 쉼표 구분)"
   >
   > **플러그인 내장:**
   > 1. `default-conventions` — 에러 처리, VO 패턴, 트랜잭션 관리
   > 2. `pagenation` — 커서 기반 페이지네이션
   >
   > **프로젝트:**
   > 3. `CLAUDE.md` — 프로젝트 아키텍처 및 레이어 컨벤션
   >
   > 예: `1,2,3` (전체) 또는 `1` (에러 처리만)

2. **유저 선택 수집**: 유저에게 선택을 받는다.

3. **설정 파일 생성**: 선택 결과를 `.convention-check.json`으로 저장한다.
   ```json
   {
     "conventions": [
       { "name": "default-conventions", "source": "plugin", "skill": "minmos-harness:default-conventions-mm" },
       { "name": "pagenation", "source": "plugin", "skill": "minmos-harness:pagenation-mm" },
       { "name": "CLAUDE.md", "source": "project", "path": "CLAUDE.md" }
     ]
   }
   ```

4. **결과 보고**:
   > "`.convention-check.json` 생성 완료. 적용 컨벤션: [선택 목록]"

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Convention Check — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .convention-check.json | OK / MISSING | 없으면 기본값 사용 |
| default-conventions 스킬 | OK / MISSING | 플러그인 스킬 확인 |
| pagenation 스킬 | OK / MISSING | 플러그인 스킬 확인 |
| CLAUDE.md | OK / MISSING | 프로젝트 루트 확인 |
| 적용 컨벤션 목록 | [목록] | 현재 설정 표시 |
```

---

## Execution

### 설정 파일 로드

1. 프로젝트 루트에서 `.convention-check.json`을 읽는다.
2. 없으면 기본값으로 진행: `default-conventions` + `pagenation`

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

위반 시 `[SQL_PATTERN]` 태그로 보고:
> "`repository.go:42` — `WHERE price IN (?)` → 범위 비교이므로 `WHERE price <= ?`가 적절합니다."

#### `[Assumption]` 태그 누락 검사

Spec(Technical Spec 또는 유저 지시)에 명시되지 않은 동작 변경이 코드에 존재하는지 검사한다:

1. `git diff`에서 새로 추가/변경된 비즈니스 로직을 추출한다.
2. 해당 변경이 Spec의 요구사항에 직접 대응하는지 확인한다.
3. 대응하지 않는 변경(e.g. 추가 필터, 정렬 변경, 상태 체크 추가 등)에 `[Assumption]` 주석 또는 커밋 메시지 태그가 없으면 위반으로 보고한다.

#### 트랜잭션 Commit/Rollback 쌍 완결성 검사

변경된 Usecase 코드에서 트랜잭션의 Commit/Rollback 쌍이 올바르게 구성되어 있는지 검사한다.
(`default-conventions` 3.2절 "트랜잭션 관리 (Unit of Work)" 기준)

**검사 대상**: `git diff`에서 변경된 `*_usecase.go` 파일 중 `uow.Begin` 또는 `tx.Begin`을 포함하는 함수.

| 검사 항목 | 위반 조건 | 태그 |
|----------|----------|------|
| Begin 후 Rollback 누락 | `uow.Begin`/`tx.Begin` 이후 에러 반환 경로에 `Rollback()` 호출이 없음 | `[TX_MISSING_ROLLBACK]` |
| Commit 실패 시 Rollback 누락 | `uow.Commit`/`tx.Commit` 에러 분기에 `Rollback()` 호출이 없음 | `[TX_COMMIT_NO_ROLLBACK]` |
| defer Rollback 사용 | `defer tx.Rollback()` 또는 `defer uow.Rollback()` 패턴 사용 | `[TX_DEFER_ROLLBACK]` |
| committed 플래그 패턴 | `committed := false` + `defer`로 조건부 Rollback 처리 | `[TX_COMMITTED_FLAG]` |

**검사 절차**:

1. 변경된 `*_usecase.go` 파일을 Grep으로 식별한다.
2. 해당 파일에서 `Begin(` 호출을 포함하는 함수 범위를 Read로 읽는다.
3. 함수 내 모든 에러 반환 경로(`if err != nil { ... return`)를 추적한다.
4. 각 에러 반환 경로 직전에 `Rollback()` 호출이 있는지 확인한다.
5. `defer` + `Rollback` 패턴 또는 `committed` 플래그 패턴이 있는지 확인한다.

위반 시 보고:
> "`order_usecase.go:78` — `[TX_MISSING_ROLLBACK]` `uow.Begin` 이후 에러 반환(line 85)에서 `Rollback()` 호출이 누락되었습니다."
> "`payment_usecase.go:42` — `[TX_DEFER_ROLLBACK]` `defer uow.Rollback()` 패턴은 금지입니다. 각 에러 시점에서 명시적으로 호출하세요."

---

#### 외부 패키지 Import 규칙

변경된 파일에 새로운 외부 패키지 import가 추가된 경우, 프로젝트 내 기존 사용 패턴과 일치하는지 자동 검사한다:

1. `git diff`에서 새로 추가된 import 라인을 추출한다.
2. 표준 라이브러리(`fmt`, `net/http` 등)와 프로젝트 내부 패키지는 제외한다.
3. 남은 외부 패키지에 대해 `Grep`으로 프로젝트 내 기존 사용 여부를 확인한다:
   - **기존에 사용 중**: 기존 import 방식(alias 등)과 일치하는지 확인
   - **프로젝트 최초 도입**: `[NEW_DEPENDENCY]`로 표기하고 위반으로 보고 (의도적 도입인지 확인 필요)
