import { expect, test } from 'claude-code/testing'

import { DEFAULT_QUICK, addQuick, parseQuick, removeQuick } from './lib'

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

const PHRASES = [
  '残りのタスクは？',
  '選択肢ごとにメリット・デメリットを明確にして推奨および影響をレポートして',
  'Artifact使ってデザインを見せて',
]

// エンジンの代わりの受け皿。送信された文言を submitted に、ストアの中身を saved に残す。
function fakeEngine(on: any, entries?: Record<string, unknown>) {
  const submitted: string[] = []
  const saved = new Map<string, unknown>(Object.entries(entries ?? {}))
  on('store.get', (_: any, e: any) => ({ value: saved.get(e.key) }))
  on('store.set', (_: any, e: any) => {
    saved.set(e.key, e.value)

    return { value: undefined }
  })
  on('prompt.submit', (_: any, e: any) => {
    submitted.push(e.text)

    return { text: e.text }
  })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('ui.open', () => ({ value: { isPlaced: true } }))

  return { submitted, saved }
}

const start = ($: any) => $.session.start({ cwd: 'D:/p', surface: 'terminal', interactive: true })
const send = ($: any, text: string) => $.prompt.submit({ text })
const labels = async (ui: any, prefix: string): Promise<string[]> =>
  [...JSON.stringify(await ui.drawn()).matchAll(new RegExp(`"key":"${prefix}-([0-9]+)"[^}]*?"label":"([^"]*)"`, 'g'))].map(m => m[2] ?? '')
const open = async ($: any) => {
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'tab-quick' })

  return ui
}

test('DEFAULT_QUICK is the three phrases', async () => {
  expect([...DEFAULT_QUICK]).toEqual(PHRASES)
})

test('parseQuick accepts only an array of non-empty strings', async () => {
  expect(parseQuick(['a', 'b'])).toEqual(['a', 'b'])
  expect(parseQuick([])).toEqual([])
  expect(parseQuick('a')).toBe(null)
  expect(parseQuick(['a', 1])).toBe(null)
  expect(parseQuick(['a', ''])).toBe(null)
  expect(parseQuick(undefined)).toBe(null)
})

test('addQuick ignores blanks and duplicates; removeQuick drops one index', async () => {
  expect(addQuick(['a'], 'b')).toEqual(['a', 'b'])
  expect(addQuick(['a'], 'a')).toEqual(['a'])
  expect(addQuick(['a'], '  ')).toEqual(['a'])
  expect(removeQuick(['a', 'b', 'c'], 1)).toEqual(['a', 'c'])
  expect(removeQuick(['a'], 5)).toEqual(['a'])
})

test('with an empty store the quick tab lists the three default phrases', async ($, on) => {
  fakeEngine(on)
  await start($)
  const ui = await open($)
  expect(await labels(ui, 'quick')).toEqual(PHRASES)
  await ui.unmount()
})

test('pressing a phrase submits its exact text', async ($, on) => {
  const { submitted } = fakeEngine(on)
  await start($)
  const ui = await open($)
  await ui.press({ key: 'quick-0' })
  await ui.press({ key: 'quick-2' })
  expect(submitted).toEqual([PHRASES[0], PHRASES[2]])
  await ui.unmount()
})

test('adding from history keeps one copy and saves to the store', async ($, on) => {
  const { saved } = fakeEngine(on)
  await start($)
  await send($, 'レビューして')
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'history-add-1' })
  await ui.press({ key: 'history-add-1' })
  await ui.press({ key: 'tab-quick' })
  expect(await labels(ui, 'quick')).toEqual([...PHRASES, 'レビューして'])
  expect(saved.get('quick')).toEqual([...PHRASES, 'レビューして'])
  await ui.unmount()
})

test('deleting removes the phrase and saves to the store', async ($, on) => {
  const { saved } = fakeEngine(on)
  await start($)
  const ui = await open($)
  await ui.press({ key: 'quick-del-0' })
  expect(await labels(ui, 'quick')).toEqual([PHRASES[1], PHRASES[2]])
  expect(saved.get('quick')).toEqual([PHRASES[1], PHRASES[2]])
  await ui.unmount()
})

test('saved phrases are loaded at session start; a bad stored value falls back to the defaults', async ($, on) => {
  fakeEngine(on, { quick: ['x', 'y'] })
  await start($)
  const ui = await open($)
  expect(await labels(ui, 'quick')).toEqual(['x', 'y'])
  await ui.unmount()
})

test('a bad stored value falls back to the defaults', async ($, on) => {
  fakeEngine(on, { quick: 'not-an-array' })
  await start($)
  const ui = await open($)
  expect(await labels(ui, 'quick')).toEqual(PHRASES)
  await ui.unmount()
})

test('session start still completes when the store cannot be read, and the defaults are used', async ($, on) => {
  // store.get の受け皿がないので、$.store.get は失敗する。
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  const started = await start($)
  expect(started.cwd).toBe('D:/p')
  const ui = await open($)
  expect(await labels(ui, 'quick')).toEqual(PHRASES)
  await ui.unmount()
})

test('the quick tab shows a note when every phrase is deleted', async ($, on) => {
  fakeEngine(on, { quick: [] })
  await start($)
  const ui = await open($)
  expect(await ui.find({ type: 'Text', text: 'なし' })).toBeDefined()
  await ui.unmount()
})
