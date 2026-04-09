---
name: e2e-test
description: "Playwright 기반 E2E 테스트를 작성하고 실행한다."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

# E2E 테스트

Playwright 기반으로 사용자 시나리오를 E2E 테스트한다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

---

## Prerequisites

### 필요 환경
- **E2E 러너**: Playwright 또는 Cypress (`.hyeondong-config.json`의 `e2eRunner` 참조)
- **개발 서버**: `package.json`의 `scripts.dev` 존재
- **Playwright 브라우저**: 설치 완료 상태

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. `.hyeondong-config.json`의 `e2eRunner` 확인. `none`이면 종료.
2. `playwright.config.ts` 존재 확인.
   - 없으면:
     > "Playwright 설정 파일이 없습니다. 생성할까요? (Y/N)"
     - Y: 기본 `playwright.config.ts` 생성
3. Playwright 브라우저 설치 확인:
   ```bash
   npx playwright install --with-deps chromium
   ```
4. `e2e/` 디렉토리 존재 확인. 없으면 생성.

### Playwright-Vitest 충돌 사전 진단

E2E 테스트 실행 전, Playwright와 Vitest 간 충돌 가능성을 점검한다:

1. `vitest.config.*`에 `globals: true`가 있으면 Playwright의 `expect`와 충돌 가능 → 경고
2. `tsconfig.json`의 `types`에 `vitest/globals`와 `@playwright/test`가 동시에 있으면 → 경고
3. 동일 파일에서 `import { expect } from 'vitest'`와 `import { expect } from '@playwright/test'`가 혼재하면 → 에러 보고
4. 충돌 감지 시 해결 방법 안내:
   > "Playwright와 Vitest의 `expect` 충돌이 감지되었습니다. `vitest.config.ts`에서 E2E 테스트 파일을 exclude하거나, tsconfig에서 types를 분리하세요."

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## E2E Test — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| .hyeondong-config.json | OK / MISSING | e2eRunner 설정 확인 |
| E2E 러너 설정 | OK / MISSING | playwright.config.* |
| Playwright 설치 | OK / MISSING | npx playwright --version |
| 브라우저 설치 | OK / MISSING | chromium 확인 |
| 개발 서버 스크립트 | OK / MISSING | scripts.dev |
| 기존 E2E 테스트 | [N]개 발견 | e2e/*.spec.ts |
```

---

## Execution

### Step 1: 테스트 대상 파악

1. `git diff --name-only`로 변경된 파일 목록을 확인한다.
2. 변경된 파일에서 영향받는 **사용자 흐름(User Flow)**을 파악한다:
   - 페이지 변경 → 해당 페이지 네비게이션 테스트
   - 폼 변경 → 폼 입력/제출 시나리오 테스트
   - API 연동 변경 → 데이터 로딩/에러 처리 테스트
   - 인증 변경 → 로그인/로그아웃 흐름 테스트

3. 기존 E2E 테스트가 있으면 패턴을 파악한다.

### Step 2: 테스트 작성

#### 페이지 네비게이션 테스트

```ts
import { test, expect } from '@playwright/test';

test.describe('페이지 이름', () => {
  test('페이지가 정상적으로 로드된다', async ({ page }) => {
    await page.goto('/path');
    await expect(page).toHaveTitle(/제목/);
    await expect(page.getByRole('heading', { name: '...' })).toBeVisible();
  });
});
```

#### 폼 인터랙션 테스트

```ts
test('폼 제출이 정상적으로 동작한다', async ({ page }) => {
  await page.goto('/form-page');
  await page.getByLabel('이름').fill('테스트');
  await page.getByLabel('이메일').fill('test@example.com');
  await page.getByRole('button', { name: '제출' }).click();
  await expect(page.getByText('성공')).toBeVisible();
});
```

#### API 모킹 테스트

```ts
test('API 에러 시 에러 메시지를 표시한다', async ({ page }) => {
  await page.route('**/api/data', (route) =>
    route.fulfill({ status: 500, body: 'Server Error' })
  );
  await page.goto('/data-page');
  await expect(page.getByText('오류가 발생했습니다')).toBeVisible();
});
```

### Step 3: 테스트 실행

```bash
npx playwright test {테스트 파일들} --reporter=list
```

개발 서버가 필요한 경우, `playwright.config.ts`의 `webServer` 설정을 확인한다.
설정이 없으면 유저에게 개발 서버 실행을 안내한다:

> "E2E 테스트 실행 전 개발 서버가 필요합니다. `playwright.config.ts`에 webServer 설정을 추가하거나,
> 별도 터미널에서 `npm run dev`를 실행해주세요."

### Step 4: 결과 보고

```markdown
## E2E 테스트 결과

| 테스트 파일 | 시나리오 수 | 통과 | 실패 |
|------------|-----------|------|------|
| login.spec.ts | 4 | 4 | 0 |
| search.spec.ts | 3 | 2 | 1 |

### 실패 테스트 (있는 경우)
| 시나리오 | 에러 | 스크린샷 |
|---------|------|---------|
| "검색 결과 표시" | Timeout waiting for element | 첨부 |

### 종합
- **총 시나리오**: N개
- **통과**: M개
- **실패**: K개
- **상태**: ALL PASS / FAILURES FOUND
```

---

## 테스트 원칙

1. **사용자 시나리오 중심**: 기술적 동작이 아닌 사용자 여정을 테스트한다.
2. **접근성 로케이터 우선**: `getByRole`, `getByLabel` > `getByTestId` > CSS 셀렉터.
3. **독립적 테스트**: 각 테스트는 독립적으로 실행 가능해야 한다.
4. **API 모킹 활용**: 외부 API 의존성은 모킹하여 안정적으로 테스트한다.
5. **기존 패턴 준수**: 프로젝트에 이미 E2E 테스트가 있으면 해당 패턴을 따른다.
