import { expect, test } from 'claude-code/testing'

import { allAdded, insideCwd, isSecretName, parseDiff } from './lib'

const PANE = {
  plugin: 'session-desk',
  component: 'Pane',
  requestId: 'session-desk',
  props: {
    title: 'Session Desk',
    isFocused: false,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const NL = String.fromCharCode(10)
const BS = String.fromCharCode(92)
const BAD = `a${String.fromCharCode(0xfffd)}b`

const DIFF = [
  'diff --git a/src/a.py b/src/a.py',
  'index 111..222 100644',
  '--- a/src/a.py',
  '+++ b/src/a.py',
  '@@ -1,3 +1,3 @@',
  ' keep',
  '-old line',
  '+new line',
  ' tail',
].join(NL)

test('parseDiff drops the file header and classifies each line', async () => {
  const { lines, truncated } = parseDiff(DIFF, 500)
  expect(truncated).toBe(false)
  expect(lines).toEqual([
    { kind: 'hunk', text: '@@ -1,3 +1,3 @@' },
    { kind: 'ctx', text: ' keep' },
    { kind: 'del', text: '-old line' },
    { kind: 'add', text: '+new line' },
    { kind: 'ctx', text: ' tail' },
  ])
})

test('parseDiff and allAdded cut at the limit and say so', async () => {
  const many = ['@@ -0,0 +1,600 @@', ...Array.from({ length: 600 }, (_, i) => `+line ${i}`)].join(NL)
  const cut = parseDiff(many, 500)
  expect(cut.lines.length).toBe(500)
  expect(cut.truncated).toBe(true)
  const text = Array.from({ length: 700 }, (_, i) => `row ${i}`).join(NL) + NL
  const added = allAdded(text, 500)
  expect(added.lines.length).toBe(500)
  expect(added.truncated).toBe(true)
  expect(allAdded(`a${NL}b${NL}`, 500).lines).toEqual([
    { kind: 'add', text: '+a' },
    { kind: 'add', text: '+b' },
  ])
})

test('isSecretName and insideCwd', async () => {
  expect(isSecretName('D:/p/.env')).toBe(true)
  expect(isSecretName('D:/p/src/a.py')).toBe(false)
  expect(insideCwd('D:/p/src/a.py', 'D:/p')).toBe(true)
  expect(insideCwd(`d:${BS}p${BS}a.py`, 'D:/p')).toBe(true)
  expect(insideCwd('E:/x/a.py', 'D:/p')).toBe(false)
  expect(insideCwd('D:/p/../q/a.py', 'D:/p')).toBe(false)
})

type FakeFile = { text: string; size?: number; real?: string; noReal?: boolean; readError?: boolean }

// エンジンの代わりの受け皿。git diff の結果は diffs（パス → 出力）。diffs にないパスは、追跡されていないファイルとして扱う。
function fakeEngine(on: any, files: Record<string, FakeFile>, diffs: Record<string, string>, gitExit = 0, gitError = 'fatal: not a git repository') {
  const norm = (path: string) => path.split(BS).join('/')
  const runs: string[][] = []
  on('session.cwd', () => ({ value: 'D:/p' }))
  on('classic.PostToolUse', () => ({}))
  on('fs.exists', (_: any, e: any) => ({ value: norm(e.path) in files }))
  on('fs.stat', (_: any, e: any) => {
    const file = files[norm(e.path)]

    return {
      value: { kind: 'file', size: file?.size ?? file?.text.length ?? 0, mtimeMs: 0, isLink: false, realPath: file?.noReal ? undefined : (file?.real ?? norm(e.path)) },
    }
  })
  on('fs.read', (_: any, e: any): any => {
    if (files[norm(e.path)]?.readError) {
      throw new Error('unreadable')
    }

    return { value: files[norm(e.path)]?.text ?? '' }
  })
  on('process.run', (_: any, e: any) => {
    runs.push([...e.argv])
    const last = norm(e.argv[e.argv.length - 1] ?? '')
    if (gitExit !== 0) {
      return { value: { exitCode: gitExit, stdout: '', stderr: gitError } }
    }
    if (e.argv.includes('diff')) {
      return { value: { exitCode: 0, stdout: diffs[last] ?? '', stderr: '' } }
    }

    // ls-files --error-unmatch: 追跡されていないなら 1
    return { value: { exitCode: last in diffs ? 0 : 1, stdout: '', stderr: '' } }
  })

  return { runs }
}

const edited = (tool: string, path: string) => ({
  tool_name: tool,
  tool_input: tool === 'NotebookEdit' ? { notebook_path: path } : { file_path: path },
  tool_response: {},
  tool_use_id: 'u',
  cwd: 'D:/p',
})

const open = async ($: any) => {
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'tab-changes' })

  return ui
}
const names = async (ui: any): Promise<string[]> =>
  [...JSON.stringify(await ui.drawn()).matchAll(/"key":"change-[0-9]+"[^}]*?"label":"([^"]*)"/g)].map(m => m[1] ?? '')

