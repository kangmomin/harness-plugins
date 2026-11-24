import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { isFinished, label, parseRun, parseState } from './register'

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

// 엔진 대신: 메모리 파일, Bash 는 정해진 출력, UI 호출은 무시.
function engine(on: On, files: Map<string, string>, bashOutput: string) {
  on('fs.exists', (_, e) => ({ value: files.has(e.path.replace(/\\/g, '/')) }))
  on('fs.read', (_, e) => ({ value: files.get(e.path.replace(/\\/g, '/')) ?? '' }))
  on('tool.call', () => ({ result: {}, text: bashOutput }))
  on('ui.status', () => ({ value: undefined }))
}

test('parseRun reads only workflow_run.py create/resume output', () => {
  expect(parseRun(COMMAND, `noise\n${RUN_JSON}\n`)?.stateFile).toBe(STATE)
  expect(parseRun('ls', RUN_JSON)).toBe(null)
  expect(parseRun(COMMAND, 'not json')).toBe(null)
  expect(parseRun(COMMAND.replace('create', 'save-verify-commands'), RUN_JSON)).toBe(null)
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
    engine(on, files, RUN_JSON)

    await $.tool.call({ tool: 'Bash', command: COMMAND })
    let band = await $.ui.mount({ ...BAND, surface })
    expect((await band.find({ type: 'Text', text: /BE · 준비 중/ }))?.text).toContain('준비 중')
    await band.unmount()

    files.set(STATE, stateText('Phase 6.2 - 구현 (agent: implementer)', ['DONE', 'IN_PROGRESS']))
    await $.tool.call({ tool: 'Edit', file_path: STATE, old_string: 'a', new_string: 'b' })
    band = await $.ui.mount({ ...BAND, surface })
    expect((await band.find({ type: 'Text', text: /Phase 6.2/ }))?.text).toBe('▶ BE · Phase 6.2 - 구현')
    await band.unmount()

    const pane = await $.ui.mount({ ...PANE, surface })
    expect((await pane.find({ type: 'Text', text: /▶ 2/ }))?.text).toContain('orchestrator')
    await pane.unmount()

    files.delete(STATE)
    await $.tool.call({ tool: 'Bash', command: 'ls' })
    band = await $.ui.mount({ ...BAND, surface })
    expect(await band.find({ type: 'Text', text: /BE ·/ })).toBe(undefined)
    await band.unmount()
  })
}

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
