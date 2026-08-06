---
name: start-workflow
description: "전체 개발 워크플로우를 자동화한다 (be-harness 베이스 + **minmos 오버레이**: E2E 메인 플로우 수집, Codex 품질 리뷰, Apidog 문서 동기화, Post-Math 컨벤션). Build 모드(기본) / Analyze 모드(--analyze) / Verify 모드(--verify). '워크플로우 시작', '기능 구현해줘(전 과정 자동)' 요청 시 사용."
allowed-tools: Read, Glob, Bash, Skill
user-invocable: true
argument-hint: "<작업 설명> | --analyze [경로] | --verify [경로]"
---

# Start Workflow (minmos 오버레이)

`be-harness:start-workflow` 에 minmos 오버레이를 얹어 실행한다. **이 문서에 절차는 없다** — 워크플로우 절차의 canonical은 be-harness다.

> 실행 시 MUST:
> ① `.claude/be-harness/skills/start-workflow.md` 를 Read 시도한다.
>    - 존재하고 `<!-- overlay-source: minmos-harness@... -->` 마커가 있으면 → **경로 B(프로젝트 복사)가 이미 설치됨.** ②를 생략하고 ③으로 간다 (중복 적용 방지).
>    - 없거나 마커가 없으면 → ②로 간다.
> ② `${CLAUDE_PLUGIN_ROOT}/overlay/common.md` 와 `${CLAUDE_PLUGIN_ROOT}/overlay/start-workflow.md` 를 Read하고, 그 내용을 "베이스 절차에 적용할 델타"로 보유한다.
>    오버레이 문서의 앵커 표(Phase 삽입/치환)는 **베이스 SKILL.md의 Phase 제목으로 매칭**한다. 절대 번호로 매칭하지 않는다.
> ③ Skill tool로 `/be-harness:start-workflow` 를 호출하고, `$ARGUMENTS` 를 **해석하지 않고 그대로** 전달한다.

오버레이 규약의 canonical: `docs/overlay.md`.

## 오버레이 요약

| 구분 | 내용 |
|------|------|
| Pre-flight 추가 | `secret/.env` · Apidog MCP · PostgreSQL MCP 연결 점검 |
| Phase 삽입 | `Phase 1` 직후 **E2E 메인 플로우 수집** / `Phase 8` 직후 **Codex 품질 리뷰** |
| Phase 치환 | `Phase 9 (API 문서 동기화)` → **Apidog 동기화** (`minmos-harness:workflow-doc-sync` 에이전트) |
| Plan 검증 보강 | Codex quota 차단 시 Claude 다관점 패널로 대체 (루프 카운터 승계) |
| 스킬 오버레이 | `request` · `e2e-test` · `e2e-test-loop` · `convention-check` · `default-conventions` |

## 전제 조건

- **`be-harness` 선행 설치 필수.** 미설치 시 아래 고지 후 종료한다:
  > "`be-harness` 가 설치되어 있지 않습니다. minmos-harness 는 be-harness 위에 오버레이를 얹는 플러그인입니다. `/plugin install be-harness@harness-plugins` 로 먼저 설치하세요."
- `common` 플러그인 권장 (커밋/PR 워크플로우, 풀스택 전환 경로).
- 환경 세팅은 `/minmos-harness:init`, 진단은 `/minmos-harness:doctor`.

## 위임 후 동작

- 베이스의 출력을 **가공하지 않고 그대로** 전달한다. 요약·재구성 금지.
- `SKIPPED:*` / `BLOCKED:*` 를 그대로 상위에 올린다.
- 이 스킬은 상태 파일을 만들거나 갱신하지 않는다.
