# スキル・プラグイン作成の共通ルール

スキル・プラグインを作る・変更するときに従う規則。

- **必須**は守る。**推奨**は、理由があれば外してよい。〔公式〕は、公式の仕様に依存する規則。

## 用語

- **単体スキル**: プラグインに属さないスキル。`plugin.json` を置くと、公式はプラグインとして読む。

## A. 状態と変数

### A1. 状態は `${CLAUDE_PLUGIN_DATA}` に置く（必須）〔公式〕
- 状態は `${CLAUDE_PLUGIN_DATA}` に置く。成果物は作業側に置く。
- `${CLAUDE_PLUGIN_ROOT}` は更新で入れ替わるので、実行時に何も書かない。
- `--plugin-dir` では、`${CLAUDE_PLUGIN_DATA}` が本番と別になる。

### A2. 変数は引数で渡す（必須）〔公式〕
- 変数は SKILL.md と agent の本文に書き、スクリプトには引数で渡す。Bash の環境変数には入らない。

      <起動コマンド> "${CLAUDE_PLUGIN_ROOT}/<スクリプト>" --data "${CLAUDE_PLUGIN_DATA}" <サブコマンド>

- 起動コマンドが見つからないときの案内を、SKILL.md に書く。

### A3. 単体スキル（必須）〔公式〕
- `${CLAUDE_SKILL_DIR}` を使う（`${CLAUDE_PLUGIN_*}` は使えない）。
- 状態は、OS の既定の場所に置く。Windows は `%LOCALAPPDATA%\<スキル名>\`、Linux は `${XDG_DATA_HOME:-$HOME/.local/share}/<スキル名>/`。同名のスキルを、ユーザー用とプロジェクト用の両方に作らない。
- A2・B2・D・G1・G2 は適用しない。他は読み替えて適用する。

## B. SKILL.md / agent

### B1. frontmatter と description（必須）
- `name` と `description` を書く。`name` はディレクトリ名と一致させる（独自の規則）。
- description に、何をするか、使う場面（利用者の言い回し）、使わない場面と代わりのスキルを書く。`disable-model-invocation: true` なら、最後は省く。
- 〔公式〕description は `when_to_use` と合わせて 1,536 文字で切れる。未知のキーは無視されるので、綴りを確かめる。

### B2. パスの書き方（必須）
- プラグイン内のコマンドは、`${CLAUDE_PLUGIN_ROOT}/…` を基準にする。
- 絶対パス、`${CLAUDE_SKILL_DIR}`、相対リンク、地の文の相対パスは書かない（基準を統一する独自の規則）。

### B3. 権限を絞る（必須）〔公式〕
- `allowed-tools` は、特定のスクリプトの特定のサブコマンドだけにする（例: `Bash(<起動コマンド> "${CLAUDE_PLUGIN_ROOT}/scripts/build" --data "${CLAUDE_PLUGIN_DATA}" build *)`）。`Bash(<起動コマンド> *)` のような広い許可は書かない。`allowed-tools` は事前承認で、他を禁じない。
- `$ARGUMENTS` は、Bash の文字列に埋め込まない（`"` での脱出で、別の引数が混入する）。ファイルに書き、パスを渡す。
- agent の `tools` は、必要なものだけにする。MCP は `mcp__<server>__*` で絞る。MCP を利用者が決める agent だけは、省略してよい（全ツールを継承する。理由を README に書く）。
- プラグインの agent では、`hooks`・`mcpServers`・`permissionMode`・`initialPrompt` は無視される。

### B4. 副作用のあるスキルは自動起動させない（必須）〔公式〕
- 外部への送信、不可逆な書き込み、常駐（`monitors` を含む）をするスキルは、`disable-model-invocation: true` にする。

## C. 出典

### C1. 出典を書く（必須）
- 取り込んだ文書・コードの出典とライセンスは、プラグインのルート（`plugins/<名前>/NOTICE`）に書く。直下の README は配布物に入らない。

