import { atom, read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { MetricsSummary, SeenCommit, Segment, Tokens } from '../types'

// 커밋 단위 사용량 측정 (#29). 세션 이벤트를 세어 구간에 누적하고, 커밋이 들어간 main turn 이 끝나면
// metrics.py record 로 넘긴다. 기록·집계의 정본은 metrics.py 이다. 이 mod 는 세고 표시만 한다.

export const METRICS_PANE = 'harness-metrics'
const LABEL_COMMAND = 'harness-metrics-label'

const segment = atom({ plugin: 'common', key: 'segment' } as const, null)
const view = atom({ plugin: 'common', key: 'metricsView' } as const, {})
// register.tsx 의 진행 표시 atom 과 같은 ref. 읽기만 한다.
const run = atom({ plugin: 'common', key: 'run' } as const, null)
const progress = atom({ plugin: 'common', key: 'progress' } as const, null)

type Block = { readonly type: string; readonly [field: string]: unknown }
export type Workflow = { runId: string; mode: string; current: string; done: number; total: number } | null

const zero = (): Tokens => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 })

export function emptySegment(now: number, costAt: number | null): Segment {
  return {
    startedAt: now, costAt, tokens: { main: zero(), sub: zero() }, models: {}, activeMs: 0, turns: 0,
    prompts: 0, chars: 0, commands: 0, followUps: 0, aborted: 0, denied: 0,
    reviewAgents: 0, reviewSkills: 0, codex: 0, commits: [], waiting: {},
  }
}

// 따옴표 안 문자열(커밋 메시지 등)을 지운 명령. 메시지 안의 `--dry-run`·`-q` 를 옵션으로 읽지 않게 한다.
const unquoted = (command: string) => command.replace(/"(?:[^"\\]|\\.)*"|'[^']*'/g, '""')

