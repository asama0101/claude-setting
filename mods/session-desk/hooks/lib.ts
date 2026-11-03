import type { DiffLine, DiffView } from '../types'

const CSI = /\u001b\[[0-9;?]*[ -/]*[@-~]/g
const OSC = /\u001b\][^\u0007\u001b]*(?:\u0007|\u001b\\)/g
const CONTROL = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/g

// ゼロ幅文字と双方向制御文字（U+200B〜200F、202A〜202E、2066〜2069）。見た目を偽装できるので除く。
const RANGES: readonly (readonly [number, number])[] = [
  [0x200b, 0x200f],
  [0x202a, 0x202e],
  [0x2066, 0x2069],
]
const INVISIBLE = new RegExp(`[${RANGES.map(([a, b]) => `${String.fromCharCode(a)}-${String.fromCharCode(b)}`).join('')}]`, 'g')

export function stripControl(text: string): string {
  return text.replace(OSC, '').replace(CSI, '').replace(CONTROL, '').replace(INVISIBLE, '')
}

const PREVIEW_CHARS = 60

// 一覧に出す 1 行。制御コードを除き、空白を 1 つにまとめ、60 字で切る。
export function preview(text: string): string {
  const flat = stripControl(text).replace(/\s+/g, ' ').trim()

  return flat.length <= PREVIEW_CHARS ? flat : `${flat.slice(0, PREVIEW_CHARS)}…`
}

// 定型文の初期値。保存した値が読めないときも、これに戻す。
export const DEFAULT_QUICK: readonly string[] = [
  '残りのタスクは？',
  '選択肢ごとにメリット・デメリットを明確にして推奨および影響をレポートして',
  'Artifact使ってデザインを見せて',
]

// ストアから読んだ値が、空でない文字列の配列のときだけ返す。外から来る値なので検証する。
export function parseQuick(raw: unknown): string[] | null {
  if (!Array.isArray(raw) || !raw.every(item => typeof item === 'string' && item !== '')) {
    return null
  }

  return [...raw]
}

export function addQuick(list: readonly string[], text: string): string[] {
  const clean = stripControl(text).trim()

  return clean === '' || list.includes(clean) ? [...list] : [...list, clean]
}

export function removeQuick(list: readonly string[], index: number): string[] {
  return list.filter((_, i) => i !== index)
}

export function isSecretName(path: string): boolean {
  const name = (path.split(/[/\\]/).pop() ?? '').toLowerCase()
  return (
    name.startsWith('.env') ||
    name.endsWith('.key') ||
    name.endsWith('.pem') ||
    name.endsWith('.pfx') ||
    name.startsWith('id_rsa') ||
    name === '.npmrc' ||
    name === '.git-credentials' ||
    name.startsWith('credentials') ||
    name === 'settings.local.json' ||
    name === '.netrc' ||
    name === '.pypirc' ||
    name.startsWith('id_ed25519') ||
    name.startsWith('id_ecdsa') ||
    name.endsWith('.p12') ||
    name.endsWith('.ppk') ||
    name.endsWith('.tfvars') ||
    name.endsWith('.jks') ||
    name.endsWith('.keystore') ||
    name.endsWith('.kdbx') ||
    name === '.htpasswd' ||
    name.startsWith('id_dsa') ||
    /^secrets?\./.test(name) ||
    name.startsWith('service-account')
  )
}

const BACKSLASH = String.fromCharCode(92)

function slashes(path: string): string {
  return path.split(BACKSLASH).join('/').replace(/\/+$/, '')
}

// path が cwd の中にあるか。`..` を含むパスは、中とみなさない。大文字小文字は区別しない（Windows）。
export function insideCwd(path: string, cwd: string): boolean {
  const file = slashes(path)
  const root = slashes(cwd).toLowerCase()
  if (file.split('/').includes('..')) {
    return false
  }
  const lower = file.toLowerCase()

  return lower.startsWith(`${root}/`)
}

const HEADER = /^(diff --git |index |--- |\+\+\+ |new file mode |deleted file mode |old mode |new mode |similarity index |rename (from|to) )/

// git diff の出力を、行の種類つきに直す。ファイルの見出しは捨てる。max 行で切る。
export function parseDiff(text: string, max: number): DiffView {
  const lines: DiffLine[] = []
  let inHunk = false
  for (const raw of stripControl(text).split('\n')) {
    if (!inHunk && HEADER.test(raw)) {
      continue
    }
    if (raw.startsWith('@@')) {
      inHunk = true
      lines.push({ kind: 'hunk', text: raw })
    } else if (inHunk && raw.startsWith('+')) {
      lines.push({ kind: 'add', text: raw })
    } else if (inHunk && raw.startsWith('-')) {
      lines.push({ kind: 'del', text: raw })
    } else if (inHunk && raw !== '') {
      lines.push({ kind: 'ctx', text: raw })
    }
    if (raw.startsWith('diff --git ')) {
      inHunk = false
    }
  }

  return { lines: lines.slice(0, max), truncated: lines.length > max }
}

// 追跡されていない新しいファイル: 全行を追加として出す。
export function allAdded(text: string, max: number): DiffView {
  const rows = stripControl(text).split('\n')
  if (rows[rows.length - 1] === '') {
    rows.pop()
  }
  const lines = rows.map((row): DiffLine => ({ kind: 'add', text: `+${row}` }))

  return { lines: lines.slice(0, max), truncated: lines.length > max }
}
