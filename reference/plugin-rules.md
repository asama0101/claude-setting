# スキル・プラグイン作成の共通ルール

Claude Code のスキル・プラグインを作る・変更するときに従う規則。

- **必須**は守る。**推奨**は、守らない理由があれば外してよい。
- 〔公式〕は、公式の仕様に依存する規則を指す。
- Python の規則（A1・A4・A5・A6・A7・H5 の Python の部分）は、`~\.claude\rules\python-venv.md` の 2 に書く。
- `<PLUGIN>` はプラグイン名、`<SKILL>` はスキル名を表す。Windows 前提で書く。

## 用語

- **単体スキル**: プラグインに属さないスキル（`~/.claude/skills/<名前>/`、`.claude/skills/`）。
- **専用環境**: プラグイン（単体スキル）だけが使う実行環境。
- **置き場**: 専用環境と状態を置くディレクトリ。プラグインでは `${CLAUDE_PLUGIN_DATA}`。
- **入口スクリプト**: SKILL.md が最初に呼ぶスクリプト。標準ライブラリだけで動かす。

## A. 実行環境と状態の置き場

### A1. 専用環境だけで実行する（必須）
- 本体は専用環境の中だけで実行する。システム側の実行環境は、入口スクリプトの起動にだけ使う。
- システム側にライブラリを入れない・読まない。
- システムの環境と専用環境の、どちらかを選ぶ分岐は作らない。

