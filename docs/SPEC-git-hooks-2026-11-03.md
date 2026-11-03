# SPEC: Git/GitHub フローを守らせる Hook 群

## 概要

### 目的・ゴール

Claude Code のセッション中に、GitHub Flow（作業ブランチ → コミット → push → PR → main へ squash マージ → タグとリリース）を促し、守らせる。Git 管理外のフォルダでは、Git 関連の Hook は何もしない。

### 入力

依頼文（原文の要約）: 既存の「未コミットのファイルを出す Hook」（`hooks/uncommitted_warn.py`）を改修し、次の6要望を満たす。

1. Git 環境でなければ、Hook を初期段階でスキップする。
2. セッション開始時に、未コミットのファイルの有無と、リモートリポジトリとの差分を確認する Hook を足す。
3. ファイルの作成・削除・編集の前に、ブランチを切るか確認する（既定は切る）。
4. ファイルの追加・削除・編集が終わったら、コミット・push・PR を促す。
5. リモートの main へマージするときは、バージョン管理・タグ管理・リリースノート作成を行う。
6. Git/GitHub を使った開発の基本フローを示し、その遵守を Hook で強制する。

入力ファイル（元のパス）: なし（参考資料の指定なし）。調べたもの: `hooks\uncommitted_warn.py`、`hooks\readme_guard.py`、`settings.json`、`README.md`（いずれも `D:\claude\local-repo\claude-setting`）。

### 前提と範囲

- 変更の対象は、リポジトリ `D:\claude\local-repo\claude-setting` のファイルだけ。`~\.claude` への反映は、README の導入手順（コピー）でユーザーが行う。
- 実装方式は、`settings.json` の Hooks（シェルコマンドを、SessionStart・PreToolUse・PostToolUse・Stop のイベントで実行する仕組み）。Mods（plugin の中の JavaScript を Claude Code のプロセス内で動かす仕組み）は使わない。理由は決定ログの Q23。
- 実装は Python。既存の Hook と同じく、stdin の JSON を読み、予期しない例外は握りつぶして終了コード 0 で終わる。
- 「Hook の失敗で作業を止めない」方針を守る。ただし、意図した拒否（deny）と促し（block）は、JSON の出力で返す。
- Windows 11 で動作を確認する。Linux は、環境に入れても無害であること（エラー表示が出ない）を保証範囲とし、実機での確認は未検証とする。
- Hook は `~\.claude` に置くので、Git を使うすべてのプロジェクトに効く。

### 変更するもの

| ファイル | 変更 |
|---|---|
| `hooks/git_flow.py` | 新規。サブコマンド `session-start`・`pre-tool`・`post-tool`・`stop`（Hook 用）と、`allow-main`・`allow-merge`（Claude が Bash で実行する用）を持つ。 |
| `hooks/uncommitted_warn.py` | 削除。Stop の未コミット警告は `git_flow.py stop` に統合する。 |
| `settings.json` | `SessionStart`・`PreToolUse`・`PostToolUse`・`Stop` の Hook を登録する。既存の `readme_guard.py` と新しい Hook のコマンドを、起動方法 `py … 2>/dev/null \|\| python3 … 2>/dev/null \|\| python … 2>/dev/null \|\| true` に直す。`permissions.ask` に `Bash(gh release create *)` を足す。 |
| `docs/git-flow.md` | 新規。基本フローと、Hook が守らせる規則を示す説明文書。 |
| `README.md` | 機能・設定の記述を、新しい Hook に合わせて直す（`permissions.ask` の件数 10 → 11 を含む）。 |
| `tests/test_git_flow.py` | 新規。一時フォルダに作った Git リポジトリで、各サブコマンドを検証する。 |

## 流れ

### 基本フロー（GitHub Flow）

1. main の最新を取り込み、作業ブランチを切る。名前は `feat/…`・`fix/…`・`docs/…`・`chore/…`。
2. ファイルを作成・削除・編集する。
3. Conventional Commits の形式でコミットする（件名の type は英語、説明は日本語）。
4. push する。
5. PR を作る。PR のタイトルも Conventional Commits の形式にする。
6. レビューを受ける。
7. `gh pr merge --squash` で main にマージする（1 PR = 1 コミット）。
8. マージ後、SemVer のタグ（`vMAJOR.MINOR.PATCH`）を打ち、GitHub Release を作る。

