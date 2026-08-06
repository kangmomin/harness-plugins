---
name: unit-test
description: "하네스별 단위 테스트 작성/실행 스킬로 위임하는 라우터. '테스트 작성해줘', '유닛 테스트 돌려줘', 구현 전 실패 테스트를 먼저 만들 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be] [--fe] [--red] [--init|--doctor] [대상 파일]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/unit-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Unit Test (라우터)

하네스별 `unit-test` 스킬로 위임한다. **이 문서에 작성 규칙은 없다** — 테스트 러너와 범위 규칙은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 설정 출처 |
|--------|----------|----------|
| `--be` | `/be-harness:unit-test` | `.claude/be-harness.local.md` (`testCommand`, `testDirs`) |
| `--fe` | `/fe-harness:unit-test` | `.claude/fe-harness.local.md` (`testRunner`) |

## 특이사항

- minmos 백엔드에는 전용 `unit-test` 스킬이 없다. `--mm` 이 오면 `--be` 로 처리하고 한 줄 고지한다: "minmos 전용 unit-test 는 없습니다. `/be-harness:unit-test` 로 진행합니다."
- `--red`, `--init`, `--doctor` 는 해석하지 않고 그대로 전달한다.