## D. 配布

### D1. plugin.json（必須）〔公式〕
- `.claude-plugin/plugin.json` に `name`・`version`・`description`・`author.name` を書く（公式の必須は `name`）。
- version は、メタとコードで一致させ、更新を届けるときに上げる（書くと、変えるまで更新は届かない）。
- agents・skills・commands・hooks は、`.claude-plugin/` に置かない。

### D2. リポジトリの構成（推奨）
- 本体は `plugins/<名前>/`、`source` は `./plugins/<名前>`（`./` で始め、`..` を含めない）。tests・docs は直下に置く。
- 直下をプラグインにするのは、tests・docs のない極小のものだけ。`source` は `"."`、E1 は `validate --strict` と目視で代える。
- README は直下に 1 つ。対応 OS と、消えるもの・残るものを書く。

### D3. marketplace.json（必須）〔公式〕
- `name`・`owner.name`・`plugins[].{name,source,description}` を書く。`plugins[].version` は書かない。

### D4. 配置と読み込み（推奨）
- `plugins/<PLUGIN>/` 直下に、`.claude-plugin/plugin.json`・`skills/<SKILL>/SKILL.md`・スクリプト・依存の固定ファイルを置く。agent は `agents/`、hooks と `bin/` はルート直下。
- `hooks/hooks.json` は、最上位の `"hooks"` キーで包む（包まないと読まれない）。
- 開発は `claude --plugin-dir ./plugins/<名前>`（直下がプラグインなら `.`）。〔公式〕

## E. 検査

### E1. 最低限の検査（必須）
次をテストにする。
1. 全 SKILL.md に frontmatter があり、`name` がディレクトリ名と一致する。
2. SKILL.md と agent に絶対パスがない。プラグイン内では `${CLAUDE_SKILL_DIR}` もない。
3. `${CLAUDE_PLUGIN_ROOT}/…` が指すファイルが実在する。
4. 相対リンク・地の文の相対パスがない。
5. version が、メタとコードで一致する。
6. 配布に必要なファイルが git 管理下にある。
7. `claude plugin validate <dir> --strict` が終了コード 0 で通る。

- 単体スキルは、1・2・4を適用する。2は絶対パスのみ。3は `${CLAUDE_SKILL_DIR}/…`。

### E2. 追加の検査（推奨）
- SKILL.md のコマンドが実在し、待機・再試行の上限と、超えたときの動きが書かれている。廃止したものが残っていない。

## F. チェックリスト

E1 にない項目を、レビューで目視する。
- [ ] A1・A2 状態は `${CLAUDE_PLUGIN_DATA}` に置き、変数は引数で渡している
- [ ] B1・B3・B4 description が揃い、`allowed-tools`・`tools` を絞り、`$ARGUMENTS` を埋め込まず、副作用に `disable-model-invocation: true` がある
- [ ] C1・D1・D3 `NOTICE`、plugin.json、marketplace.json がある
- [ ] D4 hooks と `bin/` のコマンドを B2 に準じて書いている
- [ ] G1・G2 対応 OS を明記し、予約名を使っていない
- [ ] 推奨: D2・D4・E2・G3

## G. その他

### G1. 対応 OS を明記する（必須）
- Windows 専用なら、README と plugin.json の `description` に書く。

### G2. 名前（必須）〔公式〕
- プラグイン名は kebab-case。`claude-`・`anthropic-`・`anthropics-`・`cc-plugin-` で始めず、`claude`・`anthropic`・`anthropics`・`claude-code`・`claude-mods` そのものにしない。`official` を `claude`・`anthropic` の隣に置かない。
- marketplace 名に、公式の「Reserved names」（`inline`・`builtin`・`npm`・`github` など）と、`claudeai-` で始まる名前を使わない。

### G3. 依存の取得元とパス（推奨）
- 依存は公式のレジストリから取得し、可能ならハッシュも固定する。
- パスをクォートし、空白・日本語のパスでも動くことをテストする。