test('the changes tab lists edited files once, for Edit, Write and NotebookEdit only', async ($, on) => {
  fakeEngine(on, {}, {})
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  await $.classic.PostToolUse(edited('Write', 'D:/p/b.py'))
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  await $.classic.PostToolUse(edited('NotebookEdit', 'D:/p/n.ipynb'))
  await $.classic.PostToolUse(edited('Read', 'D:/p/c.py'))
  const ui = await open($)
  expect(await names(ui)).toEqual(['D:/p/a.py', 'D:/p/b.py', 'D:/p/n.ipynb'])
  await ui.unmount()
})

test('selecting a tracked file shows its diff, additions green and deletions red', async ($, on) => {
  fakeEngine(on, { 'D:/p/src/a.py': { text: 'x' } }, { 'D:/p/src/a.py': DIFF })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/src/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(JSON.stringify(await ui.find({ type: 'Text', text: '+new line' }))).toContain('green')
  expect(JSON.stringify(await ui.find({ type: 'Text', text: '-old line' }))).toContain('red')
  expect(await ui.find({ type: 'Text', text: ' keep' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '@@ -1,3 +1,3 @@' })).toBeDefined()
  await ui.unmount()
})

test('an untracked new file is shown with every line added', async ($, on) => {
  fakeEngine(on, { 'D:/p/new.py': { text: `one${NL}two${NL}` } }, {})
  await $.classic.PostToolUse(edited('Write', 'D:/p/new.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(JSON.stringify(await ui.find({ type: 'Text', text: '+one' }))).toContain('green')
  expect(await ui.find({ type: 'Text', text: '+two' })).toBeDefined()
  await ui.unmount()
})

test('outside a git repository the diff cannot be shown', async ($, on) => {
  fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, {}, 128)
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: /Git のリポジトリではない/ })).toBeDefined()
  await ui.unmount()
})

test('git is run without external diff or textconv, with three context lines', async ($, on) => {
  const { runs } = fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, { 'D:/p/a.py': DIFF })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(runs.find(argv => argv.includes('diff'))).toEqual(['git', '-c', 'core.fsmonitor=false', 'diff', '--no-ext-diff', '--no-textconv', '-U3', 'HEAD', '--', 'D:/p/a.py'])
  await ui.unmount()
})

test('the diff is computed when a file is selected, not on every redraw', async ($, on) => {
  const { runs } = fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, { 'D:/p/a.py': DIFF })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  await ui.drawn()
  await ui.drawn()
  expect(runs.filter(argv => argv.includes('diff')).length).toBe(1)
  await ui.unmount()
})

