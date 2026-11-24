// doctor 스킬 점검 항목 중 실행 없이 볼 수 있는 것만. 정밀 판정은 /minmos-harness:doctor 가 정본이다.
// optional: 없어도 경고 수·toast 에 넣지 않는 항목.
export type Check = { id: string; label: string; ok: boolean; hint: string; optional?: boolean }

declare module 'claude-code' {
  interface PluginState {
    'minmos-harness': { checks: readonly Check[] | null }
  }
}
