// 파일이 진짜 값이다. rev 는 저장 후 pane 을 다시 그리게 하는 카운터일 뿐이다.
export type Rev = number

declare module 'claude-code' {
  interface PluginState {
    'harness-settings': { rev: Rev }
  }
}
