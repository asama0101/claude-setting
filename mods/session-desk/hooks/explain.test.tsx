import { expect, test } from 'claude-code/testing'

import { buildExplainPrompt, clipTail, maskSecrets, parseExplanation } from './lib'
import { ESC } from './test-kit'

// テストの実行環境には setTimeout があるが、型の定義（DOM なし）にはない。
declare const setTimeout: (callback: (...args: any[]) => void, ms: number) => unknown

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

const QUESTIONS = [
  {
    question: 'どの方式で実装しますか？',
    header: '方式',
    multiSelect: false,
    options: [
      { label: 'A案', description: '速いが粗い' },
      { label: 'B案', description: '遅いが堅い' },
    ],
  },
]

const GOOD = {
  summary: 'ユーザーは設定の見直しを頼んでいる',
  reason: '実装方式が決まらないと次に進めない',
  options: [
    { label: 'A案', effect: '早く終わるが後で直す' },
    { label: 'B案', effect: '時間はかかるが手戻りが少ない' },
  ],
  recommend: 'B案を推奨する',
}

type Reply = unknown

// エンジンの代わりの受け皿。モデルへの依頼を prompts に残し、返答は replies を順に返す。
function fakeEngine(on: any, replies: Reply[]) {
  const prompts: string[] = []
  on('prompt.submit', (_: any, e: any) => ({ text: e.text }))
  on('tool.call', () => ({ result: { questions: [], answers: {} } }))
  on('model.complete', (_: any, e: any): any => {
    prompts.push(String(e.prompt))

    return { value: replies.length > 0 ? replies.shift() : { isAnswered: false, reason: 'api-error' } }
  })

  return { prompts }
}

const ask = ($: any, tool = 'AskUserQuestion') => $.tool.call({ tool, questions: QUESTIONS })
const answered = (value: unknown) => ({ isAnswered: true, text: typeof value === 'string' ? value : JSON.stringify(value) })
const later = () => new Promise(resolve => setTimeout(resolve, 30))
const shown = async (ui: any): Promise<string> => JSON.stringify(await ui.drawn())
const mount = ($: any) => $.ui.mount({ ...PANE, surface: 'terminal' })

test('maskSecrets masks every pattern', async () => {
  const samples = [
    'key sk-abcdefghijklmnop1234 end',
    'id AKIAABCDEFGHIJKLMNOP end',
    'tok ghp_abcdefghijklmnopqrstuv end',
    'h Bearer abc.def-ghi end',
    'p password=hunter2 end',
    'u Password: hunter2 end',
    'c postgres://user:pass@host/db end',
    'm someone@example.co end',
  ]
  const secrets = ['sk-abcdefghijklmnop1234', 'AKIAABCDEFGHIJKLMNOP', 'ghp_abcdefghijklmnopqrstuv', 'abc.def-ghi', 'hunter2', 'hunter2', 'user:pass@host', 'someone@example.co']
  samples.forEach((text, i) => {
    const out = maskSecrets(text)
    expect(out.includes(secrets[i] ?? '')).toBe(false)
    expect(out.includes('[masked]')).toBe(true)
  })
  expect(maskSecrets('普通の文章です')).toBe('普通の文章です')
  expect(maskSecrets('see risk-assessment-and-disk-encryption-setup')).toBe('see risk-assessment-and-disk-encryption-setup')
})

test('maskSecrets also masks private keys, long-form tokens and JWTs', async () => {
  const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmno'
  const samples = [
    '-----BEGIN RSA PRIVATE KEY-----' + String.fromCharCode(10) + 'MIIEabc' + String.fromCharCode(10) + '-----END RSA PRIVATE KEY-----',
    'github_pat_' + 'a'.repeat(30),
    'gho_' + 'b'.repeat(30),
    'xoxb-1234567890-abcdef',
    'AIza' + 'c'.repeat(35),
    jwt,
    'Bearer abc+def/ghi=',
  ]
  for (const sample of samples) {
    const out = maskSecrets(`x ${sample} y`)
    expect(out).toContain('[masked]')
    expect(out).not.toContain(sample.slice(-8))
  }
})

test('buildExplainPrompt tolerates a question without options or description', async () => {
  const odd: any[] = [
    { question: '数値は？', header: '数' },
    { question: 'q2', header: 'h', options: [{ label: 'A' }] },
  ]
  const text = buildExplainPrompt(odd, [])
  expect(text).toContain('数値は？')
  expect(text).toContain('A')
  expect(text).not.toContain('undefined')
})

test('clipTail keeps the tail', async () => {
  const text = 'a'.repeat(1000) + 'b'.repeat(4000)
  expect(clipTail(text, 4000)).toBe('b'.repeat(4000))
  expect(clipTail('short', 4000)).toBe('short')
})

