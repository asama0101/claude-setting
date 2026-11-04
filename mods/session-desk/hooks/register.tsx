import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { ChangeView, Tab } from '../types'
import {
  DEFAULT_QUICK,
  addQuick,
  allAdded,
  insideCwd,
  isSecretName,
  parseDiff,
  parseQuick,
  preview,
  relativePath,
  removeQuick,
  splitPath,
  stripControl,
} from './lib'

const PANE = 'session-desk'
const STORE_KEY = 'quick'
const MAX_BYTES = 1_000_000
const MAX_DIFF_LINES = 500
const EDIT_TOOLS = ['Edit', 'Write', 'NotebookEdit']

// 状態は、このモジュールの atom に持つ。形を変えるときは、shape のタグを変える。
const SHAPE = { shape: 'desk-1' } as const
const history = atom({ plugin: 'session-desk', key: 'history' } as const, [], SHAPE)
const quick = atom({ plugin: 'session-desk', key: 'quick' } as const, [...DEFAULT_QUICK], SHAPE)
const changed = atom({ plugin: 'session-desk', key: 'changed' } as const, [], SHAPE)
const tab = atom({ plugin: 'session-desk', key: 'tab' } as const, 'history' as Tab)
const selected = atom({ plugin: 'session-desk', key: 'selected' } as const, null as number | null)
const viewed = atom({ plugin: 'session-desk', key: 'viewed' } as const, null as ChangeView)

