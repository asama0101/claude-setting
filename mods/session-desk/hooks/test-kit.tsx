// テストの共通部品。

export const ESC = String.fromCharCode(27)

type Node = { type?: string; props?: { key?: string }; children?: unknown[] }

// 描画された木から、Text の中身（文字列の子）を、描かれた順に集める。ボタンの label は含まない。
export function textsOf(tree: unknown): string[] {
  const node = tree as Node
  const found: string[] = []
  for (const child of node.children ?? []) {
    if (typeof child === 'string') {
      if (node.type === 'Text') {
        found.push(child)
      }
    } else if (typeof child === 'object' && child !== null) {
      found.push(...textsOf(child))
    }
  }

  return found
}

// 描画された木から、key を持つ要素の親（Box）を返す。ボタンが同じ行にあるかを調べるために使う。
export function parentOf(tree: unknown, key: string): Node | undefined {
  const node = tree as Node
  for (const child of node.children ?? []) {
    if (typeof child === 'object' && child !== null) {
      if ((child as Node).props?.key === key) {
        return node
      }
      const found = parentOf(child, key)
      if (found !== undefined) {
        return found
      }
    }
  }

  return undefined
}