バージョンはタグだけで持つ（VERSION ファイルは置かない）。表記と上げ方は、次の「バージョン表記の定義」に従う。

### バージョン表記の定義

この節の内容は、`docs/git-flow.md` に同じ文面で載せる。

| 項目 | 定義 |
|---|---|
| 書式 | `v` + `MAJOR.MINOR.PATCH`。各数字は10進の整数で、先頭に0を付けない。正規表現は、表の下に示す。例: `v0.1.0`、`v1.2.3`。 |
| プレリリース | 作らない。`-rc.1` などの接尾辞は使わない。 |
| 最初の版 | タグが1つもないリポジトリでは、`v0.1.0` を提案する。 |
| 版を決める材料 | 前のタグから既定ブランチまでのコミット件名（`type: 説明`）。最大の種類で決める。 |
| `feat` | MINOR を上げ、PATCH を0にする。 |
| `fix`・`perf`・`refactor` | PATCH を上げる。 |
| `docs`・`chore`・`test`・`ci`・`style`・`build` だけ | 版を上げない。`skip` を提案し、リリースを作らない。 |
| 破壊的変更（type の後の `!`、または本文の `BREAKING CHANGE`） | 1.0.0 以上では MAJOR を上げ、MINOR と PATCH を0にする。 |
| 0.y.z の間 | 破壊的変更も MINOR を上げる（PATCH を0にする）。1.0.0 にするのは、ユーザーが明示したときだけ。 |
| 検査 | `allow-merge` の版の引数と、新しいタグを作る `git tag` のタグ名が、書式の正規表現に合わなければ拒否する。 |

書式の正規表現:

```text
^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$
```


### Hook の動き

「既定ブランチ」は、`origin/HEAD` が指すブランチ。なければ `main`、`master` の順に存在するもの。「GitHub のリモート」は、`origin` の URL に `github.com` を含むもの。「セッションの免除」は、`allow-main <session_id>` で作る印で、そのセッションの間だけ有効。Bash で実行するコマンドには `session_id` が渡らないので、Hook の拒否理由に `session_id` を埋め込み、Claude にそのまま引数として渡させる。印は、一時フォルダの `claude-git-flow\<session_id>.json` に置く（セッションごとに1ファイル。同じセッションの Hook はイベントの順に動くので競合しない前提で、並列実行時の挙動は実機で確認する）。

