> 이 문서는 `start-workflow` 스킬의 Analyze 모드(`--analyze`)와 Verify 모드(`--verify`)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> `codexMode: max`면 A3 `code-analyzer` · V3 `code-verifier`는 Codex `judge` 슬롯(읽기 전용 판정)으로, V4 러너에는 §8 포인터를 추가한다 (`references/codex-mode.md` 매핑). 상태 파일에는 `## Codex` 절(`CODEX: {mode}` / `CODEX_MODELS: …`(난이도 없음 → `review` = `xhigh`) / `상태: active|fallback(...)`)을 둔다.

# Analyze / Verify Mode 상세 절차

## Analyze Mode (`--analyze`)

코드를 분석하여 아키텍처·품질·의존성·패턴·기술 부채를 보고한다. **코드 수정은 하지 않는다.**

### Phase A1: 범위 및 초점 수집

1. **범위 확인**: `$ARGUMENTS`에서 플래그 뒤 경로가 지정되었으면 해당 범위를 사용. 없으면 유저에게 확인한다.
   > "분석 범위를 지정해주세요. (전체 / 디렉토리 경로 / 파일 경로)"
2. **초점 선택**: 유저에게 분석 초점을 묻는다 (복수 선택 가능).
   > "분석 초점을 선택해주세요:
   > 1. 아키텍처 (레이어 구조, 모듈 결합도, 인터페이스)
   > 2. 코드 품질 (복잡도, 중복, Dead Code, 코드 스멜)
   > 3. 의존성 (외부 패키지, 내부 의존 그래프, 순환 의존)
   > 4. 패턴 & 기술 부채 (안티패턴, TODO/FIXME, 일관성)
   > 5. 전체 (기본값)
   >
   > 예: `5` (전체) 또는 `1,2` (아키텍처 + 품질)"
3. **추가 컨텍스트**: `$ARGUMENTS`나 대화에 특정 관심사가 포함되어 있으면 함께 전달한다.

### Phase A2: 상태 파일 생성

Write tool로 `{STATE_FILE}`을 생성한다:

```markdown
# Workflow State — Analyze Mode

## Mode
analyze

## Scope
{범위}

## Focus
{선택된 초점 목록}

## Context
{추가 컨텍스트 또는 "없음"}
```

출력: **"코드 분석을 시작합니다."**

### Phase A3: 코드 분석

```
Agent tool:
  subagent_type: be-harness:code-analyzer
  model: [분석 범위 기준 선택]
  effort: [분석 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 코드 분석을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase A3
    남은 Phase: Phase A4
    배정 model/effort: {model}/{effort}

    분석 범위: {scope}
    분석 초점: {focus}
    추가 컨텍스트: {context}

    분석 완료 후 출력 형식에 따라 보고서를 작성하세요.
```

### Phase A4: 분석 보고서

code-analyzer 에이전트의 결과를 종합하여 유저에게 보고한다.

```markdown
## Code Analysis Report

### 분석 개요
- **모드**: Analyze
- **범위**: {scope}
- **초점**: {focus}

{code-analyzer 보고서 전문}

### 추가 조치
```

> "발견된 이슈를 수정할까요?
> 1. 전체 — general-purpose 에이전트로 즉시 수정 가능한 모든 이슈 수정
> 2. 선택 — 번호로 선택한 항목만 수정
> 3. 건너뛰기 — 보고서만 출력하고 종료"

수정 후 커밋 여부를 유저에게 확인한다.

정리: 상태 파일의 `Remaining Phases`를 `없음`으로 갱신하고 기본은 보관한다. 사용자가 정리를 요청한 경우에만 `rm -f {STATE_FILE}`로 삭제한다.

---

## Verify Mode (`--verify`)

코드를 검증하여 보안·성능·잠재 버그·안정성 관점에서 **PASS/WARN/FAIL 판정**을 내린다.

### Phase V1: 범위 및 초점 수집

1. **범위 확인**: `$ARGUMENTS`에서 플래그 뒤 경로가 지정되었으면 해당 범위를 사용. 없으면 유저에게 확인한다.
   > "검증 범위를 지정해주세요. (전체 / 디렉토리 경로 / 파일 경로)"
