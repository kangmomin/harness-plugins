// doctor 스킬 점검 항목 중 실행 없이 볼 수 있는 것만. 정밀 판정은 /minmos-harness:doctor 가 정본이다.
export type Check = { id: string; label: string; ok: boolean; hint: string }

declare module 'claude-code' {
  interface PluginState {
    'minmos-harness': { checks: readonly Check[] | null }
  }
}