| 契機 | サブコマンド | 動作 |
|---|---|---|
| すべて | （共通） | `git rev-parse --is-inside-work-tree` の出力が `true` でなければ（失敗、`false`、bare リポジトリを含む）、何も出さず終了コード 0 で終わる。判定するフォルダは、`pre-tool` の Edit・Write・NotebookEdit では対象ファイルの親フォルダ、Bash と他の契機では作業フォルダ。`readme_guard.py` は対象外。 |
| SessionStart（startup・resume） | `session-start` | 現在のブランチ、未コミットの件数、リモートとの差（ahead・behind）を、`systemMessage`（ユーザー向け）と `hookSpecificOutput.additionalContext`（Claude 向け）の両方に同じ文面で出す。書式は `ブランチ: <名前> / 未コミット: <N>件 / リモート差: ahead <A>・behind <B>`。差は `git fetch` を5秒の制限で実行してから求める。fetch が失敗・時間切れなら「取得できず。前回取得時点の差」と明記する。上流ブランチがなければ、`origin/<既定ブランチ>` との差を「上流なし」と明記して出す。リモートがなければ差の表示を省く。GitHub のリモートで、最新のタグより新しく、版を上げる種類のコミット（「バージョン表記の定義」で `skip` にならないもの）が既定ブランチにあれば、「最新タグ vX.Y.Z より N コミット新しい。リリース未作成」を1行足す（タグが1つもなければ出さない）。 |
| PreToolUse（Edit・Write・NotebookEdit・Bash） | `pre-tool` | 判定を1つのサブコマンドにまとめる（同じイベントの Hook は並列実行されうるため）。 |
| 〃 ブランチ確認（要望3） | `pre-tool` | 現在のブランチが既定ブランチで、セッションの免除がなく、対象がリポジトリ内のファイルの作成・削除・編集のとき、一度止める（deny）。理由で Claude に、AskUserQuestion でユーザーに「ブランチを切る（推奨）／切らない」を聞くよう指示する。「切る」なら `git switch -c <type>/<名前>`、「切らない」なら `git_flow.py allow-main <session_id>` を実行させる。質問できないとき（非対話実行、質問ツールがないサブエージェント）は、作業を止めてユーザーに報告させる。Bash は、`rm`・`git rm`・`mv`・`Remove-Item` を含むコマンドが対象。コミットがまだ1つもないリポジトリは対象外。 |
| 〃 フロー違反（要望6） | `pre-tool`（Bash） | ① 既定ブランチ上の `git commit`・`git merge`、既定ブランチへの `git push`（`HEAD:main` の形を含む）を、セッションの免除がなければ拒否する。理由は「ブランチを切れ」。コミットがまだ1つもないリポジトリの最初のコミットは許す。② `git push` の `--force`・`-f`・`--force-with-lease` は、常に拒否する。③ 既定ブランチ上の `git merge --ff-only origin/<既定ブランチ>`（`@{u}` を含む。ローカルをリモートに追従させる操作）は許す。④ 同じ行の前の部分で `git switch -c`・`git checkout -b` を実行していれば、その後ろの commit・merge と編集・削除は、新しいブランチ上として扱う。`cd <フォルダ>` も追い、以降はそのフォルダで判定する。`rm`・`mv` は、対象のファイルが作業ツリーの外（絶対パスなど）なら対象外。 |
| 〃 マージ前の確認（要望5） | `pre-tool`（Bash） | GitHub のリモートで `gh pr merge` を実行するとき、`--squash` がない、または `--auto` がある場合は拒否する（理由で `gh pr merge --squash`（`--auto` なし）を指示）。`allow-merge` の記録がなければ拒否する。理由で Claude に、最新タグ、タグからのコミットの件名、マージする PR のタイトル（`gh pr view` で取得できたとき）、「バージョン表記の定義」から求めた提案する版を示し、ユーザーに「リリースする（既定）／しない」を聞かせ、`git_flow.py allow-merge <session_id> <vX.Y.Z または skip>` を実行させる。記録は1回のマージで消える。 |
| 〃 タグ名の検査（要望5） | `pre-tool`（Bash）と `allow-merge` | 新しいタグを作る `git tag <名前>`（`-a`・`-s` を含み、`-l`・`-d`・`--list`・`--delete` などの一覧・削除は除く）のタグ名と、`allow-merge` の `<版>`（`skip` を除く）が、「バージョン表記の定義」の正規表現に合わなければ拒否する。GitHub のリモートでなくても検査する。 |
| PostToolUse（Edit・Write・NotebookEdit・Bash） | `post-tool` | ① リポジトリ内のファイルの編集（Edit・Write・NotebookEdit と、`pre-tool` が対象とする Bash の4コマンド）を、セッションの印に記録する。② `gh pr merge` が成功し、`allow-merge` の記録が版（`skip` でない）なら、Claude に「`git fetch` → `git tag <版> origin/<既定ブランチ>` → `git push origin <版>` → `gh release create <版> --generate-notes`」を実行するよう指示し、記録を消す。`skip` のときは、記録を消すだけ。 |
| Stop | `stop` | このセッションで編集の記録（`post-tool` の①）があったときだけ動く。状態（HEAD のコミットハッシュ、未コミットの件数、push 済みかどうか、PR の有無）が前回の促しと同じなら何もしない。前回の状態は、セッションの印に保存する。`stop_hook_active` が真なら何もしない。①未コミットがある → コミットを促す。②コミット済みで未 push（GitHub のリモート。既定ブランチ上は、セッションの免除があるときだけ）→ push を促す。③push 済みで、既定ブランチ以外にいて、PR がない（`gh pr list --head` で確認。5秒の制限）→ PR 作成を促す。`gh` がなければ③は省く。促しは block の理由として Claude に渡し、Claude がユーザーに実行するかを聞く。 |

### フローの各段階を、Hook がどう扱うか（要望6）

