import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const PATH = '.claude/harness.config.json'
const PANE = {
  plugin: 'harness-settings',
  component: 'Pane',
  requestId: 'harness-settings',
  props: {
    title: 'Harness settings',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

// 엔진 대신 메모리 파일 1개를 둔다. 이 hook 들이 $.fs 의 바닥이다.
// 엔진은 상대 경로를 작업 디렉터리 기준 절대 경로로 바꿔 넘기므로 끝부분으로 맞춘다.
const key = (path: string) => (path.replace(/\\/g, '/').endsWith(PATH) ? PATH : path)

function memoryFs(on: On, initial?: string, commands: string[] = []) {
  const files = new Map<string, string>()
  if (initial !== undefined) files.set(PATH, initial)
  on('fs.exists', (_, e) => ({ value: files.has(key(e.path)) }))
  on('fs.read', (_, e) => ({ value: files.get(key(e.path)) ?? '' }))
  on('fs.write', (_, e) => {
    files.set(key(e.path), e.text)
    return { value: undefined }
  })
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('command.list', () => ({ value: commands.map(name => ({ name, description: '', source: 'plugin' as const })) }))
  return files
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`toggle writes the file and keeps unknown keys (${surface})`, async ($, on) => {
    const files = memoryFs(on, JSON.stringify({ custom: { keep: 1 }, review: { engine: 'gemini' } }))
    const ui = await $.ui.mount({ ...PANE, surface })

    await ui.press({ key: 'review.enabled' })
    const saved = JSON.parse(files.get(PATH) ?? '{}')
    expect(saved.review.enabled).toBe(false)
    expect(saved.review.engine).toBe('gemini')
    expect(saved.custom).toEqual({ keep: 1 })
    expect(saved.version).toBe(1)
    await ui.unmount()
  })

  test(`engine auto removes the key (${surface})`, async ($, on) => {
    const files = memoryFs(on, JSON.stringify({ review: { engine: 'codex' } }))
    const ui = await $.ui.mount({ ...PANE, surface })

    await ui.select({ key: 'review.engine', value: 'auto' })
    expect(JSON.parse(files.get(PATH) ?? '{}').review).toEqual({})
    await ui.unmount()
  })
}

test('missing file is created on the first change, with harness defaults', async ($, on) => {
  const files = memoryFs(on)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  expect((await ui.find({ type: 'Text', text: /없음/ }))?.text).toContain(PATH)
  await ui.press({ key: 'steps.reflect' })
  expect(JSON.parse(files.get(PATH) ?? '{}')).toEqual({ version: 1, steps: { reflect: true } })
  await ui.unmount()
})

test('an unparsable file is never overwritten', async ($, on) => {
  const files = memoryFs(on, '{broken')
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  expect((await ui.find({ type: 'Text', text: /파싱 실패/ }))?.text).toBeTruthy()
  expect(files.get(PATH)).toBe('{broken')
  await ui.unmount()
})

test('an invalid gemini model is refused', async ($, on) => {
  const files = memoryFs(on, '{}')
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  await ui.input({ key: 'review.gemini.model', text: 'x; rm -rf /' })
  expect(files.get(PATH)).toBe('{}')
  await ui.input({ key: 'review.gemini.model', text: 'gemini-x-pro' })
  expect(JSON.parse(files.get(PATH) ?? '{}').review.gemini.model).toBe('gemini-x-pro')
  await ui.unmount()
})

test('profile buttons show only for installed harness commands and run them', async ($, on) => {
  memoryFs(on, '{}', ['be-harness-profile'])
  const ran: string[] = []
  on('command.run', (_, e) => {
    ran.push(e.command)
    return { text: '' }
  })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  expect(await ui.find({ type: 'Button', key: 'fe-harness-profile' })).toBe(undefined)
  await ui.press({ key: 'be-harness-profile' })
  expect(ran).toEqual(['be-harness-profile'])
  await ui.unmount()
})

test('no profile section when no harness is installed', async ($, on) => {
  memoryFs(on, '{}')
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /프로필/ })).toBe(undefined)
  await ui.unmount()
})
