import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

import { isCommitCommand, parseCommits, scanUses } from './metrics'

const SUMMARY = JSON.stringify({ status: 'OK', dir: '/m', label: null, groups: [], recent: [], uncommitted: 0 })
const USAGE = { input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 100, cache_creation_input_tokens: 5 }

type Call = { argv: readonly string[]; stdin?: string }

// 엔진 대신: python helper 호출을 모으고, 비용은 cost 값을 돌려준다.
function engine(on: On, calls: Call[], cost: { usd: number }) {
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, stdin: e.init?.stdin as string | undefined })
    const stdout = e.argv.includes('record') ? JSON.stringify({ status: 'OK', commits: 1 }) : SUMMARY
    return { value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.usage', () => ({ value: { startedAt: 0, context: {} as never, rateLimits: [], cost: { usd: cost.usd } } }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('turn.complete', (_, e) => ({ text: e.answer }))
  on('session.end', (_, e) => ({ sessionId: e.sessionId }))
  on('ui.status', () => ({ value: undefined }))
}

async function bash($: Engine, id: string, command: string, output: string, isError = false, agentId?: string) {
  const loop = agentId ? { agentId } : {}
  await $.session.append({
    ...loop, door: 'response', uuid: `${id}-use`, origin: { kind: 'model', model: 'test' },
    message: { type: 'assistant', role: 'assistant', content: [{ type: 'tool_use', id, name: 'Bash', input: { command } }] },
  })
  await $.session.append({
    ...loop, door: 'tool-result', uuid: `${id}-result`, origin: { kind: 'tool', tool: 'Bash' },
    message: { type: 'user', role: 'user', content: [{ type: 'tool_result', tool_use_id: id, is_error: isError, content: [{ type: 'text', text: output }] }] },
  })
}

const prompt = ($: Engine, text: string) => $.prompt.submit({ text, origin: { kind: 'composer' }, wait: false })
const turn = ($: Engine, durationMs: number, agentId?: string) =>
  $.turn.complete({ answer: '', durationMs, isAborted: false, turnId: `t-${durationMs}`, reason: 'answer', usage: { ...USAGE, model: 'opus' }, ...(agentId ? { agentId } : {}) })

const records = (calls: Call[]) => calls.filter(call => call.argv.includes('record')).map(call => JSON.parse(call.stdin ?? '{}'))

test('isCommitCommand finds git commit forms, not dry runs or other git commands', () => {
  expect(isCommitCommand('git commit -m "x"')).toBe(true)
  expect(isCommitCommand('cd a && git -C repo commit -F msg')).toBe(true)
  expect(isCommitCommand('git -c user.name=x commit --amend')).toBe(true)
  expect(isCommitCommand('git -c "user.name=A B" commit -m x')).toBe(true)
  expect(isCommitCommand('git --git-dir=.git commit -m x')).toBe(true)
  expect(isCommitCommand('git commit -m "docs: explain --dry-run flag"')).toBe(true)
  expect(isCommitCommand('git commit --dry-run')).toBe(false)
  expect(isCommitCommand('git commit-tree abc')).toBe(false)
  expect(isCommitCommand('git log --grep commit')).toBe(false)
})

test('parseCommits reads every summary line, root commit and detached HEAD too', () => {
  const output = '[main abc1234] Feat: a\n 1 file changed\n[main (root-commit) 1234abcd] init\n[detached HEAD 9f9f9f9] x\n'
  expect(parseCommits(output, false)).toEqual([
    { short: 'abc1234', branch: 'main', amend: false },
    { short: '1234abcd', branch: 'main', amend: false },
    { short: '9f9f9f9', branch: 'detached HEAD', amend: false },
  ])
  expect(parseCommits('nothing to commit', false)).toEqual([])
})

test('scanUses counts review agents, review skills and codex calls', () => {
  const counts = scanUses([
    { type: 'tool_use', id: 'a', name: 'Agent', input: { subagent_type: 'be-harness:scope-reviewer' } },
    { type: 'tool_use', id: 'b', name: 'Agent', input: { subagent_type: 'Explore' } },
    { type: 'tool_use', id: 'c', name: 'Skill', input: { skill: 'code-review' } },
    { type: 'tool_use', id: 'd', name: 'Bash', input: { command: 'codex exec "review"' } },
    { type: 'tool_use', id: 'e', name: 'Bash', input: { command: 'cat ~/.codex/config' } },
    { type: 'tool_use', id: 'f', name: 'Bash', input: { command: 'git commit -m x' } },
  ])
  expect(counts).toEqual({ agents: 1, skills: 1, codex: 1, commits: { f: 'git commit -m x' } })
})

