import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { AskQuestion, ChangeView, ExplainState, ProgressItem, Tab } from '../types'
import {
  DEFAULT_QUICK,
  addQuick,
  allAdded,
  buildExplainPrompt,
  countChecks,
  insideCwd,
  isSecretName,
  parseDiff,
  parseExplanation,
  parseFrontmatter,
  parseQuick,
  pickCurrent,
  preview,
  progressBar,
  removeQuick,
  slashes,
  stripControl,
} from './lib'

const PANE = 'session-desk'
const STORE_KEY = 'quick'
const MAX_BYTES = 1_000_000
const MAX_DIFF_LINES = 500
const MAX_SPECS = 30
const MAX_CALLS = 30
const SPECS_DIR = 'docs/grill-form/specs'
const EDIT_TOOLS = ['Edit', 'Write', 'NotebookEdit']

// 状態は、このモジュールの atom に持つ。形を変えるときは、shape のタグを変える。
const SHAPE = { shape: 'desk-1' } as const
const history = atom({ plugin: 'session-desk', key: 'history' } as const, [], SHAPE)
const quick = atom({ plugin: 'session-desk', key: 'quick' } as const, [...DEFAULT_QUICK], SHAPE)
const changed = atom({ plugin: 'session-desk', key: 'changed' } as const, [], SHAPE)
const progress = atom({ plugin: 'session-desk', key: 'progress' } as const, [], SHAPE)
const explanation = atom({ plugin: 'session-desk', key: 'explanation' } as const, { phase: 'none', data: null } as ExplainState, SHAPE)
const tab = atom({ plugin: 'session-desk', key: 'tab' } as const, 'history' as Tab)
const selected = atom({ plugin: 'session-desk', key: 'selected' } as const, null as number | null)
const viewed = atom({ plugin: 'session-desk', key: 'viewed' } as const, null as ChangeView)

const TABS: readonly { id: Tab; label: string }[] = [
  { id: 'history', label: '履歴' },
  { id: 'explain', label: '解説' },
  { id: 'quick', label: '定型文' },
  { id: 'changes', label: '変更' },
  { id: 'progress', label: '進捗' },
]

type Change = NonNullable<ChangeView>['change']

// 定型文を変えたら、atom（画面）とストア（次のセッション）の両方に書く。`$` を受け取る関数は、トップレベルに置く。
async function saveQuick($: any, next: string[]) {
  await update($, quick, () => next)
  await $.store.set(STORE_KEY, next)
}

// 変更したファイルの差分を、出してよいかを順に判定して作る。秘密・外・大きい・UTF-8 でないものは、git にも渡さない。
async function describeChange($: any, path: string, cwd: string): Promise<Change> {
  const secret: Change = { kind: 'note', text: '秘密の可能性があるファイル名のため、内容を表示しない' }
  if (isSecretName(path)) {
    return secret
  }
  const stat = await $.fs.stat(path, { resolve: true }).catch(() => undefined)
  if (!stat) {
    return { kind: 'note', text: '存在しない' }
  }
  const real: string | undefined = stat.realPath
  if (real === undefined) {
    return { kind: 'note', text: '実パスを解決できないため、表示不可' }
  }
  if (isSecretName(real)) {
    return secret
  }
  if (!insideCwd(real, cwd)) {
    return { kind: 'note', text: '作業ディレクトリの外のため、内容を表示しない' }
  }
  if (stat.size > MAX_BYTES) {
    return { kind: 'note', text: '1MB を超えるため、表示不可' }
  }
  let diff
  try {
    // 外部の diff コマンドと textconv は、リポジトリの設定で任意のコマンドが動くため、使わない。
    // core.fsmonitor もリポジトリの設定でコマンドを動かせるので、切る。
    diff = await $.process.run(
      ['git', '-c', 'core.fsmonitor=false', 'diff', '--no-ext-diff', '--no-textconv', '-U3', 'HEAD', '--', real],
      { cwd, timeoutMs: 10000 },
    )
  } catch {
    return { kind: 'note', text: 'git を実行できないため、差分を出せない' }
  }
  if (diff.exitCode !== 0) {
    const isRepo = !/not a git repository/i.test(String(diff.stderr))

    return { kind: 'note', text: isRepo ? 'git diff が失敗したため、差分を出せない' : 'Git のリポジトリではないため、差分を出せない' }
  }
  let text: string = diff.stdout
  let isNew = false
  if (text.trim() === '') {
    try {
      const tracked = await $.process.run(['git', 'ls-files', '--error-unmatch', '--', real], { cwd, timeoutMs: 10000 })
      if (tracked.exitCode === 0) {
        return { kind: 'note', text: '変更なし' }
      }
      isNew = true
      text = await $.fs.read(real)
    } catch {
      return { kind: 'note', text: '読み取れないため、表示不可' }
    }
  }
  if (typeof text !== 'string' || text.includes('�')) {
    return { kind: 'note', text: 'UTF-8 でないため、表示不可' }
  }

  const view = isNew ? allAdded(text, MAX_DIFF_LINES) : parseDiff(text, MAX_DIFF_LINES)
  if (view.lines.length === 0) {
    return { kind: 'note', text: isNew ? '空のファイル' : '差分を表示できない（バイナリなど）' }
  }

  return { kind: 'diff', view }
}

