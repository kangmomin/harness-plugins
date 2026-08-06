<!-- overlay-source: minmos-harness@2.0.0 -->

## Base

`be-harness:request`

베이스는 프로젝트 구조를 가정하지 않고 `sourceDirs` 범위에서 계층을 탐색한다. 오버레이는 **Post-Math 백엔드의 실제 계층 매핑을 확정**해 탐색 비용을 줄인다.

## Phase 치환

| 앵커 | 대체 절차 |
|------|----------|
| 탐색 대상 계층 매핑 (베이스의 "각 계층의 실제 디렉토리명은 프로젝트마다 다르다" 블록) | 아래 §계층 매핑 표를 확정값으로 사용. 표에 없는 개념만 베이스의 `Glob` 탐색으로 보완 |
| 구현 체크리스트 (Spec 산출물) | 아래 §구현 체크리스트로 치환 |

## 계층 매핑 표 (확정값)

```
CLAUDE.md          → 프로젝트 컨벤션
Handler (rest/)    → API 엔드포인트, Request/Response
Usecase            → 비즈니스 로직, 인터페이스
Repository         → 데이터 접근, Entity
Domain (domain/)   → VO, Command, Error
DI (cmd/setup/)    → 의존성 주입
Errcode            → 에러 코드
Migration          → DB 스키마
```

## 상태 함수 탐색 (Go 특화)

베이스의 `Grep` 기반 날짜 상태 패턴 수집은 아래 명령으로 대체한다:

```bash
grep -rn 'start_at\|end_at\|startAt\|endAt\|validFrom\|expiresAt' internal/ --include='*.go'
grep -rn 'ComputeStatus\|DeriveStatus\|Now()\|time\.Now()' internal/ --include='*.go' | grep -i 'status\|state\|phase'
grep -rn 'const (\|type .*Status' internal/ --include='*.go' -A 8 | grep -i 'scheduled\|ongoing\|expired\|active\|inactive'
```

## 구현 체크리스트

Spec 산출물의 구현 체크리스트를 아래로 확정한다:

- [ ] Domain VO/Command
- [ ] Entity
- [ ] Repository 인터페이스 + 구현
- [ ] UoW 팩토리 메서드
- [ ] Usecase 인터페이스 + 구현
- [ ] Handler + 라우트
- [ ] DI 등록 (`cmd/setup/handler.go`)
- [ ] 에러 코드 등록 (`errcode.go`)
- [ ] DDL 마이그레이션 (해당 시)

## 추가 규칙

- 커서 기반 페이지네이션이 필요한 목록 API는 `/minmos-harness:pagenation` 컨벤션을 Spec 단계에서 참조한다.
- 그 외 절차·추적 ID 체계(`AC-nn`·`EC-nn`·`RC-nn`)·출력 형식은 **베이스를 그대로 따른다.**
