---
name: lint-check
description: "ESLint + TypeScript 타입 검사 + 접근성(a11y) 종합 코드 품질 검사"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/lint-check.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# Lint Check

ESLint, TypeScript 타입 검사, 접근성(a11y) 검사를 종합적으로 수행하고 보고한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## 실행 흐름

### Step 1: 검사 대상 파악

1. `git diff --name-only`로 변경된 파일 목록을 확인한다.
2. `.ts`, `.tsx`, `.js`, `.jsx` 파일만 필터링한다.
3. 변경된 파일이 없으면 전체 프로젝트를 대상으로 한다.

### Step 2: ESLint 검사

```bash
npx eslint {대상 파일들} --format=stylish
```

- 에러와 경고를 분류한다.
- `eslint-plugin-jsx-a11y` 규칙 위반은 별도로 **접근성 이슈**로 분류한다.
- `eslint-plugin-react-hooks` 규칙 위반은 별도로 **Hooks 규칙 위반**으로 분류한다.

### Step 3: TypeScript 타입 검사

profile의 `typeCheckCommand` 를 실행한다:

```bash
{typeCheckCommand}
```

`typeCheckCommand` 가 비어있으면 이 단계를 SKIP한다 (TypeScript 미사용 프로젝트 대응).

- 타입 에러를 수집한다.
- `any` 타입 사용을 경고로 보고한다.

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

### Step 6: 자동 수정 (선택)

자동 수정 가능한 이슈가 있으면:

> "자동 수정 가능한 이슈가 [N]건 있습니다. 자동 수정할까요? (Y/N)"

Y:
```bash
npx eslint {대상 파일들} --fix
```

수정 후 재검사하여 남은 이슈만 보고한다.
