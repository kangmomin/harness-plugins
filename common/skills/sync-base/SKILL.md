---
name: sync-base
description: "base 브랜치를 현재 브랜치로 merge 해 최신화하고, VERSION 파일이 있으면 patch 범프와 swagger(OpenAPI) version 동기화까지 수행한 뒤 push 한다. 'base 최신화해줘', 'dev 머지해와', '최신화하고 버전 올려줘', '충돌 나기 전에 base 당겨줘' 요청 시 사용."
allowed-tools: AskUserQuestion, Bash, Read, Edit, Glob, Skill
argument-hint: "[base브랜치]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/sync-base.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# /common:sync-base — base 최신화 + 버전 범프

base 브랜치를 **현재 브랜치로** merge 하고(base → here), VERSION 이 있으면 범프하며 swagger version 을 같은 값으로 맞춘 뒤 push 한다.

`/common:merge`(here → base, PR 머지)의 **역방향**이다. 혼동하지 않는다.

## 핵심 원칙

- **base 결정과 버전 계산 규칙은 `/common:commit-pr`와 동일** — 이원화하지 않는다. base 는 브랜치 모델이 최우선이고, 버전은 `max(base, 로컬) + patch 1` 이다.
- **push 는 Assumption Gate 를 거쳐서만 한다** — `/common:commit-push`의 Step 3·4를 위임 호출한다. Gate 를 우회해 직접 `git push` 하지 않는다.
- **merge 커밋과 범프 커밋을 분리한다** — 충돌을 해결할 때도 merge 커밋에는 범프하지 않은 잠정값만 담는다.
- **버전 파일 외의 충돌은 자동 해결하지 않는다** — 사용자에게 넘기고, 재실행하면 이어서 진행한다.
- **swagger version 은 VERSION 과 락스텝** — 독립 범프가 아니라 확정된 VERSION 문자열을 그대로 기입한다.

## 실행 순서 개요

```
1 브랜치 검증 → 2 base 결정 → 3 버전 대상 탐색 → 4 merge(또는 재개)
  → 5 충돌 처리 + merge 커밋 → 6 확정 버전 계산 → 7 파일 갱신 + 범프 커밋 → 8 push → 9 보고
```

버전 대상 파일을 merge 보다 **먼저** 확정한다 — Step 5의 충돌 분류가 이 목록을 필요로 한다.

## Step 1: 브랜치 검증

```bash
git branch --show-current
```

| 상태 | 행동 |
|------|------|
| 비어 있음 (detached HEAD) | "detached HEAD 상태입니다. 브랜치를 체크아웃한 뒤 다시 실행하세요." 보고 후 종료 (`BLOCKED:DETACHED_HEAD`) |
| 보호 브랜치 (`main`·`master`·`dev`·`rc*`) | "보호 브랜치에서는 실행하지 않습니다. 작업 브랜치로 이동 후 다시 실행하세요." 보고 후 종료 (`BLOCKED:ON_BASE`) |

작업 트리 검사는 여기서 하지 않는다 — 재개 경로(Step 4.1)에서는 충돌 해결 결과가 작업 트리에 있는 것이 정상이므로, 재개 여부를 판정한 뒤에 검사한다.

## Step 2: base 결정

### Step 2.1: 우선순위

`/common:commit-pr` Step 2의 base 결정 규칙을 그대로 따르되, 사용자 인자를 최상위 override 로 둔다.

1. **`$ARGUMENTS`에 브랜치명이 있으면 그 값** — 사용자 명시 override
2. **오버라이드 `.claude/common/common.md`의 브랜치 모델 표**에서 현재 브랜치 prefix 에 매핑된 base (선언돼 있으면 이 값이 확정이다)
3. **현재 브랜치의 open PR** — `gh pr view --json baseRefName`. 브랜치 모델 미선언 시 "바로 상위 브랜치"의 근거로 사용한다. gh 미설치·미인증·PR 없음이면 조용히 다음으로
4. **기본 브랜치** — `git symbolic-ref -q --short refs/remotes/origin/HEAD` 의 `origin/` 뒤 부분

