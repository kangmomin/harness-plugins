import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { age, isStale, pendingText, STALE_SECONDS } from './register'

const PANE = {
  plugin: 'work-log',
  component: 'Pane',
  requestId: 'work-log-status',
  props: { title: 'work-log', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

// 사람이 /work-log-status 를 입력한 것과 같은 입력.
const RUN = { command: 'work-log-status', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 120 } } as const

const STATUS = { scope: 'global', root: '/vault', indexExists: true, indexAgeSeconds: 120, indexState: 'OK', counts: { canonical: 3 }, errors: [] }

// 엔진 대신 MCP 서버를 둔다. calls 에 호출한 도구 이름을 남긴다.
function server(on: On, status: object | null, calls: string[] = []) {
  on('mcp.call', (_, e) => {
    calls.push(e.tool)
    if (status === null) return { value: { content: [{ type: 'text', text: 'not connected' }], isError: true } }
    return { value: { content: [{ type: 'text', text: JSON.stringify(status) }], isError: false } }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', () => ({ value: undefined }))
  on('command.register', () => ({ value: { command: 'work-log-status' } }))
  return calls
}

test('age formats seconds', () => {
  expect(age(null)).toBe('없음')
  expect(age(120)).toBe('2분 전')
  expect(age(7200)).toBe('2시간 전')
  expect(age(3 * 86400)).toBe('3일 전')
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`pane shows status and sync calls wiki_sync (${surface})`, async ($, on) => {
    const calls = server(on, STATUS)
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /인덱스:/ }))?.text).toContain('2분 전')

    await ui.press({ key: 'sync' })
    expect(calls).toContain('wiki_sync')
    await ui.unmount()
  })

  test(`pane shows init hint when scope is missing (${surface})`, async ($, on) => {
    server(on, { needsInit: true, hint: 'run init' })
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /init/ }))?.text).toContain('/work-log:init')
    await ui.unmount()
  })

  test(`pane shows the default path while the fallback folder is pending (${surface})`, async ($, on) => {
    server(on, { pending: true, root: '/home/u/.harness-plugin/work-log', configSource: 'default:harness-plugin', hint: 'first write creates it' })
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /기본 경로 사용 예정/ }))?.text).toContain('/home/u/.harness-plugin/work-log')
    expect(await ui.find({ type: 'Text', text: /인덱스:/ })).toBeUndefined()
    await ui.unmount()
  })

  test(`pane shows error when MCP fails (${surface})`, async ($, on) => {
    server(on, null)
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /not connected/ }))?.text).toContain('not connected')
    await ui.unmount()
  })
}

test('isStale covers a missing index and an old one', () => {
  expect(isStale({ indexExists: false, indexAgeSeconds: null })).toBe(true)
  expect(isStale({ indexExists: true, indexAgeSeconds: 2 * STALE_SECONDS })).toBe(true)
  expect(isStale({ indexExists: true, indexAgeSeconds: 60 })).toBe(false)
})

test('pendingText names the root that the first write will create', () => {
  expect(pendingText({ pending: true, root: '/r' })).toBe('기본 경로 사용 예정: /r (첫 쓰기 때 생성)')
  expect(pendingText({ pending: true })).toContain('-')
})

test('a DEGRADED sync is not reported as success', async ($, on) => {
  const toasts: string[] = []
  on('mcp.call', (_, e) => {
    const body = e.tool === 'wiki_sync' ? { status: 'DEGRADED', errors: [1, 2] } : STATUS
    return { value: { content: [{ type: 'text', text: JSON.stringify(body) }], isError: false } }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', (_, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  await $.command.run(RUN)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'sync' })
  expect(toasts).toEqual(['work-log 인덱스 갱신: DEGRADED (오류 2건)'])
  await ui.unmount()
})

test('language block is not added twice', async ($, on) => {
  on('prompt.context', () => ({ blocks: [{ name: 'harnessLanguage', text: 'x' }] }))
  expect((await $.prompt.context({ blocks: [] })).blocks.length).toBe(1)
})
