<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:default-conventions`

## 추가 규칙

베이스의 범용 개발 가이드라인(변경 범위, Assumption 표기, 에러 일관성 등)에 더해, **Post-Math 백엔드 고유 컨벤션**을 함께 적용한다.

> 실행 시 MUST: `references/postmath-conventions.md` 를 Read하고 그 내용을 베이스 가이드라인 뒤에 이어 제시한다.
> 두 문서가 충돌하면 **Post-Math 컨벤션이 우선**한다 (프로젝트 특화가 범용보다 구체적이므로).

커서 기반 페이지네이션 규약은 별도 스킬이 canonical이다: `/minmos-harness:pagenation`.

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/postmath-conventions.md` | 항상 |
