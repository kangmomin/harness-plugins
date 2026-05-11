---
name: doc-gen
description: "지정한 범위(파일/디렉토리/glob/PR/commit range)를 분석해 인터랙션·다이어그램이 포함된 단일 파일 문서(md 또는 html)를 생성한다."
allowed-tools: AskUserQuestion, Read, Glob, Grep, Bash, Write
argument-hint: "[-md|-html] [선택적 범위]"
user-invocable: true
---

## Project Overrides

실행 전에 아래 경로의 프로젝트 로컬 오버라이드 파일을 Read로 확인한다:

- `.claude/common/common.md` — 플러그인 공통 (모든 스킬에 적용)
- `.claude/common/skills/doc-gen.md` — 본 스킬 전용

존재하면 내용을 **추가 규칙/예외/변경점**으로 흡수해 본 스킬 흐름에 반영한다. 충돌 시 프로젝트 오버라이드가 우선. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

---

# /common:doc-gen — 단일 파일 문서 생성

지정한 범위 내의 코드/변경사항을 요약하고, 그래프와 인터랙션이 포함된 **단일 파일** 문서를 만든다.

## 핵심 철학

- **단일 파일 보장**: 외부 자산 없이 그 파일 하나로 열어볼 수 있어야 한다.
- **읽기 위한 문서**: 코드를 그대로 옮기지 않고, 구조·흐름·관계를 시각화한다.
- **범위 우선**: 어디까지 다룰지를 먼저 확정한 뒤 정리한다.
- **요약은 사실 기반**: 코드/diff에서 직접 확인한 것만 적는다. 추측은 `[Assumption]` 표기.
- **가독성이 곧 문서의 가치**: 같은 정보를 더 빨리·정확하게 흡수하게 만드는 것이 목표. 시각적 계층, 스캔 가능성(scannability), 콜아웃, 일관된 라벨링을 적극 활용한다. 화려한 장식 ≠ 가독성. **불필요한 장식은 가독성을 떨어뜨린다.**

---

## Phase 0: 인자 파싱

`$ARGUMENTS` 를 `-md` / `-html` 플래그와 나머지(범위 후보)로 분리한다.

| 토큰 | 의미 |
|------|------|
| `-md`, `--md`, `md` | 출력 포맷: Markdown |
| `-html`, `--html`, `html` | 출력 포맷: HTML |
| 그 외 | 범위 후보로 보존 (Phase 1 으로 전달) |

규칙:
1. 플래그가 둘 다 있으면 마지막에 등장한 것을 사용.
2. 플래그가 없으면 `AskUserQuestion` 으로 한 번 묻는다 (옵션: md / html).
3. 범위 후보가 비어 있으면 Phase 1 의 단계적 질문으로 진행, 있으면 그 값을 디폴트 후보로 들고 Phase 1 의 확인만 받는다.

---

## Phase 1: 범위 확정 (단계적 질문)

`AskUserQuestion` 을 사용해 한 번에 하나씩 물어가며 범위를 확정한다. 절대 추측해서 진행하지 않는다.

### Step 1 — 범위 종류

```
어떤 범위를 정리할까요?

1. 파일 / 디렉토리 / glob
2. 최근 변경(working tree, staged 포함)
3. Commit range (예: HEAD~5..HEAD, 또는 특정 SHA 범위)
4. PR (GitHub PR 번호)
```

> 인자로 들어온 후보가 있으면 1~4 중 하나로 자동 분류해서 "이게 맞나요?" 만 확인한다.

### Step 2 — 종류별 세부값

선택된 종류에 따라 하나만 더 묻는다.

- **파일/디렉토리/glob**: "정리할 경로 또는 glob 을 알려주세요. (예: `src/auth`, `internal/**/*.go`, `app/page.tsx`)"
- **최근 변경**: 추가 질문 없이 `git status` + `git diff` 로 수집.
- **Commit range**: "범위를 알려주세요. (예: `HEAD~5..HEAD`, `main..feature/x`)"
- **PR**: "PR 번호를 알려주세요. (예: `42`)" → `gh pr view <num>` + `gh pr diff <num>` 로 수집. `gh` 미설치/미인증이면 사용자에게 알리고 commit range 모드로 fallback 제안.

### Step 3 — 문서의 초점

