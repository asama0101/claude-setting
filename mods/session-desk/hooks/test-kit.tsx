// テストの共通部品。テストの `on` に、エンジンの代わりの受け皿を付ける。

export const ESC = String.fromCharCode(27)

export const task = (id: string) => ({ task_id: id, task_subject: id })

// 何も描かないときに、エンジンが描くもの（プラグインの下の受け皿）。
export const engineDraws = (on: any) =>
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine</Text>
  })

// 入力欄の上のバンド（AbovePrompt）を mount するときの引数。
export const BAND = {
  plugin: 'session-desk',
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 6,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 6 },
    view: {},
  },
} as const
