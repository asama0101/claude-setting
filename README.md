# claude-setting

Claude Code の個人設定（`~\.claude`）を、フォルダのコピーだけで取り込めるようにしたバックアップ。
Claude Code を Windows で使う人が、作業ルールと git 操作の確認を一式で試せる。

## 機能

- 作業の進め方を、規則（`CLAUDE.md`、`rules/`、`reference/`）で決める。Claude Code が、危ない操作の前に確認する。
- 未コミット変更の破棄やファイルの削除など、修復できない破壊的コマンド（`git reset --hard`・`git clean`・`rm -rf` など）の前に、確認を必ず出す。auto mode（許可の確認を自動で判断するモード）でも出る。
- Git/GitHub のフロー（作業ブランチ → コミット → push → PR → squash マージ（ユーザーが行う）→ タグ・リリース）を、hook（セッションの開始・ツールの実行・応答の終了の節目で自動実行されるコマンド）が知らせ、守らせる。フローの詳細は [reference/git-flow.md](reference/git-flow.md) にある。別の作業をしていても気づけるよう、許可の確認・選択肢の質問・質問や依頼で終わる応答のときに、Windows のトースト通知（画面の隅に出る通知）を出す（作業が終わっただけの応答では出ない）。
- コードの変更を最小にするスキル `ponytail`（`skills/`）が使える。

## 前提条件

- Windows 11（動作確認は Windows 11）。
- Python Launcher（`py` コマンド）。確認: `py --version`（動作確認した版は 3.14.3）。
- Git。確認: `git --version`（動作確認した版は 2.52）。
- GitHub CLI（`gh` コマンド）。GitHub 上のリポジトリで PR とリリースの工程を使うときに要る。確認: `gh --version`（動作確認した版は 2.98.0）。
- PowerShell 5.1 以降。導入の手順は、PowerShell で実行する。確認: `$PSVersionTable.PSVersion`（動作確認した版は 5.1）。hook のコマンドは、Git Bash でも PowerShell でも動く。
- トースト通知を見るには、Windows の設定で PowerShell の通知をオンにし、集中モード（通知を止める設定）をオフにする。
- Claude Code。確認: `claude --version`（動作確認した版は 2.1.316）。

## 導入方法

### 始める前の注意（ファイルを上書きします）

- 手順 2 のコピーは、同名のファイルを上書きする。手順 1 のバックアップを取らずに進めると、上書きされた内容は戻せない。
- すでに自分の `settings.json` がある場合は、手順 2 でコピーせず、必要な項目だけを手で取り込む。
- `CLAUDE.md` は、作者個人の作業ルールである。コピーすると、すべてのプロジェクトで Claude Code の動きが変わる。
- `rules/` の 3 件は、すべてのプロジェクトの `README.md` と Python ファイルに効く。自分の `rules/` に同種の規則があると、矛盾する。
- `settings.json` は、作者個人の設定を含む。コピーする前に、「設定」の表を確認する。
- 公式プラグイン（Claude Code に機能を足す部品）5 件は、`settings.json` の `enabledPlugins` に有効化だけを書いてある。各自の環境でインストールが必要になる場合がある。

### 手順

1. コピーで上書きされる項目を、日時付きのフォルダにバックアップする。

   ```powershell
   $bak = "$HOME\.claude-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
   New-Item -ItemType Directory -Force $bak | Out-Null
   foreach ($f in 'CLAUDE.md','settings.json','hooks','reference','rules','skills') {
     if (Test-Path "$HOME\.claude\$f") { Copy-Item "$HOME\.claude\$f" $bak -Recurse }
   }
   ```

2. このリポジトリのフォルダで、中身を `~\.claude` にコピーする。

   ```powershell
   New-Item -ItemType Directory -Force "$HOME\.claude" | Out-Null
   Copy-Item settings.json,hooks,reference,rules,skills "$HOME\.claude\" -Recurse -Force
   Copy-Item global-CLAUDE.md "$HOME\.claude\CLAUDE.md" -Force
   ```

3. Claude Code を再起動する。

### 元に戻す・アンインストール

Claude Code を終了してから実行する。最初に作った退避フォルダから、元の状態に戻す。退避になかった項目は、削除する。導入後に、これらの項目へ足したファイルは消える。退避フォルダがないときは、何も消さずに止まる。

```powershell
$bak = (Get-ChildItem $HOME -Directory -Filter '.claude-backup-*' | Sort-Object Name | Select-Object -First 1).FullName
if (-not $bak) { throw '退避フォルダがありません。何も変更していません。' }
foreach ($f in 'CLAUDE.md','settings.json','hooks','reference','rules','skills') {
  if (Test-Path "$HOME\.claude\$f") { Remove-Item "$HOME\.claude\$f" -Recurse -Force }
  if (Test-Path "$bak\$f") { Copy-Item "$bak\$f" "$HOME\.claude\" -Recurse }
}
```

### 更新

このリポジトリを最新にしてから、手順 1 と手順 2 をもう一度実行する。手順 1 は、新しい日時のフォルダを作る。

