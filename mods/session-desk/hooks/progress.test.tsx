import { expect, test } from 'claude-code/testing'

import { countChecks, parseFrontmatter, pickCurrent, progressBar } from './lib'
import { BAND, engineDraws } from './test-kit'

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
const SPECS = 'D:/p/docs/grill-form/specs'

const spec = (status: string, plan: string) => ['---', `status: ${status}`, `plan: ${plan}`, '---', '# SPEC'].join(NL)
const plan = (status: string, ...checks: string[]) =>
  ['---', `status: ${status}`, 'spec: x', '---', '# Plan', ...checks.map(c => `- [${c}] step`)].join(NL)

test('parseFrontmatter reads status and plan; an unwritten plan is null', async () => {
  expect(parseFrontmatter(spec('未対応', 'docs/grill-form/plans/a.md'))).toEqual({ status: '未対応', plan: 'docs/grill-form/plans/a.md' })
  expect(parseFrontmatter(spec('未対応', '（未作成）'))).toEqual({ status: '未対応', plan: null })
  expect(parseFrontmatter('# no frontmatter')).toEqual({ status: null, plan: null })
})

test('parseFrontmatter reads a file that starts with a BOM', async () => {
  const bom = String.fromCharCode(0xfeff)
  expect(parseFrontmatter(bom + spec('未対応', 'docs/grill-form/plans/a.md'))).toEqual({ status: '未対応', plan: 'docs/grill-form/plans/a.md' })
})

test('countChecks counts checked and all checkboxes', async () => {
  expect(countChecks(plan('未対応', ' ', 'x', 'X', ' '))).toEqual({ done: 2, total: 4 })
  expect(countChecks('no boxes')).toEqual({ done: 0, total: 0 })
})

test('pickCurrent takes the newest plan that is not finished and has steps', async () => {
  const item = (name: string, planStatus: string | null, total: number, mtime: number) => ({
    spec: name, status: '未対応', plan: `${name}.md`, planStatus, done: 0, total, mtime,
  })
  const items = [item('a', '未対応', 3, 10), item('b', '完了', 3, 99), item('c', '未対応', 3, 20), item('d', '未対応', 0, 50), item('e', null, 0, 60)]
  expect(pickCurrent(items)?.spec).toBe('c')
  expect(pickCurrent([item('b', '完了', 3, 99)])).toBeUndefined()
  expect(pickCurrent([])).toBeUndefined()
})

type FakeFile = { text: string; mtime?: number }

// 作業ディレクトリ D:/p の中の、仮のファイル。エンジンの $.fs・$.session の受け皿。
function fakeEngine(on: any, files: Record<string, FakeFile>, withStore = true) {
  const norm = (path: string) => path.split(BS).join('/')
  on('session.cwd', () => ({ value: 'D:/p' }))
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  if (withStore) {
    on('store.get', () => ({ value: undefined }))
  }
  on('classic.PostToolUse', () => ({}))
  on('fs.exists', (_: any, e: any) => ({ value: norm(e.path) in files }))
  on('fs.stat', (_: any, e: any) => ({
    value: { kind: 'file', size: files[norm(e.path)]?.text.length ?? 0, mtimeMs: files[norm(e.path)]?.mtime ?? 0, isLink: false, realPath: norm(e.path) },
  }))
  on('fs.read', (_: any, e: any) => ({ value: files[norm(e.path)]?.text ?? '' }))
  on('fs.list', (_: any, e: any) => {
    const prefix = `${norm(e.path)}/`
    const names = new Map<string, 'file' | 'dir'>()
    for (const p of Object.keys(files)) {
      if (p.startsWith(prefix)) {
        const rest = p.slice(prefix.length)
        names.set(rest.split('/')[0] ?? '', rest.includes('/') ? 'dir' : 'file')
      }
    }

    return { value: [...names].map(([name, kind]) => ({ name, kind, size: 0, mtimeMs: 0, isLink: false })) }
  })

  return files
}

const start = ($: any) => $.session.start({ cwd: 'D:/p', surface: 'terminal', interactive: true })
const edited = (path: string) => ({
  tool_name: 'Edit',
  tool_input: { file_path: path },
  tool_response: {},
  tool_use_id: 'u',
  cwd: 'D:/p',
})
const texts = async (ui: any): Promise<string[]> =>
  [...JSON.stringify(await ui.drawn()).matchAll(/"children":\["([^"]*)"\]/g)].map(m => m[1] ?? '')
const openTab = async ($: any) => {
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'tab-progress' })

  return ui
}

