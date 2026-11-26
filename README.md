# claude-setting

Claude Code の個人設定（`$HOME\.claude`）を、フォルダのコピーで取り込むための一式。Windows で Claude Code を使い、作業ルールと Git 操作の確認を最初から効かせたい人向け。このリポジトリ自体のライセンスは未設定なので、再配布や改変の可否は、作者に確認する。

```powershell
git clone https://github.com/asama0101/claude-setting.git
cd claude-setting
```

このあと、「導入方法」の手順 1（バックアップ）と手順 2（コピー）を、順に実行する。手順 2 は `$HOME\.claude` の同名の項目を上書きするので、バックアップを取る前に実行すると、元の設定に戻せなくなる。

## 機能

| できること | 内容 |
|---|---|
| 作業ルール | 進め方を、`CLAUDE.md`・`rules/`（4 件）・`reference/`（5 件）で決める。 |
| 破壊的コマンドの確認 | `git reset --hard`・`git clean`・`rm -rf` など、元に戻しにくい 11 件のコマンドの前に、確認を出す。 |
| Git/GitHub のフロー | hook が、作業ブランチ → コミット → push → PR → ユーザーが squash マージ → タグ・リリースの順を守らせる。 |
| トースト通知 | 許可の確認・選択肢の質問・質問や依頼で終わる応答のときに、Windows のトースト通知を出す。 |
| スキル `ponytail` | コードの変更を最小にするスキル 6 件（`skills/`）。 |

hook は、セッションの開始・ツールの実行・応答の終了で自動実行されるコマンドである。フローの詳細は [reference/git-flow.md](reference/git-flow.md) にある。トースト通知は、画面の隅に出る通知で、作業が終わっただけの応答では出ない。確認の対象は、下の「設定」に挙げた 11 件だけである。

`hooks/readme_guard.py`（README の更新を促す hook）は同梱されるが、`settings.json` には登録していないので、既定では動かない。

## 導入方法

次のものが要る。確認のコマンドと、動作を確かめた版を並べる。

| 必要なもの | 確認のコマンド | 動作を確かめた版 |
|---|---|---|
| Windows 11 | なし | Windows 11 Pro |
| Claude Code | `claude --version` | 2.1.328 |
| Git for Windows | `git --version` | 2.52.0 |
| Python（hook 用。`py`・`python3`・`python` のどれか） | `py --version` | 3.14.3 |
| PowerShell（導入の手順を実行する） | `$PSVersionTable.PSVersion` | 5.1 |
| GitHub CLI（PR とリリースの工程で使う） | `gh --version` | 2.98.0 |

トースト通知を見るには、Windows の設定で PowerShell の通知をオンにし、集中モード（通知を止める設定）をオフにする。

### 始める前の注意（ファイルを上書きします）

- 手順 2 は、`$HOME\.claude` の同名の項目を上書きする。手順 1 のバックアップを取らないと、元に戻せない。
- すでに自分の `settings.json` があるなら、手順 2 でコピーせず、必要な項目だけを手で取り込む。
- `global-CLAUDE.md` は、作者個人の作業ルールである。`CLAUDE.md` としてコピーすると、すべてのプロジェクトで Claude Code の動きが変わる。
- `rules/` の 4 件は、すべてのプロジェクトの `README.md` と Python ファイルに効く。自分の `rules/` に同種の規則があると、矛盾する。
- `settings.json` の `enabledPlugins` は、公式ディレクトリのプラグイン 4 件（`frontend-design`・`superpowers`・`claude-md-management`・`pr-review-toolkit`）を有効にする。プラグインは hook を持てるので、使わないものは、コピー後に `enabledPlugins` から消す。

### 手順

