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

export type Tokens = { input: number; output: number; cacheRead: number; cacheWrite: number }

// git commit 출력의 `[branch abc1234] 제목` 줄에서 읽은 커밋. helper 가 전체 sha·변경 줄 수를 붙인다.
export type SeenCommit = { short: string; branch: string; amend: boolean }

// 마지막 기록 이후 세션 구간의 누적값. 커밋이 끝난 main turn 이 끝나면 metrics.py record 로 넘기고 비운다.
export type Segment = {
  startedAt: number
  costAt: number | null
  tokens: { main: Tokens; sub: Tokens }
  models: Readonly<Record<string, number>>
  activeMs: number
  turns: number
  prompts: number
  chars: number
  commands: number
  followUps: number
  aborted: number
  denied: number
  reviewAgents: number
  reviewSkills: number
  codex: number
  commits: readonly SeenCommit[]
  // tool_use id → git commit 명령. 결과 행이 올 때까지 기다린다.
  waiting: Readonly<Record<string, string>>
}

export type MetricsGroup = {
  label: string
  commits: number
  avgTokens: number
  avgCostUsd: number
  avgActiveMin: number
  avgPrompts: number
  avgFollowUps: number
  avgAborted: number
  avgDenied: number
  avgReviews: number
  tokensPerLine: number | null
}

export type MetricsRecent = { ts: number; short: string; subject: string | null; label: string; tokens: number; shared: number }

export type MetricsSummary = {
  dir: string
  label: string | null
  groups: readonly MetricsGroup[]
  recent: readonly MetricsRecent[]
  uncommitted: number
}

export type MetricsView = { summary?: MetricsSummary; error?: string; lastRecord?: string }

declare module 'claude-code' {
  interface PluginState {
    common: {
      run: Run | null
      progress: Progress | null
      pending: Record<string, string>
      segment: Segment | null
      metricsView: MetricsView
    }
  }
}
