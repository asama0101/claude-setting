# permissions の棚卸（2026-11-03）

`settings.json` の `permissions`（A-1〜A-3 の反映後: allow 16・ask 11・deny 68）を、5 観点で点検した所見と提案。反映は、ユーザーの承認後に行う。方針は、「permissions で防ぐのは、秘密情報の閲覧・編集と、修復できない破壊的コマンドだけ」である。

出典: [Configure permissions](https://code.claude.com/docs/en/permissions)（2026-11-03 に確認）。

## 所見

| 観点 | 所見 |
| --- | --- |
| 1. 過剰な allow | `grep *`・`cat *`・`head *`・`tail *` は、読み取りだけである。`py -m pytest *` はテストコードを実行するため、信頼できるリポジトリに限る。`git commit *`・`git switch *` は、`--amend` などの変種を含むが、reflog で戻せる。未コミット変更を捨てる `git switch` の変種は、ask で止める |
| 2. deny の漏れ | 下の提案 1。`Read(**/.git/config)` は、`git config --list` などの Bash コマンドを止めない |
| 3. ask の妥当性 | 修復できない操作のうち、ask にないものがある。下の提案 2 |
| 4. 重複と矛盾 | `Read(**/credentials*)` は、既存の `Read(**/.aws/credentials)` と `Read(**/.claude/.credentials.json)` を含む（害はない）。`Read(**/credentials*)` は、`credentials.md` のような普通の文書も止める。ask が allow より優先されることは、公式ドキュメントに書かれている（deny → ask → allow の順で、最初に合ったものが決める） |
| 5. 2 ファイルの一致 | リポジトリの `settings.json` と `~\.claude\settings.json` は、`permissions` の allow・ask・deny と `hooks` が一致している。差があるのは、`autoMode`・`enabledPlugins`・`extraKnownMarketplaces` |

## 提案

| 番号 | 対象ルール | 変更案 | 理由 |
| --- | --- | --- | --- |
| 1 | deny | `Read` と `Edit` に、`**/.config/gh/**`・`**/.gnupg/**`・`**/*.tfstate`・`**/*.tfvars`・`**/.pgpass` を足す | GitHub のトークン、GPG の鍵、Terraform の状態と変数、PostgreSQL のパスワードを含みうる |
| 2 | ask | `Bash(git branch -D *)`・`Bash(git stash drop *)`・`Bash(git stash clear)` を足す | 参照されなくなったコミットや、保存した変更を失う。reflog で戻せないものがある |
| 3 | deny | `Read(**/credentials*)` を、`Read(**/credentials)`・`Read(**/credentials.json)` に絞る | 普通の文書を止めない |
| 4 | deny | `Edit(**/.git/config)` を足す | リモートの URL や認証の設定の書き換えを防ぐ（Read の deny はあるが Edit はない） |

## 確認できなかったこと

- `grep *` の allow が、Read の deny を迂回するか。公式ドキュメントが挙げる、deny の対象の Bash コマンドは、`cat`・`head`・`tail`・`sed`・`tee` と、リダイレクト（`>`・`<`）である。`grep` は挙げられていない（未検証）。
- auto mode で、ask がどう扱われるか（未検証）。
