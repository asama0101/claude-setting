# スキル・プラグイン作成の共通ルール

Claude Code のスキル・プラグインを作る・変更するときに従う規則。

- **必須**は守る。**推奨**は、守らない理由があれば外してよい。
- 〔公式〕は、公式の仕様に依存する規則を指す。公式の仕様は 2026-11-07 に `code.claude.com/docs` の plugins・skills・sub-agents の各ページで確認した。公式が求めていない、この文書独自の規則には〔公式〕を付けない。
- 個人用で配布しないプラグインは、E と H1〜H3 と F1 の 6 を除いて守る。これらは、配布するときに守る。
- Python の規則（A1・A4・A5・A6・A7・H5 の Python の部分）は、`~/.claude/rules/python-venv.md` の 2 に書く。ただし、venv の位置（A2）と新規環境の検査（F2）は、Python の専用 venv に限った規則で、この文書に書く。Node の扱いは A2 に書く。
- `<PLUGIN>` はプラグイン名、`<SKILL>` はスキル名を表す。環境変数名の `<PLUGIN>_HOME`・`<SKILL>_HOME` では、名前を大文字にし、`-` を `_` に置き換える（`my-plugin` は `MY_PLUGIN_HOME`）。Windows 前提で書く。

## 用語

- **単体スキル**: プラグインに属さないスキル（`~/.claude/skills/<名前>/`、`.claude/skills/`）。その中に `.claude-plugin/plugin.json` を置くと、公式はプラグインとして読み込む。単体スキルは、`plugin.json` を持たないものに限る。
- **専用環境**: プラグイン（単体スキル）だけが使う実行環境。
- **置き場**: 専用環境と状態を置くディレクトリ。プラグインでは `${CLAUDE_PLUGIN_DATA}`。実体は A2 のとおり A7 の優先順で決まる（単体スキルは A9）。
- **入口スクリプト**: SKILL.md が最初に呼ぶスクリプト。標準ライブラリだけで動かす。

## A. 実行環境と状態の置き場

### A1. 専用環境だけで実行する（必須）
- 本体は専用環境の中だけで実行する。システム側の実行環境は、入口スクリプトの起動にだけ使う。
- システム側にライブラリを入れない・読まない。Python の専用 venv の `python.exe` は `-I`（隔離モード）で起動し、`PYTHONPATH` などの環境変数と利用者のサイト設定を読ませない。
- システムの環境と専用環境の、どちらかを選ぶ分岐は作らない。

