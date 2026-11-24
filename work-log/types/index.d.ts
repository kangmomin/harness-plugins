// wiki_status 응답 중 pane 이 쓰는 필드. 원본: mcp/server.js wiki_status().
export type WikiStatus = {
  needsInit?: boolean
  hint?: string
  scope?: string
  root?: string
  indexExists?: boolean
  indexAgeSeconds?: number | null
  indexState?: string
  counts?: Record<string, number> | null
  errors?: readonly unknown[]
}

// error 는 MCP 호출 실패(서버 미연결 등). status 와 함께 오지 않는다.
export type WikiView = { status?: WikiStatus; error?: string; busy?: boolean }

declare module 'claude-code' {
  interface PluginState {
    'work-log': { view: WikiView }
  }
}
