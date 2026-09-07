---
name: commit
description: "현재까지의 작업을 논리적 단위별로 나눠 컨벤션에 맞는 메시지로 순차 커밋한다. '커밋해줘', '작업 단위로 커밋', 변경사항을 정리해 커밋해야 할 때 사용."
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/commit.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Commit — 논리 단위 커밋

현재 변경사항을 논리적 작업 단위로 분류해 단위별로 순차 커밋한다.
**커밋 메시지 컨벤션의 canonical은 본 스킬이다** (commit-push, commit-pr, commit-hard-push가 이 절차를 위임받는다).

## Step 1: 변경사항 파악

`git rev-parse --show-toplevel`로 GIT_ROOT를 확정한다. 아래 모든 Git 명령은 `git -C "{GIT_ROOT}"`로 실행하고 소유 경로는 그 root 기준으로 전달한다. nested cwd에서 root-relative 경로에 cwd prefix를 다시 붙이지 않는다.

- `git status`로 staged/unstaged 변경사항 확인
- `git diff`와 `git diff --cached`로 파일별 변경 내용 파악

## Step 2: 논리 단위 분류

- 관련된 변경끼리 그룹화하고, 각 그룹이 하나의 완성된 기능/수정 단위가 되도록 구성한다 (기능 추가 / 버그 수정 / 리팩토링 / 문서 수정 등).
- **하나의 커밋은 하나의 책임(Single Responsibility)만 갖는다.** 관련 없는 변경은 별도 커밋으로 분리한다.

## Step 3: 단위별 순차 커밋

가장 핵심적인 변경부터, 각 단위별로:

1. 해당 그룹의 명시 경로만 스테이징한다. 변경 전 index와 작업 트리의 차이를 확인하고 사용자 부분 스테이징을 임의로 전체 파일로 덮지 않는다. 파일 전체를 그룹에 포함해도 되는 경우 `git -C "{GIT_ROOT}" add -- {관련 파일 인자들}`을 사용한다.
2. 메시지는 실행별 파일로 작성하고 `git -C "{GIT_ROOT}" --literal-pathspecs commit --only -F "{MESSAGE_FILE}" -- {관련 파일 인자들}`로 대상 파일을 제한한다. 기존 index에 무관한 파일이 있어도 이 커밋에 섞지 않는다. 부분 hunk만 커밋해야 하면 별도 임시 index를 사용하며 기존 index/working bytes를 보존한다.
3. 실제 새 커밋의 경로/트리와 계획한 그룹이 같은지 확인한다. hook이 범위를 바꾸었으면 원격 작업 전 보고·정리한다. 동일 파일을 여러 그룹으로 나누는 경우 --only가 작업 트리 전체 파일을 취한다는 점을 적용한다.

### 커밋 메시지 컨벤션

- 형식: `Prefix: 간략한 설명` — 설명과 본문은 한국어, Prefix는 영문 유지.
- 본문(선택): 변경 의도, 테스트 결과, 이슈 번호(예: `Refs: #123`)를 남긴다.

| Prefix | 사용 시점 |
|--------|----------|
| `Add` | 새로운 기능 또는 파일 추가 |
| `Fix` | 버그 수정 및 오류 해결 |
| `Del` | 불필요한 코드나 리소스 삭제 |
| `Refactor` | 기능 변화 없이 코드 구조 개선 |
| `Doc` | 문서(README, 위키, 주석 등) 수정 |
| `Test` | 테스트 코드 추가 또는 수정 |
| `Chore` | 빌드/설정/의존성 업데이트 등 잡무 처리 |
| `WIP` | 진행 중인 작업 임시 저장 — 리뷰 요청 전에 스쿼시하거나 정리한다 |

예: `Add: 로그인 페이지 UI 추가`, `Fix: 사용자 인증 로직 버그 수정`

## Step 4: 완료 확인

- `git log --oneline -10`으로 커밋 이력 확인
- `git status`로 남은 변경사항 확인. 의도하지 않은 변경이 남았으면 Step 2로 돌아가 분류를 재검토한다.

## 주의사항

- `.env`, credentials 등 민감한 파일은 커밋하지 않는다. staged에 포함되어 있으면 제외하고 사용자에게 알린다.
- 커밋 시 Claude Code의 서명을 남기지 않는다.
