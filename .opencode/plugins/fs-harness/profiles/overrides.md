# fs-harness Project Overrides

플러그인 스킬/에이전트의 **기본 동작을 그대로 두고**, 프로젝트마다 필요한 **추가 규칙/예외/피드백**을 프로젝트 내부에 레이어로 두기 위한 규약.

플러그인 원본 파일(`fs-harness/skills/{name}/SKILL.md`)은 **절대 수정하지 않는다**. 프로젝트 특화 규칙은 아래 경로의 오버라이드 파일에만 작성한다.

## 경로 구조

```
<repo-root>/.claude/fs-harness/
├── common.md                          # 플러그인 공통 오버라이드 (모든 스킬/에이전트에 적용)
├── skills/
│   ├── commit.md                      # /fs-harness:commit 오버라이드
│   ├── request.md                     # /fs-harness:request 오버라이드
│   ├── start-workflow.md              # /fs-harness:start-workflow 오버라이드
│   ├── convention-check.md
│   ├── e2e-test.md
│   └── ... (스킬 이름과 동일하게)
└── agents/
    ├── workflow-implementer.md        # fs-harness:workflow-implementer 에이전트 오버라이드
    ├── code-verifier.md
    └── ... (에이전트 이름과 동일하게)
```

모든 파일은 선택적이다. 없으면 해당 레이어를 건너뛴다.

## 병합 규칙

스킬/에이전트 실행 시 로드 순서:

1. **플러그인 기본 동작** — `fs-harness/skills/{name}/SKILL.md` 또는 `fs-harness/agents/{name}.md` (Claude Code가 로드)
2. **공통 오버라이드** — `.claude/fs-harness/common.md` 가 있으면 먼저 읽는다
3. **스킬별 오버라이드** — `.claude/fs-harness/skills/{name}.md` 또는 `.claude/fs-harness/agents/{name}.md` 가 있으면 읽는다

### 충돌 해결

| 상황 | 규칙 |
|------|------|
| 오버라이드가 새 규칙 추가 | 플러그인 기본 동작 + 오버라이드 규칙 모두 적용 |
| 오버라이드가 특정 단계 변경 | 해당 단계만 오버라이드 지시로 치환, 나머지는 플러그인 기본 따름 |
| 오버라이드가 특정 단계 skip 지시 | 그 단계를 SKIPPED로 처리 |
| 오버라이드와 플러그인 기본 동작 충돌 | **오버라이드가 우선** |
| 오버라이드가 빈 파일 | 없는 것과 동일 |

스킬이 여러 Phase/Step으로 구성되면, 오버라이드는 "어느 Phase에 어떤 추가 규칙을 적용하는지" 명확히 기술해야 한다.

## 오버라이드 파일 포맷

frontmatter는 선택. 본문은 자유로운 markdown. 단, 아래 섹션을 **권장**한다:

```markdown
---
scope: skill:commit          # 또는 agent:workflow-implementer, common
applies-to: fs-harness@0.1.0+ # 최소 플러그인 버전
updated: 2026-04-21
---

# Project Override: /fs-harness:commit

## 추가 규칙
- [이 프로젝트에서만 적용되는 규칙들]

## 변경 사항
- [플러그인 기본 동작 중 일부를 이렇게 대체한다]

## Skip 지시
- [특정 단계를 건너뛰어야 한다면 이유와 함께]

## 참고
- 이 파일은 start-workflow Phase 9 보완점이 자동으로 append 될 수 있다.
```

자유 markdown만 있어도 된다. 스킬이 읽어서 문맥에 맞게 반영한다.

## 보완점 자동 반영 (2-Tier 경로 + 도메인 라우팅)

Phase 8 회고에서 도출된 보완점은 **대상 도메인별로 분류**된 뒤, 유저가 선택한 경로로 반영된다.

### 도메인 라우팅

| 보완점 대상 | 저장 경로 | submit-feedback |
|-----------|----------|-----------------|
| BE 스킬/에이전트 | `.claude/be-harness/...` | `/be-harness:submit-feedback` |
| FE 스킬/에이전트 | `.claude/fe-harness/...` | `/fe-harness:submit-feedback` |
| 풀스택 계약/오케스트레이션 | `.claude/fs-harness/...` | `/fs-harness:submit-feedback` |

### Tier 1: 로컬 오버라이드 (기본값)

- 적용 범위: 현 프로젝트만
- 경로: 도메인별 로컬 오버라이드 파일
- 플러그인 원본은 건드리지 않음

### Tier 2: 플러그인 레포 community-feedback PR (선택)

- 적용 범위: 모든 사용자 (단, 유지보수자 큐레이션 후)
- 경로: 각 플러그인의 `community-feedback/{skills,agents,common}/...`
- 제출: 도메인별 `submit-feedback` 이 gh CLI로 fork/clone → append → PR
- **범용성 있는 피드백**에만 권장

Phase 8 옵션:
1. **로컬만** (default) — 각 도메인의 Tier 1 에만 저장
2. **로컬 + PR** — 도메인별로 독립 PR (be/fe/fs 병렬 가능)
3. **건너뛰기**

각 submit-feedback 은 독립 동작. 한쪽이 `[SKIPPED:*]` 나 FAILED 여도 다른 도메인 PR은 계속 진행.

## 전역 컨벤션 파일과의 차이

| 구분 | 용도 | 파일 경로 |
|------|------|----------|
| profile | 빌드/테스트 명령, 디렉토리 경로 등 **값(setting)** | `.claude/fs-harness.local.md` |
| projectConventions | `convention-check` 가 검사 기준으로 삼는 컨벤션 문서 | profile의 `projectConventions` 필드 (예: `CLAUDE.md`) |
| **Project Overrides (이 문서)** | **각 스킬/에이전트에 대한 프로젝트별 동작 조정/추가 규칙** | `.claude/fs-harness/{skills,agents}/{name}.md` |

Profile 은 "값", projectConventions 는 "코드 규약의 참조 문서", Overrides 는 "스킬 그 자체의 행동 변형" — 역할이 분리되어 있다.

## 로드 절차 (각 스킬 공통)

```
1. 스킬 실행이 시작되면 아래 순서로 Read:
   a. .claude/fs-harness/common.md (있으면)
   b. .claude/fs-harness/skills/{본인 스킬 이름}.md (있으면)
2. 위 내용을 "프로젝트 추가 지시"로 해석하여 스킬 본문 흐름에 반영
3. 각 단계가 오버라이드에 의해 수정/추가/제거되었는지 판단
4. 최종 결과 보고 시 어떤 오버라이드가 적용되었는지 명시
```

에이전트도 동일 — 본인 프롬프트 실행 전에 `.claude/fs-harness/agents/{name}.md` 를 Read.

## 주의

- 오버라이드 파일은 **프로젝트 저장소에 커밋**되어야 팀 전체에 일관 적용된다.
- 프라이빗/개인 설정은 `.claude/fs-harness/common.local.md` 처럼 `.local.md` 접미사를 쓰고 `.gitignore` 대상으로 둘 수 있다 (선택).
- 오버라이드를 통해 **플러그인 기본 동작을 역행**(예: "빌드 검증 건너뛰기")하는 건 가능하지만, 이유는 반드시 파일에 기록한다.
