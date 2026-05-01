---
name: be-harness__commit-pr
description: "커밋, 브랜치 생성, PR 오픈까지 전체 워크플로우 수행"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/commit-pr.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


0. 이미 생성된 PR 이 있다면 /be-harness:commit-push-mm 만 진행해
1. VERSION 파일이 있다면 patch VERSION 을 올려.
2. 브랜치 생성 (이미 `feat/**` 또는 `hotfix/**` 브랜치에 있다면 이 단계를 건너뛴다)
3. /be-harness:commit-push-mm 를 진행해
4. 작업을 분석하여 브랜치 바로 상위 브랜치로 draft PR 을 열어.

---

## 브랜치 명명 컨벤션 (Step 2 상세)

### 브랜치 생성 규칙

**형식**: `{prefix}/{kebab-case-설명}`

| prefix | 용도 | 예시 |
|--------|------|------|
| `feat` | 기능 추가/변경 | `feat/grpc-e2e-test` |
| `hotfix` | 긴급 버그 수정 | `hotfix/fix-jwt-parsing` |

### 이름 생성 절차

1. **diff 분석**: `git diff`의 변경 파일과 내용을 읽고, **핵심 변경 내용을 2~4 단어로 요약**한다.
2. **prefix 선택 — 사용자에게 질문**:
   diff 분석 결과를 바탕으로 prefix 후보를 제시하고 사용자에게 선택을 받는다.
   > "브랜치 prefix를 선택해주세요:"
   > 1. `feat` — 기능 추가/변경
   > 2. `hotfix` — 긴급 버그 수정
   >
   > (추천: `feat` — diff 분석 기반)
   
   사용자가 번호 또는 prefix명으로 응답하면 해당 값을 사용한다.
3. **kebab-case 변환**: 요약을 영문 소문자 kebab-case로 변환한다.
   - 한글이면 영문으로 번역
   - 공백과 특수문자는 `-`로 치환
   - 연속 `-` 제거, 앞뒤 `-` 제거
4. **최종 확인**: 생성할 브랜치명을 사용자에게 보여주고 승인을 받는다.
   > "브랜치명: `feat/grpc-e2e-test` — 이대로 생성할까요? (Y/수정할 이름 입력)"
   
   사용자가 다른 이름을 입력하면 해당 이름을 사용하되, 이름 규칙 검증은 동일하게 수행한다.

### 이름 규칙 (반드시 준수)

| 규칙 | 올바른 예 | 잘못된 예 |
|------|----------|----------|
| **영문 소문자 + 하이픈만 사용** | `feat/add-grpc-support` | `feat/Add_gRPC_Support` |
| **2~4 단어로 간결하게** | `feat/grpc-e2e-test` | `feat/add-grpc-rpc-e2e-test-automation-support-for-all-services` |
| **구체적 의미 포함** | `feat/cursor-pagination` | `feat/update-code` |
| **prefix 뒤에 `/` 필수** | `feat/user-auth` | `feat-user-auth` |
| **숫자 허용, 선행 숫자 금지** | `feat/oauth2-login` | `feat/2nd-attempt` |

### 자동 검증

브랜치 생성 후 아래 패턴에 매칭되는지 검증한다:
```
^(feat|hotfix)/[a-z][a-z0-9-]{1,40}$
```
매칭 실패 시 이름을 재생성한다.

### worktree 브랜치 처리

현재 브랜치가 `worktree-*` 패턴이면 diff 내용 기반으로 위 규칙에 맞는 이름으로 `git branch -m`한다.