// ファイルを選んだときに、差分を作って atom に入れる。同じファイルをもう一度選ぶと閉じる。描画は atom を読むだけ。
async function toggleChange($: any, path: string) {
  if ((await read($, viewed))?.path === path) {
    await update($, viewed, () => null)
    return
  }
  const change = await describeChange($, path, await $.session.cwd())
  await update($, viewed, () => ({ path, change }))
}

// 進捗の読み直しは補助の機能。失敗しても、開始や編集の流れは止めない。
async function safeRefresh($: any) {
  try {
    await refreshProgress($)
  } catch {
    // 次の機会に読み直す。
  }
}

async function readText($: any, path: string): Promise<string | undefined> {
  try {
    const text = await $.fs.read(path)

    return typeof text === 'string' ? text : undefined
  } catch {
    return undefined
  }
}

// docs/grill-form/specs/*.md の status と plan、plan のチェックボックスの数を読み直して、atom に書く。
// 描画のたびには読まない。セッションの開始・編集ツールの実行後・進捗タブを開いたときに呼ぶ。
async function refreshProgress($: any) {
  const root = slashes(await $.session.cwd())
  let entries: { name: string; kind: string }[] = []
  try {
    entries = await $.fs.list(`${root}/${SPECS_DIR}`)
  } catch {
    // フォルダがなければ、一覧は空。
  }
  const items: ProgressItem[] = []
  for (const entry of entries.filter(x => x.kind === 'file' && /\.md$/i.test(x.name)).slice(0, MAX_SPECS)) {
    const specText = await readText($, `${root}/${SPECS_DIR}/${entry.name}`)
    const front = parseFrontmatter(specText ?? '')
    let plan = front.plan
    let planStatus: string | null = null
    let counts = { done: 0, total: 0 }
    let mtime = 0
    if (plan !== null) {
      const planPath = `${root}/${plan}`
      const planText = insideCwd(planPath, root) ? await readText($, planPath) : undefined
      if (planText === undefined) {
        plan = null
      } else {
        planStatus = parseFrontmatter(planText).status
        counts = countChecks(planText)
        mtime = (await $.fs.stat(planPath).catch(() => undefined))?.mtimeMs ?? 0
      }
    }
    items.push({ spec: entry.name, status: front.status, plan, planStatus, done: counts.done, total: counts.total, mtime })
  }
  await update($, progress, () => items)
}

// 1 セッションのモデル呼び出しの回数。同時に質問が来ても超えないよう、同期的に数える（ホットリロードでは 0 に戻る）。
let used = 0
// 新しい質問が来たら、前の質問の解説は捨てる。
let latest = 0

// AskUserQuestion の質問を、haiku に解説させる。失敗しても、質問は止めない。`$` を受け取る関数は、トップレベルに置く。
async function explain($: any, questions: AskQuestion[]) {
  const mine = ++latest
  const set = async (state: ExplainState) => {
    if (mine === latest) {
      await update($, explanation, () => state)
    }
  }
  if (used >= MAX_CALLS) {
    await set({ phase: 'limit', data: null })
    return
  }
  used++
  await set({ phase: 'loading', data: null })
  let data = null
  try {
    const prompt = buildExplainPrompt(questions, await read($, history))
    const result = await $.model.complete({ model: 'haiku', prompt, timeoutMs: 8000 })
    data = result?.isAnswered ? parseExplanation(result.text) : null
  } catch {
    // 依頼の組み立てもモデルの呼び出しも、失敗したら「作れなかった」にする。「作成中」のまま残さない。
  }
  await set(data === null ? { phase: 'failed', data: null } : { phase: 'ready', data })
}

