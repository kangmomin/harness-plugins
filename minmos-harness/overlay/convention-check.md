<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:convention-check`

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| 기본 컨벤션 목록 (`.convention-check.json` 부재 시의 기본값) | `default-conventions` + `pagenation` + profile의 `projectConventions` |
| `--init` 의 "플러그인 내장" 후보 목록 | 아래 §컨벤션 후보로 치환 |

## 컨벤션 후보

`--init` 실행 시 제시하는 목록에 아래를 포함한다:

> **플러그인 내장:**
> 1. `default-conventions` — 범용 개발 가이드라인 + Post-Math 고유 컨벤션(에러 처리, VO 패턴, 트랜잭션)
> 2. `pagenation` — 커서 기반 페이지네이션
>
> **프로젝트:**
> 3. `CLAUDE.md` — 프로젝트 아키텍처 및 레이어 컨벤션

생성되는 `.convention-check.json` 의 `skill` 필드는 오버레이 기준으로 적는다:

```json
{
  "conventions": [
    { "name": "default-conventions", "source": "plugin", "skill": "be-harness:default-conventions", "overlay": "minmos-harness" },
    { "name": "pagenation", "source": "plugin", "skill": "minmos-harness:pagenation" },
    { "name": "CLAUDE.md", "source": "project", "path": "CLAUDE.md" }
  ]
}
```

## Pre-flight 추가

`--doctor` 점검 표에 아래 행을 추가한다:

| 항목 | 상태 | 비고 |
|------|------|------|
| pagenation 스킬 | OK / MISSING | `/minmos-harness:pagenation` 존재 확인 |
| postmath-conventions | OK / MISSING | `overlay/references/postmath-conventions.md` 존재 확인 |

## 검사 기준 추가

베이스가 로드하는 컨벤션 문서에 더해 `references/postmath-conventions.md` 를 **항상** 검사 기준에 포함한다.

절차·보고 형식·태그 체계는 **베이스를 그대로 따른다** (보고 전용 — 코드를 수정하지 않는다).