> 브랜치 모델이 선언된 프로젝트에서 open PR 의 base 가 모델과 다르면, 모델 값을 쓰고 그 사실을 경고로 남긴다 — PR base 가 선언된 모델을 덮어쓰지 않는다.

4까지 실패하면 `AskUserQuestion` 으로 묻는다:
> base 브랜치를 결정하지 못했습니다.
> 1. `main` 사용
> 2. `dev` 사용
> 3. 직접 입력 — 입력값은 `git rev-parse --verify origin/{입력}` 으로 존재를 확인하고, 실패하면 1회 재질문
> 4. 중단 (`BLOCKED:NO_BASE`)

### Step 2.2: 현재 브랜치 대조

현재 브랜치 == `{base}` 이면 "현재 브랜치가 base 입니다. 최신화는 `git pull` 로 충분합니다." 보고 후 종료 (`BLOCKED:ON_BASE`).

### Step 2.3: fetch

```bash
git fetch origin {base}
```

실패(원격 없음·네트워크·브랜치 부재) 시 에러 원문을 보고하고 종료한다 (`BLOCKED:FETCH_FAILED`). 로컬 `{base}` 로 폴백하지 않는다 — 최신화가 목적인데 낡은 로컬 ref 를 병합하면 목적에 반한다.

### Step 2.4: 가져올 커밋 수 기록

```bash
git rev-list --count HEAD..origin/{base}
```

merge **전에** 재둔다 — merge 후에 세면 merge 커밋·범프 커밋이 섞여 들어간다. 0이면 base 가 앞서 있지 않다는 뜻이며, 그래도 Step 3 이후를 계속 수행한다.

## Step 3: 버전 대상 탐색

### Step 3.1: VERSION 파일

저장소 루트의 `VERSION` 또는 `VERSION.txt`. 둘 다 없으면 `SKIPPED:NO_VERSION_FILE` 로 기록한다 — 이 경우 **버전 관련 단계를 모두 생략**하고, 충돌 분류에서도 swagger 를 자동 해결 대상으로 보지 않는다 (락스텝의 기준값이 없으므로). merge 와 push 는 그대로 진행한다.

### Step 3.2: swagger 대상 집합

1. 오버라이드 `.claude/common/skills/sync-base.md` 에 `swaggerVersionFiles` 목록이 선언돼 있으면 그 경로를 대상으로 한다.
2. 선언이 없으면 아래를 탐색한다 (`.git`·`node_modules`·`vendor` 제외):

| 경로 패턴 | 갱신 지점 |
|-----------|-----------|
| `docs/swagger.json`, `openapi.json`, `swagger.json` | `info.version` |
| `docs/swagger.yaml`, `docs/swagger.yml`, `openapi.yaml`, `openapi.yml` | `info.version` |
| `docs/docs.go` (Go swag 생성물) | `SwaggerInfo.Version` |
| `*.go` 의 `// @version` 어노테이션 | 어노테이션 값 |

**Go swag 보정**: 오버라이드가 `docs/docs.go`·`docs/swagger.json`·`docs/swagger.yaml` 중 일부만 지정했더라도, 나머지 파일이 실제로 존재하면 대상 집합에 포함한다 — 세 파일은 함께 생성되므로 하나만 고치면 서로 어긋난다.

0건이면 `SKIPPED:NO_SWAGGER` 로 기록하고 계속 진행한다 (경고가 아니다 — swagger 를 쓰지 않는 프로젝트가 정상 경로다).

> `docs/docs.go` 같은 생성물을 손으로 고치는 것이 프로젝트 정책에 어긋나면(예: `swag init` 재생성이 원칙), 오버라이드에 재생성 커맨드를 선언해 Step 7.2를 치환한다.

여기서 확정한 집합을 **버전 대상 집합**이라 부르고 이후 단계에서 재사용한다.

## Step 4: merge

### Step 4.1: 재개 판정

