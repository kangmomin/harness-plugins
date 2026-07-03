---
name: commit-pr
description: "커밋, 브랜치 생성, push, PR 오픈까지 전체 워크플로우를 수행한다. 'PR 올려줘', '커밋하고 PR까지', 'ready로 열어줘', 'version 올리고 PR 열어줘' 요청 시 사용. 기본은 draft PR이며 --ready로 ready 생성, --bump-only로 VERSION 범프 전용 PR을 만든다."
argument-hint: "[--ready] [--bump-only]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit-pr.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Commit & PR

커밋부터 PR 오픈까지 수행한다.
브랜치 판정·명명·커밋·push는 `/common:commit-push`가 canonical이며, 본 스킬은 그 앞뒤(기존 PR 확인, VERSION 갱신, PR 생성)만 정의한다.

## Flags

| 플래그 | 효과 |
|--------|------|
| `--ready` | PR을 draft가 아닌 ready 상태로 생성한다. 기존 open PR이 draft면 `gh pr ready`로 전환한다 |
| `--bump-only` | 코드 변경 커밋 없이 VERSION patch 범프만 커밋→push→PR 한다. VERSION 변경이 배포 트리거인 프로젝트의 배포용 PR 원커맨드. `--ready`와 조합 가능 |

플래그가 없으면 현행과 동일하게 동작한다 (전체 변경 커밋 + draft PR).
`--bump-only`는 Step 1~4 대신 하단 **Bump-Only 절차**를 수행한다.

## Step 1: 기존 PR 확인

```bash
gh pr view --json number,state,url,isDraft,baseRefName
```

현재 브랜치에 이미 열린 PR이 있으면 아래를 수행하고 종료한다 (기존 PR에 커밋이 추가됨):

1. `/common:commit-push` 절차를 수행한다.
2. `--ready`이고 해당 PR이 draft면 `gh pr ready {번호}`로 전환한다.
3. **본문 동기화 확인**: 이번에 추가된 논리 단위 커밋 중 PR 본문에 반영되지 않은 항목(커밋 제목 대조)이 있으면 선택지를 제시한다. 본문이 이미 정합하면 이 단계는 조용히 통과한다.
   > 1. PR 본문 갱신 — 추가분 요약을 보여준 뒤 반영
   > 2. 그대로 두기
4. **VERSION 재범프 확인**: 로컬 VERSION 버전 ≤ `origin/{PR의 baseRefName}` 의 VERSION 버전이면 (base가 먼저 전진한 경우) 선택지를 제시한다:
   > 1. patch 재범프 커밋 추가 후 push
   > 2. 그대로 두기 — 머지 시 수동 해결

## Step 2: VERSION 갱신

프로젝트 루트의 `VERSION` 또는 `VERSION.txt`가 대상이다. 없으면 건너뛴다 (`SKIPPED:NO_VERSION_FILE`).

1. **base 결정 (1회)**: 오버라이드에 브랜치 모델(prefix → 허용 base 표, `/common:commit-push`의 "브랜치 모델" 섹션 참조)이 선언돼 있으면 현재 브랜치 prefix에 매핑된 base, 없으면 현재 브랜치의 바로 상위 브랜치. **여기서 결정한 base를 Step 4의 PR base로 재사용한다** (이원화 금지). 보호 브랜치에서 시작해 Step 3에서 새 브랜치가 생성되는 경우에는 시작 시점의 그 브랜치(분기 원점)가 base다.
2. base의 버전을 조회한다:
   ```bash
   git fetch origin {base} --quiet
   git show origin/{base}:$(git rev-parse --show-prefix){VERSION파일}
   ```
3. `max(base 버전, 로컬 버전)` 기준 patch +1 로 범프해 이번 커밋에 포함한다 (semver 3필드 비교 — 병렬 브랜치가 이미 점유한 버전을 자동 회피).
4. 조회 실패(오프라인, origin/base 부재) 또는 semver 파싱 실패 시: 로컬 기준 patch +1 로 폴백하고 고지한다 — "base 버전 확인 불가 — 로컬 기준 범프. 머지 시 충돌 가능".

> 한계: 이 절차는 base가 이미 전진한 경우의 충돌을 막는다. 머지 전 동시 오픈 PR들끼리의 동일 버전 점유는 남으며, 한쪽이 먼저 머지된 뒤 다른 PR의 Step 1-4 재범프로 해소한다.

## Step 3: 커밋 + Push

`/common:commit-push` 절차를 수행한다.
보호 브랜치에서의 새 브랜치 생성, `worktree-*` 등 컨벤션 불일치 브랜치의 이름 재생성, 논리 단위 커밋, push가 모두 여기에 포함된다.

## Step 4: PR 생성

1. 변경사항을 분석해 PR 제목과 본문을 작성한다.
   - 제목: 커밋 메시지 컨벤션과 동일한 `Prefix: 한국어 설명` 형식
   - 본문: 변경 요약, 주요 변경 파일, 테스트/검증 결과
2. base는 Step 2에서 결정한 값을 사용한다.
3. **브랜치 모델 조합 검증** (오버라이드 선언 시): `{현재 브랜치 prefix} → {base}` 조합이 선언된 모델과 다르면 선택지를 제시한다. 모델에 없는 prefix면 현행 규칙(바로 상위 브랜치)으로 폴백하고 경고만 남긴다.
   > 1. 허용 base로 변경해 PR 생성
   > 2. 브랜치 재생성 후 재시도 (Step 3 재수행)
   > 3. 그대로 진행 — 위반 사유를 PR 본문에 기록
4. PR을 연다 (기본 draft, `--ready`면 `--draft` 생략):
   ```bash
   gh pr create --draft --title "{제목}" --body "{본문}" --base {base}
   ```
5. 생성된 PR URL을 보고한다.

실패 시 (gh 미인증, 권한 부족 등): 에러 원문을 보고하고 선택지를 제시한다.
> 1. 안내된 조치(예: `gh auth login`) 후 Step 4 재시도
> 2. 중단 — 커밋과 push는 완료된 상태로 종료

## Bump-Only 절차 (`--bump-only`)

Step 1의 단락 규칙을 적용하지 않는다 — open PR이 있어도 범프 자체가 목적이므로 아래를 수행한다. Step 1-3(본문 동기화 확인)도 이 경로에는 적용하지 않는다.

1. VERSION 파일(`VERSION` 또는 `VERSION.txt`)이 없으면 `BLOCKED:NO_VERSION_FILE` 보고 후 선택지를 제시한다:
   > 1. `0.1.0`으로 새로 생성하고 진행
   > 2. 중단
2. `/common:commit-push`의 **Step 1(브랜치 판정)만** 수행한다 — 보호 브랜치면 새 브랜치 생성.
3. Step 2 절차로 범프하되 **VERSION 파일만 스테이징해 단독 커밋**한다 (`git add {VERSION파일}` 한정 — 작업 트리의 다른 변경은 건드리지 않는다).
4. `/common:commit-push`의 Step 3(push)을 수행한다.
5. PR: open PR이 없으면 Step 4로 생성한다 (`--ready` 반영). 이미 있으면 생성은 생략하고, `--ready`+draft면 `gh pr ready {번호}`만 수행한다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | PR 생성(또는 기존 PR 갱신) 완료 |
| `SKIPPED:NO_VERSION_FILE` | VERSION 파일 없음 — 범프 생략 (일반 경로) |
| `BLOCKED:NO_VERSION_FILE` | `--bump-only`인데 VERSION 파일 없음 — 사용자 선택 대기 |