### A2. 置き場は `${CLAUDE_PLUGIN_DATA}`（必須）〔公式〕
- 専用環境と状態は `${CLAUDE_PLUGIN_DATA}` に置く。
- `${CLAUDE_PLUGIN_ROOT}` には状態を置かない。更新で中身が入れ替わる。
- `claude --plugin-dir` で読み込むと、置き場が本番と別になる。開発時は A7 で固定する。
- 置き場は、A7 の優先順で決まる 1 つのパス。通常は `--data "${CLAUDE_PLUGIN_DATA}"` の値で、開発・テストで `<PLUGIN>_HOME` を設定したときはそちらが優先される。
- 専用 venv を持つ入口スクリプトは、言語（Python、Node）を問わず、置き場の直下の `venv\` に作る。Python は `venv\Scripts\python.exe`。
- venv の位置を、置き場と別に指定する設定（環境変数・引数・設定ファイル）は作らない。置き場が変わると venv も一緒に移る。〔機械: 置き場を一時フォルダにして `setup --yes` を実行し、`<置き場>\venv` ができて、ほかの場所に venv ができない〕

### A3. 変数は引数で渡す（必須）〔公式〕
- `${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` は、SKILL.md（と agent）の本文に書く。
- 入口スクリプトには引数で渡す。これらの変数は、Bash ツールの環境変数に入らない。

      python "${CLAUDE_PLUGIN_ROOT}/<入口スクリプト>" --data "${CLAUDE_PLUGIN_DATA}" <サブコマンド>

### A4. 依存は `==` で固定する（必須）
- 依存は固定用のファイルで管理し、すべて版を固定する（Node は `package-lock.json`）。
- 固定する版は、新しい専用環境で全テストが通った版にする。
- 環境の版がずれたら、終了コード 3 で止まる。再同期は、承認後の `setup --yes` で行う。

### A5. 導入は利用者の承認を得てから（必須）
- 環境（専用環境・ブラウザなど容量が大きいもの）は、承認を得てから導入する。
- 承認を求めるときは、場所・内容・容量を説明する。`setup`（`--yes` なし）は、これらを表示して終了コード 3 で止まる。
- 小さな任意依存は、承認を得て導入するか、代替手段を案内して止まる。
- 動かなくなった環境は、承認済みの場所だけで作り直す。

### A6. 入口スクリプトの契約（必須）
- サブコマンド `doctor`（診断のみ。何も変更しない）と `setup`（A5）を持つ。
- 終了コード: 0 成功、1 実行時のエラー、2 引数・設定のエラー、3 専用環境が使えない。
- 終了コード 3 のとき、不足の内容と、置き場を含む `setup` の案内を出す。
- 専用環境を使わないスクリプトには、これらを求めない。

### A7. 置き場の優先順（推奨）
- 置き場は、環境変数 `<PLUGIN>_HOME`、引数 `--data <パス>` の順で決める。
- どちらもなければ、`--data` の付け方を表示して終了コード 2 で止まる。
- 入口スクリプトは、`--data` を取り除き、子プロセスの `<PLUGIN>_HOME` に入れて渡す。
- 開発専用の探索（リポジトリ内の環境の自動検出など）は作らない。

### A8. 巨大な共有バイナリは専用環境の対象外（推奨）
- 100 MB 以上で他のツールと共有できるもの（ブラウザなど）は、専用環境に入れず、そのツールの既定の共有の場所に置く。
- README に「共有で、専用環境の対象外」と書く。

### A9. 単体スキルの場合（必須）〔公式〕
- 単体スキルでは、`${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` が使えない。代わりに `${CLAUDE_SKILL_DIR}` を使う。
- 置き場は、環境変数 `<SKILL>_HOME`、`%LOCALAPPDATA%\<スキル名>\` の順で決める。
- A1・A4・A5・A6・A8 はそのまま適用する。A2・A7 はこの優先順で置き換える。A3 は適用しない。
- 専用 venv は、この優先順で決まる置き場の直下の `venv\` に作る（A2 と同じ）。

## B. 本体と利用者の成果物の分離

### B1. プラグイン本体は読み取り専用（必須）
- `${CLAUDE_PLUGIN_ROOT}` には、実行時に何も書かない。成果物は作業側、状態は `${CLAUDE_PLUGIN_DATA}` に置く。

### B2. 作業側へ写したものの更新手段を決める（推奨）
- 本体のファイルを作業側へコピーする設計では、更新を届ける手段を README に書く。
- 消してよいのは、再生成できる派生ファイルだけにする。

## C. SKILL.md / agent の書き方

### C1. frontmatter と description（必須）〔公式〕
- frontmatter に `name` と `description` を書く。`name` はディレクトリ名と一致させる。
- description には、何をするか、使う場面（利用者の言い回し）、使わない場面と代わりに使うスキルの 3 点を書く。
- `disable-model-invocation: true` のスキルは、3 点目を省略してよい。
- description は `when_to_use` と合わせて 1,536 文字で切られる。

### C2. パスの書き方（必須）
- プラグイン内の SKILL.md と agent のコマンドは、`${CLAUDE_PLUGIN_ROOT}/…` を基準に書く。
- 絶対パス、`${CLAUDE_SKILL_DIR}`、相対リンク、地の文の相対パスは書かない。

### C3. 権限を絞る（必須）〔公式〕
- `allowed-tools` は、特定のスクリプトだけに絞る（例: `Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/build.py" *)`）。
- `Bash(node *)` のような広い許可は書かない。agent の `tools` は、必要なものだけにする。
- MCP は `mcp__<server>__*` でサーバー単位に絞る。
- 使う MCP を利用者が決める（D1）agent は、`tools` を省略してよい。省略すると、利用できるすべてのツールを継承する。理由を書く。
- プラグインの agent では、`hooks`・`mcpServers`・`permissionMode`・`initialPrompt` は無視される。

### C4. 細則は references に置く（推奨）
- SKILL.md が 200 行を超えるときは、細則を `references/*.md` に移し、「書く前に読む」と指示する。

### C5. 副作用のあるスキルは自動で起動させない（必須）〔公式〕
- 外部への送信、不可逆な書き込み、常駐をするスキルは、`disable-model-invocation: true` にする。
- それ以外の副作用のあるスキルも、同じにすることを推奨する。

### C6. 重い処理は委譲する（推奨）
- 処理が長いスキルは入口にして、サブエージェントに `$ARGUMENTS` を渡して委譲する。
- 引数が空のときは、CLAUDE.md の原則1に従って聞き返す。Bash に渡す `$ARGUMENTS` は、クォートする。

## D. 外部依存

### D1. MCP は同梱しない（必須）
- `.mcp.json`、`.mcpb` ファイル、plugin.json と marketplace.json の `mcpServers` を置かない。公式は同梱を認めているが、この規則では禁止する。
- 利用者が用意した MCP を使う。指定は `${CLAUDE_PLUGIN_DATA}` に保存してよい。
- 指定がない、または MCP が使えないときは、代替手段か案内を出して止まる。推測でツールを探さない。

### D2. 取り込んだものの出典を書く（必須）
- 他者の文書・コードを取り込むときは、出典とライセンスを README の「出典」節か `NOTICE` に書く。
- `NOTICE` はプラグイン本体（`plugins/<名前>/NOTICE`）に置く。直下だけでは、キャッシュにコピーされない。

## E. 配布メタ

### E1. plugin.json（必須）〔公式〕
- `.claude-plugin/plugin.json` に、`name`・`version`・`description`・`author.name` を書く（公式の必須は `name` だけ）。
- version は、メタとコード（`package.json`・`__version__`）で一致させ、更新を届けるときに上げる。
- agents・skills・commands・hooks を `.claude-plugin/` の中に置かない。読み込まれない。

### E2. 推奨の項目（推奨）
- `license`・`repository`・`keywords` を書く。

### E3. リポジトリの構成（推奨）
- 二重構造を既定とする。`plugins/<名前>/` が本体、marketplace.json の `source` が `./plugins/<名前>` である。
- tests・docs・見本は、本体の外（リポジトリ直下）に置く。
- 直下をプラグインにするのは、これらがない極小のものだけにする。`source` は `"."` にする。
- README は直下に 1 つだけ置く。`plugins/<名前>/README.md` は作らない。
- 利用者向けの詳細（H1・H4・A8・D2・H3・B2）を、直下の README に書く。開発者向けの案内は書かない。
- 相対パスの `source` は `./` で始め、`..` を含めない。

### E4. marketplace.json（必須）〔公式〕
- `name`・`owner.name`・`plugins[].{name,source,description}` を書く（公式の必須は `description` を除く）。

### E5. 開発時の読み込み〔公式〕
- 二重構造は `claude --plugin-dir ./plugins/<名前>` で読み込む。直下がプラグインなら `claude --plugin-dir .`。

### E6. プラグイン本体の標準配置（推奨）
- `plugins/<PLUGIN>/` の直下に、`.claude-plugin/plugin.json`・`skills/<SKILL>/SKILL.md`・入口スクリプト・依存の固定用のファイルを置く。
- agent は `agents/<名前>.md`、取り込んだものは `NOTICE` に置く（あるときだけ）。
- コード・資源の置き場（`scripts/`、`assets/` など）の名前は、決めて README に書く。
- 細則は、1 スキル用なら `skills/<SKILL>/references/`、共有なら直下の `references/` に置く。
- hooks や `bin/` は、ルート直下に置く。

## F. 検査

### F1. 最低限の検査（必須）
次の内容をテストにする。Python のテストは `~\.claude\rules\python-testing.md` に従う。
1. 全 SKILL.md に frontmatter があり、`name` がディレクトリ名と一致する。
2. SKILL.md に、絶対パス（`C:/Users` など）・`${CLAUDE_SKILL_DIR}` がない。
3. SKILL.md が書く `${CLAUDE_PLUGIN_ROOT}/…` が指すファイルが実在する。
4. 相対リンク・地の文の相対パスがない。
5. MCP を同梱していない（D1）。
6. version が、メタとコードで一致している。
7. 配布に必要なファイルが git 管理下にある。
8. `claude plugin validate <dir> --strict` が通る。

- 単体スキルには、1・2・4 を適用する。3 は `${CLAUDE_SKILL_DIR}/…` の実在を確かめる。

### F2. 追加の検査（推奨）
- SKILL.md に書いたコマンドが実在し、待機や再試行の上限と超えたときの動きが書かれている。
- 廃止したものが残っていない。
- 環境がないときは終了コード 3、置き場がないときは終了コード 2 で止まる。
- 専用 venv を持つプラグインは、リリース前に、A4 の確認とは別に、新規の専用 venv で動くことを確かめる（テストは動かさない。pytest は `requirements.txt` に入っていない）。開発用 venv を有効化せず、PyPI に接続できる環境で、空の使い捨てフォルダを `<PLUGIN>_HOME` にして次を行う。
  1. `setup --yes` が成功する。
  2. `doctor` が終了コード 0 になる。
  3. SKILL.md の最初の入口スクリプト呼び出しを、`--data` を外して実行し、終了コード 0 になる。それが `setup`・`doctor` なら 1・2 と重なるので、次の呼び出しを使う。
- 同じ手順を、README または入口スクリプトが検査する最低限の版の Python で入口スクリプトを起動して行う。その Python を用意できないときは、理由を添えて完了報告に「未検証」と書く。

## H. その他の規則

### H1. 対応 OS を明記する（必須）
- Windows 専用のときは、README と plugin.json の `description` に書く。

### H2. 名前（必須）〔公式〕
- プラグイン名は kebab-case にする。`claude-`・`anthropic-`・`anthropics-`・`cc-plugin-` で始めず、`claude`・`anthropic`・`claude-code` そのものにしない。
- `official` を `claude`・`anthropic` の隣に置かない。
- marketplace 名に、予約語（`inline`・`builtin`・`npm`・`github` など）と `claudeai-` で始まる名前を使わない。

### H3. バージョンと状態の移行（推奨）
- version は semver で付ける。
- `${CLAUDE_PLUGIN_DATA}` の設定ファイルに `schema_version` を入れ、形式を変える版では移行手順を README に書く。

### H4. アンインストールの扱い（推奨）
- 消えるもの（`${CLAUDE_PLUGIN_DATA}`）と残るもの（A8 の共有バイナリ、利用者の成果物）を README に書く。

### H5. 依存の取得元とパス（推奨）
- 依存は公式のレジストリ（PyPI・npm）から取得し、可能ならハッシュも固定する。
- コマンドのパスをクォートし、空白・日本語を含むパスでも動くことをテストで確かめる。

## G. チェックリスト

F1 で検査できない項目を、レビュー時に目視で確認する。
- [ ] A2・A3 状態は `${CLAUDE_PLUGIN_DATA}` に置き、専用 venv は置き場直下の `venv\` に作り、変数は引数で渡している
- [ ] A4 依存をすべて `==` で固定している
- [ ] A5・A6 承認後の `setup --yes`、`doctor`、終了コード 0/1/2/3 がある
- [ ] B1 実行時に `${CLAUDE_PLUGIN_ROOT}` へ書いていない
- [ ] C1・C3 description に 3 点があり、`allowed-tools`・`tools` を絞っている
- [ ] C5 送信・不可逆な書き込み・常駐に `disable-model-invocation: true` がある
- [ ] D2・E1・E4 出典、plugin.json、marketplace.json の項目がある
- [ ] H1・H2 対応 OS を明記し、予約名を使っていない
- [ ] 推奨: A7・A8・B2・C4・C6・E2・E3・E6・F2・H3・H4・H5 を守っている
