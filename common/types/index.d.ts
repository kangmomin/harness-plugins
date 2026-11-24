// 진행 중인 start-workflow 실행. workflow_run.py create/resume 의 JSON 출력에서 얻는다.
export type Run = { stateFile: string; mode: string; runId: string }

export type PhaseRow = { phase: string; agent: string; status: string }

// 상태 파일(workflow-state.md)에서 읽은 값. 파일이 단일 출처이며 이 값은 표시용 사본이다.
export type Progress = {
  current: string
  rows: readonly PhaseRow[]
  // 한 번이라도 파일을 읽었는가. 읽은 뒤 파일이 사라지면 아카이브로 보고 표시를 끝낸다.
  seen: boolean
}

declare module 'claude-code' {
  interface PluginState {
    common: { run: Run | null; progress: Progress | null; pending: Record<string, string> }
  }
}
