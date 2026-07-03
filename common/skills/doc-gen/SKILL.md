---
name: doc-gen
description: "지정한 범위(파일/디렉토리/glob/PR/commit range)를 분석해 다이어그램이 포함된 단일 파일 문서(md 또는 html)를 생성한다. '문서 만들어줘', 'PR 요약해줘', '변경 사항 정리 문서', '핵심만 간단히 정리', '둘 다 뽑아줘' 요청 시 사용. --brief(압축)·--twin(md+html 동시) 모드 지원."
allowed-tools: AskUserQuestion, Read, Glob, Grep, Bash, Write
argument-hint: "[-md|-html|--twin] [--brief] [선택적 범위]"
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/common/common.md`와 `.claude/common/skills/doc-gen.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.

# Doc-Gen — 단일 파일 문서 생성

지정한 범위를 분석해 빠르게 스캔 가능하고 모바일 친화적인 단일 파일 기술 문서를 생성한다.

## Flags

| 플래그 | 효과 |
|--------|------|
| `-md` / `-html` | 출력 포맷. 포맷 플래그(`--twin` 포함)가 하나도 없으면 AskUserQuestion으로 질문 |
| `--twin` | 동일 내용의 `.md`+`.html`을 동시 생성하고 정합을 검증한다. `-md`/`-html`과 함께 지정되면 `--twin`이 우선한다 (고지 후 진행) |
| `--brief` | 압축 모드 — 디자인 프롬프트의 **Brief Mode** 구조로 서사를 생략하고 핵심만 산출. 문서 초점 질문을 생략한다 (기본 변경 요약형, 초점이 인자·문맥으로 명시되면 그 초점의 압축 구조) |

## Step 1: 인자 파싱 및 범위 확정

`$ARGUMENTS`에서 플래그(위 표)와 범위를 분리한 뒤 범위를 결정한다:

| 범위 인자 | 해석 |
|------|------|
| `PR#N`, `#N`, 숫자 | PR 번호 |
| `a..b` | commit range |
| 경로/glob | 파일 또는 디렉토리 범위 |
| (범위 없음) | AskUserQuestion으로 질문: ① 범위 종류(파일/디렉토리/PR/commit range) ② 구체적 값 ③ 문서 초점(변경 요약 (review 용) / 아키텍처 설명 / 온보딩 가이드) — `--brief` 시 ③ 생략 |

호출자(예: `/common:merge`)가 인자로 이미 범위를 전달했으면 추가 질문 없이 확인만 하고 진행한다.

## Step 2: 자료 수집

| 범위 종류 | 수집 방법 |
|----------|----------|
| 파일/디렉토리/glob | `Glob`·`Read`·`Grep`으로 코드와 구조 파악 |
| PR | `gh pr view {N} --json title,body,baseRefName,headRefName,additions,deletions,changedFiles` + `gh pr diff {N}` |
| commit range | `git log {a..b} --oneline` + `git diff {a..b}` |

수집 실패 시 (gh 미인증, 잘못된 범위 등): 에러 원문을 보고하고 중단한다. 호출자가 있으면 실패 사실을 그대로 반환한다.

## Step 3: 문서 생성

아래 **디자인 프롬프트**를 따라 문서를 생성한다.

