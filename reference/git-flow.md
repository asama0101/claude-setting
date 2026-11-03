# Git/GitHub の基本フロー

Claude Code の Hook（`hooks/git_flow.py`）が守らせる、GitHub Flow の規則。Git 管理外のフォルダでは、この Hook は何もしない。

## 基本フロー

1. main の最新を取り込み、作業ブランチを切る。
2. ファイルを作成・削除・編集する。
3. Conventional Commits の形式でコミットする（件名の type は英語、説明は日本語）。
4. push する。
5. PR を作る。PR のタイトルも Conventional Commits の形式にする。
6. レビューを受ける。
7. `gh pr merge --squash` で main にマージする（1 PR = 1 コミット）。
8. マージ後、SemVer のタグ（`vMAJOR.MINOR.PATCH`）を打ち、GitHub Release を作る。

## ブランチ名

`<type>/<短い名前>` の形にする。type は次の4つ。

- `feat/`: 機能の追加
- `fix/`: 不具合の修正
- `docs/`: 文書だけの変更
- `chore/`: 設定・保守の変更

## バージョン表記の定義

バージョンはタグだけで持つ（VERSION ファイルは置かない）。

| 項目 | 定義 |
|---|---|
| 書式 | `v` + `MAJOR.MINOR.PATCH`。各数字は10進の整数で、先頭に0を付けない。正規表現は、表の下に示す。例: `v0.1.0`、`v1.2.3`。 |
| プレリリース | 作らない。`-rc.1` などの接尾辞は使わない。 |
| 最初の版 | タグが1つもないリポジトリでは、`v0.1.0` を提案する。 |
| 版を決める材料 | 前のタグから既定ブランチまでのコミット件名（`type: 説明`）と、マージする PR のタイトル。最大の種類で決める。type のないコミットは数えない。 |
| `feat` | MINOR を上げ、PATCH を0にする。 |
| `fix`・`perf`・`refactor` | PATCH を上げる。 |
| `docs`・`chore`・`test`・`ci`・`style`・`build` だけ | 版を上げない。`skip` を提案し、リリースを作らない。 |
| 破壊的変更（type の後の `!`、または本文の `BREAKING CHANGE:`） | 1.0.0 以上では MAJOR を上げ、MINOR と PATCH を0にする。 |
| 0.y.z の間 | 破壊的変更も MINOR を上げる（PATCH を0にする）。1.0.0 にするのは、ユーザーが明示したときだけ。 |
| 検査 | `allow-merge` の版の引数と、新しいタグを作る `git tag` のタグ名が、書式の正規表現に合わなければ拒否する。 |

書式の正規表現:

```text
^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$
```

## 各段階を Hook がどう扱うか

| 段階 | 扱い | 内容 |
|---|---|---|
| 1 ブランチを切る | 強制（deny）＋確認 | 既定ブランチ上の編集・削除と、commit・merge・push を拒否する。ユーザーが「切らない」を選んだセッションは外れる。 |
| 2 編集 | 促し | 編集の記録を残す。 |
| 3 コミット | 促し（block） | コミットを促す。コミットメッセージの形式は検査しない。 |
| 4 push | 促し（block）＋強制（deny） | push を促す。force push と既定ブランチへの push は拒否する。 |
| 5 PR 作成 | 促し（block） | PR 作成を促す。PR タイトルの形式は検査しない。 |
| 6 レビュー | 助言のみ | Hook では扱わない。 |
| 7 マージ | 強制（deny） | `--squash` 以外と `--auto` を拒否し、リリースの確認が済むまで拒否する。 |
| 8 タグとリリース | 促し | マージ後に、タグと GitHub Release の作成手順を Claude に指示する。 |

## Hook が動く契機

「既定ブランチ」は、`origin/HEAD` が指すブランチ。なければ `main`、`master` の順に存在するもの。「GitHub のリモート」は、`origin` の URL に `github.com` を含むもの。PR・リリースの工程（段階4の push 待ち、5、7、8）は、GitHub のリモートのときだけ動く。

| 契機 | 動作 |
|---|---|
| セッション開始 | ブランチ、未コミットの件数、リモートとの差（ahead・behind）を出す。差は `git fetch`（5秒の制限）のあとで求める。上流ブランチがなければ、`origin/<既定ブランチ>` との差を出す。GitHub のリモートで、最新タグより新しい（版を上げる）コミットが既定ブランチにあれば、リリース未作成の1行を足す。 |
| 編集・削除の前 | 既定ブランチ上なら一度止め、Claude にユーザーへ「ブランチを切る（推奨）／切らない」を聞かせる。 |
| Bash の実行前 | 既定ブランチ上の `git commit`・`git merge`・`git push`、`--force` 系の `git push`、書式に合わないタグの作成、`gh pr merge` を検査する。既定ブランチ上の `git merge --ff-only origin/<既定ブランチ>`（ローカルをリモートに追従させる操作）は許す。同じ行で `git switch -c` などでブランチを切ったあとの操作は、新しいブランチ上として扱う。 |
| Bash の実行後 | `gh pr merge` が成功したら、タグ・push・GitHub Release の作成を Claude に指示する。 |
| 応答の終了 | 編集があったセッションで、コミット → push → PR の順に、未了の段階を Claude に促す。同じ状態では1回だけ。既定ブランチ上では、「ブランチを切らない」を選んだセッション以外は、push を促さない。 |

## ブランチを切らないとき

「切らない」を選ぶと、Claude が `git_flow.py allow-main <セッション ID>` を実行する。そのセッションの間だけ、ブランチ確認と、既定ブランチへの commit・push の拒否が外れる。force push は、外れない。

## リリースするとき

`gh pr merge` の前に、Claude がユーザーへ「リリースする（提案する版）／しない」を聞き、`git_flow.py allow-merge <セッション ID> <版 または skip>` を実行する。この記録は、1回のマージで消える。マージのあと、Claude が `git tag`、`git push origin <版>`、`gh release create <版> --generate-notes` を実行する（各コマンドは、`permissions.ask` の対象外である。既定ブランチへの push と強制 push は、Hook が拒否する）。
