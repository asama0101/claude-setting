import { expect, test } from 'claude-code/testing'

import { preview } from './lib'
import { ESC, parentOf, textsOf } from './test-kit'

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

// エンジンの代わりの受け皿。送信は、そのまま通す。
function fakeEngine(on: any) {
  on('prompt.submit', (_: any, e: any) => ({ text: e.text }))
}

// 実際の送信は wait と origin も持つ。テストでは text だけを渡す。
const send = ($: any, text: string) => $.prompt.submit({ text })

// 一覧の行は、番号つきの Text。描画の JSON から、順に取り出す。
const rows = async (ui: any): Promise<string[]> => textsOf(await ui.drawn()).filter(text => /^[0-9]+\. /.test(text))

test('preview collapses whitespace, strips control codes and cuts at 60 characters', async () => {
  expect(preview('short')).toBe('short')
  expect(preview(`a${String.fromCharCode(0x200b)}b${String.fromCharCode(0x202e)}c`)).toBe('abc')
  expect(preview('a\n  b\tc')).toBe('a b c')
  expect(preview(`${ESC}[31mred${ESC}[0m`)).toBe('red')
  expect(preview('x'.repeat(60))).toBe('x'.repeat(60))
  expect(preview('x'.repeat(61))).toBe(`${'x'.repeat(60)}…`)
})

test('history lists sent prompts newest first with numbers, keeping duplicates', async ($, on) => {
  fakeEngine(on)
  for (const text of ['first', 'second', 'second', 'third']) {
    await send($, text)
  }
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await rows(ui)).toEqual(['4. third', '3. second', '2. second', '1. first'])
  await ui.unmount()
})

test('history does not record blank prompts and passes the prompt through unchanged', async ($, on) => {
  fakeEngine(on)
  const sent = await send($, '  \n ')
  expect(sent.text).toBe('  \n ')
  await send($, 'real')
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await rows(ui)).toEqual(['1. real'])
  await ui.unmount()
})

test('history shows 60 characters, and selecting a row shows the whole prompt', async ($, on) => {
  fakeEngine(on)
  const long = `${'a'.repeat(60)}${'b'.repeat(40)}`
  await send($, long)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await rows(ui)).toEqual([`1. ${'a'.repeat(60)}…`])
  expect(await ui.find({ type: 'Text', text: long })).toBeUndefined()
  await ui.press({ key: 'history-1' })
  expect((await ui.find({ type: 'Text', text: long }))?.text).toBe(long)
  await ui.press({ key: 'history-1' })
  expect(await ui.find({ type: 'Text', text: long })).toBeUndefined()
  await ui.unmount()
})

test('the prompt is plain text and the actions are short bordered buttons on their own line', async ($, on) => {
  fakeEngine(on)
  const long = 'x'.repeat(100)
  await send($, long)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const tree = await ui.drawn()
  const json = JSON.stringify(tree)
  // 文は Button の label に入れない。操作の名前は短い。
  expect(json).not.toContain('"label":"1. ')
  expect(json).toContain('"label":"全文"')
  expect(json).toContain('"label":"定型文に追加"')
  // 2 つの操作のボタンは同じ段にあり、その段に文は入っていない。外側は縦並び。
  const actions = parentOf(tree, 'history-1')
  expect(parentOf(tree, 'history-add-1')).toBe(actions)
  expect(JSON.stringify(actions)).not.toContain('xxxx')
  // 追加は目立つ色（primary）。全文は控えめ（secondary）。
  expect(JSON.stringify(await ui.find({ key: 'history-add-1' }))).toContain('"variant":"primary"')
  expect(JSON.stringify(await ui.find({ key: 'history-1' }))).toContain('"variant":"secondary"')
  await ui.unmount()
})

test('history shows a note when nothing was sent', async ($, on) => {
  fakeEngine(on)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'なし' })).toBeDefined()
  await ui.unmount()
})
