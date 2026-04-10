---
name: start-workflow-hd
description: "전체 프론트엔드 개발 워크플로우를 자동화. 요청 분석 → 난이도 산정 → Plan 리뷰 → 구현 → 품질 루프 → 컴포넌트/접근성 리뷰 → PR → 성찰까지 일관된 파이프라인으로 실행한다."
argument-hint: <작업 설명 또는 빈 값>
---

# Start Workflow — Orchestrator

전체 프론트엔드 개발 라이프사이클을 **오케스트레이션 패턴**으로 실행한다.
각 자율 실행 Phase를 전용 서브 에이전트에 위임하여, 단일 컨텍스트 소진 없이 전 단계를 완주한다.

## Flags

| 플래그 | 단축 | 효과 |
|--------|------|------|
| `--hard` | `-h` | 브랜치 생성/검증을 건너뛰고 현재 브랜치에서 바로 push. PR 생략. |

`$ARGUMENTS`에 `--hard` 또는 `-h`가 포함되어 있으면 `$HARD_MODE = true`로 설정한다.

### --hard 모드 영향

| Phase | 일반 모드 | --hard 모드 |
|-------|----------|------------|
| Phase 3.5 | feature 브랜치 생성 필수 | **건너뜀** (현재 브랜치 유지) |
| Phase 4 커밋 | 동일 | 동일 |
| Phase 7 PR | workflow-pr (브랜치 생성 + PR) | **현재 브랜치에서 바로 push, PR 생략** |

---

```
[유저 대화] Phase 0~3  : 직접 실행 (Spec, Plan, 리뷰)
[상태 저장] Phase 3.5  : 상태 파일 생성
[자율 실행] Phase 4~8  : 서브 에이전트 순차 위임
[유저 대화] Phase 9    : 최종 보고 + 보완점 적용
```

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

## Advisor / Executor 원칙

- `workflow-implementer`만 코드 수정, 커밋, push를 수행한다.
- `scope-reviewer`, `component-reviewer`, `a11y-reviewer`, Plan reviewer, Codex Architect 리뷰, `workflow-reflection`은 **읽기 전용 advisor**로 동작한다.
- advisor는 방향, 누락, 위험만 판단한다. 직접 파일을 수정하거나 커밋 전략을 실행하지 않는다.
- advisor 결과는 항상 오케스트레이터가 해석해서 다음 액션으로 변환한다.

## 자율 실행 규칙

- Phase 0~3: 유저와 대화하며 Spec 확인, Plan 리뷰 피드백 반영
- **Phase 3.5 이후 ~ Phase 8 완료까지**: 서브 에이전트를 순차 호출하며 **묻지 않고 자동 실행**
- Phase 9: 최종 보고에서 보완점 반영 여부만 유저에게 질문

### Spec 외 변경 금지 원칙

자율 실행 중 Spec에 명시되지 않은 동작 변경이 필요하다고 판단되면:
1. **코드를 수정하지 않고** 해당 사항을 기록한다.
2. Phase 9 보고서에 `[Assumption]` 태그로 표기하여 유저에게 가시화한다.
3. 유저 승인 후에만 해당 변경을 적용한다.

### 연속 실행 필수 규칙 (CRITICAL)

**서브 에이전트가 완료되면 즉시 다음 단계를 실행한다. 절대 멈추지 않는다.**

- 에이전트 결과를 받으면 한 줄 요약만 출력하고, **같은 응답 안에서** 바로 다음 Agent tool을 호출한다.
- **유저 응답을 기다리거나, 진행 여부를 묻거나, 중간 보고 후 멈추는 것은 금지**
- 유일한 정지 지점은 **Phase 9 (최종 보고)** 뿐이다

---

## Phase 0: 작업 범위 수집

### 분기: 이미 상세 Spec이 제공된 경우

`$ARGUMENTS` 또는 대화 컨텍스트에 다음 조건을 **모두** 충족하는 상세 설명이 이미 포함되어 있으면 `/request` 호출을 **생략**한다:
- 작업 유형이 명확 (화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정)
- 대상 컴포넌트/페이지/API가 특정됨
- 핵심 요구사항이 구체적으로 기술됨

이 경우, 제공된 내용을 Technical Spec으로 직접 정리하고 유저 확인을 받는다.

