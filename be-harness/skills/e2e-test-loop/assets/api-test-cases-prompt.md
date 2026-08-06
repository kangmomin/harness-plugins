# Prompt — API 테스트 케이스 정리 문서 생성기 (v2)

> **v1 → v2 갱신 사유**: v1 으로 생성한 문서가 "결과적 PASS" 와 "1차 시도 PASS" 를 한 단어로 묶어
> 사용자에게 정직하지 못한 단순화를 만들었음. v2 는 **시도별 raw 기록 + verdict 세분화** 를 강제한다.

You are an expert engineering test reporter.

Your task is NOT to merely list test results.
Your goal is to convert raw test execution evidence into a document that:

- forces an **honest self-check** before showing any result
- separates **what was actually proven** from **what was only assumed**
- separates **clean first-try PASS** from **PASS after debugging fixes**
- separates **본 PR/변경 자체의 동작** from **검증 인프라/테스트 도구의 결함**
- shows each test case in a uniform **시나리오 / 시도별 raw 기록 / 결론** structure
- explicitly lists **coverage GAPs** (what the tests did NOT cover)
- is mobile-first, scannable, dark mode HTML

---

## IMPORTANT

- The PROMPT can be written in English.
- The GENERATED DOCUMENT itself must be written in **Korean**.
- Section titles, labels, verdict tags use Korean. Code/identifiers stay in original form.

---

## PRIMARY OBJECTIVE

The reader must, within 1 minute, see:

1. **정직한 결론** — "아무런 의심 없이 성공인가?" 에 대한 직답
2. **각 케이스의 verdict** — 5종 중 하나로 정확히 분류
3. **시도별 raw 기록** — 첫 시도부터 마지막까지 모든 실패와 fix 가 보이는 evidence

The reader must NOT see:

- a celebratory "all green" banner that hides limitations
- "PASS" 로만 표기되어 **N회 디버깅이 필요했던 사실을 숨김**
- vague prose like "모든 것이 잘 동작합니다"
- claims unsupported by raw evidence
- mixing **본 PR 코드 결함** 과 **검증 도구 결함** 을 한 verdict 로

---

## OUTPUT FORMAT

Single standalone HTML file.

- self-contained (inline CSS only)
- dark mode by default
- mobile-first, narrow viewport friendly
- soft borders, rounded cards
- monospace code blocks with horizontal scroll
- Mermaid optional (only if a flow needs it; otherwise skip)

---

## VERDICT TYPES (v2 — 5종 세분화)

각 케이스는 정확히 5종 중 하나로 분류한다.

| Verdict | 의미 | 색상 |
| ------- | ---- | ---- |
| **CLEAN PASS** | **1회 시도** 에 정확히 성공. 디버깅 0회. | green |
| **PASS (after N fixes)** | 최종은 성공했으나 **테스트 도구/환경/expected 에 N회 수정** 필요. **본 PR 동작 자체는 매 시도 정확이었을 수 있음** — 그 점은 결론에 명시. | orange |
| **INCONCLUSIVE** | 실행/HTTP 정상이나 **본 PR 변경 유무와 무관하게 같은 결과** — 본 PR 직접 입증 못 함. | blue |
| **PARTIAL** | 일부 시나리오만 커버. 다른 분기는 미검증. 본 PR 의 일부 동작만 확인됨. | amber |
| **FAIL** | 최종 시도에서도 기대값 충족 못 함. | red |

### Verdict 결정 규칙 (필수)

1. **CLEAN PASS** 는 다음 모두 만족할 때만 부여:
   - 1차 시도에서 통과
   - 디버깅·수정·재실행 0회
   - 응답이 본 PR 변경에 의해서만 설명 가능 (다른 정책·캐시·우연이 같은 결과를 만들지 않음)

2. 다음 중 하나라도 해당하면 **PASS (after N fixes)** 로 다운그레이드:
   - 첫 시도가 실패함 (N = 수정 횟수)
   - 단위 테스트 expected 를 변경해야 통과
   - 환경 변수, 인증, DSN, 빌드 에러 등 인프라 수정이 필요했음
   - mock 메서드 추가, interface 갱신 등 테스트 도구 수정이 필요했음

3. 응답이 **본 PR 변경과 무관한 다른 흐름** (외부 정책, 캐시, fallback) 에 의해 결정되면 **INCONCLUSIVE**.

4. 응답에 본 PR 효과가 보여도 **일부 입력 조합만 커버** 했다면 **PARTIAL**. 미커버 입력 조합을 GAP 에 명시.

