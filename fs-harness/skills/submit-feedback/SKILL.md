---
name: submit-feedback
description: "프로젝트 워크플로우에서 수집된 fs-harness 피드백을 플러그인 레포(kangmomin/harness-plugins)의 community-feedback 영역에 PR로 제출한다. 실패 시 로컬 저장으로 fallback."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
argument-hint: "<보완점 항목 JSON> 또는 대화 컨텍스트에서 수집"
user-invocable: true
---

## Project Overrides

실행 전에 아래 파일이 있으면 Read로 확인:
- `.claude/fs-harness/common.md`
- `.claude/fs-harness/skills/submit-feedback.md`

상세 규약: 플러그인 루트 `OVERRIDES.md`.

---

# submit-feedback — 피드백을 플러그인 레포에 PR로 제출

`start-workflow` Phase 9 에서 수집된 **범용성 있는 보완점**을 플러그인 원본 레포의 `community-feedback/` 영역에 PR로 보낸다.

## 언제 쓰나

- 보완점이 "이 프로젝트만의 규칙"이 아니라 **다른 팀에도 도움이 될 범용 규칙**이라고 판단될 때
- 유저가 Phase 9 에서 "로컬 저장 + PR" 옵션을 선택했을 때 자동 호출됨
- 수동으로 단독 실행도 가능 (`/fs-harness:submit-feedback`)

## 언제 쓰지 말아야 하나

- 피드백이 프로젝트 특정 도메인/스택에만 의미 있을 때 → 로컬 오버라이드(`.claude/fs-harness/...`)만 쓰고 여기 오지 않음
- 사내 용어/시크릿/티켓 번호/내부 경로가 피드백에 포함된 경우 → 범용화 후 다시 시도

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## 사전 조건

| 항목 | 필요성 | 확인 방법 |
|------|--------|-----------|
| `gh` CLI 설치 | 필수 | `command -v gh` |
| `gh` 인증 | 필수 | `gh auth status` |
| `git` 설치 | 필수 | `command -v git` |
| 플러그인 `upstream.repo` | 필수 | `fs-harness/.claude-plugin/plugin.json` 읽기 |
| 네트워크 접근 | 필수 | 시도 후 판정 |

하나라도 누락되면 이 스킬은 `[SKIPPED:{사유}]` 를 반환하고 호출자(start-workflow)가 로컬 저장만 수행하도록 신호한다.

---

## 입력

호출자가 아래를 전달한다 (없으면 대화 이력에서 수집):

```
feedback_items:
  - target_type: skill | agent | common
    target_name: commit | workflow-implementer | ...
    summary: 한 줄 요약
    context: 어떤 작업에서 나왔는지 (범용 용어만)
    proposal: 구체적 변경/추가
    generality: "범용" | "특정 조건" | "프로젝트 한정"
    condition: (generality != 범용일 때) 적용 조건
```

`generality` 가 `"프로젝트 한정"` 인 항목은 PR 대상에서 제외하고 유저에게 그 이유와 함께 로컬 저장만 권고.

---

## 실행 절차

### Step 1: 사전 조건 점검 + Dry-run 요약

아래를 순차 실행하며 상태를 수집한다:

```bash
command -v gh && gh auth status 2>&1 | head -5
command -v git
```

`plugin.json` 의 `upstream.repo` 를 읽는다 (기본: `kangmomin/harness-plugins`). 
현재 gh 인증 사용자가 해당 repo 의 소유자와 같은지 확인:

```bash
GH_USER=$(gh api user --jq .login)
UPSTREAM_OWNER=$(echo "{upstream.repo}" | cut -d/ -f1)
# 같으면 self_owner=true (fork 불필요), 다르면 fork 필요
```

사용자에게 dry-run 요약을 보여준다:

```markdown
## PR 제출 계획

- 레포: kangmomin/harness-plugins
- 모드: {self-owner / fork}
- 추가할 파일:
  - fs-harness/community-feedback/skills/commit.md (+1 엔트리)
  - fs-harness/community-feedback/agents/workflow-implementer.md (+1 엔트리)
- 브랜치명: feedback/fs-harness/{YYYYMMDD}-{요약-kebab}
- PR 제목: "[fs-harness] feedback: {요약}"

### 제외된 항목 (프로젝트 한정)
- agent:scope-reviewer — "사내 티켓 참조 강제" (프로젝트 한정, 로컬에만 저장 권고)

진행할까요? (yes/no/edit)
```

`edit` 을 고르면 각 항목 제목/본문을 순차 수정할 수 있게 한다.

### Step 2: 피드백 본문 작성

각 `feedback_items` 에 대해, `community-feedback/{target_type}s/{target_name}.md` 에 append 할 섹션을 작성한다.

```markdown
## {YYYY-MM-DD}

**출처**: /fs-harness:start-workflow Phase 8 성찰
**대상**: {target_type}:{target_name}
**요지**: {summary}
**범용성**: {generality}{, 조건: condition 있으면}

### 컨텍스트
{context — 사내 용어·시크릿 제거됨을 확인}

### 제안
{proposal}
```

유저가 이전 Step 에서 `edit` 을 선택했으면 각 섹션을 보여주고 수정받는다.

### Step 3: fork/clone

#### Self-owner 모드 (gh 사용자 == upstream 소유자)

fork 불필요. 원본 레포를 임시 디렉토리에 clone:

```bash
WORK=$(mktemp -d -t harness-feedback-XXXX)
cd "$WORK"
gh repo clone {upstream.repo} . -- --depth 1 --branch {defaultBranch}
```