먼저 **merge 가 아닌 다른 작업이 진행 중인지** 배제한다 — rebase 는 충돌 중에도 `MERGE_HEAD` 를 노출할 수 있고, cherry-pick 은 `MERGE_HEAD` 없이 충돌만 남긴다:

```bash
ls .git/rebase-merge .git/rebase-apply 2>/dev/null
git rev-parse -q --verify CHERRY_PICK_HEAD
git rev-parse -q --verify REVERT_HEAD
```

하나라도 걸리면 merge 로 착각하지 않고 종료한다 (`BLOCKED:OTHER_OP_IN_PROGRESS`) — "rebase/cherry-pick/revert 가 진행 중입니다. 마무리하거나 중단(`--abort`)한 뒤 다시 실행하세요."

```bash
git rev-parse -q --verify MERGE_HEAD
```

`MERGE_HEAD` 가 있으면 이전 실행이 남긴 merge 다.

1. 이 merge 가 `{base}` 에서 온 것인지 확인한다 — **동일성이 아니라 조상 관계로** 판정한다. Step 2.3이 방금 fetch 했으므로, 사용자가 충돌을 해결하는 사이 base 가 더 전진했으면 `MERGE_HEAD ≠ origin/{base}` 가 되는 것이 정상이다:
   ```bash
   git merge-base --is-ancestor MERGE_HEAD origin/{base}
   ```
   - **성공(조상)** — 같은 base 계열이다. `MERGE_HEAD` 와 `origin/{base}` 가 다르면 "base 가 더 전진했습니다 — 이번 실행을 마친 뒤 한 번 더 실행하는 것을 권장합니다" 를 경고로 남기고 계속한다. 진행 중인 merge 를 abort 하라고 안내하지 않는다 (사용자의 충돌 해결 결과가 사라진다).
   - **실패(무관)** — 다른 merge 가 진행 중이다. 보고 후 종료한다 (`BLOCKED:FOREIGN_MERGE`) — "진행 중인 다른 merge 가 있습니다. 마무리하거나 `git merge --abort` 후 다시 실행하세요."
2. `git diff --name-only --diff-filter=U` 로 남은 충돌을 확인하고 **Step 5로 진행**한다 (충돌 0건이어도 Step 5.4가 merge 를 마무리해야 하므로 Step 5를 건너뛰지 않는다).

`MERGE_HEAD` 가 없으면 Step 4.2로 진행한다.

### Step 4.2: 작업 트리 검증 (재개가 아닐 때만)

```bash
git status --porcelain
```

변경사항이 있으면 `AskUserQuestion`:
> 1. `/common:commit` 으로 커밋 후 진행
> 2. `git stash` 후 진행 — 완료 시 `git stash pop` 을 안내한다
> 3. 중단 (`BLOCKED:DIRTY_TREE`)

### Step 4.3: merge 실행

```bash
git merge --no-ff origin/{base}
```

`--no-ff` 로 고정한다 — 이 스킬은 항상 "base 를 가져온" 지점을 이력에 남긴다. rebase 는 쓰지 않는다 (이미 push 된 브랜치의 이력을 다시 쓰지 않기 위함).

| 결과 | 행동 |
|------|------|
| `Already up to date.` | merge 커밋 없음. Step 5는 통과하고 Step 6은 계속 수행한다 — base 가 앞서 있지 않아도 로컬 VERSION 이 base 와 같으면 범프 대상이다 |
| 성공 | Step 5로 진행 |
| 충돌 | Step 5로 진행 |
| 그 외 실패 (index lock, 손상 등) | 에러 원문 보고 후 종료 (`BLOCKED:MERGE_FAILED`) |

## Step 5: 충돌 처리

```bash
git diff --name-only --diff-filter=U
```

### Step 5.1: 분류

0건이면 분류·해결을 건너뛰고 **Step 5.4**로 간다 (Step 6이 아니다 — 재개 경로에서는 아직 merge 가 커밋되지 않았을 수 있다). 충돌 파일마다:

| 파일 | 분류 |
|------|------|
| Step 3.1의 VERSION 파일 | **버전 충돌** |
| Step 3.2의 버전 대상 집합에 속하고, 충돌 헌크 내부가 전부 version 라인 | **버전 충돌** |
| 그 외 | **일반 충돌** |

충돌 헌크 **내부 라인만** 추출해 판정한다. 스테이지 전체(`:2:`/`:3:`)를 비교하지 않는다 — git 이 version 라인만 남기고 나머지를 이미 병합했을 수 있고, 그 경우 전체 비교는 자동 해결 가능한 건을 일반 충돌로 오분류한다:

```bash
awk '/^<<<<<<< /{i=1;next} /^=======$/{i=2;next} /^>>>>>>> /{i=0;next} i' {파일}
```

판정은 **그 파일에 배정된 Step 3.2의 대상 필드**로만 한다 — `info.version` / `SwaggerInfo.Version` / `// @version` 중 해당 파일의 것. `version` 이 들어간 아무 라인이나 받아주지 않는다: Go 파일의 다른 `Version:` 구조체 필드, YAML 의 `apiVersion:`·`openapi:` 같은 라인이 함께 충돌한 경우를 버전 충돌로 오분류하기 때문이다.

버전 충돌로 인정하는 조건은 둘 다 만족할 때다:
- 헌크 내부 ours 쪽과 theirs 쪽에 **대상 필드 라인이 각각 정확히 1줄**씩 있다
- 헌크 내부에 그 두 줄 **외의 라인이 없다**

하나라도 어긋나면 일반 충돌로 분류한다.
Step 3.1이 `SKIPPED:NO_VERSION_FILE` 이면 swagger 충돌도 일반 충돌로 다룬다 — 기입할 기준값이 없다.

### Step 5.2: 일반 충돌이 하나라도 있으면 중단

merge 를 **되돌리지 않고 그대로 둔 채** 보고하고 종료한다 (`BLOCKED:CONFLICT`):

```
⚠️ 자동 해결할 수 없는 충돌이 있습니다. merge 는 진행 중 상태로 두었습니다.
- 충돌 파일: {목록}
해결 후 `git add {파일}` 하고 `/common:sync-base` 를 다시 실행하면
남은 충돌 해결과 버전 범프부터 이어서 진행합니다. 되돌리려면 `git merge --abort`.
```

`git commit` 은 안내하지 않는다 — 재실행 시 Step 4.1이 merge 를 이어받아 마무리한다.

### Step 5.3: 버전 충돌 자동 해결 (잠정값)

**범프하지 않은 잠정값**으로 해결한다. 범프는 Step 6에서 한 번만 한다 — merge 커밋에 범프를 섞지 않기 위함이다.

1. 각 버전 충돌 파일의 양쪽 값을 읽는다:
   ```bash
   git show :2:{파일}   # ours — 현재 브랜치
   git show :3:{파일}   # theirs — base
   ```
2. **잠정값은 저장소 전체에 하나뿐이며, VERSION 파일에서만 유도한다** — swagger 파일별로 따로 계산하지 않는다:
   - VERSION 파일이 충돌했으면 그 파일의 `max(ours, theirs)` (semver 3필드 수치 비교)
   - VERSION 파일이 충돌하지 않았으면 merge 결과의 VERSION 값 (`cat {VERSION파일}`)

   swagger 파일의 ours/theirs 값은 판정에만 쓰고, 기입값으로는 쓰지 않는다 — 파일 간 값이 어긋나 있어도 이 단계에서 하나로 수렴시킨다.
