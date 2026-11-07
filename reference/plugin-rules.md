# スキル・プラグイン作成の共通ルール

スキル・プラグインを作る・変更するときに従う規則。

- **必須**は守る。**推奨**は、理由があれば外してよい。〔公式〕は、公式の仕様に依存する規則。
- 配布しない個人用は、E・H1・H2・F1 の 5 を除いて守る。
- Python の規則（A1・A4〜A7・H5）は、`~/.claude/rules/python-venv.md` の 2 にも書く。Windows 前提。
- `<PLUGIN>`・`<SKILL>` は名前。環境変数名では、大文字にして `-` を `_` にする（`MY_PLUGIN_HOME`）。

## 用語

- **単体スキル**: プラグインに属さないスキル。`plugin.json` を置くと、公式はプラグインとして読む。
- **専用環境**: そのプラグインだけが使う実行環境。
- **置き場**: 専用環境と状態の置き場。A7 で決まる。
- **入口スクリプト**: SKILL.md が最初に呼ぶ、標準ライブラリだけのスクリプト。

## A. 実行環境と状態

### A1. 専用環境だけで実行する（必須）
- 本体は専用環境の中だけで実行する。システム側は、入口の起動にだけ使う。
- システム側にライブラリを入れず、読まない。環境を選ぶ分岐は作らない。
- 専用 venv の Python は `-B -I` で起動する。

### A2. 置き場は `${CLAUDE_PLUGIN_DATA}`（必須）〔公式〕
- 専用環境と状態は `${CLAUDE_PLUGIN_DATA}` に置く。`${CLAUDE_PLUGIN_ROOT}` は更新で入れ替わるので、何も置かない。
- `--plugin-dir` では置き場が別になる。開発時は A7 で固定する。
- 専用 venv は、置き場の直下の `venv\` に作る。位置を別に指定する設定は作らない。置き場を変えたら、承認（A5）を取り直す。
- Node は、`package.json` と lockfile を置き、公式の自動導入に任せる。`npm ci` は自分で実行しない。

### A3. 変数は引数で渡す（必須）〔公式〕
- 変数は SKILL.md と agent の本文に書き、入口には引数で渡す。Bash の環境変数には入らない。

      python -B -I "${CLAUDE_PLUGIN_ROOT}/<入口スクリプト>" --data "${CLAUDE_PLUGIN_DATA}" <サブコマンド>

- 入口は 1 ファイルにする（`-I` は入口のフォルダを読まない）。Node は `python` を `node` にする。
- `python` を起動できないとき（Store のスタブなど）の案内（`py -3`）を SKILL.md に書く。

### A4. 依存は `==` で固定する（必須）
- 間接依存も固定する（本体の依存だけの venv の `pip freeze`。`-e` と `@ file://` は除く。Node は `package-lock.json`）。
- 版は、本体と開発用の依存を入れた新しい venv で、全テストが通ったものにする。
- 版がずれたら、終了コード 3 で止まる。再同期は承認後の `setup --yes`。

### A5. 導入は承認を得てから（必須）
- 専用環境と依存の導入は、容量を問わず承認を得る。作り直しも同じ。Node の公式の自動導入は例外。
- `setup`（`--yes` なし）は、場所・内容・容量を表示して終了コード 3 で止まる。SKILL.md は、その出力を見せ、承認後に `--yes` を付ける。
- 任意の依存は、承認を得るか、代替手段を案内して止まる。

### A6. 入口スクリプトの契約（必須）
- `doctor`（何も変更しない）と `setup` を持つ。`doctor` は、専用 venv の Python を起動して、依存の import まで確かめる。
- 終了コード: 0 成功、1 実行時のエラー、2 引数・設定のエラー、3 専用環境が使えない。
- 3 のときは、不足の内容と `setup` の案内を出す。置き場のフォルダがないときも 3（`setup --yes` が作る）。
- フックから呼ぶ入口は、2 を返さない（フックでは 2 が停止の意味）。
- 専用環境を使わないスクリプトには求めない。

### A7. 置き場の優先順
- 必須: 環境変数 `<PLUGIN>_HOME`、引数 `--data` の順で決める。両方あって違うときは、環境変数を使い、警告を出す。
- 必須: どちらもなければ、`--data` の付け方を表示して終了コード 2 で止まる（フックは A6）。
- 推奨: `--data` を `<PLUGIN>_HOME` に入れて子プロセスに渡す。
- 推奨: 開発専用の探索（環境の自動検出など）は作らない。
- 開発・検査の `<PLUGIN>_HOME` は、そのコマンドの環境にだけ設定する。