// `git commit`, `git -C x commit`, `git -c "k=v w" commit`, `git --git-dir=x commit` 를 찾는다.
// `commit-tree` 는 아니다. 따옴표 밖의 --dry-run 은 커밋이 아니다.
const COMMIT = /\bgit(?:\s+(?:-[Cc]\s+(?:"[^"]*"|'[^']*'|\S+)|--[\w-]+(?:=\S+)?))*\s+commit(?![\w-])/
export const isCommitCommand = (command: string) => COMMIT.test(command) && !/(?:^|\s)--dry-run(?:\s|$)/.test(unquoted(command))
const isQuiet = (command: string) => /(?:^|\s)(?:-q|--quiet)(?:\s|$)/.test(unquoted(command))

// git commit 출력의 요약 줄 `[branch (root-commit) abc1234] 제목`. detached HEAD 처럼 branch 에 공백이 있어도 읽는다.
export function parseCommits(output: string, amend: boolean): SeenCommit[] {
  const found: SeenCommit[] = []
  for (const match of output.matchAll(/^\[(.+?)(?: \(root-commit\))? ([0-9a-f]{7,40})\] /gm)) {
    found.push({ short: match[2] ?? '', branch: match[1] ?? '', amend })
  }
  return found
}

const REVIEW_AGENT = /review|verif/i
const REVIEW_SKILL = /review|verify|convention-check|simplify/i
// 셸 단어로 codex 를 실행하는 호출. 경로나 문자열 안의 codex 는 세지 않는다.
const CODEX = /(?:^|[\s;&|(])codex(?:\s|$)/
// Claude Code 가 거부된 tool 호출에 돌려주는 문장.
const DENIED = /doesn't want to proceed|tool use was rejected/i

export type Counts = { agents: number; skills: number; codex: number; commits: Record<string, string> }

// assistant 행의 tool_use 를 센다. commits: 결과를 기다릴 git commit 호출.
export function scanUses(content: readonly Block[]): Counts {
  const counts: Counts = { agents: 0, skills: 0, codex: 0, commits: {} }
  for (const block of content) {
    if (block.type !== 'tool_use') continue
    const input = (block.input ?? {}) as Record<string, unknown>
    if ((block.name === 'Agent' || block.name === 'Task') && REVIEW_AGENT.test(String(input.subagent_type ?? ''))) counts.agents++
    if (block.name === 'Skill' && REVIEW_SKILL.test(String(input.skill ?? ''))) counts.skills++
    if (block.name !== 'Bash' || typeof input.command !== 'string') continue
    if (CODEX.test(input.command)) counts.codex++
    if (typeof block.id === 'string' && isCommitCommand(input.command)) counts.commits[block.id] = input.command
  }
  return counts
}

export function isDenied(block: Block, text: string): boolean {
  return block.is_error === true && DENIED.test(text)
}

// common register.tsx 의 resultText 와 같은 규칙. 순환 import 를 피하려고 따로 둔다.
function textOf(block: Block): string {
  const content = block.content
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content.map(part => (part && typeof part === 'object' && typeof part.text === 'string' ? part.text : '')).join('')
}

function addTokens(into: Tokens, usage: { input_tokens: number; output_tokens: number; cache_read_input_tokens: number; cache_creation_input_tokens: number }): Tokens {
  return {
    input: into.input + (usage.input_tokens || 0),
    output: into.output + (usage.output_tokens || 0),
    cacheRead: into.cacheRead + (usage.cache_read_input_tokens || 0),
    cacheWrite: into.cacheWrite + (usage.cache_creation_input_tokens || 0),
  }
}

export const sumTokens = (t: Tokens) => t.input + t.output + t.cacheRead + t.cacheWrite

async function costNow($: EngineInterface): Promise<number | null> {
  try {
    const { cost } = await $.session.usage()
    return !cost || cost.hasUnknownPrice ? null : cost.usd
  } catch {
    return null
  }
}

async function ensure($: EngineInterface): Promise<void> {
  if (await read($, segment)) return
  const costAt = await costNow($)
  await update($, segment, current => current ?? emptySegment(Date.now(), costAt))
}

async function change($: EngineInterface, fn: (s: Segment) => Segment): Promise<void> {
  await ensure($)
  await update($, segment, current => (current ? fn(current) : current))
}

// be/fe register.tsx helper() 와 같은 python 후보 순서. metrics.py 는 POSIX 전용 모듈을 쓰지 않는다.
async function helper($: EngineInterface, args: readonly string[], stdin?: string): Promise<any> {
  const script = `${$.plugin.root}/hooks/metrics.py`
  let last = ''
  for (const python of ['python3', 'python']) {
    let out
    try {
      out = await $.process.run([python, '-I', '-B', script, ...args, '--cwd', '.'], { stdin, timeoutMs: 20000 })
    } catch (err) {
      last = String(err)
      continue
    }
    if (out.exitCode === 0) return JSON.parse(out.stdout)
    const failed = out.stderr.match(/\{.*"status".*\}/)
    if (failed) throw new Error(JSON.parse(failed[0]).error)
    if (/Traceback|metrics\.py/.test(out.stderr)) throw new Error(out.stderr.trim().split('\n').pop() || `exit ${out.exitCode}`)
    last = out.stderr.trim() || `${python} exit ${out.exitCode}`
  }
  throw new Error(`python 을 실행하지 못했습니다: ${last}`)
}

export function payload(s: Segment, now: number, cost: number | null, workflow: Workflow) {
  return {
    startedAt: s.startedAt,
    tokens: s.tokens,
    models: s.models,
    // 비용이 줄었으면 세션 합계가 새로 시작된 것이다(/clear, 새 세션). 그때는 지금 값 전체가 이 구간 비용이다.
    costUsd: cost === null || s.costAt === null ? null : cost >= s.costAt ? cost - s.costAt : cost,
    time: { wallMs: now - s.startedAt, activeMs: s.activeMs, turns: s.turns },
    input: {
      prompts: s.prompts, chars: s.chars, avgChars: s.prompts ? Math.round(s.chars / s.prompts) : 0,
      commands: s.commands, followUps: s.followUps, aborted: s.aborted, denied: s.denied,
    },
    review: { agents: s.reviewAgents, skills: s.reviewSkills, codex: s.codex, workflow },
    commits: s.commits,
  }
}

// 측정 기록에 붙이는 진행 중 workflow 요약. 진행 표시 atom 을 그대로 읽는다.
async function workflow($: EngineInterface): Promise<Workflow> {
  const active = await read($, run)
  if (!active) return null
  const state = await read($, progress)
  const rows = state?.rows ?? []
  return { runId: active.runId, mode: active.mode, current: state?.current ?? '', done: rows.filter(row => row.status === 'DONE').length, total: rows.length }
}

const addAll = (a: Tokens, b: Tokens): Tokens => ({ input: a.input + b.input, output: a.output + b.output, cacheRead: a.cacheRead + b.cacheRead, cacheWrite: a.cacheWrite + b.cacheWrite })

// 기록하지 못한 구간(old)을 그 뒤에 쌓인 구간(now)과 합친다. 시작 시각·기준 비용은 old 것을 쓴다.
export function merge(old: Segment, now: Segment): Segment {
  const models: Record<string, number> = { ...old.models }
  for (const [model, n] of Object.entries(now.models)) models[model] = (models[model] ?? 0) + n
  return {
    startedAt: old.startedAt, costAt: old.costAt,
    tokens: { main: addAll(old.tokens.main, now.tokens.main), sub: addAll(old.tokens.sub, now.tokens.sub) }, models,
    activeMs: old.activeMs + now.activeMs, turns: old.turns + now.turns, prompts: old.prompts + now.prompts,
    chars: old.chars + now.chars, commands: old.commands + now.commands, followUps: old.followUps + now.followUps,
    aborted: old.aborted + now.aborted, denied: old.denied + now.denied, reviewAgents: old.reviewAgents + now.reviewAgents,
    reviewSkills: old.reviewSkills + now.reviewSkills, codex: old.codex + now.codex,
    commits: [...old.commits, ...now.commits], waiting: now.waiting,
  }
}

const isEmpty = (s: Segment) => s.commits.length === 0 && s.turns === 0 && s.prompts === 0

async function flush($: EngineInterface): Promise<void> {
  const before = await read($, segment)
  if (!before || isEmpty(before)) return
  const now = Date.now()
  const cost = await costNow($)
  const flow = await workflow($)
  // 읽기와 비우기를 한 update 안에서 한다. 그 사이의 await 동안 들어온 이벤트를 잃지 않는다.
  // 결과를 기다리는 commit 호출(waiting)은 다음 구간으로 넘긴다.
  let taken: Segment | null = null
  await update($, segment, s => {
    taken = s
    return { ...emptySegment(now, cost), waiting: s?.waiting ?? {} }
  })
  const current = taken as Segment | null
  if (!current || isEmpty(current)) return
  const body = payload(current, now, cost, flow)
  try {
    const result = await helper($, ['record'], JSON.stringify(body))
    await update($, view, v => ({ ...v, error: undefined, lastRecord: `${result.commits}개 커밋 기록 · ${sumTokens(body.tokens.main) + sumTokens(body.tokens.sub)} tokens` }))
    // 집계는 pane 을 연 적이 있을 때만 갱신한다. 커밋마다 python 을 두 번 기다리지 않게 한다.
    if ((await read($, view)).summary) await load($)
  } catch (err) {
    // 기록은 부가 기능이다. 구간을 되돌려 다음 기록에서 다시 시도하고, 원인을 pane 에 남긴다.
    await update($, segment, s => (s ? merge(current, s) : current))
    await update($, view, v => ({ ...v, error: `기록 실패 (다음 기록에서 다시 시도): ${err instanceof Error ? err.message : String(err)}` }))
  }
}

async function load($: EngineInterface): Promise<void> {
  try {
    const summary = (await helper($, ['summary'])) as MetricsSummary
    await update($, view, v => ({ ...v, summary }))
  } catch (err) {
    await update($, view, v => ({ ...v, error: `집계 실패: ${err instanceof Error ? err.message : String(err)}` }))
  }
}

const fmt = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n))

// session.start·session.end 는 matcher 없이 한 번만 hook 할 수 있다. register.tsx 의 hook 이 아래 두 함수를 부른다.
export async function registerMetricsCommands($: EngineInterface): Promise<void> {
  await $.command.register({ name: METRICS_PANE, description: '커밋 단위 Claude 사용량과 label 별 비교 pane 을 연다' })
  await $.command.register({ name: LABEL_COMMAND, description: '측정 label 을 정한다 (예: before-tdd). 인자가 없으면 해제', argumentHint: '[label]' })
}

// 세션이 끝나면 커밋되지 않은 구간도 기록한다 (summary 의 uncommitted).
export async function flushOnEnd($: EngineInterface): Promise<void> {
  try {
    await flush($)
  } catch {
    // 종료를 막지 않는다.
  }
}

export function registerMetrics(on: On): void {
  // 사람이 보낸 프롬프트만 센다 (reminder·작업 알림 제외).
  on('prompt.submit', async ($, e, next) => {
    const result = await next(e)
    try {
      const own = e.command?.name === METRICS_PANE || e.command?.name === LABEL_COMMAND
      if (!('drop' in result) && !e.isMeta && !own && (e.origin.kind === 'composer' || e.origin.kind === 'bridge')) {
        await change($, s => ({
          ...s,
          prompts: s.prompts + 1,
          followUps: s.followUps + (s.prompts > 0 ? 1 : 0),
          chars: s.chars + e.text.length,
          commands: s.commands + (e.command ? 1 : 0),
        }))
      }
    } catch {
      // 측정 실패는 프롬프트를 막지 않는다.
    }
    return result
  }).catch(($, e, next) => next(e))

  // turn.complete 의 usage 는 그 turn 의 실제 요청 합계다. 중단·API 오류 turn 은 usage 가 없다.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    try {
      const usage = e.usage
      const side = e.agentId ? 'sub' : 'main'
      await change($, s => ({
        ...s,
        tokens: usage ? { ...s.tokens, [side]: addTokens(s.tokens[side], usage) } : s.tokens,
        models: usage ? { ...s.models, [usage.model]: (s.models[usage.model] ?? 0) + sumTokens(addTokens(zero(), usage)) } : s.models,
        // subagent 시간은 main turn 안에 겹친다. 활동 시간은 main 만 더한다.
        activeMs: s.activeMs + (e.agentId ? 0 : e.durationMs),
        turns: s.turns + (e.agentId ? 0 : 1),
        aborted: s.aborted + (!e.agentId && e.isAborted ? 1 : 0),
      }))
      // 커밋은 turn 중간에 생긴다. 그 turn 의 토큰까지 넣으려고 main turn 이 끝날 때 기록한다.
      if (!e.agentId && ((await read($, segment))?.commits.length ?? 0) > 0) await flush($)
    } catch {
      // 측정 실패는 turn 결과에 영향이 없다.
    }
    return result
  })

  // main·subagent 행을 모두 본다. 커밋은 subagent(workflow-implementer 등)도 만든다.
  on('session.append', { door: ['response', 'tool-result'] }, async ($, e, next) => {
    const stored = await next(e)
    try {
      const content = e.message.content as readonly Block[]
      if (e.door === 'response') {
        const counts = scanUses(content)
        if (counts.agents + counts.skills + counts.codex + Object.keys(counts.commits).length > 0) {
          await change($, s => ({
            ...s,
            reviewAgents: s.reviewAgents + counts.agents,
            reviewSkills: s.reviewSkills + counts.skills,
            codex: s.codex + counts.codex,
            waiting: { ...s.waiting, ...counts.commits },
          }))
        }
        return stored
      }
      const results = content.filter(block => block.type === 'tool_result')
      if (results.length === 0) return stored
      const waiting = (await read($, segment))?.waiting ?? {}
      let denied = 0
      const commits: SeenCommit[] = []
      const done: string[] = []
      for (const block of results) {
        const text = textOf(block)
        if (isDenied(block, text)) denied++
        const id = String(block.tool_use_id ?? '')
        const command = waiting[id]
        if (command === undefined) continue
        done.push(id)
        if (block.is_error === true) continue
        const amend = /(?:^|\s)--amend(?:\s|$)/.test(unquoted(command))
        const found = parseCommits(text, amend)
        // -q 커밋은 요약 줄을 출력하지 않는다. helper 가 기록 시점의 HEAD 로 푼다.
        commits.push(...(found.length === 0 && isQuiet(command) ? [{ short: 'HEAD', branch: '', amend }] : found))
      }
      if (denied + commits.length + done.length > 0) {
        await change($, s => ({
          ...s,
          denied: s.denied + denied,
          commits: [...s.commits, ...commits],
          waiting: Object.fromEntries(Object.entries(s.waiting).filter(([key]) => !done.includes(key))),
        }))
      }
    } catch {
      // 측정 실패는 행 저장에 영향이 없다.
    }
    return stored
  }).catch(($, e, next) => next(e))

  on('command.run', { command: METRICS_PANE }, async $ => {
    await $.ui.open({ id: METRICS_PANE, title: 'Harness metrics' })
    await load($)
    const summary = (await read($, view)).summary
    return { text: summary ? `pane 을 열었습니다. 기록 폴더: ${summary.dir}` : 'pane 을 열었습니다.', isTextDisplayOnly: true }
  })

  on('command.run', { command: LABEL_COMMAND }, async ($, e) => {
    const name = e.args.trim()
    try {
      const result = await helper($, name ? ['label', '--set', name] : ['label', '--clear'])
      await load($)
      return { text: result.label ? `측정 label: ${result.label}. 다음 기록부터 적용됩니다.` : '측정 label 을 해제했습니다. 플러그인 버전으로 묶습니다.', isTextDisplayOnly: true }
    } catch (err) {
      return { text: `label 을 바꾸지 못했습니다: ${err instanceof Error ? err.message : String(err)}`, isTextDisplayOnly: true }
    }
  })

  on('ui.render', { component: 'Pane', requestId: METRICS_PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const state = await read($, view)
    const live = await read($, segment)
    const summary = state.summary
    const liveTokens = live ? sumTokens(live.tokens.main) + sumTokens(live.tokens.sub) : 0
    return (
      <Box flexDirection="column">
        <Text bold>현재 구간 · label: {summary?.label ?? '(없음 → 플러그인 버전)'}</Text>
        <Text>
          {fmt(liveTokens)} tokens · 프롬프트 {live?.prompts ?? 0} · 활동 {Math.round((live?.activeMs ?? 0) / 60000)}분 · 대기 커밋 {live?.commits.length ?? 0}
        </Text>
        {state.lastRecord ? <Text dimColor>최근 기록: {state.lastRecord}</Text> : null}
        {state.error ? <Text color="error" wrap="truncate">{state.error}</Text> : null}
        <Text bold>label 별 커밋당 평균 (비용은 추정값)</Text>
        <Text dimColor>{'label'.padEnd(18)} {'커밋'.padStart(4)} {'tokens'.padStart(8)} {'$'.padStart(6)} {'분'.padStart(5)} {'입력'.padStart(4)} {'후속'.padStart(4)} {'거부'.padStart(4)} {'리뷰'.padStart(4)} {'tok/줄'.padStart(7)}</Text>
        {(summary?.groups ?? []).map(g => (
          <Text key={g.label} wrap="truncate">
            {g.label.slice(0, 18).padEnd(18)} {String(g.commits).padStart(4)} {fmt(g.avgTokens).padStart(8)} {g.avgCostUsd.toFixed(2).padStart(6)} {String(g.avgActiveMin).padStart(5)} {String(g.avgPrompts).padStart(4)} {String(g.avgFollowUps).padStart(4)} {String(g.avgDenied).padStart(4)} {String(g.avgReviews).padStart(4)} {(g.tokensPerLine === null ? '-' : fmt(g.tokensPerLine)).padStart(7)}
          </Text>
        ))}
        {summary && summary.groups.length === 0 ? <Text dimColor>아직 기록된 커밋이 없습니다.</Text> : null}
        <Text bold>최근 커밋</Text>
        {(summary?.recent ?? []).map(r => (
          <Text key={`${r.ts}-${r.short}`} wrap="truncate">
            {r.short} {fmt(r.tokens).padStart(7)}{r.shared > 1 ? `/${r.shared}` : ''} [{r.label}] {r.subject ?? ''}
          </Text>
        ))}
        {summary ? <Text dimColor wrap="truncate">미커밋 구간 {summary.uncommitted} · {summary.dir}</Text> : null}
      </Box>
    )
  })
}
