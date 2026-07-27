---
name: doctor
description: "하네스별 환경 진단 스킬로 위임하는 라우터. '환경 점검해줘', '설정 진단', 'doctor 돌려줘', 스킬이 예상대로 동작하지 않을 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm|--hd]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/doctor.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Doctor (라우터)

하네스별 진단 스킬로 위임한다. **이 문서에 점검 항목은 없다** — 진단 대상은 각 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 진단 범위 |
|--------|----------|----------|
| `--be` | `/be-harness:doctor` | profile 유효성·명령 실행 가능성·Git 상태 |
| `--fe` | `/fe-harness:doctor` | profile·테스트 러너·린터 설정 |
| `--mm` | `/minmos-harness:minmo-doctor-mm` | minmos 전 의존성 (DB/Apidog MCP/Codex 등) 일괄 |
| `--hd` | `/hyeondongs-harness:hyeondong-doctor-hd` | hyeondongs 환경 설정 |

## 특이사항

- **여러 하네스를 함께 쓰는 프로젝트라면 후보를 하나만 고르지 말고 순차 실행을 권한다.** 후보가 2개 이상일 때 선택지에 "전부 순차 실행" 항목을 포함하고, 선택 시 후보를 순서대로 위임한 뒤 결과를 하네스별로 구분해 제시한다.
- 진단은 읽기 전용이므로 여러 개를 돌려도 부작용이 없다.
