---
name: simplify-loop
description: "하네스별 코드 단순화 반복 루프로 위임하는 라우터. '심플리파이 돌려줘', '코드 간소화', 구현 직후 정리가 필요할 때 사용. 대상 플래그가 없으면 설치된 하네스 중에서 선택지를 제시한다."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Glob, Bash, Skill
argument-hint: "[--be|--fe|--mm] [--dry-run] [--max-iter N]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/simplify-loop.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Simplify Loop (라우터)

하네스별 `simplify-loop`으로 위임한다. **이 문서에 절차는 없다** — 루프 제어와 리뷰 방식은 대상 스킬이 정의한다.

> 실행 시 MUST: 플러그인 루트 `ROUTING.md`를 Read하고 그 절차(플래그 파싱 → 후보 산출 → 선택지 → 위임)를 따른다.

## 위임 대상

| 플래그 | 대상 스킬 | 루프 방식 |
|--------|----------|----------|
| `--be` | `/be-harness:simplify-loop` | 빌트인 `/simplify` 반복 (최대 10회) |
| `--fe` | `/fe-harness:simplify-loop` | 빌트인 `/simplify` 반복 (최대 10회) |
| `--mm` | `/minmos-harness:simplify-loop-mm` | Workflow tool 기반 4관점 리뷰 + Devil's Advocate + Arbiter, 3단 폴백 |

## 특이사항

- `--mm`은 **동작 원리가 다르다** — 결정적 script가 루프를 제어하고 4관점 병렬 리뷰를 거친다. 나머지는 빌트인 `/simplify` 반복이다. 후보에 `--mm`이 포함되면 선택지에 이 차이를 밝힌다.
- `--dry-run`, `--max-iter N` 은 해석하지 않고 그대로 전달한다.