### 기본: /request 호출

위 조건을 충족하지 않으면 `$request-hd`를 호출하여 Technical Spec을 생성한다.

---

## Phase 1: 난이도 산정

Technical Spec을 분석하여 1~10 난이도를 산정한다.

| 요소 | 낮음 (1-3) | 중간 (4-6) | 높음 (7-10) |
|------|-----------|-----------|------------|
| 파일 수 | 1-3개 | 4-7개 | 8개+ |
| 컴포넌트 수 | 1개 | 2-3개 | 4개+ |
| 상태 복잡도 | useState 단순 | 여러 상태 조합 | 전역 상태 + 서버 상태 |
| API 연동 | 없음 | 기존 API | 새 API 연동 |
| 반응형/a11y | 기본 | 반응형 필수 | 반응형 + 접근성 + 애니메이션 |
| 엣지 케이스 | 1-2개 | 3-5개 | 6개+ |

출력: `난이도: [N]/10 — [근거]`

### Advisor 에스컬레이션 트리거

다음 중 **하나라도** 만족하면 Phase 3 또는 Phase 5에서 advisor 에스컬레이션을 강제한다:
- 난이도 7+
- API 계약, 응답 구조, 타입 계약 변경
- 전역 상태, 라우팅, 공용 레이아웃 수정
- 3개 이상 화면/컴포넌트/상태 영역 동시 수정
- 품질 루프 2회차에도 `modified == true`
- 접근성 또는 빌드 안정성 리스크가 높아 롤백 비용이 큰 경우

> 에스컬레이션 시 advisor는 "새 구현을 쓰는 역할"이 아니라, 현재 Plan/구현의 위험 신호만 좁혀서 판단한다.

---

## Phase 2: Scope Reviewer 준비

Phase 5에서 사용할 scope-reviewer 정보를 메모한다:
- Technical Spec 전문
- 엣지 케이스 목록
- Plan 요약 (10줄 이내)
- 변경 파일 / 의도 중심 diff 요약
- `[Assumption]` 목록
- 실패 로그 발췌본 (마지막 20~30줄, 있을 때만)

### Advisor 입력 축약 원칙

- advisor에게 전체 대화나 전체 로그를 그대로 넘기지 않는다.
- 필요한 것만 묶어서 전달한다: `Spec`, `Plan 요약`, `diff 요약`, `엣지 케이스`, `실패 로그 일부`
- 로그는 원인 파악에 필요한 마지막 구간만 전달한다.
- advisor는 입력이 좁을수록 일관성이 높다. 정보가 많다고 품질이 올라간다고 가정하지 않는다.

---

## Phase 3: Plan 작성 + 리뷰

### 3.1 Plan 작성

Plan 시작 활성화. Plan 포함 내용:
- 구현 순서 (파일 단위)
- 각 파일 변경 내용 요약
- **최종 코드 구조**: 컴포넌트 분리, 훅 추출, 상태 설계를 Plan 단계에서 확정한다.
- 의존 관계
- 예상 리스크

### 3.2 다관점 Plan 리뷰

**최대 3개 서브에이전트 병렬 실행**, 2배치로 진행:

```
Batch 1 (병렬): 유지보수성 + 성능 + 엣지 케이스
Batch 2 (병렬): 상태 정합성 + 접근성 + 기존 코드 영향
```

각 에이전트(subagent_type: `general-purpose`) 프롬프트:

```
당신은 [관점명] 리뷰어입니다.
아래 Plan을 [관점] 관점에서만 리뷰하세요.

## Technical Spec
[Spec 전문]

## Plan
[Plan 전문]

## 리뷰 형식
**Verdict**: APPROVE / CONCERN / REJECT
**Issues**: [문제 목록 또는 "없음"]
**Suggestions**: [개선 제안 또는 "없음"]
**Next Action**: [오케스트레이터가 바로 수행할 1개 액션]
```

리뷰 종합:
- **REJECT 1개+**: Plan 수정 → 해당 관점 재리뷰
- **CONCERN만**: 타당한 것 자동 반영

### 3.3 Codex Architect 리뷰 (에스컬레이션 시)