| 段階 | 扱い | 内容 |
|---|---|---|
| 1 ブランチを切る | 強制（deny）＋確認 | 既定ブランチ上の編集・削除と、commit・merge・push を拒否する。「切らない」を選んだセッションは外れる。 |
| 2 編集 | 促し | 編集の記録を残す。 |
| 3 コミット | 促し（block） | コミットを促す。コミットメッセージの形式は検査しない。 |
| 4 push | 促し（block）＋強制（deny） | push を促す。force push と既定ブランチへの push は拒否する。 |
| 5 PR 作成 | 促し（block） | PR 作成を促す。PR タイトルの形式は検査しない。 |
| 6 レビュー | 助言のみ | `docs/git-flow.md` に書く。Hook では扱わない。 |
| 7 マージ | 強制（deny） | `--squash` 以外と `--auto` を拒否し、リリースの確認が済むまで拒否する。 |
| 8 タグとリリース | 促し | マージ後に、タグと GitHub Release の作成手順を Claude に指示する。 |

### 計画（検証つき）

1. `tests/test_git_flow.py` に、受入条件ごとのテストを書く（先に失敗させる）→ 検証: `pytest tests/test_git_flow.py` が、実装前に失敗する。
2. `hooks/git_flow.py` を実装する → 検証: 同じテストが、すべて通る。
3. `settings.json` を直す → 検証: `py -c "import json;json.load(open('settings.json',encoding='utf-8'))"` が通る。Linux 相当の確認として、`py` を PATH から外した環境で起動方法のコマンドを実行し、エラー出力がなく終了コード 0 になる。
4. `hooks/uncommitted_warn.py` を削除し、`docs/git-flow.md` と `README.md` を直す → 検証: `grep -r uncommitted_warn` が、`.git` 以外でヒットしない。README の件数を `settings.json` と照合する。
5. 実機で、一時リポジトリに対し、Claude Code から各 Hook を確認する → 検証: 受入条件 3〜9 の動作を目視で確認し、結果を報告する（確認できない項目は「未検証」と書く）。特に、PostToolUse が Bash の失敗時に動かないこと、同じイベントの Hook の並列実行時の挙動、SessionStart の `systemMessage` がユーザーの画面に出ることは、仕様を未確認なので実機で確かめる。
6. CLAUDE.md の規則に従い、完了報告の前に、文脈を共有しない新規のサブエージェントが「正しさと要件」「過剰実装とリスク」の観点でレビューを行う（ファイル数が2以上なので、観点ごとに別のサブエージェント） → 検証: 指摘と対応を報告する。

## 受入条件

テストは、一時フォルダに作った Git リポジトリ（リモートは、ローカルの bare リポジトリ）で行う。

1. Git 管理外のフォルダ、`.git` フォルダの中、bare リポジトリで、全サブコマンドが、何も出力せず終了コード 0 で終わる。
2. `session-start` が、`systemMessage` と `hookSpecificOutput.additionalContext` の両方に、正規表現 `ブランチ: .+ / 未コミット: \d+件` に一致する文面を出す。リモートがあるときは `リモート差: ahead \d+・behind \d+` も含む。リモートが取得できないときは、「取得できず」の文言を含む。リモートがないリポジトリでは、ahead・behind を出力しない。
3. 既定ブランチ上で、リポジトリ内のファイルへの `pre-tool`（Edit・Write・Bash の `rm`）が deny を返し、理由に `AskUserQuestion`、`git switch -c`、`allow-main <session_id>`（実際の ID）を含む。作業ブランチ上、またはリポジトリ外のファイルでは、何も返さない。
4. `allow-main` を実行したセッションでは、3 が deny を返さず、既定ブランチ上の `git commit` と `git push` も拒否されない。別のセッションには効かない。
5. 既定ブランチ上の `git commit`・`git merge`・`git push`（`HEAD:main` を含む）が、免除がなければ deny になる。作業ブランチ上では deny にならない。コミットが1つもないリポジトリの最初のコミットは deny にならない。
6. `git push --force`・`-f`・`--force-with-lease` が、免除の有無にかかわらず、deny になる。
7. GitHub のリモートで、`allow-merge` の記録がない `gh pr merge --squash` が deny になり、理由に最新タグと `allow-merge <session_id>` を含む。`--squash` がない、または `--auto` がある `gh pr merge` は、記録があっても deny になる。`allow-merge <session_id> v0.2.0` のあとの `gh pr merge --squash` は通り、`post-tool` が記録を消す（次の `gh pr merge` は再び deny になる）。GitHub 以外のリモートでは deny にならない。
8. `post-tool` が、`allow-merge` の記録が版のとき、`gh pr merge` の成功後に `git tag`・`git push origin`・`gh release create` を含む指示を返す。`skip` のときは何も返さない。
9. `stop` が、編集の記録のあるセッション（Edit・Write と、Bash の `rm` を含む）で、未コミット → コミット、未 push → push、PR なし → PR の促しを block で返す。同じ状態では2回目に何も返さない。`stop_hook_active` が真なら何も返さない。編集のないセッションでは何も返さない。
10. `settings.json` が JSON として読め、`SessionStart`・`PreToolUse`・`PostToolUse`・`Stop` に新しい Hook が登録されている。Hook のコマンドは、すべて `py … || python3 … || python … || true`（各コマンドの標準エラー出力は捨てる）の形である。PATH を `git` と `bash` のあるフォルダだけに絞り、`py`・`python3`・`python` が見つからない環境で、各 Hook のコマンドを実行しても、エラー出力がなく終了コード 0 になる。
11. `permissions.ask` に `Bash(gh release create *)` があり、README の件数（11）と一致する。
12. `hooks/uncommitted_warn.py` が存在せず、リポジトリ内に参照が残っていない。
13. `docs/git-flow.md` に、基本フロー8段階、ブランチ名の規則、上の「バージョン表記の定義」の表（この SPEC と同じ文面）、「各段階を Hook がどう扱うか」の表がある。
14. 版の書式の検査:
    - `allow-merge <session_id> v1.2.3` と `v0.1.0` は受け付ける。`1.2.3`、`V1.2.3`、`v1.2`、`v01.2.3`、`v1.2.3-rc.1` は拒否する。`skip` は受け付ける。
    - `git tag v1.2.3` と `git tag -a v1.2.3 -m x` は通り、`git tag 1.2.3` と `git tag release` は deny になる。`git tag -l`、`git tag -d v1.2.3` は検査しない。
