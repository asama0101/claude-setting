# 開発者向け

このリポジトリを更新して公開する人向けの情報。使い方は [README.md](../README.md) を見る。

## 設計判断

- リポジトリ直下を `~\.claude` と同じ構成にした。フォルダの中身をコピーするだけで使えるようにするため。
- 実機の `CLAUDE.md` だけは、`global-CLAUDE.md` の名前で保存する。`CLAUDE.md` という名前のファイルは、Claude Code がプロジェクトの指示として自動で読み込む。このリポジトリで作業すると、グローバルの規則が二重に読み込まれるため。リポジトリ内に、`CLAUDE.md` という名前のファイルを置かない。
- 利用者向けの説明は `README.md`、更新者向けの説明はこのファイルに書く。
- README と Python の規則（`rules/`）は、Claude Code 公式のパス限定ルールにした。`paths` で指定したファイルを扱うときに自動で読み込まれる。対象は `readme-rules.md` が `**/README.md`、`python-style.md` が `**/*.py`、`python-testing.md` が `**/test_*.py` と `**/tests/**/*.py` である。
- `docs/plugin-rules.md` は `rules/` に移していない。対象ファイルを 1 つのパターンで言い切れず、318 行あり、パス指定なしにすると毎回読み込まれるため。`CLAUDE.md` の「リファレンス」から読ませる。
- `CLAUDE.md` の「リファレンス」には、`rules/` の 3 件を載せていない。読ませる指示と自動読み込みで、同じ規則が二重に文脈へ入るため。
- 存在しないファイルを新規作成するときは、規則が書き込みと同時に読み込まれ、書く内容の決定に間に合わない可能性がある（未確認）。問題が出たら、`CLAUDE.md` の「リファレンス」に規則を戻す。

## 構成

| このリポジトリ | `~\.claude` 側 | 備考 |
|---|---|---|
| `global-CLAUDE.md` | `CLAUDE.md` | 名前を変えて保存（上記の設計判断を参照） |
| `settings.json` | `settings.json` | 公開用に加工済み（下記） |
| `statusline.py` | `statusline.py` | |
| `hooks/` | `hooks\` | `__pycache__` は含めない |
| `docs/` | `docs\` | `plugin-rules.md` と、このファイル（`development.md`） |
| `rules/` | `rules\` | パス限定ルール 3 件（`paths` の frontmatter 付き） |
| `skills/ponytail*`、`skills/NOTICE` | `skills\` | `NOTICE` は上流の MIT ライセンス全文 |

## 取り込まないもの

- 認証情報
- 会話履歴・実行時の状態
- 個人の作業記録
- アカウント ID を含む同期キャッシュ（`skills/synced/`）

## 公開用の加工（実機から再取り込みするたびに適用する）

- hook と statusLine のコマンドは `py "$HOME/.claude/..."` の形にする。Git Bash と PowerShell の両方で `$HOME` が展開される。絶対パスを書かない。
- `settings.json` の `autoMode` から、実機のパスとリポジトリの状態を除く。
- `settings.json` の `extraKnownMarketplaces` と、そのマーケットプレイス由来のプラグインを除く。
- `docs/` と `rules/` のパスは `~\.claude\...` と書く。
- ユーザー名・メールアドレス・GitHub アカウント名を書かない。

## 公開前の検査

3 つとも通ること。自分のメールアドレスと GitHub アカウント名は、1 つ目に `|` で足して検査する。

```bash
grep -rniE "$USERNAME|C:[/\\]+Users[/\\]+[a-z]" .                        # 出力なし
grep -rnE "(sk-|ghp_|xox[bp]-|AKI[A])[A-Za-z0-9_-]{8,}|-----BEG[I]N" .   # 出力なし
py -m json.tool settings.json > /dev/null && echo OK                    # OK
```

push・公開は、作者の確認を取ってから行う。
