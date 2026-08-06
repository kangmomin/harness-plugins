<!-- overlay-source: hyeondongs-harness@3.0.0 -->

## Base

`fe-harness` 전체 (모든 스킬·에이전트 공통)

## Pre-flight 추가

베이스의 profile 탐색에 hyeondongs 레거시 설정을 2순위로 얹는다.

| 점검 항목 | 확인 방법 | 누락 시 영향 |
|----------|----------|-------------|
| `.claude/fe-harness.local.md` | 파일 존재 | 1순위 profile. 있으면 그대로 사용 (오버레이 개입 없음) |
| `.hyeondong-config.json` | 파일 존재 + 유효한 JSON | 1순위가 없을 때의 **2순위 profile**. 읽기 전용으로 사용하며 절대 수정하지 않는다 |
| 둘 다 없음 | — | `SKIPPED:NO_PROFILE` — `/hyeondongs-harness:init` 또는 `/fe-harness:init` 안내 |

필드 매핑(프레임워크·UI 라이브러리·상태관리·테스트/E2E 러너·패키지 매니저)의 canonical은 `fe-harness` 루트 `PROFILE.md` 다. 오버레이는 매핑을 재정의하지 않는다.

> `.claude/fe-harness.local.md` 가 기능적으로 더 완전하다 (빌드/검증 명령, 서버, Git·커밋 컨벤션, `reportDir` 포함). 새 프로젝트는 `/fe-harness:init` 을 권장한다.

## 추가 규칙

- **Language**: 유저와의 모든 대화는 한국어로 진행한다.
- `.hyeondong-config.json` 은 **읽기 전용**이다. 값 변경이 필요하면 `/hyeondongs-harness:init` 을 통해서만 수정한다.
