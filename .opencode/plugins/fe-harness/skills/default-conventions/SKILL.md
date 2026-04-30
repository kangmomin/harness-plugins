---
name: default-conventions
description: "React/Next.js/TypeScript 프론트엔드 개발 및 리뷰 가이드라인 (Local Convention)"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/fe-harness/common.md` — 플러그인 공통 (모든 스킬/에이전트에 적용)
- `.claude/fe-harness/skills/default-conventions.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.


# 프론트엔드 개발 및 리뷰 가이드라인 (Local Convention)

당신은 프론트엔드 프로젝트의 코드를 수정하거나 리뷰할 때 반드시 아래의 규칙을 준수해야 하는 전문 개발 파트너입니다.

## 1. 컴포넌트 구조

### 1.1 컴포넌트 파일 구조
- 하나의 파일에는 **하나의 export 컴포넌트**만 정의한다.
- 컴포넌트 내부에서만 사용되는 헬퍼 컴포넌트는 같은 파일에 정의할 수 있으나, export하지 않는다.
- 파일 내 순서:
  1. import 문
  2. 타입/인터페이스 정의
  3. 상수 정의
  4. 컴포넌트 정의 (named export function)
  5. (선택) 내부 헬퍼 컴포넌트

### 1.2 Props 설계
- Props 타입은 `interface`로 정의한다 (`type` 대신).
- Props 이름은 `{ComponentName}Props` 형식이다.
- **콜백 Props**: `on` 접두사 사용 (예: `onClick`, `onSubmit`, `onChange`).
- **Boolean Props**: `is`, `has`, `should` 접두사 사용 (예: `isLoading`, `hasError`).
- **children**: 레이아웃/컨테이너 컴포넌트에서만 사용.

### 1.3 컴포넌트 선언
- **named export function** 사용 (`export default` 금지, 페이지 컴포넌트 제외).
- Arrow function이 아닌 `function` 키워드 사용.

```tsx
// OK
export function ProductCard({ title, price }: ProductCardProps) { ... }

// NOT OK
const ProductCard = ({ title, price }: ProductCardProps) => { ... };
export default ProductCard;
```

- Next.js 페이지/레이아웃만 `export default` 허용.

## 2. 상태관리

### 2.1 서버 상태 vs 클라이언트 상태
- **서버 상태** (API 데이터): TanStack Query / SWR로 관리한다.
- **클라이언트 상태** (UI 상태): `useState` / `useReducer` 또는 Zustand로 관리한다.
- 서버 상태를 클라이언트 상태 저장소(Redux, Zustand)에 복사하지 않는다.

### 2.2 React Query 패턴
- Query key는 배열 형태로, 계층적으로 구성한다: `['users', userId, 'posts']`
- Custom hook으로 감싸서 사용한다:
  ```tsx
  export function useUser(userId: string) {
    return useQuery({
      queryKey: ['users', userId],
      queryFn: () => fetchUser(userId),
    });
  }
  ```
- Mutation도 custom hook으로 감싼다.

### 2.3 useState 최소화
- 파생 가능한 값은 `useState` 대신 계산한다.
- 여러 관련 상태는 `useReducer`로 묶는다.
- 전역 필요 없는 상태는 가장 가까운 컴포넌트에서 관리한다.

## 3. API 호출

### 3.1 API 클라이언트
- `fetch` 또는 `axios` 인스턴스를 하나의 파일에서 생성하고 재사용한다.
- 인증 토큰 주입은 인터셉터/래퍼에서 처리한다.
- Base URL은 환경 변수로 관리한다.

### 3.2 에러 처리
- API 에러는 일관된 형식으로 변환한다:
  ```ts
  interface ApiError {
    status: number;
    message: string;
    code?: string;
  }
  ```
- 에러 바운더리(`ErrorBoundary`)를 활용하여 컴포넌트 트리의 에러를 처리한다.
- 로딩/에러/성공 상태를 명시적으로 처리한다. 누락된 상태가 있으면 위반.

