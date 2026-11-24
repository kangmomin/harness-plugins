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

// 상태 파일을 바꾸지 않는 도구. 이 호출 뒤에는 다시 읽지 않는다.
const READ_ONLY_TOOLS = new Set(['Read', 'Grep', 'Glob', 'LS', 'WebFetch', 'WebSearch', 'ToolSearch'])

// workflow_run.py create/resume 출력(JSON 1개)에서 실행 정보를 꺼낸다. 다른 출력이면 null.
export function parseRun(command: string, output: string): Run | null {
  if (!/workflow_run\.py/.test(command) || !/\b(create|resume)\b/.test(command)) return null
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

  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    try {
      if (e.tool === 'Bash' && 'text' in result && typeof result.text === 'string' && !result.isError) {
        const found = parseRun(String(e.command ?? ''), result.text)
        if (found) {
          await update($, run, () => found)
          await update($, progress, () => null)
        }
      }
      if (!READ_ONLY_TOOLS.has(String(e.tool))) await refresh($)
    } catch {
      // 표시는 부가 기능이다. 실패해도 도구 결과는 그대로 돌려준다.
    }
    return result
  }).catch(($, e, next) => next(e)) // 감시만 한다. 실패해도 호출을 막지 않는다(next 는 replay-safe).

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