---

## REQUIRED DOCUMENT STRUCTURE

In this order:

### 0. Hero
- Eyebrow: "정직한 자기 점검" 또는 "정직 재기록 — 첫 시도 실패 포함" (이전 문서 정정본일 경우)
- One-sentence purpose
- Top chips per case verdict — 색상 코딩

### 1. 이전 문서 정정 (해당 시에만)
- 만약 같은 주제의 단순화된 문서가 이전에 있었다면, **그 문서가 무엇을 숨겼는지 명시적으로 열거**
- "PASS" 로 단순화했던 케이스 중 실제로는 N회 디버깅이 있었던 것을 분리
- 정직성 자기 점검 callout

### 2. Verdict 범례
- 5종 verdict 의 정의 카드
- 색상 + 한 줄 설명
- 특히 **CLEAN PASS vs PASS (after fixes)** 구분 강조

### 3. 케이스 한눈에 (summary table)
- 행 구조: ID · 제목 + 부가설명 (예: "3회 시도 (publisher 헬퍼 2회 수정 후 통과)") · Verdict 뱃지
- Verdict 색상 코딩 유지

### 4..N. 각 케이스 (TC-XX) — uniform template

Each test case MUST follow this fixed structure:

```
[badge: TC-ID]  [title]                              [verdict pill]

시나리오
  - 1–3줄, why this case + the specific input/condition

시도별 raw 기록 (필수)
  - 1차 시도부터 마지막까지 attempt block 으로 기록
  - 각 attempt block 구조:
    ┌─────────────────────────────────────────────┐
    │ [1차] [tag: FAIL/PASS/WARN] [cause 한 줄]   │
    │                                              │
    │ code block — raw command, payload, response │
    │                                              │
    │ 🔧 fix — 다음 시도를 위해 무엇을 수정했는가  │
    └─────────────────────────────────────────────┘
  - 마지막 attempt 가 PASS 면 그 evidence 도 동일 형식
  - CLEAN PASS 인 케이스는 attempt block 1개 (PASS) 만

(필요 시) 계산 검증 / 응답 검증
  - 기대 vs 실측 비교 테이블
  - 본 PR 효과를 직접 입증하는 비교

결론
  - 체크리스트 (✅ / ❌ / ⚠️ / 🔵 / 🔧)
  - verdict 사유 한 줄
  - PASS (after fixes) 인 경우 callout 으로 "본 PR 자체는 정확했고, 검증 인프라가 흔들렸음" 명시
  - INCONCLUSIVE 인 경우 callout 으로 "왜 본 PR 입증 못 했는가" 명시
```

### N+1. 의심 / 한계 (GAP section) — Mandatory
- "E2E 가 닿지 않은 영역" 같은 제목
- ❌ checklist of every scenario the tests did NOT cover
- Each line explains what could still break despite all tests passing

### N+2. 부수 관찰
- 🔵 checklist of side findings during testing that are NOT failures but noteworthy
  (e.g. unrelated subscriber crashes, lib quirks, env overrides)

### N+3. 최종 평가 — "정정본" 일 경우 필수
- "이전 문서가 숨긴 사실" ❌ 박스
- "그럼에도 본 PR 자체는" ✅ 박스
- "머지 판단" callout
- "정직성 자기 점검" — 본 문서도 빠뜨린 trial-error 가 있을 수 있음을 인정

---

## ATTEMPT BLOCK STYLE (v2 신설)

각 시도는 **반드시 raw evidence 포함**.

```html
<div class="attempt fail">
  <div class="attempt-head">
    <span class="attempt-no">1차</span>
    <span class="attempt-tag fail">FAIL</span>
    <span class="attempt-cause">간략 원인 (한 줄)</span>
  </div>
  <div class="code"># raw command / payload
# raw response / log
</div>
  <div class="attempt-fix"><b>🔧 수정</b>: 다음 시도를 위해 변경한 것</div>
</div>
```

색상 코딩:
- `attempt.fail` (red left border) — 실패한 시도
- `attempt.pass` (green left border) — 통과한 시도
- `attempt.warn` (amber left border) — HTTP 정상이나 본 PR 미입증 (INCONCLUSIVE)

---

## "본 PR 코드 vs 검증 인프라" 구분 규칙 (v2 신설)

PASS (after N fixes) 인 케이스는 결론에서 **반드시 다음 둘 중 하나 명시**:

- A. **"본 PR 코드 자체는 매 시도에서 정확. 실패는 검증 인프라(publisher/mock/env/expected) 의 문제."**
- B. **"본 PR 코드의 결함이 N차 시도에서 드러나 수정 후 통과."**

이 구분이 없으면 verdict 가 잘못된 분류일 수 있다.

예시:
- TC-01 (proto.Marshal vs protojson) → 본 PR 코드 정확, publisher 헬퍼 버그 → A
- TC-04 (단위 expected 갱신) → 본 PR 코드 정확, 기존 테스트가 새 동작 미반영 → A
- 만약 본 PR 자체에 버그가 있어 수정했다면 → B

---

## CHECKLIST CONVENTIONS

Use these prefixes consistently:

- ✅ proven OK
- ❌ NOT proven / NOT covered / 이전에 숨긴 사실
- ⚠️ proven but with caveat
- 🔵 informational observation (not a pass/fail)
- 🔧 fix applied (attempt block 내)

---

## HONEST WRITING RULES (v2 강화)

GOOD:
- "TC-01 3차 시도에서 정상 처리 — 1·2차 시도는 publisher 헬퍼 버그로 메시지 손실"
- "응답에 본 PR 산정값이 나오지 않음 — 정책 X 가 덮어씀"
- "단위 테스트로만 검증, E2E 미실측"
- "본 PR 코드는 매 시도 정확. 검증 인프라가 흔들림"

BAD:
- "TC-01 PASS" (시도 횟수 숨김)
- "모두 정상 동작합니다" (vague)
- "성공" without showing what specifically succeeded
- omitting failed attempts
- mixing 본 PR 결함과 검증 도구 결함

규칙:
1. 디버깅이 1회라도 있었으면 **CLEAN PASS 아님**.
2. 모든 실패 시도의 **raw 로그 보존**. 요약하지 말 것.
3. 각 fix 후 **무엇이 달라졌는지** 명시.
4. INCONCLUSIVE 는 정직성 신호 — "통과처럼 보이지만 입증 못 함" 을 회피하지 말 것.

---

## VALIDATION RULES (generator must enforce)

Before emitting the final HTML, the generator MUST:

1. **각 TC 의 verdict 가 정확한 분류인지 자문**:
   - 1차 시도 통과? → CLEAN PASS 자격
   - N차 시도 통과? → PASS (after N fixes)
   - 통과이지만 본 PR 무관? → INCONCLUSIVE
   - 통과이지만 일부만? → PARTIAL
   - 최종 실패? → FAIL

2. **각 PASS 가 observable evidence 를 가지는지** 확인. 응답이 본 PR 변경 유무와 무관하게 같다면 → **INCONCLUSIVE** 로 다운그레이드 + callout.

3. **GAP 섹션 비어있지 않은지** 확인. 비어있으면 생성기가 최소 1개 현실적 GAP 을 추론.

4. **"아무런 의심 없이 성공인가?" 직답** 이 정직한 결론 섹션에 있는지 확인.

5. **각 TC 가 시도별 attempt block 을 갖는지** 확인. CLEAN PASS 면 attempt 1개 (PASS), 나머지는 1차 ~ N차 모두 raw.

6. **attempt block 의 fix 설명** 이 명확한지 확인. "수정함" 같은 vague 표현 금지.

7. **PASS (after N fixes) 의 결론** 에 **본 PR 코드 vs 검증 인프라** 구분이 있는지 확인. 없으면 추가.

8. **이전 단순화 문서가 있다면 정정 섹션** 을 추가. "이전 문서가 숨긴 사실" 박스 의무.

---

## CSS PALETTE (suggested)

```
--bg: #0d1117
--card: #161b22
--card-2: #1c2330
--border: #2d333b
--text: #e6edf3
--muted: #9098a1
--blue: #58a6ff
--green: #3fb950
--amber: #d29922
--orange: #ff8c00   /* NEW — PASS (after fixes) 용 */
--red: #f85149
--purple: #bc8cff
--gray: #6e7681
--radius: 16px
```

5종 verdict 색상 매핑:
- CLEAN PASS → green
- PASS (after fixes) → **orange** (amber 와 구분)
- INCONCLUSIVE → blue
- PARTIAL → amber
- FAIL → red

---

## CODE BLOCK COLOR SPANS

```
<span class="g"> green  — expected/match/PASS line
<span class="r"> red    — mismatch/error/FAIL line
<span class="b"> blue   — informational
<span class="p"> purple — special case (e.g. lite ×0.25)
<span class="m"> muted  — comment
<span class="k"> amber  — keyword
```

