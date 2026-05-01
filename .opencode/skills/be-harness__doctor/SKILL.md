---
name: be-harness__doctor
description: "be-harness 환경 상태를 진단한다. profile 유효성, 명령 실행 가능성, Git 상태, convention 설정을 점검."
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/be-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/be-harness/skills/doctor.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# be-harness Doctor

profile을 읽고, be-harness 스킬이 정상 동작할 수 있는지 진단한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다 (profile language 필드 기준).

---

## 점검 항목

| # | 항목 | 확인 방법 | 필수/선택 |
|---|------|----------|----------|
| 1 | `.claude/be-harness.local.md` | Read | 필수 |
| 2 | `preset` 필드 | profile 파싱 | 필수 |
| 3 | `buildCommand` 실행 가능 | `command -v` 또는 dry-run | 필수 |
| 4 | `testCommand` 실행 가능 | 동일 | 필수 |
| 5 | `lintCommand` 실행 가능 | 동일 | 선택 |
| 6 | `typeCheckCommand` 실행 가능 | 동일 | 선택 |
| 7 | `sourceDirs` 경로 존재 | `test -d` | 필수 |
| 8 | `testDirs` 경로 존재 | `test -d` | 선택 |
| 9 | Git 초기화 | `git rev-parse --is-inside-work-tree` | 필수 |
| 10 | `mainBranch` 존재 | `git rev-parse --verify <branch>` | 필수 |
| 11 | `.convention-check.json` | Read | 선택 |
| 12 | `projectConventions`의 각 파일 | Read | 선택 |
| 13 | `serverUrl` 포맷 유효성 | 정규식 | 선택 |
| 14 | `e2eEnabled && runServerCommand` | 두 값 조합 체크 | 정보 |
| 15 | `.claude/be-harness/` 오버라이드 디렉토리 | `test -d` | 선택 |
| 16 | `.claude/be-harness/common.md` | `test -f` | 선택 |
| 17 | `.claude/be-harness/skills/*.md` 개수 | Glob | 정보 |
| 18 | `.claude/be-harness/agents/*.md` 개수 | Glob | 정보 |

## 보고 형식

```markdown
## be-harness Doctor

### 필수 항목
| 항목 | 상태 | 비고 |
|------|------|------|
| profile | OK / MISSING | 경로 또는 생성 안내 |
| preset | OK (go/node/custom) / INVALID | |
| buildCommand | OK / NOT_FOUND / EMPTY | 실행 명령 |
| testCommand | OK / NOT_FOUND / EMPTY | 실행 명령 |
| sourceDirs | OK / MISSING_PATHS | 누락 경로 |
| Git | OK / NOT_INITIALIZED | |
| mainBranch | OK / NOT_FOUND | 브랜치 이름 |

### 선택 항목
| 항목 | 상태 | 비고 |
|------|------|------|
| lintCommand | OK / EMPTY | |
| typeCheckCommand | OK / EMPTY | |
| testDirs | OK / MISSING_PATHS | |
| .convention-check.json | OK / MISSING | convention-check 기본값 사용 |
| projectConventions | OK / MISSING_FILES | |
| serverUrl | OK / INVALID | |
| .claude/be-harness/ 오버라이드 디렉토리 | OK / MISSING | 없으면 `/be-harness:init` 또는 수동 생성 |
| 오버라이드 파일 개수 | common:Y/N, skills:N개, agents:N개 | 로드 순서 표시 |

### 종합 판정
| | |
|---|---|
| 필수 | PASS / FAIL |
| 선택 | PASS / WARN |

### 권장 조치
- 없으면 "현재 설정으로 바로 워크플로우 실행 가능" 출력.
- 있으면 각 항목별 간단한 조치 문구를 제시 (예: "`/be-harness:init` 재실행").
```

## 실행 절차

1. `.claude/be-harness.local.md` 를 Read한다. 없으면 `MISSING`으로 표기하고 `/be-harness:init` 실행을 권장한 뒤 종료한다.
2. YAML frontmatter를 파싱한다. 잘못된 포맷이면 `INVALID`로 표기.
3. 각 명령에 대해 첫 번째 토큰(`go`, `npm`, `make` 등)이 PATH에 있는지 `command -v` 로 확인.
4. `sourceDirs`, `testDirs` 의 각 경로를 `test -d`로 확인.
5. Git 초기화 및 `mainBranch` 존재 확인.
6. 결과를 표 형식으로 보고.

## 주의사항

- 명령을 실제로 실행하지 않는다 (빌드/테스트는 느리고 side effect 발생 가능).
- `run_in_background` 관련 명령(runServerCommand)은 존재 여부만 확인.
- `preset: custom` 인 경우 프리셋 기본값을 적용하지 않고 모든 값이 명시되었는지 확인한다.