3. VERSION 파일은 잠정값 한 줄로 덮어쓴다.
4. swagger 파일은 **충돌 블록 전체**(`<<<<<<<` 줄부터 `>>>>>>>` 줄까지, 마커 3줄과 양쪽 본문을 모두 포함)를 **ours 쪽 version 라인 한 줄**로 치환하고, 그 줄의 버전 값만 잠정값으로 바꾼다 — 들여쓰기·따옴표·키 표기는 원본 그대로 둔다. 마커만 지우고 양쪽 라인을 모두 남기면 version 키가 중복돼 YAML/JSON 이 깨진다.
5. `git add {해결한 파일들}` — 커밋은 하지 않는다 (Step 5.4가 단독 출구다).
6. semver 파싱에 실패하면 잠정값을 만들 수 없으므로 `AskUserQuestion`:
   > 충돌한 버전 값을 해석하지 못했습니다 (ours: `{값}`, theirs: `{값}`).
   > 1. 잠정값 직접 입력 — `X.Y.Z` 형식만 받는다. 형식이 아니면 1회 재질문하고, 그래도 아니면 2번으로 간다
   > 2. 일반 충돌로 재분류 — Step 5.2의 중단 절차를 따른다 (`BLOCKED:CONFLICT`)

   Step 6.2의 "버전 단계 생략" 선택지는 여기에 쓰지 않는다 — 충돌 헌크가 해결되지 않은 채 남기 때문이다.

### Step 5.4: merge 마무리

```bash
git rev-parse -q --verify MERGE_HEAD
```

`MERGE_HEAD` 가 있으면 (충돌을 자동 해결했거나, 재개 경로로 들어와 사용자가 이미 해결해 둔 경우) merge 를 커밋한다:

```bash
git commit --no-edit
```

이것이 merge 커밋을 만드는 **유일한 지점**이다 — 범프 커밋(Step 7.3)과 반드시 분리된다. 충돌 없이 깨끗하게 merge 된 경우와 `Already up to date` 인 경우에는 `MERGE_HEAD` 가 없으므로 아무 일도 하지 않는다.

커밋 실패(스테이징되지 않은 충돌 잔여 등) 시 에러 원문을 보고하고 종료한다 (`BLOCKED:MERGE_FAILED`).

## Step 6: 확정 버전 계산

Step 3.1이 `SKIPPED:NO_VERSION_FILE` 이면 이 단계와 Step 7을 건너뛰고 Step 8로 간다.

### Step 6.1: 범프 판정

```bash
cat {VERSION파일}                        # merge 반영된 현재 값
git show origin/{base}:{VERSION파일}     # base 값
```

| 비교 (semver 3필드 수치) | 확정 버전 |
|--------------------------|-----------|
| 로컬 ≤ base | `max(base, 로컬)` 의 patch +1 — `/common:commit-pr` Step 2와 동일한 계산식 |
| 로컬 > base | **로컬 값 그대로** (범프 없음). `SKIPPED:ALREADY_AHEAD` 로 기록하되, swagger 동기화는 이 값으로 계속 수행한다 |

> 무조건 범프하지 않는 이유: 이미 범프한 브랜치에서 다시 실행하면 이중 범프가 된다. 조건부 규칙은 세 경우를 모두 덮는다 — 브랜치만 범프됨(범프 없음, 확정=로컬) / base 만 전진(base+1) / 양쪽 범프(Step 5.3에서 max 로 수렴 후 +1). 이 판단 기준은 `/common:commit-pr` Step 1의 4번(VERSION 재범프 확인)과 같다.

### Step 6.2: 파싱 실패 정책

`v` 접두·4필드·비수치 등으로 semver 3필드 파싱에 실패하거나 `git show` 가 실패하면 자동 판단하지 않고 `AskUserQuestion` 으로 확정 버전을 받는다:
> VERSION 값을 해석하지 못했습니다 (로컬: `{값}`, base: `{값}`).
> 1. 확정 버전 직접 입력 — `X.Y.Z` 형식만 받는다. 형식이 아니면 1회 재질문하고, 그래도 아니면 2번으로 간다
> 2. 버전 단계 생략 후 계속 (`SKIPPED:VERSION_PARSE_FAILED`) — Step 7을 건너뛰고 Step 8로 간다
> 3. 중단

Step 5.3의 파싱 실패는 이 정책이 아니라 Step 5.3 자체의 선택지를 쓴다 — 그 시점에는 충돌 헌크가 미해결이라 "생략 후 계속" 이 성립하지 않는다.