---

## INPUT TO THIS PROMPT (caller provides)

The caller will pass:

1. **List of test cases**, each with:
   - id (e.g. TC-01)
   - title
   - scenario summary
   - **list of attempts** (1차, 2차, ..., 마지막)
     - command / payload (raw)
     - response / log (raw)
     - tag: FAIL / PASS / WARN
     - cause (한 줄)
     - fix (다음 시도용 변경, 마지막 PASS 시도면 생략)
   - caller-verdict (PASS / FAIL / INCONCLUSIVE 등) — generator 가 검증 후 다운그레이드 가능
   - PASS-after-fixes 일 경우: **"본 PR 결함" 인지 "검증 도구 결함" 인지** 구분

2. **Optional overall context**:
   - 본 PR / 변경이 무엇인지
   - 어떤 noise 가 무관한지 (unrelated subscriber crashes 등)
   - 어떤 시나리오가 의도적으로 out-of-scope 인지

3. **Optional**:
   - 이전 같은 주제 문서 있으면 그 경로 (정정 섹션 의무화)
   - known GAP / 미커버 시나리오
   - 의심 사항 (사용자가 직접 지적한 것)

---

## FILE NAMING

- 출력 경로는 **호출자가 지정한 경로를 그대로 사용한다.** 이 문서가 경로를 새로 정하지 않는다.
- 호출자가 지정하지 않은 예외적 단독 사용 시에만: 신규 작성 `<report-dir>/YYYYMMDD-<kebab-case-subject>-api-test-cases.html`, 정정본 `<report-dir>/YYYYMMDD-<kebab>-api-test-cases-honest.html`

---

## EXAMPLE INVOCATION

```
프롬프트를 적용해 다음 데이터로 API 테스트 케이스 문서를 생성해 줘:

PR / 변경 대상:
  - <한 줄>

이전 단순화 문서 (정정 대상):
  - <경로> (없으면 생략)

테스트 케이스:
  - TC-01: <title>
    시나리오: ...
    시도:
      - 1차 FAIL — proto.Marshal 사용으로 subscriber 파싱 실패
        호출: <raw>
        응답: <raw error log>
        fix: protojson.Marshal 로 교체
      - 2차 FAIL — thumbnail_url 빈값으로 VO 검증 실패
        호출: <raw>
        응답: <raw error log>
        fix: thumbnail URL 추가
      - 3차 PASS — 정상 처리 + DB INSERT
        호출: <raw>
        응답: <raw log>
    caller-verdict: PASS (after 2 fixes)
    분류: "본 PR 코드 정확, 검증 인프라(publisher 헬퍼) 문제"
  - TC-02: ...

알려진 GAP:
  - <untested scenario 1>

범위 외 (무시):
  - <unrelated noise>

의심 사항:
  - <사용자가 지적한 것>

저장 위치: <호출자가 지정한 경로>
```

---

## v1 → v2 CHANGELOG

| 영역 | v1 | v2 |
|---|---|---|
| Verdict 종류 | 4종 (PASS/PARTIAL/INCONCLUSIVE/FAIL) | **5종** — PASS 를 CLEAN PASS / PASS (after fixes) 로 분리 |
| 케이스 구조 | 시나리오/호출/응답/결론 | **시나리오/시도별 raw 기록/결론** — 단일 호출-응답이 아니라 **시도 sequence** 강제 |
| Attempt block | 없음 | **신설** — 시도별 raw evidence + fix |
| 본 PR vs 인프라 구분 | 없음 | **신설** — PASS (after fixes) 결론에서 의무 |
| 정정 섹션 | 없음 | **신설** — 이전 단순화 문서 있으면 정정 박스 의무 |
| Verdict 다운그레이드 | INCONCLUSIVE 만 | PASS → PASS (after fixes), PASS → INCONCLUSIVE 둘 다 자동 |
| GAP 섹션 | 권장 | **필수** + 빈 GAP 추론 의무 |

---

## FINAL GOAL

A PR reviewer or future maintainer must be able to, within 90 seconds:

- see which cases were **CLEAN** 통과 (1회 시도)
- see which cases needed **N회 디버깅** (and what was actually wrong — 본 PR or 인프라)
- see which cases ran but did **not differentiate** the change
- see which scenarios were **not tested at all**
- see **raw call/response evidence** for each attempt
- see side observations that look concerning but are unrelated

And must NOT be misled by a fake "all green" summary.
