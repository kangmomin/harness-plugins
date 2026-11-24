import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PhaseRow, Progress, Run } from '../types'

// work-log mod 도 같은 이름·문장을 쓴다. 이름이 같으면 먼저 넣은 쪽만 남는다(중복 주입 방지).
export const LANGUAGE_BLOCK = {
  name: 'harnessLanguage',
  text: 'Always talk in ASD-STE100 Simplified Technical Korean.\nAlways talk to me like I have ADHD.',
}

const PANE = 'harness-progress'
const run = atom({ plugin: 'common', key: 'run' } as const, null)
const progress = atom({ plugin: 'common', key: 'progress' } as const, null)

// tool_use id → workflow_run.py 명령. 결과 행이 올 때까지 기다린다.
const pending = atom({ plugin: 'common', key: 'pending' } as const, {})

type Block = { readonly type: string; readonly [field: string]: unknown }

const isRunCommand = (command: string) => /workflow_run\.py/.test(command) && /\b(create|resume)\b/.test(command)

// workflow_run.py create/resume 출력(JSON 1개)에서 실행 정보를 꺼낸다. 다른 출력이면 null.
export function parseRun(command: string, output: string): Run | null {
  if (!isRunCommand(command)) return null
  const start = output.indexOf('{')
  const end = output.lastIndexOf('}')
  if (start < 0 || end <= start) return null
  try {
    const data = JSON.parse(output.slice(start, end + 1))
    if (typeof data?.STATE_FILE !== 'string') return null
    return { stateFile: data.STATE_FILE, mode: String(data.MODE ?? ''), runId: String(data.RUN_ID ?? '') }
  } catch {
    return null
  }
}

// assistant 행에서 workflow_run.py create/resume 를 부르는 Bash 호출을 찾는다.
export function runCalls(content: readonly Block[]): Record<string, string> {
  const found: Record<string, string> = {}
  for (const block of content) {
    if (block.type !== 'tool_use' || block.name !== 'Bash') continue
    const command = (block.input as { command?: unknown } | undefined)?.command
    if (typeof block.id === 'string' && typeof command === 'string' && isRunCommand(command)) {
      found[block.id] = command
    }
  }
  return found
}

export function resultText(block: Block): string {
  const content = block.content
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content.map(part => (part && typeof part === 'object' && typeof part.text === 'string' ? part.text : '')).join('')
}

function section(text: string, title: string): string[] {
  const lines = text.split(/\r?\n/)
  const start = lines.findIndex(line => line.trim() === `## ${title}`)
  if (start < 0) return []
  const body: string[] = []
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith('## ')) break
    body.push(line)
  }
  return body
}

// 템플릿: be/fe-harness skills/start-workflow/references/templates.md 의 Current Phase·Phase Assignments.
export function parseState(text: string): Omit<Progress, 'seen'> {
  const current = section(text, 'Current Phase').find(line => line.trim() !== '')?.trim() ?? ''
  const rows: PhaseRow[] = []
  for (const line of section(text, 'Phase Assignments')) {
    const cells = line.split('|').slice(1, -1).map(cell => cell.trim())
    if (cells.length < 5 || cells[0] === 'Phase' || /^-+$/.test(cells[0] ?? '')) continue
    rows.push({ phase: cells[0] ?? '', agent: cells[1] ?? '', status: cells[cells.length - 1] ?? '' })
  }
  return { current, rows }
}

// 표가 있고 모든 행이 끝났으면 실행이 끝난 것이다.
export function isFinished(rows: readonly PhaseRow[]): boolean {
  return rows.length > 0 && rows.every(row => !/PENDING|IN_PROGRESS/.test(row.status))
}

export function label(mode: string, current: string): string {
  const phase = current.replace(/\s*\(.*\)\s*$/, '')
  return `${mode ? mode.toUpperCase() : 'WF'} · ${phase || '준비 중'}`
}

