# common

여러 harness(be/fe/fs/특화 하네스)에서 공통으로 사용하는 스킬 모음.

`be-harness`, `fe-harness`, `fs-harness`, `minmos-harness`, `hyeondongs-harness` 등 어떤 하네스를 쓰더라도 **먼저 설치되어야 하는 베이스 플러그인**이다. 도메인 종속성이 없는 범용 스킬만 둔다.

## 설치

```bash
/plugin marketplace add kangmomin/harness-plugins

# 다른 하네스를 쓰기 전에 먼저 설치
/plugin install common@harness-plugins
```

이후 원하는 하네스를 설치한다.

```bash
/plugin install be-harness@harness-plugins
/plugin install fe-harness@harness-plugins
# ...
```

## 스킬 목록

### 문서 / 문서화

| 스킬 | 호출 | 설명 |
|------|------|------|
| **doc-gen** | `/common:doc-gen` | 지정한 범위(파일/디렉토리/glob/PR/commit range)를 분석해 다이어그램이 포함된 단일 파일 문서(`-md`/`-html`, `--twin`으로 동시 생성+정합 검증, `--brief`로 압축 모드)로 정리. 저장 전 Mermaid lint 자체 점검 |

### 커밋 / Push / PR 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **commit** | `/common:commit` | 변경사항을 논리적 단위별로 나눠서 커밋 |
| **commit-push** | `/common:commit-push` | commit + push (브랜치 컨벤션 검증/생성 포함). 브랜치 모델 오버라이드 선언 시 prefix·base 조합까지 검증 |
| **commit-pr** | `/common:commit-pr` | commit + push + 브랜치 생성 + PR 오픈(기본 draft, `--ready`로 ready 전환, `--bump-only`로 VERSION 범프 전용 PR). base 브랜치 대조 VERSION 자동 범프, 기존 open PR 본문 동기화 확인 포함 |
| **commit-hard-push** | `/common:commit-hard-push` | 보호 브랜치 제한 없이 commit + push |
| **merge** | `/common:merge` | PR 을 머지. doc-gen 으로 요약 컨펌 후 머지 방식(일반/스쿼시/리베이스/취소) 선택 |

### 하네스 공용 진입점 (라우터)

여러 하네스가 같은 이름의 스킬을 제공한다. 매번 `/be-harness:`, `/fe-harness:` 같은 접두를 기억하는 대신 `/common:` 으로 진입하고 대상만 고른다.

**대상 플래그**: `--be`(백엔드) · `--fe`(프론트엔드) · `--fs`(풀스택) · `--mm`(minmos) · `--hd`(hyeondongs — 세팅/진단/풀스택 전용, 그 외는 `--fe` 로 처리)
**플래그를 생략하면** 설치된 하네스 중에서 선택지를 제시한다. 후보가 하나뿐이면 묻지 않고 바로 실행한다.

| 스킬 | 호출 | 위임 대상 |
|------|------|----------|
| **start-workflow** | `/common:start-workflow` | be · fe · fs · mm (+ `--mm-fs` / `--hd-fs` 풀스택 변형) |
| **request** | `/common:request` | be · fe · mm |
| **e2e-test** | `/common:e2e-test` | be · fe · mm |
| **e2e-test-loop** | `/common:e2e-test-loop` | be · mm |
| **simplify-loop** | `/common:simplify-loop` | be · fe · mm |
| **convention-check** | `/common:convention-check` | be · fe · mm |
| **default-conventions** | `/common:default-conventions` | be · fe · mm |
| **doctor** | `/common:doctor` | be · fe · mm · hd (후보 전체 순차 실행 가능) |
| **init** | `/common:init` | be · fe · mm · hd |
| **component** | `/common:component` | fe |
| **unit-test** | `/common:unit-test` | be · fe |
| **lint-check** | `/common:lint-check` | fe |
| **test-loop** | `/common:test-loop` | fe |

`--hd` 는 `init` · `doctor` · `start-workflow --hd-fs` 에서만 고유 대상을 가진다. 나머지 라우터에서는 `--fe` 로 처리하고 한 줄 고지한다 (hyeondongs 프론트엔드 스킬 10종이 fe-harness 로 통합됨).

라우터는 **절차를 갖지 않는다.** 실제 동작은 위임 대상 하네스 스킬이 정의하며, 라우터는 대상 결정과 인자 전달만 한다. 공통 규약: 플러그인 루트 [`ROUTING.md`](./ROUTING.md).

### 하네스 무관 스킬

동작이 하네스와 무관해 common 이 직접 구현하는 스킬. 대상 플래그는 동작을 바꾸지 않고 **범위를 좁히는 필터**로만 쓰인다.

| 스킬 | 호출 | 설명 |
|------|------|------|
| **how-to-use** | `/common:how-to-use` | 설치된 모든 harness 플러그인의 스킬 목록·사용법 안내. 플래그로 특정 하네스만 좁히기 가능 |
| **submit-feedback** | `/common:submit-feedback` | 수집된 범용 보완점을 플러그인 레포 `community-feedback/` 에 PR 제출. 대상 플러그인은 플래그·보완점 경로·프로젝트 구조 순으로 판별 |

## 사용 예시

```bash
# 현재 작업 디렉토리에서 시작 — 단계적 질문으로 범위 확정 후 md 출력
/common:doc-gen -md

# HTML 모드, src/auth 범위
/common:doc-gen -html src/auth

# PR 범위 요약
/common:doc-gen -md PR#42

# 압축 모드로 PR 요약 (핵심만)
/common:doc-gen --brief PR#42

# 작업 후 커밋만
/common:commit

# 커밋 + push (브랜치 자동 정리)
/common:commit-push

# 커밋 + push + draft PR
/common:commit-pr

# 커밋 + push + ready PR (VERSION 범프 포함)
/common:commit-pr --ready

# PR 머지 (doc-gen 요약 컨펌 + 머지 방식 선택)
/common:merge          # 현재 브랜치에 연결된 PR
/common:merge 42       # 특정 PR
```

자세한 동작 흐름은 각 스킬의 `skills/<name>/SKILL.md` 참고.

## Project Overrides

다른 하네스와 동일한 오버라이드 규약을 따른다. 자세한 내용은 `OVERRIDES.md`.

```
.claude/common/
├── common.md                       # 플러그인 공통 오버라이드
└── skills/
    ├── doc-gen.md                  # /common:doc-gen 오버라이드
    ├── commit.md                   # /common:commit 오버라이드
    ├── commit-push.md              # /common:commit-push 오버라이드
    ├── commit-pr.md                # /common:commit-pr 오버라이드
    ├── commit-hard-push.md         # /common:commit-hard-push 오버라이드
    └── merge.md                    # /common:merge 오버라이드
```
