export type Tab = 'history' | 'quick' | 'changes' | 'progress' | 'explain'

// SPEC 1 件と、それが指す計画の進捗。mtime は計画ファイルの更新時刻（ミリ秒）。
export type ProgressItem = {
  spec: string
  status: string | null
  plan: string | null
  planStatus: string | null
  done: number
  total: number
  mtime: number
}

// AskUserQuestion の質問 1 件のうち、解説に使う部分。
export type AskQuestion = {
  question: string
  header: string
  options?: { label: string; description?: string }[]
}

export type Explanation = {
  summary: string
  reason: string
  options: { label: string; effect: string }[]
  recommend: string
}

export type DiffKind = 'hunk' | 'add' | 'del' | 'ctx'
export type DiffLine = { kind: DiffKind; text: string }
export type DiffView = { lines: DiffLine[]; truncated: boolean }

// 選んだファイルの差分、または表示しない理由。path は選んだファイル。
export type ChangeView = {
  path: string
  change: { kind: 'note'; text: string } | { kind: 'diff'; view: DiffView }
} | null

// 解説の状態。none: まだ質問がない。limit: 1 セッションの呼び出しの上限に達した。
export type ExplainState = { phase: 'none' | 'loading' | 'ready' | 'failed' | 'limit'; data: Explanation | null }

declare module 'claude-code' {
  interface PluginState {
    'session-desk': {
      history: Shaped<string[]>
      quick: Shaped<string[]>
      changed: Shaped<string[]>
      progress: Shaped<ProgressItem[]>
      explanation: Shaped<ExplainState>
      viewed: ChangeView
      tab: Tab
      selected: number | null
    }
  }
}
