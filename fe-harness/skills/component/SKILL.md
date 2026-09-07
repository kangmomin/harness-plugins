---
name: component
description: "컴포넌트 보일러플레이트를 자동 생성한다. '컴포넌트 만들어줘', 새 컴포넌트 스캐폴딩이 필요할 때 사용. .claude/fe-harness.local.md 설정에 따라 스타일, 테스트, Storybook 파일을 함께 생성."
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
argument-hint: <컴포넌트 이름 또는 설명>
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/component.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.


# Component Generator

`.claude/fe-harness.local.md` 설정에 따라 컴포넌트 보일러플레이트를 생성한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## Prerequisites

먼저 현재 설치된 FE `skills/config/assets/profile.py resolve --domain fe --cwd "{CWD}"`로 실효 설정을 읽는다. primary가 없고 유효 legacy만 있으면 정상 진행하며 JSON에는 쓰지 않는다. 둘 다 없는 경우에만 init으로 설정 생성을 안내한다. 아래의 profile 표/설정 조회는 모두 이 실효 결과를 뜻한다.


- 실효 profile 필요. 레거시는 읽기 전용으로 정상 지원한다.

---

## 실행 흐름

### Step 1: 설정·지원 조합 확인

실효 profile의 framework·typescript·testRunner·uiLibrary·componentPattern·storybook을 읽고 기존 파일과 package 의존성이 선택과 일치하는지 확인한다. `vite`는 이 하네스에서 React + Vite 선택이다. Vue Vite 등 다른 조합이면 프로젝트 템플릿을 먼저 확인하고 임의 React 생성은 하지 않는다.

| framework | 언어 | 단위 러너 | 생성 형태 |
|-----------|------|-----------|-----------|
| nextjs / vite(React) / cra | TypeScript | Vitest / Jest | .tsx 컴포넌트·테스트, .ts 배럴·스토리 |
| nextjs / vite(React) / cra | JavaScript | Vitest / Jest | .jsx 컴포넌트·테스트, .js 배럴·스토리 |
| nuxt(Vue 3) | TypeScript / JavaScript | Vitest | .vue SFC(script lang 분기), .ts/.js 테스트·배럴·스토리 |
| nuxt + Jest / 알 수 없는 framework·언어 / Vue + React 전용 UI | 해당 조합 | 해당 러너 | 파일 생성 전 BLOCKED:UNSUPPORTED_COMBINATION; 기존 프로젝트의 검증된 템플릿이 제공되면 그 경로 사용 |

Nuxt의 기본 UI는 tailwind/css-modules를 지원한다. Vue에 styled-components/shadcn/mui/antd의 React 템플릿을 적용하지 않는다. 이 helper는 framework-neutral 컴포넌트 골격이다. Next client boundary, Nuxt auto-import/composable/SSR, CRA 설정을 포함한 앱 통합은 기존 프로젝트 규칙을 별도로 따른다.

테스트 API는 Vitest면 `vitest`, Jest면 `@jest/globals`에서 **명시 import**한다. globals 설정을 요구하지 않는다. Testing Library는 React/Vue에 맞춰 선택한다. Storybook은 선택한 renderer의 패키지·기존 구성에서 사용 가능할 때만 생성하며 JS에는 `import type`/interface/타입 주석을 쓰지 않는다. 누락 의존성을 자동 설치하지 않는다.

### Step 2: 컴포넌트 정보 수집

`$ARGUMENTS`에서 컴포넌트 이름을 추출한다. 없으면 질문한다:

> "어떤 컴포넌트를 생성할까요? (이름과 간단한 설명)"
> 예: `SearchBar 상품 검색 입력 필드`

추가 질문:

> "컴포넌트 배치 경로를 선택해주세요:"

`componentPattern`에 따라:
- **feature-based**: `src/features/{도메인}/components/{ComponentName}/`
- **atomic**: `src/components/{atoms|molecules|organisms}/{ComponentName}/`
- **flat**: `src/components/{ComponentName}/`

기존 프로젝트의 디렉토리 구조를 `Glob`으로 탐색하여 적합한 경로를 제안한다.

### Step 3: 템플릿 생성·적용·검증

선택 조합을 helper에 전달한다. helper는 JSON만 반환하며 프로젝트 파일을 쓰지 않는다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/component/assets/component_templates.py" \
  --name "{ComponentName}" --framework "{framework}" --typescript "{true|false}" \
  --runner "{testRunner}" --ui "{uiLibrary}"
```

storybook:true이면 `--storybook`을 추가한다. BLOCKED(exit 2)는 파일을 하나도 쓰지 않고 사용자에게 원인을 알린다. 이름·경로가 부정확하면 임의 정규화하지 않는다.

- `files` 객체에서 반환한 확장자·import·언어를 그대로 시작점으로 삼고 요청된 props/동작에 맞춰 최소 수정한다. React와 Vue 파일을 섞지 않는다.
- 목적지에 같은 파일이 있으면 기존 내용을 읽어 요청된 변경으로 통합한다. 새 보일러플레이트로 전체 덮어쓰지 않는다. 파일 생성 전 충돌 목록을 확인한다.
- 기본 scaffold는 React children / Vue slot 콘텐츠를 전달하며 테스트는 그 콘텐츠가 렌더되는지 확인한다. 도메인 동작 테스트는 요청된 관측 가능한 요구사항이 있을 때 추가한다.
- 스타일 파일은 uiLibrary별로 생성하고, 스토리는 해당 renderer의 형식을 사용한다. 인터랙티브 요소를 추가했으면 실제 역할·레이블·키보드 동작을 확인한다.
- 실효 build/type/unit 명령으로 새 파일을 검증한다. TypeScript false는 타입 검사를 SKIP하고 JS 컴파일·선택 runner 검증은 수행한다. Vitest globals:false에서도 테스트가 실행돼야 한다.

저장소 fixture `tests/fixtures/fe-components/verify.py`는 생성 helper를 직접 실행해 React/Vue·JS/TS·Vitest/Jest 지원 조합을 Vite build, vue-tsc, 실제 두 runner로 검증한다. 이는 Next/Nuxt/CRA 앱 전체나 Storybook 브라우저 빌드 검증과 구별한다. 프로젝트 검증에 실패하면 생성 완료 PASS를 보고하지 않는다.

### Step 4: 결과 보고

```markdown
## 컴포넌트 생성 완료

| 파일 | 경로 |
|------|------|
| 컴포넌트 | `src/features/auth/components/LoginForm/LoginForm.tsx` |
| 테스트 | `src/features/auth/components/LoginForm/LoginForm.test.tsx` |
| 스토리 | `src/features/auth/components/LoginForm/LoginForm.stories.tsx` |
| 배럴 | `src/features/auth/components/LoginForm/index.ts` |

선택한 framework·언어·runner, 실제 실행한 검증과 SKIP/미검증 범위를 함께 보고한다.
```

---

## 컴포넌트 네이밍 규칙

| 규칙 | 올바른 예 | 잘못된 예 |
|------|----------|----------|
| PascalCase | `SearchBar` | `searchBar`, `search-bar` |
| 의미 있는 이름 | `ProductCard` | `Card1` |
| 접미사 패턴 | `LoginForm`, `UserList`, `NavBar` | `Login`, `Users` |
