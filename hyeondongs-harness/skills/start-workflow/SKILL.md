---
name: start-workflow
description: "전체 프론트엔드 개발 워크플로우를 자동화한다 (fe-harness 베이스 + **hyeondongs 오버레이**: .hyeondong-config.json profile 폴백, 풀스택 전환 시 minmos 백엔드 연계). '워크플로우 시작', '화면/컴포넌트 만들어줘(전 과정 자동)' 요청 시 사용."
allowed-tools: Read, Glob, Bash, Skill
user-invocable: true
argument-hint: "<작업 설명 또는 빈 값>"
---

# Start Workflow (hyeondongs 오버레이)

`fe-harness:start-workflow` 에 hyeondongs 오버레이를 얹어 실행한다. **이 문서에 절차는 없다** — 워크플로우 절차의 canonical은 fe-harness다.

> 진입 시 먼저 동봉 `references/entry-contract.md`를 Read하고 동봉 `workflow_policy.py route`를 entry=`hd`로 실행한다. 실제 설치 호출명으로 검사하며 미지원/충돌은 오버레이 Pre-flight·profile 저장 전에 종료한다. 원래 MODE와 PUBLISH_POLICY는 위임/도메인 전환에서도 보존한다.


> 실행 시 MUST:
> ① common 델타와 start-workflow 델타를 **파일별로** 결정한다. `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/start-workflow.md`를 각각 Read한다.
> ② 동봉 `workflow_policy.py sources`에 확인한 `plugin`, 절대 `plugin_root`/`cwd`, `files:["overlay/common.md","overlay/start-workflow.md"]`를 전달해 실제 소스를 결정한다. 같은 overlay-source 마커의 프로젝트 파일이 있으면 **그 파일에 한해** 설치본 로드를 생략한다. 없으면 `${CLAUDE_PLUGIN_ROOT}/overlay/common.md` 또는 `overlay/start-workflow.md` 중 해당 파일을 읽는다. 마커 없는 사용자 규칙은 보존한다. 다른 request/e2e 델타도 파일별로 적용한다.
> ③ READY의 **실제 `dispatch` 호출명**으로 Skill tool을 호출하고 gate의 인자·MODE·PUBLISH_POLICY·ROUTE_TARGET을 인계한다. 고정 별칭을 다시 만들지 않는다. base는 inherited_route_target을 보존하며 이 wrapper를 재호출하지 않는다.
> 오버레이 앵커는 베이스 Phase 제목으로 매칭한다. FS 전환은 common의 fullstack-overlays hook 매핑을 따르며 단일 도메인 Phase 번호를 FS에 복사하지 않는다.

오버레이 규약의 canonical: `docs/overlay.md`.

## 오버레이 요약

| 구분 | 내용 |
|------|------|
| Pre-flight 추가 | `.hyeondong-config.json` 을 2순위 profile로 사용 (읽기 전용) |
| Phase 치환 | 풀스택 전환 시 **백엔드 도메인을 minmos 오버레이로 지정** |

## 전제 조건

- **`fe-harness` 선행 설치 필수.** 미설치 시 아래 고지 후 종료한다:
  > "`fe-harness` 가 설치되어 있지 않습니다. hyeondongs-harness 는 fe-harness 위에 오버레이를 얹는 플러그인입니다. `/plugin install fe-harness@harness-plugins` 로 먼저 설치하세요."
- `common` 권장 (풀스택 진입점, 커밋/PR 워크플로우), `minmos-harness` 권장 (풀스택 시 백엔드 오버레이).
- 환경 세팅은 `/hyeondongs-harness:init`, 진단은 `/hyeondongs-harness:doctor`.

## 위임 후 동작

- 베이스의 출력을 **가공하지 않고 그대로** 전달한다. 요약·재구성 금지.
- `SKIPPED:*` / `BLOCKED:*` 를 그대로 상위에 올린다.
- 이 스킬은 상태 파일을 만들거나 갱신하지 않는다.
