---
name: start-workflow
description: "하네스별 개발 워크플로우(Spec → Plan → 구현 → 품질 루프 → PR)로 위임하는 라우터. '워크플로우 시작', '기능 구현해줘(전 과정 자동)', '코드 분석/검증해줘' 요청 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--fs|--mm|--mm-fs|--hd-fs] <작업 설명 또는 대상 스킬 플래그>"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/start-workflow.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Start Workflow (라우터)

하네스별 `start-workflow`로 위임한다. **이 문서에 절차는 없다** — 실제 워크플로우는 위임 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 적용 |
|--------|----------|------|
| `--be` | `/be-harness:start-workflow` | 범용 백엔드 (Go/Node) |
| `--fe` | `/fe-harness:start-workflow` | 범용 프론트엔드 |
| `--fs` | `/fs-harness:start-workflow` | 범용 풀스택 (FE+BE 병렬 오케스트레이션) |
| `--mm` | `/minmos-harness:start-workflow-mm` | minmos 백엔드 |
| `--mm-fs` | `/minmos-harness:start-workflow-fs` | minmos 풀스택 |
| `--hd-fs` | `/hyeondongs-harness:start-workflow-fs` | hyeondongs 풀스택 |

## 특이사항

- 대상 스킬의 모드 플래그(`--hard`, `--analyze`, `--verify`)와 작업 설명은 **해석하지 않고 그대로 전달**한다.
- 대상 워크플로우가 FE+BE 동시 변경으로 판정해 풀스택으로 전환하는 경우(be-harness Phase 3의 `fullstack` 판정 등), 그 전환은 **대상 스킬이 직접 수행**한다. 라우터는 개입하지 않는다.
- 워크플로우는 장시간 자율 실행되므로, 후보가 2개 이상이면 **반드시 선택지를 거친다.** 프로젝트 신호만으로 조용히 실행하지 않는다.
