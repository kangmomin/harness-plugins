> 이 문서는 `start-workflow-mm` 스킬의 Phase 7.2(구현), 8(빌드 체크), 11(문서 동기화), 12(PR), 13(성찰)에서 로드된다. 단독 실행 금지.
> Phase 9(품질 루프)·10(Codex 품질 리뷰)의 프롬프트는 `references/quality-loop.md`에 있다.
> `{STATE_FILE}`, `{IMPL_NOTES}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 서브 에이전트 프롬프트 모음

## Phase 7.2: 구현 (Green)

### TDD 활성 시 공통 추가 블록

`$TDD = true` 이고 Phase 7.1이 `SKIPPED:*`가 아니면 아래 블록을 **모든 구현 프롬프트에 추가**한다:

```
    ## TDD 규칙 (Phase 7.1에서 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 테스트를 고쳐서 통과시키는 것은 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고
      `[TestConflict]` 태그로 보고하세요. 판정은 오케스트레이터가 합니다.
    - Phase 7.1이 만든 스텁을 실제 구현으로 채우세요.
    - 통과 기준: 상태 파일 `## TDD Test Map`의 모든 테스트 통과
      AND `## Test Baseline` 대비 신규 실패 0건
```

`[TestConflict]` 판정 절차는 `references/tdd.md`의 "Phase 7.2" 섹션을 따른다.

### sequential 모드 (기본)

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 7.2
    남은 Phase: Phase 8, 9, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경(예: 필터 추가, 정렬 변경 등)을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    [Implementation Notes 규칙]
    설계 결정·편차·트레이드오프·미결 질문이 발생하면 **코드 수정 전에**
    `{IMPL_NOTES}`의 해당 섹션(`## 설계 결정` / `## 편차` / `## 트레이드오프` / `## 미결 질문`)에 한 줄을 append 하세요.
    기존 줄 수정 금지(append-only), 마크다운만 작성(HTML 금지). [Assumption] 항목은 `## 편차` 섹션에도 동시 기록하세요.

    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

완료 후 유저에게 간략 보고: "Phase 7.2 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

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
    현재 Phase: Phase 7.2 parallel-slices
    남은 Phase: Phase 8, 9, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}

    ## 담당 슬라이스
    제목: {Slice N 제목}
    파일 범위: {Slice N 파일 목록}
    설명: {Slice N 설명}

    ## 제한사항 (CRITICAL)
    - **위 파일 범위에 해당하는 파일만 수정하세요.** 범위 밖 파일은 절대 수정하지 않습니다.
    - **git commit을 하지 마세요.** 코드 구현만 수행합니다. 커밋은 오케스트레이터가 처리합니다.
    - **go build를 실행하지 마세요.** 빌드 검증은 오케스트레이터가 처리합니다.

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    [Implementation Notes 규칙]
    설계 결정·편차·트레이드오프·미결 질문이 발생하면 **코드 수정 전에**
    `{IMPL_NOTES}`의 해당 섹션에 한 줄을 append 하세요.
    여러 슬라이스 에이전트가 같은 파일을 동시에 append 할 수 있으므로, 각 줄 앞에 담당 슬라이스 이름을 prefix로 붙이세요(예: `- [Slice 1] Phase 7 | ...`).
    기존 줄 수정 금지(append-only), 마크다운만 작성.

    구현 완료 후 변경 파일 목록, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

모든 슬라이스 에이전트 완료 후, 오케스트레이터가 일괄 커밋:

```bash
git add [전체 변경 파일]
git commit -m "$(cat <<'EOF'
Add: [작업 요약] (병렬 슬라이스 구현)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

완료 후 유저에게 간략 보고: "Phase 7.2 완료: [N]개 슬라이스 병렬 구현, [변경 파일 수]개 파일"

## Phase 8: 빌드 실패 수정 에이전트

빌드 실패 시에만 호출한다.

```
Agent tool:
  subagent_type: general-purpose
  model: [빌드 실패 심각도 기준 선택]
  effort: [빌드 실패 심각도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}에서 `go build ./cmd/main.go` 빌드 에러를 수정하세요.
    상태 파일 `{STATE_FILE}`을 읽고 Phase 8 상태를 갱신하세요.
    남은 Phase: Phase 9, 10, 11, 12, 13, 14
    배정 model/effort: {model}/{effort}
    에러 메시지: {빌드 에러 출력}
    수정 후 빌드가 성공하는지 확인하세요.

    [Implementation Notes 규칙]
    빌드 실패 원인이 Spec/Plan과 어긋난 결정이거나 향후 영향 있는 트레이드오프라면
    `{IMPL_NOTES}`의 해당 섹션에 한 줄 append 하세요(append-only, 마크다운).
```

수정 후 커밋: `git add [수정 파일들] && git commit -m "Fix: 빌드 에러 수정 (Phase 8)"`

## Phase 11: 문서 동기화 (workflow-doc-sync)

```
Agent tool:
  subagent_type: minmos-harness:workflow-doc-sync
  model: [문서/계약 변경 범위 기준 선택]
  effort: [문서/계약 변경 범위 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 API 문서를 동기화하세요.
    작업 유형: {Task Type}
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 11
    남은 Phase: Phase 12, 13, 14
    배정 model/effort: {model}/{effort}

    [외부 도구 규칙]
    MCP tool 호출 전 capability(read/write)를 먼저 확인하세요.
    지원하지 않는 기능은 시도하지 말고 수동 가이드를 제공하세요.

    [Implementation Notes 규칙]
    OAS 스키마와 실제 코드 간 불일치, 응답 케이스 추가/삭제, 수동 안내로 전환한 항목 등이 있으면
    `{IMPL_NOTES}`의 해당 섹션에 한 줄 append 하세요(append-only, 마크다운).
    Apidog 업로드 실패·권한 부족으로 동기화를 보류한 항목은 `## 미결 질문`에 기록하세요.
```

## Phase 12: PR 생성 (workflow-pr)

```
Agent tool:
  subagent_type: be-harness:workflow-pr
  model: [PR 복잡도 기준 선택]
  effort: [PR 복잡도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 PR을 생성하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 12
    남은 Phase: Phase 13, 14
    배정 model/effort: {model}/{effort}
    PR URL을 반드시 보고하세요.

    [Implementation Notes 규칙]
    `{IMPL_NOTES}`를 읽어 `## 미결 질문` 항목이 있으면
    PR description 본문 끝에 "리뷰어 확인 필요" 블록으로 그대로 옮겨 넣으세요.
    그 외 섹션은 PR 본문에 자동 포함하지 않습니다(Phase 14 HTML 산출물로 별도 표면화).
```

## Phase 13: 성찰 (workflow-reflection)

```
Agent tool:
  subagent_type: be-harness:workflow-reflection
  model: [워크플로우 변경량 기준 선택]
  effort: [워크플로우 변경량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 13
    남은 Phase: Phase 14
    배정 model/effort: {model}/{effort}
    성찰 결과와 스킬 보완점을 보고하세요.

    [Implementation Notes 규칙]
    `{IMPL_NOTES}`를 함께 읽어 라이브 노트가 누락한 판단(설계 결정·트레이드오프)이 있으면
    해당 섹션에 append 하세요. 워크플로우 자체에 대한 보완 아이디어(스킬 개선)는 노트에 쓰지 말고
    Phase 14 보고서 "보완점" 표에 기록하세요.
```
