// profile.py resolve 결과 중 pane 이 쓰는 필드. 파일이 단일 출처이며 이 값은 표시용 사본이다.
export type Profile = {
  values: Record<string, unknown>
  sources: Record<string, string>
  writable: boolean
  path: string
}

export type ProfileView = { profile?: Profile; error?: string; busy?: boolean }

declare module 'claude-code' {
  interface PluginState {
    'fe-harness': { view: ProfileView }
  }
}
