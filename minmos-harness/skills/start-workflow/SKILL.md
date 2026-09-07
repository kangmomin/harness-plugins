---
name: start-workflow
description: "전체 개발 워크플로우를 자동화한다 (be-harness 베이스 + **minmos 오버레이**: E2E 메인 플로우 수집, Codex 품질 리뷰, Apidog 문서 동기화, Post-Math 컨벤션). Build 모드(기본) / Analyze 모드(--analyze) / Verify 모드(--verify). '워크플로우 시작', '기능 구현해줘(전 과정 자동)' 요청 시 사용."
allowed-tools: Read, Glob, Bash, Skill
user-invocable: true
argument-hint: "<작업 설명> | --analyze [경로] | --verify [경로]"
---

# Start Workflow (minmos 오버레이)

`be-harness:start-workflow` 에 minmos 오버레이를 얹어 실행한다. **이 문서에 절차는 없다** — 워크플로우 절차의 canonical은 be-harness다.

> 진입 시 먼저 동봉 `references/entry-contract.md`를 Read하고 동봉 `workflow_policy.py route`를 entry=`mm`로 실행한다. 실제 설치 호출명으로 검사하며 미지원/충돌은 오버레이 Pre-flight·profile 저장 전에 종료한다. 원래 MODE와 PUBLISH_POLICY는 위임/도메인 전환에서도 보존한다.


> 실행 시 MUST:
> ① common 델타와 start-workflow 델타를 **파일별로** 결정한다. `.claude/be-harness/common.md`와 `.claude/be-harness/skills/start-workflow.md`를 각각 Read한다.
> ② 동봉 `workflow_policy.py sources`에 확인한 `plugin`, 절대 `plugin_root`/`cwd`, `files:["overlay/common.md","overlay/start-workflow.md"]`를 전달해 실제 소스를 결정한다. 같은 overlay-source 마커의 프로젝트 파일이 있으면 **그 파일에 한해** 설치본 로드를 생략한다. 없으면 `${CLAUDE_PLUGIN_ROOT}/overlay/common.md` 또는 `overlay/start-workflow.md` 중 해당 파일을 읽는다. 마커 없는 사용자 규칙은 보존한다. 다른 request/e2e 델타도 파일별로 적용한다.
> ③ READY의 **실제 `dispatch` 호출명**으로 Skill tool을 호출하고 gate의 인자·MODE·PUBLISH_POLICY·ROUTE_TARGET을 인계한다. 고정 별칭을 다시 만들지 않는다. base는 inherited_route_target을 보존하며 이 wrapper를 재호출하지 않는다.
> 오버레이 앵커는 베이스 Phase 제목으로 매칭한다. FS 전환은 common의 fullstack-overlays hook 매핑을 따르며 단일 도메인 Phase 번호를 FS에 복사하지 않는다.

오버레이 규약의 canonical: `docs/overlay.md`.

## 오버레이 요약

| 구분 | 내용 |
|------|------|
| Pre-flight 추가 | `secret/.env` · Apidog MCP · PostgreSQL MCP 연결 점검 |
| Phase 삽입 | `Phase 1` 직후 **E2E 메인 플로우 수집** / `Phase 8` 직후 **Codex 품질 리뷰** |
| Phase 치환 | `Phase 9 (API 문서 동기화)` → **Apidog 동기화** (`minmos-harness:workflow-doc-sync` 에이전트) |
| Plan 검증 보강 | Codex 실패(quota·MCP 부재 등) 시 Claude 다관점 패널로 대체 + `SKIPPED:CODEX_*` 기록 (루프 카운터 승계, 모드는 베이스 `codexMode`) |
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
