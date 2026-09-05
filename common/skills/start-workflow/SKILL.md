---
name: start-workflow
description: "개발 워크플로우(Spec → Plan → 구현 → 품질 루프 → PR)의 단일 진입점. 요청을 분석해 백엔드/프론트엔드/풀스택을 판정하고 해당 하네스로 위임하거나 풀스택을 직접 오케스트레이션한다. '워크플로우 시작', '기능 구현해줘(전 과정 자동)', '풀스택으로 진행해줘', '코드 분석/검증해줘' 요청 시 사용."
user-invocable: true
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Agent, EnterPlanMode, ExitPlanMode, Skill
argument-hint: "[--be|--fe|--fs] <작업 설명> | --analyze [경로] | --verify [경로]"
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/start-workflow.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Start Workflow — 단일 진입점

개발 워크플로우의 **유일한 공용 진입점**이다. 어느 하네스를 쓸지 기억하지 않아도 된다.

- **단일 도메인**(backend / frontend) → 해당 하네스 스킬에 위임한다. **이 문서에 그 절차는 없다.**
- **풀스택**(FE+BE 동시 변경) → 이 스킬이 직접 오케스트레이션한다 (`references/fullstack.md`).

## Flags

| 플래그 | 효과 |
|--------|------|
| `--be` | 도메인 판정을 건너뛰고 백엔드로 확정 |
| `--fe` | 도메인 판정을 건너뛰고 프론트엔드로 확정 |
| `--fs` | 도메인 판정을 건너뛰고 풀스택으로 확정 |
| `--mm` | 백엔드 + `minmos-harness` 오버레이로 확정 |
| `--hd` | 프론트엔드 + `hyeondongs-harness` 오버레이로 확정 |

- 대상 플래그는 **인자 어느 위치에나** 올 수 있다. 플래그를 제거한 나머지 인자는 그대로 대상에 전달한다.
- 대상 스킬 고유 플래그(`--resume`, `--hard`, `--no-tdd`, `--reflect`, `--tier standard`, `--codex`, `--codex-models`, `--analyze`, `--verify` 등)는 **해석하지 않고 그대로 넘긴다.**
- 두 개 이상의 대상 플래그가 오면 오류로 처리한다: "대상 플래그는 하나만 지정하세요: {입력된 목록}".

### 통과 플래그 (단일 도메인 vs 풀스택)

| 플래그 | 단일 도메인 위임 | 풀스택 (`--fs`) |
|--------|----------------|----------------|
| `--resume {STATE_FILE}` | 그대로 전달 | `run-lifecycle.md`로 절대 상태 경로·저장소·모드·미완료 여부 검증 |
| `--reflect` | 그대로 전달 — 해당 하네스의 성찰 Phase 활성화 (기본 off) | **이 스킬이 소비** — 풀스택 Phase 10 회고를 1회만 실행하고 하위 도메인 에이전트에 전달하지 않는다 |
| `--tier standard` | 그대로 전달 — 검증 티어 상향 강제 | 무시 (풀스택은 항상 standard) |
| `--hard` / `--no-tdd` | 그대로 전달 | `references/fullstack.md` Flags 참조 |
| `--codex {none\|mix\|max}` | 그대로 전달 — 해당 하네스가 profile `codexMode`에 저장 | **이 스킬이 소비** — `references/fullstack.md` Pre-flight에서 해석하고 be·fe profile 양쪽에 기록 (`references/codex-mode.md`) |
| `--codex-models {슬롯}={provider}/{model}[@{effort}],…` | 그대로 전달 — 해당 하네스가 profile `codexModels`에 저장 | **이 스킬이 소비** — Pre-flight에서 `codexMode` 확정 직후 슬롯 resolve(`codexModels` 블록 단위 be → fe → 기본값, 플래그는 슬롯 단위 덮어쓰기), 기록은 writable be·fe 모두 (`references/codex-mode.md` §2.1) |

## Language Rule

유저와의 모든 대화는 한국어로 진행한다 (대상 하네스 profile에 `language`가 있으면 위임 후에는 그 값을 따른다).

---

## Step 1: 대상 플래그 파싱

`$ARGUMENTS`에서 위 표의 플래그를 찾는다. `--resume`이 있으면 명시된 상태의 `## Run` MODE로 도메인을 결정하고 Step 2를 생략한다 (`be`/`analyze`/`verify` → backend, `fe` → frontend, `fs` → fullstack). analyze/verify는 해당 모드 플래그도 전달한다. 대상/모드 플래그와 충돌하거나 Run이 없으면 `BLOCKED:RUN_MISMATCH`; 실제 재개는 대상 하네스의 경로 검증 성공 후에만 한다.

- 플래그 있음 → 도메인 확정. **Step 2를 건너뛰고 Step 3으로.**
- 플래그 없음 → Step 2.

## Step 2: 도메인 판정

### 2.1 신호 스캔

아래를 Glob/Read로 조용히 확인한다 (출력하지 않는다).

| 신호 | 시사 도메인 |
|------|------------|
| `.claude/be-harness.local.md` 존재 | backend |
| `.claude/fe-harness.local.md` 존재 | frontend |
| `.hyeondong-config.json` 존재 | frontend (hyeondongs 오버레이 후보) |
| `go.mod` · `pom.xml` · `build.gradle*` · `Cargo.toml` · `requirements.txt` · `pyproject.toml` | backend |
| `package.json` + `next`/`react`/`vue`/`svelte`/`vite` 의존성 | frontend |
| 위 backend·frontend 신호가 **모두** 잡힘 | fullstack 후보 |

### 2.2 요청 분석

