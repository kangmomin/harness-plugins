import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

// 하네스 resolver(harness_config.py)와 같은 경로·키. 파일이 단일 출처이며 이 mod 는 편집기일 뿐이다.
export const CONFIG_PATH = '.claude/harness.config.json'
const PANE = 'harness-settings'
// harness_config.py 와 같은 규칙: '-' 로 시작하면 gemini CLI 플래그로 읽히므로 첫 글자는 영숫자.
const MODEL = /^(?:[A-Za-z0-9][A-Za-z0-9._:/-]*)?$/

const rev = atom({ plugin: 'harness-settings', key: 'rev' } as const, 0)

type Json = Record<string, unknown>
type Loaded = { data: Json; error?: string; exists: boolean }

// [키 경로, 라벨, 키가 없을 때 하네스가 쓰는 기본값]
const TOGGLES: ReadonlyArray<readonly [string, string, boolean]> = [
  ['review.enabled', '타 모델 리뷰 (전체)', true],
  ['review.points.plan', '  Plan 리뷰', true],
  ['review.points.quality', '  품질 리뷰', true],
  ['steps.ocr', 'OCR 보조 입력', true],
  ['steps.e2e', 'E2E', true],
  ['steps.simplifyLoop', 'simplify-loop', true],
  ['steps.reflect', '성찰 (reflect)', false],
]
const ENGINES = ['auto', 'codex', 'gemini', 'claude'] as const
// 프로필 편집은 profile.py 를 가진 be/fe-harness mod 가 맡는다. 여기서는 설치된 쪽의 pane 만 연다.
const PROFILE_COMMANDS: ReadonlyArray<readonly [string, string]> = [
  ['be-harness-profile', 'BE 프로필 편집'],
  ['fe-harness-profile', 'FE 프로필 편집'],
]

async function openProfile($: EngineInterface, command: string): Promise<void> {
  try {
    await $.command.run({ command })
  } catch (err) {
    $.ui.toast(`/${command} 실행 실패: ${err instanceof Error ? err.message : String(err)}`)
  }
}

export function getPath(data: Json, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, key) => (node && typeof node === 'object' ? (node as Json)[key] : undefined),
    data,
  )
}

// 모르는 키는 보존한다. value === undefined 면 키를 지운다(= 하네스 기본값).
export function setPath(data: Json, path: string, value: unknown): Json {
  const [head = '', ...rest] = path.split('.')
  const next: Json = { ...data }
  if (rest.length === 0) {
    if (value === undefined) delete next[head]
    else next[head] = value
    return next
  }
  const child = next[head]
  next[head] = setPath(child && typeof child === 'object' && !Array.isArray(child) ? (child as Json) : {}, rest.join('.'), value)
  return next
}

async function load($: EngineInterface): Promise<Loaded> {
  if (!(await $.fs.exists(CONFIG_PATH))) return { data: {}, exists: false }
  try {
    const parsed = JSON.parse(await $.fs.read(CONFIG_PATH))
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { data: {}, exists: true, error: 'root 가 JSON 객체가 아닙니다' }
    }
    return { data: parsed as Json, exists: true }
  } catch (err) {
    return { data: {}, exists: true, error: String(err) }
  }
}

export function flag(data: Json, path: string, fallback: boolean): boolean {
  const value = getPath(data, path)
  return typeof value === 'boolean' ? value : fallback
}

export function summary(data: Json): string {
  const on = (path: string, fallback: boolean) => (flag(data, path, fallback) ? '✓' : '✗')
  const engine = getPath(data, 'review.engine')
  const reviewer = flag(data, 'review.enabled', true) ? (typeof engine === 'string' ? engine : 'auto') : 'claude'
  return `review: ${reviewer} · plan${on('review.points.plan', true)} quality${on('review.points.quality', true)} · e2e${on('steps.e2e', true)}`
}

// 파싱할 수 없는 파일은 덮어쓰지 않는다. 사용자가 직접 고치게 둔다.
async function save($: EngineInterface, change: (data: Json) => Json): Promise<void> {
  const current = await load($)
  if (current.error) {
    $.ui.toast(`${CONFIG_PATH} 를 읽을 수 없어 저장하지 않았습니다: ${current.error}`)
    return
  }
  const data = change({ version: 1, ...current.data })
  await $.fs.write(CONFIG_PATH, JSON.stringify(data, null, 2) + '\n')
  $.ui.status(summary(data))
  await update($, rev, n => n + 1)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'harness-settings',
      description: 'harness 공통 설정(.claude/harness.config.json)을 pane 에서 켜고 끈다',
    })
    const current = await load($)
    if (current.exists && !current.error) $.ui.status(summary(current.data))
    return next(e)
  })

  on('command.run', { command: 'harness-settings' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Harness settings' })
    const current = await load($)
    return { text: current.error ? `설정 파일 오류: ${current.error}` : `pane 을 열었습니다. ${summary(current.data)}` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Select, Input } = $.ui.resolve(e)
    await read($, rev)
    const { data, error, exists } = await load($)
    if (error) {
      return (
        <Box flexDirection="column">
          <Text color="red">{CONFIG_PATH} 파싱 실패 — 직접 고친 뒤 다시 여세요.</Text>
          <Text dimColor>{error}</Text>
        </Box>
      )
    }
    const engine = getPath(data, 'review.engine')
    const model = getPath(data, 'review.gemini.model')
    const installed = new Set((await $.command.list()).map(command => command.name))
    const profiles = PROFILE_COMMANDS.filter(([command]) => installed.has(command))
    return (
      <Box flexDirection="column">
        <Text dimColor>{exists ? CONFIG_PATH : `${CONFIG_PATH} (없음 — 첫 변경 때 생성)`}</Text>
        {TOGGLES.map(([path, label, fallback]) => {
          const value = flag(data, path, fallback)
          return (
            <Box flexDirection="row">
              <Button key={path} label={`${value ? 'ON ' : 'OFF'}`} onPress={() => save($, d => setPath(d, path, !flag(d, path, fallback)))} />
              <Text> {label}</Text>
            </Box>
          )
        })}
        <Select
          key="review.engine"
          label="리뷰 엔진 (auto = codexMode 따름)"
          options={ENGINES.map(value => ({ value }))}
          value={typeof engine === 'string' ? engine : 'auto'}
          onSelect={value => save($, d => setPath(d, 'review.engine', value === 'auto' ? undefined : value))}
        />
        <Input
          key="review.gemini.model"
          label="Gemini 모델 (빈 값 = CLI 기본)"
          value={typeof model === 'string' ? model : ''}
          onSubmit={value => {
            const text = value.trim()
            if (!MODEL.test(text)) {
              $.ui.toast('모델명 형식 오류: 첫 글자는 영숫자, 나머지는 A-Z a-z 0-9 . _ : / - 만 허용')
              return
            }
            return save($, d => setPath(d, 'review.gemini.model', text === '' ? undefined : text))
          }}
        />
        <Text dimColor>리뷰 OFF = 건너뛰지 않고 Claude 패널이 리뷰합니다.</Text>
        {profiles.length > 0 ? <Text bold>프로필 (.claude/*-harness.local.md)</Text> : null}
        {profiles.map(([command, label]) => (
          <Button key={command} label={label} onPress={() => openProfile($, command)} />
        ))}
      </Box>
    )
  })
}
