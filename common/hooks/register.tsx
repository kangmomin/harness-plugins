import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PhaseRow, Progress, Run } from '../types'
import { flushOnEnd, registerMetrics, registerMetricsCommands } from './metrics'

// work-log mod 도 같은 이름·문장을 쓴다. 이름이 같으면 먼저 넣은 쪽만 남는다(중복 주입 방지).
export const LANGUAGE_BLOCK = {
  name: 'harnessLanguage',
  text: 'Always talk in ASD-STE100 Simplified Technical Korean.\nAlways talk to me like I have ADHD.',
}

// Why: 에이전트는 스킬의 틀린 지시를 우회하고 끝낸다. 기록이 없으면 스킬이 고쳐지지 않는다.
// mod 가 없는 호스트에서는 기록만 없다. 스킬 절차는 같다 (papercut.py 가 정본, 로컬 전용).
export const papercutBlock = (root: string) => ({
  name: 'harnessPapercut',
  text: [
    'While running a harness skill (common, be-harness, fe-harness, minmos-harness, hyeondongs-harness, work-log): if a skill instruction was wrong, a skill command ended differently than the skill says, or you needed a workaround, record it once after the task. Do not ask the user. Do not include secrets.',
    `echo '{"plugin":"","skill":"","goal":"","command":"","expected":"","actual":"","workaround":"","proposal":""}' | python3 -I -B "${root.split('\\').join('/')}/hooks/papercut.py" record --cwd .`,
    'Fill every field you know (plugin, skill, goal, actual are required). Use `python` if `python3` is missing.',
  ].join('\n'),
})

const PANE = 'harness-progress'
// metrics.tsx 도 같은 ref 로 읽는다 (scan 규칙상 atom 은 파일마다 리터럴로 선언한다).
const run = atom({ plugin: 'common', key: 'run' } as const, null)
const progress = atom({ plugin: 'common', key: 'progress' } as const, null)

// tool_use id → workflow_run.py 명령. 결과 행이 올 때까지 기다린다.
const pending = atom({ plugin: 'common', key: 'pending' } as const, {})

type Block = { readonly type: string; readonly [field: string]: unknown }

// `workflow_run.py create` 처럼 스크립트 바로 뒤의 하위 명령만 인정한다 (`--resume` 같은 플래그는 제외).
const isRunCommand = (command: string) => /workflow_run\.py["']?\s+(create|resume)\b/.test(command)

// workflow_run.py run_paths() 가 만드는 절대 경로만 받는다. 다른 파일을 읽지 않게 한다.
const isStateFile = (path: string) => /^(\/|[A-Za-z]:[\\/]|\\\\[^\\/?.])/.test(path) && /[\\/]workflow-state\.md$/.test(path)

// workflow_run.py create/resume 출력(JSON 1개)에서 실행 정보를 꺼낸다. 다른 출력이면 null.
export function parseRun(command: string, output: string): Run | null {
  if (!isRunCommand(command)) return null
  const start = output.indexOf('{')
  const end = output.lastIndexOf('}')
  if (start < 0 || end <= start) return null
  try {
    const data = JSON.parse(output.slice(start, end + 1))
    if (typeof data?.STATE_FILE !== 'string' || !isStateFile(data.STATE_FILE)) return null
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

// 템플릿: be/fe-harness skills/start-workflow/references/templates.md 의 Current Phase·Phase Assignments·Remaining Phases.
export function parseState(text: string): Omit<Progress, 'seen'> & { done: boolean } {
  const current = section(text, 'Current Phase').find(line => line.trim() !== '')?.trim() ?? ''
  const rows: PhaseRow[] = []
  for (const line of section(text, 'Phase Assignments')) {
    const cells = line.split('|').slice(1, -1).map(cell => cell.trim())
    if (cells.length < 5 || cells[0] === 'Phase' || /^-+$/.test(cells[0] ?? '')) continue
    rows.push({ phase: cells[0] ?? '', agent: cells[1] ?? '', status: cells[cells.length - 1] ?? '' })
  }
  // workflow_run.py resume 과 같은 완료 규칙: Remaining Phases 가 `없음`. Analyze/Verify 처럼 표가 없는 모드도 덮는다.
  const remaining = section(text, 'Remaining Phases').map(line => line.trim()).filter(Boolean).join('\n')
  return { current, rows, done: remaining === '없음' || remaining === '- 없음' }
}

// 완료 규칙이 쓰이지 않은 상태 파일을 위한 보조 규칙: 표가 있고 모든 행이 끝났다.
export function isFinished(rows: readonly PhaseRow[]): boolean {
  return rows.length > 0 && rows.every(row => !/^(PENDING|IN_PROGRESS)\b/.test(row.status))
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
  const { done, ...parsed } = parseState(await $.fs.read(active.stateFile))
  if (done || isFinished(parsed.rows)) {
    await finish($)
    return
  }
  // 같은 내용이면 쓰지 않는다. 쓰면 band·pane 이 다시 그려진다.
  if (previous?.seen && JSON.stringify({ current: previous.current, rows: previous.rows }) === JSON.stringify(parsed)) return
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
      $.ui.status(undefined) // 이전 실행의 status 를 남기지 않는다.
    }
  }
  await refresh($)
}

async function finish($: EngineInterface): Promise<void> {
  await update($, run, () => null)
  await update($, progress, () => null)
  await update($, pending, () => ({}))
  $.ui.status(undefined)
}

export const register: Register = on => {
  registerMetrics(on)

  on('prompt.context', async ($, e, next) => {
    const result = await next(e)
    const papercut = papercutBlock($.plugin.root)
    const missing = [LANGUAGE_BLOCK, papercut].filter(added => !result.blocks.some(block => block.name === added.name))
    return missing.length ? { ...result, blocks: [...result.blocks, ...missing] } : result
  })

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: PANE,
      description: '진행 중인 start-workflow 의 Phase 표를 pane 으로 연다',
    })
    await registerMetricsCommands($)
    return next(e)
  })

  // tool.call 을 hook 하면 그 도구의 백그라운드 전환·실시간 출력이 꺼진다. 그래서 저장되는 행만 읽는다.
  // main 대화의 모델 응답·도구 결과 행만 본다. subagent 의 시험 실행이 진행 중인 실행을 덮지 않게 한다.
  on('session.append', { door: ['response', 'tool-result'] }, async ($, e, next) => {
    const stored = await next(e)
    if (e.agentId) return stored
    try {
      await observe($, e.message.content as readonly Block[])
    } catch {
      // 표시는 부가 기능이다. 실패해도 행 저장에는 영향이 없다.
    }
    return stored
  }).catch(($, e, next) => next(e))

  // /clear 는 새 대화다. 이전 대화의 실행을 표시하지 않는다.
  on('session.end', async ($, e, next) => {
    // workflow 요약을 붙이려고 finish 보다 먼저 기록한다.
    await flushOnEnd($)
    if (e.reason === 'clear') await finish($)
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'Workflow progress' })
    const active = await read($, run)
    return { text: active ? `pane 을 열었습니다. ${active.stateFile}` : '진행 중인 워크플로우가 없습니다.', isTextDisplayOnly: true }
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