const COLORS = { add: 'green', del: 'red', hunk: 'cyan', ctx: undefined } as const

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    void $.ui.open({ id: PANE, title: 'Session Desk' }).catch(() => {})
    try {
      const saved = parseQuick(await $.store.get(STORE_KEY))
      await update($, quick, () => saved ?? [...DEFAULT_QUICK])
    } catch {
      // 保存した定型文を読めなくても、初期値で動く。
    }
    await safeRefresh($)

    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    if (e.text.trim() !== '') {
      await update($, history, list => [...list, e.text])
    }

    return next(e)
  })

  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    void update($, tab, () => 'explain').catch(() => {})
    void explain($, e.questions).catch(() => {})

    return next(e)
  })

  on('classic.PostToolUse', async ($, e, next) => {
    if (EDIT_TOOLS.includes(e.tool_name)) {
      const input = (e.tool_input ?? {}) as { file_path?: unknown; notebook_path?: unknown }
      const path =
        typeof input.file_path === 'string'
          ? input.file_path
          : typeof input.notebook_path === 'string'
            ? input.notebook_path
            : undefined
      if (path !== undefined) {
        await update($, changed, list => (list.includes(path) ? [...list] : [...list, path]))
        // 開いていた差分は、再編集で古くなる。閉じて、開き直すときに作り直す。
        await update($, viewed, now => (now?.path === path ? null : now))
      }
      await safeRefresh($)
    }

    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const current = await read($, tab)

    let body
    if (current === 'history') {
      const sent = await read($, history)
      const phrases = await read($, quick)
      const chosen = await read($, selected)
      body = (
        <Box flexDirection="column">
          {sent.length === 0 && <Text dimColor>なし</Text>}
          {sent
            .map((text, i) => ({ text, n: i + 1 }))
            .reverse()
            .map(({ text, n }) => (
              <Box flexDirection="column">
                <Box gap={1}>
                  <Button
                    key={`history-${n}`}
                    label={`${n}. ${preview(text)}`}
                    onPress={() => update($, selected, now => (now === n ? null : n))}
                  />
                  <Button key={`history-add-${n}`} label="定型文に追加" onPress={() => saveQuick($, addQuick(phrases, text))} />
                </Box>
                {chosen === n && <Text>{stripControl(text)}</Text>}
              </Box>
            ))}
        </Box>
      )
    } else if (current === 'explain') {
      const state = await read($, explanation)
      const data = state.data
      body = (
        <Box flexDirection="column">
          {state.phase === 'none' && <Text dimColor>なし</Text>}
          {state.phase === 'loading' && <Text dimColor>解説を作成中…</Text>}
          {state.phase === 'failed' && <Text dimColor>解説を作れなかった</Text>}
          {state.phase === 'limit' && <Text dimColor>{`解説の上限（${MAX_CALLS} 回）に達した`}</Text>}
          {state.phase === 'ready' && data !== null && (
            <Box flexDirection="column">
              <Text dimColor>AI による推定</Text>
              <Text bold>指示の要約</Text>
              <Text>{data.summary}</Text>
              <Text bold>なぜ今この質問か</Text>
              <Text>{data.reason}</Text>
              <Text bold>選択肢ごとの影響</Text>
              {data.options.map(option => (
                <Text>{`・${option.label}: ${option.effect}`}</Text>
              ))}
              <Text bold>推奨</Text>
              <Text>{data.recommend}</Text>
            </Box>
          )}
        </Box>
      )
    } else if (current === 'quick') {
      const phrases = await read($, quick)
      body = (
        <Box flexDirection="column">
          {phrases.length === 0 && <Text dimColor>なし</Text>}
          {phrases.map((text, i) => (
            <Box gap={1}>
              <Button
                key={`quick-${i}`}
                label={stripControl(text)}
                onPress={() => {
                  void $.prompt.submit({ text })
                }}
              />
              <Button key={`quick-del-${i}`} label="削除" onPress={() => saveQuick($, removeQuick(phrases, i))} />
            </Box>
          ))}
        </Box>
      )
    } else if (current === 'changes') {
      const files = await read($, changed)
      const change = (await read($, viewed))?.change
      body = (
        <Box flexDirection="column">
          {files.length === 0 && <Text dimColor>なし</Text>}
          {files.map((path, i) => (
            <Button key={`change-${i}`} label={stripControl(path)} onPress={() => toggleChange($, path)} />
          ))}
          {change?.kind === 'note' && <Text dimColor>{change.text}</Text>}
          {change?.kind === 'diff' &&
            change.view.lines.map(line => (
              <Text color={COLORS[line.kind]} dimColor={line.kind === 'hunk'} wrap="truncate-end">
                {line.text}
              </Text>
            ))}
          {change?.kind === 'diff' && change.view.truncated && <Text dimColor>{`${MAX_DIFF_LINES} 行までを表示`}</Text>}
        </Box>
      )
    } else {
      const items = await read($, progress)
      body = (
        <Box flexDirection="column">
          {items.length === 0 && <Text dimColor>なし</Text>}
          {items.map(item => {
            const bar = progressBar(item.done, item.total)

            return (
              <Box flexDirection="column">
                <Text bold>{stripControl(`${item.spec}（${item.status ?? '不明'}）`)}</Text>
                {item.plan === null && <Text dimColor>計画: 未作成</Text>}
                {item.plan !== null && (
                  <Box gap={1}>
                    <Text dimColor>{stripControl(item.plan)}</Text>
                    {bar !== null && <Text>{bar.bar}</Text>}
                    {bar !== null && <Text>{bar.label}</Text>}
                  </Box>
                )}
              </Box>
            )
          })}
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        <Box gap={1}>
          {TABS.map(item => (
            <Button
              key={`tab-${item.id}`}
              label={item.label}
              onPress={async () => {
                if (item.id === 'progress') {
                  await safeRefresh($)
                }
                await update($, tab, () => item.id)
              }}
            />
          ))}
        </Box>
        {body}
      </Box>
    )
  })

  // 入力欄の上のバンド: 完了していない計画のうち、更新が最も新しい 1 件の進捗バー。なければ何も足さない。
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) {
      return next(e)
    }
    const current = pickCurrent(await read($, progress))
    const bar = current === undefined ? null : progressBar(current.done, current.total)
    if (bar === null) {
      return next(e)
    }
    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box gap={1}>
        <Text>{bar.bar}</Text>
        <Text>{bar.label}</Text>
      </Box>
    )
  })
}