1. 上書きされる項目を、日時付きのフォルダにバックアップする。

   ```powershell
   $bak = "$HOME\.claude-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
   New-Item -ItemType Directory -Force $bak | Out-Null
   foreach ($f in 'CLAUDE.md','settings.json','hooks','reference','rules','skills') {
     if (Test-Path "$HOME\.claude\$f") { Copy-Item "$HOME\.claude\$f" $bak -Recurse }
   }
   Get-ChildItem $bak
   ```

   最後の `Get-ChildItem` で、`$HOME\.claude` にもともとあった項目が、すべて `$bak` にあることを確かめる。欠けているときは、手順 2 に進まない。バックアップは、導入の前に取ったものでなければならない。導入のあとに取ると、戻したときに導入後の状態になる。

2. このリポジトリのフォルダで、中身を `$HOME\.claude` にコピーする。

   ```powershell
   New-Item -ItemType Directory -Force "$HOME\.claude" | Out-Null
   Copy-Item settings.json,hooks,reference,rules,skills "$HOME\.claude\" -Recurse -Force
   Copy-Item global-CLAUDE.md "$HOME\.claude\CLAUDE.md" -Force
   ```

3. Claude Code を再起動する。次の 1 行で、コピーした `settings.json` が JSON として読めることを確かめる。期待される出力は `OK` である。動作の確認は、「使い方」の基本例で行う。

   ```powershell
   py -c "import json,os;json.load(open(os.path.expanduser('~/.claude/settings.json'),encoding='utf-8'));print('OK')"
   ```

### 元に戻す・アンインストール