```
이 문서의 초점은 무엇인가요?

1. 아키텍처 / 구성요소 관계 — 모듈/계층/의존성 시각화 중심
2. 흐름 / 시퀀스 — 요청 흐름, 함수 호출 순서, 상태 전이 중심
3. 변경 요약 (review 용) — diff 요약, 영향 범위, 핵심 포인트 중심
4. API 명세 — 엔드포인트, 입출력, 에러 케이스 중심
```

복수 선택 가능. 디폴트는 (1+2).

### Step 4 — 출력 파일 경로

```
출력 파일 경로를 지정할까요? (엔터/스킵 시 기본값)
```

기본값 규칙:
- md: `./docs/doc-gen-<unix-timestamp>.md`
- html: `./docs/doc-gen-<unix-timestamp>.html`

`./docs/` 가 없으면 `Bash` 로 생성한다. 사용자가 다른 경로를 지정하면 그대로 사용.

---

## Phase 2: 범위 분석

확정된 범위에서 정보를 수집한다.

### 도구 매핑

| 범위 종류 | 수집 명령 |
|----------|----------|
| 파일/디렉토리/glob | `Glob` 으로 파일 목록 → `Read` 로 내용 |
| 최근 변경 | `git status -s`, `git diff`, `git diff --staged` (Bash) |
| Commit range | `git log --oneline <range>`, `git diff <range>` (Bash) |
| PR | `gh pr view <n> --json title,body,headRefName,baseRefName,files`, `gh pr diff <n>` (Bash) |

### 구조 추출

수집 결과에서 아래를 추출한다 (해당 시).

- 파일 단위: 경로, 역할(헤더/네임스페이스/패키지/`package`/`module` 선언으로 추정), 핵심 export.
- 호출/의존: import / require / `from X import Y` / Go import 그래프.
- 진입점: `main`, route 정의, handler 등록, page 컴포넌트 등 프로젝트 컨벤션 기준으로 식별.
- 변경 요약: 추가/삭제/수정 파일 카운트, 핵심 hunk 의 의미.
- (API 초점일 때) HTTP method + path + request/response 필드.

추출은 코드에 직접 보이는 사실만. 추측이 필요하면 `[Assumption]` 으로 표기.

---

## Phase 3: 단일 파일 출력 생성

출력 포맷에 따라 파일을 생성한다. 두 포맷 모두 **외부 빌드 단계 없이 그 파일 하나로 열람 가능** 해야 한다.

### 공통 섹션 (양쪽 포맷 공통 골격)

1. **헤드라인** — 범위·생성일·초점
2. **요약 (TL;DR)** — 3~5줄. 가능하면 첫 줄은 "한 문장 요약", 이후는 핵심 변경/구성 bullet.
3. **읽기 가이드** *(선택, 5섹션 이상일 때만)* — 누가 어느 섹션을 먼저 읽어야 하는지 안내하는 2~4줄 표.
4. **구성요소 다이어그램** — Mermaid `graph TD` 또는 `flowchart LR`. **다이어그램 위에 한 줄 캡션** 필수.
5. **흐름 다이어그램** — Mermaid `sequenceDiagram` 또는 `stateDiagram-v2`. 캡션 필수.
6. **세부 항목** — 파일/모듈/엔드포인트 단위 카드. 펼침/접힘.
7. **변경 / Diff 요약** — 범위가 변경 기반일 때만. 카운트(추가/삭제/수정)는 표로, 핵심 hunk 는 콜아웃으로.
8. **엣지 케이스 / 주의** — 발견한 위험 신호. **반드시 콜아웃(Warning/Note)으로 표기.**
9. **부록** — 원본 경로 / 커밋 SHA / PR 링크 등

초점이 위 중 일부에 한정되면 해당 섹션만 두텁게, 나머지는 생략한다.

#### 섹션별 가독성 규칙 (양쪽 포맷 공통)

- **섹션 헤더 직후 한 줄 도입부**: 모든 `h2` 섹션은 헤더 바로 아래에 "이 섹션이 무엇을 다루는지" 한 줄 요약을 둔다. 본론은 그 다음부터.
- **카드 라벨 일관성**: 파일/엔드포인트/모듈 카드는 모두 동일 라벨 순서로 작성한다.
  - **역할** → **주요 함수/export** → **의존** → **진입점** → **엣지 케이스** (해당 없는 항목은 라벨 자체를 생략)
