---
name: how-to-use
description: "설치된 harness 플러그인의 스킬 목록과 사용법을 안내한다. '어떤 스킬 있어?', '사용법 알려줘', '뭐 할 수 있어?', 플러그인을 처음 쓸 때 사용. 특정 하네스만 보려면 대상 플래그를 붙인다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm|--hd] [스킬명]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/how-to-use.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# How to Use

설치된 harness 플러그인의 스킬을 안내한다.

대상 플래그는 동작을 바꾸는 스위치가 아니라 **출력 범위를 좁히는 필터**다.

## Step 1: 범위 결정

| 입력 | 범위 |
|------|------|
| 플래그 없음 | 세션에 설치된 **모든** harness 플러그인 |
| `--be` / `--fe` / `--mm` / `--hd` | 해당 플러그인만 |
| 스킬명 (예: `start-workflow`) | 그 이름을 제공하는 모든 플러그인의 해당 스킬 |

플래그가 없어도 **선택지를 묻지 않는다.** 전체 안내가 기본 동작이며, 이것이 처음 쓰는 사용자에게 가장 유용하다.

## Step 2: 실제 세션 metadata 수집

접두사 목록으로 설치 여부를 추정하지 않는다. 호스트가 현재 세션에 제공한 스킬의 정확한 `name`, `description`, `argument_hint`, 실제 `invocation`(제공된 경우)을 수집한다. 설치 이름이 바뀌거나 새 하네스가 추가돼도 원래 호출 식별자를 보존한다. 파일 경로만 발견된 스킬은 호출 가능하다고 표시하지 않는다.

`assets/skill_catalog.py`에 `{skills:[...], filter?, plugin?, skill?}` JSON을 전달해 목록을 구성한다. 이 helper는 스킬 실행이나 설치를 하지 않는다.

- `roles`는 호스트/설치 manifest에서 확인한 논리 역할 `be|fe|mm|hd`이며 근거 경로/metadata key를 `roles_source`로 함께 전달한다. 이름만 보고 역할을 붙이지 않는다.
- 역할 정보가 없으면 기본 전체 안내에 `분류 미확인`으로 함께 표시한다. `--be` 등 역할 필터에 대해 근거가 없으면 `UNVERIFIED_FILTER`를 보고하며, 현재 실제 plugin 이름으로 좁힐 수 있음을 안내한다.
- 플러그인별로 묶되 동일 basename의 스킬을 합치지 않는다. `start-workflow` 제공자는 모두 보존한다.
- plugin 목록이 비었거나 요청 스킬이 없으면 `NO_MATCH`와 현재 확인 가능한 이름만 보고한다. 정적인 설치 명령이나 존재하지 않는 호출명을 대신 만들지 않는다.

## Step 3: 출력

각 plugin별로 `스킬 | 실제 호출명 | 설명` 표를 만든다. 설명은 metadata 첫 문장을 사용한다. 예시의 호출명도 행의 실제 식별자를 그대로 사용한다.

진입점 안내는 반환된 `entrypoints`가 있을 때만 출력한다. 여러 개면 역할/설치 설명에 따라 나란히 보여 준다. common이 없는 환경에 common 호출을 권하지 않는다. 반환된 `invocation`이 없으면 정확한 `name`과 ‘세션의 스킬 선택/호출 도구에서 이 이름 사용’을 표시하며 `/`·`$` 형태를 추측하지 않는다.

워크플로우 flags·모델 슬롯 예시는 해당 스킬의 현재 `argument_hint` 또는 사용자가 선택한 상세 문서로 검증한 것만 쓴다. 다른 배포판의 고정 예시를 복사하지 않는다.

## Step 4: 개별 스킬 상세

해당 항목의 `description` 전문과 `argument_hint`를 보여 준다. 실제 세션 metadata가 제공한 스킬 경로가 있으면 필요한 문서 하나를 읽어 예시를 작성한다. 모든 예시의 호출 부분은 같은 항목의 `invocation`/`name`을 사용한다. 경로나 인자 계약을 확인할 수 없으면 설명까지만 제공한다.

같은 이름을 여러 플러그인이 제공하면 플러그인별로 나란히 보여 주고, 확인된 차이만 밝힌다.
