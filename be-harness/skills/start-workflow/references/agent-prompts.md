> 이 문서는 `start-workflow` 스킬의 Phase 6.2(구현), 7(빌드 체크), 9(문서 동기화), 10(PR), 11(성찰)에서 로드된다.
> "공통 규약: 에이전트 사망 처리"는 전 Phase 공통이다 — 사망 발생 시 미로드 상태면 이 문서를 Read한다. 단독 실행 금지.
> Phase 6.1(Red)의 프롬프트는 `references/tdd.md`, Phase 8(품질 루프)의 프롬프트는 `references/quality-loop.md`에 있다.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.
> 각 프롬프트의 "남은 Phase" 목록은 예시다 — 실제 값은 상태 파일 `Remaining Phases` 기준으로 치환한다 (예: `--reflect` 미지정 시 Phase 11 제외).

# 서브 에이전트 프롬프트 모음

## 공통 규약: 에이전트 사망 처리

> 모든 Phase의 Claude 서브 에이전트에 적용한다. **Codex 호출 실패는 대상이 아니다** — SKILL.md Phase 4.3의 `CODEX-UNAVAILABLE` 처리(특화 하네스는 해당 오버레이 규약)를 따른다.

**감지**: Agent tool이 오류를 반환하거나, 결과에 해당 프롬프트가 요구한 완료 보고 형식이 없는 경우.

**재시도 — Phase당 최대 2회**:

| 순서 | 행동 |
|------|------|
| 1차 | 동일 model/effort로 재실행 (일시 오류 대응 — API 529, 타임아웃 등) |
| 2차 | model 1단계 강등(opus→sonnet, sonnet→haiku; **haiku는 바닥이므로 강등 없이 동일 조건 재시도**) + 프롬프트에 "간결 모드: 산출물 형식은 유지하고 핵심만 수행" 추가. 강등은 사망 복구 전용 예외로, 이때만 Model/Effort 등급표·검증 판정 강등 금지 규칙보다 우선한다 (강등된 검증 판정은 "축소 실행 내역"에 재실행 권장과 함께 고지) |

| 종료 조건 | 결과 |
|----------|------|
| 재시도 성공 | Phase 정상 진행. `Phase Results`에 `agent_retry({원인})` 기록 |
| 2회 실패 — 격리 필수 단계(Phase 8.8) | `SKIPPED:AGENT_DIED` 기록 후 계속. **오케스트레이터 직접 대체 금지** — Spec을 아는 쪽이 읽으면 격리가 무너져 무의미하다 |
| 2회 실패 — 읽기 전용 스캔·문서·PR·성찰 류 | 오케스트레이터가 축소 절차로 직접 수행 → Phase `DONE`, `Phase Results`에 `degraded_fallback({원인} / {축소 내용})` 기록 |
| 2회 실패 — 구현·수정류 (Phase 6.1, 6.2, 7 build-fix, 8.5) | `BLOCKED:AGENT_DIED` — 에러 요약 보고 후 중단 (Phase 7 `BLOCKED:BUILD_FAIL`과 동일 취급) |

**축소 절차 기준**: 원 프롬프트의 산출물 형식은 유지하되, 범위를 이번 브랜치 변경 파일로 한정해 오케스트레이터가 직접 수행한다.

**검증 최후 보존**: 세션/토큰 한계로 인한 사망이 한 워크플로우에서 2회 누적되면, 이후 남은 Phase에서
검증·리뷰 위임(Phase 8.4 scope, 8.8 Read-back)은 **위임을 유지**하고(독립성·격리가 검출력의 근거),
비검증 위임 Phase(9 문서 동기화 등)는 직접 축소 수행 대신 `SKIPPED:BUDGET_PRESERVED`를 우선 선택해 검증 예산을 보존한다
(이 상태가 아니면 위 종료 조건 표대로 직접 축소 수행이 기본).