15. 版の決め方のルール（`git_flow.py` の関数）のテスト。コミット件名の一覧と前のタグから、次の版が表のとおりに出る。
    - `feat` を含む → MINOR（例: `v1.2.3` → `v1.3.0`）。`fix` だけ → PATCH（`v1.2.3` → `v1.2.4`）。`docs` だけ → `skip`。
    - 破壊的変更あり: `v1.2.3` → `v2.0.0`、`v0.3.0` → `v0.4.0`。
    - タグが1つもない → `v0.1.0`。
    - この関数の結果は、`allow-merge` の拒否理由の「提案する版」に含める。
16. 既存の `readme_guard.py` の動作は変わらない（起動方法の変更を除く）。

## 非目標

- Git Flow（develop・release・hotfix）と trunk-based の対応。
- `CHANGELOG.md` と `VERSION` ファイルの管理。
- `.git/hooks`（pre-commit など）の Git 側の Hook。
- Claude の外で行う手動の `git` 操作の制御（Hook は Claude のツール呼び出しだけを見られる）。
- Mods での実装。
- Hook によるブランチの自動作成。ブランチは、ユーザーの確認のあとに Claude が作る。
- リポジトリごとの有効・無効の設定ファイル。
- `readme_guard.py` の Git 判定の追加。
- `statusline.py` と、`py` を使うほかの設定の Linux 対応。
- Bash でのファイル削除・移動の網羅的な検出（主要な4種類のコマンドだけ）。
- Linux 実機での動作確認（未検証）。
- PowerShell ツールなど、Bash ツール以外の操作の検査。
- コミットメッセージと PR タイトルの形式の検査。
- プレリリース版（`-rc.N`）のタグ。
- `gh pr merge --auto` への対応（拒否する）。
- `pyproject.toml`・`requirements-dev.txt`・`.gitattributes` の新設（リポジトリの既存の慣習にない）。

## リスク

