import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const PLUGIN = 'fe-harness'
const RUN = { command: `${PLUGIN}-profile`, args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 120 } } as const
const PANE = {
  plugin: PLUGIN,
  component: 'Pane',
  requestId: `${PLUGIN}-profile`,
  props: { title: 'profile', isFocused: false, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const done = (stdout: object) => ({ value: { exitCode: 0, stdout: JSON.stringify(stdout), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })

// 엔진 대신 profile.py 를 흉내 낸다. 값은 메모리에 두고, 호출 순서를 기록한다.
function fakeHelper(on: On, opts: { values?: Record<string, unknown>; writable?: boolean; stderr?: string }) {
  const values: Record<string, unknown> = { ...(opts.values ?? {}) }
  const calls: string[] = []
  on('process.run', (_, e) => {
    const action = e.argv[4] ?? ''
    calls.push([action, ...e.argv.filter(a => a === '--apply')].join(' '))
    if (opts.stderr) return { value: { exitCode: 1, stdout: '', stderr: opts.stderr, isStdoutTruncated: false, isStderrTruncated: false } }
    if (action === 'resolve') return done({ values, sources: {}, writable: opts.writable ?? true, profile_path: '/repo/.claude/x.local.md' })
    const changes = JSON.parse(e.init?.stdin ?? '{}')
    const changed = Object.entries(changes).some(([k, v]) => values[k] !== v)
    if (e.argv.includes('--apply')) {
      Object.assign(values, changes)
      return done({ status: 'DONE', changed, sha256_before: 'abc' })
    }
    return done({ status: 'PREVIEW', changed, sha256_before: 'abc', preview: '' })
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', () => ({ value: undefined }))
  return { values, calls }
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`select runs preview then apply with the sha (${surface})`, async ($, on) => {
    const helper = fakeHelper(on, { values: { codexMode: 'mix', language: 'ko' } })
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.select({ key: 'codexMode', value: 'max' })
    expect(helper.values.codexMode).toBe('max')
    expect(helper.calls).toEqual(['resolve', 'edit', 'edit --apply', 'resolve'])
    await ui.unmount()
  })

  test(`unchanged value is not applied (${surface})`, async ($, on) => {
    const helper = fakeHelper(on, { values: { language: 'ko' } })
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.select({ key: 'language', value: 'ko' })
    expect(helper.calls).toEqual(['resolve', 'edit', 'resolve'])
    await ui.unmount()
  })

  test(`no profile file shows the init hint and no fields (${surface})`, async ($, on) => {
    fakeHelper(on, { writable: false })
    await $.command.run(RUN)
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /init/ }))?.text).toContain(`/${PLUGIN}:init`)
    await ui.unmount()
  })

  test(`POSIX-only helper on Windows shows a clear error (${surface})`, async ($, on) => {
    fakeHelper(on, { stderr: "ModuleNotFoundError: No module named 'fcntl'" })
    const result = await $.command.run(RUN)
    expect(result.text).toContain('POSIX')
  })
}
