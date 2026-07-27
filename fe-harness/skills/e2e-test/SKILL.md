---
name: e2e-test
description: "Playwright 기반 E2E 테스트를 작성하고 실행한다. 화면/플로우 구현 후 'E2E 테스트 돌려줘', 실제 브라우저 검증이 필요할 때 사용."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/e2e-test.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.


# E2E 테스트

Playwright 기반으로 사용자 시나리오를 E2E 테스트한다.

## Language Rule

유저와의 모든 대화는 profile의 `language` 값(기본 `ko`, 한국어)을 따른다.

---

## Prerequisites

### 필요 환경
- **E2E 러너**: Playwright 또는 Cypress (`.claude/fe-harness.local.md`의 `e2eRunner` 참조)
- **개발 서버**: `package.json`의 `scripts.dev` 존재
- **Playwright 브라우저**: 설치 완료 상태

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. `.claude/fe-harness.local.md`의 `e2eRunner` 확인. `none`이면 종료.
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
| .claude/fe-harness.local.md | OK / MISSING | e2eRunner 설정 확인 |
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

4. **Spec 엣지 케이스 승계** (Spec에 `EC-*` ID가 있을 때): `/fe-harness:request` Phase 4가 만든 엣지 케이스 표(start-workflow에서 호출된 경우 상태 파일의 `## Edge Cases`)의 **각 행을 빠짐없이** 시나리오로 포함한다. 위 1~3의 자체 도출은 그대로 유지한다 — Spec이 놓친 흐름을 잡는 독립 축이다.
   - 브라우저에서 재현 불가능한 케이스(외부 서비스 장애, 시간 경과 필요 등)만 예외로 두고 `UNCOVERED:{사유}`로 리포트에 남긴다. **"검증이 번거롭다"는 예외 사유가 아니다.**
   - Spec에 엣지 케이스 표가 없거나 ID가 없으면 승계를 건너뛰고 리포트에 `대조 기준 없음`으로 표기한다.

### Step 2: 테스트 작성

**Spec에서 승계한 시나리오는 테스트 title 앞에 ID를 붙인다** — `test('[EC-03] 재고가 0이면 품절 배지가 보인다', ...)`.
Step 4 리포트와 `start-workflow` Phase 7.7 read-back이 이 ID로 커버리지를 대조하므로, ID를 바꾸거나 생략하지 않는다. 자체 도출 시나리오는 접두 없이 둔다.

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

### Spec 커버리지
| Spec 엣지 케이스 | 대응 테스트 | 상태 |
|-----------------|------------|------|
| EC-01 | `[EC-01] ...` | 실행됨 |
| EC-02 | — | `UNCOVERED:외부 결제 위젯 재현 불가` |

- Spec 엣지 케이스 [N]건 중 [M]건 실행, [K]건 미커버 (Spec에 ID가 없으면 `대조 기준 없음`)

### 종합
- **총 시나리오**: N개
- **통과**: M개
- **실패**: K개
- **미커버**: L개
- **상태**: ALL PASS / FAILURES FOUND / PASS WITH UNCOVERED
```

| 상태 | 조건 |
|------|------|
| `ALL PASS` | 실패 0건 **AND** 미커버 0건 |
| `PASS WITH UNCOVERED` | 실패 0건 **AND** 미커버 1건 이상 (사유가 명시된 것만) |
| `FAILURES FOUND` | 실패 1건 이상 |

미커버는 구현 결함이 아니라 **검증 공백**이므로 수정 루프의 트리거가 아니다. 사유와 함께 남겨 호출자가 판단하게 한다.

---

## 테스트 원칙

1. **사용자 시나리오 중심**: 기술적 동작이 아닌 사용자 여정을 테스트한다.
2. **접근성 로케이터 우선**: `getByRole`, `getByLabel` > `getByTestId` > CSS 셀렉터.
3. **독립적 테스트**: 각 테스트는 독립적으로 실행 가능해야 한다.
4. **API 모킹 활용**: 외부 API 의존성은 모킹하여 안정적으로 테스트한다.
5. **기존 패턴 준수**: 프로젝트에 이미 E2E 테스트가 있으면 해당 패턴을 따른다.