`$ARGUMENTS`와 대화 컨텍스트에서 변경 대상을 추정한다.

| 단서 | 판정 |
|------|------|
| API·엔드포인트·DB·스키마·마이그레이션·인증 로직·배치 | backend |
| 화면·페이지·컴포넌트·스타일·상태 관리·폼·접근성 | frontend |
| "화면에서 ~를 호출", "API 만들고 화면도", 신규 기능 전체 | fullstack |
| 판단 불가 | 신호 스캔 결과를 권장으로 제시 |

### 2.3 유저 확인 (MUST)

**판정만으로 조용히 실행하지 않는다.** 워크플로우는 장시간 자율 실행되므로 반드시 확인을 거친다.

`AskUserQuestion`으로 backend / frontend / fullstack 선택지를 제시하고, 판정 결과 라벨 끝에 `(권장)`을 붙이며 근거를 한 줄로 적는다.

`AskUserQuestion`을 쓸 수 없는 컨텍스트(서브에이전트 등)에서는 번호 매긴 선택지를 출력하고 응답을 기다린다:

```
어느 도메인으로 실행할까요?
1. 백엔드 (권장: go.mod 발견)
2. 프론트엔드
3. 풀스택 (FE+BE 동시)
4. 취소
```

## Step 3: 위임 대상 결정

### 3.1 오버레이 감지

세션 스킬 목록에서 특화 하네스의 위임 스킬 존재를 확인한다.

| 도메인 | 1순위 (오버레이 있을 때) | 2순위 (베이스) |
|--------|------------------------|---------------|
| backend | `/minmos-harness:start-workflow` | `/be-harness:start-workflow` |
| frontend | `/hyeondongs-harness:start-workflow` | `/fe-harness:start-workflow` |
| fullstack | — (Step 4에서 직접 실행) | — |

- `--mm` / `--hd` 는 1순위를 **강제**한다. 해당 플러그인이 없으면 미설치 안내 후 종료한다.
- 플래그 없이 1순위가 존재하면 위임 전에 한 줄로 고지한다:
  > "`{플러그인}` 오버레이가 설치되어 있어 `/{플러그인}:start-workflow` 로 진행합니다. 베이스만 쓰려면 `--be`/`--fe` 를 지정하세요."

### 3.2 미설치 안내 (graceful degradation)

| 감지 | 폴백 | 고지 문구 |
|------|------|----------|
| 지정한 도메인의 베이스 하네스가 세션에 없음 | 종료 | "`{플러그인}` 이 설치되어 있지 않습니다. `/plugin install {플러그인}@harness-plugins` 로 설치하거나, 설치된 도메인을 지정하세요: {후보 목록}" |
| 풀스택인데 be/fe 중 한쪽만 있음 | 단일 도메인 제안 후 종료 | "풀스택 작업이지만 `{누락 플러그인}` 이 없습니다. 설치하거나 `{설치된 도메인}` 단일로 진행하세요." |
| 하나도 없음 | 종료 | "워크플로우를 제공하는 하네스가 하나도 설치되어 있지 않습니다: be-harness, fe-harness" |

## Step 4: 실행

### 4.1 단일 도메인 — 위임

Skill tool로 Step 3에서 정한 스킬을 호출하고, **대상 플래그를 제거한 나머지 인자를 그대로 전달**한다.

- 대상 스킬의 출력을 **가공하지 않고 그대로** 전달한다. 요약·재구성 금지.
- `SKIPPED:*` / `BLOCKED:*` 를 반환하면 그대로 상위에 올린다.
- 이 스킬은 상태 파일을 만들거나 갱신하지 않는다.

### 4.2 풀스택 — 직접 오케스트레이션

> 풀스택 판정 시 MUST: 같은 폴더의 `references/fullstack.md`를 Read하고 Phase 1~11 절차를 따른다.

`references/fullstack.md`가 이 경로의 canonical이다. 이 문서는 진입 판정까지만 책임진다.

## 도메인 재판정 (위임 후)

위임한 단일 도메인 워크플로우가 실행 중 반대 도메인 변경이 필요하다고 판정하면, **그 하네스가 직접 `/common:start-workflow --fs` 를 호출해 전환**한다 (be-harness Phase 3의 `fullstack` 판정, fe-harness Phase 1의 풀스택 판정). 이 스킬은 그 판정에 개입하지 않는다.

`--fs` 로 재진입하면 Step 1에서 플래그를 감지해 Step 2(도메인 판정)를 건너뛰고 곧바로 Step 4.2로 간다 — 재귀는 발생하지 않는다.
이미 진행된 커밋은 그대로 두고, 풀스택 Phase 1(기능 정의)부터 다시 시작한다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` / `IN_PROGRESS` / `PENDING` | Phase 진행 상태 (풀스택 경로) |
| `SKIPPED:{사유}` | 조건 미충족으로 건너뜀 |
| `BLOCKED:{사유}` | 진행 불가 — 사용자 개입 필요 |
| `PASS` / `WARN` / `FAIL` | 도메인별 테스트 판정 (풀스택 경로) |

## References

| 파일 | 로드 시점 |
|------|----------|
| `references/fullstack.md` | 도메인 판정이 `fullstack`일 때 (Step 4.2) |
| `references/contract-templates.md` | 풀스택 Phase 1, 2, 3, 5, 9, 11 |
| `references/fullstack-tdd.md` | 풀스택 Phase 5, 6 |
| `references/fullstack-agent-prompts.md` | 풀스택 Phase 6.1·6.2·8.1 |
| `references/codex-mode.md` | 풀스택 첫 리뷰어/위임 dispatch 직전 1회 (Codex 모드 정의·호출 계약·실패 정책) |
