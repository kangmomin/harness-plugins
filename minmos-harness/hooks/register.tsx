import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Check } from '../types'

const PANE = 'minmos-status'
const checks = atom({ plugin: 'minmos-harness', key: 'checks' } as const, null)

// 파일 경로는 세션 작업 디렉터리 기준. doctor SKILL.md "3. 프로젝트 파일" 과 같은 목록.
const FILES: ReadonlyArray<readonly [string, string, string]> = [
  ['secret/.env', 'secret/.env', 'e2e-test 에 필요'],
  ['.conventions.json', '.conventions.json', 'convention-check 에 필요'],
  ['migrations', 'infra/flyway/migrations', 'db-gen-committed 에 필요'],
]
const MCP: ReadonlyArray<readonly [string, RegExp, string]> = [
  ['Apidog MCP', /^mcp__.*apidog.*__/i, 'apidog-schema-gen·e2e-test 에 필요'],
  ['PostgreSQL MCP', /^mcp__.*postgres.*__/i, 'e2e-test DB 확인에 필요'],
]

export function summary(list: readonly Check[]): string {
  // 선택 항목(Apidog Push 용 env)은 세지 않는다. doctor 도 선택으로 분류한다.
  const bad = list.filter(check => !check.ok && !check.optional).length
  return bad === 0 ? 'minmos: ✓' : `minmos: ⚠${bad}`
}

// 가벼운 점검만 한다. DB 쿼리·빌드·네트워크 호출은 하지 않는다.
export async function inspect($: EngineInterface): Promise<Check[]> {
  const list: Check[] = []
  // env 이름은 리터럴이어야 validate 가 읽는다. 값은 읽기만 하고 표시하지 않는다.
  const token = await $.env.get('APIDOG_ACCESS_TOKEN')
  const project = await $.env.get('APIDOG_PROJECT_ID')
  list.push({ id: 'env.token', label: 'APIDOG_ACCESS_TOKEN', ok: Boolean(token), hint: '선택: Apidog Push 에만 필요', optional: true })
  list.push({ id: 'env.project', label: 'APIDOG_PROJECT_ID', ok: Boolean(project), hint: '선택: Apidog Push 에만 필요', optional: true })
  for (const [id, path, hint] of FILES) {
    list.push({ id: `file.${id}`, label: path, ok: await $.fs.exists(path), hint })
  }
  const tools = (await $.tool.list()).map(tool => tool.name)
  for (const [label, pattern, hint] of MCP) {
    list.push({ id: `mcp.${label}`, label, ok: tools.some(name => pattern.test(name)), hint: `${hint} (서버 연결 전이면 잠시 뒤 다시 확인)` })
  }
  return list
}

async function refresh($: EngineInterface): Promise<readonly Check[]> {
  let list: Check[]
  try {
    list = await inspect($)
  } catch (err) {
    // 점검 실패는 표시만 한다. 명령·버튼이 실패로 끝나지 않게 한다.
    list = [{ id: 'inspect', label: '점검 실패', ok: false, hint: err instanceof Error ? err.message : String(err) }]
  }
  await update($, checks, () => list)
  $.ui.status(summary(list))
  return list
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: PANE, description: 'minmos-harness 의존성(env·파일·MCP) 상태를 pane 으로 연다' })
    // MCP 서버가 붙을 시간을 둔다. 첫 프롬프트를 막지 않는다.
    $.clock.after(8000, () => {
      void refresh($).then(list => {
        const bad = list.filter(check => !check.ok && !check.optional)
        if (bad.length > 0) {
          $.ui.toast(`minmos-harness: ${bad.map(check => check.label).join(', ')} 없음. /${PANE} 또는 /minmos-harness:doctor`)
        }
      }).catch(() => undefined)
    })
    return next(e)
  })

  on('command.run', { command: PANE }, async $ => {
    await $.ui.open({ id: PANE, title: 'minmos-harness' })
    return { text: summary(await refresh($)), isTextDisplayOnly: true }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, checks)
    if (!list) return <Text dimColor>점검 중…</Text>
    return (
      <Box flexDirection="column">
        {list.map(check => (
          <Box key={check.id} flexDirection="row">
            <Text color={check.ok ? 'success' : check.optional ? undefined : 'warning'} dimColor={!check.ok && check.optional}>{check.ok ? 'OK  ' : check.optional ? '선택' : 'WARN'}</Text>
            <Text wrap="truncate"> {check.label}{check.ok ? '' : ` — ${check.hint}`}</Text>
          </Box>
        ))}
        <Button key="refresh" label="다시 점검" onPress={() => refresh($)} />
        <Text dimColor>정밀 진단(DB 쿼리·빌드·Codex)은 /minmos-harness:doctor</Text>
      </Box>
    )
  })
}
