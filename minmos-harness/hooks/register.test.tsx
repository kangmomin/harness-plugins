import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { summary } from './register'

const RUN = { command: 'minmos-status', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 120 } } as const
const PANE = {
  plugin: 'minmos-harness',
  component: 'Pane',
  requestId: 'minmos-status',
  props: { title: 'minmos-harness', isFocused: false, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

// 엔진 대신: 정해진 env·파일·도구 목록.
function engine(on: On, opts: { env: Record<string, string>; files: string[]; tools: string[] }) {
  on('env.get', (_, e) => ({ value: opts.env[e.name] }))
  on('fs.exists', (_, e) => ({ value: opts.files.some(path => e.path.replace(/\\/g, '/').endsWith(path)) }))
  on('tool.list', () => ({ value: opts.tools.map(name => ({ name, description: '', mcp: true })) }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
}

test('summary counts warnings', () => {
  expect(summary([])).toBe('minmos: ✓')
  expect(summary([{ id: 'a', label: 'a', ok: false, hint: '' }, { id: 'b', label: 'b', ok: true, hint: '' }])).toBe('minmos: ⚠1')
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`all present reads OK (${surface})`, async ($, on) => {
    engine(on, {
      env: { APIDOG_ACCESS_TOKEN: 't', APIDOG_PROJECT_ID: 'p' },
      files: ['secret/.env', '.conventions.json', 'infra/flyway/migrations'],
      tools: ['mcp__apidog__read_project_oas_x', 'mcp__postgres__query'],
    })
    const result = await $.command.run(RUN)
    expect(result.text).toBe('minmos: ✓')
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: /WARN/ })).toBe(undefined)
    await ui.unmount()
  })

  test(`missing items read WARN without showing env values (${surface})`, async ($, on) => {
    engine(on, { env: { APIDOG_PROJECT_ID: 'secret-id' }, files: [], tools: [] })
    const result = await $.command.run(RUN)
    expect(result.text).toBe('minmos: ⚠6')
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /APIDOG_ACCESS_TOKEN/ }))?.text).toContain('Apidog Push')
    expect(await ui.find({ type: 'Text', text: /secret-id/ })).toBe(undefined)
    await ui.unmount()
  })
}
