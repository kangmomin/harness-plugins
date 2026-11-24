import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Profile } from '../types'

// be-harness/hooks/register.tsx 와 이 블록·view atom 의 plugin 이름만 다르다. 나머지는 같게 유지한다.
const PLUGIN = 'fe-harness'
const DOMAIN = 'fe'
type Field = { key: string; label: string; kind: 'enum'; options: readonly string[] } | { key: string; label: string; kind: 'bool' | 'string' }
export const FIELDS: readonly Field[] = [
  { key: 'codexMode', label: 'Codex 모드', kind: 'enum', options: ['none', 'mix', 'max'] },
  { key: 'language', label: '대화 언어', kind: 'enum', options: ['ko', 'en'] },
  { key: 'e2eRunner', label: 'E2E runner', kind: 'enum', options: ['playwright', 'cypress', 'none'] },
  { key: 'serverUrl', label: '서버 URL', kind: 'string' },
]
// ---

const PANE = `${PLUGIN}-profile`
const view = atom({ plugin: 'fe-harness', key: 'view' } as const, {})

// 편집 정본: skills/config/assets/profile.py (config 스킬과 같은 preview → apply 경로).
async function helper($: EngineInterface, args: readonly string[], stdin?: string): Promise<any> {
  const script = `${$.plugin.root}/skills/config/assets/profile.py`
  let last = ''
  for (const python of ['python3', 'python']) {
    let out
    try {
      out = await $.process.run([python, '-I', '-B', script, ...args, '--domain', DOMAIN, '--cwd', '.'], { stdin, timeoutMs: 20000 })
    } catch (err) {
      last = String(err) // 실행 파일이 없으면 다음 후보로 넘어간다.
      continue
    }
    if (out.exitCode === 0) return JSON.parse(out.stdout)
    const blocked = out.stderr.match(/\{.*"status":\s*"BLOCKED".*\}/)
    if (blocked) throw new Error(JSON.parse(blocked[0]).error)
    // fcntl 은 POSIX 전용이다. Windows 기본 Python 에서는 helper 가 동작하지 않는다.
    if (/fcntl/.test(out.stderr)) throw new Error('profile.py 는 POSIX(macOS·Linux·WSL) Python 이 필요합니다')
    throw new Error(out.stderr.trim().split('\n').pop() || `exit ${out.exitCode}`)
  }
  throw new Error(`python 을 실행하지 못했습니다: ${last}`)
}

async function load($: EngineInterface): Promise<void> {
  try {
    const result = await helper($, ['resolve'])
    const profile: Profile = { values: result.values ?? {}, sources: result.sources ?? {}, writable: Boolean(result.writable), path: String(result.profile_path ?? '') }
    await update($, view, () => ({ profile }))
  } catch (err) {
    await update($, view, () => ({ error: String(err instanceof Error ? err.message : err) }))
  }
}

export async function save($: EngineInterface, key: string, value: unknown): Promise<void> {
  const changes = JSON.stringify({ [key]: value })
  await update($, view, current => ({ ...current, busy: true }))
  try {
    const preview = await helper($, ['edit'], changes)
    if (preview.status !== 'PREVIEW') throw new Error(`예상하지 못한 응답: ${preview.status}`)
    if (preview.changed) {
      await helper($, ['edit', '--apply', '--expected-sha256', String(preview.sha256_before)], changes)
      $.ui.toast(`${key} = ${JSON.stringify(value)} 저장. 진행 중인 워크플로우는 다음 실행부터 적용됩니다.`)
    }
  } catch (err) {
    $.ui.toast(`${key} 저장 실패: ${err instanceof Error ? err.message : String(err)}`)
  }
  await load($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: PANE, description: `${PLUGIN} profile(.claude/${DOMAIN}-harness.local.md) 주요 값을 pane 에서 바꾼다` })
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: `${PLUGIN} profile` })
    await load($)
    const { profile, error } = await read($, view)
    return { text: error ? `profile 읽기 실패: ${error}` : `pane 을 열었습니다. ${profile?.path ?? ''}` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Select, Input } = $.ui.resolve(e)
    const { profile, error, busy } = await read($, view)
    if (error) {
      return (
        <Box flexDirection="column">
          <Text color="error">profile 을 읽지 못했습니다.</Text>
          <Text dimColor>{error}</Text>
        </Box>
      )
    }
    if (!profile) return <Text dimColor>불러오는 중…</Text>
    if (!profile.writable) {
      // 파일 생성은 init 담당이다. 이 pane 은 기존 파일의 키만 바꾼다.
      return <Text color="warning">편집할 profile 이 없습니다. /{PLUGIN}:init 을 먼저 실행하세요.</Text>
    }
    return (
      <Box flexDirection="column">
        <Text dimColor wrap="truncate">{profile.path}{busy ? ' (저장 중…)' : ''}</Text>
        {FIELDS.map(field => {
          const value = profile.values[field.key]
          if (field.kind === 'enum') {
            return (
              <Select key={field.key} label={field.label} options={field.options.map(option => ({ value: option }))}
                value={typeof value === 'string' ? value : field.options[0] ?? ''} onSelect={picked => save($, field.key, picked)} />
            )
          }
          if (field.kind === 'bool') {
            const enabled = value !== false
            return (
              <Box key={field.key} flexDirection="row">
                <Button key={field.key} label={enabled ? 'ON ' : 'OFF'} onPress={() => save($, field.key, !enabled)} />
                <Text> {field.label}</Text>
              </Box>
            )
          }
          return (
            <Input key={field.key} label={field.label} value={typeof value === 'string' ? value : ''}
              onSubmit={text => save($, field.key, text.trim())} />
          )
        })}
        <Text dimColor>다른 키: /{PLUGIN}:config</Text>
      </Box>
    )
  })
}
