<!-- overlay-source: hyeondongs-harness@3.0.0 -->

## Base

`fe-harness:start-workflow`

베이스의 Phase 구성을 그대로 따르고, 아래 델타만 얹는다. **베이스 Phase 번호를 재부여하지 않는다** (`docs/overlay.md` §4).

## Pre-flight 추가

`overlay/common.md` 의 "Pre-flight 추가"를 그대로 적용한다 (`.hyeondong-config.json` 2순위 profile).

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| `Phase 1 (작업 범위 수집)` 내부: 풀스택 판정 | 판정 기준은 베이스 그대로. **전환 시 백엔드 도메인을 `minmos-harness` 오버레이로 지정**한다 — `/common:start-workflow --fs` 호출 시 "백엔드는 minmos 오버레이 적용" 을 컨텍스트로 함께 전달한다. minmos-harness 가 설치되어 있지 않으면 이 지정 없이 be-harness 베이스로 진행한다. |

hyeondongs 프로젝트는 Post-Math 백엔드(minmos)와 짝을 이루므로, 풀스택 전환 시 백엔드 쪽이 Apidog 동기화·gRPC E2E 규칙을 그대로 받아야 계약이 어긋나지 않는다.

## 추가 규칙

- 상태 파일·리포트 경로는 베이스의 `{REPORT_DIR}`(profile `reportDir`, 없으면 `.claude/harness-reports`)를 따른다. `.hyeondong-config.json` 에는 이 필드가 없으므로 기본값이 적용된다.

그 외 Phase 절차·품질 루프·TDD·리뷰 구성은 **베이스를 그대로 따른다.**