test('a binary diff, a missing real path and other git failures each get their own note', async ($, on) => {
  const binary = ['diff --git a/a.bin b/a.bin', 'Binary files a/a.bin and b/a.bin differ'].join(NL)
  fakeEngine(on, { 'D:/p/a.bin': { text: 'x' }, 'D:/p/n.py': { text: 'x', noReal: true } }, { 'D:/p/a.bin': binary })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.bin'))
  await $.classic.PostToolUse(edited('Edit', 'D:/p/n.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: /バイナリ/ })).toBeDefined()
  await ui.press({ key: 'change-1' })
  expect(await ui.find({ type: 'Text', text: /実パス/ })).toBeDefined()
  await ui.unmount()
})

test('a git failure that is not "not a repository" is reported as a failed git diff', async ($, on) => {
  fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, {}, 128, 'fatal: bad revision HEAD')
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: /git diff が失敗/ })).toBeDefined()
  await ui.unmount()
})

test('more secret file names are never shown', async () => {
  for (const name of ['secrets.yml', 'prod.tfvars', 'a.p12', 'a.ppk', 'id_ed25519', 'id_ecdsa', '.netrc', '.pypirc', 'service-account-prod.json', 'id_dsa', 'a.jks', 'a.keystore', 'a.kdbx', '.htpasswd']) {
    expect(isSecretName(`D:/p/${name}`)).toBe(true)
  }
  for (const name of ['README.md', 'secretary.md', 'secrets_policy_notes.md']) {
    expect(isSecretName(`D:/p/${name}`)).toBe(false)
  }
})

test('secret names, paths outside the cwd, big files and non-UTF-8 are never shown or sent to git', async ($, on) => {
  const { runs } = fakeEngine(
    on,
    {
      'D:/p/.env': { text: 'KEY=1' },
      'D:/q/a.py': { text: 'x' },
      'D:/p/link.txt': { text: 'x', real: 'D:/p/.env' },
      'D:/p/big.py': { text: 'x', size: 1_000_001 },
      'D:/p/bad.py': { text: BAD },
    },
    { 'D:/p/bad.py': BAD },
  )
  for (const path of ['D:/p/.env', 'D:/q/a.py', 'D:/p/link.txt', 'D:/p/big.py', 'D:/p/bad.py']) {
    await $.classic.PostToolUse(edited('Edit', path))
  }
  const ui = await open($)
  const expectNote = async (key: string, note: RegExp) => {
    await ui.press({ key })
    expect(await ui.find({ type: 'Text', text: note })).toBeDefined()
  }
  await expectNote('change-0', /秘密の可能性/)
  await expectNote('change-1', /作業ディレクトリの外/)
  await expectNote('change-2', /秘密の可能性/)
  await expectNote('change-3', /1MB/)
  await expectNote('change-4', /UTF-8/)
  const sent = runs.flat().filter(a => a.endsWith('.env') || a.startsWith('D:/q') || a.endsWith('link.txt') || a.endsWith('big.py'))
  expect(sent).toEqual([])
  await ui.unmount()
})

test('editing a file again closes its old diff so a stale one is never shown', async ($, on) => {
  fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, { 'D:/p/a.py': DIFF })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: '+new line' })).toBeDefined()
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  expect(await ui.find({ type: 'Text', text: '+new line' })).toBeUndefined()
  await ui.unmount()
})

test('an untracked file that cannot be read gets a note, not an unhandled error', async ($, on) => {
  fakeEngine(on, { 'D:/p/new.py': { text: 'x', readError: true } }, {})
  await $.classic.PostToolUse(edited('Write', 'D:/p/new.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: /読み取れない/ })).toBeDefined()
  await ui.unmount()
})

test('a long diff is cut at 500 lines with a note', async ($, on) => {
  const long = ['@@ -0,0 +1,600 @@', ...Array.from({ length: 600 }, (_, i) => `+line ${i}`)].join(NL)
  fakeEngine(on, { 'D:/p/a.py': { text: 'x' } }, { 'D:/p/a.py': long })
  await $.classic.PostToolUse(edited('Edit', 'D:/p/a.py'))
  const ui = await open($)
  await ui.press({ key: 'change-0' })
  expect(await ui.find({ type: 'Text', text: /500 行まで/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '+line 498' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '+line 499' })).toBeUndefined()
  await ui.unmount()
})