const FILES: Record<string, FakeFile> = {
  [`${SPECS}/2026-a-design.md`]: { text: spec('未対応', 'docs/grill-form/plans/2026-a.md') },
  [`${SPECS}/2026-b-design.md`]: { text: spec('完了', 'docs/grill-form/plans/2026-b.md') },
  [`${SPECS}/2026-c-design.md`]: { text: spec('未対応', '（未作成）') },
  'D:/p/docs/grill-form/plans/2026-a.md': { text: plan('未対応', 'x', ' ', ' '), mtime: 20 },
  'D:/p/docs/grill-form/plans/2026-b.md': { text: plan('完了', 'x', 'x'), mtime: 30 },
}

test('the progress tab lists each SPEC with its status, its plan and the plan steps done', async ($, on) => {
  fakeEngine(on, { ...FILES })
  await start($)
  const ui = await openTab($)
  const all = (await texts(ui)).join('|')
  expect(all).toContain('2026-a-design.md')
  expect(all).toContain('2026-c-design.md')
  expect(all).toContain('未作成')
  expect(all).toContain('1/3')
  expect(all).toContain('2/2')
  expect(all).toContain('█'.repeat(3) + '░'.repeat(7))
  await ui.unmount()
})

test('the band shows the newest unfinished plan only, and yields to a survey', async ($, on) => {
  engineDraws(on)
  fakeEngine(on, { ...FILES })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  const bar = progressBar(1, 3)
  expect((await ui.find({ type: 'Text', text: bar?.bar }))?.text).toBe(bar?.bar)
  expect(await ui.find({ type: 'Text', text: '1/3' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '2/2' })).toBeUndefined()
  await ui.unmount()
  const survey = await $.ui.mount({ ...BAND, props: { ...BAND.props, hasSurvey: true }, surface: 'terminal' })
  expect(await survey.find({ type: 'Text', text: '1/3' })).toBeUndefined()
  await survey.unmount()
})

test('the band adds nothing when no plan is unfinished', async ($, on) => {
  engineDraws(on)
  fakeEngine(on, {
    [`${SPECS}/2026-b-design.md`]: FILES[`${SPECS}/2026-b-design.md`]!,
    'D:/p/docs/grill-form/plans/2026-b.md': FILES['D:/p/docs/grill-form/plans/2026-b.md']!,
  })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^engine$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /\d\/\d/ })).toBeUndefined()
  await ui.unmount()
})

test('editing a plan refreshes the bar, and so does opening the progress tab', async ($, on) => {
  engineDraws(on)
  const files = fakeEngine(on, { ...FILES })
  await start($)
  files['D:/p/docs/grill-form/plans/2026-a.md'] = { text: plan('未対応', 'x', 'x', ' '), mtime: 40 }
  await $.classic.PostToolUse(edited('D:/p/docs/grill-form/plans/2026-a.md'))
  const band = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: '2/3' })).toBeDefined()
  await band.unmount()
  files['D:/p/docs/grill-form/plans/2026-a.md'] = { text: plan('未対応', 'x', 'x', 'x'), mtime: 50 }
  const ui = await openTab($)
  expect((await texts(ui)).join('|')).toContain('3/3')
  await ui.unmount()
})

test('session start still completes when the store cannot be read', async ($, on) => {
  fakeEngine(on, { ...FILES }, false)
  const started = await start($)
  expect(started.cwd).toBe('D:/p')
})

test('a plan path outside the cwd is ignored', async ($, on) => {
  fakeEngine(on, {
    [`${SPECS}/2026-x-design.md`]: { text: spec('未対応', '../../outside.md') },
    'D:/outside.md': { text: plan('未対応', ' ') },
  })
  await start($)
  const ui = await openTab($)
  const all = (await texts(ui)).join('|')
  expect(all).toContain('2026-x-design.md')
  expect(all).not.toContain('0/1')
  await ui.unmount()
})

test('with no specs folder the progress tab says there is nothing', async ($, on) => {
  fakeEngine(on, {})
  await start($)
  const ui = await openTab($)
  expect(await ui.find({ type: 'Text', text: 'なし' })).toBeDefined()
  await ui.unmount()
})