Advisor 에스컬레이션 트리거를 만족하면, Codex 사용 가능 시 Architect 관점으로 Plan 리뷰를 위임한다.
Codex advisor 입력은 아래로 제한한다:
- Technical Spec 전문
- Plan 전문
- 가장 큰 리스크 3개

출력 형식은 반드시 다음을 따른다:
`APPROVE / CONCERN / REJECT + Next Action`

Codex advisor는 직접 구현하지 않는다.
불가 시 건너뛴다.

### 3.4 Plan 확정

Plan 확정 실행.

---

## Phase 3.5: Feature 브랜치 생성 + 상태 파일 생성 + 자율 실행 시작

### 브랜치 생성

- **`$HARD_MODE = false`** (일반): 구현 시작 전 반드시 feature 브랜치를 생성한다. main/master에 직접 커밋하지 않는다.
- **`$HARD_MODE = true`** (`--hard`): 브랜치 생성을 **건너뛴다**. 현재 브랜치가 무엇이든 그대로 사용한다.

```bash
# 일반 모드: 현재 브랜치가 main/master/dev면 반드시 새 브랜치 생성
git checkout -b feat/{작업 요약 kebab-case}
```

이미 feature 브랜치(`feat/**`, `hotfix/**`)에 있으면 건너뛴다.

### 상태 파일 생성

Write tool로 `/tmp/workflow-state.md`를 생성한다:

```markdown
# Workflow State

## Spec
[Technical Spec 전문 그대로 복사]

## Task Type
[화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]

## Difficulty
[N]/10

## Edge Cases
[엣지 케이스 목록]

## Plan
[확정된 Plan 전문 그대로 복사]

## Config
[.hyeondong-config.json 주요 설정]
```

출력: **"자율 실행을 시작합니다. Phase 4~8을 서브 에이전트로 순차 실행합니다."**

---

## Phase 4~8: 서브 에이전트 순차 실행

**각 Phase를 전용 서브 에이전트에 위임한다.**

### Phase 4: 구현

```
서브에이전트:
  agent: workflow-implementer
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 Plan에 따라 코드를 구현하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    
    [Assumption 규칙]
    Spec에 명시되지 않은 동작 변경을 수행한 경우,
    해당 항목에 반드시 [Assumption] 태그를 붙여 보고하세요.
    
    [커밋 단위 규칙]
    컴포넌트 1개 = 커밋 1개를 원칙으로 합니다.
    관련 없는 컴포넌트 변경을 하나의 커밋에 묶지 마세요.
    
    구현 완료 후 변경 파일 목록, 커밋 수, Plan 대비 차이점, [Assumption] 목록을 보고하세요.
```

### Phase 4.5: 빌드 체크 (MANDATORY — 구현 직후 강제 실행)

구현 에이전트 완료 즉시, 품질 루프 진입 전에 **반드시 빌드 + 타입 체크를 실행**한다.
컴파일 오류(미사용 변수, import 누락, 타입 에러, 무한 루프 등)를 조기에 잡아 핫픽스를 방지한다.

`.hyeondong-config.json`의 `framework`에 따라:
```bash
# Next.js
npx next build 2>&1 | tail -30

# Vite
npx vite build 2>&1 | tail -30

# 공통 타입 체크
npx tsc --noEmit 2>&1
```

- **성공** → Phase 5로 진행.
- **실패** → general-purpose 에이전트를 생성하여 빌드 에러를 수정한다:
  ```
  서브에이전트:
    agent: general
    prompt: |
      프로젝트 루트 {CWD}에서 빌드/타입 체크 에러를 수정하세요.
      에러 메시지: {빌드 에러 출력}
      수정 후 빌드가 성공하는지 확인하세요.
  ```
  수정 후 커밋:
  ```bash
  git add [수정 파일들]
  git commit -m "Fix: 빌드 에러 수정 (Phase 4.5)"
  ```
  빌드 재시도 → 성공하면 Phase 5로 진행. **최대 3회 시도** 후에도 실패하면 유저에게 보고하고 중단.

### Phase 5: 품질 루프 (오케스트레이터 직접 관리)

최대 3회 반복.