## Step 7: 파일 갱신 + 커밋

Step 3.1이 `SKIPPED:NO_VERSION_FILE` 이거나 Step 6.2가 `SKIPPED:VERSION_PARSE_FAILED` 면 확정 버전이 없으므로 이 단계 전체를 건너뛰고 Step 8로 간다.

### Step 7.1: VERSION

확정 버전을 VERSION 파일에 쓴다 (기존 파일의 개행 유무를 보존). Step 6.1이 `SKIPPED:ALREADY_AHEAD` 면 값이 이미 확정 버전이므로 쓰지 않는다.

### Step 7.2: swagger

버전 대상 집합의 **모든** 파일에 확정 버전을 기입한다. 편집 지점은 Step 3.2 표의 필드로 한정한다 — `info.version` / `SwaggerInfo.Version` / `// @version`. 파일 안의 다른 version 유사 문자열(의존성 버전, `openapi:` 스펙 버전 등)은 건드리지 않는다.

갱신 후 각 파일을 다시 읽어 검증한다 — 대상 필드가 **정확히 1개** 존재하고 그 값이 확정 버전과 같아야 한다. 필드가 2개 이상이면 (Step 5.3의 충돌 치환이 잘못된 경우) 그대로 두면 파일이 깨지므로 반드시 잡아낸다. 하나라도 어긋나면 그 파일과 현재 값을 보고하고 **즉시 종료한다** (`BLOCKED:VERSION_WRITE_FAILED`) — 계속할지 묻지 않는다. 검증에 실패한 값을 커밋·push 하면 swagger 가 깨진 채 원격에 올라가고, 상태 코드의 "push 미수행" 보장도 깨진다. 로컬 상태(merge 커밋 포함)는 그대로 보존되므로 사용자가 파일을 고친 뒤 다시 실행하면 된다.

### Step 7.3: 커밋

버전 파일만 스테이징해 단독 커밋한다 — merge 커밋과 분리해야 이력에서 버전 변경 지점이 드러난다:

```bash
git add {VERSION파일} {갱신한 swagger 파일들}
git commit -m "Chore: VERSION {확정 버전} 범프 ({base} 동기화)"
```

`SKIPPED:ALREADY_AHEAD` 라도 swagger 가 갱신됐으면 커밋한다 (메시지: `Chore: swagger version {확정 버전} 동기화`). **스테이징한 변경이 하나도 없으면** 이 단계를 건너뛴다. 작업 트리의 다른 변경은 건드리지 않는다.

파일 쓰기·`git add`·`git commit` 중 어느 하나라도 실패하면 **Step 8로 진행하지 않는다** — 버전 파일만 수정된 채 push 되는 상태를 만들지 않기 위함이다. 에러 원문을 보고하고 종료한다 (`BLOCKED:VERSION_WRITE_FAILED`).

## Step 8: Push

`/common:commit-push`의 **Step 3(Assumption Gate)과 Step 4(push)만** 수행한다. Step 2(커밋)는 이 스킬이 이미 자기 방식으로 마쳤다.

**Step 1(브랜치 판정)을 위임하지 않는 이유**: commit-push Step 1은 컨벤션 불일치 브랜치를 `git branch -m` 으로 재명명한다. sync-base 는 이미 존재하는(대개 이미 push 되어 PR 이 열려 있는) 브랜치를 최신화하는 스킬이므로, merge 도중 이름을 바꾸면 원격 브랜치·PR 과 어긋난다. 대신 **경고만** 남긴다 — 현재 브랜치명이 이름 규칙(`/common:commit-push` "브랜치 이름 규칙")에 맞지 않으면 보고에 한 줄로 알리고 계속 진행한다. 이름 정리는 사용자가 별도로 `/common:commit-push` 로 처리한다.

