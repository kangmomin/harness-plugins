---
name: convention-check
description: "프론트엔드 프로젝트 컨벤션 위배 사항을 검사하고 보고"
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion
user-invocable: true
---

## Prerequisites

### 설정 파일
- **`.donghyeon-config.json`** (프로젝트 루트): `conventions` 배열에서 적용할 컨벤션 목록을 참조한다.
- 이 파일이 없으면 기본값 (`default-conventions`)으로 동작한다.

### `--init` (컨벤션 선택)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **사용 가능한 컨벤션 목록 제시**: 플러그인 내 컨벤션 스킬과 프로젝트의 CLAUDE.md를 탐색하여 목록을 구성한다.

   > "어떤 컨벤션을 적용할까요? (복수 선택 가능, 쉼표 구분)"
   >
   > **플러그인 내장:**
   > 1. `default-conventions` — React/Next.js/TypeScript 가이드라인
   >
   > **프로젝트:**
   > 2. `CLAUDE.md` — 프로젝트 아키텍처 컨벤션
   >
   > 예: `1,2` (전체) 또는 `1` (기본만)

2. **유저 선택 수집**: `AskUserQuestion`으로 선택을 받는다.

3. **설정 파일 업데이트**: `.donghyeon-config.json`의 `conventions` 배열을 업데이트한다.
   ```json
   {
     "conventions": [
       { "name": "default-conventions", "source": "plugin", "skill": "donghyeons-harness:default-conventions" },
       { "name": "CLAUDE.md", "source": "project", "path": "CLAUDE.md" }
     ]
   }
   ```

4. **결과 보고**:
   > "컨벤션 설정 완료. 적용 컨벤션: [선택 목록]"

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## Convention Check — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .donghyeon-config.json | OK / MISSING | conventions 배열 확인 |
| default-conventions 스킬 | OK / MISSING | 플러그인 스킬 확인 |
| CLAUDE.md | OK / MISSING | 프로젝트 루트 확인 |
| 적용 컨벤션 목록 | [목록] | 현재 설정 표시 |
```

---

## Execution

### 설정 파일 로드

1. 프로젝트 루트에서 `.donghyeon-config.json`을 읽는다.
2. `conventions` 배열이 없으면 기본값으로 진행: `default-conventions`

### 컨벤션 검사

설정된 각 컨벤션에 대해 위배 사항을 검사하고 보고한다:

- **`source: "plugin"`**: 해당 스킬의 내용을 기준으로 코드를 검사한다.
- **`source: "project"`**: 해당 파일의 내용을 기준으로 코드를 검사한다.

#### `[Assumption]` 태그 누락 검사

Spec(Technical Spec 또는 유저 지시)에 명시되지 않은 동작 변경이 코드에 존재하는지 검사한다:

1. `git diff`에서 새로 추가/변경된 비즈니스 로직을 추출한다.
2. 해당 변경이 Spec의 요구사항에 직접 대응하는지 확인한다.
3. 대응하지 않는 변경(e.g. 추가 필터, 정렬 변경, 상태 체크 추가 등)에 `[Assumption]` 주석 또는 커밋 메시지 태그가 없으면 위반으로 보고한다.

#### 외부 패키지 Import 규칙

변경된 파일에 새로운 외부 패키지 import가 추가된 경우, 프로젝트 내 기존 사용 패턴과 일치하는지 자동 검사한다:

1. `git diff`에서 새로 추가된 import 라인을 추출한다.
2. `react`, `next`, 프로젝트 내부 경로(`@/`, `~/`, `../`)는 제외한다.
3. 남은 외부 패키지에 대해 `Grep`으로 프로젝트 내 기존 사용 여부를 확인한다:
   - **기존에 사용 중**: 기존 import 방식(alias 등)과 일치하는지 확인
   - **프로젝트 최초 도입**: `[NEW_DEPENDENCY]`로 표기하고 위반으로 보고 (의도적 도입인지 확인 필요)

#### 컴포넌트 구조 검사

`.donghyeon-config.json`의 `componentPattern`에 따라:

- **feature-based**: 컴포넌트가 올바른 feature 디렉토리에 배치되었는지
- **atomic**: atoms/molecules/organisms 분류가 적절한지
- **flat**: components/ 하위에 배치되었는지

---

## 출력 형식

```markdown
## Convention Check 결과

### 컨벤션 위반
| # | 컨벤션 | 파일 | 위반 내용 | 심각도 |
|---|--------|------|----------|--------|
| 1 | default-conventions | src/... | [내용] | ERROR / WARN |

### [Assumption] 태그 누락
| # | 파일 | 변경 내용 | 태그 필요 여부 |
|---|------|----------|-------------|

### 외부 패키지
| # | 패키지 | 파일 | 상태 |
|---|--------|------|------|
| 1 | lodash | src/... | [NEW_DEPENDENCY] |

### 종합
- **위반 사항**: N개 (ERROR: A, WARN: B)
- **상태**: CLEAN / VIOLATIONS FOUND
```