test('parseExplanation accepts one valid object and rejects everything else', async () => {
  expect(parseExplanation(JSON.stringify(GOOD))).toEqual(GOOD)
  expect(parseExplanation('```json\n' + JSON.stringify(GOOD) + '\n```')).toEqual(GOOD)
  expect(parseExplanation('これは JSON ではない')).toBe(null)
  expect(parseExplanation(JSON.stringify([GOOD]))).toBe(null)
  expect(parseExplanation(JSON.stringify({ ...GOOD, summary: undefined }))).toBe(null)
  expect(parseExplanation(JSON.stringify({ ...GOOD, reason: 'x'.repeat(201) }))).toBe(null)
  expect(parseExplanation(JSON.stringify({ ...GOOD, options: Array.from({ length: 9 }, () => GOOD.options[0]) }))).toBe(null)
  expect(parseExplanation(JSON.stringify({ ...GOOD, options: [{ label: 'A', effect: 1 }] }))).toBe(null)
  const cleaned = parseExplanation(JSON.stringify({ ...GOOD, summary: `${ESC}[31mred${ESC}[0m` }))
  expect(cleaned?.summary).toBe('red')
})

test('buildExplainPrompt masks secrets, keeps at most 5 prompts and 4000 characters each', async () => {
  const prompts = ['p1', 'p2', 'p3', 'p4', 'p5', 'password=hunter2 ' + 'z'.repeat(5000)]
  const text = buildExplainPrompt(QUESTIONS, prompts)
  expect(text).toContain('どの方式で実装しますか？')
  expect(text).toContain('A案')
  expect(text).not.toContain('hunter2')
  expect(text).not.toContain('p1')
  expect(text).toContain('p2')
  expect(text.includes('z'.repeat(4001))).toBe(false)
  expect(text.includes('z'.repeat(3900))).toBe(true)
})

test('an AskUserQuestion call starts one haiku call and does not wait for it', async ($, on) => {
  const prompts: string[] = []
  let release: (value: unknown) => void = () => {}
  const gate = new Promise(resolve => {
    release = resolve
  })
  on('tool.call', () => ({ result: { questions: [], answers: {} } }))
  on('model.complete', async (_: any, e: any): Promise<any> => {
    prompts.push(`${e.model}:${String(e.prompt).length}`)

    return { value: await gate }
  })
  const outcome = await Promise.race([ask($).then(() => 'called'), new Promise(resolve => setTimeout(() => resolve('timeout'), 500))])
  expect(outcome).toBe('called')
  await later()
  expect(prompts.length).toBe(1)
  expect(prompts[0]?.startsWith('haiku:')).toBe(true)
  const ui = await mount($)
  expect(await shown(ui)).toContain('作成中')
  release(answered(GOOD))
  await later()
  expect(await shown(ui)).toContain('B案を推奨する')
  await ui.unmount()
})

test('the explanation tab shows the four parts when the model answers', async ($, on) => {
  fakeEngine(on, [answered(GOOD)])
  await ask($)
  await later()
  const ui = await mount($)
  const text = await shown(ui)
  expect(text).toContain(GOOD.summary)
  expect(text).toContain(GOOD.reason)
  expect(text).toContain('A案')
  expect(text).toContain('早く終わるが後で直す')
  expect(text).toContain(GOOD.recommend)
  expect(text).not.toContain('どの方式で実装しますか？')
  await ui.unmount()
})

test('a model call that throws ends in the failed note', async ($, on) => {
  on('tool.call', () => ({ result: { questions: [], answers: {} } }))
  on('model.complete', (): any => {
    throw new Error('boom')
  })
  const result = await ask($)
  expect(result.deny).toBeUndefined()
  await later()
  const ui = await mount($)
  expect(await shown(ui)).toContain('作れなかった')
  await ui.unmount()
})

test('prompts sent earlier reach the model masked', async ($, on) => {
  const { prompts } = fakeEngine(on, [answered(GOOD)])
  await ($ as any).prompt.submit({ text: 'この設定を直して password=hunter2' })
  await ask($)
  await later()
  expect(prompts[0]).toContain('この設定を直して')
  expect(prompts[0]).not.toContain('hunter2')
})

test('a failed model call or a bad reply shows a note and never blocks the question', async ($, on) => {
  fakeEngine(on, [{ isAnswered: false, reason: 'api-error' }, answered('これは JSON ではない')])
  for (let i = 0; i < 2; i++) {
    const result = await ask($)
    expect(result.deny).toBeUndefined()
    await later()
    const ui = await mount($)
    expect(await shown(ui)).toContain('作れなかった')
    await ui.unmount()
  }
})

test('other tools do not start a model call, and the 31st question does not either', async ($, on) => {
  const { prompts } = fakeEngine(on, Array.from({ length: 40 }, () => answered(GOOD)))
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  expect(prompts.length).toBe(0)
  for (let i = 0; i < 31; i++) {
    await ask($)
  }
  await later()
  expect(prompts.length).toBe(30)
  const ui = await mount($)
  expect(await shown(ui)).toContain('上限')
  await ui.unmount()
})

test('before any question the explanation tab says there is nothing', async ($, on) => {
  fakeEngine(on, [])
  const ui = await mount($)
  await ui.press({ key: 'tab-explain' })
  expect(await shown(ui)).toContain('なし')
  await ui.unmount()
})
