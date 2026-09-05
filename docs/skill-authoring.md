# 스킬 작성 표준 (Skill Authoring Convention)

이 저장소의 모든 플러그인 스킬(`{plugin}/skills/{name}/SKILL.md`)과 에이전트(`{plugin}/agents/{name}.md`)가 따르는 작성 표준이다.
스킬을 새로 만들거나 수정할 때 이 문서를 기준으로 작성하고, 리뷰 시 이 문서를 체크리스트로 사용한다.

## 1. Frontmatter

```yaml
---
name: {스킬 디렉토리명과 정확히 일치}
description: "{한 문장 기능 요약}. {트리거 조건 — 사용자가 언제/어떤 표현으로 요청할 때 사용하는지}."
user-invocable: true
allowed-tools: {사용하는 도구 목록 — 선택}
argument-hint: {인자를 받는 스킬만 — 선택}
---
```

- `description`은 **기능 요약 + 사용 시점(when-to-use)** 2요소가 모두 있어야 한다.
- 트리거 키워드에는 사용자가 실제로 입력할 표현(한국어 구문 포함)을 넣는다.
  - 나쁨: `"프로젝트 컨벤션 위배 사항을 검사하고 보고"`
  - 좋음: `"프로젝트 컨벤션 위배 사항을 검사하고 보고한다. 커밋/PR 전 점검, '컨벤션 검사해줘', '규칙 위반 확인' 요청 시 사용."`

## 2. 본문 섹션 순서

```
1. Project Overrides (3행 축약형 — §4)
2. # 제목 + 목적 1~2문장
3. ## Flags            (플래그가 있는 스킬만, 표 형식)
4. ## 전제 조건         (필요 도구/설정/MCP + 미충족 시 행동)
5. ## Step/Phase 본문
6. ## 출력 형식         (코드펜스 템플릿)
7. ## 상태 코드         (해당 스킬이 쓰는 코드의 부분집합 표 — §5)
8. ## References       (분리 파일이 있는 스킬만 — §8)
```

해당 없는 섹션은 생략한다. 순서는 바꾸지 않는다.

## 3. 용어 규칙: Step과 Phase

| 용어 | 용도 | 번호 규칙 |
|------|------|----------|
| **Phase** | 오케스트레이터 계열(start-workflow*, *-loop)의 최상위 단계 | `Phase N`, 하위는 `Phase N.M` (한 단계 깊이까지) |
| **Step** | 단일 스킬의 절차 | `Step 1, 2, 3…` 연속 정수, 하위는 `Step N.M` |

- 비정규 번호(`Step 4.5`, `Step 3-1`, `Step 0`) 금지. 절차가 추가되면 재번호한다.
- 한 스킬 안에서 Step과 Phase를 혼용하지 않는다.

## 4. Project Overrides 축약형

오버라이드를 지원하는 플러그인(common/be/fe)의 모든 스킬·에이전트 머리말은 아래 3행 표준형을 사용한다:

```markdown
> **Project Overrides**: 실행 전 `.claude/{plugin}/common.md`와 `.claude/{plugin}/skills/{skill}.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
```

- 경로 문자열은 **글자 단위로 동결**한다 (사용자 프로젝트 호환성).
- 병합 규칙·레이어 구조 등 상세 설명의 canonical은 각 플러그인의 `OVERRIDES.md`다. 스킬 본문에 중복 서술하지 않는다.
- 에이전트는 `skills/{skill}.md` 대신 `agents/{agent}.md` 경로를 쓴다.

## 5. 상태 코드 표준 세트

| 코드 | 의미 |
|------|------|
| `DONE` | 단계 정상 완료 |
| `IN_PROGRESS` | 진행 중 |
| `PENDING` | 미시작 |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 — 사유 필수 (예: `SKIPPED:POSTGRES_MCP_UNAVAILABLE`) |
| `BLOCKED:{사유}` | 진행 불가, 사용자 개입 필요 — 루프 상한 도달, 전제 미충족 등 |
| `FAIL` | 수행했으나 실패 |

리뷰/검증 스킬의 **판정**은 `PASS / WARN / FAIL` 3단계를 쓰고, 반드시 수치 기준을 동반한다
(모범: `be-harness/agents/code-verifier.md` — "PASS = Critical/High 0건, WARN = Critical 0건 + High 1~2건, FAIL = Critical 1건+ 또는 High 3건+").

위 세트 밖의 상태 코드를 새로 만들지 않는다. 스킬 본문의 `## 상태 코드` 섹션에는 그 스킬이 실제로 쓰는 부분집합만 표로 적는다.

