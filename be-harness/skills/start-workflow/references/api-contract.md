> 이 문서는 `start-workflow` Build 모드 Phase 4.1(초안), 4.4(승인), 4.5(FE 이슈), 12(보고)에서 로드된다. 단독 실행 금지.

# API 계약 확정 + FE 이슈

순서: Plan 작성·리뷰(4.1~4.3) → **API 계약 승인(4.4, ExitPlanMode 전)** → **FE 이슈(4.5)** → 브랜치·baseline(5) → 구현(6, Red → Green — quick은 6.2에 테스트 동반) → 빌드(7) → 품질 루프·테스트(8). 4.5 뒤의 절차는 바뀌지 않는다.

## 1. 실행 조건

| 조건 | 결과 |
|------|------|
| 작업 유형이 API 생성/수정/삭제 | §2~§4 실행 (모든 티어) |
| 그 외 (내부 로직·배치·리팩터 등) | Phase 4.5 = `SKIPPED:NO_API_CHANGE` — §2~§4 생략 |

4.4·4.5는 Phase 5 이전이므로 **유저와 대화할 수 있는 구간**이다. 상태 파일은 아직 없다. 결과는 Phase 5에서 상태 파일 `## API Contract`에 복사한다.

## 2. 계약 표 (Phase 4.1 — Plan에 포함)

Plan에 `## API Contract` 섹션으로 아래 표를 넣는다. Plan 리뷰(4.2·4.3)는 이 표도 함께 본다.

```
| ID | Method Path | Auth | Request | Response | Errors (status·code) | 호환성 | 근거 |
|----|-------------|------|---------|----------|----------------------|--------|------|
| API-01 | POST /v1/orders | user | {itemId:string, qty:int≥1} | 201 {orderId:string} | 400 INVALID_QTY · 401 · 404 ITEM_NOT_FOUND | 신규 | AC-01, EC-02 |
```

- 1행 = endpoint 1개. 필드는 이름·타입·필수 여부·제약을 쓴다. 기존 필드를 바꾸면 `old → new`로 쓴다.
- `호환성` = `신규` | `삭제` | `호환(추가 필드만)` | `비호환({변경 내용})` | `변경 없음`.
- `근거`는 Spec의 `AC-nn`/`EC-nn`/`RC-nn`이다. 근거가 없는 행은 만들지 않는다. Red 테스트(6.1)는 지금과 같이 AC/EC/RC를 근거로 한다 — 이 표는 새 테스트 근거를 만들지 않는다.

## 3. 사용자 승인 (Phase 4.4 — ExitPlanMode 전)

4.4의 Plan 승인 화면에서 계약 표를 **별도 항목으로 먼저** 보여 주고 승인 / 수정 / 중단을 받는다. Plan 승인과 같은 승인 절차이므로 따로 한 번 더 묻지 않는다 (`execution-policy.md`의 승인 재사용).

- **수정**: 사용자가 말한 행을 고치고, Plan의 영향받는 부분도 고친다. 그 다음 4.4의 재판정 규칙(T·P 상향만, 올라간 P의 4.2·4.3만 실행)을 그대로 따른다. P가 quick이면 4.3을 다시 실행하지 않는다. 고친 행만 다시 승인받는다.
- **중단**: 워크플로우를 끝낸다 (상태 파일 생성 전).
- 승인 결과(최종 표·승인 시각)는 Plan과 함께 보관했다가 Phase 5에서 복사한다.

## 4. FE 이슈 (Phase 4.5 — ExitPlanMode 후)

### 4.1 외부 계약 변경 판정

아래 중 1개라도 있으면 **변경 있음**이다:
- `호환성`이 `신규` · `삭제` · `호환(추가 필드만)` · `비호환(…)`
- status code·에러 code·인증 조건의 변경

모든 행이 `변경 없음`이면 `SKIPPED:NO_EXTERNAL_CHANGE`.

### 4.2 분기

| 상태 | 행동 | FE 이슈 결과 |
|------|------|------|
| 변경 없음 | 이슈를 만들지 않는다 | `SKIPPED:NO_EXTERNAL_CHANGE` |
| profile `frontendRepo` 비어 있음 | 초안만 남기고 Phase 12에서 수동 등록 안내 | `SKIPPED:FRONTEND_REPO_EMPTY` |
| `frontendRepo` 있음 | 초안을 보여 주고 AskUserQuestion으로 등록 승인 | 아래 |
| ㄴ 승인 | 중복 검사 후 `gh issue create -R {frontendRepo} --title "…" --body-file {RUN_DIR}/fe-issue.md` | `DONE {URL}` |
| ㄴ 거절 | 초안만 남긴다 | `SKIPPED:USER_DECLINED` |
| ㄴ `gh` 없음·인증·권한 오류 | 초안을 남기고 오류 1줄 기록, 워크플로우는 계속 | `SKIPPED:GH_UNAVAILABLE` |

- 이슈 등록은 외부에 글을 쓰는 동작이다. 사용자 승인 없이 만들지 않는다.
- 초안은 먼저 `{RUN_DIR}/fe-issue.md`에 Write한다. 등록하면 같은 파일 끝에 `URL: {URL}`을 바로 append한다. Phase 5 전에 세션이 끊겨도 기록이 남는다.
- **중복 검사**: 만들기 전에 `{RUN_DIR}/fe-issue.md`에 `URL:`이 있으면 다시 만들지 않는다. 없으면 `gh issue list -R {frontendRepo} --state open --search "{제목} in:title"`로 같은 제목을 찾는다. 있으면 그 URL을 쓰고 새로 만들지 않는다.
- Phase 4.5 상태는 `DONE`(이슈 처리를 끝냄) 또는 `SKIPPED:NO_API_CHANGE`다. 위 표의 결과는 `## API Contract`의 `FE 이슈` 줄에만 쓴다.

### 4.3 이슈 초안

```
제목: [API] {작업 요약} — {신규|변경|삭제} {N}건

## 변경 요약
{작업 요약 1~2줄}

## API 계약
{§2 표에서 `변경 없음`이 아닌 행만}

## FE 영향
- 비호환 변경: {행 ID와 내용 | 없음}
- 배포 순서 주의: {있으면 1줄 | 없음}

## BE 작업
- BE PR: 생성 후 링크 예정 (BE PR 본문에 이 이슈 링크가 들어간다)
```

## 5. 이후 단계와의 연결

- Phase 5: `## API Contract`에 최종 표 · 승인 시각 · FE 이슈 결과/URL · `{RUN_DIR}/fe-issue.md` 경로를 기록한다.
- Phase 6~8: 자율 실행 중에 계약을 바꿔야 하면 코드를 먼저 바꾸지 않는다. Spec 외 변경 금지 원칙대로 `[Assumption]`으로 기록하고 Phase 12에서 결정받는다.
- Phase 10: FE 이슈 URL이 있으면 PR 본문에 `FE 이슈: {URL}` 1줄을 넣는다.
- Phase 12: 보고서 §1에 FE 이슈 결과를 1줄로 쓴다. `SKIPPED:FRONTEND_REPO_EMPTY`·`SKIPPED:USER_DECLINED`·`SKIPPED:GH_UNAVAILABLE`이면 초안 경로(`{RUN_DIR}/fe-issue.md`)와 수동 등록 안내를 함께 쓴다. 결정으로 계약이 바뀌었고 FE 이슈가 있으면 이슈 갱신(코멘트) 여부도 함께 묻는다 — 승인 후에만 `gh issue comment`.
