---
name: hyeondong-doctor-hd
description: "hyeondongs-harness 플러그인의 모든 의존성 상태를 한 번에 진단한다."
---

# hyeondong's harness Doctor

플러그인이 정상 동작하기 위한 모든 의존성을 한 번에 점검하고, 문제가 있으면 해결 방법을 안내한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## 점검 항목

### 1. 런타임 환경

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| Node.js 설치 | `node --version` | 전체 |
| Node.js 버전 | 18+ 이상인지 확인 | 전체 |
| 패키지 매니저 | lock 파일로 판별 (pnpm/yarn/npm/bun) | 전체 |
| 패키지 설치 상태 | `node_modules/` 존재 확인 | 전체 |

### 2. 프로젝트 설정

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| .hyeondong-config.json | 파일 존재 및 유효한 JSON 확인 | 전체 |
| package.json | 파일 존재 확인 | 전체 |
| TypeScript 설정 | `tsconfig.json` 존재 확인 | lint-check, convention-check |
| CLAUDE.md | 파일 존재 확인 | convention-check |

### 3. 코드 품질 도구

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| ESLint 설정 | `.eslintrc.*` / `eslint.config.*` 존재 확인 | lint-check |
| ESLint 실행 | `npx eslint --version` | lint-check |
| Prettier 설정 | `.prettierrc.*` 존재 확인 | lint-check |
| TypeScript 컴파일 | `npx tsc --noEmit` (dry-run) | lint-check |

### 4. 테스트 환경

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| 테스트 러너 설정 | `vitest.config.*` / `jest.config.*` 확인 | unit-test |
| 테스트 러너 실행 | `npx vitest --version` / `npx jest --version` | unit-test |
| E2E 러너 설정 | `playwright.config.*` / `cypress.config.*` 확인 | e2e-test |
| E2E 러너 실행 | `npx playwright --version` | e2e-test |
| Playwright 브라우저 | `npx playwright install --dry-run` 상태 확인 | e2e-test |

### 5. 빌드 환경

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| 빌드 스크립트 | `package.json`의 `scripts.build` 존재 확인 | start-workflow |
| 개발 서버 스크립트 | `package.json`의 `scripts.dev` 존재 확인 | e2e-test |
| Storybook | `.storybook/` 디렉토리 확인 | component |

### 6. 외부 도구 (선택)

| 항목 | 점검 방법 | 관련 스킬 |
|------|----------|----------|
| Codex MCP | `mcp__codex__codex` 호출 가능 여부 | start-workflow (난이도 7+) |

---

## 실행 흐름

1. 모든 항목을 **병렬로** 점검한다 (독립적인 검사는 동시에).
2. 결과를 수집하여 아래 형식으로 출력한다.

---

## 출력 형식

```markdown
## hyeondong's harness Doctor Report

### 런타임 환경
| 항목 | 상태 | 비고 |
|------|------|------|
| Node.js 설치 | OK / MISSING | 버전: vX.Y.Z |
| Node.js 버전 | OK / OUTDATED | 18+ 필요 |
| 패키지 매니저 | OK | pnpm / yarn / npm / bun |
| 패키지 설치 | OK / MISSING | node_modules 확인 |

### 프로젝트 설정
| 항목 | 상태 | 비고 |
|------|------|------|
| .hyeondong-config.json | OK / MISSING | 없으면 /hyeondong-init 실행 필요 |
| package.json | OK / MISSING | |
| tsconfig.json | OK / MISSING | |
| CLAUDE.md | OK / MISSING | 컨벤션 기준 |

### 코드 품질 도구
| 항목 | 상태 | 비고 |
|------|------|------|
| ESLint 설정 | OK / MISSING | |
| ESLint 실행 | OK / FAIL | |
| Prettier 설정 | OK / MISSING | 선택 |
| TypeScript 컴파일 | OK / FAIL | tsc --noEmit |

### 테스트 환경
| 항목 | 상태 | 비고 |
|------|------|------|
| 테스트 러너 설정 | OK / MISSING | vitest / jest |
| 테스트 러너 실행 | OK / FAIL | |
| E2E 러너 설정 | OK / MISSING / SKIP | playwright / cypress |
| E2E 러너 실행 | OK / FAIL / SKIP | |
| Playwright 브라우저 | OK / MISSING / SKIP | |

### 빌드 환경
| 항목 | 상태 | 비고 |
|------|------|------|
| 빌드 스크립트 | OK / MISSING | scripts.build |
| 개발 서버 스크립트 | OK / MISSING | scripts.dev |
| Storybook | OK / MISSING | 선택 |

### 외부 도구
| 항목 | 상태 | 비고 |
|------|------|------|
| Codex | OK / MISSING | 선택 (난이도 7+ 전용) |

---

### 종합
- **필수 항목**: [N]개 중 [M]개 OK
- **선택 항목**: [N]개 중 [M]개 OK
- **상태**: ALL CLEAR / ISSUES FOUND

### 해결 필요 (ISSUES FOUND인 경우)
| # | 항목 | 해결 방법 |
|---|------|----------|
| 1 | [항목] | `$hyeondong-init-hd` 실행 또는 [구체적 안내] |
```

---

## 필수 vs 선택 분류

| 항목 | 분류 | 이유 |
|------|------|------|
| Node.js 설치/버전 | **필수** | 모든 스킬에서 사용 |
| package.json | **필수** | 프로젝트 기본 |
| .hyeondong-config.json | **필수** | 플러그인 설정 |
| TypeScript 설정 | **필수** | 타입 검사 |
| ESLint 설정 | **필수** | 린트 검사 |
| 테스트 러너 | **필수** | 단위 테스트 |
| 빌드 스크립트 | **필수** | 빌드 검증 |
| CLAUDE.md | **필수** | 컨벤션 기준 |
| Prettier | 선택 | 포매팅 (ESLint로 대체 가능) |
| E2E 러너 | 선택 | hyeondong-config에서 none 가능 |
| Storybook | 선택 | hyeondong-config에서 false 가능 |
| Codex | 선택 | 난이도 7+ Plan 리뷰 전용 |
| Playwright 브라우저 | 선택 | E2E 사용 시만 필수 |