### A2. 置き場は `${CLAUDE_PLUGIN_DATA}`（必須）〔公式〕
- 専用環境と状態は `${CLAUDE_PLUGIN_DATA}` に置く。
- `${CLAUDE_PLUGIN_ROOT}` には状態を置かない。更新で中身が入れ替わる。
- `claude --plugin-dir` で読み込むと、置き場が本番と別になる。開発時は A7 で固定する。
- 置き場は、1 つのパスで決まる。決め方（優先順）は A7 に従う。通常は `--data "${CLAUDE_PLUGIN_DATA}"` の値で、開発・テストで `<PLUGIN>_HOME` を設定したときはそちらが優先される。
- Python の専用 venv は、入口スクリプトの言語（Python、Node）を問わず、置き場の直下の `venv\` に作る。実行ファイルは `venv\Scripts\python.exe`。
- Node の依存（`node_modules`）は専用 venv の対象外。`package.json` と lockfile（`package-lock.json`）を本体に置き、公式の自動導入（キャッシュの作成時と更新時。lifecycle script は動かず、60 秒が上限）に任せる。`${CLAUDE_PLUGIN_ROOT}` で自分では `npm ci` しない。自動導入で入らない依存（ビルドが要るもの、60 秒で終わらないもの）は、Python と同じ A5 の承認を取って、置き場に入れる。
- venv の位置を、置き場と別に指定する設定（環境変数・引数・設定ファイル）は作らない。置き場を変えたら、venv は新しい置き場の下に作り直す（venv は移動できない）。新しい場所は未承認なので、A5 の承認を取り直してから作る。
- 〔機械〕置き場を空の一時フォルダにして、PyPI に接続できる環境で次を確かめる（F1 の 11 として実行する）。一時フォルダは、(c) で調べる場所の外に作る。
  - (a) `--yes` なしの `setup` が、終了コード 3 で止まり、`venv\` を作らない。
  - (b) `setup --yes` のあと、`<置き場>\venv\Scripts\python.exe` がある。
  - (c) (b) の前後で、`pyvenv.cfg` を含むフォルダの一覧が変わらない。調べる場所は、`${CLAUDE_PLUGIN_ROOT}`（単体スキルは `${CLAUDE_SKILL_DIR}`。実パスに置き換える）と、開発中はリポジトリ直下。再帰するときは `.git`・`node_modules` を除く。
- 同じ置き場に対する `setup --yes` を、複数のセッションが同時に実行することは想定しない。

### A3. 変数は引数で渡す（必須）〔公式〕
- `${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` は、SKILL.md（と agent）の本文に書く。
- 入口スクリプトには引数で渡す。これらの変数は、Bash ツールの環境変数に入らない。

      python -B -I "${CLAUDE_PLUGIN_ROOT}/<入口スクリプト>" --data "${CLAUDE_PLUGIN_DATA}" <サブコマンド>

- `-I` は、入口スクリプトのあるフォルダを `sys.path` に入れない。入口は 1 ファイルにするか、`sys.path` に自分で追加する。

- Node の入口は `python` を `node` に読み替える（C3 の例も同じ）。
- 公式の置換では、Windows のパスは `/` 区切りになる。入口スクリプトは、`/` と `\` の両方を受け付ける。
- 入口を起動する `python` が見つからない（Microsoft Store のスタブなど）ときは、終了コード 3 と区別できない。SKILL.md に、起動できないときの案内（`py -3` の使用など）を書く。

### A4. 依存は `==` で固定する（必須）
- 依存は固定用のファイルで管理し、間接依存も含めてすべて版を固定する（本体の依存だけを入れた venv で `pip freeze` し、`-e` と `@ file://` の行を除いて `requirements.txt` にする。Node は `package-lock.json`）。
- 固定する版は、新しい venv に `requirements.txt` と開発用の依存（`requirements-dev.txt`）を入れて、全テストが通った版にする。F2 の確認は、これとは別の新しい置き場で、`requirements.txt` の依存だけを入れて行う。
- 環境の版がずれたら、終了コード 3 で止まる。再同期は、承認後の `setup --yes` で行う。

### A5. 導入は利用者の承認を得てから（必須）
- 専用環境と、その中への依存の導入は、容量を問わず、すべて承認を得てから行う。ブラウザなど容量が大きいものも同じ。
- 承認を求めるときは、場所・内容・容量を説明する。`setup`（`--yes` なし）は、これらを表示して終了コード 3 で止まる。
- SKILL.md は、`setup`（`--yes` なし）の出力を利用者に見せ、承認を得てから `--yes` を付ける。`allowed-tools` に `setup` を含めない。含めると、承認なしで導入が走る（C3）。
- 任意の依存は、承認を得て導入するか、代替手段を案内して止まる。
- 動かなくなった環境の作り直しも、`setup --yes` で行う。承認を取った置き場だけで作り直す。
- Node の公式の自動導入（A2）は、lifecycle script を動かさず、registry の固定版だけを入れるので、承認の例外とする。

### A6. 入口スクリプトの契約（必須）
- サブコマンド `doctor`（診断のみ。何も変更しない）と `setup`（A5）を持つ。`doctor` は、専用 venv の Python を子プロセスとして起動し、依存を import できるところまで確かめる。
- 終了コード: 0 成功、1 実行時のエラー、2 引数・設定のエラー、3 専用環境が使えない。
- 終了コード 3 のとき、不足の内容と、置き場を含む `setup` の案内を出す。置き場の指定はあるが、そのフォルダがまだないときも、終了コード 3 とする（`setup --yes` が作る。`doctor` は作らない）。
- フック（`hooks`）から入口を呼ぶと、終了コード 2 は「処理を止める」意味になる。フックから呼ぶ入口は、止める必要がない場面では 0 を返して警告だけを出す。
- 専用環境を使わないスクリプトには、これらを求めない。

### A7. 置き場の優先順（優先順は必須。そのほかは推奨）
- 必須: 置き場は、環境変数 `<PLUGIN>_HOME`、引数 `--data <パス>` の順で決める。A2・A9 はこの順に従う。
- 必須: どちらもなければ、`--data` の付け方を表示して終了コード 2 で止まる。フックから呼ぶ場合は、A6 を優先して 0 と警告にする。
- 必須: 環境変数と `--data` の両方があって値が違うときは、環境変数を使い、標準エラーに警告を出す。
- 推奨: 入口スクリプトは、`--data` を取り除き、子プロセスの `<PLUGIN>_HOME` に入れて渡す。
- 推奨: 開発専用の探索（リポジトリ内の環境の自動検出など）は作らない。
- 開発・検査で `<PLUGIN>_HOME` を設定するときは、そのコマンドの環境にだけ設定する。シェルの設定ファイルに残さない（本番の置き場を上書きするため）。

### A8. 巨大な共有バイナリは専用環境の対象外（推奨）
- 100 MB 以上で他のツールと共有できるもの（ブラウザなど）は、専用環境に入れず、そのツールの既定の共有の場所に置く。
- README に「共有で、専用環境の対象外」と書く。

### A9. 単体スキルの場合（必須）〔公式〕
- 単体スキルでは、`${CLAUDE_PLUGIN_ROOT}`・`${CLAUDE_PLUGIN_DATA}` が使えない。代わりに `${CLAUDE_SKILL_DIR}` を使う。
- 置き場は、環境変数 `<SKILL>_HOME`、`%LOCALAPPDATA%\<SKILL>\` の順で決める。既定の場所があるので、終了コード 2 は出ない。同名の単体スキルをユーザー用とプロジェクト用の両方に作らない（置き場が共有される）。
- 専用 venv は、この優先順で決まる置き場の直下の `venv\` に作る（A2 と同じ）。
- 適用する規則: A1・A4・A5・A6・A8・B1・B2・C1・C3〜C6・D1・D2・F1・F2（読み替えは F1・F2 のとおり）・G・H4・H5。A2・A7 は、上の優先順に置き換えて適用する。
- 適用しない規則: A3・C2・E 全体・H1〜H3。

## B. 本体と利用者の成果物の分離

### B1. プラグイン本体は読み取り専用（必須）
- `${CLAUDE_PLUGIN_ROOT}` には、実行時に何も書かない。成果物は作業側、状態は `${CLAUDE_PLUGIN_DATA}` に置く。
- Python は、読み込んだモジュールの `__pycache__` を書く。入口は `python -B -I` で起動し、子プロセスの Python も `-B` で起動する。
- 〔機械〕F1 の 11 の実行全体の前後で、`${CLAUDE_PLUGIN_ROOT}` のファイル一覧が変わらない。

### B2. 作業側へ写したものの更新手段を決める（推奨）
- 本体のファイルを作業側へコピーする設計では、更新を届ける手段を README に書く。
- 消してよいのは、再生成できる派生ファイルだけにする。

## C. SKILL.md / agent の書き方

### C1. frontmatter と description（必須）
- frontmatter に `name` と `description` を書く。`name` はディレクトリ名と一致させる（この文書の規則。公式は一致を求めない。プラグインのスキルでは、`name` がコマンド名の末尾を決める）。
- 〔公式〕description は、スキルの一覧に載り、Claude が使うかどうかの判断に使われる。
- description には、何をするか、使う場面（利用者の言い回し）、使わない場面と代わりに使うスキルの 3 点を書く。
- `disable-model-invocation: true` のスキルは、3 点目を省略してよい。
- 〔公式〕description は `when_to_use` と合わせて 1,536 文字で切られる。
- 上の項目のほかにも、公式には `when_to_use`・`user-invocable`・`disallowed-tools`・`context`・`agent`・`paths` などの項目がある（skills の Frontmatter reference）。未知のキーは警告なしで無視されるので、綴りを確かめる。
- agent の frontmatter にも、`name` と `description` を書く。

### C2. パスの書き方（必須）
- プラグイン内の SKILL.md と agent のコマンドは、`${CLAUDE_PLUGIN_ROOT}/…` を基準に書く。
- 絶対パス、`${CLAUDE_SKILL_DIR}`、相対リンク、地の文の相対パスは書かない。`${CLAUDE_SKILL_DIR}` の禁止は、基準を `${CLAUDE_PLUGIN_ROOT}` に統一するための、この文書の規則である（公式は使えるとしている）。

### C3. 権限を絞る（必須）〔公式〕
- `allowed-tools` は、特定のスクリプトの特定のサブコマンドだけに絞る（例: `Bash(python -B -I "${CLAUDE_PLUGIN_ROOT}/scripts/build.py" --data "${CLAUDE_PLUGIN_DATA}" build *)`。A3 の呼び出しの形に合わせる）。引数を列挙できるときは列挙する。
- `allowed-tools` は、他のツールを禁じない。事前に承認するだけである。`setup` は含めない（`setup *` のような末尾 `*` も、`setup --yes` に一致するので書かない）。
- A5 の承認の確認は、SKILL.md の手順であって、権限の仕組みではない。利用者が広い許可（`Bash(python *)` など）や bypass を設定していると、強制されない。
- `$ARGUMENTS` は、Bash のコマンド文字列に埋め込まない。クォートしても、`"` での脱出や `--yes` の混入を防げない。Write ツールでファイルに書き、パスだけを渡す。
- `Bash(node *)` のような広い許可は書かない。agent の `tools` は、必要なものだけにする。
- MCP は `mcp__<server>__*` でサーバー単位に絞る。
- 使う MCP を利用者が決める（D1）agent は、`tools` を省略してよい。省略すると、メイン会話専用の一部のツールを除いて、利用できるすべてのツールを継承する。理由を、直下の README の安全の節に書く。
- プラグインの agent では、`hooks`・`mcpServers`・`permissionMode`・`initialPrompt` は無視される。

### C4. 細則は references に置く（推奨）
- SKILL.md が 200 行を超えるときは、細則を `references/*.md` に移し、「書く前に読む」と指示する。

### C5. 副作用のあるスキルは自動で起動させない（必須）〔公式〕
- 外部への送信、不可逆な書き込み（削除・上書き）、常駐をするスキルは、`disable-model-invocation: true` にする。常駐には、`monitors` の登録を含む（`monitors` は利用者の権限で、sandbox の外で動く）。
- 依存の導入（`setup`）を呼ぶスキルも、同じにする。
- それ以外の副作用のあるスキル（作業側へのファイル生成など）も、同じにすることを推奨する。

### C6. 重い処理は委譲する（推奨）
- 処理が長いスキルは入口にして、サブエージェントに `$ARGUMENTS` を渡して委譲する。frontmatter の `context: fork` と `agent` で、スキル自体をサブエージェントで実行してもよい。
- 引数が空のときは、不足している内容を利用者に聞き返す。
- `$ARGUMENTS` の渡し方は、C3 に従う。

## D. 外部依存

### D1. MCP は同梱しない（必須）
- `.mcp.json`、`.mcpb` ファイル、plugin.json と marketplace.json の `mcpServers` を置かない。公式は同梱を認めているが、この規則では禁止する。
- 利用者が用意した MCP を使う。禁止の理由は、同梱すると、利用者の承認なしにツールの範囲が広がるため。指定は、`userConfig`（公式の設定項目）か `${CLAUDE_PLUGIN_DATA}` に保存してよい。
- 指定がない、または MCP が使えないときは、代替手段か案内を出して止まる。推測でツールを探さない。

### D2. 取り込んだものの出典を書く（必須）
- 他者の文書・コードを取り込むときは、出典とライセンスを `NOTICE` に書く。README の「出典」節に併記してよいが、README だけでは足りない。
- `NOTICE` はプラグインのルート（二重構造なら `plugins/<名前>/NOTICE`。直下がプラグインなら直下。単体スキルはスキルのディレクトリ）に置く。直下だけでは、キャッシュにコピーされず、利用者が受け取る配布物に入らない。

## E. 配布メタ

### E1. plugin.json（必須）〔公式〕
- `.claude-plugin/plugin.json` に、`name`・`version`・`description`・`author.name` を書く（公式の必須は `name` だけ）。
- version は、メタとコード（`package.json`・`__version__`）で一致させ、更新を届けるときに上げる。〔公式〕version を書くと、文字列を変えるまで利用者に更新が届かない。書かないと、git 管理のソースでは commit SHA が版になる。この文書は、書く（上げる）方針にする。
- agents・skills・commands・hooks を `.claude-plugin/` の中に置かない。読み込まれない。

### E2. 推奨の項目（推奨）
- `license`・`repository`・`keywords` を書く。

### E3. リポジトリの構成（推奨）
- 二重構造を既定とする。`plugins/<名前>/` が本体、marketplace.json の `source` が `./plugins/<名前>` である。
- tests・docs・見本は、本体の外（リポジトリ直下）に置く。
- 直下をプラグインにするのは、tests・docs・見本のない極小のものだけにする。F1 は tests を前提にするので、この場合の F1 は、`claude plugin validate --strict`（8）と目視で代える。`source` は `"."` にする（下の `./` で始める規則の例外）。
- README は直下に 1 つだけ置く。`plugins/<名前>/README.md` は作らない。
- 利用者向けの詳細（H1・H4・A8・D2・H3・B2）を、直下の README に書く。開発者向けの案内は書かない。
- 相対パスの `source` は `./` で始め、`..` を含めない。

### E4. marketplace.json（必須）〔公式〕
- `name`・`owner.name`・`plugins[].{name,source,description}` を書く（公式の必須は `description` を除く）。`plugins[].version` は書かない（plugin.json の version が優先され、二重管理になる）。

### E5. 開発時の読み込み〔公式〕
- 二重構造は `claude --plugin-dir ./plugins/<名前>` で読み込む。直下がプラグインなら `claude --plugin-dir .`。

### E6. プラグイン本体の標準配置（推奨）
- `plugins/<PLUGIN>/` の直下に、`.claude-plugin/plugin.json`・`skills/<SKILL>/SKILL.md`・入口スクリプト・依存の固定用のファイルを置く。
- agent は `agents/<名前>.md`、取り込んだものは `NOTICE` に置く（あるときだけ）。
- コード・資源の置き場（`scripts/`、`assets/` など）の名前は、決めて README に書く。
- 細則は、1 スキル用なら `skills/<SKILL>/references/`、共有なら直下の `references/` に置く。
- hooks や `bin/` は、ルート直下に置く。`hooks/hooks.json` は、最上位の `"hooks"` キーで包む（包まないと読み込まれない）。hooks と `bin/` のコマンドも、C2 に準じて書く。F1 では検査しないので、G で目視する。

## F. 検査

### F1. 最低限の検査（必須）
次の内容をテストにする。Python のテストは `~/.claude/rules/python-testing.md` に従う。
1. 全 SKILL.md に frontmatter があり、`name` がディレクトリ名と一致する。
2. SKILL.md と agent に、絶対パス（`C:/Users` など）がない。プラグイン内では、`${CLAUDE_SKILL_DIR}` もない。
3. SKILL.md が書く `${CLAUDE_PLUGIN_ROOT}/…` が指すファイルが実在する。
4. 相対リンク・地の文の相対パスがない。
5. MCP を同梱していない（D1）。
6. version が、メタとコードで一致している（配布するとき）。
7. 配布に必要なファイルが git 管理下にある。
8. `claude plugin validate <dir> --strict` が終了コード 0 で通る。

専用環境を持つ場合は、さらに次もテストにする。
9. `requirements.txt` に `==` のない行がない（Node は lockfile がある）。
10. 環境がないときに入口スクリプトが終了コード 3、置き場の指定がないときに終了コード 2（単体スキルを除く）で止まる。
11. A2 の〔機械〕(a)〜(c)。実行の前後で `${CLAUDE_PLUGIN_ROOT}` のファイル一覧が変わらないこと（B1）も、同じ実行で確かめる。

- 単体スキルには、1・2・4を適用し、専用環境を持つ場合は 9〜11 も適用する。2 は絶対パスだけを調べ、`${CLAUDE_SKILL_DIR}` は調べない。3 は `${CLAUDE_SKILL_DIR}/…` の実在を確かめる。5〜8 は適用しない。

### F2. 追加の検査（推奨）
- SKILL.md に書いたコマンドが実在し、待機や再試行の上限と超えたときの動きが書かれている。
- 廃止したものが残っていない。
- 専用 venv を持つプラグインは、リリース前に、A4 の確認とは別に、新規の専用 venv で動くことを確かめる（新規 venv の中ではテストを動かさない）。開発用 venv を有効化せず、PyPI に接続できる環境で、空の使い捨てフォルダを `<PLUGIN>_HOME` にして次を行う。
  1. `setup --yes` が成功する。
  2. `doctor` が終了コード 0 になる。
  3. SKILL.md が最初に呼ぶ入口スクリプトのサブコマンドが、読み取りだけで副作用のないものなら、それを実行して終了コード 0 になる。次のものは除く: `setup`・`doctor`、A5 の承認が要るもの、外部サービスや利用者の入力値が要るもの、C5 の副作用があるもの、仕様上 0 以外を返すもの。`${CLAUDE_PLUGIN_ROOT}` を実パスに置き換え、`--data` の代わりに `<PLUGIN>_HOME` で置き場を渡す。該当するものがなければ、この手順を省き、完了報告に「手順 3 は該当なし」と書く。専用 venv の起動の確認は、手順 2 の `doctor`（A6）が担う。
- 同じ手順を、README または入口スクリプトが検査する最低限の版の Python で入口スクリプトを起動して行う。使い捨てフォルダは版ごとに新しい空のものにする。その Python を用意できないときは、理由を添えて完了報告に「未検証」と書く。
- 単体スキルは、A9 に従って読み替えて同じ確認を行う。`${CLAUDE_PLUGIN_ROOT}` は `${CLAUDE_SKILL_DIR}`、`<PLUGIN>_HOME` は `<SKILL>_HOME` にする。A3 の `--data` はないので、手順 3 の `--data` は付けず、置き場は `<SKILL>_HOME` だけで渡す（既定の `%LOCALAPPDATA%\<SKILL>\` は使わない）。

## G. チェックリスト

F1 に入れていない項目を、レビュー時に目視で確認する。
- [ ] A1 専用環境の中だけで実行し、Python は `-I` で起動している
- [ ] A2・A3・A7 状態は `${CLAUDE_PLUGIN_DATA}` に置き、専用 venv は置き場直下の `venv\` に作り、変数は引数で渡し、置き場の優先順に従っている
- [ ] A4 依存をすべて `==` で固定している
- [ ] A5・A6 承認後の `setup --yes`（`allowed-tools` に含めていない）、`doctor`、終了コード 0/1/2/3 がある
- [ ] B1 実行時に `${CLAUDE_PLUGIN_ROOT}` へ書いていない
- [ ] C1・C3 description に 3 点があり、`allowed-tools`・`tools` を絞っている
- [ ] C5 送信・不可逆な書き込み・常駐に `disable-model-invocation: true` がある
- [ ] A9 単体スキルは、適用する規則の一覧に従っている
- [ ] C3 `$ARGUMENTS` を Bash の文字列に埋め込んでいない。`allowed-tools` に `setup` を含めていない
- [ ] D2・E1・E4 出典（`NOTICE`）、plugin.json、marketplace.json の項目がある
- [ ] E6 hooks と `bin/` を使うとき、C2 に準じて書いている
- [ ] A9 単体スキルの既定の置き場（`%LOCALAPPDATA%\<SKILL>\`）で動く（F2 では検査しない）
- [ ] H1・H2 対応 OS を明記し、予約名を使っていない
- [ ] 推奨: A7 の推奨部分・A8・B2・C4・C6（委譲）・E2・E3・E6・F2・H3・H4・H5 を守っている

## H. その他の規則

### H1. 対応 OS を明記する（必須）
- Windows 専用のときは、README と plugin.json の `description` に書く。

### H2. 名前（必須）〔公式〕
- プラグイン名は kebab-case にする。`claude-`・`anthropic-`・`anthropics-`・`cc-plugin-` で始めず、`claude`・`anthropic`・`anthropics`・`claude-code`・`claude-mods` そのものにしない。`claude`・`anthropic`・`anthropics` を単語として含む名前は、warning になる。`--strict`（F1 の 8）で落ちるので使わない。
- `official` を `claude`・`anthropic` の隣に置かない。
- marketplace 名に、予約語を使わない。予約語は、`inline`・`builtin`・`skills-dir`・`synced`・`claude-plugin-test`・`npm`・`pip`・`uv`・`cargo`・`github`・`gh`・公式の marketplace 名（`claude-plugins-official` など）・`claude-community`・`healthcare`・`anthropic-plugin-directory`・`claude-plugin-directory`・JavaScript の prototype 名（`constructor` など）・なりすましに見える名前（`official-claude-plugins` など）。`claudeai-` で始まる名前も使わない。一覧の正本は、公式の marketplace-reference の「Reserved names」である。

### H3. バージョンと状態の移行（推奨）
- version は semver で付ける。
- `${CLAUDE_PLUGIN_DATA}` の設定ファイルに `schema_version` を入れ、形式を変える版では移行手順を README に書く。

### H4. アンインストールの扱い（推奨）
- 消えるもの（`${CLAUDE_PLUGIN_DATA}`）と残るもの（A8 の共有バイナリ、利用者の成果物）を README に書く。

### H5. 依存の取得元とパス（推奨）
- 依存は公式のレジストリ（PyPI・npm）から取得し、可能ならハッシュも固定する。
- コマンドのパスをクォートし、空白・日本語を含むパスでも動くことをテストで確かめる。
