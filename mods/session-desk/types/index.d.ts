export type Tab = 'history' | 'quick' | 'changes'

export type DiffKind = 'hunk' | 'add' | 'del' | 'ctx'
export type DiffLine = { kind: DiffKind; text: string }
export type DiffView = { lines: DiffLine[]; truncated: boolean }

// 選んだファイルの差分、または表示しない理由。path は選んだファイル。
export type ChangeView = {
  path: string
  change: { kind: 'note'; text: string } | { kind: 'diff'; view: DiffView }
} | null

declare module 'claude-code' {
  interface PluginState {
    'session-desk': {
      history: Shaped<string[]>
      quick: Shaped<string[]>
      changed: Shaped<string[]>
      viewed: ChangeView
      tab: Tab
      selected: number | null
    }
  }
}
