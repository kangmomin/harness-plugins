# simplify-loop Workflow Script

> 이 문서는 `simplify-loop` 스킬의 Phase 2(dry-run: `SCAN_PROMPT`만 사용)와 Phase 4(Workflow 실행)에서 로드된다. 단독 실행 금지.

## args 명세

Workflow tool 호출 시 아래 script 전문을 `script` 파라미터로, args를 `args` 파라미터로 전달한다.
**모든 args는 필수다** — 기본값 정의처는 SKILL.md 상단 플레이스홀더가 유일하며, script는 in-script 기본값을 두지 않는다.

| 키 | 타입 | 의미 |
|----|------|------|
| `diffCommand` | string | 스킬 Phase 1이 확정한 diff 명령 (범위 식별 전용 — 스니펫은 작업 트리 Read로 추출) |
| `maxIterations` | number | `{MAX_ITER}` 값 |
| `candidateCap` | number | `{CANDIDATE_CAP}` 값 |
| `retryLimit` | number | `{RETRY_LIMIT}` 값 |

호출 예:

```
Workflow tool:
  script: <아래 코드 블록 전문>
  args: { "diffCommand": "git diff HEAD", "maxIterations": 10, "candidateCap": 8, "retryLimit": 1 }
```

## 반환 형식

`{ status, iterations, applied[], rejected[], holds[], failed[], iterLog[], note }`

- `status`: `DONE` | `BLOCKED:MAX_ITERATIONS` | `BLOCKED:NO_PROGRESS` | `BLOCKED:REVIEW_INCOMPLETE` | `FAIL`
- `iterLog[i]`: iteration별 후보 리뷰 상세 (4관점 verdict/confidence, DA strength, Arbiter 판정) — 스킬 Phase 6 보고서의 데이터 원천
- `note`: FAIL 시 부가 설명 (예: "적용 내역 미확인 — git diff 수동 검토 필요")

## Script 전문

