---
name: unit-test
description: "하네스별 단위 테스트 작성/실행 스킬로 위임하는 라우터. '테스트 작성해줘', '유닛 테스트 돌려줘' 요청 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--fe|--hd] [--init|--doctor] [대상 파일]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/unit-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Unit Test (라우터)

프론트엔드 하네스의 `unit-test` 스킬로 위임한다. **이 문서에 작성 규칙은 없다** — 테스트 러너와 패턴은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 설정 출처 |
|--------|----------|----------|
| `--fe` | `/fe-harness:unit-test` | `.claude/fe-harness.local.md` (`testRunner`) |
| `--hd` | `/hyeondongs-harness:unit-test-hd` | `.hyeondong-config.json` |

## 특이사항

- 백엔드 계열에는 대응 스킬이 없다. Go/Node 백엔드 테스트는 각 하네스 profile의 `testCommand` 로 `/common:start-workflow` 품질 루프에서 실행된다.
- `--init`, `--doctor` 는 해석하지 않고 그대로 전달한다.