## 4. 스타일링

### 4.1 Tailwind CSS (기본)
- 클래스명이 길면 `cn()` (clsx/tailwind-merge) 유틸리티로 조합한다.
- 반응형: `sm:`, `md:`, `lg:` 접두사로 처리한다.
- 다크모드: `dark:` 접두사로 처리한다.
- 인라인 `style` 속성은 동적 값(JS 계산 필요)일 때만 사용한다.

### 4.2 컴포넌트 스타일 배치
- 스타일 관련 로직은 컴포넌트 파일 내에 유지한다.
- 공통 스타일 유틸리티는 `styles/` 또는 `lib/` 디렉토리에 배치한다.

## 5. TypeScript

### 5.1 타입 안전성
- `any` 사용 금지. 부득이하면 `unknown`으로 대체하고 타입 가드를 사용한다.
- 이벤트 핸들러 타입: `React.MouseEvent<HTMLButtonElement>` 등 구체적 타입 사용.
- API 응답 타입은 별도 파일에서 관리한다 (`types/` 또는 `api/types.ts`).

### 5.2 제네릭 활용
- 재사용 컴포넌트는 제네릭으로 타입 유연성을 제공한다:
  ```tsx
  interface ListProps<T> {
    items: T[];
    renderItem: (item: T) => React.ReactNode;
  }
  ```

### 5.3 Enum 대신 const assertion
```ts
// OK
const STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  ERROR: 'error',
} as const;
type Status = typeof STATUS[keyof typeof STATUS];

// NOT OK
enum Status { IDLE, LOADING, ERROR }
```

## 6. 성능

### 6.1 불필요한 리렌더링 방지
- `React.memo`: 순수 표시 컴포넌트 + 자주 리렌더링되는 부모에서만 사용.
- `useMemo` / `useCallback`: 실제 성능 문제가 확인된 경우에만 사용.
- 조기 최적화 금지 — 먼저 측정하고, 필요하면 최적화한다.

### 6.2 번들 사이즈
- 대규모 라이브러리는 트리 셰이킹 가능한 import 방식을 사용한다:
  ```ts
  // OK
  import { debounce } from 'lodash-es';
  
  // NOT OK
  import _ from 'lodash';
  ```
- Dynamic import (`next/dynamic`, `React.lazy`)로 코드 스플리팅한다.

### 6.3 이미지 최적화
- Next.js: 반드시 `next/image`의 `Image` 컴포넌트를 사용한다.
- `width`, `height` 또는 `fill` 속성을 반드시 지정한다.

## 7. 커밋 및 PR 운영 지침

- **커밋 메시지 형식**: [Prefix]: 간략한 설명
- **Prefix**: Add, Fix, Del, Refactor, Style, Doc, Test, Chore, WIP
- **PR 제목**: [commit-prefix]: 작업내용

## 8. 작업 프로세스

- **분석**: 작업 시작 전 현재 코드와 컨벤션의 일치 여부를 먼저 분석한다.
- **구현**: 위 규칙에 따라 코드를 작성한다.
- **최종 코드리뷰**: 작업 종료 전 Props 설계, 상태관리, 에러 처리를 스스로 리뷰한다.
- **결과 보고**: 모든 응답의 마지막에 아래 양식으로 보고를 수행한다.

## 최종 작업 보고 (Final Report)
1. **수정 사항 요약**
    - (컨벤션 준수 여부 및 주요 변경점 정리)
2. **예상되는 사이드 이펙트**
    - (인접 컴포넌트 영향도 및 상태 무결성 리스크 분석)
3. **영향 받는 페이지/컴포넌트**
    - 대상: [컴포넌트/페이지 목록]
    - UI 변경: (레이아웃/스타일/인터랙션 변화)
4. **접근성 영향**
    - (a11y 관련 변경 사항)
