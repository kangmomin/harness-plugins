---
name: lint-check
description: "ESLint + TypeScript 타입 검사 + 접근성(a11y) 종합 코드 품질 검사. 커밋/PR 전 점검, '린트 돌려줘', '코드 품질 검사' 요청 시 사용. start-workflow 품질 루프에서 자동 호출됨."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/lint-check.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.


# Lint Check

ESLint, TypeScript 타입 검사, 접근성(a11y) 검사를 종합적으로 수행하고 보고한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## 공통 변경 범위

`../start-workflow/references/scope-contract.md`를 먼저 읽고 workflow_scope.py의 START_SHA→현재 tree+index 및 소유 untracked 결과를 사용한다. 아래 변경 파일/추가 라인 분석의 입력은 이 `paths`·`patch`·`index_patch`다. dirty 여부로 HEAD 기준을 선택하거나 일반 git diff로 재계산하지 않는다. 범위 오류는 BLOCKED이고, 파일이 없다고 전체 프로젝트로 자동 확대하지 않는다. 명시 custom 검증 명령은 원래 범위를 유지하되 그 명령의 출처를 보고한다.

## 실행 흐름

### Step 1: 검사 대상 파악

1. 공통 범위의 `paths`에서 선택 framework·언어의 소스(.ts/.tsx/.js/.jsx/.vue)를 확인한다.
2. 삭제·symlink는 각각 diff/링크 자체로 검토한다. 기존 사용자 untracked를 자동 포함하지 않는다.
3. custom lintCommand는 그대로 실행한다. 기본 ESLint 전체 명령의 범위는 명령 출처와 함께 보고한다.

### Step 2: 설정된 lint 실행

먼저 FE `skills/config/assets/profile.py resolve --domain fe --cwd "{CWD}"`의 `commands.lintCommand`와 출처를 확인한다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/config/assets/profile.py" run --domain fe --cwd "{CWD}" --key lintCommand
```

- 명시 `lintCommand`는 workspace·환경변수·옵션을 포함한 **원문 그대로** 실행한다. 파일 목록·formatter·`--fix`를 임의 추가하지 않는다. package.scripts.lint 감지 명령도 동일하다.
- 명령이 없거나 비어 있고 감지한 script도 없으면 **설치된 로컬 ESLint**에만 fallback한다. 없으면 SKIP으로 보고한다. 다운로드는 하지 않는다.
- runner가 ESLint일 때만 jsx-a11y/react-hooks 규칙을 해당 분류로 보고한다. 다른 runner는 원래 진단 형식을 보존한다. 파싱하지 못한 출력은 성공 0건으로 바꾸지 않는다.

### Step 3: 타입 검사

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/config/assets/profile.py" run --domain fe --cwd "{CWD}" --key typeCheckCommand
```

`typescript:false` 또는 실효 명령 없음은 SKIP이다. 사용자 typeCheckCommand를 `tsc --noEmit`으로 바꾸지 않는다. 타입 오류를 수집하고 실제 종료 코드와 함께 보고한다.

### Step 4: 접근성 검사

ESLint의 `jsx-a11y` 플러그인 결과에서 접근성 이슈를 추출한다.
추가로 변경된 컴포넌트에서 다음을 코드 분석으로 검사한다:

| 검사 항목 | 기준 |
|----------|------|
| img alt 속성 | 모든 `<img>`에 의미 있는 alt 존재 |
| 버튼 접근성 | `<button>` 또는 `role="button"`에 텍스트/aria-label 존재 |
| 폼 레이블 | 모든 입력 필드에 `<label>` 또는 `aria-label` 연결 |
| 색상 대비 | 하드코딩된 색상 값이 있으면 경고 |
| 키보드 접근 | `onClick`만 있고 `onKeyDown`이 없는 비-인터랙티브 요소 경고 |

### Step 5: 결과 보고

```markdown
## Lint Check 결과

### ESLint
| 구분 | 건수 |
|------|------|
| 에러 | N개 |
| 경고 | M개 |
| 자동 수정 가능 | K개 |

### TypeScript
| 구분 | 건수 |
|------|------|
| 타입 에러 | N개 |
| any 사용 경고 | M개 |

### 접근성 (a11y)
| 이슈 | 파일 | 내용 |
|------|------|------|
| img alt 누락 | src/... | `<img>` alt 속성 없음 |
| 버튼 레이블 없음 | src/... | 아이콘 버튼에 aria-label 없음 |

### Hooks 규칙
| 이슈 | 파일 | 내용 |
|------|------|------|
| 의존성 누락 | src/... | useEffect deps 배열 불완전 |

### 종합
- **총 이슈**: N개 (에러: A, 경고: B, a11y: C)
- **상태**: CLEAN / ISSUES FOUND
```

### Step 6: 자동 수정

수정이 요청·승인된 범위에서만 수행한다. built-in ESLint fallback(`source:runner:eslint`)은 같은 helper에 `--fix`를 추가할 수 있다. custom 명령은 자동 변형하지 않으며, 프로젝트가 문서화한 fix 명령이 있으면 그 명령을 별도로 사용한다. helper는 custom 명령에 `--fix`를 붙이려 하면 실행 전 거부한다. 수정 후 원래 lint·관련 타입 검사를 다시 실행한다.