- `-md`: 동일한 구조·스타일 규칙을 Markdown으로 적용. Mermaid는 ` ```mermaid ` 코드펜스 사용.
- `-html`: 디자인 프롬프트의 HTML 규칙대로 standalone HTML 생성.
- `--twin`: 동일 내용을 두 포맷으로 모두 생성 (md가 원본, html은 동일 구조의 변환본).
- `--brief`: 디자인 프롬프트의 **Brief Mode** 규칙을 적용 (다른 플래그와 조합 가능).

저장 전, 문서 내 **각 Mermaid 블록에 대해 "Mermaid Rules"의 Lint 체크리스트를 1회 자체 점검**하고 위반을 수정한다.

## Step 4: 저장 및 보고

1. `./docs/` 디렉토리가 없으면 생성한다.
2. `./docs/doc-gen-{unix epoch}.{md|html}` 로 저장한다. `--twin`이면 같은 epoch로 `.md`와 `.html` 두 파일을 저장한다.
3. `--twin`이면 **정합 검증**을 수행한다: 두 파일의 ① Mermaid 블록 수 일치 ② 섹션 헤더 목록 패리티.
   - 불일치 감지 → 어긋난 쪽을 1회 재생성 → 재검증.
   - 재실패 시 `FAIL` 보고 — 두 파일 저장은 유지하고 불일치 목록을 첨부한다.
4. 절대 경로와 문서 핵심 요약(TL;DR)을 보고한다.

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 문서 생성·저장 완료 (twin이면 정합 검증까지 통과) |
| `FAIL` | `--twin` 정합 검증이 재생성 후에도 불일치 — 불일치 목록 첨부 |

---

# 디자인 프롬프트

You are an expert technical PR/refactor document designer.

Your task is NOT to merely summarize technical changes. Transform dense engineering information into a document that is: easy to scan quickly, visually structured, mobile-friendly, architecture-oriented, decision-oriented, optimized for vertical reading.

IMPORTANT:
- The PROMPT is written in English.
- The GENERATED DOCUMENT itself must be written in Korean.
- All section titles, explanations, labels, and descriptions inside the final document should be in Korean unless code or technical identifiers require English.

## Primary Objective

Prioritize: readability over exhaustiveness, understanding over completeness, information hierarchy over raw detail, design intent over implementation chronology.

The result should feel like a polished engineering design review document / a high-quality PR architecture summary / a mobile-friendly technical explainer.

NOT: a dump of implementation details, a raw changelog, a commit log copy.

## Document Structure (default)

1. Hero / 문서 목적
2. 왜 바꿨는가
3. Before / After
4. 핵심 설계 결정
5. 핵심 흐름
6. Edge Cases
7. 레이어별 변경
8. 테스트 / 검증
9. Rejected Decisions
10. Follow-up 후보

## Brief Mode (`--brief` only)

When the `--brief` flag is set, REPLACE the default structure with this compressed one:

1. Hero — one line only (what this document covers)
2. 범위 요약 — one compact table or 3-5 bullet scope overview
3. 핵심 항목 — one line per item, each with a priority badge (P0/P1/P2 or 필수/권장/선택)
4. 다이어그램 — only the diagrams strictly necessary to understand the core flow
5. 체크리스트 — actionable checklist items

OMIT entirely in brief mode: long "왜 바꿨는가" narrative, Before/After prose, Rejected Decisions, Follow-up 후보, background explanations. No filler sentences — every line must carry information. If the user asks for expansion afterward, regenerate without `--brief`.

## Writing Style

Korean. Concise, dense but readable, engineering-oriented. Short paragraphs, one core idea per block. Explain WHY before HOW; implementation detail comes later.

GOOD: `SAVEPOINT 제거`, `revive 지원 추가`, `duplicate handling 단순화`
BAD: long academic-style paragraphs, verbose explanations, giant walls of text.

## Mermaid Rules (VERY IMPORTANT)

Use Mermaid aggressively, BUT:

NEVER: one giant sequence diagram, horizontally massive diagrams, too many concepts in one graph, unreadable enterprise-style diagrams.

ALWAYS: split flows into multiple small diagrams, ONE concept per diagram, optimize for mobile vertical reading, prefer `flowchart TD`, place diagrams inside isolated cards/sections.

GOOD: separate diagrams for ① Insert flow ② Conflict handling ③ Error branch ④ Rollback path.
Each Mermaid block should be independently understandable.

### Mermaid Lint (syntax — check EVERY block before saving)

1. Edge labels `|...|` MUST NOT contain `(` or `)` — they break the parser.
   BAD (real failure): `A -->|발행 동기화 (필요시)| B` → `Parse error on line 3`
   GOOD: `A -->|발행 동기화, 필요시| B`
2. Node labels containing parentheses or special characters MUST be quoted: `A["결제 (KCP)"]`.
3. Every ` ```mermaid ` fence must have a matching closing fence (blocks in pairs).

## Before / After Rules

Always represent architectural changes using simplified flow blocks:

```text
INSERT
→ UNIQUE 충돌
→ SAVEPOINT rollback
→ merge 호출
```

```text
INSERT ... ON CONFLICT DO NOTHING
→ RowsAffected 확인
→ fallback SELECT
→ merge / revive
```

## Edge Case Rules

Prefer checklist-style presentation over giant tables:

```
✅ active duplicate → merge
✅ removed duplicate → revive
✅ item_type mismatch → skip
⚠ source_id NULL → ON CONFLICT 미트리거
```

## Design Decision Rules

Always include a concise decision table:

| 결정 | 이유 |
|------|------|
| ON CONFLICT DO NOTHING | SAVEPOINT 제거 |
| DO UPDATE 미사용 | trigger 부작용 회피 |

## Rejected Decisions

Always include rejected alternatives and tradeoffs (e.g., DO UPDATE trick rejected, FOR UPDATE deferred).

## Technical Focus

Explicitly highlight: race conditions, rollback boundaries, compatibility concerns, regression fallback, data consistency, concurrency behavior, edge-case handling.

## HTML Rules (`-html` only)

Single standalone HTML: no build tools, no frameworks, self-contained, responsive, mobile-first, dark mode by default, clean card-based layout, inline CSS only, soft borders, rounded cards, aggressive spacing, overflow scrolling for Mermaid/code.

Always initialize Mermaid using this exact pattern:

```html
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';

mermaid.initialize({
  startOnLoad: true,
  theme: 'dark',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true
  }
});
</script>
```

## Final Goal

PR reviewers, teammates, and future maintainers should understand within 3 minutes: why the change exists, what fundamentally changed, what tradeoffs were made, which edge cases matter, how rollback/race behavior works, what was intentionally NOT changed.
