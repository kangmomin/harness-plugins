---
name: start-workflow
description: "전체 프론트엔드 개발 워크플로우를 자동화한다 (fe-harness 베이스 + **hyeondongs 오버레이**: .hyeondong-config.json profile 폴백, 풀스택 전환 시 minmos 백엔드 연계). '워크플로우 시작', '화면/컴포넌트 만들어줘(전 과정 자동)' 요청 시 사용."
allowed-tools: Read, Glob, Bash, Skill
user-invocable: true
argument-hint: "<작업 설명 또는 빈 값>"
---

# Start Workflow (hyeondongs 오버레이)

`fe-harness:start-workflow` 에 hyeondongs 오버레이를 얹어 실행한다. **이 문서에 절차는 없다** — 워크플로우 절차의 canonical은 fe-harness다.

> 실행 시 MUST:
> ① `.claude/fe-harness/skills/start-workflow.md` 를 Read 시도한다.
>    - 존재하고 `<!-- overlay-source: hyeondongs-harness@... -->` 마커가 있으면 → **경로 B(프로젝트 복사)가 이미 설치됨.** ②를 생략하고 ③으로 간다 (중복 적용 방지).
>    - 없거나 마커가 없으면 → ②로 간다.
> ② `${CLAUDE_PLUGIN_ROOT}/overlay/common.md` 와 `${CLAUDE_PLUGIN_ROOT}/overlay/start-workflow.md` 를 Read하고, 그 내용을 "베이스 절차에 적용할 델타"로 보유한다.
>    오버레이 문서의 앵커 표는 **베이스 SKILL.md의 Phase 제목으로 매칭**한다. 절대 번호로 매칭하지 않는다.
> ③ Skill tool로 `/fe-harness:start-workflow` 를 호출하고, `$ARGUMENTS` 를 **해석하지 않고 그대로** 전달한다.

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