에이전트 프롬프트의 유일한 정의처는 아래 script 내 named const다 (`SCAN_PROMPT`, `PERSPECTIVES`, `REVIEW_PROMPT`, `DA_PROMPT`, `ARBITER_PROMPT`, `APPLY_PROMPT`, `RECONCILE_PROMPT`).
리뷰 프로세스는 simplify-review-convention(4관점 → 만장일치 시 Devil's Advocate → Arbiter)의 재구현이며 **canonical은 본 파일이다** (전역 규칙 파일과의 동기화는 수동).

```javascript
export const meta = {
  name: 'simplify-loop',
  description: '변경 코드 단순화 후보를 4관점 배치 리뷰로 수렴할 때까지 반복 적용',
  phases: [
    { title: 'Scan', detail: '후보 스캔 + 코드 필터' },
    { title: 'Review', detail: '4관점 배치 리뷰 + Devils Advocate/Arbiter' },
    { title: 'Apply', detail: '승인 후보 순차 적용 + 화해' },
  ],
}

// ═══ args — 전부 필수 (기본값 정의처는 SKILL.md 플레이스홀더가 유일) ═══
if (!args || !args.diffCommand || !args.maxIterations || !args.candidateCap || !args.retryLimit) {
  throw new Error('필수 args 누락: diffCommand, maxIterations, candidateCap, retryLimit')
}
const DIFF_CMD = args.diffCommand
const MAX_ITER = args.maxIterations
const CAP = args.candidateCap
const RETRY = args.retryLimit

// ═══ 유틸 (순수 문자열 연산 — script는 fs 접근 불가) ═══
const norm = s => String(s || '').replace(/\s+/g, ' ').trim()
const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(36) }
const contentKeyOf = c => c.file + '#' + hash(norm(c.current))
const proposedKeyOf = c => c.file + '#' + hash(norm(c.proposed))

// ═══ 프롬프트 — 단일 출처: 본 script의 named const (simplify-review-convention 재구현, canonical) ═══
const SCAN_PROMPT = (seenSummary) => `당신은 코드 단순화 후보를 스캔하는 에이전트입니다.

## 범위 식별
\`${DIFF_CMD}\`를 실행해 변경된 파일/영역을 식별하세요. **이 명령은 범위 식별 전용입니다** —
후보의 current 스니펫은 반드시 작업 트리의 실제 파일을 Read해서 추출하세요 (diff 텍스트에서 복사 금지).

## 후보 기준 (동작 보존이 대전제)
- 중복 코드 제거, 불필요한 추상화 제거, 죽은 코드 제거, 더 단순한 동등 표현으로 교체
- 기존 동작을 100% 보존하는 변경만 제안. 기능 추가/동작 변경/스타일 취향은 후보가 아님
- 무관한 코드의 리팩토링 금지 — 변경 범위 내 코드만

## 제외 목록 (이미 처리된 항목 — 아래 disposition 규칙 준수)
${seenSummary || '(없음)'}

- disposition이 APPLIED/REJECTED/SUGGESTION/HOLD/FAILED인 항목: 재제안 금지
- disposition이 PENDING인 항목: 재제안 금지 (별도 재처리 중)
- disposition이 STALE인 항목을 다시 제안할 때: 해당 항목의 id를 matchedSeenId에 반드시 지정
- disposition이 RECONSIDER인 항목의 수정안을 제안할 때: 해당 항목의 id를 revisesId에 반드시 지정하고 기각 사유를 반영해 proposed를 수정

## 출력
- 발견한 후보 전체 수를 totalFound에 기록하고, 중요도 순 상위 ${CAP}건만 candidates에 담으세요
- 변경된 코드가 전혀 없으면 diffEmpty=true, candidates=[]
- 각 후보: file(저장소 루트 기준 상대경로), line(현재 작업 트리 기준), summary(한 줄),
  current(작업 트리의 실제 코드 스니펫, 정확히), proposed(제안 코드), rationale(근거)`

const PERSPECTIVES = [
  { key: 'Correctness', question: '이 단순화가 기존 동작을 100% 보존하는가? 엣지 케이스가 누락되지 않았는가?' },
  { key: 'Readability', question: '코드가 실제로 더 읽기 쉬워지는가? 팀 컨벤션과 일치하는가?' },
  { key: 'Performance', question: '성능 저하 없이 동일하거나 더 나은 효율을 보장하는가?' },
  { key: 'Stability', question: '변경의 blast radius는? 의존 코드에 영향은 없는가?' },
]

const REVIEW_PROMPT = (p, batch) => `당신은 코드 단순화 제안의 **${p.key}** 관점 리뷰어입니다.
핵심 질문: ${p.question}

다른 리뷰어의 판정을 알 수 없는 독립 리뷰입니다. 각 후보에 대해 필요하면 해당 파일을 Read해
주변 맥락을 확인한 뒤, 후보마다 아래를 판정하세요:
- verdict: CHANGE(변경 지지) / KEEP(현행 유지) / CONDITIONAL(조건부 — 확신 부족 포함)
- confidence: High / Medium / Low
- rationale: 2~3문장 근거
- risks: 변경 시 리스크 (없으면 "없음")

## 리뷰 대상 후보
${JSON.stringify(batch.map(c => ({ candidateId: c.id, file: c.file, line: c.line, summary: c.summary, current: c.current, proposed: c.proposed, rationale: c.rationale })), null, 2)}

모든 candidateId에 대해 정확히 1개의 verdict를 반환하세요.`

const DA_PROMPT = (batch, verdictNotes) => `당신은 이 코드 변경들에 **반대하는 역할**(Devil's Advocate)을 맡았습니다.
4개 관점 리뷰어 전원이 "변경 필요(CHANGE)"라고 판정했지만, 당신은 각 후보에 대해 반드시 반론을
구성해야 합니다. "반대할 게 없다"는 허용되지 않습니다. 후보마다 4요소를 모두 작성하세요:
1. reasonsToKeep: 현재 코드가 가진 숨겨진 장점이나 의도
2. riskScenario: 이 변경이 문제를 일으킬 수 있는 구체적 상황 1개 이상
3. alternative: 전면 변경 대신 부분 변경/유지가 더 나은 경우의 논증
4. strength: 본인 반론의 설득력 자기 평가 (Strong / Moderate / Weak — Weak이라도 반론은 필수)

## 만장일치 후보 및 찬성 요지
${JSON.stringify(batch.map(c => ({ candidateId: c.id, file: c.file, summary: c.summary, current: c.current, proposed: c.proposed, 찬성요지: verdictNotes[c.id] })), null, 2)}`

const ARBITER_PROMPT = (batch, verdictNotes, dissents) => `당신은 중재자(Arbiter)입니다. 이전 리뷰어들과 무관한 독립 판단을 내리세요.
각 후보에 대해 찬성 의견(4관점 만장일치 CHANGE)과 Devil's Advocate의 반론을 평가하세요:
1. 구체성: 반론이 구체적 시나리오/코드 경로에 기반하는가?
2. 재현 가능성: 반론의 위험 시나리오가 실제로 발생할 수 있는가?
3. 비용 대비: 변경의 이점이 반론이 지적한 위험보다 명확히 큰가?

후보별 판정:
- PROCEED: 반론이 형식적/비현실적 → 변경 진행
- RECONSIDER: 반론에 타당한 포인트 → 제안 수정 필요 (reasoning에 수정 방향 명시)
- HOLD: 반론이 강력 → 보류, 사용자 판단 위임

## 입력
${JSON.stringify(batch.map(c => ({ candidateId: c.id, file: c.file, summary: c.summary, current: c.current, proposed: c.proposed, 찬성요지: verdictNotes[c.id], 반론: dissents[c.id] })), null, 2)}

각 후보에 verdict(PROCEED/RECONSIDER/HOLD), reasoning(3~5문장), action(다음 단계)을 반환하세요.`

const APPLY_PROMPT = (batch) => `당신은 승인된 코드 단순화를 적용하는 에이전트입니다. 아래 후보를 **순서대로 하나씩** 적용하세요.

각 후보마다:
1. 해당 파일을 Read하고 current 스니펫이 **정확히 일치**하는지 확인
2. 일치하지 않으면 절대 적용하지 말고 result=STALE (reason에 불일치 내용)
3. 일치하면 current → proposed로 외과적 수정만 수행 (무관 코드 변경 금지), 성공 시 result=APPLIED
4. 수정 시도가 실패하면 result=FAILED (reason 필수)

## 적용 대상 (순서대로)
${JSON.stringify(batch.map(c => ({ candidateId: c.id, file: c.file, line: c.line, current: c.current, proposed: c.proposed })), null, 2)}

모든 candidateId에 대해 결과를 반환하세요.`

const RECONCILE_PROMPT = (batch) => `당신은 적용 결과를 검증(화해)하는 에이전트입니다. 직전 적용 에이전트가 실패해
어떤 후보가 실제로 반영됐는지 불명확합니다. **파일을 수정하지 마세요.**

각 후보마다 해당 파일을 Read해서:
- proposed 코드가 존재하고 current가 사라짐 → result=APPLIED
- current가 그대로 존재 → result=FAILED (reason: "apply agent 실패, 미반영")
- 둘 다 아님(제3의 상태) → result=STALE (reason에 현재 상태 요약)

(git diff 원본 대조가 아니라 후보별 파일 내용 확인입니다 — 사용자 변경·이전 적용분과 섞이기 때문)

## 검증 대상
${JSON.stringify(batch.map(c => ({ candidateId: c.id, file: c.file, current: c.current, proposed: c.proposed })), null, 2)}

모든 candidateId에 대해 결과를 반환하세요.`

// ═══ 스키마 (candidateId는 iteration마다 동적 enum) ═══
const scanSchema = {
  type: 'object', required: ['diffEmpty', 'totalFound', 'candidates'],
  properties: {
    diffEmpty: { type: 'boolean' },
    totalFound: { type: 'integer' },
    candidates: { type: 'array', items: {
      type: 'object', required: ['file', 'line', 'summary', 'current', 'proposed', 'rationale'],
      properties: {
        file: { type: 'string' }, line: { type: 'integer' }, summary: { type: 'string' },
        current: { type: 'string' }, proposed: { type: 'string' }, rationale: { type: 'string' },
        matchedSeenId: { type: 'string' }, revisesId: { type: 'string' },
      } } },
  },
}
const reviewSchema = ids => ({
  type: 'object', required: ['verdicts'],
  properties: { verdicts: { type: 'array', items: {
    type: 'object', required: ['candidateId', 'verdict', 'confidence', 'rationale', 'risks'],
    properties: {
      candidateId: { enum: ids },
      verdict: { enum: ['CHANGE', 'KEEP', 'CONDITIONAL'] },
      confidence: { enum: ['High', 'Medium', 'Low'] },
      rationale: { type: 'string' }, risks: { type: 'string' },
    } } } },
})
const daSchema = ids => ({
  type: 'object', required: ['dissents'],
  properties: { dissents: { type: 'array', items: {
    type: 'object', required: ['candidateId', 'reasonsToKeep', 'riskScenario', 'alternative', 'strength'],
    properties: {
      candidateId: { enum: ids }, reasonsToKeep: { type: 'string' }, riskScenario: { type: 'string' },
      alternative: { type: 'string' }, strength: { enum: ['Strong', 'Moderate', 'Weak'] },
    } } } },
})
const arbiterSchema = ids => ({
  type: 'object', required: ['rulings'],
  properties: { rulings: { type: 'array', items: {
    type: 'object', required: ['candidateId', 'verdict', 'reasoning', 'action'],
    properties: {
      candidateId: { enum: ids }, verdict: { enum: ['PROCEED', 'RECONSIDER', 'HOLD'] },
      reasoning: { type: 'string' }, action: { type: 'string' },
    } } } },
})
const applySchema = ids => ({
  type: 'object', required: ['results'],
  properties: { results: { type: 'array', items: {
    type: 'object', required: ['candidateId', 'result'],
    properties: {
      candidateId: { enum: ids },
      result: { enum: ['APPLIED', 'FAILED', 'STALE'] },
      reason: { type: 'string' },
    } } } },
})

// ═══ 상태 ═══
const seen = new Map() // contentKey → { id, file, line, summaryLine, disposition, retryCount, contentKey, proposedKey }
const applied = [], rejected = [], holds = [], failed = [], iterLog = []
let pendingRetry = [] // [{ candidate(내부에 infraRetry), reason }]
let iter = 0, converged = false, noProgressStreak = 0, candSeq = 0
let exitStatus = null, exitNote = null

const seenList = () => Array.from(seen.values())
const seenSummaryText = () => {
  const rows = seenList().map(e => `- [${e.id}] ${e.disposition} · ${e.file} · ${e.summaryLine}`)
  const pend = pendingRetry.map(p => `- [${p.candidate.id}] PENDING · ${p.candidate.file} · ${p.candidate.summary} (재제안 금지)`)
  return rows.concat(pend).join('\n')
}
const addSeen = (c, disposition) => {
  seen.set(c.contentKey, {
    id: c.id, file: c.file, line: c.line, summaryLine: c.summary,
    disposition, retryCount: c.inheritedRetryCount || 0,
    contentKey: c.contentKey, proposedKey: c.proposedKey,
  })
}
const INFRA_REASONS = ['REVIEWER_FAILURE', 'ARBITER_FAILURE', 'MISSING_VERDICT']
const toInfraPending = (c, reason, nextPending) => {
  const infraRetry = (c.infraRetry || 0) + 1
  if (infraRetry > RETRY) {
    holds.push({ candidateId: c.id, file: c.file, line: c.line, summary: c.summary, current: c.current, proposed: c.proposed, reason: reason + ' (재시도 소진)' })
    addSeen(c, 'HOLD')
  } else {
    nextPending.push({ candidate: Object.assign({}, c, { infraRetry }), reason })
  }
}

// ═══ 메인 루프 ═══
while (!converged && !exitStatus && iter < MAX_ITER) {
  iter++
  phase('Iteration ' + iter)

  // ── 1. Scan (null → 1회 재시도 → FAIL. 거짓 DONE 금지) ──
  let scan = await agent(SCAN_PROMPT(seenSummaryText()), { schema: scanSchema, label: 'scan#' + iter, phase: 'Scan' })
  if (!scan) scan = await agent(SCAN_PROMPT(seenSummaryText()), { schema: scanSchema, label: 'scan-retry#' + iter, phase: 'Scan' })
  if (!scan) { exitStatus = 'FAIL'; exitNote = '스캔 에이전트 재시도 후에도 실패 — 수렴 미확인'; break }

  let raw = scan.candidates || []
  if (scan.totalFound > raw.length) log('Scan: 발견 ' + scan.totalFound + '건 중 상한 ' + CAP + '건만 리뷰 대상 (초과 ' + (scan.totalFound - raw.length) + '건 이월)')
  raw = raw.slice(0, CAP)
  if (iter >= 2 && scan.diffEmpty && pendingRetry.length === 0) { converged = true; break }

  // ── 2. 코드 필터 (순서 고정: id 부여 → 링크 브랜치 → seen/pending drop) ──
  const fresh = []
  for (const rc of raw) {
    candSeq++
    const c = Object.assign({}, rc, { id: 'i' + iter + '-c' + candSeq })
    c.contentKey = contentKeyOf(c)
    c.proposedKey = proposedKeyOf(c)
    // (c) 링크 브랜치 — seen-drop보다 먼저 평가 (아니면 재제안 허용이 사문화)
    let linked = null
    if (rc.revisesId) {
      const m = seenList().find(e => e.id === rc.revisesId)
      if (m && m.disposition === 'RECONSIDER') linked = m
      else { log('필터: ' + c.id + ' drop — revisesId ' + rc.revisesId + ' 는 RECONSIDER 엔트리가 아님'); continue }
    }
    if (!linked && rc.matchedSeenId) {
      const m = seenList().find(e => e.id === rc.matchedSeenId)
      if (m && m.disposition === 'STALE') linked = m
      else { log('필터: ' + c.id + ' drop — matchedSeenId ' + rc.matchedSeenId + ' 는 재제안 가능 엔트리가 아님'); continue }
    }
    if (!linked) {
      // auto-link 백스톱 (STALE/RECONSIDER 한정 — APPLIED/REJECTED 오탐 방지)
      // STALE: proposed 동일 + current 변경 → proposedKey 일치, 라인 근접(±40) tie-breaker
      const st = seenList().find(e => e.disposition === 'STALE' && e.proposedKey === c.proposedKey && Math.abs((e.line || 0) - (c.line || 0)) <= 40)
      if (st) linked = st
      // RECONSIDER 대칭: current 동일 + proposed 변경 → contentKey 일치 (revisesId 누락 백스톱)
      if (!linked) {
        const rec = seenList().find(e => e.disposition === 'RECONSIDER' && e.contentKey === c.contentKey)
        if (rec) linked = rec
      }
    }
    if (linked) {
      if (linked.retryCount < RETRY) { linked.retryCount++; c.linkedTo = linked.id; fresh.push(c) }
      else log('필터: ' + c.id + ' drop — ' + linked.id + ' 재제안 한도(' + RETRY + ') 소진')
      continue
    }
    // (d) 통상 dedup + 재투입분과의 이중 리뷰 방지
    if (seen.has(c.contentKey)) continue
    if (pendingRetry.some(p => p.candidate.contentKey === c.contentKey)) continue
    fresh.push(c)
  }

  // ── 수렴 판정: fresh 0 && pendingRetry 소진 (재투입 전 판정으로 인한 고아화 방지) ──
  if (fresh.length === 0 && pendingRetry.length === 0) { converged = true; break }
  const batch = fresh.concat(pendingRetry.map(p => p.candidate))
  const nextPending = []
  pendingRetry = []

  // ── 3. 관점별 배치 리뷰 (4개 병렬 — 판정에 4 verdict 전부 필요하므로 barrier 정당) ──
  const ids = batch.map(c => c.id)
  const rSchema = reviewSchema(ids)
  const reviews = await parallel(PERSPECTIVES.map(p => async () => {
    let r = await agent(REVIEW_PROMPT(p, batch), { schema: rSchema, label: 'review:' + p.key + '#' + iter, phase: 'Review' })
    if (!r) r = await agent(REVIEW_PROMPT(p, batch), { schema: rSchema, label: 'review-retry:' + p.key + '#' + iter, phase: 'Review' })
    return { key: p.key, out: r }
  }))
  const deadPerspectives = reviews.filter(r => !r || !r.out)
  const logEntry = { iteration: iter, candidates: [] }
  if (deadPerspectives.length > 0) {
    log('Iteration ' + iter + ': 관점 리뷰어 ' + deadPerspectives.length + '개 실패 — 후보 전원 재처리 대기')
    for (const c of batch) toInfraPending(c, 'REVIEWER_FAILURE', nextPending)
    pendingRetry = nextPending
    iterLog.push(logEntry)
    continue
  }
  // 관점별 verdict 맵 (중복/미지 id는 초과분 drop + log)
  const vmap = {}
  for (const r of reviews) {
    vmap[r.key] = {}
    for (const v of r.out.verdicts) {
      if (!ids.includes(v.candidateId)) { log('리뷰 집계: 미지 candidateId ' + v.candidateId + ' (' + r.key + ') drop'); continue }
      if (vmap[r.key][v.candidateId]) { log('리뷰 집계: 중복 verdict ' + v.candidateId + ' (' + r.key + ') 초과분 drop'); continue }
      vmap[r.key][v.candidateId] = v
    }
  }

  // ── 4. 판정 (후보별, script 코드) ──
  const approvedNow = [], unanimous = []
  const verdictNotes = {}
  for (const c of batch) {
    const vs = PERSPECTIVES.map(p => vmap[p.key][c.id])
    if (vs.some(v => !v)) { toInfraPending(c, 'MISSING_VERDICT', nextPending); continue }
    const entry = { id: c.id, file: c.file, line: c.line, summary: c.summary, verdicts: {}, decision: null }
    PERSPECTIVES.forEach((p, i) => { entry.verdicts[p.key] = { verdict: vs[i].verdict, confidence: vs[i].confidence, rationale: vs[i].rationale, risks: vs[i].risks } })
    logEntry.candidates.push(entry)
    const changes = vs.filter(v => v.verdict === 'CHANGE').length // CONDITIONAL은 non-CHANGE 집계
    verdictNotes[c.id] = vs.map((v, i) => PERSPECTIVES[i].key + ': ' + v.verdict + '(' + v.confidence + ') ' + v.rationale).join(' / ')
    if (changes === 4) { unanimous.push(c); entry.decision = 'UNANIMOUS→DA' }
    else if (changes === 3) {
      const minority = vs.find(v => v.verdict !== 'CHANGE')
      entry.decision = 'APPROVED(3/4)'; entry.minorityWarning = minority.rationale
      approvedNow.push(c)
    }
    else if (changes === 2) {
      entry.decision = 'HOLD(2/2 사용자 위임)'
      holds.push({ candidateId: c.id, file: c.file, line: c.line, summary: c.summary, current: c.current, proposed: c.proposed, reason: 'SPLIT_2_2 — 사용자 판단 위임', detail: verdictNotes[c.id] })
      addSeen(c, 'HOLD')
    }
    else if (changes === 1) {
      entry.decision = 'REJECTED(suggestion 기록)'
      const ch = vs.find(v => v.verdict === 'CHANGE')
      rejected.push({ candidateId: c.id, file: c.file, summary: c.summary, kind: 'SUGGESTION', suggestion: ch.rationale })
      addSeen(c, 'SUGGESTION')
    }
    else {
      entry.decision = 'REJECTED'
      rejected.push({ candidateId: c.id, file: c.file, summary: c.summary, kind: 'REJECTED' })
      addSeen(c, 'REJECTED')
    }
  }

  // ── 4b. 만장일치 → Devil's Advocate → Arbiter (배치, 후보별 schema 강제) ──
  if (unanimous.length > 0) {
    const uniIds = unanimous.map(c => c.id)
    const da = await agent(DA_PROMPT(unanimous, verdictNotes), { schema: daSchema(uniIds), label: 'devils-advocate#' + iter, phase: 'Review' })
    const dmap = {}
    if (da) for (const d of da.dissents) { if (uniIds.includes(d.candidateId) && !dmap[d.candidateId]) dmap[d.candidateId] = d }
    const arb = da ? await agent(ARBITER_PROMPT(unanimous, verdictNotes, dmap), { schema: arbiterSchema(uniIds), label: 'arbiter#' + iter, phase: 'Review' }) : null
    const amap = {}
    if (arb) for (const a of arb.rulings) { if (uniIds.includes(a.candidateId) && !amap[a.candidateId]) amap[a.candidateId] = a }
    for (const c of unanimous) {
      const entry = logEntry.candidates.find(e => e.id === c.id)
      const d = dmap[c.id], a = amap[c.id]
      if (!d || !a) { toInfraPending(c, 'ARBITER_FAILURE', nextPending); if (entry) entry.decision = 'INFRA_PENDING(ARBITER_FAILURE)'; continue }
      entry.daStrength = d.strength
      entry.arbiter = { verdict: a.verdict, reasoning: a.reasoning }
      if (a.verdict === 'PROCEED') { entry.decision = 'APPROVED(만장일치+Arbiter PROCEED)'; approvedNow.push(c) }
      else if (a.verdict === 'RECONSIDER') {
        entry.decision = 'RECONSIDER(수정 재제안 허용)'
        rejected.push({ candidateId: c.id, file: c.file, summary: c.summary, kind: 'RECONSIDER', arbiterReasoning: a.reasoning })
        addSeen(c, 'RECONSIDER')
      }
      else {
        entry.decision = 'HOLD(Arbiter)'
        holds.push({ candidateId: c.id, file: c.file, line: c.line, summary: c.summary, current: c.current, proposed: c.proposed, reason: 'ARBITER_HOLD — ' + a.reasoning, daStrength: d.strength })
        addSeen(c, 'HOLD')
      }
    }
  }

  // ── 5. Apply (단일 에이전트 순차 적용 → null 시 화해 → 화해도 null 시 FAIL) ──
  let appliedNow = 0, failedNow = 0
  if (approvedNow.length > 0) {
    const aIds = approvedNow.map(c => c.id)
    let ap = await agent(APPLY_PROMPT(approvedNow), { schema: applySchema(aIds), label: 'apply#' + iter, phase: 'Apply' })
    if (!ap) {
      log('Apply 에이전트 실패 — 화해 에이전트로 실제 반영 내역 재구성')
      ap = await agent(RECONCILE_PROMPT(approvedNow), { schema: applySchema(aIds), label: 'reconcile#' + iter, phase: 'Apply' })
      if (!ap) { exitStatus = 'FAIL'; exitNote = '적용 내역 미확인 — git diff 수동 검토 필요'; iterLog.push(logEntry); break }
    }
    const rmap = {}
    for (const r of ap.results) { if (aIds.includes(r.candidateId) && !rmap[r.candidateId]) rmap[r.candidateId] = r }
    for (const c of approvedNow) {
      const r = rmap[c.id] || { result: 'FAILED', reason: '적용 결과 누락' }
      const entry = logEntry.candidates.find(e => e.id === c.id)
      if (entry) entry.applyResult = r.result
      if (r.result === 'APPLIED') { appliedNow++; applied.push({ candidateId: c.id, file: c.file, line: c.line, summary: c.summary }); addSeen(c, 'APPLIED') }
      else if (r.result === 'STALE') { addSeen(c, 'STALE'); log('Apply: ' + c.id + ' STALE — 다음 스캔에서 재제안 ' + RETRY + '회 허용') }
      else { failedNow++; failed.push({ candidateId: c.id, file: c.file, summary: c.summary, reason: r.reason || '미상' }); addSeen(c, 'FAILED') }
    }
    // NO_PROGRESS: 승인>0 & 적용 0 (STALE 제외) 2회 연속
    if (appliedNow === 0 && failedNow > 0) noProgressStreak++
    else noProgressStreak = 0
    if (noProgressStreak >= 2) { exitStatus = 'BLOCKED:NO_PROGRESS'; iterLog.push(logEntry); pendingRetry = nextPending; break }
  }

  pendingRetry = nextPending
  iterLog.push(logEntry)
  log('Iteration ' + iter + ' 완료: 후보 ' + batch.length + ' / 적용 ' + appliedNow + ' / 보류 누적 ' + holds.length + ' / 재처리 대기 ' + pendingRetry.length)
}

// ═══ 종료 처리: 모든 종료 경로에서 잔존 pendingRetry를 holds로 flush (침묵 매장 금지) ═══
for (const p of pendingRetry) {
  holds.push({ candidateId: p.candidate.id, file: p.candidate.file, line: p.candidate.line, summary: p.candidate.summary, current: p.candidate.current, proposed: p.candidate.proposed, reason: p.reason + ' — 종료 시 미처리(flush)' })
  addSeen(p.candidate, 'HOLD')
}
pendingRetry = []

// 상태 판정 (flush 이후; REVIEW_INCOMPLETE가 DONE보다 우선)
let status
if (exitStatus) status = exitStatus
else {
  const allInfra = holds.length > 0 && holds.every(h => INFRA_REASONS.some(r => String(h.reason || '').indexOf(r) >= 0))
  if (applied.length === 0 && allInfra) status = 'BLOCKED:REVIEW_INCOMPLETE'
  else if (converged) status = 'DONE'
  else status = 'BLOCKED:MAX_ITERATIONS'
}
return { status, iterations: iter, applied, rejected, holds, failed, iterLog, note: exitNote }
```