- **콜아웃 활용**: 단순 강조 텍스트(`**중요**`)는 지양. 대신 콜아웃 박스(Note / Tip / Warning / Danger 4종) 중 의미에 맞는 하나를 사용.
- **표 vs bullet**: 항목이 3개 이상이면서 동일 속성을 갖는 데이터는 표. 1~2개 항목이거나 자유 서술은 bullet.
- **링크 명사화**: "여기 클릭" 금지. 링크 텍스트는 그 자체로 무엇을 가리키는지 의미가 통해야 한다.
- **약어**: 첫 등장 시 풀이. 예: `JWT (JSON Web Token)`. 약어가 매우 일반적이면 생략 가능.

### A. md 포맷

- 다이어그램은 ` ```mermaid ` 코드블록.
- 인터랙션은 `<details><summary>` 토글로 표현. 토글 안에 코드 스니펫·전체 표 등 큰 덩어리를 둔다.
- 단일 `.md` 파일. 추가 자산 금지.

#### md 가독성 규칙

- **헤딩 깊이**: `h1` 은 문서 제목 1개. `h2` 가 주 섹션. `h3` 은 한 섹션 내 하위 그룹까지만. **`h4` 이상 사용 금지** — 더 깊어지면 카드(`<details>`) 또는 표로 재구성.
- **GitHub 콜아웃 블록쿼트 사용** (GitHub/VSCode/대부분 뷰어 지원):
  - `> [!NOTE]` — 보조 설명
  - `> [!TIP]` — 권장 사항/팁
  - `> [!IMPORTANT]` — 놓치면 안 되는 정보
  - `> [!WARNING]` — 잘못 사용 시 문제 발생 가능
  - `> [!CAUTION]` — 위험·되돌릴 수 없는 동작
- **코드 블록 언어 표시 의무**: ` ```ts `, ` ```go `, ` ```bash ` 등 항상 언어 명시. 언어가 없거나 plain 텍스트면 ` ```text `.
- **표는 정렬 표기 사용**: `|:---|` (좌), `|:---:|` (중앙), `|---:|` (우). 숫자 컬럼은 우측 정렬.
- **링크 형식**: 같은 경로를 본문에서 반복하지 말고 reference-style 링크(`[label][ref]`) 활용. 단 한 번만 등장하면 inline 으로 충분.
- **이모지**: 의미가 분명한 곳에만 (예: ✅/❌/⚠️). 장식용 이모지 금지.

#### 파일/모듈 카드 예시

```markdown
<details>
<summary><b>auth/login.go</b> — POST /v1/login 핸들러</summary>

- **역할**: 사용자 인증 요청을 처리하고 JWT 발급.
- **주요 함수**: `Login(ctx, req)` ([`auth/login.go:42`](auth/login.go))
- **의존**: `auth/jwt.go`, `users/repo.go`
- **진입점**: `router.POST("/v1/login", Login)` ([`router.go:18`](router.go))
- **엣지 케이스**: 잘못된 비밀번호 시 동일한 응답 시간 유지 (timing attack 방어).

> [!WARNING]
> 잠금 정책이 없어 brute-force 에 노출됨. 다음 PR 에서 rate limit 추가 예정.

</details>
```

#### 다이어그램 + 캡션 예시

```markdown
> **그림 1.** 로그인 요청의 전체 흐름.

