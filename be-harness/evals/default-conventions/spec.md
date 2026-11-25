# be-harness:default-conventions 명세

스킬 파일은 이 명세에서 다시 만들 수 있어야 한다. 모델이나 호스트가 바뀌면 SKILL.md 를 고치고, 이 명세와 사례로 다시 시험한다.

## 목표
be-harness 의 언어 중립 개발 컨벤션을 제공한다. convention-check 의 검사 기준이다.

## 결과물
- 질문받은 규칙의 정확한 내용 (예: 주석 접두사, 주석 길이, Assumption 태그)

## 필수 행동
- 새 주석은 `Why:` 로 시작하고 블록은 2줄 이하라는 규칙을 그대로 전달한다.
- 프로젝트 특화 규칙은 프로젝트 `CLAUDE.md` 와 `projectConventions` 가 우선한다고 알린다.

## 금지 행동
- 문서에 없는 규칙을 만들지 않는다.