### 어휘 3필드 분리

상태 코드·판정·진단 분류는 **서로 다른 필드**다. 한 열에 섞어 적지 않는다.

| 필드 | 허용 값 | 등장 위치 |
|------|--------|----------|
| **상태 코드** | 위 표준 세트 | Phase/Step의 진행 상태 열, `Current Phase` |
| **판정** | `PASS` / `WARN` / `FAIL` (수치 기준 동반) | 리뷰·검증 스킬의 최종 판정 |
| **진단 분류 (데이터)** | 스킬이 정의하는 snake_case 값 | 그 스킬의 결과 표 **셀 안에서만** |

**진단 분류**는 상태 코드가 아니라 데이터다. 검증 결과를 분류해 표에 담을 때 쓰며, 반드시 소문자 snake_case로 표기해 상태 코드(대문자)와 시각적으로 구분한다.
정의한 스킬의 결과 표 밖으로 나가서는 안 되며, **Phase 진행 상태 열에 등장하면 규약 위반이다.**

기존 예: `start-workflow`의 TDD 진단 분류(`red_assertion`, `already_satisfied`, `cannot_compile`, `deferred_e2e`, `regression`, `pre_existing`, `new_red`, `flaky`) — `TDD Test Map`과 회귀 대조 표에만 등장한다.

> `e2e-test`의 `UNCOVERED:{사유}`처럼 대문자 접두형으로 먼저 자리 잡은 커버리지 표기는 하위 호환을 위해 유지한다. **신규 도입은 snake_case 진단 분류를 쓴다.**

## 6. 루프 작성 규칙 (3요소 필수)

모든 반복 절차는 아래 3요소를 반드시 명시한다:

1. **최대 반복 횟수** — 상한 없는 루프 금지.
2. **종료조건 표** — `조건 → 결과 상태` 형식.
3. **상한 도달 시 행동** — `BLOCKED:{사유}` 보고 + **번호 매긴 사용자 선택지** (각 선택지의 후속 단계 포함).

예 (모범: `be-harness/skills/e2e-test-loop/SKILL.md`):

```markdown
| 종료 조건 | 결과 |
|----------|------|
| 모든 시나리오 통과 | DONE |
| 5회 반복 후에도 실패 잔존 | BLOCKED:MAX_ITERATIONS — 사용자 선택지 제시 |
| 같은 파일을 두 번 연속 같은 방향으로 수정 | BLOCKED:NO_PROGRESS — 즉시 중단, 미해결 보고 |
```

## 7. 에러 / Fallback 규칙

- **"사용자에게 묻는다"는 항상 번호 매긴 선택지 + 각 선택의 후속 단계를 동반한다.** "위 어느 것도 없으면 사용자에게 묻는다"식 개방형 종결 금지.
- **Graceful degradation은 3요소로 명시한다**: ① 감지 방법(어떤 호출/검사가 실패하면) → ② 폴백 절차 → ③ 사용자 고지 문구.
- **하드코딩 값은 스킬 상단 한 곳에 정의**하고 본문은 플레이스홀더로 참조한다:
  ```markdown
  - `{STATE_FILE}` = `{RUN_DIR}/workflow-state.md`
  ```
  본문에서는 `{STATE_FILE}`만 사용한다. 값 변경이 한 줄 수정으로 끝나야 한다.
- **MCP 도구명은 패턴 탐색으로 일반화한다**: 도구명에 프로젝트별 접미사가 붙는 경우(예: Apidog)
  `mcp__apidog__read_project_oas_*` 패턴으로 세션 도구 목록에서 탐색하고, 기본값을 병기한다. 미발견 시 graceful degradation.