` ``mermaid
flowchart LR
  Client -->|POST /v1/login| Handler
  Handler --> Usecase
  Usecase --> Repo[(DB)]
  Usecase --> JWT[JWT Signer]
` ``
```

### B. html 포맷

- 단일 `.html` 파일. 의존성은 **Mermaid CDN 한 개만** 허용. 그 외 모든 CSS/JS 는 인라인.
- 레이아웃: **1-column 단일 본문**. 사이드바·테마 토글·검색 기능은 포함하지 않는다.
- 인터랙션 요구사항:
  - **최상단 목차 (TOC)**: 헤드라인 바로 아래에 목차 카드. 모든 `h2` 섹션 자동 수집. 클릭 시 해당 섹션으로 smooth scroll. 항목이 6개를 넘으면 2-column grid 로 자동 배치.
  - 섹션별 카드 펼침/접힘 (`<details>` 또는 직접 토글).
  - 다이어그램은 Mermaid 가 `DOMContentLoaded` 후 렌더.
  - **코드 블록 우상단에 "복사" 버튼** — 클릭 시 `navigator.clipboard.writeText` 로 코드 복사, 토스트로 "복사됨" 알림.
  - **"맨 위로" 버튼** — `scrollY > 600` 일 때 우하단 floating, 클릭 시 smooth scroll.
  - **콜아웃 박스 4종** (`.callout-note`, `.callout-tip`, `.callout-warning`, `.callout-danger`) — 좌측 색상 보더 + 라벨 + 본문.
  - **카드 헤더 뱃지** — 카드(`<details>`) 의 summary 에 분류 뱃지를 둘 수 있게 클래스 제공 (`.badge-handler`, `.badge-service`, `.badge-repo`, `.badge-external`, `.badge-util` 등 도메인 적합한 색 4~6종).
- 가독성 요구사항 (타이포그래피):
  - 본문 폰트 크기 `clamp(14px, 0.95rem + 0.1vw, 16px)`, 줄간격 `1.65`.
  - 본문 텍스트 폭 `max-width: min(72ch, 100%)` 로 한 줄을 60~75자 사이로 유지. 코드/표/다이어그램은 이 제한에서 제외(전체 폭 활용).
  - 헤딩은 본문보다 줄간격 좁게(`1.3`), 위 여백 크게(아래는 작게) — 다음 본문과 시각적 결합.
  - 코드 폰트는 `ui-monospace, SFMono-Regular, Menlo` 계열, 크기는 본문의 `0.92em`.
  - 단락 사이 여백은 `0.75em`, 섹션 사이는 `2em` 이상.
- **반응형 요구사항 (세로 모니터/좁은 viewport 안정성)**:
  - 1-column 단일 본문이므로 어떤 폭에서도 레이아웃은 변하지 않는다. 패딩과 폰트만 viewport 에 따라 조정.
  - 폭 `< 1024px`: 본문 좌우 패딩 축소.
  - 폭 `< 480px` (좁은 portrait): 패딩/폰트 추가 축소, TOC 는 1-column 으로 강제, 모든 카드는 가로폭 100%.
  - 본문 콘텐츠 폭은 가독성 보장을 위해 텍스트 단락은 `max-width: min(72ch, 100%)`, 코드/표/다이어그램은 `max-width: min(1100px, 100%)`.
  - 모든 `<pre>`, `.mermaid`, 표(`<table>`) 는 wrapper 에 `overflow-x: auto` + `max-width: 100%` 적용. 다이어그램이 좁은 화면에서 잘리지 않고 가로 스크롤되어야 한다.
  - 긴 경로/URL/식별자는 `word-break: break-word; overflow-wrap: anywhere;` 로 줄바꿈.
  - 이미지/SVG 는 `max-width: 100%; height: auto;`.
  - viewport meta 는 `width=device-width, initial-scale=1` 유지.
- 외부 폰트/이미지 금지. 아이콘이 필요하면 inline SVG.
- 보안: 사용자가 입력한 코드를 HTML 에 삽입할 때는 `<` `>` `&` 를 escape.

#### HTML 템플릿 (시작점)

```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{{TITLE}}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  :root {
    --bg: #ffffff; --fg: #1f2328; --muted: #57606a;
    --border: #d0d7de; --accent: #0969da; --code-bg: #f6f8fa;
    --content-w: min(1100px, 100%);
    --text-w: min(72ch, 100%);
    /* 콜아웃 색 */
    --note-bg: #ddf4ff; --note-fg: #0969da; --note-bd: #54aeff;
    --tip-bg: #dafbe1; --tip-fg: #1a7f37; --tip-bd: #4ac26b;
    --warn-bg: #fff8c5; --warn-fg: #9a6700; --warn-bd: #d4a72c;
    --danger-bg: #ffebe9; --danger-fg: #cf222e; --danger-bd: #ff8182;
    /* 카드 뱃지 색 */
    --b-handler: #0969da; --b-service: #8250df; --b-repo: #1a7f37;
    --b-external: #9a6700; --b-util: #57606a;
  }
  * { box-sizing: border-box; }
  html, body { max-width: 100%; overflow-x: hidden; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Pretendard", sans-serif;
    font-size: clamp(14px, 0.95rem + 0.1vw, 16px);
    line-height: 1.65;
    background: var(--bg); color: var(--fg);
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
  main {
    margin: 0 auto;
    padding: 32px 32px 64px;
    width: 100%;
    max-width: var(--content-w);
  }
  /* 본문 텍스트는 좁은 max-width, 코드/표/다이어그램은 전체 폭 */
  main > section > p,
  main > section > ul,
  main > section > ol,
  main > section > blockquote {
    max-width: var(--text-w);
  }
  h1.doc-title {
    font-size: clamp(22px, 1.4rem + 0.5vw, 32px);
    line-height: 1.3; margin: 0 0 4px;
    word-break: break-word;
  }
  .doc-meta { color: var(--muted); font-size: 0.9em; margin-bottom: 24px; }
  section { margin-bottom: 40px; min-width: 0; }
  section > h2 {
    font-size: clamp(18px, 1.1rem + 0.3vw, 24px);
    line-height: 1.3;
    margin: 1.5em 0 0.5em;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
    word-break: break-word;
    scroll-margin-top: 16px;
  }
  section > h2:first-child { margin-top: 0; }
  section > h3 {
    font-size: 1.05em; line-height: 1.3;
    margin: 1.4em 0 0.4em;
  }
  p { margin: 0.4em 0 0.9em; }
  p, li, td, th, summary { overflow-wrap: anywhere; word-break: break-word; }
  a { color: var(--accent); overflow-wrap: anywhere; word-break: break-word; }
  a:hover { text-decoration: underline; }

  /* 최상단 목차 */
  .toc-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 18px;
    margin: 0 0 32px;
    background: var(--code-bg);
  }
  .toc-card > h2 {
    font-size: 0.85em; font-weight: 700;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 8px; padding: 0; border: 0;
  }
  .toc-list {
    list-style: none; padding: 0; margin: 0;
    display: grid; gap: 4px 16px;
    grid-template-columns: 1fr;
    counter-reset: toc;
  }
  .toc-card.multi .toc-list { grid-template-columns: repeat(2, 1fr); }
  @media (max-width: 600px) {
    .toc-card.multi .toc-list { grid-template-columns: 1fr; }
  }
  .toc-list li { counter-increment: toc; }
  .toc-list a {
    display: block; padding: 4px 0;
    color: var(--fg); text-decoration: none;
  }
  .toc-list a::before {
    content: counter(toc, decimal-leading-zero) ".";
    display: inline-block; min-width: 2.5em;
    color: var(--muted); font-variant-numeric: tabular-nums;
  }
  .toc-list a:hover { color: var(--accent); }

  details {
    border: 1px solid var(--border); border-radius: 6px;
    padding: 10px 14px; margin: 8px 0; background: var(--bg);
  }
  details > summary {
    cursor: pointer; font-weight: 600;
    list-style: none;
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  }
  details > summary::-webkit-details-marker { display: none; }
  details > summary::before {
    content: "▸"; font-size: 0.9em; color: var(--muted);
    transition: transform 0.15s ease;
  }
  details[open] > summary::before { transform: rotate(90deg); }
  details[open] > summary { margin-bottom: 8px; }

  /* 카드 뱃지 */
  .badge {
    display: inline-flex; align-items: center;
    padding: 1px 8px; border-radius: 999px;
    font-size: 0.75em; font-weight: 600;
    background: var(--code-bg); color: var(--muted);
    border: 1px solid var(--border);
    white-space: nowrap;
  }
  .badge-handler { color: #fff; background: var(--b-handler); border-color: transparent; }
  .badge-service { color: #fff; background: var(--b-service); border-color: transparent; }
  .badge-repo { color: #fff; background: var(--b-repo); border-color: transparent; }
  .badge-external { color: #fff; background: var(--b-external); border-color: transparent; }
  .badge-util { color: #fff; background: var(--b-util); border-color: transparent; }

  /* 콜아웃 */
  .callout {
    border-left: 4px solid; border-radius: 6px;
    padding: 10px 14px; margin: 12px 0;
    max-width: var(--text-w);
  }
  .callout .callout-label {
    font-weight: 700; font-size: 0.85em; text-transform: uppercase;
    letter-spacing: 0.05em; display: block; margin-bottom: 4px;
  }
  .callout p:last-child { margin-bottom: 0; }
  .callout-note    { background: var(--note-bg);   border-color: var(--note-bd); }
  .callout-note    .callout-label { color: var(--note-fg); }
  .callout-tip     { background: var(--tip-bg);    border-color: var(--tip-bd); }
  .callout-tip     .callout-label { color: var(--tip-fg); }
  .callout-warning { background: var(--warn-bg);   border-color: var(--warn-bd); }
  .callout-warning .callout-label { color: var(--warn-fg); }
  .callout-danger  { background: var(--danger-bg); border-color: var(--danger-bd); }
  .callout-danger  .callout-label { color: var(--danger-fg); }

  /* 코드/표/다이어그램 */
  pre, code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  pre {
    background: var(--code-bg); padding: 14px 16px; border-radius: 6px;
    overflow-x: auto; max-width: 100%;
    font-size: 0.92em; line-height: 1.55;
  }
  code { overflow-wrap: anywhere; word-break: break-word; font-size: 0.92em; }
  p code, li code, td code {
    background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 4px;
  }
  table {
    display: block; max-width: 100%; overflow-x: auto;
    border-collapse: collapse; margin: 12px 0;
  }
  table th, table td {
    border: 1px solid var(--border); padding: 6px 10px; text-align: left;
  }
  table th { background: var(--code-bg); }
  img, svg { max-width: 100%; height: auto; }
  .scroll-x { overflow-x: auto; max-width: 100%; }
  .mermaid { background: var(--bg); max-width: 100%; overflow-x: auto; }
  .mermaid svg { max-width: 100%; height: auto; }
  .caption {
    font-size: 0.88em; color: var(--muted); text-align: center;
    margin: 4px 0 12px;
  }

  /* 코드 블록 wrapper + 복사 버튼 */
  .codeblock { position: relative; margin: 12px 0; }
  .codeblock > pre { margin: 0; padding-top: 32px; }
  .codeblock .lang-label {
    position: absolute; top: 6px; left: 12px;
    font-size: 0.72em; font-weight: 600;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.05em; pointer-events: none;
  }
  .codeblock .copy-btn {
    position: absolute; top: 6px; right: 8px;
    border: 1px solid var(--border); background: var(--bg);
    color: var(--fg); border-radius: 6px;
    padding: 2px 10px; font-size: 0.8em; cursor: pointer;
    opacity: 0.7; transition: opacity 0.15s ease;
  }
  .codeblock:hover .copy-btn { opacity: 1; }
  .codeblock .copy-btn.copied { color: var(--tip-fg); border-color: var(--tip-bd); }

  /* 맨 위로 버튼 */
  .to-top {
    position: fixed; right: 20px; bottom: 24px;
    width: 44px; height: 44px; border-radius: 50%;
    border: 1px solid var(--border); background: var(--bg);
    color: var(--fg); cursor: pointer;
    font-size: 18px; line-height: 1;
    box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    display: none; align-items: center; justify-content: center;
    z-index: 30;
  }
  .to-top.visible { display: flex; }

  /* 토스트 */
  .toast {
    position: fixed; left: 50%; bottom: 32px; transform: translateX(-50%);
    background: var(--fg); color: var(--bg);
    padding: 8px 16px; border-radius: 999px;
    font-size: 0.9em; opacity: 0; pointer-events: none;
    transition: opacity 0.2s ease;
    z-index: 40;
  }
  .toast.show { opacity: 1; }

  /* 반응형 */
  @media (max-width: 1023px) {
    main { padding: 24px 20px 56px; }
  }
  @media (max-width: 479px) {
    main { padding: 16px 14px 48px; }
    section { margin-bottom: 32px; }
    pre { padding: 10px 12px; font-size: 0.88em; }
    details { padding: 8px 12px; }
    .to-top { right: 14px; bottom: 18px; width: 40px; height: 40px; }
    .toc-card { padding: 12px 14px; }
  }

  /* 인쇄 */
  @media print {
    .to-top, .toast, .copy-btn { display: none !important; }
    main { padding: 0; max-width: 100%; }
    details[open] > summary { page-break-after: avoid; }
  }
</style>
</head>
<body>
<main id="main">
  <header>
    <h1 class="doc-title">{{TITLE}}</h1>
    <div class="doc-meta">{{META}}</div>
  </header>

  <!-- 최상단 목차 (JS 가 자동 채움) -->
  <nav class="toc-card" id="tocCard" aria-label="목차">
    <h2>목차</h2>
    <ol class="toc-list" id="tocList"></ol>
  </nav>

  <section id="summary">
    <h2>요약</h2>
    <p>{{TLDR}}</p>
  </section>

  <section id="architecture">
    <h2>구성요소</h2>
    <p class="caption">{{ARCHITECTURE_CAPTION}}</p>
    <div class="scroll-x">
      <div class="mermaid">
{{ARCHITECTURE_MERMAID}}
      </div>
    </div>
  </section>

  <section id="flow">
    <h2>흐름</h2>
    <p class="caption">{{FLOW_CAPTION}}</p>
    <div class="scroll-x">
      <div class="mermaid">
{{FLOW_MERMAID}}
      </div>
    </div>
  </section>

  <section id="items">
    <h2>세부 항목</h2>
    {{ITEM_CARDS}}
  </section>

  <section id="changes">
    <h2>변경 요약</h2>
    {{CHANGE_SUMMARY}}
  </section>

  <section id="risks">
    <h2>엣지 케이스 / 주의</h2>
    {{RISKS}}
  </section>

  <section id="appendix">
    <h2>부록</h2>
    {{APPENDIX}}
  </section>
</main>

<button class="to-top" id="toTop" aria-label="맨 위로" title="맨 위로">↑</button>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script>
  const main = document.getElementById('main');

  // 1) 최상단 목차 자동 생성 (h2 만)
  const tocCard = document.getElementById('tocCard');
  const tocList = document.getElementById('tocList');
  const sections = main.querySelectorAll('section[id] > h2');
  sections.forEach(h => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '#' + h.parentElement.id;
    a.textContent = h.textContent;
    li.appendChild(a); tocList.appendChild(li);
  });
  if (sections.length === 0) tocCard.style.display = 'none';
  if (sections.length > 6) tocCard.classList.add('multi');

  // 2) 코드 블록 wrap + 복사 버튼 + 언어 라벨
  function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove('show'), 1600);
  }
  document.querySelectorAll('pre').forEach(pre => {
    if (pre.closest('.codeblock') || pre.closest('.mermaid')) return;
    const wrap = document.createElement('div');
    wrap.className = 'codeblock';
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    const codeEl = pre.querySelector('code');
    const lang = codeEl && [...codeEl.classList].find(c => c.startsWith('language-'));
    if (lang) {
      const label = document.createElement('span');
      label.className = 'lang-label';
      label.textContent = lang.replace('language-', '');
      wrap.appendChild(label);
    }
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'copy-btn'; btn.textContent = '복사';
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(pre.innerText);
        btn.textContent = '복사됨'; btn.classList.add('copied');
        showToast('코드가 클립보드에 복사되었습니다');
        setTimeout(() => { btn.textContent = '복사'; btn.classList.remove('copied'); }, 1600);
      } catch {
        showToast('복사에 실패했습니다');
      }
    });
    wrap.appendChild(btn);
  });

  // 3) 맨 위로 버튼
  const toTop = document.getElementById('toTop');
  window.addEventListener('scroll', () => {
    toTop.classList.toggle('visible', window.scrollY > 600);
  }, { passive: true });
  toTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // 4) Mermaid 초기 렌더
  if (window.mermaid) {
    mermaid.initialize({ startOnLoad: true, theme: 'default' });
  }
