# common

여러 harness(be/fe/특화 하네스)에서 공통으로 사용하는 스킬 모음.

`be-harness`, `fe-harness`, `minmos-harness`, `hyeondongs-harness` 등 어떤 하네스를 쓰더라도 **먼저 설치되어야 하는 베이스 플러그인**이다. 도메인 종속성이 없는 범용 스킬만 둔다.

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
| **commit-push** | `/common:commit-push` | commit + push (브랜치 컨벤션 검증/생성 포함). 브랜치 모델 오버라이드 선언 시 prefix·base 조합까지 검증. push 전 Assumption Gate로 `[Assumption]` 태그를 사용자 확인 후 전부 제거해야 push 가능 |
| **commit-pr** | `/common:commit-pr` | commit + push + 브랜치 생성 + PR 오픈(기본 draft, `--ready`로 ready 전환, `--bump-only`로 VERSION 범프 전용 PR). base 브랜치 대조 VERSION 자동 범프, 기존 open PR 본문 동기화 확인 포함. Assumption Gate 승인 항목은 PR 본문 "확정된 결정" 섹션에 기록. PR 본문은 결론 → 리뷰어가 할 일 → 주요 변경 → 남은 한계 순서로 쓰고 검증·확정된 결정 등은 `<details>`로 접으며, ASD-STE100 Simplified Technical 원칙(짧은 능동문, 한 단어 한 뜻)과 목록·표로 작성(주의가 쉽게 흩어지는 독자 기준) |
| **commit-hard-push** | `/common:commit-hard-push` | 보호 브랜치 제한 없이 commit + push (Assumption Gate 적용) |
| **merge** | `/common:merge` | PR 을 머지. doc-gen 으로 요약 컨펌 후 머지 방식(일반/스쿼시/리베이스/취소) 선택 |
| **sync-base** | `/common:sync-base` | `merge` 의 **역방향** — base 를 현재 브랜치로 merge 해 최신화. VERSION 이 있으면 base 대조 조건부 patch 범프, swagger(OpenAPI) version 을 같은 값으로 동기화한 뒤 push. base 결정·버전 계산은 `commit-pr` 규칙과 동일, push 는 `commit-push` 의 Assumption Gate 를 거침. 버전 파일 충돌만 자동 해결하고 그 외 충돌은 merge 진행 상태로 두어 재실행 재개 |
| **resolve-assumption** | `/common:resolve-assumption` | 코드·미push 커밋 메시지에 남은 `[Assumption]` 태그를 항목별로 하나씩 확인받아 해소. 승인 시 태그만 삭제하고 `[확정]` 류 대체 워딩을 남기지 않음. 게이트가 아니므로 보류 가능하며 push 하지 않음 |

