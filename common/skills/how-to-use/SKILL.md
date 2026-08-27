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

## Step 2: 스킬 수집

세션 스킬 목록에서 아래 접두를 가진 항목을 수집한다:

`common:` · `be-harness:` · `fe-harness:` · `minmos-harness:` · `hyeondongs-harness:`

각 스킬의 `description` 첫 문장을 요약으로 쓴다. 스킬 파일을 직접 읽지 않는다 (세션 목록으로 충분하고, 미설치 플러그인 경로 접근을 피한다).

## Step 3: 출력

```markdown
## 설치된 harness 스킬

### common — 공용 진입점
| 스킬 | 호출 | 설명 |
|------|------|------|
| start-workflow | `/common:start-workflow` | 워크플로우 단일 진입점 (도메인 판정 → 위임 / 풀스택 직접 실행) |
| commit-push | `/common:commit-push` | 커밋 후 push |

### be-harness — 범용 백엔드
| 스킬 | 호출 | 설명 |
|------|------|------|

(설치된 플러그인만 섹션으로 출력)

---
**워크플로우는 `/common:start-workflow` 하나로 시작합니다.** 요청을 분석해 백엔드/프론트엔드/풀스택을 판정하고 확인을 거쳐 실행합니다.
도메인을 미리 알면 플래그로 고정할 수 있습니다: `/common:start-workflow --be`, `--fe`, `--fs`
성찰은 기본 off입니다 — 주기적으로 `--reflect`를 붙여 실행하세요. 검증 티어(light/standard)는 Spec 점수로 자동 판정되며 `--tier standard`로 상향을 강제할 수 있습니다.
Codex 사용 모드는 `--codex none|mix|max`로 지정하면 profile `codexMode`에 저장됩니다 (기본 mix — Plan 리뷰만 Codex, max는 서브에이전트까지 Codex 위임). 위임 모델은 슬롯별로 `--codex-models review=zai/glm-5.3@high` 형식으로 바꿀 수 있습니다 (profile `codexModels` 저장 — provider는 Codex `~/.codex/config.toml`의 `[model_providers.<id>]`에 정의, GLM·Kimi 등).
그 외 스킬은 하네스를 직접 지정합니다: `/be-harness:request`, `/fe-harness:component`
```

- 설치된 플러그인이 `common` 뿐이면 하네스 설치를 안내한다:
  > "harness 플러그인이 설치되어 있지 않습니다. `/plugin install be-harness@harness-plugins` 처럼 필요한 하네스를 설치하세요."

## Step 4: 개별 스킬 상세 (스킬명이 주어진 경우)

해당 스킬의 `description` 전문과 `argument-hint` 를 보여주고, 실행 예시 2~3개를 제시한다.
같은 이름을 여러 플러그인이 제공하면 **플러그인별로 나란히** 보여주고 차이를 한 줄로 밝힌다.
