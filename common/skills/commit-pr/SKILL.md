---
name: commit-pr
description: "커밋, 브랜치 생성, push, PR 오픈까지 전체 워크플로우를 수행한다. 'PR 올려줘', '커밋하고 PR까지', 'ready로 열어줘', 'version 올리고 PR 열어줘' 요청 시 사용. 기본은 draft PR이며 --ready로 ready 생성, --bump-only로 VERSION 범프 전용 PR을 만든다."
argument-hint: "[--ready] [--bump-only]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit-pr.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Commit & PR

브랜치 준비·논리 단위 커밋·Assumption Gate·push는 설치된 common commit-push/commit이 canonical이다. 이 스킬은 base·VERSION·기존 PR 재사용과 PR 생성을 연결한다. 위임 시 이미 확정한 브랜치·base·실행 소유 변경을 전달하고 같은 준비 질문을 반복하지 않는다.

## Flags

| 플래그 | 동작 |
|--------|------|
| 없음 | 논리 단위 커밋 → push → draft PR |
| --ready | 새 PR ready 또는 기존 draft ready 전환 |
| --bump-only | VERSION patch 변경만 새 커밋에 포함한 뒤 Gate → push → PR |

## Step 0: root·브랜치·base 확정

**VERSION 유무와 무관하게 가장 먼저 수행한다.**

1. Git root와 시작 브랜치·HEAD를 확인한다. 현재 index/작업 트리 및 실행 소유 경로를 보존한다. detached HEAD는 목적 브랜치가 결정되기 전 commit/push하지 않는다.
2. 현재 브랜치의 open PR을 조회한다. 인증/조회 오류와 “open PR 없음”을 구분한다. 오류를 새 PR 없음으로 간주하지 않는다.
3. commit-push Step 1로 최종 브랜치를 준비한다(기존 PR 브랜치는 유지). base 우선순위: 기존 PR baseRefName → 명시 사용자 base → 최종 prefix의 프로젝트 브랜치 모델 → 보호 브랜치에서 분기했다면 그 시작 브랜치 → profile mainBranch/원격 기본 브랜치. 서로 충돌하거나 후보가 여러 개면 해결 전 BLOCKED:BASE_UNRESOLVED다. feature의 push upstream을 부모 브랜치로 추정하지 않는다.
4. `{BASE_NAME}`(PR 목적 브랜치 이름)과 실제 ref `{BASE_REF}`를 기록한다. 원격 base를 사용하면 먼저 `git -C "{GIT_ROOT}" fetch origin "{BASE_NAME}"`의 종료 코드를 확인한다. fetch 실패 시 기존 ref 사용 여부와 stale 근거를 명시하며 base 자체가 없으면 중단한다.
5. 아래 읽기 전용 helper로 `{GIT_ROOT}`, `{BASE_SHA}`, root-relative VERSION 후보를 확정한다. 재명명으로 prefix가 달라지면 여기서 매핑을 다시 검증한다.

```bash
python3 -I -B "{COMMON_ROOT}/skills/commit/assets/git_checks.py" base --cwd "{CWD}" --base-ref "{BASE_REF}"
```

`version_path:null`은 base 미해결이 아니다. 두 VERSION 파일이 있으면 범프할 파일을 별도로 결정한다. root-relative 경로에 현재 디렉터리 prefix를 덧붙이지 않는다.

## Step 1: VERSION

- root의 VERSION 또는 VERSION.txt가 없으면 일반 실행은 `SKIPPED:NO_VERSION_FILE`로 계속한다. bump-only는 `BLOCKED:NO_VERSION_FILE`; 파일 생성이 요청되지 않았으면 임의 버전을 만들지 않는다.
- 기준 버전은 `git -C "{GIT_ROOT}" show "{BASE_SHA}:{VERSION_PATH}"`로 읽는다. local/base의 유효 semver 세 필드를 비교해 큰 값의 patch를 1 올린다.
- base에 VERSION이 없거나 내용이 semver가 아니면 그 원인을 명시한다. 일반 명령 오류를 “파일 없음”으로 숨기지 않는다. local 기준 범프를 쓰는 기존 fallback은 `version_base:local`과 미검증 이유를 보고하며, PR base 자체는 Step 0의 확정값을 유지한다.
- 기존 open PR도 base 버전이 전진해 재범프가 필요한지 확인한다. 추가 범프 뒤에는 새 커밋·새 HEAD Gate·push까지 다시 수행한다. 같은 버전을 가진 동시 PR 점유를 자동 회피했다고 주장하지 않는다.

## Step 2: 커밋과 Gate·push

일반 경로는 common commit의 논리 단위 커밋을 수행한다. 테스트 후 남은 소스 수정과 VERSION 변경을 빠뜨리지 않는다. 각 커밋의 실제 경로/트리를 확인하고, 사용자 소유의 무관한 staged/unstaged는 포함하지 않는다.

bump-only는 **VERSION만 명시한 --only 커밋**을 사용한다. `git add VERSION` 뒤 일반 commit은 기존 index 전체를 포함하므로 사용하지 않는다.

```bash
git -C "{GIT_ROOT}" add -- "{VERSION_PATH}"
git -C "{GIT_ROOT}" --literal-pathspecs commit --only -F "{COMMIT_MESSAGE_FILE}" -- "{VERSION_PATH}"
```

커밋 후 실제 변경 경로가 VERSION 하나인지, 무관한 index blob·작업 트리 내용이 보존됐는지 확인한다. hook이 범위를 바꿨으면 바로 보고하고 원격 작업 전에 정리한다. bump-only는 **새 커밋의 파일 범위**이며 현재 브랜치의 기존 미push 커밋까지 제거하는 옵션은 아니다. 기존 커밋이 있으면 push/PR 범위에 포함됨을 보고한다.

이후 commit-push Step 3의 Gate를 **현재 HEAD**로 수행하고 Step 4로 push한다. Gate 성공 뒤 VERSION·amend·rebase 등으로 HEAD가 바뀌면 Gate를 다시 실행한다. Git 오류/미해소 태그면 push/PR을 진행하지 않는다.

## Step 3: PR 생성 또는 갱신

1. 기존 open PR이면 같은 PR을 재사용한다. base가 Step 0의 값과 같은지 확인한다. 신규/보완 커밋의 최종 결과를 기준으로 제목·본문을 갱신하고, --ready 요청은 draft일 때만 반영한다.
2. 새 PR은 `{BASE_NAME}`을 반드시 전달한다. 본문은 실제 줄바꿈이 있는 실행별 임시 파일로 작성한다. 요약·주요 변경·실제 검증/미검증·확정된 결정만 포함한다.

```bash
gh pr create --draft --title "{TITLE}" --body-file "{PR_BODY_FILE}" --base "{BASE_NAME}"
```

--ready이면 --draft만 생략한다. 태그를 본문에 재삽입하지 않는다. 생성/갱신 후 PR의 head SHA·base·URL을 조회해 의도한 브랜치와 일치하는지 확인한다. 실제 실패/차단을 DONE으로 보고하지 않는다. 전송 실패 시 커밋/push/PR 중 어디까지 완료됐는지 각각 보고하고 이미 생성된 PR이 있는지 조회 후 재시도한다.

## 보고

브랜치·base 이름/SHA·생성 커밋·push HEAD·PR URL·검증 결과와 상태를 보고한다. 자신의 메시지/본문 임시 파일만 정리한다. `BLOCKED:GIT_CHECK`, `BLOCKED:BASE_UNRESOLVED`, `BLOCKED:ASSUMPTION_UNRESOLVED`는 원격 작업 미완료 상태다.