2. **초점 선택**: 유저에게 검증 초점을 묻는다 (복수 선택 가능).
   > "검증 초점을 선택해주세요:
   > 1. 보안 (SQL Injection, XSS, 인증/인가, 데이터 노출)
   > 2. 성능 (N+1 쿼리, 메모리 누수, 리소스 관리)
   > 3. 잠재 버그 (Nil 역참조, 동시성, 에러 처리, 로직 결함)
   > 4. 안정성 (리소스 관리, 장애 복원력, 테스트 커버리지)
   > 5. 전체 (기본값)
   >
   > 예: `5` (전체) 또는 `1,3` (보안 + 잠재 버그)"

### Phase V2: 상태 파일 생성 + 정적 분석

Write tool로 `{STATE_FILE}`을 생성한다:

```markdown
# Workflow State — Verify Mode

## Mode
verify

## Scope
{범위}

## Focus
{선택된 초점 목록}
```

profile 값을 사용해 정적 분석을 순차 실행한다 (비어있는 명령은 SKIP):

```bash
{lintCommand}      # 비어있으면 SKIP
{buildCommand}     # 비어있으면 SKIP
{typeCheckCommand} # 비어있으면 SKIP
```

테스트 커버리지가 초점에 포함된 경우(`전체` 또는 `안정성`): `{testCommand}` 실행.

결과를 상태 파일에 append한다. SKIP된 명령은 `SKIPPED:PROFILE_EMPTY`로 기록.

출력: **"코드 검증을 시작합니다."**

### Phase V3: 코드 검증

```
Agent tool:
  subagent_type: be-harness:code-verifier
  model: [검증 범위/초점 기준 선택]
  effort: [검증 범위/초점 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 코드 검증을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase V3
    남은 Phase: Phase V4, V5
    배정 model/effort: {model}/{effort}

    검증 범위: {scope}
    검증 초점: {focus}
    정적 분석 결과:
    [lint 결과]
    [build 결과]
    [typecheck 결과]
    [test/coverage 결과 (실행한 경우)]

    검증 완료 후 출력 형식에 따라 보고서를 작성하세요.
```

### Phase V4: 컨벤션 검사 (조건부)

검증 초점에 `전체`가 포함되어 있을 때만 실행한다. 아니면 `SKIPPED:FOCUS_NOT_FULL`.

```
Agent tool:
  subagent_type: general-purpose
  model: [컨벤션 검사 범위 기준 선택]
  effort: [컨벤션 검사 범위 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 /be-harness:convention-check 를 실행하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase V4 상태를 갱신하세요.
    배정 model/effort: {model}/{effort}
    결과를 "위반: N건" 형식으로 보고하세요.
```

### Phase V5: 종합 검증 보고서

code-verifier 결과 + 정적 분석 결과 + 컨벤션 검사 결과를 종합하여 보고한다.

```markdown
## Code Verification Report

### 검증 개요
- **모드**: Verify
- **범위**: {scope}
- **초점**: {focus}

### 정적 분석 결과
| 도구 | 판정 | 비고 |
|------|------|------|
| lint | PASS/FAIL/SKIPPED | {요약} |
| build | PASS/FAIL/SKIPPED | {요약} |
| typecheck | PASS/FAIL/SKIPPED | {요약} |
| test/coverage | PASS/FAIL/SKIPPED ({%}) | 실행한 경우만 |

### 코드 검증 결과
{code-verifier 보고서 전문}

### 컨벤션 검사 결과
{convention-check 결과 또는 "미실행"}

### 종합 판정
| 항목 | 판정 |
|------|------|
| 정적 분석 | PASS/FAIL |
| 보안 | PASS/WARN/FAIL |
| 성능 | PASS/WARN/FAIL |
| 잠재 버그 | PASS/WARN/FAIL |
| 안정성 | PASS/WARN/FAIL |
| 컨벤션 | PASS/WARN/FAIL (실행 시) |
| **종합** | **PASS/WARN/FAIL** |

### 즉시 수정 권고 (Critical + High)
{이슈 목록}
```

> "발견된 이슈를 수정할까요?
> 1. Critical+High 전체 — general-purpose 에이전트로 모두 수정
> 2. 선택 — 번호로 선택한 항목만 수정
> 3. 건너뛰기 — 보고서만 출력하고 종료"

수정 후 커밋 여부를 유저에게 확인한다.

정리: 상태 파일의 `Remaining Phases`를 `없음`으로 갱신하고 기본은 보관한다. 사용자가 정리를 요청한 경우에만 `rm -f {STATE_FILE}`로 삭제한다.