const TABS: readonly { id: Tab; label: string }[] = [
  { id: 'history', label: '履歴' },
  { id: 'quick', label: '定型文' },
  { id: 'changes', label: '編集ファイル' },
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

// パネルが開いていれば閉じ、閉じていれば（幅が足りず、描かれずに待っているときも）開く。
// 人の押下で開くため、端末の幅に関係なく出る。
async function togglePane($: any) {
  const isUp = (await $.ui.panes()).some((pane: { id: string; isPlaced: boolean }) => pane.id === PANE && pane.isPlaced)
  if (isUp) {
    await $.ui.close({ id: PANE })
  } else {
    await $.ui.open({ id: PANE, title: 'Session Desk' })
  }
}

const COLORS = { add: 'green', del: 'red', ctx: undefined } as const

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    void $.ui.open({ id: PANE, title: 'Session Desk' }).catch(() => {})
    try {
      const saved = parseQuick(await $.store.get(STORE_KEY))
      await update($, quick, () => saved ?? [...DEFAULT_QUICK])
    } catch {
      // 保存した定型文を読めなくても、初期値で動く。
    }

    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    // 履歴には、ユーザーが送ったものだけを載せる。サブエージェント宛てなど、他の送信元は載せない。
    const byUser =
      e.origin?.kind === 'composer' ||
      e.origin?.kind === 'bridge' ||
      (e.origin?.kind === 'plugin' && e.origin.name === 'session-desk')
    if (byUser && e.text.trim() !== '') {
      await update($, history, list => [...list, e.text])
    }

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
        <Box flexDirection="column" gap={1}>
          {sent.length === 0 && <Text dimColor>なし</Text>}
          {sent
            .map((text, i) => ({ text, n: i + 1 }))
            .reverse()
            .map(({ text, n }) => {
              // 開いているかの判定は 1 回にして、label と見た目で食い違わないようにする。
              const isOpen = chosen === n
              const mark = isOpen ? '▴' : '▾'
              const word = isOpen ? '短く' : '全文'

              return (
                <Box flexDirection="column">
                  <Text>{`${n}. ${isOpen ? stripControl(text) : preview(text)}`}</Text>
                  <Box gap={2}>
                    <Button
                      key={`history-${n}`}
                      plain
                      label={`${mark} ${word}`}
                      onPress={() => update($, selected, now => (now === n ? null : n))}
                    >
                      <Text color="suggestion">{`${mark} ${word}`}</Text>
                    </Button>
                    <Button
                      key={`history-add-${n}`}
                      plain
                      label="＋ 定型文に追加"
                      onPress={() => saveQuick($, addQuick(phrases, text))}
                    >
                      <Text color="suggestion">＋ 定型文に追加</Text>
                    </Button>
                  </Box>
                </Box>
              )
            })}
        </Box>
      )
    } else if (current === 'quick') {
      const phrases = await read($, quick)
      body = (
        <Box flexDirection="column" gap={1}>
          {phrases.length === 0 && <Text dimColor>なし</Text>}
          {phrases.map((text, i) => (
            <Box flexDirection="column">
              <Text>{stripControl(text)}</Text>
              <Box gap={2}>
                <Button
                  key={`quick-${i}`}
                  plain
                  label="▶ 送信"
                  onPress={() => {
                    void $.prompt.submit({ text })
                  }}
                >
                  <Text color="suggestion">▶ 送信</Text>
                </Button>
                <Button
                  key={`quick-del-${i}`}
                  plain
                  label="× 削除"
                  onPress={() => saveQuick($, removeQuick(phrases, i))}
                >
                  <Text color="error">× 削除</Text>
                </Button>
              </Box>
            </Box>
          ))}
        </Box>
      )
    } else {
      const files = await read($, changed)
      const opened = await read($, viewed)
      const cwd = await $.session.cwd()
      body = (
        <Box flexDirection="column" gap={1}>
          {files.length === 0 && <Text dimColor>なし</Text>}
          {files.map((path, i) => {
            const isOpen = opened?.path === path
            const { name, dir } = splitPath(relativePath(path, cwd))
            const change = isOpen ? opened?.change : undefined
            // 行番号の桁は、3 桁を最小に、表示する最大の番号に合わせる（大きいファイルでも本文がずれない）。
            const width =
              change?.kind === 'diff' ? Math.max(3, ...change.view.lines.map(line => String(line.no ?? '').length)) : 3

            // 差分は、選んだファイルの項目の中（名前とフォルダの真下）に開く。どのファイルの差分かが、位置で分かる。
            return (
              <Box key={`change-item-${i}`} flexDirection="column">
                <Button
                  key={`change-${i}`}
                  plain
                  label={`${isOpen ? '▸ ' : ''}${stripControl(name)}`}
                  onPress={() => toggleChange($, path)}
                >
                  {isOpen && <Text color="suggestion">▸ </Text>}
                  <Text bold={isOpen}>{stripControl(name)}</Text>
                </Button>
                {dir !== '' && <Text dimColor>{`  ${stripControl(dir)}`}</Text>}
                {change?.kind === 'note' && <Text dimColor>{`│ ${change.text}`}</Text>}
                {change?.kind === 'diff' &&
                  change.view.lines.map((line, index) =>
                    line.kind === 'hunk' ? (
                      index === 0 ? null : <Text key={`diff-${index}`} dimColor>│ ⋯</Text>
                    ) : (
                      <Text key={`diff-${index}`} color={COLORS[line.kind]} dimColor={line.kind === 'ctx'}>
                        {`│${String(line.no ?? '').padStart(width)} ${line.text}`}
                      </Text>
                    ),
                  )}
                {change?.kind === 'diff' && change.view.truncated && <Text dimColor>{`│ ${MAX_DIFF_LINES} 行までを表示`}</Text>}
              </Box>
            )
          })}
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        <Box gap={2}>
          {TABS.map(item =>
            current === item.id ? (
              <Button key={`tab-${item.id}`} plain label={`▸ ${item.label}`} onPress={() => update($, tab, () => item.id)}>
                <Text color="suggestion">▸</Text> <Text bold>{item.label}</Text>
              </Button>
            ) : (
              <Button key={`tab-${item.id}`} plain dimColor label={item.label} onPress={() => update($, tab, () => item.id)} />
            ),
          )}
        </Box>
        {body}
      </Box>
    )
  })

  // 入力欄の上のバンド: パネルの開閉ボタン 1 つ。アンケート中は出さない。
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) {
      return next(e)
    }
    const { Box, Button } = $.ui.resolve(e)

    return (
      <Box>
        <Button key="panel-toggle" label="サイドパネルの開閉" onPress={() => togglePane($)} />
      </Box>
    )
  })
}
