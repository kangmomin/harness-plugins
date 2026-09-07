---
name: merge
description: "현재 브랜치 또는 지정한 PR을 머지한다. 머지 전 doc-gen으로 PR 요약을 생성해 컨펌받고 머지 방식(일반/스쿼시/리베이스)을 선택한다. '머지해줘', 'PR 머지', '#42 머지' 요청 시 사용."
allowed-tools: AskUserQuestion, Bash, Read, Skill
argument-hint: "[PR번호]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/merge.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# PR 머지

사용자가 검토·승인한 PR의 **그 HEAD**를 머지하고 원격 완료 상태를 확인한다. 요약 생성, 머지 방식 확인, remote merge, 로컬 동기화·브랜치 정리를 별도 상태로 보고한다. 이미 명시한 승인·방식은 반복해서 묻지 않는다.

## Step 1: PR·호스트 확인

실제 설치된 gh의 버전·인증·`--match-head-commit` 지원을 확인한다. 지원하지 않는 버전이면 pin 없이 머지하지 않는다. PR 번호/URL과 대상 저장소를 확정하고 모든 조회에 같은 PR URL을 사용한다. 숫자 없는 호출은 현재 브랜치에서 찾되 조회 실패와 PR 없음은 구분한다.

조회 필드:

```bash
gh pr view "{PR_URL}" --json id,number,url,title,state,isDraft,headRefName,headRefOid,baseRefName,baseRefOid,mergeable,autoMergeRequest,mergeCommit,additions,deletions,changedFiles
```

이미 MERGED면 mergeCommit을 확인해 보고한다. CLOSED는 머지하지 않는다. draft 해제는 요청 범위에 따라 예약한다. 충돌이면 해결 전 머지하지 않는다. UNKNOWN은 제한된 재조회 후 미확인으로 보고하며 성공으로 바꾸지 않는다.

## Step 2: 요약에 사용할 HEAD 고정

요약 **전** 조회 JSON을 실행별 파일 `{PR_BEFORE}`에 저장한다. helper `snapshot`의 결과를 `{REVIEWED}`에 저장하며 여기의 headRefOid/baseRefOid가 요약 입력이다.

```bash
python3 -I -B "{COMMON_ROOT}/skills/merge/assets/merge_state.py" snapshot --current "{PR_BEFORE}"
```

현재 설치된 common doc-gen으로 PR 요약을 만든다. 가능하면 고정 SHA 범위의 diff를 사용하고 제목에 PR URL/HEAD를 기록한다. PR#로 실시간 diff를 읽은 경우 **요약 직후 다시 조회**하여 아래 check-review를 통과해야 이 요약을 승인 대상으로 쓸 수 있다.

```bash
python3 -I -B "{COMMON_ROOT}/skills/merge/assets/merge_state.py" check-review --reviewed "{REVIEWED}" --current "{PR_AFTER_SUMMARY}"
```

요약 도중 HEAD/base가 바뀌면 요약을 새 snapshot에서 다시 만든다. 요약 후의 새 HEAD를 이전 요약의 reviewed 값에 덮어쓰지 않는다. 요약 실패는 직접 검토한 고정 diff와 사용자 지시가 있지 않은 한 머지 준비 미완료다.

## Step 3: 검토·방식 확정

고정 HEAD와 변경 요약, 문서 경로를 보여준다. 현재 HEAD에 대한 승인과 merge/squash/rebase 방식이 이미 명시됐으면 재질문하지 않는다. 필요한 경우에만 요약을 기준으로 승인·방식을 함께 확인한다. 취소하면 요약을 보존하고 종료한다. HEAD가 바뀌면 이전 승인을 새 코드에 적용하지 않는다.

## Step 4: pin으로 실행

1. PR을 다시 조회해 check-review를 통과시킨다. snapshot을 갱신해 검사를 우회하지 않는다.
2. 예약된 draft 해제를 수행한 경우에도 동일 HEAD인지 확인한다.
3. helper `command`로 argv를 구성하고 해당 인자 그대로 실행한다. helper 자체는 gh를 호출하지 않는다.

