---
name: resolve-assumption
description: "코드·커밋 메시지에 남은 `[Assumption]` 추론 태그를 항목별로 하나씩 확인받아 해소한다. 'assumption 해소해줘', '추론 태그 정리해줘', '가정한 것들 확인해줘', push 전에 미리 태그를 정리하고 싶을 때 사용. 승인된 항목은 태그만 삭제하며 '확정' 같은 대체 워딩을 남기지 않는다."
user-invocable: true
allowed-tools: Bash, Read, Edit, Grep, Glob, AskUserQuestion, Skill
argument-hint: "[경로|--worktree|--branch|--commits]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/resolve-assumption.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Resolve Assumption

`[Assumption]` 태그를 **항목별로 하나씩** 사용자 확인을 받아 해소한다.

`/common:commit-push` Step 3(Assumption Gate)이 push 직전의 **하드 게이트**라면, 본 스킬은 개발 도중 아무 때나 돌릴 수 있는 **해소 도구**다. 게이트가 아니므로 보류를 허용하고 push/PR을 트리거하지 않는다.

> **canonical 관계**: 태그 스캔 범위와 제거 규칙의 canonical은 `/common:commit-push` Step 3이다. 본 스킬은 그 규칙을 따르되, 작업 트리(uncommitted) 스캔과 항목별 순차 처리를 더한다. 규칙이 갈리면 canonical이 우선한다.

## 핵심 원칙

**승인된 추측은 태그만 지운다.** `[확정]`·`(확정)`·`// 확인됨` 같은 **대체 마커를 남기지 않는다** — 태그가 있던 자리에 다른 워딩을 채워 넣는 순간 그 흔적이 다시 리뷰 대상이 된다. 검토 이력은 코드가 아니라 최종 보고(Step 5)에 남긴다.

## Step 1: 범위 결정

| 인자 | 스캔 범위 |
|------|----------|
| 없음 (기본) | 작업 트리 + 브랜치 diff + 미push 커밋 메시지 |
| `--worktree` | 작업 트리(uncommitted)만 |
| `--branch` | 브랜치 diff(`{base}...HEAD`) 추가 라인만 |
| `--commits` | 미push 커밋 메시지만 |
| 경로/glob | 해당 경로에 한정 (커밋 메시지 스캔은 생략) |

`{base}`는 알려진 값이 있으면 재사용한다 — 기존 open PR의 `baseRefName`, 직전 `/common:commit-pr`에서 결정한 base. 없으면 `@{upstream}`, 그것도 없으면 기본 브랜치(`origin/HEAD`)와의 merge-base.

## Step 2: 스캔

```bash
# ① 작업 트리 — 추적 파일의 미커밋 추가 라인
git diff HEAD -- {경로} | grep -n '^+.*\[Assumption\]'
# ② 작업 트리 — untracked 파일
git ls-files --others --exclude-standard -z | xargs -0 -r grep -HnI '\[Assumption\]'
# ③ 브랜치 diff — 이 브랜치가 추가한 라인
git diff {base}...HEAD -- {경로} | grep -n '^+.*\[Assumption\]'
# ④ 커밋 메시지 — 미push 커밋 본문 (upstream 없으면 {base}..HEAD)
git log @{upstream}..HEAD --format='%h %s%n%b' | grep -B1 '\[Assumption\]'
```

- diff 출력의 `+` 라인만 대상이다 — **브랜치가 만들지 않은 레거시 태그는 건드리지 않는다**(surgical 원칙).
- ①과 ③은 겹칠 수 있다. 같은 `파일:라인`은 **1건으로 합쳐** 중복 제시하지 않는다.
- 이미 push된 커밋 메시지의 태그는 재작성 불가(force-push 금지)이므로 **WARN으로 보고만** 하고 처리 대상에서 제외한다.
- **0건이면** "해소할 `[Assumption]`이 없습니다"만 보고하고 종료한다(`DONE`).

발견 시 전체 목록을 먼저 한 번 보여준다 — 몇 건을 몇 단계에 걸쳐 처리하는지 사용자가 알아야 한다.

```
[Assumption] 3건 발견 — 항목별로 확인합니다.
1. internal/order/service.go:142 — 결제 취소 시 재고 즉시 복원
2. internal/order/repo.go:88 — status='ACTIVE'만 조회 대상
3. 커밋 a1b2c3d — "Fix: 주문 취소 처리"
```

## Step 3: 항목별 해소 (1건씩)

목록의 각 항목을 **순서대로 하나씩** 처리한다. 한 항목이 끝나기 전에 다음 항목으로 넘어가지 않는다.

항목마다 다음을 제시한다:

> **[{i}/{N}] `{파일:라인}`** (또는 `커밋 {해시}`)
> 추측 내용: "{태그에 적힌 추측}"
> 주변 맥락: {해당 코드가 무엇을 하는지 1~2줄}
>
> 1. **승인** — 추측이 맞음. 태그를 제거한다
> 2. **수정** — 추측이 틀림. 지시한 방향으로 코드를 고치고 태그를 제거한다
> 3. **보류** — 아직 판단 불가. 태그를 그대로 두고 다음 항목으로
> 4. **중단** — 남은 항목을 처리하지 않고 종료