### A9. 単体スキル（必須）〔公式〕
- `${CLAUDE_SKILL_DIR}` を使う（`${CLAUDE_PLUGIN_*}` は使えない）。
- 置き場は、`<SKILL>_HOME`、`%LOCALAPPDATA%\<SKILL>\` の順で決める。同名のスキルを、ユーザー用とプロジェクト用の両方に作らない。
- A3・C2・E・H1・H2 は適用しない。他は読み替えて適用する。

## B. 本体は読み取り専用

### B1. 実行時に `${CLAUDE_PLUGIN_ROOT}` へ書かない（必須）
- 成果物は作業側、状態は `${CLAUDE_PLUGIN_DATA}` に置く。

## C. SKILL.md / agent

### C1. frontmatter と description（必須）
- `name` と `description` を書く。`name` はディレクトリ名と一致させる（独自の規則）。
- description に、何をするか、使う場面（利用者の言い回し）、使わない場面と代わりのスキルを書く。`disable-model-invocation: true` なら、最後は省く。
- 〔公式〕description は `when_to_use` と合わせて 1,536 文字で切れる。未知のキーは無視されるので、綴りを確かめる。

### C2. パスの書き方（必須）
- プラグイン内のコマンドは、`${CLAUDE_PLUGIN_ROOT}/…` を基準にする。
- 絶対パス、`${CLAUDE_SKILL_DIR}`、相対リンク、地の文の相対パスは書かない（基準を統一する独自の規則）。

### C3. 権限を絞る（必須）〔公式〕
- `allowed-tools` は、特定のスクリプトの特定のサブコマンドだけにする（例: `Bash(python -B -I "${CLAUDE_PLUGIN_ROOT}/scripts/build.py" --data "${CLAUDE_PLUGIN_DATA}" build *)`）。`Bash(node *)` のような広い許可は書かない。
- `allowed-tools` は事前承認で、他を禁じない。`setup` は含めない（`setup *` も `setup --yes` に一致する）。広い許可を設定した利用者には、A5 の確認は効かない。
- `$ARGUMENTS` は、Bash の文字列に埋め込まない（`"` での脱出や `--yes` の混入を防げない）。ファイルに書き、パスを渡す。
- agent の `tools` は、必要なものだけにする。MCP は `mcp__<server>__*` で絞る。MCP を利用者が決める agent だけは、省略してよい（全ツールを継承する。理由を README に書く）。
- プラグインの agent では、`hooks`・`mcpServers`・`permissionMode`・`initialPrompt` は無視される。

### C5. 副作用のあるスキルは自動起動させない（必須）〔公式〕
- 外部への送信、不可逆な書き込み、常駐（`monitors` を含む）、`setup` の呼び出しは、`disable-model-invocation: true` にする。

## D. 出典

### D2. 出典を書く（必須）
- 取り込んだ文書・コードの出典とライセンスは、プラグインのルート（`plugins/<名前>/NOTICE`）に書く。直下の README は配布物に入らない。

## E. 配布

### E1. plugin.json（必須）〔公式〕
- `.claude-plugin/plugin.json` に `name`・`version`・`description`・`author.name` を書く（公式の必須は `name`）。
- version は、メタとコードで一致させ、更新を届けるときに上げる（書くと、変えるまで更新は届かない）。
- agents・skills・commands・hooks は、`.claude-plugin/` に置かない。

### E3. リポジトリの構成（推奨）
- 本体は `plugins/<名前>/`、`source` は `./plugins/<名前>`（`./` で始め、`..` を含めない）。tests・docs は直下に置く。
- 直下をプラグインにするのは、tests・docs のない極小のものだけ。`source` は `"."`、F1 は `validate --strict` と目視で代える。
- README は直下に 1 つ。対応 OS と、消えるもの・残るものを書く。

### E4. marketplace.json（必須）〔公式〕
- `name`・`owner.name`・`plugins[].{name,source,description}` を書く。`plugins[].version` は書かない。

