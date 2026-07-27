---
name: init
description: "하네스별 프로젝트 초기 설정(profile 생성)으로 위임하는 라우터. '하네스 세팅해줘', 'init 실행', 'profile 만들어줘', 플러그인 첫 사용 시 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm|--hd]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/init.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Init (라우터)

하네스별 초기 설정 스킬로 위임한다. **이 문서에 설정 절차는 없다** — 수집 항목과 생성 파일은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 생성물 |
|--------|----------|--------|
| `--be` | `/be-harness:init` | `.claude/be-harness.local.md` (Go/Node 프리셋) |
| `--fe` | `/fe-harness:init` | `.claude/fe-harness.local.md` |
| `--mm` | `/minmos-harness:minmo-init-mm` | minmos 전 사전 세팅 일괄 |
| `--hd` | `/hyeondongs-harness:hyeondong-init-hd` | `.hyeondong-config.json` |

## 특이사항

- **이 라우터는 프로젝트 신호로 권장 후보를 표시하지 않는다.** init은 신호(profile 파일)를 *만드는* 스킬이라, 신호가 없는 상태가 정상이다. 후보를 그대로 나열한다.
- 이미 해당 profile이 존재하면 대상 스킬이 갱신 여부를 묻는다. 라우터는 존재 여부를 검사하지 않는다.
- 풀스택 프로젝트는 백엔드·프론트엔드 init을 **각각** 실행해야 한다. 후보에 양쪽이 있으면 선택지에 "둘 다 순차 실행" 항목을 포함한다.