```
for iteration in 1..3:
  5.0 build + type-check      → Bash 직접 실행
  5.1 simplify-loop           → 서브 에이전트 (general-purpose)
  5.2 convention-check        → 서브 에이전트 (general-purpose)
  5.3 test-loop               → 서브 에이전트 (general-purpose)
  5.4 scope-reviewer          → 서브 에이전트 (scope-reviewer)
  5.5 lint-check              → 서브 에이전트 (general-purpose)

  수정 있음? → 커밋 후 다음 iteration
  수정 없음? → 루프 탈출
```

#### 품질 루프 Advisor 에스컬레이션

- iteration 2 이상인데도 `modified == true`이면 advisor 에스컬레이션을 수행한다.
- 동일 단계에서 같은 유형의 실패가 2회 반복되면 advisor 에스컬레이션을 수행한다.
- 이때 advisor 입력은 전체 로그가 아니라 아래만 전달한다:
  - 현재 iteration
  - 실패한 단계 이름
  - 최근 수정 파일 요약
  - 마지막 실패 로그 20~30줄
  - 오케스트레이터가 추정한 원인 3개 이하
- advisor 출력은 반드시 `Verdict / Issues / Suggestions / Next Action` 형식으로 받는다.

#### 5.0 Build + Type Check

Bash로 직접 실행. `.hyeondong-config.json`의 `framework`에 따라:

```bash
# Next.js
npx next build && npx tsc --noEmit

# Vite
npx vite build && npx tsc --noEmit

# 기타
npm run build && npx tsc --noEmit
```

실패 시 general-purpose 에이전트를 생성하여 에러 수정을 위임한다.

#### 5.1 Simplify

```
서브에이전트:
  agent: general
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 $simplify-loop-hd 를 실행하세요.
    완료 후 "수정: Y/N, N건" 형식으로 보고하세요.
```

#### 5.2 Convention Check

```
서브에이전트:
  agent: general
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 $convention-check-hd 를 실행하세요.
    위반 사항이 있으면 수정하세요.
    완료 후 "위반: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 5.3 Test Loop

```
서브에이전트:
  agent: general
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 $test-loop-hd 를 실행하세요.
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 5.4 Scope Review

```
서브에이전트:
  agent: scope-reviewer
  prompt: |
    상태 파일 `/tmp/workflow-state.md`의 Technical Spec을 기준으로
    현재 구현된 코드를 검증하세요.
    프로젝트 루트: {CWD}

    리뷰 입력은 Spec, Edge Cases, diff 요약까지만 사용하세요.
    직접 수정하지 말고 아래 형식으로만 답하세요.
    **Verdict**: APPROVE / CONCERN / REJECT
    **Issues**: [문제 목록 또는 "없음"]
    **Suggestions**: [개선 제안 또는 "없음"]
    **Next Action**: [오케스트레이터가 바로 수행할 1개 액션]
```

#### 5.5 Lint Check

```
서브에이전트:
  agent: general
  prompt: |
    프로젝트 루트 {CWD}에서 Skill tool로 $lint-check-hd 를 실행하세요.
    이슈가 있으면 수정하세요.
    완료 후 "이슈: N건, 수정: Y/N" 형식으로 보고하세요.
```

#### 루프 판정

- `modified == true` → 변경사항 커밋 후 루프 재시작
- `modified == false` → 루프 탈출
- 3회 도달 → 미해결 사항 보고 후 강제 탈출

### Phase 6: 컴포넌트/접근성 리뷰 (조건부)

**작업 유형이 화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정인 경우만 실행. API 연동 유형은 건너뛴다.**

두 에이전트를 **병렬 실행**:

```
Agent tool (병렬 1):
  agent: component-reviewer
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}

    직접 수정하지 말고 아래 형식으로만 답하세요.
    **Verdict**: APPROVE / CONCERN / REJECT
    **Issues**: [문제 목록 또는 "없음"]
    **Suggestions**: [개선 제안 또는 "없음"]
    **Next Action**: [오케스트레이터가 바로 수행할 1개 액션]

Agent tool (병렬 2):
  agent: a11y-reviewer
  prompt: |
    변경된 파일: [git diff --name-only의 .tsx 파일 목록]
    프로젝트 루트: {CWD}

    직접 수정하지 말고 아래 형식으로만 답하세요.
    **Verdict**: APPROVE / CONCERN / REJECT
    **Issues**: [문제 목록 또는 "없음"]
    **Suggestions**: [개선 제안 또는 "없음"]
    **Next Action**: [오케스트레이터가 바로 수행할 1개 액션]
```