선택에 따른 처리:

| 선택 | 처리 |
|------|------|
| 승인 | Step 4의 제거 규칙 적용. 확정된 결정 목록에 기록 |
| 수정 | 사용자 지시대로 코드 수정 → 태그 제거. 확정된 결정 목록에 **수정된 내용**으로 기록 |
| 보류 | 아무것도 바꾸지 않는다. 보류 목록에 기록 |
| 중단 | 즉시 Step 5로 이동. 남은 항목은 미처리로 보고 |

**한 항목의 처리를 끝낸 뒤 다음 항목으로 넘어간다** — 여러 항목을 모아 일괄 확인받지 않는다. 사용자가 명시적으로 "나머지 전부 승인"이라고 하면 그때만 일괄 처리한다.

## Step 4: 태그 제거 규칙

### 코드 주석

`[Assumption]` 마커만 지운다. **대체 워딩을 넣지 않는다.**

| 상황 | 처리 |
|------|------|
| 주석의 설명이 코드 이해에 필요 | 마커만 떼고 태그 없는 일반 주석으로 남긴다 |
| 주석이 태그를 달기 위해서만 존재 | 주석 라인 전체를 삭제한다 |
| 코드 라인 끝의 인라인 태그 | 태그 부분만 잘라낸다. 남은 주석이 빈 `//`가 되면 함께 지운다 |

```go
// 변경 전
// [Assumption] 결제 취소 시 재고를 즉시 복원한다고 가정
restoreStock(ctx, order.Items)

// 승인 후 — 설명이 유용한 경우
// 결제 취소 시 재고를 즉시 복원한다
restoreStock(ctx, order.Items)

// 승인 후 — 설명이 불필요한 경우
restoreStock(ctx, order.Items)
```

금지 예시 — 아래 중 어느 것도 만들지 않는다:

```go
// [확정] 결제 취소 시 재고를 즉시 복원한다   ← 금지
// (확정) 결제 취소 시 재고를 즉시 복원한다   ← 금지
// [Assumption→확인됨] ...                    ← 금지
```

### 커밋 메시지 (미push 한정)

| 대상 | 처리 |
|------|------|
| 마지막 커밋 | `git commit --amend`로 본문에서 태그 라인 제거 |
| 그 이전 커밋 | `git reset --soft {범위 시작}` 후 `/common:commit` 절차로 재커밋 |
| 이미 push된 커밋 | 건드리지 않는다 (WARN 보고만) |

### 변경 커밋

태그 제거·코드 수정으로 발생한 변경은 관련 논리 단위 커밋에 amend하거나, 별도로 묶어 `Chore: 확인된 Assumption 태그 정리`로 커밋한다. **커밋 여부는 사용자에게 확인받는다** — 본 스킬은 push하지 않는다.

## Step 5: 보고

```markdown
## Assumption 해소 결과

- 발견: {N}건 / 승인 {a}건 · 수정 {b}건 · 보류 {c}건 · 미처리 {d}건

### 확정된 결정
- `{파일:라인}` — {확정된 동작}
- `{파일:라인}` — {수정 후 동작} (기존 추측: {틀렸던 내용})

### 보류
- `{파일:라인}` — {추측 내용} · 태그 유지

### WARN
- 이미 push된 커밋 `{해시}`에 태그 잔존 — 재작성 불가

### 상태: {DONE | PARTIAL | ABORTED}
```

| 상태 | 조건 |
|------|------|
| `DONE` | 처리 대상 태그 0건 잔존 |
| `PARTIAL` | 보류 항목이 남음 |
| `ABORTED` | 사용자가 중단을 선택 |

### 확정된 결정을 어디로 옮기는가

`convention-check`는 `[Assumption]` 태그 없는 유추 변경을 위반으로 잡되, **PR 본문 또는 워크플로우 보고서의 "확정된 결정" 섹션에 기록되어 있으면 통과**시킨다. 본 스킬로 push 전에 태그를 미리 지우면 이후 Assumption Gate는 0건으로 조용히 통과하므로, 승인 항목이 PR 본문에 자동으로 실리지 않는다.

→ 보고 후 다음을 안내한다: **"이후 `/common:commit-pr`로 PR을 열 때 위 '확정된 결정' 목록을 PR 본문의 `### 확정된 결정` 섹션에 옮기세요."**

코드에는 어떤 확정 워딩도 남기지 않되, 검토 이력은 PR 본문에서 살아남는다.

## 하지 않는 것

- push·PR 생성 (`/common:commit-push`, `/common:commit-pr`의 역할)
- 브랜치 diff 밖의 레거시 태그 정리 (surgical 원칙)
- 이미 push된 커밋의 메시지 재작성 (force-push 금지)
- 보류 항목을 이유로 한 차단 — 게이트가 아니다
