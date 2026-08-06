> 이 문서는 `start-workflow`(fs-harness) 스킬의 Phase 6.1(Red)·6.2(병렬 구현)과 Phase 8.1(계약 격리 Read-back)에서 로드된다. 단독 실행 금지.
> Red 단계의 소유권·배리어 규칙은 `references/tdd.md`가 canonical이다.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# Red 에이전트 프롬프트 (Phase 6.1)

TDD 활성 시에만 실행한다. 두 에이전트를 **같은 메시지 내에서 병렬 호출**하고, 검증·기록·커밋은 오케스트레이터가 배리어에서 단독 수행한다.

```
Agent tool:  (× 2 — 백엔드 / 프론트엔드)
  subagent_type: general-purpose
  model: [계약 조항 수·도메인 복잡도 기준 선택]
  effort: [동일 기준]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고, **{Backend|Frontend} 담당 범위**의 계약 기반 테스트를 작성하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 6.1 (Red) — {Backend|Frontend}
    남은 Phase: Phase 6.2, 7, 8, 9, 10
    배정 model/effort: {model}/{effort}

    ## 근거 (이것만 사용)
    frozen Integration Contract의 `CT-nn` / Feature Matrix의 `F-nn`
    / 해당 도메인 Spec의 `EC-nn` (있을 때만)
    근거 밖의 테스트는 작성하지 마세요.

    ## 담당 범위
    - 백엔드: handler·usecase 단위 테스트 — 계약이 약속한 **응답**을 검증
    - 프론트엔드: 컴포넌트·훅 테스트 — 계약이 약속한 **소비**를 검증

    ## 금지 (CRITICAL)
    - 상대 도메인 파일을 수정하지 마세요.
    - **공용 계약 스키마 테스트를 수정하지 마세요.** 오케스트레이터 소유입니다.
    - 실제 구현을 작성하지 마세요. 컴파일을 위한 **빈 스텁**만 허용됩니다.
    - git commit 을 하지 마세요. 커밋은 오케스트레이터가 처리합니다.

    ## 보고
    { 근거 ID, 테스트명, 파일, 진단 분류 } 매핑 표를 반환하세요.
    이번 계약 변경이 담당 도메인의 관측 가능한 동작을 바꾸지 않으면
    `N/A(영향 없음)` 과 그 **근거를 파일 단위로** 제시하세요.
```

**배리어**: 두 에이전트가 모두 유효 Red 또는 근거 있는 `N/A`를 반환해야 Phase 6.2로 진행한다.
그 뒤 오케스트레이터가 공용 계약 테스트를 작성하고, 도메인별 TDD Test Map을 기록하고, 단일 Red 커밋을 만든다.

---

# 구현 에이전트 프롬프트 (Phase 6.2)

두 구현 에이전트를 **같은 메시지 내에서 병렬 호출**한다 (Agent tool × 2).

TDD 활성 시 아래 블록을 두 프롬프트에 **모두 추가**한다:

```
    ## TDD 규칙 (Phase 6.1에서 계약 기반 테스트가 선작성되었습니다)
    - **테스트 파일을 수정하지 마세요.** 공용 계약 테스트는 열어보되 수정 금지입니다.
    - 테스트가 잘못되었다고 판단되면 코드와 테스트 어느 쪽도 고치지 말고
      `[TestConflict]` 태그로 보고하세요. 계약 조항과 연결된 충돌이면
      오케스트레이터가 Phase 2(계약 정의)로 되돌립니다.
    - Phase 6.1이 만든 스텁을 실제 구현으로 채우세요.
    - 통과 기준: 담당 도메인 `## TDD Test Map` 전체 통과
      AND 해당 도메인 `## Test Baseline` 대비 신규 실패 0건
```

## 백엔드 구현 에이전트

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [백엔드 작업량 기준 선택]
  effort: [백엔드 작업량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고, **Backend Plan** 섹션만 구현하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 6.2 Backend
    남은 Phase: Phase 7, 8, 9, 10
    배정 model/effort: {model}/{effort}
    profile: .claude/be-harness.local.md 를 읽어 빌드/커밋 명령을 결정하세요.
    금지: Frontend Plan 파일 수정, 계약 외 필드 추가.
    보고: 변경 파일, 계약 차이점, [Assumption] 목록, 막힌 계약 항목.
```

## 프론트엔드 구현 에이전트

```
Agent tool:
  subagent_type: fe-harness:workflow-implementer
  model: [프론트엔드 작업량 기준 선택]
  effort: [프론트엔드 작업량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고, **Frontend Plan** 섹션만 구현하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 6.2 Frontend
    남은 Phase: Phase 7, 8, 9, 10
    배정 model/effort: {model}/{effort}
    profile: .claude/fe-harness.local.md 를 읽어 빌드/커밋 명령을 결정하세요.
    금지: Backend Plan 파일 수정, 계약 외 필드 가정.
    보고: 변경 파일, 계약 차이점, [Assumption] 목록, 막힌 계약 항목.
```

두 에이전트 모두 보고해야 할 것:

- 변경 파일 목록
- 계약 대비 차이점
- `[Assumption]` 목록
- 막힌 계약 항목

구현 중 계약 변경이 필요하면 즉시 Phase 2(통신 계약 정의)로 돌아간다.

---

# 계약 격리 Read-back 프롬프트 (Phase 8.1)

두 에이전트를 **같은 메시지 내에서 병렬 호출**한다 (Agent tool × 2). 서로의 결과도, frozen contract도 주지 않는다.

> **격리 규칙 (CRITICAL)**: 아래 세 조건을 모두 지킨다.
> ① `{STATE_FILE}` 경로를 전달하지 않고 읽지 말라고 명시 ② frozen contract·Plan·Feature Matrix를 프롬프트 본문에 넣지 않음 ③ "상태 파일을 읽고 갱신하세요" 문구를 넣지 않음(상태 갱신은 오케스트레이터가 수행) ④ **도메인별 `## TDD Test Map`을 전달하지 않음** (`CT-nn` ↔ 테스트 매핑이라 계약을 역추론하게 된다).
> 하나라도 빠지면 에이전트가 계약을 읽고 그대로 옮겨 적어 **Diff가 항상 0건**이 된다.

## 백엔드 계약 복원 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: [계약 복잡도 기준 선택]
  effort: [계약 복잡도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}의 백엔드 코드만 읽고, 이 서버가 **실제로 제공하는 API 계약**을 복원하세요.

    ## 읽을 범위
    이번 브랜치에서 변경된 handler / route / DTO / 에러 매핑 코드
    (`git diff --name-only main...HEAD` 로 확인)

    ## 규칙
    - 프론트엔드 코드는 읽지 마세요.
    - `/tmp/workflow-state.md` 를 비롯한 명세·계약·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 의도를 추측하지 말고, **라우팅 등록·DTO 태그·검증 분기·반환 status code가 실제로 보장하는 것**만 적으세요.
    - 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 엔드포인트
    | Method | Path | Request 필드 (타입, 필수) | Response 필드 (타입) | 에러 status·코드 | 인증 | 출처 |
    |--------|------|--------------------------|---------------------|-----------------|------|------|

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    완료 후 "복원: N개 엔드포인트, 해석 불가: M건" 형식으로 보고하세요.
```

## 프론트엔드 계약 복원 에이전트

```
Agent tool:
  subagent_type: general-purpose
  model: [계약 복잡도 기준 선택]
  effort: [계약 복잡도 기준 선택]
  prompt: |
    프로젝트 루트 {CWD}의 프론트엔드 코드만 읽고, 이 클라이언트가 **실제로 기대하는 API 계약**을 복원하세요.

    ## 읽을 범위
    이번 브랜치에서 변경된 API 클라이언트 / 쿼리 훅 / 응답 타입 / 에러 처리 코드
    (`git diff --name-only main...HEAD` 로 확인)

    ## 규칙
    - 백엔드 코드는 읽지 마세요.
    - `/tmp/workflow-state.md` 를 비롯한 명세·계약·계획 문서는 **읽지 마세요**. 존재하더라도 열지 마세요.
    - 파일을 수정하지 마세요.
    - 의도를 추측하지 말고, **요청 URL·전송 body·응답 타입 선언·에러 분기가 실제로 기대하는 것**만 적으세요.
    - 확신할 수 없는 항목은 지어내지 말고 `해석 불가`로 분리하세요.

    ## 출력 형식
    ### 복원된 호출
    | Method | Path | 보내는 필드 (타입) | 기대 Response 필드 (타입) | 처리하는 에러 status·코드 | 인증 헤더 | 출처 |
    |--------|------|-------------------|--------------------------|--------------------------|----------|------|

    ### 해석 불가
    - `file:line` — [무엇이 불분명한지]

    완료 후 "복원: N개 호출, 해석 불가: M건" 형식으로 보고하세요.
```

## 3방향 대조 (오케스트레이터가 직접 수행)

두 복원본과 frozen contract를 대조한다. 계약을 가진 쪽만 할 수 있으므로 **에이전트에 위임하지 않는다**.

| 축 | 확인 | 대표 증상 |
|----|------|----------|
| BE ↔ contract | 서버가 계약에서 이탈 | 계약에 없는 필수 필드 요구, status code 불일치 |
| FE ↔ contract | 클라이언트가 계약에서 이탈 | 계약에 없는 응답 필드 참조, 에러 코드 미처리 |
| **BE ↔ FE** | 양쪽이 서로 어긋남 | 필드명 camelCase/snake_case 불일치, 한쪽만 nullable 가정 |

**BE ↔ FE 축이 이 단계의 고유 가치다.** 양쪽이 계약에서 같은 방향으로 이탈하면 위 두 축은 통과하지만, 서로 다른 방향으로 이탈하면 런타임에서만 드러난다. 병렬 구현에서 가장 흔한 실패 모드다.

불일치 항목을 Phase 8.2 검증 대상 목록의 **우선 항목**으로 넘긴다. Phase 8.1은 코드를 수정하지 않는다.