- Stop で `readme_guard.py` と `git_flow.py stop` の両方が block すると、Claude が2つの確認を行う。並列に実行されうるが、状態ファイルは別々で、どちらも「同じ状態では1回だけ」なので、無限には続かない。並列時の理由の扱いは、実機で確認する（未検証）。
- `session-start` の `git fetch` で、最大5秒、開始が遅れる。
- 全 Git リポジトリで、main への直接の commit・push が、免除なしでは拒否される。作業の進め方が変わる。「切らない」を選べば、そのセッションだけ外せる。
- GitHub のリモートを持つすべてのリポジトリで、`gh pr merge` のたびにリリースの確認が出る。タグが1つもないリポジトリでも出る（「しない」を選べば進める）。
- 免除の印はセッションごとに一時フォルダへ置くので、セッションを変えると、再び確認が出る。
- Bash の拒否の判定は、コマンド文字列の照合なので、書き方によって取りこぼす（`bash -c` で包んだ `git commit` など）。拒否を回避する目的ではなく、既定の誤操作を防ぐ範囲とする。
- `force push` は、CLAUDE.md の「確認すれば実行できる」より強く、常に拒否される。必要なときは、ユーザーが `!` 付きで自分の端末から実行する。
- `gh` が未ログインのときは、PR 作成・リリース作成の指示が実行できない。Claude は、その旨を報告して止まる。
- Linux 実機では確認していない（保証するのは、エラー表示が出ないことだけ）。
- `git tag` の書式の検査は、GitHub 以外のリモートや、別の命名規則のリポジトリでも効く。必要なときは、ユーザーが `!` 付きで自分の端末から実行する。
- `cd` の行き先が分からないとき（`cd -`・`$VAR`・存在しないフォルダ）は、作業フォルダを変えずに判定する。引用符の外に `(` か `||` がある行では、`cd` が後ろに効くとは限らないので、`cd` の前後のフォルダを両方検査し、どちらかが拒否なら拒否する。その行でのブランチ作成は、「新しいブランチ上」の扱いに使わない。`cd $(…)` や `pushd` のように行き先が静的に分からない場合は、元のフォルダで判定する（素通りしうる）。`git switch -c foo || git commit` のように、ブランチ作成が失敗しても続く書き方は、新しいブランチ上として扱う。`rm` の対象が複数のリポジトリにまたがるときは、最初の作業ツリー内の対象だけで判定する。
- PostToolUse は、終了コードが 0 以外の Bash でも動く（実機で確認済み。存在しないファイルの `rm` で、編集の記録が付いた）。`gh pr merge` が失敗しても、`allow-merge` の記録が消え、リリースの手順を促す。促しの手順1が、MERGED でなければ止める確認なので、マージされていないのにタグを打つことはない。次の `gh pr merge --squash` では、確認が再び出る。
- `allow-main`・`allow-merge` は Claude が実行できるので、Hook は、誤操作を防ぐ範囲の仕組みである（回避の防止ではない）。
- Bash ツール以外（PowerShell ツールなど）の操作は、検査しない。`allow-*` のコマンドも、Bash ツールで実行する前提。
- コマンド行の解析は文字列の照合なので、`cat <<EOF` の本文の中の `git push --force` のような文言も、コマンドとして拒否する。
- 状態ファイルは一時フォルダに置く。Hook と Bash ツールの一時フォルダが異なる環境（サンドボックスなど）では、`allow-main` の印が Hook に届かない（未検証）。
- `git fetch` が時間切れのとき、子プロセスが残って終了が遅れる可能性がある（未検証。settings.json の timeout が上限）。

## 決定ログ

