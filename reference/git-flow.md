# Git/GitHub の基本フロー

Hook（`hooks/git_flow.py`）が守らせる GitHub Flow の規則。Git 管理外のフォルダでは、Hook は何もしない。

## 基本フロー

1. main の最新を取り込み、作業ブランチを切る。
2. ファイルを作成・削除・編集する。
3. Conventional Commits の形式でコミットする（type は英語、説明は日本語）。
4. push する。
5. PR を作る。タイトルも Conventional Commits の形式にする。
6. レビューを受ける。
7. ユーザーが `--squash` で main にマージする（1 PR = 1 コミット）。Claude はマージしない。
8. ユーザーが求めたとき、Claude がタグ（`vMAJOR.MINOR.PATCH`）を打ち、GitHub Release を作る。

## ブランチ名

`<type>/<短い名前>` の形にする。type は次の4つ。

- `feat/`: 機能の追加
- `fix/`: 不具合の修正
- `docs/`: 文書だけの変更
- `chore/`: 設定・保守の変更

## バージョン表記の定義

バージョンはタグだけで持つ。VERSION ファイルは置かない。

| 項目 | 定義 |
|---|---|
| 書式 | `v` + `MAJOR.MINOR.PATCH`。先頭に0を付けない。例: `v1.2.3`。 |
| プレリリース | 作らない。 |
| 最初の版 | タグがなければ `v0.1.0` を提案する。 |
| 版を決める材料 | 前のタグから既定ブランチまでのコミット件名。最大の種類で決める。type のないコミットは数えない。 |
| `feat` | MINOR を上げ、PATCH を0にする。 |
| `fix`・`perf`・`refactor` | PATCH を上げる。 |
| `docs`・`chore`・`test`・`ci`・`style`・`build` だけ | 版を上げない。`skip` を提案し、リリースを作らない。 |
| 破壊的変更（`!` または `BREAKING CHANGE:`） | 1.0.0 以上では MAJOR を上げ、他を0にする。 |
| 0.y.z の間 | 破壊的変更も MINOR を上げる。1.0.0 にするのは、ユーザーが明示したときだけ。 |
| 検査 | `git tag` のタグ名が、下の正規表現に合わなければ拒否する。 |

```text
^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$
```

## 各段階を Hook がどう扱うか

「既定ブランチ」は、`origin/HEAD` が指すブランチ。なければ `main`、`master` の順。
PR の工程（段階4の push 待ち、5、7）は、`origin` が `github.com` のときだけ動く。

| 段階 | 扱い | 内容 |
|---|---|---|
| 1 ブランチを切る | 強制（deny）＋確認 | 既定ブランチ上の編集・削除・commit・merge・push を拒否する。「切らない」を選んだセッションは外れる。 |
| 2 編集 | 促し | 編集の記録を残す。 |
| 3 コミット | 促し（block） | コミットを促す。メッセージの形式は検査しない。 |
| 4 push | 促し（block）＋強制（deny） | push を促す。force push と既定ブランチへの push は拒否する。 |
| 5 PR 作成 | 促し（block） | PR 作成を促す。タイトルの形式は検査しない。 |
| 6 レビュー | 助言のみ | Hook では扱わない。 |
| 7 マージ | 強制（deny） | `gh pr merge` を常に拒否する。マージはユーザーが行う。 |
| 8 タグとリリース | 助言のみ | Hook では扱わない。セッション開始時に、未リリースのコミットがあれば、提案する版を知らせる。 |

## ブランチを切らないとき

「切らない」を選ぶと、Claude が `git_flow.py allow-main <セッション ID>` を実行する。そのセッションの間だけ、ブランチ確認と、既定ブランチへの commit・push の拒否が外れる。
force push は外れない。

## リリースするとき

ユーザーが PR をマージしたあと、リリースを求められたときに行う。

1. `gh pr view --json state` で state が MERGED であることを確認する。MERGED でなければ、止めてユーザーに報告する。
2. AskUserQuestion でユーザーに「リリースする（提案する版）／しない」を聞く。
3. 「する」なら、次を実行する。
   - `git fetch origin`
   - `git tag <版> origin/<既定ブランチ>`
   - `git push origin <版>`
   - `gh release create <版> --generate-notes`
