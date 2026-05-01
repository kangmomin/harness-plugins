---
name: fe-harness__how-to-use
description: "플러그인 내 스킬의 사용법을 안내한다. 스킬 목록을 보여주고 선택한 스킬의 사용법을 설명한다."
allowed-tools: AskUserQuestion, Read, Glob
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/how-to-use.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# How to Use — 스킬 사용법 안내

이 플러그인(fe-harness)에 포함된 스킬의 사용법을 안내한다.

## 실행 흐름

### Step 1: 스킬 목록 탐색

`Glob`으로 `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` 를 탐색하여 현재 플러그인에 등록된 스킬 목록을 수집한다.
각 SKILL.md의 frontmatter에서 `name`과 `description`을 읽는다.

### Step 2: 스킬 선택 질문

`AskUserQuestion`으로 사용자에게 어떤 스킬의 사용법이 궁금한지 질문한다.
번호를 매겨 선택하기 쉽게 한다.

형식:

```
어떤 스킬의 사용법이 궁금하신가요?

 1. /commit — 현재까지의 작업을 논리적 단위별로 나눠서 커밋
 2. /request — 작업 유형별 단계적 질문을 통해 Technical Spec 생성
 ...
```

- `$ARGUMENTS`에 스킬 이름이 있으면 선택 질문을 건너뛰고 바로 Step 3으로 진행한다.
- 예: `/how-to-use commit` → 바로 commit 스킬 안내

### Step 3: 해당 스킬의 SKILL.md 읽기

선택된 스킬의 `${CLAUDE_PLUGIN_ROOT}/skills/{선택된 스킬}/SKILL.md` 전문을 `Read`로 읽는다.

### Step 4: 사용법 안내

읽은 SKILL.md 내용을 기반으로 다음을 포함하여 **사용자 친화적으로** 안내한다:

1. **한 줄 요약** — 이 스킬이 뭘 하는지
2. **호출 방법** — `/스킬명` 또는 `/스킬명 인자` 형식
3. **주요 동작 흐름** — 스킬이 실행되면 어떤 단계를 거치는지 간결하게
4. **필요한 인자** — `argument-hint`가 있으면 설명, 없으면 "인자 없이 실행"
5. **사전 조건** — 스킬 실행 전 필요한 것이 있으면 안내 (예: `--init` 옵션)
6. **관련 스킬** — 함께 쓰면 좋은 다른 스킬이 있으면 언급

안내는 간결하게. SKILL.md 원문을 그대로 붙여넣지 않는다.

### Step 5: 추가 질문

안내 후 `AskUserQuestion`으로 추가로 궁금한 스킬이 있는지 물어본다.
있으면 Step 3으로 돌아간다. 없으면 종료한다.