| ID | 決定 | 理由 |
|---|---|---|
| Q1 | 目的・判定基準は、依頼文から推定した案どおり | 6要望と現状の構成から導いた |
| Q2 | 障壁は、Hook の見える範囲の限界、確認の頻度、fetch の遅さ、`gh` の未ログインを想定済み | 設計で対処できる |
| Q3 | 制約は、案に加えて、Linux に入れても影響を出さない | ユーザーの追加指示 |
| Q4 | `py → python3 → python` の順に試す起動方法にする | Windows の動作を変えずに、Linux のエラーを防ぐ |
| Q5 | main/master 上のときだけ確認する。操作は Edit・Write・NotebookEdit と、Bash の `rm`・`git rm`・`mv`・`Remove-Item` | 依頼の「作成・削除・編集」の最小の範囲 |
| Q6 | Hook が止め、Claude が質問してブランチを作る。「切らない」はセッションだけ免除 | 「確認する（既定は切る）」を満たす |
| Q7 | `git fetch` を5秒の制限で実行して比べる。失敗時は明記する | 最新の差が要望2の目的 |
| Q8 | Stop で止め、Claude に次の行動を促させる。同じ状態では1回 | 促しを実際の行動につなげる |
| Q9 | GitHub Flow | 要望3〜5と一致し、単純 |
| Q10 | main への commit・merge・push と force push は拒否。それ以外は警告。「切らない」のセッションは main への commit・push の拒否を外す | 遵守させつつ逃げ道を残す |
| Q11 | SemVer をタグだけで管理 | バージョンのファイルがなく、ずれない |
| Q12 | GitHub Release の自動生成ノート | ファイルが増えない |
| Q13 | マージの前後の2点で関与する | 版数を、文脈が新しいうちに決める |
| Q14 | Web UI のマージ後の未リリースを、セッション開始時に1行で出す（タグがなければ出さない） | 漏れを拾い、他のリポジトリでうるさくしない |
| Q15 | squash | 1 PR = 1 コミットで、ノートの自動生成と合う |
| Q16 | GitHub のリモートのときだけ、PR・リリース工程を有効にする | 設定なしで、対象を GitHub に絞れる |
| Q17 | `git_flow.py` を新設し、`uncommitted_warn.py` は削除する | Stop の警告の重複を避ける |
| Q18 | `readme_guard.py` はスキップの対象外 | Git に依存しない |
| Q19 | タグの書式は `vMAJOR.MINOR.PATCH` だけ（プレリリースなし） | 個人・少人数の設定リポジトリでは、プレリリースを使わない |
| Q20 | 0.y.z の間は、破壊的変更も MINOR を上げる。1.0.0 はユーザーが明示したときだけ | SemVer の 0.y.z の慣習。意図しない 1.0.0 を防ぐ |
| Q21 | `feat` → MINOR、`fix`・`perf`・`refactor` → PATCH、`docs` などだけ → 版を上げない | 利用者に関わる変更のあるときだけリリースする |
| Q22 | 版の書式に合わない `allow-merge` の引数と `git tag` を拒否する | 定義を文書だけにせず、Hook で守らせる |
| Q23 | Hooks で実装する。Mods は使わない | Hooks は、要望の5つの動作（開始時の表示、実行前の拒否、実行後の指示、終了時の促し、他 OS への無害さ）を、公式ドキュメント（https://code.claude.com/docs/en/hooks.md ）の記載どおりに実現できる。Mods は、終了時に Claude へ促す方法の記載がなく、新しい仕組みで版ごとに型定義が変わり、`~\.claude` へのコピーでは読み込まれない |
| 補足 | Q13 で示した「各コマンドは、これまでどおり `permissions.ask` の確認を通る」を満たすため、`Bash(gh release create *)` を `permissions.ask` に足す | 現状の `permissions.ask` に `gh release create` がなかった |
| 補足 | 既定のコード規則（`rules\python-style.md`）のうち、`pyproject.toml` などの新設は行わない。新しいコードは規則どおり（`pathlib`・UTF-8・型ヒント）に書き、ruff はスクラッチパッドの設定で一時的に確認する | 既存の慣習を優先する（CLAUDE.md） |

## 参考元（GitHub の類似リポジトリ）

検索語: `claude-code hooks`、`claude code git hooks`、`claude code hooks git`（`gh search repos`、スター数の降順、更新が直近1年以内）。READMEの説明のみ確認し、コードは取り込んでいない。

| 参考元の URL | ライセンス | 取り入れた点 | 切り捨てた点 |
|---|---|---|---|
| https://github.com/karanb192/claude-code-hooks | MIT | 安全系 Hook を、プラグインとして配る発想（考え方のみ） | 配布の仕組み（依頼にない） |
| https://github.com/disler/claude-code-hooks-mastery | 不明 | 考え方のみ（Hook の種類と JSON の入出力） | すべて |
| https://github.com/tlq5l/claude-guards | MIT | 考え方のみ（Git 操作を Hook で守る発想） | 購入・pipefail の Hook |
| https://github.com/bgorzelic/quality-gates | MIT | 考え方のみ（Hook・Git hook・CI の多層で守る発想） | Git 側の Hook・CI（非目標） |
| https://github.com/ThammanaSrinivas/guardrails | MIT | 考え方のみ（Claude Code の Hook と Git の Hook を同じ規則にそろえる発想） | Git 側の Hook・CI（非目標） |

ブランチ確認・リモートとの差・リリース工程まで通して扱う類似のリポジトリは、見つからなかった。