## 8. Progressive Disclosure (references 분리)

- SKILL.md 본문은 **목표 ~400줄 / 절대 상한 500줄**. 초과분은 같은 스킬 폴더의 `references/*.md`로 분리한다.
- **본문에 남기는 것**: 항상 실행되는 제어 흐름 — Phase/Step 순서, 판정 기준, 루프 상한, 상태 코드, 플레이스홀더 정의.
- **references로 보내는 것**: 특정 분기에서만 필요한 것 — 모드별 상세 절차, 출력 템플릿 원문, 서브에이전트 프롬프트 전문, 도메인 패턴 모음.
- 참조 지시문은 **강제형 + 읽기 트리거 명시**:
  ```markdown
  > Phase 4 진입 시 MUST: 같은 폴더의 `references/agent-prompts.md`를 Read하고 해당 Phase 섹션의 프롬프트를 사용한다.
  ```
  "필요하면 참조" 같은 약한 표현 금지.
- 각 reference 파일 머리말에 소속을 명시한다:
  ```markdown
  > 이 문서는 `start-workflow` 스킬의 Phase 4~8에서 로드된다. 단독 실행 금지.
  ```
- 플레이스홀더(`{STATE_FILE}` 등) 정의는 **본문 단일 위치**에만 둔다. reference에서는 사용만 한다.
- 기존 검증된 패턴: `minmos-harness/skills/apidog-schema-gen/references/extraction-patterns.md`
  (스킬 폴더 내부 + SKILL.md 기준 상대 경로 — 실배포에서 동작 확인됨). 신규 분리는 전부 이 구조를 따른다.

## 9. 스킬 간 참조 규칙

- **cross-plugin 참조는 스킬 이름 호출만 허용**: `/common:commit` 처럼 Skill tool 이름으로 호출한다.
  다른 플러그인의 파일 경로 참조 금지 (플러그인은 개별 설치되므로 경로가 보장되지 않는다).
- common 스킬에 의존하는 플러그인은 전제 조건 섹션에 "common 플러그인 선행 설치"를 명시한다.
- 같은 플러그인 안에서도 다른 스킬의 절차를 재사용할 때는 파일 경로가 아닌 스킬 이름으로 위임한다
  (예: commit-pr → "`/common:commit-push` 절차를 수행한 뒤 PR을 생성한다").
- 절차를 위임받는 canonical 스킬을 하나 정하고, 나머지는 차이점만 기술한다. 복붙 금지.

### 특화 하네스의 오버레이

특화 하네스(`minmos-harness`, `hyeondongs-harness`)는 베이스 하네스(`be-harness`, `fe-harness`)의 절차를 복제하지 않고 **델타만** 얹는다.

- 오버레이 문서는 `{plugin}/overlay/{skill}.md`에 두고, 위치 지정은 **절대 Phase 번호가 아니라 앵커**로 한다.
- 위임 스킬은 절차를 갖지 않는다 (목표 50줄 이내).
- 오버레이가 베이스보다 나은 **범용** 절차를 갖게 되면 베이스로 승격한다.

상세 규약의 canonical은 `docs/overlay.md`다. 이 문서에 중복 서술하지 않는다.

## 10. 기타

- 모든 스킬 출력은 한국어. 본문도 한국어로 작성한다 (코드/식별자/상태 코드는 원형 유지).
- UTF-8 인코딩을 보장한다 (U+FFFD 대체 문자 등 깨진 문자 발견 시 즉시 정정).
- 출력 형식이 있는 스킬은 `## 출력 형식`에 코드펜스 템플릿을 제공한다. "사용자 친화적으로 안내한다"처럼 형식 없는 지시 금지.
- 후속 스킬이 파싱하는 보고서(Workflow Report, E2E 테스트 결과 등)의 **섹션 머리글은 변경하지 않는다**.

- 실행 경로는 `workflow_run.py`로 생성·검증한 `{RUN_DIR}` 아래에 둔다. 재개는 명시 경로·저장소·모드·RUN_ID 검증을 거치며, 고정 전역 상태 경로를 추가하지 않는다.