Gate 에 넘길 base 는 **`origin/{base}`** 다 (로컬 `{base}` 가 아니다). Gate 는 `git diff {base}...HEAD` 로 브랜치 diff 를 뜨는데, 로컬 ref 가 낡았으면 merge-base 가 과거로 잡혀 base 자신의 커밋까지 스캔 대상에 들어가고 엉뚱한 `[Assumption]` 로 push 가 막힌다. Step 2에서 확정한 값을 재계산 없이 그대로 넘긴다.

| 결과 | 처리 |
|------|------|
| Gate 통과 → push 성공 | `DONE` |
| `[Assumption]` 미해소로 사용자가 중단 | `BLOCKED:ASSUMPTION_UNRESOLVED` — merge·범프 커밋은 **로컬에 보존**된 상태로 종료. 태그 해소 후 `/common:commit-push` 로 이어서 push |
| push 실패 (인증·거부·원격 충돌) | commit-push Step 4의 실패 처리에 따른다. 종료 시 `BLOCKED:PUSH_FAILED` |

merge 만 하고 push 는 나중에 하려면 이 단계에서 중단을 선택하면 된다 — 로컬 커밋은 그대로 남는다.

## Step 9: 보고

```
✅ base 최신화 완료
- base: {base} — {merge 커밋 SHA | "Already up to date"}
- 가져온 커밋: {Step 2.4에서 센 수}개
- VERSION: {이전} → {확정 버전}   (또는 SKIPPED 사유)
- swagger: {갱신한 파일 목록}      (또는 SKIPPED:NO_SWAGGER)
- 자동 해결한 버전 충돌: {파일 목록 또는 '없음'}
- 커밋: {merge 커밋 SHA}, {범프 커밋 SHA}
- push: 완료 (origin/{현재 브랜치})   (또는 중단 사유)
```

재개 경로(Step 4.1)로 진입해 "가져온 커밋" 수를 모르면 그 줄을 생략한다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | merge + 범프 + push 완료 (base 가 앞서 있지 않았던 경우 포함) |
| `SKIPPED:NO_VERSION_FILE` | VERSION 파일 없음 — 범프·swagger 생략, merge·push 는 수행 |
| `SKIPPED:ALREADY_AHEAD` | 로컬 VERSION 이 base 보다 앞섬 — 범프 생략, swagger 는 로컬 값으로 동기화 |
| `SKIPPED:NO_SWAGGER` | swagger 파일 없음 — 동기화 생략 |
| `SKIPPED:VERSION_PARSE_FAILED` | semver 파싱 실패 — 사용자가 버전 단계 생략 선택 |
| `BLOCKED:DETACHED_HEAD` | detached HEAD |
| `BLOCKED:ON_BASE` | 현재 브랜치가 base 이거나 보호 브랜치 |
| `BLOCKED:NO_BASE` | base 결정 실패 — 사용자 중단 |
| `BLOCKED:FETCH_FAILED` | `git fetch origin {base}` 실패 |
| `BLOCKED:DIRTY_TREE` | 작업 트리에 미커밋 변경 — 사용자 중단 선택 |
| `BLOCKED:OTHER_OP_IN_PROGRESS` | rebase·cherry-pick·revert 진행 중 |
| `BLOCKED:FOREIGN_MERGE` | 결정된 base 와 무관한 merge 가 진행 중 |
| `BLOCKED:VERSION_WRITE_FAILED` | 버전 파일 쓰기·검증·커밋 실패 — push 미수행, 로컬 상태 보존 |
| `BLOCKED:MERGE_FAILED` | 충돌 외 사유로 merge 실패 |
| `BLOCKED:CONFLICT` | 버전 외 충돌 — merge 진행 상태 유지, 해결 후 재실행으로 재개 |
| `BLOCKED:ASSUMPTION_UNRESOLVED` | Assumption Gate 미해소 — 로컬 커밋 보존, push 만 미수행 |
| `BLOCKED:PUSH_FAILED` | push 실패 — 로컬 커밋 보존 |

## 호출 예시

```bash
/common:sync-base          # base 자동 결정 (브랜치 모델 → PR base → origin/HEAD)
/common:sync-base dev      # base 명시
/common:sync-base main
```
