> 이 문서는 `start-workflow`(fs-harness) 스킬의 Phase 6(병렬 구현)에서 로드된다. 단독 실행 금지.
> `{STATE_FILE}` 등 플레이스홀더 정의는 SKILL.md 본문을 따른다.

# 구현 에이전트 프롬프트 (Phase 6)

두 구현 에이전트를 **같은 메시지 내에서 병렬 호출**한다 (Agent tool × 2).

## 백엔드 구현 에이전트

```
Agent tool:
  subagent_type: be-harness:workflow-implementer
  model: [백엔드 작업량 기준 선택]
  effort: [백엔드 작업량 기준 선택]
  prompt: |
    상태 파일 `{STATE_FILE}`을 읽고, **Backend Plan** 섹션만 구현하세요.
    프로젝트 루트: {CWD}
    현재 Phase: Phase 6 Backend
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
    현재 Phase: Phase 6 Frontend
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
