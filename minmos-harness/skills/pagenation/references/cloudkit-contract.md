# 확인한 CloudKit cursor 계약

2026-09-06, `/workspace/cloudkit` HEAD `76a65f38e9bf092cc25f2a4119a6f3dde6ea94d6`의 `cloudKit/cursor_data.go`를 읽고 파일 자체를 임시 stdlib-only Go module에 복사하여 실행했다. 소비 저장소/모듈 캐시 소스를 수정하지 않았다. 기록은 harness 저장소의 `tests/fixtures/cloudkit-cursor/observed.json`이다.

- `ParseOrderParam`은 `|`로 항목을 나눈다. column/direction 문자열을 유지하고 방향을 lowercase로 바꾸지만 허용 키/asc·desc 검증을 하지 않는다. 잘못된 항목은 조용히 빠진다.
- `EqualOrderSpecs`는 column/direction을 비교하며 value는 비교하지 않는다.
- `CursorEncode`는 `CURSOR_SECRET`이 있으면 HMAC 서명을 추가하고 없으면 unsigned로 동작한다. 설정은 `sync.Once`로 고정되므로 signed/unsigned 검증은 별도 프로세스로 실행했다.
- 실제 `CursorDecode`에서 int64 `9007199254740993`이 interface{}의 float64 `9007199254740992`로 바뀌었다. 정수 ID를 원래 값 그대로 seek하려면 검증된 typed codec 경계가 필요하다.
- `CursorEncode`는 JSON marshal 실패 시 panic했다. adapter는 해당 오류가 workflow/process를 중단하지 않도록 오류 계약을 명시해야 한다.

이 관측은 해당 소스 버전에 한정된다. 소비 서비스의 호출 전 검증/권한 필터를 조사하지 않았으므로 그 서비스의 SQL Injection 취약점으로 단정하지 않는다. 설치된 CloudKit 버전이 다르면 해당 소스를 먼저 확인한다.
