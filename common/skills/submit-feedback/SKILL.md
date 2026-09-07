---
name: submit-feedback
description: "harness 플러그인 사용 중 수집된 범용 보완점을 플러그인 레포(kangmomin/harness-plugins)의 community-feedback 영역에 PR로 제출한다. '피드백 보내줘', '보완점 PR 올려줘' 요청 시 사용. 실패 시 로컬 저장으로 fallback."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
argument-hint: "[--be|--fe|--mm|--hd] <보완점 항목 JSON> 또는 대화 컨텍스트에서 수집"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/submit-feedback.md`를 Read. 우선순위는 플러그인 루트 `OVERRIDES.md`를 따른다.

# Submit Feedback

워크플로우 성찰에서 수집한 범용 제안을 대상 플러그인의 `community-feedback/`에 PR로 제출한다. 제출 요청은 원본 스킬 수정이나 로컬 활성 override 적용 권한을 뜻하지 않는다.

## 1. 대상과 본문 확정

현재 세션의 실제 plugin metadata와 upstream manifest에서 대상 plugin·repo·default branch를 확인한다. `--be|--fe|--mm|--hd`는 확인된 논리 역할 필터로 사용한다. 여러 plugin이면 각각 처리한다. 대상이 모호하면 내용 정리까지 진행하고 대상만 확인받는다.

입력은 `{plugin, date: YYYY-MM-DD, items:[...]}`다. 각 항목은 `target_type: skill|agent|common`, 단일 경로 성분인 `target_name`, `summary`, `context`, `proposal`, `generality: 범용|특정 조건|프로젝트 한정`, 선택 `condition`을 가진다. 사내 용어·시크릿·개인 정보가 있는 본문은 외부 제출 전 범용화해 구체적인 diff로 검토한다. 프로젝트 한정 항목은 외부 제출에서 제외한다.

## 2. 로컬 보존 — 인증·네트워크 점검보다 먼저

`assets/feedback.py prepare`를 사용한다. JSON 입력은 `{payload: 위 입력, artifact_root: 프로젝트의 .claude/{plugin}/feedback-submissions 절대 경로}`다. 실행별 0700 디렉터리에 0600 `payload.json`을 저장하고 fsync한다. 반환된 `artifact`와 `sha256`를 원래 receipt로 보존한다.

이 스킬이 로컬 보존의 주체다. 단독 호출과 start-workflow 호출 모두 동일하다. 호출자가 또 저장하도록 신호만 보내지 않는다. 보존본은 제출 증거이며 **활성 common.md/skills/agents override가 아니다**. 로컬 저장이 실패하면 경로·실패를 보고하고 원격 작업을 시작하지 않는다.

경로 매핑은 helper의 `destination()` 하나만 사용한다. preview와 실제 append가 동일한 `destinations`를 따른다.

| target_type | 경로 |
|---|---|
| skill | `{plugin}/community-feedback/skills/{target_name}.md` |
| agent | `{plugin}/community-feedback/agents/{target_name}.md` |
| common | `{plugin}/community-feedback/common/{date}-{summary-slug}-{identity-hash}.md` |

`common`을 `commons`로 만들지 않는다. hash는 날짜·대상·요약으로 정해 같은 입력은 같은 경로, slug가 같은 서로 다른 제안은 서로 다른 경로가 된다.

## 3. 구체적인 제출 내용과 권한 확인

로컬 receipt, 추가 예정 파일, 본문 diff, 제외 항목, upstream/base, PR 제목을 제시한다. 사용자가 이미 이 제출을 요청·승인했다면 재확인하지 않는다. 아직 외부 제출 권한이 없다면 완성된 제안에 대해 마지막으로 확인받는다.

이후 `gh`/`git` 존재와 `gh auth status`, 실제 로그인 사용자 및 upstream 접근을 확인한다. 실패하면 `feedback.py outcome`에 `{stage: auth, result: FAILED}`를 전달해 LOCAL_ONLY를 보고한다. artifact는 유지한다. 진단 중 설치·로그인·fork를 자동으로 수행하지 않는다.

## 4. 실행 소유 임시 checkout

이 실행만의 `mktemp -d` 경로를 기록하고 그 안에 clone한다. self-owner는 upstream, 다른 사용자는 확인한 본인 fork를 사용한다. 기존 fork는 upstream 정합성을 확인한 뒤 재사용한다. clone은 argument 배열 또는 정확히 인용한 경로로 실행한다. 기존 작업 checkout을 임시 경로로 취급하지 않는다.

fork/clone 오류는 해당 stage의 FAILED 또는 결과 불명확 시 UNKNOWN으로 기록하고 원격 작업을 멈춘다. 로컬 보존본은 유지하며 소유한 임시 checkout만 정리한다. 임의 기존 브랜치로 `checkout ... || checkout ...`하는 fallback은 사용하지 않는다.

브랜치는 `feedback/{plugin}/{date}-{로컬 artifact 실행 ID}`로 유일하게 만든다. 재개 시 같은 ID의 기존 branch/PR을 먼저 조회하고 repo/base/head와 제출 내용 hash를 대조한다. 일치한 기존 PR은 `EXISTS_MATCH`, 다른 내용이면 `EXISTS_OTHER`; 후자에 append·강제 push하지 않는다.

## 5. 중복 제거와 실제 파일 쓰기

`feedback.py apply`에 `{receipt: Step 2 원래 receipt, checkout: 소유 임시 clone 절대 경로}`를 전달한다. receipt의 payload hash를 다시 검증하고 symlink 목적지를 거부한다. 날짜·대상·요약이 같은 항목은 skip한다. 기존 형식의 항목도 동일 필드로 대조한다.

- `NO_CHANGES` / `added=0`: artifact 경로와 중복 결과를 보고하고 종료. git add/commit/push/PR 호출 없음.
- `READY`: 반환된 정확한 `paths`만 stage하고 실제 staged diff가 있는지 확인한다. 변경이 사라졌으면 NO_CHANGES. 빈 commit은 만들지 않는다.

각 단계 후 `feedback.py outcome`의 `{stage, result, added}` 판정을 따른다. `ACK`는 실제 성공 확인이 있는 경우만 사용한다. commit → push → PR 순서며 앞 단계 실패를 다음 단계의 성공으로 덮지 않는다.

PR 본문은 정확한 텍스트 파일로 만들고 `gh pr create --body-file`로 전달한다. 셸 command substitution으로 본문을 합성하지 않는다. fork head는 확인된 `{user}:{branch}`, self-owner는 확인된 `{branch}`를 사용한다.

## 6. 응답 유실과 결과 보고

| 상황 | 상태·후속 처리 |
|---|---|
| gh/auth/fork/clone/commit 실패 | LOCAL_ONLY, 로컬 artifact 유지 |
| 중복만 남음 | NO_CHANGES, 빈 commit/PR 없음 |
| push 또는 PR 응답 timeout/유실 | UNKNOWN, 같은 요청을 바로 다시 보내지 않음 |
| 확인된 기존 동일 PR | ALREADY_SUBMITTED + 실제 URL |
| 기존 다른 PR/branch | LOCAL_ONLY + 충돌 정보 |
| 실제 PR 생성 및 repo/base/head/내용 확인 | SUBMITTED + 실제 URL |

UNKNOWN은 원격 branch SHA 또는 PR repo/base/head/내용을 새로 readback한다. 성공이 확인되면 다음 단계나 ALREADY_SUBMITTED로 정정한다. 확인이 안 되면 UNKNOWN을 유지한다. 응답 유실을 실패로 추정해 두 번째 PR을 만들지 않는다. 정상 종료 코드만으로 다른 대상의 PR을 성공 처리하지 않는다.

보고에는 상태, 실제 PR URL(확인된 경우만), artifact 경로/hash, added/중복/제외 개수, 남은 readback을 포함한다. 소유 임시 checkout과 본문 파일은 finally에서 정리하며 durable artifact는 삭제하지 않는다. 정리 실패는 제출 결과와 별도로 보고한다. 호출자는 이 결과를 그대로 최종 기록에 반영하고 같은 항목을 재저장하거나 재전송하지 않는다.