#### Fork 모드 (다른 사용자)

```bash
WORK=$(mktemp -d -t harness-feedback-XXXX)
cd "$WORK"
# fork (이미 있으면 --clone 으로 바로 clone)
gh repo fork {upstream.repo} --clone --remote --default-branch-only
cd harness-plugins
# upstream remote 는 gh fork 가 자동 추가
git fetch upstream {defaultBranch}
git checkout -b {branch} upstream/{defaultBranch}
```

### Step 4: 파일 append 및 커밋

```bash
BRANCH="feedback/fs-harness/$(date +%Y%m%d)-{요약-kebab}"
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"

# 각 feedback_item 에 대해 해당 파일에 append (없으면 생성)
# 파일 경로: fs-harness/community-feedback/{skills|agents|common}/{name}.md
# common 은 파일명 패턴: common/{YYYY-MM-DD}-{summary-kebab}.md (일자별 별도 파일)
```

append 규칙:

- 파일이 없으면 frontmatter 포함한 신규 생성:

  ```markdown
  ---
  target: {target_type}:{target_name}
  created: {YYYY-MM-DD}
  ---

  # Community Feedback: {target}
  ```

- 파일이 있으면 맨 아래에 Step 2 에서 작성한 섹션을 append
- 동일한 (날짜, target, summary) 조합이 이미 존재하면 중복이므로 건너뜀

커밋:

```bash
git add fs-harness/community-feedback/
git commit -m "Add: fs-harness 커뮤니티 피드백 추가: {요약}"
```

### Step 5: push + PR 생성

```bash
# self-owner: origin = upstream
# fork: origin = 유저의 fork
git push -u origin "$BRANCH"

gh pr create \
  --repo {upstream.repo} \
  --title "[fs-harness] feedback: {요약}" \
  --body "$(위 본문)" \
  --base {defaultBranch} \
  --head "{self-owner: $BRANCH / fork: $GH_USER:$BRANCH}"
```

PR 본문 템플릿:

```markdown
## Summary
fs-harness 사용 중 수집된 피드백 {N}건을 community-feedback 영역에 추가합니다.

## 추가된 항목
| 대상 | 요지 | 범용성 |
|------|------|--------|
| skill:commit | ... | 범용 |
| agent:workflow-implementer | ... | 특정 조건 |

## 출처
- 워크플로우: /fs-harness:start-workflow Phase 8 성찰 (자동 제출)

## 주의
- 원본 SKILL.md 는 변경하지 않습니다.
- 유지보수자 검토 후 범용 규칙으로 승격 여부를 결정합니다.

자동 생성: /fs-harness:submit-feedback
```

### Step 6: 결과 보고 + 임시 디렉토리 정리

```markdown
## PR 제출 완료

- PR: {PR URL}
- 추가된 파일: {목록}
- 제외된 항목: {프로젝트 한정으로 skip 된 항목 목록}

임시 작업 디렉토리 정리: {WORK} 삭제 완료
```

임시 디렉토리 삭제:

```bash
rm -rf "$WORK"
```

---

## 실패 처리 (fallback)

| 상황 | 처리 |
|------|------|
| `gh` 없음 | `[SKIPPED:NO_GH]` 반환. 설치 안내 출력 (`https://cli.github.com`) |
| `gh auth status` 실패 | `[SKIPPED:NO_AUTH]` 반환. `gh auth login` 안내 |
| fork/clone 네트워크 실패 | `[SKIPPED:NETWORK]` 반환 |
| push 실패 (권한/보호 브랜치) | 에러 로그 출력 + `[FAILED]` 반환 |
| gh pr create 실패 | push 는 이미 완료되었으므로 수동 PR 링크 안내 |
| 본 스킬 자체가 중단 | 임시 디렉토리는 가능한 정리. `WORK` 경로를 유저에게 알림 |

fallback 시 호출자(`start-workflow`)는 로컬 저장(`.claude/fs-harness/...`)만 수행하고 정상 종료. 워크플로우 전체를 실패로 만들지 않는다.

---

## 범용성 검토 가이드라인 (stay-in-community 판정)

이 스킬은 `generality` 필드로 범용성을 판단하지만, **모호하면 유저에게 확인**한다:

> "이 피드백이 사내 도메인/용어/티켓에 의존하지 않고 다른 팀에도 유용한가요?"
> - Yes → PR 대상
> - No → 로컬 전용 (.claude/fs-harness/... 에만 저장, PR 생략)
> - 모르겠음 → 로컬 전용으로 처리 (안전 기본값)

아래 단어가 본문에 있으면 **경고**한다:

- 사내 시스템명, 서비스명, 내부 패키지 경로 (예: `cloudKit.`, `errcode.WARN_*`)
- 티켓 번호 (`JIRA-XXX`, `#123`)
- 시크릿처럼 보이는 값
- 개인 이메일/Slack 채널

경고 시 유저에게 본문을 다시 보여주고 수정/삭제/건너뛰기를 받는다.

---

## 출력 형식

성공:
```
## submit-feedback 결과: SUCCESS
- PR: {URL}
- 파일: {N}개
- 제외: {M}건
```

스킵 (fallback):
```
## submit-feedback 결과: [SKIPPED:{사유}]
{사유 상세}
{호출자는 로컬 저장만 수행할 것}
```

실패:
```
## submit-feedback 결과: FAILED
{에러 요약}
{브랜치가 만들어졌다면 수동 PR 안내}
```