test('a commit made by a subagent is recorded when the main turn ends, with both token sides', async ($, on) => {
  const calls: Call[] = []
  const cost = { usd: 1 }
  engine(on, calls, cost)
  await prompt($, 'hello')
  await prompt($, 'fix it')
  await bash($, 's1', 'git commit -m "Feat: x"', '[issue/29 abc1234] Feat: x\n 2 files changed', false, 'agent-1')
  await turn($, 5000, 'agent-1')
  expect(records(calls)).toEqual([]) // subagent turn 은 기록하지 않는다.
  cost.usd = 1.5
  await turn($, 60000)
  const [record] = records(calls)
  expect(record.commits).toEqual([{ short: 'abc1234', branch: 'issue/29', amend: false }])
  expect(record.tokens.main.cacheRead).toBe(100)
  expect(record.tokens.sub.output).toBe(20)
  expect(record.models.opus).toBe(270)
  expect(record.costUsd).toBe(0.5)
  expect(record.time.activeMs).toBe(60000)
  expect(record.input).toEqual(expect.objectContaining({ prompts: 2, followUps: 1, chars: 11, denied: 0 }))
  // 기록 뒤 구간은 비워진다. 다음 main turn 은 커밋이 없으므로 기록하지 않는다.
  await turn($, 1000)
  expect(records(calls).length).toBe(1)
})

test('a quiet commit is recorded as HEAD; an OS permission error is not a denial', async ($, on) => {
  const calls: Call[] = []
  engine(on, calls, { usd: 0 })
  await bash($, 'q', 'git commit -q -m x', '')
  await bash($, 'p', './run.sh', 'bash: ./run.sh: Permission denied', true)
  await turn($, 1000)
  const [record] = records(calls)
  expect(record.commits).toEqual([{ short: 'HEAD', branch: '', amend: false }])
  expect(record.input.denied).toBe(0)
})

test('a failed record keeps the interval for the next record', async ($, on) => {
  const calls: Call[] = []
  let fail = true
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, stdin: e.init?.stdin as string | undefined })
    if (fail) return { value: { exitCode: 2, stdout: '', stderr: '{"status": "NOT_GIT_REPO", "error": "x"}', isStdoutTruncated: false, isStderrTruncated: false } }
    return { value: { exitCode: 0, stdout: JSON.stringify({ status: 'OK', commits: 2 }), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.usage', () => ({ value: { startedAt: 0, context: {} as never, rateLimits: [], cost: { usd: 0 } } }))
  on('turn.complete', (_, e) => ({ text: e.answer }))
  await bash($, 'a', 'git commit -m a', '[main aaaaaaa] a')
  await turn($, 1000)
  fail = false
  await bash($, 'b', 'git commit -m b', '[main bbbbbbb] b')
  await turn($, 2000)
  const last = JSON.parse(calls[calls.length - 1]?.stdin ?? '{}')
  expect(last.commits.map((c: { short: string }) => c.short)).toEqual(['aaaaaaa', 'bbbbbbb'])
  expect(last.time.activeMs).toBe(3000)
  expect(last.tokens.main.input).toBe(20)
})

test('metrics commands are not counted as prompts', async ($, on) => {
  const calls: Call[] = []
  engine(on, calls, { usd: 0 })
  await $.prompt.submit({ text: '/harness-metrics', command: { name: 'harness-metrics', args: '' }, origin: { kind: 'composer' }, wait: false })
  await prompt($, 'real')
  await bash($, 'c', 'git commit -m x', '[main abc1234] x')
  await turn($, 1000)
  expect(records(calls)[0].input.prompts).toBe(1)
})

test('a failed commit is not recorded; denied tool calls are counted', async ($, on) => {
  const calls: Call[] = []
  engine(on, calls, { usd: 0 })
  await bash($, 'c', 'git commit -m x', 'error: [main abc1234] hook failed', true)
  await bash($, 'd', 'rm -rf x', "The user doesn't want to proceed with this tool use. The tool use was rejected", true)
  await turn($, 1000)
  expect(records(calls)).toEqual([])
  await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } })
  const [record] = records(calls)
  expect(record.commits).toEqual([])
  expect(record.input.denied).toBe(1)
  expect(record.time.turns).toBe(1)
})
