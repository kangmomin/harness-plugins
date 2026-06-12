---
name: simplify-loop-hd
description: "수정 사항이 없을 때까지 빌트인 /simplify를 반복 실행한다 (최대 10회). 구현 직후 코드 단순화 정리, '심플리파이 돌려줘' 요청 시 사용. start-workflow-hd 품질 루프에서 자동 호출됨."
user-invocable: true
---

아래 절차를 따라 Claude Code **빌트인** `/simplify` 스킬을 반복 실행해:

> **주의**: 여기서 `/simplify`는 Claude Code 빌트인 스킬이다. 본 플러그인(hyeondongs-harness)의 스킬이 아니다.
> Skill tool 호출 시 `skill: "simplify"` (빌트인)로 호출해야 하며, `skill: "hyeondongs-harness:simplify"`로 호출하면 안 된다.

## 절차

1. 빌트인 `/simplify` 를 실행한다 (`skill: "simplify"`).
2. 리뷰 결과를 확인한다:
   - **코드 수정이 적용된 경우** → iteration 카운트를 1 증가시키고 1번으로 돌아간다.
   - **수정할 사항이 없는 경우** (Applied Changes: 없음, 또는 모든 에이전트가 KEEP 판정) → 루프를 종료한다.
3. **최대 10회** iteration 후에는 수정 사항 유무와 관계없이 종료한다.

## 반복 패턴 감지 규칙

simplify 과정에서 **동일한 에러 핸들링 패턴이 3개 파일 이상**에서 반복 수정되면, 개별 수정 대신 유틸리티 추출을 권고한다:

> "동일한 에러 핸들링 패턴이 [N]개 파일에서 반복됩니다. 공통 유틸리티 함수로 추출하는 것을 권고합니다."
> - 대상 파일: [파일 목록]
> - 반복 패턴: [패턴 설명]

이 권고는 수정 건수에 포함하되, 실제 추출은 유저 승인 후에만 진행한다.

## 종료 조건

| 조건 | 결과 |
|------|------|
| 수정할 사항 없음 (Applied Changes: 없음 / 전원 KEEP) | 정상 종료 |
| 10회 도달, 수정 계속 발생 | 강제 종료 — 마지막 수정 내역을 출력에 포함 |

## 종료 시 출력

```
Simplify Loop 완료
- 총 iteration: N회
- 총 수정 횟수: M회
```