### E5. 配置と読み込み（推奨）
- `plugins/<PLUGIN>/` 直下に、`.claude-plugin/plugin.json`・`skills/<SKILL>/SKILL.md`・入口・依存の固定ファイルを置く。agent は `agents/`、hooks と `bin/` はルート直下。
- `hooks/hooks.json` は、最上位の `"hooks"` キーで包む（包まないと読まれない）。
- 開発は `claude --plugin-dir ./plugins/<名前>`（直下がプラグインなら `.`）。〔公式〕

## F. 検査

### F1. 最低限の検査（必須）
次をテストにする（Python は `~/.claude/rules/python-testing.md`）。
1. 全 SKILL.md に frontmatter があり、`name` がディレクトリ名と一致する。
2. SKILL.md と agent に絶対パスがない。プラグイン内では `${CLAUDE_SKILL_DIR}` もない。
3. `${CLAUDE_PLUGIN_ROOT}/…` が指すファイルが実在する。
4. 相対リンク・地の文の相対パスがない。
5. version が、メタとコードで一致する。
6. 配布に必要なファイルが git 管理下にある。
7. `claude plugin validate <dir> --strict` が終了コード 0 で通る。

専用環境を持つ場合は、さらに次もテストにする。
8. `requirements.txt` に `==` のない行がない（Node は lockfile）。
9. 環境がないとき終了コード 3、置き場の指定がないとき終了コード 2（単体スキルを除く）で止まる。
10. 空の一時フォルダを置き場にし、PyPI に接続できる環境で確かめる。一時フォルダは、`${CLAUDE_PLUGIN_ROOT}` とリポジトリの外に作る。
    - `--yes` なしの `setup` は、終了コード 3 で止まり、`venv\` を作らない。
    - `setup --yes` のあと、`venv\Scripts\python.exe` があり、`doctor` が 0 になる。
    - 前後で、`${CLAUDE_PLUGIN_ROOT}` のファイル一覧が変わらない（B1）。

- 単体スキルは、1・2・4と、専用環境があれば 8〜10 を適用する。2 は絶対パスのみ。3 は `${CLAUDE_SKILL_DIR}/…`。`${CLAUDE_PLUGIN_ROOT}` は `${CLAUDE_SKILL_DIR}`、`<PLUGIN>_HOME` は `<SKILL>_HOME` に読み替える。

### F2. 追加の検査（推奨）
- SKILL.md のコマンドが実在し、待機・再試行の上限と、超えたときの動きが書かれている。廃止したものが残っていない。
- リリース前に、開発用 venv を使わず、`requirements.txt` の依存だけで F1 の 10 を行う。最低限の版の Python でも行う。用意できなければ、理由を添えて「未検証」と報告する。

## G. チェックリスト

F1 にない項目を、レビューで目視する。
- [ ] A1〜A3・A7 専用環境の中だけで実行し、状態と venv は置き場に置き、変数は引数で渡している
- [ ] A4〜A6 依存を固定し、承認後の `setup --yes`、`doctor`、終了コード 0〜3 がある
- [ ] C1・C3・C5 description が揃い、`allowed-tools`・`tools` を絞り、`setup` を含めず、`$ARGUMENTS` を埋め込まず、副作用に `disable-model-invocation: true` がある
- [ ] D2・E1・E4 `NOTICE`、plugin.json、marketplace.json がある
- [ ] E5 hooks と `bin/` のコマンドを C2 に準じて書いている
- [ ] H1・H2 対応 OS を明記し、予約名を使っていない
- [ ] 推奨: A7 の推奨・E3・E5・F2・H5

## H. その他

### H1. 対応 OS を明記する（必須）
- Windows 専用なら、README と plugin.json の `description` に書く。

### H2. 名前（必須）〔公式〕
- プラグイン名は kebab-case。`claude-`・`anthropic-`・`anthropics-`・`cc-plugin-` で始めず、`claude`・`anthropic`・`anthropics`・`claude-code`・`claude-mods` そのものにしない。`official` を `claude`・`anthropic` の隣に置かない。
- marketplace 名に、公式の「Reserved names」（`inline`・`builtin`・`npm`・`github` など）と、`claudeai-` で始まる名前を使わない。

### H5. 依存の取得元とパス（推奨）
- 依存は PyPI・npm から取得し、可能ならハッシュも固定する。
- パスをクォートし、空白・日本語のパスでも動くことをテストする。