**고지**: `agent_retry`·`degraded_fallback`·`SKIPPED:BUDGET_PRESERVED`·`SKIPPED:AGENT_DIED`가 1건이라도 있으면
Phase 12 보고서의 "축소 실행 내역" 섹션에 Phase·Status·진단·원인·축소 내용·재실행 권장을 기록한다 (템플릿: `references/templates.md`).

`agent_retry`·`degraded_fallback`은 상태 코드가 아니라 **진단 분류(데이터)**다 — `Phase Results` 표와 보고서 "축소 실행 내역" 표의 셀 안에서만 쓴다.

## Phase 6.2: 구현 (Green)

### Implementation Notes 공통 추가 블록

**파일을 수정하는 모든 자율 실행 에이전트 프롬프트에 아래 블록을 추가한다.** 읽기 전용 스캔 에이전트에는 넣지 않는다 (이슈 보고서로 대신 전달되고, 통합 수정 단계가 기록한다).

```
    [Implementation Notes 규칙]
    설계 결정·편차·트레이드오프·미결 질문이 발생하면 **코드 수정 전에**
    `{IMPL_NOTES}`의 해당 섹션(`## 설계 결정` / `## 편차` / `## 트레이드오프` / `## 미결 질문`)에
    한 줄을 append 하세요.
    기존 줄 수정 금지(append-only), 마크다운만 작성(HTML/JSON 금지).
    [Assumption] 항목은 `## 편차` 섹션에도 동시 기록하세요.
```


### TDD 활성 시 공통 추가 블록

TDD가 활성이면(`$TDD = true` 이고 Phase 6.1이 `SKIPPED:*`가 아니면) 아래 블록을 **모든 구현 프롬프트에 추가**한다:

```
    ## TDD 규칙 (Phase 6.1에서 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 테스트를 고쳐서 통과시키는 것은 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고
      `[TestConflict]` 태그로 보고하세요. 판정은 오케스트레이터가 합니다.
    - Phase 6.1이 만든 스텁을 실제 구현으로 채우세요.
    - 통과 기준: 상태 파일 `## TDD Test Map`의 모든 테스트 통과
      AND `## Test Baseline` 대비 신규 실패 0건
```

`[TestConflict]` 판정 절차는 `references/tdd.md`의 "Phase 6.2" 섹션을 따른다.

### sequential 모드 (기본)

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 6.2
    남은 Phase: Phase 7, 8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경(예: 필터 추가, 정렬 변경 등)을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    {TDD 활성 시: 위 "TDD 규칙" 블록을 여기에 삽입}

    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption]·[TestConflict] 목록을 보고하세요.
```

완료 후 유저에게 간략 보고: "Phase 6.2 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

### parallel-slices 모드

상태 파일의 Slices에 정의된 2~3개 슬라이스를 **동시에 병렬 구현**한다.
같은 브랜치에서 파일 소유권을 분리하여 충돌을 방지한다.

**중요**: 병렬 에이전트는 **커밋하지 않는다**. 구현만 수행하고, 커밋은 모든 에이전트 완료 후 오케스트레이터가 일괄 처리한다.

> `workflow-implementer`는 커밋/빌드가 내장되어 있어 커밋 유보 지시와 충돌한다.
> 병렬 모드에서는 `general-purpose` 에이전트를 사용한다.

슬라이스 수만큼 Agent를 **하나의 메시지에서 동시에** 호출한다:

```
# 모든 슬라이스를 동일 메시지에서 병렬 호출
Agent tool:  (× 슬라이스 수)
  subagent_type: general-purpose
  model: [슬라이스 난이도 기준 선택]
  effort: [슬라이스 난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고, 아래 슬라이스만 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 6.2 parallel-slices
    남은 Phase: Phase 7, 8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}

    ## 담당 슬라이스
    제목: {Slice N 제목}
    파일 범위: {Slice N 파일 목록}
    설명: {Slice N 설명}

    ## 제한사항 (CRITICAL)
    - **위 파일 범위에 해당하는 파일만 수정하세요.** 범위 밖 파일은 절대 수정하지 않습니다.
    - **git commit을 하지 마세요.** 코드 구현만 수행합니다. 커밋은 오케스트레이터가 처리합니다.
    - **빌드 명령을 실행하지 마세요.** 빌드 검증은 오케스트레이터가 처리합니다.

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    구현 완료 후 변경 파일 목록, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

모든 슬라이스 에이전트 완료 후, 오케스트레이터가 일괄 커밋:

```bash
git add [전체 변경 파일]
git commit -m "Add: [작업 요약] (병렬 슬라이스 구현)"
```

(profile의 `{commitCoAuthor}`가 비어있지 않으면 `Co-Authored-By` 라인을 본문에 추가한다)

완료 후 유저에게 간략 보고: "Phase 6.2 완료: [N]개 슬라이스 병렬 구현, [변경 파일 수]개 파일"

## Phase 7: 빌드 실패 수정 에이전트

빌드 실패 시에만 호출한다 (성공 시 에이전트 불필요).

```
Agent tool:
  subagent_type: general-purpose
  model: [빌드 실패 심각도 기준 선택]
  effort: [빌드 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 `{buildCommand}` 빌드 에러를 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 7 상태를 갱신하세요.
    남은 Phase: Phase 8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}
    에러 메시지: {빌드 에러 출력}
    수정 후 빌드가 성공하는지 확인하세요.
```

수정 후 커밋:

```bash
git add [수정 파일들]
git commit -m "Fix: 빌드 에러 수정 (Phase 7)"
```

## Phase 9: API 문서 동기화

```
Agent tool:
  subagent_type: general-purpose
  model: [문서 변경 범위 기준 선택]
  effort: [문서 변경 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 API 문서({apiDocsPath})를 동기화하세요.
    작업 유형: {Task Type}
    프로젝트 루트: {현재 작업 디렉토리}
    API 문서 파일: {apiDocsPath}
    현재 Phase: Phase 9
    남은 Phase: Phase 10, 11, 12
    배정 model/effort: {model}/{effort}

    [규칙]
    - 문서 포맷(OpenAPI/Swagger/Postman 등)을 파일 확장자/내용으로 자동 판정.
    - 새로 추가/변경된 엔드포인트·필드만 반영. 무관한 영역은 건드리지 않음.
    - 문서 생성/푸시 도구(외부 서비스)는 사용하지 않는다. 파일 편집으로 끝낸다.
    - 변경 후 `git diff {apiDocsPath}` 결과를 요약해 보고.
```

외부 API 문서 플랫폼(Apidog, Postman 등) 동기화가 필요하면 **프로젝트 쪽에 별도 스크립트/훅을 두고** 이 Phase 이후에 수동 실행한다. be-harness는 파일 기반 동기화만 보장한다.

## Phase 10: PR 생성 (workflow-pr)

```
Agent tool:
  subagent_type: be-harness:workflow-pr
  model: [PR 복잡도 기준 선택]
  effort: [PR 복잡도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 PR을 생성하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 10
    남은 Phase: Phase 11, 12
    배정 model/effort: {model}/{effort}
    PR URL을 반드시 보고하세요.
    Assumption Gate에 걸리면 push/PR 없이 BLOCKED:ASSUMPTION_UNRESOLVED와 태그 목록을 보고하세요.
```

## Phase 11: 성찰 (workflow-reflection)

`$REFLECT = true`일 때만 호출한다 (기본은 `SKIPPED:REFLECT_NOT_REQUESTED` — SKILL.md Phase 11).

```
Agent tool:
  subagent_type: be-harness:workflow-reflection
  model: [워크플로우 변경량 기준 선택]
  effort: [워크플로우 변경량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 11
    남은 Phase: Phase 12
    배정 model/effort: {model}/{effort}
    성찰 결과와 스킬 보완점을 보고하세요.
```