async function refresh($: EngineInterface): Promise<void> {
  const active = await read($, run)
  if (!active) return
  const previous = await read($, progress)
  if (!(await $.fs.exists(active.stateFile))) {
    // 상태 본문은 Plan 승인 뒤에 생긴다. 한 번 읽은 파일이 사라졌으면 아카이브된 것이다.
    if (previous?.seen) await finish($)
    return
  }
  const parsed = parseState(await $.fs.read(active.stateFile))
  if (isFinished(parsed.rows)) {
    await finish($)
    return
  }
  await update($, progress, () => ({ ...parsed, seen: true }))
  const short = parsed.current.match(/Phase\s+([\w.]+)/)?.[1]
  $.ui.status(`wf: ${active.mode.toUpperCase() || 'WF'}${short ? ` P${short}` : ''}`)
}

async function observe($: EngineInterface, content: readonly Block[]): Promise<void> {
  const calls = runCalls(content)
  if (Object.keys(calls).length > 0) await update($, pending, current => ({ ...current, ...calls }))
  const results = content.filter(block => block.type === 'tool_result')
  if (results.length === 0) return
  const waiting = await read($, pending)
  for (const block of results) {
    const id = String(block.tool_use_id ?? '')
    const command = waiting[id]
    if (command === undefined) continue
    await update($, pending, current => Object.fromEntries(Object.entries(current).filter(([key]) => key !== id)))
    const found = block.is_error ? null : parseRun(command, resultText(block))
    if (found) {
      await update($, run, () => found)
      await update($, progress, () => null)
    }
  }
  await refresh($)
}

async function finish($: EngineInterface): Promise<void> {
  await update($, run, () => null)
  await update($, progress, () => null)
  $.ui.status(undefined)
}

export const register: Register = on => {
  on('prompt.context', async ($, e, next) => {
    const result = await next(e)
    if (result.blocks.some(block => block.name === LANGUAGE_BLOCK.name)) return result
    return { ...result, blocks: [...result.blocks, LANGUAGE_BLOCK] }
  })

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: PANE,
      description: '진행 중인 start-workflow 의 Phase 표를 pane 으로 연다',
    })
    return next(e)
  })

  // tool.call 을 hook 하면 그 도구의 백그라운드 전환·실시간 출력이 꺼진다. 그래서 저장되는 행만 읽는다.
  on('session.append', async ($, e, next) => {
    const stored = await next(e)
    try {
      await observe($, e.message.content as readonly Block[])
    } catch {
      // 표시는 부가 기능이다. 실패해도 행 저장에는 영향이 없다.
    }
    return stored
  }).catch(($, e, next) => next(e))

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'Workflow progress' })
    const active = await read($, run)
    return { text: active ? `pane 을 열었습니다. ${active.stateFile}` : '진행 중인 워크플로우가 없습니다.' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const active = await read($, run)
    if (e.props.hasSurvey || !active) return next(e)
    const current = (await read($, progress))?.current ?? ''
    const { Text } = $.ui.resolve(e)
    return <Text dimColor wrap="truncate">▶ {label(active.mode, current)}</Text>
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const active = await read($, run)
    const state = await read($, progress)
    if (!active) return <Text dimColor>진행 중인 워크플로우가 없습니다.</Text>
    return (
      <Box flexDirection="column">
        <Text bold>{label(active.mode, state?.current ?? '')}</Text>
        <Text dimColor wrap="truncate">{active.stateFile}</Text>
        {(state?.rows ?? []).map(row => (
          <Text color={row.status === 'IN_PROGRESS' ? 'warning' : row.status === 'DONE' ? 'success' : undefined} dimColor={row.status === 'PENDING'} wrap="truncate">
            {row.status === 'DONE' ? '✓' : row.status === 'IN_PROGRESS' ? '▶' : '·'} {row.phase.padEnd(4)} {row.agent}
          </Text>
        ))}
      </Box>
    )
  })
}
