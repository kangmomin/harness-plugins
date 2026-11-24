import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { WikiStatus } from '../types'

// common mod 과 같은 이름·문장. 둘 다 설치돼도 한 번만 들어간다.
export const LANGUAGE_BLOCK = {
  name: 'harnessLanguage',
  text: 'Always talk in ASD-STE100 Simplified Technical Korean.\nAlways talk to me like I have ADHD.',
}

const PANE = 'work-log-status'
// .mcp.json 의 서버 키 "work-log" 를 도구 이름 표기로 쓴 것.
const SERVER = 'plugin_work-log_work-log'
export const STALE_SECONDS = 24 * 60 * 60

const view = atom({ plugin: 'work-log', key: 'view' } as const, {})

export function parseStatus(text: string): WikiStatus {
  const data = JSON.parse(text)
  if (!data || typeof data !== 'object') throw new Error('wiki_status 응답이 객체가 아닙니다')
  return data as WikiStatus
}

export function age(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number') return '없음'
  if (seconds < 3600) return `${Math.round(seconds / 60)}분 전`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}시간 전`
  return `${Math.round(seconds / 86400)}일 전`
}

async function call($: EngineInterface, tool: 'wiki_status' | 'wiki_sync'): Promise<string> {
  const result = await $.mcp.call(SERVER, tool)
  const text = result.content.map(block => block.text ?? '').join('')
  if (result.isError) throw new Error(text || `${tool} 실패`)
  return text
}

async function load($: EngineInterface): Promise<WikiStatus | undefined> {
  try {
    const status = parseStatus(await call($, 'wiki_status'))
    await update($, view, () => ({ status }))
    return status
  } catch (err) {
    await update($, view, () => ({ error: String(err) }))
    return undefined
  }
}

async function sync($: EngineInterface): Promise<void> {
  await update($, view, current => ({ ...current, busy: true }))
  try {
    await call($, 'wiki_sync')
    $.ui.toast('work-log 인덱스를 갱신했습니다.')
  } catch (err) {
    $.ui.toast(`wiki_sync 실패: ${String(err)}`)
  }
  await load($)
}

export const register: Register = on => {
  on('prompt.context', async ($, e, next) => {
    const result = await next(e)
    if (result.blocks.some(block => block.name === LANGUAGE_BLOCK.name)) return result
    return { ...result, blocks: [...result.blocks, LANGUAGE_BLOCK] }
  })

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: PANE, description: 'work-log 인덱스 상태를 pane 으로 열고 동기화한다' })
    // MCP 서버 기동을 첫 프롬프트 앞에서 기다리지 않는다.
    $.clock.after(5000, () => {
      void load($).then(status => {
        if (status && !status.needsInit && (status.indexAgeSeconds ?? 0) > STALE_SECONDS) {
          $.ui.toast(`work-log 인덱스가 ${age(status.indexAgeSeconds)} 것입니다. /${PANE} 에서 동기화하세요.`)
        }
      })
    })
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'work-log' })
    const status = await load($)
    return { text: status ? `pane 을 열었습니다. 인덱스: ${age(status.indexAgeSeconds)}` : 'work-log MCP 서버에 연결하지 못했습니다.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const { status, error, busy } = await read($, view)
    if (error) {
      return (
        <Box flexDirection="column">
          <Text color="error">work-log MCP 호출 실패</Text>
          <Text dimColor>{error}</Text>
          <Text dimColor>/work-log:doctor 로 진단하세요.</Text>
        </Box>
      )
    }
    if (!status) return <Text dimColor>불러오는 중…</Text>
    if (status.needsInit) {
      return (
        <Box flexDirection="column">
          <Text color="warning">스코프가 설정되지 않았습니다. /work-log:init 을 실행하세요.</Text>
          {status.hint ? <Text dimColor>{status.hint}</Text> : null}
        </Box>
      )
    }
    const counts = Object.entries(status.counts ?? {}).map(([k, v]) => `${k} ${v}`).join(' · ')
    const stale = (status.indexAgeSeconds ?? 0) > STALE_SECONDS || !status.indexExists
    return (
      <Box flexDirection="column">
        <Text wrap="truncate">scope: {status.scope ?? '-'}</Text>
        <Text dimColor wrap="truncate">{status.root ?? ''}</Text>
        <Text color={stale ? 'warning' : undefined}>
          인덱스: {status.indexExists ? age(status.indexAgeSeconds) : '없음'} ({status.indexState ?? '-'})
        </Text>
        {counts ? <Text dimColor>{counts}</Text> : null}
        {(status.errors?.length ?? 0) > 0 ? <Text color="error">인덱스 오류 {status.errors?.length}건</Text> : null}
        <Button key="sync" label={busy ? '동기화 중…' : '동기화 (wiki_sync)'} onPress={() => (busy ? undefined : sync($))} />
      </Box>
    )
  })
}