</script>
</body>
</html>
```

위 템플릿의 `{{...}}` 토큰을 Phase 2 분석 결과로 치환해 단일 파일을 만든다. 토큰을 모두 채울 수 없으면 빈 섹션은 제거한다.

### C. 다이어그램 작성 규칙

- **캡션 의무화**: 모든 다이어그램 위(또는 바로 아래)에 "이 다이어그램이 무엇을 보여주는지" 한 줄 캡션. md 는 `> **그림 N.** ...`, html 은 `<p class="caption">...</p>`.
- **노드는 30개 이하**. 그 이상이면 그룹화(subgraph) 하거나 두 다이어그램으로 분리.
- **노드 라벨**은 짧은 명사구. **라인 라벨**에 동사/메서드.
- **외부 시스템 표기 구분**: DB `[(...)]`, 외부 API `[/.../]`, 큐 `>...]`, 사용자 액터 `((사용자))`.
- **식별자에 한국어**를 쓸 때는 따옴표로 감싼다 (`A["회원 도메인"] --> B`).
- **노드 분류별 색**: subgraph 또는 `classDef` 로 분류별 색을 일관 적용 (예: handler=파랑, service=보라, repo=초록, external=주황). 색은 카드 뱃지 색과 매칭.
- **방향성**: 한 다이어그램 안에서 흐름 방향(LR/TD)을 섞지 않는다.

---

## Phase 4: 검증 및 마무리

1. 출력 파일을 `Read` 로 다시 열어 다음을 확인:
   - md:
     - ` ```mermaid ` 블록이 닫혀 있는지, `<details>` 가 짝이 맞는지.
     - 모든 코드블록에 언어가 명시돼 있는지 (` ```text ` 도 허용).
     - `h4` 이상 헤딩이 존재하는지 (있으면 카드/표로 재구성 검토).
     - 위험·주의 사항이 `> [!WARNING]` / `> [!CAUTION]` 콜아웃으로 표기됐는지.
   - html:
     - `<script src="...mermaid...">` 한 줄만 외부 의존성으로 존재하는지, 다른 외부 URL 없는지.
     - `<meta name="viewport" content="width=device-width,initial-scale=1" />` 존재 여부.
     - **최상단 목차 카드**(`.toc-card`)가 헤드라인 직후에 존재하는지.
     - 사이드바·테마 토글·검색 input 이 **존재하지 않는지**.
     - 모든 `.mermaid` / `<pre>` / `<table>` 이 `overflow-x: auto` 가 적용된 wrapper 안 또는 자체에 갖고 있는지.
     - 본문 단락(`section > p/ul/ol/blockquote`)에 `max-width: var(--text-w)` 가 적용돼 한 줄이 너무 길지 않은지.
     - 콜아웃(`.callout-note/.callout-tip/.callout-warning/.callout-danger`) CSS 와 카드 뱃지(`.badge-*`) CSS 가 정의돼 있는지.
     - "맨 위로" 버튼(`.to-top`) 과 코드 복사 버튼(`.copy-btn`) JS 가 포함돼 있는지.
2. 파일 크기를 보고한다.
3. 사용자에게 절대경로와 한 줄 요약을 출력한다.

성공 보고 형식:
```
✅ 문서 생성 완료
- 파일: <abs path>
- 포맷: md|html
- 범위: <확정된 범위 한 줄 요약>
- 섹션: <포함된 섹션 목록>
```

실패 시:
- 범위가 비어 있다 → "범위에서 분석 가능한 코드/변경을 찾지 못했습니다" 와 함께 종료.
- gh 미설치/미인증으로 PR 모드 실패 → 그대로 보고하고 commit range 로 fallback 제안.

---

## 중요 원칙

1. **단일 파일** — md 는 추가 자산 0, html 은 Mermaid CDN 1개 외 0.
2. **사실 기반 요약** — 코드에서 직접 확인한 것만, 추측은 표기.
3. **범위 확정 후 분석** — Phase 1 없이 Phase 2 진입 금지.
4. **인터랙션은 의미 있게** — 토글/복사/맨 위로는 가독성을 위한 것. 장식용 애니메이션·이펙트 추가 금지.
5. **다이어그램은 보여줄 수 있는 것만** — 노드 30개 초과 시 분할. 캡션 의무.
6. **경로 표기** — 코드 인용 시 `path/file.ext:line` 형식 유지.
7. **콜아웃 우선** — 위험·주의·팁은 본문 강조 텍스트가 아니라 콜아웃(Note/Tip/Warning/Danger) 박스로.
8. **카드 라벨 일관성** — 모든 카드는 동일 라벨 순서 사용. 항목 없으면 라벨 자체를 생략.
9. **헤딩 깊이 ≤ 3** — `h4` 이상 사용 금지. 더 깊어지면 카드/표로 재구성.
10. **한 줄 길이** — html 본문 단락은 60~75자 사이가 되도록 `max-width: var(--text-w)`. 코드/표/다이어그램은 제외.