旧版（規則の文書を `docs\` に置いていた版）から更新するときは、手順 2 のあとに、`~\.claude\docs\git-flow.md` と `~\.claude\docs\plugin-rules.md` を手で削除する。規則の文書は `~\.claude\reference\` に移り、旧 `docs\` の 2 件は参照されなくなる。

## 使い方

導入の成果を、次の操作で確認する。

1. コピーした `settings.json` が読めることを確認する。

   ```powershell
   py -c "import json,os;json.load(open(os.path.expanduser('~/.claude/settings.json'),encoding='utf-8'));print('OK')"
   ```

   期待される出力:

   ```text
   OK
   ```

## 設定

`settings.json` の次の項目は、作者個人の好みや運用に合わせてある。自分の環境に合わせて変更する。表にない項目（`autoMode`、`env`、`effortLevel`、`inputNeededNotifEnabled`、`agentPushNotifEnabled`）も、作者個人の設定である。

| 項目 | 値 | 内容 |
|---|---|---|
| `permissions.defaultMode` | `auto` | auto mode で起動する。 |
| `skipAutoPermissionPrompt` | `true` | auto mode の確認画面を出さない。 |
| `permissions.disableBypassPermissionsMode` | `disable` | 権限確認を省略するモードを使えなくする。 |
| `permissions.allow` | 16 件 | 確認なしで実行するコマンド。 |
| `permissions.deny` | 68 件 | 読み書きを禁じるパスと、禁じるコマンド。 |
| `permissions.ask` | 11 件 | 確認を必ず出すコマンド。 |
| `attribution.sessionUrl` | `false` | コミットと PR に、セッションのリンクを付けない。 |
| `remoteControlAtStartup` | `true` | 起動時に Remote Control を有効にする。 |
| `model` | `sonnet` | 既定のモデル。 |
| `language` | `japanese` | 応答の言語。 |
| `theme` | `dark` | 配色。 |
| `tui` | `fullscreen` | 画面の表示方式。 |

- `permissions.allow` と `permissions.deny` の中身は、`settings.json` で確認する。`deny` は、`.env`・`.ssh`・認証情報のファイルを守る。プロジェクトの `.env.example` や `.npmrc` の編集も、拒否される。
- `permissions.ask` は、修復できない破壊的コマンドの 11 件である: `git reset --hard`・`git clean`・`git checkout --`・`git restore`・`git checkout .`・`rm -r`・`rm -rf`・`rm -fr`・`git switch --discard-changes`・`git switch -f`・`git switch --force`。`git push`・`git tag`・`gh release create`・`git commit`・`gh pr create` は、修復できるので、確認の対象外である（`main` 上のコミットと、強制 push は Hook が拒否する）。`gh pr merge` は、確認ではなく、Hook が常に拒否する（マージはユーザーが行う）。auto mode でも確認が出る。
- `env` の `CLAUDE_CODE_USE_POWERSHELL_TOOL` を `0` にして、PowerShell ツール（PowerShell でコマンドを実行する Claude Code のツール）を無効にしている。hook と `permissions.ask` は Bash ツールだけを対象にするので、PowerShell ツールが有効だと、これらを通らずに `git reset --hard` などが実行される。Git Bash がある Windows では、`permissions.deny` に Bash のルール（`Bash(sudo *)`）があるだけでも PowerShell ツールは無効になるが、ルールを変えると有効に戻るので、明示的に無効にしてある。
- `git restore --staged` にも確認が出る。`git checkout .` は完全一致なので、`git checkout ./dir` や `git checkout HEAD -- f` は対象外である。
- `attribution.sessionUrl` を `false` にしても、`Co-Authored-By`（コミットに付く共著者の行）と PR の定型文は、既定のまま付く。
- `remoteControlAtStartup` が `true` だと、Remote Control（ほかの端末から、実行中のセッションを見たり操作したりする機能）が有効になる。不要なら `false` にする。

### 用語

- auto mode: 危険な操作かを分類器が確かめ、問題がなければ確認なしで実行する Claude Code のモード。許可の確認が減る。
- Remote Control: ほかの端末から、実行中のセッションを見たり操作したりする機能。

## 困ったとき

### 「用語 'py' は、コマンドレット、関数、スクリプト ファイル、または操作可能なプログラムの名前として認識されません。」

Python Launcher が入っていない。Python の公式インストーラーで入れ、`py --version` が動くことを確認する。

### 「can't open file '…\.claude\hooks\….py': [Errno 2] No such file or directory」

hook のスクリプトが見つからない。次の 2 点を確認する。

- `Test-Path "$HOME\.claude\hooks\git_flow.py"` が `True` になること。`False` なら、手順 2 をやり直す。
- Git Bash で `echo $HOME` を実行し、`/c/Users/<ユーザー名>` の形になっていること。環境変数 `HOME` を別の場所に変えていると、`~\.claude` を指さなくなる。

## ライセンス

`skills/ponytail*` は第三者の作品で、MIT ライセンスである。上流は <https://github.com/DietrichGebert/ponytail>。著作権表示とライセンス全文は [skills/NOTICE](skills/NOTICE) にある。
