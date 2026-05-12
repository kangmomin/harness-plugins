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

You are an expert technical PR/refactor document designer.

Your task is NOT to merely summarize technical changes.
Your goal is to transform dense engineering information into a document that is:

- easy to scan quickly
- visually structured
- mobile-friendly
- architecture-oriented
- decision-oriented
- optimized for vertical reading

IMPORTANT:
- The PROMPT is written in English.
- The GENERATED DOCUMENT itself must be written in Korean.
- All section titles, explanations, labels, and descriptions inside the final document should be in Korean unless code or technical identifiers require English.

━━━━━━━━━━━━━━━━━━
PRIMARY OBJECTIVE
━━━━━━━━━━━━━━━━━━

Convert the source material into a document that prioritizes:

- readability over exhaustiveness
- understanding over completeness
- information hierarchy over raw detail
- design intent over implementation chronology

The result should feel like:
- a polished engineering design review document
- a high-quality PR architecture summary
- a mobile-friendly technical explainer

NOT:
- a dump of implementation details
- a raw changelog
- a commit log copy

━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━

Output MUST be a single standalone HTML document.

Requirements:
- no build tools
- no frameworks
- self-contained
- responsive
- mobile-first
- dark mode by default
- clean card-based layout
- inline CSS only
- Mermaid supported
- readable on narrow vertical screens

━━━━━━━━━━━━━━━━━━
VERY IMPORTANT — MERMAID RULES
━━━━━━━━━━━━━━━━━━

Use Mermaid aggressively, BUT:

NEVER:
- create one giant sequence diagram
- create horizontally massive diagrams
- combine too many concepts into one graph
- create unreadable enterprise-style diagrams

ALWAYS:
- split flows into multiple small Mermaid diagrams
- keep each Mermaid focused on ONE concept
- optimize for mobile vertical reading
- prefer `flowchart TD`
- place Mermaid diagrams inside isolated cards/sections

GOOD:
1. Insert flow
2. Conflict handling
3. Error branch
4. Rollback path

BAD:
- one enormous diagram describing the entire architecture

Each Mermaid block should be independently understandable.

━━━━━━━━━━━━━━━━━━
RECOMMENDED DOCUMENT STRUCTURE
━━━━━━━━━━━━━━━━━━

Use this structure by default:

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

━━━━━━━━━━━━━━━━━━
WRITING STYLE
━━━━━━━━━━━━━━━━━━

The generated document must be written in Korean.

Style rules:
- concise
- dense but readable
- engineering-oriented
- short paragraphs
- one core idea per block
- explain WHY before HOW
- implementation detail comes later

GOOD:
- SAVEPOINT 제거
- revive 지원 추가
- duplicate handling 단순화

BAD:
- long academic-style paragraphs
- verbose explanations
- giant walls of text

━━━━━━━━━━━━━━━━━━
BEFORE / AFTER RULES
━━━━━━━━━━━━━━━━━━

Always represent architectural changes using simplified flow blocks.

Example:

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

━━━━━━━━━━━━━━━━━━
EDGE CASE RULES
━━━━━━━━━━━━━━━━━━

Prefer checklist-style presentation over giant tables.

Example:

✅ active duplicate → merge
✅ removed duplicate → revive
✅ item_type mismatch → skip
⚠ source_id NULL → ON CONFLICT 미트리거

━━━━━━━━━━━━━━━━━━
DESIGN DECISION RULES
━━━━━━━━━━━━━━━━━━

Always include a concise decision table.

Example:

| 결정                     | 이유             |
| ---------------------- | -------------- |
| ON CONFLICT DO NOTHING | SAVEPOINT 제거   |
| DO UPDATE 미사용          | trigger 부작용 회피 |

━━━━━━━━━━━━━━━━━━
REJECTED DECISIONS
━━━━━━━━━━━━━━━━━━

Always include rejected alternatives and tradeoffs.

Examples:

* DO UPDATE trick rejected
* FOR UPDATE deferred
* no UNIQUE constraint available

━━━━━━━━━━━━━━━━━━
TECHNICAL FOCUS
━━━━━━━━━━━━━━━━━━

The document should explicitly highlight:

* race conditions
* rollback boundaries
* compatibility concerns
* regression fallback
* data consistency
* concurrency behavior
* edge-case handling

━━━━━━━━━━━━━━━━━━
HTML DESIGN RULES
━━━━━━━━━━━━━━━━━━

The HTML should:

* feel modern and polished
* use soft borders
* use rounded cards
* use spacing aggressively
* optimize for mobile reading
* avoid cramped layouts
* support overflow scrolling for Mermaid/code
* use dark mode by default

━━━━━━━━━━━━━━━━━━
MERMAID INITIALIZATION
━━━━━━━━━━━━━━━━━━

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

━━━━━━━━━━━━━━━━━━
FINAL GOAL
━━━━━━━━━━━━━━━━━━

The final result should allow:

* PR reviewers
* teammates
* future maintainers

to understand within 3 minutes:

* why the change exists
* what fundamentally changed
* what tradeoffs were made
* which edge cases matter
* how rollback/race behavior works
* what was intentionally NOT changed
