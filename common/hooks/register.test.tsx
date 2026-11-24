import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

import { isFinished, label, parseRun, parseState, resultText, runCalls } from './register'

const STATE = 'C:/tmp/harness-workflow-x/workflow-state.md'
const RUN_JSON = JSON.stringify({ CWD: '/repo', MODE: 'be', RUN_ID: 'abc', STATE_FILE: STATE })
const COMMAND = 'python3 "/p/skills/start-workflow/assets/workflow_run.py" create --cwd "/repo" --mode "be"'

const stateText = (current: string, statuses: string[]) => `## Run
- MODE: be

## Current Phase
${current}

## Phase Assignments
| Phase | Agent | Model | Effort | Status |
|-------|-------|-------|--------|--------|
${statuses.map((status, i) => `| ${i + 1} | orchestrator | 현재 세션 | 현재 세션 | ${status} |`).join('\n')}

## Remaining Phases
- Phase 8: 품질 루프
`

const BAND = {
  plugin: 'common',
  component: 'AbovePrompt',
  requestId: 'band',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 5, bodyColumns: 60, scroll: { offset: 0, bodyRows: 5 }, view: {} },
} as const

const PANE = {
  plugin: 'common',
  component: 'Pane',
  requestId: 'harness-progress',
  props: { title: 'Workflow progress', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const slash = (path: string) => path.split('\\').join('/')

// 엔진 대신: 메모리 파일, UI 호출은 무시.
function engine(on: On, files: Map<string, string>) {
  on('fs.exists', (_, e) => ({ value: files.has(slash(e.path)) }))
  on('fs.read', (_, e) => ({ value: files.get(slash(e.path)) ?? '' }))
  on('ui.status', () => ({ value: undefined }))
}

// 엔진이 대화에 저장하는 두 행(모델의 Bash 호출, 그 결과)을 올린다. common 의 session.append hook 이 읽는다.
async function bash($: Engine, id: string, command: string, output: string, isError = false) {
  await $.session.append({
    door: 'response', uuid: `${id}-use`, origin: { kind: 'model', model: 'test' },
    message: { type: 'assistant', role: 'assistant', content: [{ type: 'tool_use', id, name: 'Bash', input: { command } }] },
  })
  await $.session.append({
    door: 'tool-result', uuid: `${id}-result`, origin: { kind: 'tool', tool: 'Bash' },
    message: { type: 'user', role: 'user', content: [{ type: 'tool_result', tool_use_id: id, is_error: isError, content: [{ type: 'text', text: output }] }] },
  })
}

async function bandText($: Engine, surface: 'terminal' | 'desktop') {
  const band = await $.ui.mount({ ...BAND, surface })
  const text = (await band.find({ type: 'Text', text: /·/ }))?.text
  await band.unmount()
  return text
}

test('parseRun reads only workflow_run.py create/resume output', () => {
  expect(parseRun(COMMAND, `noise\n${RUN_JSON}\n`)?.stateFile).toBe(STATE)
  expect(parseRun('ls', RUN_JSON)).toBe(null)
  expect(parseRun(COMMAND, 'not json')).toBe(null)
  expect(parseRun(COMMAND.replace('create', 'save-verify-commands'), RUN_JSON)).toBe(null)
})

test('runCalls finds only workflow_run.py Bash calls; resultText joins text parts', () => {
  const content = [
    { type: 'text', text: 'hi' },
    { type: 'tool_use', id: 'a', name: 'Bash', input: { command: COMMAND } },
    { type: 'tool_use', id: 'b', name: 'Bash', input: { command: 'ls' } },
    { type: 'tool_use', id: 'c', name: 'Read', input: { file_path: 'workflow_run.py create' } },
  ]
  expect(runCalls(content)).toEqual({ a: COMMAND })
  expect(resultText({ type: 'tool_result', content: 'plain' })).toBe('plain')
  expect(resultText({ type: 'tool_result', content: [{ type: 'text', text: 'a' }, { type: 'text', text: 'b' }] })).toBe('ab')
})

test('parseState reads current phase and the table, skipping header rows', () => {
  const parsed = parseState(stateText('Phase 8 - 품질 루프 (agent: quality)', ['DONE', 'IN_PROGRESS', 'PENDING']))
  expect(parsed.current).toBe('Phase 8 - 품질 루프 (agent: quality)')
  expect(parsed.rows.map(row => row.status)).toEqual(['DONE', 'IN_PROGRESS', 'PENDING'])
  expect(isFinished(parsed.rows)).toBe(false)
  expect(isFinished(parseState(stateText('Phase 12', ['DONE', 'DONE'])).rows)).toBe(true)
  expect(isFinished([])).toBe(false)
  expect(label('be', parsed.current)).toBe('BE · Phase 8 - 품질 루프')
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`band follows the state file and ends when archived (${surface})`, async ($, on) => {
    const files = new Map<string, string>()
    engine(on, files)

    await bash($, 't1', COMMAND, `${RUN_JSON}\n`)
    expect(await bandText($, surface)).toBe('▶ BE · 준비 중')

    files.set(STATE, stateText('Phase 6.2 - 구현 (agent: implementer)', ['DONE', 'IN_PROGRESS']))
    await bash($, 't2', 'git status', '')
    expect(await bandText($, surface)).toBe('▶ BE · Phase 6.2 - 구현')

    const pane = await $.ui.mount({ ...PANE, surface })
    expect((await pane.find({ type: 'Text', text: /▶ 2/ }))?.text).toContain('orchestrator')
    await pane.unmount()

    files.delete(STATE)
    await bash($, 't3', 'ls', '')
    expect(await bandText($, surface)).toBe(undefined)
  })
}

test('a workflow_run.py call that errored starts no run', async ($, on) => {
  engine(on, new Map())
  await bash($, 'x', COMMAND, RUN_JSON, true)
  expect(await bandText($, 'terminal')).toBe(undefined)
})

test('language block is appended after the engine blocks', async ($, on) => {
  on('prompt.context', () => ({ blocks: [{ name: 'currentDate', text: 'today' }] }))
  const added = await $.prompt.context({ blocks: [] })
  expect(added.blocks.map(block => block.name)).toEqual(['currentDate', 'harnessLanguage'])
})

test('language block is not added twice (work-log mod added it first)', async ($, on) => {
  on('prompt.context', () => ({ blocks: [{ name: 'harnessLanguage', text: 'x' }] }))
  const added = await $.prompt.context({ blocks: [] })
  expect(added.blocks.map(block => block.name)).toEqual(['harnessLanguage'])
})