Critical 이슈가 있으면 general-purpose 에이전트로 수정을 위임한다.

### Phase 7: PR / Push

- **`$HARD_MODE = false`** (일반):
  ```
  서브에이전트:
    agent: workflow-pr
    prompt: |
      상태 파일 `/tmp/workflow-state.md`를 읽고 PR을 생성하세요.
      프로젝트 루트: {현재 작업 디렉토리}
      PR URL을 반드시 보고하세요.
  ```

- **`$HARD_MODE = true`** (`--hard`):
  PR 생성을 건너뛰고, 현재 브랜치에서 바로 push만 수행한다.
  ```bash
  git push origin $(git branch --show-current)
  ```
  출력: "Phase 7 완료: `{브랜치명}`에 push 완료 (--hard 모드, PR 생략)"

### Phase 8: 성찰

```
서브에이전트:
  agent: workflow-reflection
  prompt: |
    상태 파일 `/tmp/workflow-state.md`를 읽고 워크플로우 성찰을 수행하세요.
    프로젝트 루트: {현재 작업 디렉토리}
    성찰 결과와 스킬 보완점을 보고하세요.
```

---

## Phase 9: 최종 보고

Phase 4~8 에이전트들의 결과를 종합하여 보고서를 작성한다.

```markdown
## Workflow Report

### 1. 작업 요약
- **작업 유형**: [화면 생성/화면 수정/컴포넌트 생성/컴포넌트 수정/API 연동/API 연동 수정]
- **난이도**: [N]/10 (산정) → [M]/10 (체감)
- **PR**: [PR URL]

### 2. 구현 내역
- **변경 파일**: [N]개
- **커밋 수**: [N]개
- **핵심 컴포넌트**: [요약]

### 3. 엣지 케이스 대응
| # | 케이스 | 대응 방법 |
|---|--------|----------|

### 4. 품질 루프 결과
| 단계 | 루프 횟수 | 수정 건수 |
|------|----------|----------|
| simplify | N | M |
| convention | N | M |
| test | N | M |
| scope-review | N | M |
| lint | N | M |

### 5. 컴포넌트/접근성 리뷰
- 컴포넌트 리뷰: [요약]
- 접근성 리뷰: [요약]

### 6. 성찰
[성찰 에이전트 결과]

### 7. 보완점
| # | 대상 스킬 | 보완 내용 | 적용 여부 |
|---|----------|----------|----------|
```

### 보완점 적용

> "위 보완점을 해당 스킬에 반영할까요? (전체/선택/건너뛰기)"

### 정리

상태 파일을 삭제한다:

```bash
rm -f /tmp/workflow-state.md
```

---

## 흐름 요약

```
[유저 대화]
Phase 0: /request → Technical Spec (유저 확인)
Phase 1: 난이도 산정 (1-10)
Phase 2: scope-reviewer 메모
Phase 3: Plan 작성 → 6관점 리뷰 (3+3 병렬) → [에스컬레이션 시: Codex Advisor] → Plan 확정
Phase 3.5: 상태 파일 생성 → "자율 실행 시작"

[자율 실행 — 유저 확인 없이 완주]
Phase 4: workflow-implementer          → 구현 + 커밋
Phase 5: 품질 루프 (오케스트레이터 관리, 최대 3회)
  5.0 build + type-check               → Bash 직접
  5.1 simplify-loop                    → general-purpose 에이전트
  5.2 convention-check                 → general-purpose 에이전트
  5.3 test-loop                        → general-purpose 에이전트
  5.4 scope-reviewer                   → scope-reviewer 에이전트
  5.5 lint-check                       → general-purpose 에이전트
  → 수정 있으면 커밋 후 재시작, 없으면 탈출
Phase 6: component-reviewer + a11y-reviewer (병렬, 컴포넌트 변경 시만)
Phase 7: workflow-pr                   → PR 생성
Phase 8: workflow-reflection           → 성찰

[유저 대화]
Phase 9: 최종 보고 → 보완점 적용 (유저 선택) → 정리
```