```bash
python3 -I -B "{COMMON_ROOT}/skills/merge/assets/merge_state.py" command --reviewed "{REVIEWED}" --current "{PR_LATEST}" --method "{merge|squash|rebase}"
```

결과는 `gh pr merge {PR_URL} --{method} --match-head-commit {REVIEWED_HEAD}`다. 조회와 실행 사이의 HEAD 변경도 GitHub의 match 검사가 거부한다. `--admin`으로 필수 규칙/queue를 우회하지 않는다. branch deletion은 아직 실행하지 않는다.

## Step 5: 원격 결과 판정

**명령 종료 코드가 0이든 아니든** 같은 PR을 다시 조회하고 결과를 helper에 전달한다. 원격 머지 성공 뒤 응답·로컬 작업만 실패할 수 있다. 조회가 실패하면 `UNKNOWN_REMOTE_STATE`로 보존하고 맹목적으로 merge를 재호출하지 않는다.

```bash
python3 -I -B "{COMMON_ROOT}/skills/merge/assets/merge_state.py" outcome --reviewed "{REVIEWED}" --current "{PR_AFTER_MERGE}" --command-exit "{MERGE_EXIT}"
```

| 원격 결과 | 처리 |
|-----------|------|
| MERGED + mergeCommit.oid 확인 + reviewed HEAD 일치 | 실제 머지 완료. **mergeCommit.oid**를 보고 |
| MERGED지만 다른 HEAD/base 또는 SHA 누락 | 차이/증거 부족 보고, 자동 삭제 안 함 |
| OPEN + autoMergeRequest | PENDING_AUTO_MERGE; 완료 아님 |
| OPEN, queue 근거 없음 | OPEN_UNCONFIRMED; queue 등록으로 추정하지 않음 |
| CLOSED | CLOSED_UNMERGED |
| 조회 실패 | UNKNOWN; 완료·미완료를 단정하지 않음 |

필수 merge queue에서는 exit 0이 대기 등록일 수 있다. 실제 queue 진입을 별도 API로 확인하지 않았다면 QUEUED라고 쓰지 않는다. 대기 상태는 원격 MERGED가 확인될 때까지 브랜치 삭제·완료 보고를 하지 않는다. 사용자가 대기 종료를 원하면 현재 상태와 PR URL을 보존한다.

## Step 6: 동기화·정리·보고

MERGED 확인 후에만 base를 fetch하고 필요하면 로컬 base를 ff-only로 갱신한다. dirty worktree·다른 worktree가 점유한 브랜치를 강제로 checkout/delete하지 않는다. 로컬 base가 이후 전진하더라도 이번 PR의 merge SHA는 Step 5 값으로 유지한다.

브랜치 삭제는 실제 소유 저장소·head 이름·현재 ref를 확인하고 실행한다. remote ref가 reviewed HEAD 이후 전진했으면 삭제하지 않는다. 원격 삭제는 조회한 ref OID에 대한 lease 조건을 사용하며, fork branch는 다른 저장소의 같은 이름과 구분한다. 로컬 삭제는 `-d`의 병합 확인을 유지하고 실패했다고 강제 삭제하지 않는다. 요청 범위에 없는 branch는 보존한다.

보고: PR URL·reviewed HEAD·원격 상태·mergeCommit SHA·사용한 방식·동기화 결과·실제 삭제 결과·요약 경로. remote merge가 성공했어도 로컬 동기화/삭제가 실패하면 각각 표시한다. 자기 임시 조회/명령 파일만 정리하고 요약은 보존한다.

공식 계약: [gh pr merge의 HEAD 조건·queue 동작](https://cli.github.com/manual/gh_pr_merge), [gh pr view JSON 필드](https://cli.github.com/manual/gh_pr_view).
