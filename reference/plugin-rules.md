# スキル・プラグイン作成の共通ルール

Claude Code のスキル・プラグインを作る・変更するときに従う規則。

- **必須**は守る。**推奨**は、守らない理由があれば外してよい。〔公式〕は、公式の仕様に依存する規則を指す。
- 配布しない個人用のプラグインは、E、H1、H2、F1 の 5 を除いて守る。
- Python の規則（A1・A4〜A7・H5 の Python の部分）は、`~/.claude/rules/python-venv.md` の 2 にも書く。Windows 前提で書く。
- `<PLUGIN>` はプラグイン名、`<SKILL>` はスキル名。環境変数名では、大文字にして `-` を `_` に置き換える（`my-plugin` は `MY_PLUGIN_HOME`）。

## 用語

- **単体スキル**: プラグインに属さないスキル（`~/.claude/skills/<名前>/`、`.claude/skills/`）。`.claude-plugin/plugin.json` を置くと、公式はプラグインとして読み込む。
- **専用環境**: プラグイン（単体スキル）だけが使う実行環境。
- **置き場**: 専用環境と状態を置くディレクトリ。決め方は A7。
- **入口スクリプト**: SKILL.md が最初に呼ぶスクリプト。標準ライブラリだけで動かす。

## A. 実行環境と状態

### A1. 専用環境だけで実行する（必須）
- 本体は専用環境の中だけで実行する。システム側の実行環境は、入口スクリプトの起動にだけ使う。
- システム側にライブラリを入れない・読まない。システムの環境と専用環境を選ぶ分岐は作らない。
- 専用 venv の Python は `-B -I` で起動する。`-I` は環境変数と利用者のサイト設定を読まず、`-B` は `__pycache__` を書かない。

