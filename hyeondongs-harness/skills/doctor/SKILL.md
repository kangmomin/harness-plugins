---
name: doctor
description: "hyeondongs-harness 플러그인의 모든 의존성 상태를 한 번에 진단한다. 워크플로우가 SKIP을 내거나 설정이 의심될 때, '환경 진단해줘' 요청 시 사용."
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
---


# Hyeondong Doctor

이 스킬은 현재 설치된 **fe-harness doctor**에 위임한다. 세션 스킬 메타데이터에서 실제 FE doctor 호출명과 설치 루트를 확인하고 그 SKILL.md를 실행한다. 기본 경로/러너 검사 로직을 여기에 복제하지 않는다. FE base가 없으면 `BLOCKED:BASE_NOT_INSTALLED`로 정확한 의존성을 안내한다.

- 실효 profile은 FE `skills/config/assets/profile.py`가 결정한다. 현대 `.claude/fe-harness.local.md`가 있으면 레거시를 읽지 않는다. 레거시만 있어도 LEGACY로 정상 진단한다.
- `typescript:false`, `e2eRunner:none`, `codexMode:none`, `storybook:false`는 SKIP이다. Cypress 선택에 Playwright를 검사하지 않는다.
- Hyeondong 오버라이드가 추가하는 검사만 base 결과에 합친다. 단순 파일 부재를 설정 실패로 다시 분류하지 않는다.
- 진단 중 다운로드 없음. 실제 테스트를 실행하지 않았으면 PASS라고 보고하지 않는다.
- 해결 안내의 init/config/doctor 이름도 실제 설치 메타데이터에서 찾는다. 별칭을 만들어 안내하지 않는다.
