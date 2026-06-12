> 이 문서는 `start-workflow` 스킬의 Phase 6(구현), 7(빌드 체크), 9(문서 동기화), 10(PR), 11(성찰)에서 로드된다. 단독 실행 금지.
> Phase 8(품질 루프)의 프롬프트는 `references/quality-loop.md`에 있다.
> `{STATE_FILE}`, `{buildCommand}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 서브 에이전트 프롬프트 모음

## Phase 6: 구현

### sequential 모드 (기본)

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [난이도 기준 선택]
  effort: [난이도 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    현재 Phase: Phase 6
    남은 Phase: Phase 7, 8, 9, 10, 11, 12
    배정 model/effort: {model}/{effort}

    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경(예: 필터 추가, 정렬 변경 등)을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.

    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

완료 후 유저에게 간략 보고: "Phase 6 완료: [변경 파일 수]개 파일, [커밋 수]개 커밋"

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
    현재 Phase: Phase 6 parallel-slices
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

완료 후 유저에게 간략 보고: "Phase 6 완료: [N]개 슬라이스 병렬 구현, [변경 파일 수]개 파일"

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
```

## Phase 11: 성찰 (workflow-reflection)

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