### A2. 置き場は `${CLAUDE_PLUGIN_DATA}`（必須）〔公式〕
- 専用環境と状態は `${CLAUDE_PLUGIN_DATA}` に置く。`${CLAUDE_PLUGIN_ROOT}` は、更新で入れ替わるので、何も置かない。
- `claude --plugin-dir` で読み込むと、置き場が本番と別になる。開発時は A7 で固定する。
- Python の専用 venv は、入口の言語を問わず、置き場の直下の `venv\` に作る。venv の位置を別に指定する設定は作らない。置き場を変えたら、A5 の承認を取り直して作り直す。
- Node は、`package.json` と lockfile を本体に置き、公式の自動導入に任せる。自分では `npm ci` しない。

### A3. 変数は引数で渡す（必須）〔公式〕
- `${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` は、SKILL.md と agent の本文に書き、入口スクリプトには引数で渡す。Bash ツールの環境変数には入らない。

      python -B -I "${CLAUDE_PLUGIN_ROOT}/<入口スクリプト>" --data "${CLAUDE_PLUGIN_DATA}" <サブコマンド>

- `-I` は入口のフォルダを `sys.path` に入れないので、入口は 1 ファイルにする。Node の入口は `python` を `node` に読み替える。
- `python` を起動できないとき（Microsoft Store のスタブなど）の案内（`py -3` など）を、SKILL.md に書く。

### A4. 依存は `==` で固定する（必須）
- 間接依存も含めて、すべて版を固定する（本体の依存だけを入れた venv の `pip freeze`。`-e` と `@ file://` の行は除く。Node は `package-lock.json`）。
- 固定する版は、新しい venv に本体と開発用の依存を入れて、全テストが通った版にする。
- 環境の版がずれたら、終了コード 3 で止まる。再同期は、承認後の `setup --yes` で行う。

### A5. 導入は利用者の承認を得てから（必須）
- 専用環境とその依存の導入は、容量を問わず、承認を得てから行う。作り直しも同じ。Node の公式の自動導入は例外とする。
- `setup`（`--yes` なし）は、場所・内容・容量を表示して、終了コード 3 で止まる。SKILL.md は、その出力を利用者に見せ、承認を得てから `--yes` を付ける。
- 任意の依存は、承認を得て導入するか、代替手段を案内して止まる。

### A6. 入口スクリプトの契約（必須）
- サブコマンド `doctor`（診断のみ。何も変更しない）と `setup`（A5）を持つ。`doctor` は、専用 venv の Python を子プロセスとして起動し、依存を import できるところまで確かめる。
- 終了コード: 0 成功、1 実行時のエラー、2 引数・設定のエラー、3 専用環境が使えない。
- 終了コード 3 のとき、不足の内容と、置き場を含む `setup` の案内を出す。置き場のフォルダがまだないときも 3 とする（`setup --yes` が作る）。
- フックから呼ぶ入口は、2 を返さない。フックでは 2 が「処理を止める」意味になる。
- 専用環境を使わないスクリプトには、これらを求めない。

### A7. 置き場の優先順
- 必須: 環境変数 `<PLUGIN>_HOME`、引数 `--data <パス>` の順で決める。両方があって違うときは、環境変数を使い、警告を出す。
- 必須: どちらもなければ、`--data` の付け方を表示して終了コード 2 で止まる（フックから呼ぶときは A6）。
- 推奨: 入口は、`--data` を `<PLUGIN>_HOME` に入れて子プロセスに渡す。
- 推奨: 開発専用の探索（リポジトリ内の環境の自動検出など）は作らない。
- 開発・検査で `<PLUGIN>_HOME` を設定するときは、そのコマンドの環境にだけ設定する。

### A9. 単体スキルの場合（必須）〔公式〕
- `${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` は使えない。`${CLAUDE_SKILL_DIR}` を使う。
- 置き場は、環境変数 `<SKILL>_HOME`、`%LOCALAPPDATA%\<SKILL>\` の順で決める（A7 の代わり）。ユーザー用とプロジェクト用に同名のスキルを作らない。
- A3・C2・E・H1・H2 は適用しない。それ以外は、読み替えて適用する。

## B. 本体は読み取り専用

### B1. 実行時に `${CLAUDE_PLUGIN_ROOT}` へ書かない（必須）
- 成果物は作業側、状態は `${CLAUDE_PLUGIN_DATA}` に置く。Python は A1 の `-B` で起動する。

## C. SKILL.md / agent の書き方

### C1. frontmatter と description（必須）
- `name` と `description` を書く。`name` はディレクトリ名と一致させる（この文書の規則）。
- description には、何をするか、使う場面（利用者の言い回し）、使わない場面と代わりに使うスキルの 3 点を書く。`disable-model-invocation: true` のスキルは、3 点目を省略してよい。
- 〔公式〕description は `when_to_use` と合わせて 1,536 文字で切られる。未知の frontmatter のキーは警告なしで無視されるので、綴りを確かめる。

### C2. パスの書き方（必須）
- プラグイン内のコマンドは、`${CLAUDE_PLUGIN_ROOT}/…` を基準に書く。
- 絶対パス、`${CLAUDE_SKILL_DIR}`、相対リンク、地の文の相対パスは書かない（基準を統一するための、この文書の規則）。

### C3. 権限を絞る（必須）〔公式〕
- `allowed-tools` は、特定のスクリプトの特定のサブコマンドだけにする（例: `Bash(python -B -I "${CLAUDE_PLUGIN_ROOT}/scripts/build.py" --data "${CLAUDE_PLUGIN_DATA}" build *)`）。`Bash(node *)` のような広い許可は書かない。
- `allowed-tools` は、事前に承認するだけで、他のツールを禁じない。`setup` は含めない（`setup *` も `setup --yes` に一致する）。A5 の承認は SKILL.md の手順で、利用者が広い許可を設定していると強制されない。
- `$ARGUMENTS` は、Bash のコマンド文字列に埋め込まない。クォートしても、`"` での脱出や `--yes` の混入を防げない。ファイルに書き、パスだけを渡す。
- agent の `tools` は、必要なものだけにする。MCP は `mcp__<server>__*` で絞る。MCP を利用者が決める agent だけは、省略してよい（全ツールを継承する。理由を README に書く）。
- プラグインの agent では、`hooks`・`mcpServers`・`permissionMode`・`initialPrompt` は無視される。

### C5. 副作用のあるスキルは自動で起動させない（必須）〔公式〕
- 外部への送信、不可逆な書き込み、常駐（`monitors` を含む）、依存の導入（`setup`）をするスキルは、`disable-model-invocation: true` にする。

## D. 出典

### D2. 取り込んだものの出典を書く（必須）
- 他者の文書・コードを取り込むときは、出典とライセンスを、プラグインのルート（二重構造なら `plugins/<名前>/NOTICE`）の `NOTICE` に書く。直下の README は、利用者の受け取る配布物に入らない。

## E. 配布

### E1. plugin.json（必須）〔公式〕
- `.claude-plugin/plugin.json` に、`name`・`version`・`description`・`author.name` を書く（公式の必須は `name` だけ）。
- version は、メタとコードで一致させ、更新を届けるときに上げる（書くと、文字列を変えるまで更新が届かない）。
- agents・skills・commands・hooks は、`.claude-plugin/` の中に置かない。

### E3. リポジトリの構成（推奨）
- `plugins/<名前>/` が本体、marketplace.json の `source` が `./plugins/<名前>`（`./` で始め、`..` を含めない）。tests・docs は、リポジトリ直下に置く。
- 直下をプラグインにするのは、tests・docs のない極小のものだけにする。`source` は `"."`、F1 は `claude plugin validate --strict` と目視で代える。
- README は直下に 1 つだけ置き、利用者向けの内容（対応 OS、消えるもの・残るもの）を書く。

### E4. marketplace.json（必須）〔公式〕
- `name`・`owner.name`・`plugins[].{name,source,description}` を書く。`plugins[].version` は書かない。

### E5. 配置と読み込み（推奨）
- `plugins/<PLUGIN>/` の直下に、`.claude-plugin/plugin.json`・`skills/<SKILL>/SKILL.md`・入口スクリプト・依存の固定用のファイルを置く。agent は `agents/`、hooks と `bin/` はルート直下に置く。
- `hooks/hooks.json` は、最上位の `"hooks"` キーで包む（包まないと読み込まれない）。
- 開発時は `claude --plugin-dir ./plugins/<名前>` で読み込む（直下がプラグインなら `.`）。〔公式〕

## F. 検査

### F1. 最低限の検査（必須）
次をテストにする。Python のテストは `~/.claude/rules/python-testing.md` に従う。
1. 全 SKILL.md に frontmatter があり、`name` がディレクトリ名と一致する。
2. SKILL.md と agent に、絶対パスがない。プラグイン内では、`${CLAUDE_SKILL_DIR}` もない。
3. SKILL.md が書く `${CLAUDE_PLUGIN_ROOT}/…` が指すファイルが実在する。
4. 相対リンク・地の文の相対パスがない。
5. version が、メタとコードで一致している。
6. 配布に必要なファイルが git 管理下にある。
7. `claude plugin validate <dir> --strict` が終了コード 0 で通る。

専用環境を持つ場合は、さらに次もテストにする。
8. `requirements.txt` に `==` のない行がない（Node は lockfile）。
9. 環境がないときに終了コード 3、置き場の指定がないときに終了コード 2（単体スキルを除く）で止まる。
10. 空の一時フォルダを置き場にして、PyPI に接続できる環境で、次を確かめる。一時フォルダは、`${CLAUDE_PLUGIN_ROOT}` とリポジトリの外に作る。
    - `--yes` なしの `setup` は、終了コード 3 で止まり、`venv\` を作らない。
    - `setup --yes` のあと、`venv\Scripts\python.exe` があり、`doctor` が終了コード 0 になる。
    - 実行の前後で、`${CLAUDE_PLUGIN_ROOT}` のファイル一覧が変わらない（B1）。

- 単体スキルには、1・2・4と、専用環境を持つ場合は 8〜10 を適用する。2 は絶対パスだけを調べる。3 は `${CLAUDE_SKILL_DIR}/…` の実在を確かめる。`${CLAUDE_PLUGIN_ROOT}` は `${CLAUDE_SKILL_DIR}`、`<PLUGIN>_HOME` は `<SKILL>_HOME` に読み替える。

### F2. 追加の検査（推奨）
- SKILL.md に書いたコマンドが実在し、待機や再試行の上限と超えたときの動きが書かれている。廃止したものが残っていない。
- 専用 venv を持つプラグインは、リリース前に、F1 の 10 を、開発用 venv を使わずに、`requirements.txt` の依存だけで行う。README または入口が検査する最低限の版の Python でも行う。用意できないときは、理由を添えて完了報告に「未検証」と書く。

## G. チェックリスト

F1 に入れていない項目を、レビュー時に目視で確認する。
- [ ] A1・A2・A3・A7 専用環境の中だけで実行し、状態と venv は置き場に置き、変数は引数で渡している
- [ ] A4・A5・A6 依存を固定し、承認後の `setup --yes`、`doctor`、終了コード 0〜3 がある
- [ ] C1・C3・C5 description に 3 点があり、`allowed-tools`・`tools` を絞り、`setup` を含めず、`$ARGUMENTS` を埋め込まず、副作用に `disable-model-invocation: true` がある
- [ ] D2・E1・E4 `NOTICE`、plugin.json、marketplace.json の項目がある
- [ ] E5 hooks と `bin/` のコマンドを、C2 に準じて書いている
- [ ] H1・H2 対応 OS を明記し、予約名を使っていない
- [ ] 推奨: A7 の推奨部分・E3・E5・F2・H5 を守っている

## H. その他

### H1. 対応 OS を明記する（必須）
- Windows 専用のときは、README と plugin.json の `description` に書く。

### H2. 名前（必須）〔公式〕
- プラグイン名は kebab-case。`claude-`・`anthropic-`・`anthropics-`・`cc-plugin-` で始めず、`claude`・`anthropic`・`anthropics`・`claude-code`・`claude-mods` そのものにしない。`official` を `claude`・`anthropic` の隣に置かない。
- marketplace 名は、公式の「Reserved names」の予約語（`inline`・`builtin`・`npm`・`github` など）と、`claudeai-` で始まる名前を使わない。

### H5. 依存の取得元とパス（推奨）
- 依存は公式のレジストリ（PyPI・npm）から取得し、可能ならハッシュも固定する。
- コマンドのパスをクォートし、空白・日本語を含むパスでも動くことをテストで確かめる。