Claude Code を終了してから実行する。手順 1 の最初のバックアップから、6 項目を元に戻す。バックアップになかった項目は削除する。導入後にこれらの項目へ足したファイルと、導入後に変えた `settings.json`・`CLAUDE.md` の内容も消える。残したい変更は、実行の前に別の場所へ写す。バックアップがなければ、何も消さずに止まる。`$HOME\.claude\plugins\` に入ったマーケットプレイスとプラグインは戻らない。`/plugin` で個別に外す。

```powershell
$bak = (Get-ChildItem $HOME -Directory -Filter '.claude-backup-*' | Sort-Object Name | Select-Object -First 1).FullName
if (-not $bak) { throw 'バックアップがありません。何も変更していません。' }
foreach ($f in 'CLAUDE.md','settings.json','hooks','reference','rules','skills') {
  if (Test-Path "$HOME\.claude\$f") { Remove-Item "$HOME\.claude\$f" -Recurse -Force }
  if (Test-Path "$bak\$f") { Copy-Item "$bak\$f" "$HOME\.claude\" -Recurse }
}
```

### 更新

リポジトリを最新にして（`git pull`）、手順 1 と 2 をもう一度実行する。手順 1 は、新しい日時のフォルダを作る。手順 2 は上書きコピーなので、新しい版で削除・改名されたファイルは、`$HOME\.claude` に残る。必要なら手で削除する。規則の文書を `docs\` に置いていた旧版から更新するときは、手順 2 のあとに `$HOME\.claude\docs\git-flow.md` と `$HOME\.claude\docs\plugin-rules.md` を手で削除する。

## 使い方

導入すると、git 管理下のフォルダで、次の動きが加わる。基本の例は、既定ブランチ（`main`）上でのファイル編集である。

1. Claude Code を、`main` ブランチで、コミットが 1 件以上ある git リポジトリで起動する（コミットがないリポジトリでは、hook が働かない）。
2. Claude にファイルを作らせる。
3. hook が編集を止め、ブランチを切るかを、ユーザーに聞くよう Claude に指示する。出力（要約）:

   ```text
   現在 main（既定ブランチ）です。ファイルの作成・削除・編集の前に、ブランチを切るか確認します。
   ```

4. 「ブランチを切る」を選ぶと、Claude が `feat/…`・`fix/…`・`docs/…`・`chore/…` のブランチを作って、編集をやり直す。「切らない」を選ぶと、そのセッションの間だけ、確認と、既定ブランチへの commit・push の拒否が外れる。

`gh pr merge` は、どこで実行しても hook が拒否する。マージはユーザーが行う（PR の画面、または `! gh pr merge <番号> --squash`）。force push と、既定ブランチへの push も拒否する。

## 設定

次の項目は、作者個人の好みや運用に合わせてある。自分の環境に合わせて変更する。

| 項目 | 値 | 内容 |
|---|---|---|
| `permissions.defaultMode` | `auto` | auto mode で起動する。 |
| `skipAutoPermissionPrompt` | `true` | auto mode の確認画面を出さない。 |
| `permissions.disableBypassPermissionsMode` | `disable` | 権限確認を省略するモードを使えなくする。 |
| `permissions.allow` | 14 件 | 確認なしで実行するコマンド（読み取り系の `git`・`ls`・`cat` など、`git add`・`git switch`・`git commit`）。 |
| `permissions.deny` | 50 件 | 読み書きを禁じるパスと、禁じるコマンド（`sudo`）。 |
| `permissions.ask` | 11 件 | 確認を出すコマンド。 |
| `attribution.sessionUrl` | `false` | コミットと PR に、セッションのリンクを付けない。 |
| `remoteControlAtStartup` | `false` | 起動時に Remote Control（ほかの端末から、実行中のセッションを見たり操作したりする機能）を有効にしない。`true` にすると、起動のたびに有効になる。 |
| `model` | `sonnet` | 既定のモデル。 |
| `language` | `japanese` | 応答の言語。 |
| `theme` | `dark` | 配色。 |
| `tui` | `fullscreen` | 画面の表示方式。 |

表にない `autoMode`・`env`・`effortLevel`・`skipWorkflowUsageWarning`・`inputNeededNotifEnabled`・`agentPushNotifEnabled` も、作者個人の設定である。

- `deny` は、`.env`・`.ssh`・認証情報の鍵ファイルの読み書きを、Claude Code の読み書きのツール（Read・Edit）に対して拒否する。`allow` にある `Bash(cat *)` などの経由で読めるかは、未確認である。プロジェクトの `.env.example` や `.npmrc` の編集も、拒否される。
- `defaultMode: auto` は、利用できるプランやモデルが限られる。使えない環境で、どう動くかは未確認である。`allow` の `git commit *` は、確認なしでコミットする。
- `ask` の 11 件は、`git reset --hard`・`git clean`・`git checkout --`・`git restore`・`git checkout .`・`rm -r`・`rm -rf`・`rm -fr`・`git switch --discard-changes`・`git switch -f`・`git switch --force` である。`git restore --staged` のように戻せる操作も含む。次の操作は対象外で、確認なしに実行される: `rm file`（`-r` なし）・`git checkout -f`・`git branch -D`・`git stash drop`・`find -delete`・`git push`・`git commit`・`gh pr create`。`git checkout .` は完全一致なので、`git checkout ./dir` も対象外である。
- `env` の `CLAUDE_CODE_USE_POWERSHELL_TOOL` は `0` で、PowerShell ツールを無効にする。有効にすると、hook と `ask` を通らずに `git reset --hard` などが実行される。
- `attribution.sessionUrl` を `false` にしても、`Co-Authored-By` の行と PR の定型文は、既定のまま付く。

## 困ったとき

### `main` で編集しても、ブランチの確認が出ない

hook が動いていない。Python が見つからないか、hook のスクリプトが見つからないと、hook は何も出さずに終わり、ガードが無効になる。次を確認する。

- PowerShell で `py --version` を実行する。「用語 'py' は、コマンドレット、…として認識されません。」と出たら、Python Launcher（`py` コマンド）が入っていない。Python の公式インストーラーで入れる。hook は、`py` がなければ `python3`、`python` の順に試す。
- コミットがない git リポジトリでは、hook は働かない。

### hook のスクリプトが見つからない

次の 2 点を確認する。

- `Test-Path "$HOME\.claude\hooks\git_flow.py"` が `True` になること。`False` なら、手順 2 をやり直す。
- 環境変数 `HOME` を変えていると、hook は `$HOME\.claude` を探せない。変えていないことを確かめる。

## ライセンス

このリポジトリ自体のライセンスは、未設定である。`skills/ponytail*` は第三者の作品で、MIT ライセンスである。上流は <https://github.com/DietrichGebert/ponytail>。著作権表示とライセンス全文は [skills/NOTICE](skills/NOTICE) にある。