### 워크플로우 진입점

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/common:start-workflow` | 개발 워크플로우의 **단일 진입점**. 요청을 분석해 백엔드/프론트엔드/풀스택을 판정하고, 단일 도메인이면 해당 하네스로 위임하고 풀스택이면 계약 기반 병렬 오케스트레이션을 직접 실행. `--reflect`(성찰, 기본 off)·`--tier quick|light|standard`(검증 티어 선언 — 진입 gate가 값 검증)는 단일 도메인에 그대로 전달(풀스택은 `--tier`를 무시하고 항상 standard), 풀스택은 `--reflect`를 직접 소비해 Phase 10 회고 1회 + 종료 시 md Workflow Report 아카이브. `--codex none|mix|max`는 Codex 사용 모드(profile `codexMode` 저장) — 단일 도메인은 통과, 풀스택은 직접 소비해 be·fe profile에 기록. `--codex-models`(슬롯별 위임 모델, profile `codexModels`)도 동일 |

**도메인 플래그**: `--be`(백엔드) · `--fe`(프론트엔드) · `--fs`(풀스택) · `--mm`(백엔드 + minmos 오버레이) · `--hd`(프론트엔드 + hyeondongs 오버레이)
**공통 설정**: `.claude/harness.config.json`(타 모델 리뷰 on/off·리뷰 엔진 codex/gemini/claude·단계 토글)을 be/fe/풀스택이 함께 읽는다. 편집은 `harness-settings` mod의 `/harness-settings`. 계약: `skills/start-workflow/references/review-config.md`.

**플래그를 생략하면** 프로젝트 신호(`go.mod`, `package.json`, profile 파일 등)와 요청 내용으로 도메인을 판정하고 **확인을 거친 뒤** 실행한다.

단일 도메인 위임 시 절차는 위임 대상 하네스가 정의한다. 풀스택 절차는 `skills/start-workflow/references/fullstack.md` 가 canonical이다.

워크플로우 외 스킬(`request`, `e2e-test`, `convention-check`, `doctor`, `init` 등)은 하네스를 직접 지정해 호출한다: `/be-harness:request`, `/fe-harness:component`.

### 구현 준비

| 스킬 | 호출 | 설명 |
|------|------|------|
| **ready-for-impl** | `/common:ready-for-impl` | 구현 전에 주제별 인터뷰 라운드(목표·범위 → 동작·인터페이스 → 데이터·상태 → 예외·권한 → 비기능 → 완료·검증)로 요구사항을 확정하고, 작업 계약과 `AC`/`EC`/`RC`(풀스택 `F`) 추적 ID를 갖춘 Spec md를 저장. 코드를 수정하지 않으며 결과 Spec은 `start-workflow` Phase 1의 상세 Spec 분기로 그대로 인계 |

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

# base 를 현재 브랜치로 최신화 + VERSION/swagger 버전 범프
/common:sync-base      # base 자동 결정
/common:sync-base dev  # base 명시

# 구현 전에 인터뷰로 Spec만 확정 (코드 수정 없음)
/common:ready-for-impl "주문 취소 기능 추가"
/common:ready-for-impl --be --out ./specs "정산 배치 API 추가"

# 선택: Ponytail 원칙으로 최소 범위·재사용 점검 (외부 플러그인 설치 불필요)
/common:ready-for-impl --ponytail "주문 취소 기능 추가"

# 워크플로우 시작 (도메인 자동 판정 후 확인)
/common:start-workflow "주문 취소 기능 추가"

# 도메인 고정
/common:start-workflow --be "정산 배치 API 추가"
/common:start-workflow --fs "쿠폰 등록 화면과 API"
```

자세한 동작 흐름은 각 스킬의 `skills/<name>/SKILL.md` 참고.

## mod (Claude Code 전용)

`hooks/register.tsx` (`hooks/hooks.json` 의 `modules`).

### 커뮤니케이션 규칙 주입

대화의 첫 메시지 컨텍스트에 `harnessLanguage` 블록으로 다음 두 규칙을 넣는다. 컴팩션 뒤에도 다시 들어간다.

- Always talk in ASD-STE100 Simplified Technical Korean.
- Always talk to me like I have ADHD.

work-log mod 도 같은 블록을 넣는다. 이름이 같으면 한 번만 들어간다.

### 워크플로우 진행 표시

| 위치 | 내용 |
|------|------|
| band (프롬프트 위) | `▶ BE · Phase 8 - 품질 루프` |
| status line | `wf: BE P8` |
| `/harness-progress` pane | Phase Assignments 표 (✓ 완료 · ▶ 진행 · · 대기) |

- 감지: main 대화에서 모델이 Bash 로 `workflow_run.py create|resume` 를 실행하면 그 출력의 `STATE_FILE`(절대 경로 `workflow-state.md` 만)을 기억한다. 이후 도구 결과가 올 때마다 상태 파일의 `Current Phase`·`Phase Assignments` 를 다시 읽는다. subagent 의 실행은 보지 않는다.
- 종료: `Remaining Phases` 가 `없음`(workflow_run.py 와 같은 규칙)이거나, 읽은 적 있는 상태 파일이 사라지거나(아카이브), `/clear` 하면 표시를 지운다.
- 한계: Plan 을 거절해 상태 파일이 생기지 않은 실행은 `준비 중` 으로 남는다 (`/clear` 또는 새 실행으로 지워진다).
- be·fe·풀스택·Analyze·Verify 모두 같은 band 1개로 표시한다. 스킬 문서는 바꾸지 않는다.
- `tool.call` 은 hook 하지 않는다 (도구의 백그라운드 전환을 끄기 때문). Code Mode 한계: [docs/codeact-review.md](../docs/codeact-review.md).

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
    ├── merge.md                    # /common:merge 오버라이드
    ├── sync-base.md                # /common:sync-base 오버라이드 (swaggerVersionFiles 선언)
    ├── resolve-assumption.md       # /common:resolve-assumption 오버라이드
    ├── ready-for-impl.md           # /common:ready-for-impl 오버라이드 (specDir 선언)
    └── start-workflow.md           # /common:start-workflow 오버라이드
```
