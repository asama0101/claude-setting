---
status: 未対応
plan: （未作成）
---
# SPEC: Claude Code の作業環境の整備（要件 A〜F）

最初の依頼と、途中で加わった要望を、要素に分解し、似たものをまとめて、真の要望から組み上げ直した SPEC（第 2 版。レビュー 5 体の指摘を反映）。以前の SPEC 4 件を置き換える。以前の実装はすべて破棄済みで、この SPEC から始める。

## 概要

### 真の要望
| 要件 | 真の要望 | 元の要望（要素 ID） |
| --- | --- | --- |
| A 安全と承認の最適化 | permissions で防ぐのは、秘密情報の閲覧・編集と、修復できない破壊的コマンドだけにする（承認疲れを減らしつつ、事故を防ぐ） | R2-1・R2-2・L3-1〜L3-3・L4・L5 |
| B 作業の見える化 | いま何を送って、何を聞かれ、何が変わったかを、サイド UI パネルに出したままにする。よく送る文は、定型文として残す | R3-8・R6・N1〜N4 |
| C 見落としの防止 | **取り下げ**（B-2 の解説が、質問に限って担う。脱線の防止は、R5 の取り下げにより、担う要件がない） | R4-2 |
| D 繰り返しの手間の削減 | **B-3 に統合**（定型文を残せる） | R6 |
| E 規約の一元化 | 規約を 1 か所に集め、重複と矛盾をなくす | R1・L1・L2 |
| F 拡張の影響の把握 | 入れた拡張が、環境とデザインにどう効くかを知り、入れる前に判断できる | R2-1・R4-1・R7 |

### 要素 ID の定義
- R1 開発用 venv をリポジトリ直下に作り、`.gitignore` の対象にする（規約の有無も知る）。R2-1 blast-radius を取り込む。R2-2 permissions を棚卸する。
- R3-1 作業コンテキストの常駐。R3-2 読み込まれているファイルの一覧。R3-3 README・docs の更新案の自動提示。R3-4 ステージごとのライブ進捗バー。R3-5 成果物の一覧。R3-6 変更差分（GitHub 方式）。R3-7 ファイル内容の確認（MD/HTML はプレビュー）。R3-8 prompt-rail・qa-guide を参照する（B の「参照元」の節）。
- R4-1 公式「You should know」の取り込み。R4-2 （ユーザーの指定）同名の mod で、サイドエージェントが会話と出力を監視し（取り下げ。B-2 に一部が残る）、見落としそうな情報を入力欄の上にメモで出す。R5 「今日の目標」の固定。R6 定型文 3 つ。R7 frontend-design が Artifact のデザインに影響するかの確認。
- N1〜N5（第 3 版で、ユーザーが B の要望として出し直したもの）: N1 prompt-rail を参考に、送ったプロンプトを履歴として残す。N2 qa-guide を参考に、AskUserQuestion の選択肢に AI の解説（指示の要約、なぜ今この質問か）を出す。N3 よく送るプロンプトを、定型文として残せる（残りのタスク確認、選択肢のメリット・デメリット・影響の提示）。N4 ファイルの変更内容を GitHub 形式で表示する。N5 SPEC・実装計画の進捗状況を見える化する（取り下げ）。
- L1 `plugin-rules.md` から Python・venv の記載を消し、Python の規約を参照させる。L2 `pptx-deck\CLAUDE.md` の venv の記載を消す。L3-1 permissions を緩める。L3-2 README の hook をやめる。L3-3 コミット・PR 作成・push の確認を省く（方針変更: `CLAUDE.md` の「Git」の節を消す）。L4 秘密を含みうるファイルの deny を足す。L5 blast-radius の動作を知る → 壊れていたので、アンインストールした（原因は未調査）。のち、取り下げ。

### 元の要望との差
| 要素 | 差 |
| --- | --- |
| R3-1〜R3-3・R3-5・R3-7 | **取り下げ**（第 3 版。コンテキスト、README 更新案、成果物の一覧、ファイル内容の確認は、N1〜N5 に置き換える） |
| R3-4・N5 | **取り下げ**（第 3 版の実機確認のあと、ユーザーの判断。「完了」の確かな根拠がなかったため。下の B-5 の経緯） |
| R3-6 | N4 で**復活**（第 3 版。GitHub 形式の差分） |
| R5 | **取り下げ**（ユーザーの判断） |
| R2-1 | **取り下げ**（ユーザーの判断。A-5）。blast-radius は壊れていた（原因は未調査）ため、アンインストールした。再導入しない |
| R2-2 | 手作業の棚卸（blast-radius は棚卸ツールではなかった）。反映は承認後 |
| R4-1・R4-2 | 公式は公開情報で確認できなかった。R4-2（見落とし防止のメモ）は取り下げ。B-2 の解説が、AskUserQuestion の質問に限って近い役割を担う |
| L3-1 | 方針: permissions で防ぐのは、秘密情報と、修復できない破壊的コマンドだけ（A）。依頼にない追加: A-1（`rm` と `git switch --discard-changes` の ask） |
| 依頼にない追加 | 会話の一部を haiku に送る（B-2。常時有効、設定なし）、mod は `--plugin-dir` で読み込む（設定への登録はしない） |

### 進め方の方針（G）
- 質問は、短く、1 つずつ。
- 要件ごとに、**テストを先に書き**、単独で完了と検証ができる単位に分ける。各単位の終わりに、ユーザーの承認を取る。ブランチ上で小さくコミットし、戻せるようにする（実装をまとめて破棄することを避ける）。
- 修復できない操作（破棄・削除など）は、範囲を示して確認してから行う。
- 動作を確かめる方法を決めてから実装する。確かめられないものは、「未検証」と明記する。
- 一時物は、スクラッチパッドか OS の一時フォルダに置く。既存の `py -m pytest -q` の全件が、変更の前後で通ること。
- 破棄の原因: 不明（ユーザーの判断。実装は、要件の前提が途中で変わり、確認も多く出たため、SPEC から作り直すことになった、と推定）。

### 取り下げと確認できなかったもの
- 取り下げ（ユーザーの判断）: 変更差分の表示（R3-6）、今日の目標（R5）。
- 確認できなかった: Anthropic 公式の「You should know」（公開リポジトリに存在しない。調べた範囲: anthropics/claude-code と claude-plugins-official）。

## 要件と受入条件

確認の方法の区分: 〔機械〕コマンドで確かめる。〔操作〕ユーザーの操作が要る（できなければ「未検証」と明記する）。検証のコマンドは、Git Bash のパス形式（`/c/...`）で書く。

### A 安全と承認の最適化

**A 全体の方針: `settings.json` の permissions で防ぐのは、「秘密情報の閲覧・編集」と「修復できない破壊的コマンド」だけ。** それ以外（`git push`・`git tag`・`gh pr merge`・`gh release create`・`git commit` など、修復できる操作）は、permissions では止めない。安全網の mod（blast-radius など）は取り下げる。

**A-1 修復できない破壊的コマンドは、確認なしには実行されない。**

| 操作 | 止める仕組み |
| --- | --- |
| `rm -r`・`rm -rf`・`rm -fr` | ask（**追加**） |
| `git switch --discard-changes`・`-f`・`--force`（未コミット変更の破棄） | ask（**追加**） |
| `git reset --hard`・`git clean`・`git checkout --`・`git restore`・`git checkout .` | ask（既存） |
| `git push --force`、既定ブランチへの `git push` | hook（`git_flow.py`）が拒否する（既存・変更なし。承認では実行できず、ユーザーが `!` で実行する） |
| 秘密情報の閲覧・編集 | deny（A-3） |

- 受入条件: ① `settings.json` の ask に、表の ask のパターンが全て入っている（スクリプトで照合）〔機械〕。② 一時リポジトリで、`git switch --force` が ask になる（ask が allow より優先される）。確かめられなければ、allow を `Bash(git switch -c *)` に絞る〔操作または機械〕。③ 代表の 2 操作（一時フォルダの `rm -rf`、`git reset --hard`）で、確認が出て、承認で実行・拒否で中止になる。auto mode での挙動を記録する（確認できなければ「未検証」）〔操作〕。

**A-2 permissions の allow と ask を、上の方針に合わせる。**
- allow に追加（全文）: `Bash(py -m pytest *)`・`Bash(py -m ruff *)`・`Bash(git add *)`・`Bash(git switch *)`・`Bash(git commit *)`。
- ask から外す: `Bash(git push *)`・`Bash(git tag *)`・`Bash(gh pr merge *)`・`Bash(gh release create *)`（修復できる操作のため）。
- 結果の件数: allow 16、ask 11（`git reset --hard *`・`git clean *`・`git checkout -- *`・`git restore *`・`git checkout .`・`rm -r *`・`rm -rf *`・`rm -fr *`・`git switch --discard-changes *`・`git switch -f *`・`git switch --force *`）。
- 受入条件: `settings.json` の allow・ask が上のとおり〔機械〕。新しいセッションで、`py -m pytest` と `git add` が確認なしに実行される〔操作〕。
- 限界: Stop の hook（`git_flow.py`）は、応答の終了ごとに、コミットと push の確認を求め続ける（A-6）。

**A-3 秘密を含みうるファイルの読み書きを deny する。** 既存の 56 件に、次の 12 件を追加して 68 件にする。
- Read: `**/.aws/config`・`**/.git/config`・`**/*.jks`・`**/*.keystore`・`**/credentials*`。
- Edit（Read だけだった既存の規則の対）: `**/AppData/Local/Microsoft/Credentials/**`・`**/AppData/Roaming/Microsoft/Credentials/**`・`**/AppData/Roaming/Microsoft/Protect/**`・`**/System32/config/SAM`・`**/System32/config/SYSTEM`・`**/System32/config/SECURITY`・`**/NTUSER.DAT`。
- 受入条件: 上の 12 件が追加され、既存の 56 件が残り、合計 68 件で、重複がない（スクリプトで照合）〔機械〕。deny した Read が拒否される〔操作〕。
- 注意: `credentials*` は、`credentials.md` のような普通の文書も止める。`.git/config` の Read の deny は、Claude の Read ツールだけに効き、`git remote -v` などの Bash には効かない。

**A-4 permissions を棚卸し、所見と提案を報告する（反映は承認後）。** 報告は `docs\permissions-audit-2026-11-03.md` に残す（公開リポジトリのため、設定行は引用せず、規則名と行番号だけ。ユーザー名・個人のパスを転記しない）。
- 受入条件: 5 観点（過剰な allow・deny の漏れ・ask の妥当性・重複と矛盾・2 ファイルの一致）の所見と、「対象ルール・変更案・理由」の提案の表がある。`scan_secrets` と `C:\Users\` の `grep` で、秘密と個人のパスがない。棚卸の前後（A の他の変更の前に）で、2 つの `settings.json` の SHA-256 が同一〔機械〕。
- 「2 ファイルの一致」の定義: `permissions` の allow・ask・deny の集合と、`hooks`。`enabledPlugins`・`extraKnownMarketplaces`・`attribution` の差は、報告にとどめる。

**A-5 blast-radius は取り下げる（ユーザーの判断）。** 導入しない。保留中のエラーで常に拒否され、アンインストールした（原因は未調査のまま、調べない）。`rm` などの破壊的コマンドは、A-1 の ask が担う。

**A-6 hook: README の更新漏れの促し（`readme_guard.py`）をやめる。** `settings.json` の hooks から、PostToolUse の `record` と Stop の `check` の 2 つの呼び出しを外す。`git_flow.py` の 4 種の hook（SessionStart・PreToolUse・PostToolUse・Stop）と、`readme_guard.py` のファイルは変えない。
- 受入条件: hooks に `readme_guard` がなく、`git_flow.py` の 4 種が残っている〔機械〕。README の記述（11 行の機能、140〜144 行の `Test-Path`）を事実に合わせる。

**A-7 `CLAUDE.md` から、「Git」の節（`## Git` の見出しと 2 項目）と、「安全」の節（`## 安全` の見出しと 6 項目。ユーザーの追加指示）を消す。** 「安全」の節の 6 項目は、削除・上書き前の中身の確認、秘密情報のマスク、テストを弱めない規則、期待値の変更の規則、無関係な失敗の報告、一時ファイルの置き場。`rules\python-style.md` の「安全」への参照も直す。 消す内容は、「確認なしにコミット・push・PR 作成・マージ・タグ作成・リモートのブランチ削除をしない」と、「コミットメッセージの慣習（Conventional Commits）」の 2 項目。
- 「Git」を参照している 3 か所（「確認の基準」の 2 項目、「ユーザーへの確認方法」の 1 項目）から、「Git」の語を取り除く。「リファレンス」の `git-flow.md` の行は残す。
- 受入条件: `CLAUDE.md` に `## Git` と、節としての「Git」への参照がない。`global-CLAUDE.md` と `~\.claude\CLAUDE.md` が `cmp` で同一。他の節に矛盾する記述がない（全文を `grep`）〔機械〕。
- 影響: コミット・push・PR 作成・マージの確認は、「確認の基準」（外部への公開・送信）と `git_flow.py` の hook だけが担う。コミットメッセージの既定の形式は、`git-flow.md` にあれば、それに従う。

### B 作業の見える化（mod `session-desk`。対象はターミナル、Windows、Claude Code 2.1.287 以降）

**方針（第 3 版で書き直し）**: サイド UI パネル 1 つに、4 つのタブ（履歴・解説・定型文・変更）を置く。パネルは、端末の幅が 144 列以上のときに出る。旧 B-1〜B-4・C-1・D-1 は、この節に置き換える（旧 B-1 コンテキスト、旧 B-2 成果物、旧 B-3 ドキュメント候補、旧 C-1 見落とし防止のメモは、取り下げ）。

**mod の構成**（第 1 版の実装は破棄済み。旧実装の `lib.ts`・テスト補助・描画の部品は参考にしてよい。新規にテストを先に書く）
- 置き場: リポジトリの `mods/session-desk/`。開発は `~/.claude/dev-mods/<セッション ID>/session-desk/` で行い、完成後に一方向にコピーする。使うときは `claude --plugin-dir "./mods/session-desk"`。
- ファイル: `.claude-plugin/plugin.json`、`hooks/hooks.json`、`hooks/register.tsx`、`hooks/lib.ts`（純粋な処理）、`types/index.d.ts`、`tsconfig.json`、テスト（`hooks/*.test.tsx`）。
- フックのイベント: `session.start`（パネルを開く）、`prompt.submit`（履歴）、`tool.call`（`AskUserQuestion` の解説）、`classic.PostToolUse`（Edit・Write・NotebookEdit の変更ファイル）、`ui.render`（Pane）。
- 状態: 履歴・解説・変更ファイル・選択中のタブは `atom`（セッションの中。ホットリロードでは残り、セッションの終了で消える）。定型文は `$.store`（セッションをまたいで残る）。
- 検証コマンド: `claude plugin validate <mod>`、`tsc -p <mod>`、`claude plugin test <mod>`。

| ID | 要件 | 受入条件 |
| --- | --- | --- |
| B-1 履歴 | 送ったプロンプトを、新しい順に番号つきで一覧する（1 件は先頭 60 字。選ぶと全文を展開する）。セッションの中だけ残す | テスト（送った順に記録される、重複を潰さない、60 字で切る、展開する）〔機械〕。実機で、プロンプトを送ると一覧に増える〔操作〕 |
| B-2 解説 | Claude が `AskUserQuestion` で選択肢を出したとき、解説をパネルに出す。内容は、①指示の要約 ②なぜ今この質問をしているか ③各選択肢を選んだときの影響 ④推奨の 1 行。質問の画面は、解説を待たずに出す（解説は後から表示される） | テスト（質問が出ると 1 回だけ解説の呼び出しが始まる、画面は待たない、失敗しても質問は進む、返答の検証と切り詰め）〔機械〕。実機で、質問のたびに解説が出る〔操作〕 |
| B-3 定型文 | パネルの「定型文」タブに、定型文の一覧を出し、押すとその文言をそのまま送信する。履歴の各行の「定型文に追加」と、定型文の各行の「削除」で、増減できる。セッションをまたいで残る。初期値は、3 つ: 「残りのタスクは？」「選択肢ごとにメリット・デメリットを明確にして推奨および影響をレポートして」「Artifact使ってデザインを見せて」 | テスト（初期値が上の 3 つと一致、追加、重複の追加は 1 件、削除、押すと文言が送信される、保存して読み直せる）〔機械〕。実機で、追加した定型文が次のセッションにも残る〔操作〕 |
| B-4 変更 | セッションの中で Edit・Write・NotebookEdit したファイルの一覧を出し、選ぶと変更内容を GitHub 形式の差分で出す: ファイル名、ハンクの見出し、追加行を緑の `+`、削除行を赤の `-`、前後の文脈 3 行。新規ファイルは全行が追加。1 ファイル 500 行まで | テスト（追加・削除・文脈の描き分け、新規ファイル、500 行の切り詰め）〔機械〕。実機で、編集したファイルの差分が出る〔操作〕 |
| B-5 進捗 | **取り下げ**（ユーザーの判断）。実装して実機で見たが、「進捗」の根拠が確実でなかった: 計画のチェックボックスは、実行用のスキル（superpowers の executing-plans）の手順に、付ける指示がない。実行の台帳（`progress.md`）は、スクリプト `task-done` がテスト通過時だけ書くが、テストの中身は保証せず、計画の完了後に削除され、SPEC から直接実装する作業にはない。確実な根拠は、git のコミットとテストの合否だけだった。再開する場合は、根拠（コミット件名の要件 ID、またはテストの対応表）から決める。実装は削除済み | なし（取り下げ） |

**B-2 の補足**
- 呼び出し: `$.model.complete` で haiku を使う。入力は、質問と選択肢、直近のプロンプト最大 5 件（各 4000 文字まで、末尾側を残す）。ツールの結果は含めない。1 つの質問につき 1 回。1 セッション最大 30 回。タイムアウト 8 秒。呼び出しに失敗したら、解説を出さず、他の機能は動き続ける。
- 送る前に、次の 7 種をマスクする: `sk-` の鍵、`AKIA` の鍵、`ghp_` のトークン、`Bearer` のトークン、`password`・`token`・`api_key` などの代入、`://user:pass@` を含む接続文字列、メールアドレス。氏名・電話番号・住所は、マスクしない。
- 返答は、JSON として読み、4 項目（要約・理由・選択肢ごとの影響・推奨）の型と長さ（各 200 字）を検証する。制御文字を除く。
- 保存: マスク前の原文を、状態・ログ・ファイル・エラーメッセージに残さない。
- 受容: 承認によって、次を受容する。マスクは完全ではなく、個人情報と貼り付けたコード中の秘密は漏れうる。会話の一部が、設定なしで常に別のモデル呼び出しに送られる。止めるには mod 全体を読み込まない。受容は、決定ログに記録する。

**B-4 の補足**
- 差分の出どころ: `git diff HEAD -- <ファイル>`（`$.process.run`。実行は作業ディレクトリ）。Git のリポジトリでないときは、「差分を出せない」と表示する。
- 秘密のファイル名（A-3 の deny と同じ種類）・作業ディレクトリ外（実パスで判定）・1MB 超・UTF-8 以外は、内容を出さない。
- Claude Code に、組み込みの `/diff`（端末幅 110 列以上）がある。この要件は、それと別に、パネルに常駐させるためのもの。

**参照元**: prompt-rail（B-1・B-3）、claude_qamods の qa-guide（B-2）は、考え方のみ参考にする。コードは流用しない（レビューで確認）。

**取り下げ**: 旧 B-1 コンテキスト、旧 B-2 成果物、旧 B-3 ドキュメント候補、旧 B-4 のタスクの完了数の進捗バー、B-5 の進捗（上の経緯）、旧 C-1 見落とし防止のメモ、旧 D-1 の固定のボタン 3 つ（B-3 の初期値として残る）。

### E 規約の一元化

| ID | 要件 | 受入条件 |
| --- | --- | --- |
| E-1 | 開発用 venv の規則を `rules\python-venv.md` に書く: リポジトリ直下の `.venv/` に作り、`.gitignore` に入れる。既存の別名は、そのまま使ってよい。このリポジトリには venv を作らない（規則を書くだけ）。規約の有無の答えは、「開発用 venv の規約はなかった。`docs\plugin-rules.md` に、プラグインの専用 venv の規則はあった」。`plugin-rules.md` の A7 の「開発専用の探索を作らない」とは、相互に参照する | `grep` の出力（`rules\`・`docs\`・`global-CLAUDE.md` の `venv`）と、一時リポジトリでの `git check-ignore .venv`〔機械〕 |
| E-2 | Python の規則を、`rules\python-venv.md` の 2 に移す。対象は、`docs\plugin-rules.md` の A1・A4・A5・A6・A7・H5 の **Python の部分**。言語を問わない部分（`setup` の流れ、終了コード 0〜3 の意味と免除、置き場の優先順、Node の `package-lock.json`）は、`plugin-rules.md` に残す。見出し番号は変えない。`python-style.md`・`python-testing.md` の `plugin-rules` への参照を、移動後の節に直す | `plugin-rules.md` に、`venv`・`requirements.txt`・`run.py`・`ensurepip`・`.venv` の語が、`python-venv.md` への参照の文以外にない（例示としての Node の混成構成の言及を除く）。旧文の各規則が、どちらかにある（`git show HEAD:docs/plugin-rules.md` と照合）。参照の節番号が正しい。作業フォルダと `~\.claude` が `cmp` で同一。行末は LF〔機械〕 |
| E-3 | `D:\local-repo\pptx-deck\CLAUDE.md`（`D:\claude\local-repo\pptx-deck\CLAUDE.md`）の、venv に関するコマンド集（11〜33 行）を消す。このファイルは git で追跡されていない。消す前に、スクラッチパッドへ退避し、行番号が現在の内容と合っていることを確かめる | 退避がある。消した範囲が、11〜33 行のコマンド集だけ〔機械〕 |

README の件数など、E と A と B の変更で事実と合わなくなる記述は、それぞれの要件の中で直す。

### F 拡張の影響の把握

**F-1 frontend-design が有効なとき、Artifact のデザインに影響するかを確認する。** 比較する条件: 「有効」と、「無効」（`--settings` の `enabledPlugins` で false）。本文の読み比べと、2 条件の実測（同じ依頼「Artifact使ってデザインを見せて」）。実測は、Artifact が使える対話セッションで行う（`claude -p` では使えない）。
- 判断基準: Skill 呼び出し（frontend-design・artifact-design）の有無と、出力 HTML の `font-family` と色に差がある場合を、「影響あり」とする。
- 受入条件: 2 条件の結果の表と、読み比べの所見を、チャットで報告する〔操作〕。できなければ「未検証」と理由。

## 〔操作〕の確認チェックリスト

実機の項目（B と A-2）は、**1 回の依頼にまとめる**。項目ごとに、準備 → 操作 → 期待 → 記録の欄で書く。できなかった項目は、「未検証」と理由を記録する。
- 準備: Claude Code 2.1.287 以降。`claude --plugin-dir ".\mods\session-desk"` で起動。端末の幅 144 列以上。疑似データのセッション。
- B-1: プロンプトを数回送る → 「履歴」タブに新しい順で増える。
- B-2: AskUserQuestion を使わせる → 「解説」タブに、要約・理由・影響・推奨が出る。
- B-3: 定型文を押す → 文言が送信される。履歴から追加し、次のセッションにも残る。
- B-4: ファイルを編集させる → 「変更」タブに、緑の追加行と赤の削除行が出る。
- A-2: 新しいセッションで `py -m pytest`・`git add` が確認なしに実行される。
- A-1: 一時フォルダで `rm -rf`、一時リポジトリで `git reset --hard`・`git switch --force` を頼む → 確認が出る。
- F-1: 有効・無効の 2 条件で、同じ依頼を実行し、Skill 呼び出しと HTML の差を記録する。

## 実装の順序と依存
1. E（規約。他の要件の前提ではないが、`CLAUDE.md` と permissions の変更を、規約と食い違わせないため先に決める）。
2. A（権限。A-1 の ask の優先順位の確認を、A-2 の反映の前に行う。A-7 の `CLAUDE.md` と A-2 の permissions は同時に反映する）。
3. B（1 つの mod。B-1 → B-3 → B-4 → B-2 の順。B-2 は、モデルの呼び出しとマスクが要るため最後。ユーザーの操作待ちの間は、テストの先行や、F-1 の準備を進める）。
4. F。
- README は、変更した要件ごとに直す。
- 各要件で、テストを先に書き、確認のあと、新規サブエージェント 2 体のレビューを受ける（`CLAUDE.md` の対象に当たる変更のとき。設定の追加のみで、ファイル数が 1 のものは対象外）。

## 非目標
- プラグイン（pptx-deck・pj-lens・vault-kb・grill-form）の実装・SKILL.md・テストの変更。
- `git_flow.py`・`readme_guard.py` の変更や削除、Stop hook とブランチ確認の変更。既存の deny 56 件の削除や緩和。`defaultMode`・`disableBypassPermissionsMode` の変更。
- 今日の目標、HTML のソース表示、更新案の文面の生成、見落とし防止のメモ（旧 C-1）、成果物・コンテキスト・ドキュメント候補のタブ（旧 B-1〜B-3）、作業の最中（タイマー）での監視、履歴のセッションをまたぐ保存、SPEC・計画の編集（見るだけ）。
- `settings.json` への mod の登録（`--plugin-dir` での読み込みだけ）、GitHub での mod の公開。
- 緩めた permissions の範囲（A-2）以外の ask の追加（`git branch -D`・`git stash drop`・`curl`・`wget` など。A-4 の提案にとどめる）。

## リスク
- B-2 は、会話の一部（質問・選択肢・直近のプロンプト）を別のモデル呼び出しに送る。マスクは完全ではない。止めるには mod 全体を読み込まない。
- B-1 の履歴は、セッションの中の状態に、プロンプトの原文を持つ（秘密を貼ると残る。セッションの終了で消える）。B-3 の定型文は、`$.store` にセッションをまたいで残る。秘密を定型文に追加しない。
- B-4 は、作業ディレクトリの Git の差分を出す。リポジトリでないとき、巨大な差分、バイナリは出せない（切り詰めと表示で扱う）。
- 緩めた permissions（`git switch *`・`git commit *`）の危険な変種のうち、未コミット変更を捨てる `git switch --discard-changes/-f/--force` は、A-1 の ask で止める。`git commit --amend` などは、reflog で戻せるため止めない。auto mode が ask をどう扱うかは未確認。
- `CLAUDE.md` の「Git」の節を消すと、コミット・push・PR 作成・マージ・タグ作成・リモートのブランチ削除の確認が、permissions にも `CLAUDE.md` にもなくなる（残るのは、`git_flow.py` の hook と、「確認の基準」の外部公開の確認）。コミットメッセージの慣習の記載も消える。
- `git tag`・`gh pr merge`・`gh release create` の確認は、`CLAUDE.md` と hook に頼る。hook は、Python が起動できないと、黙って無効になる（`|| true`）。
- `Read(**/credentials*)` は、普通の文書の読み取りも止める。
- 2 つの `settings.json` は、`enabledPlugins` などが違う。コピーせず、それぞれに同じ変更を入れる。`~\.claude` の変更前に、2 つの `settings.json` と `CLAUDE.md`、`pptx-deck\CLAUDE.md` を、スクラッチパッドへ退避する。
- インラインのスクリプトで、バックスラッシュが変わる（`\r` が改行になる）。Edit ツールで書くか、文字コードで組み立てる。
- `.py` がまだない段階では、`python-venv.md` は自動で読み込まれない。`plugin-rules.md` の参照の文で補う。
- 変更タブは、ファイルの内容（差分）を画面に出す。ファイル名で判定するため、名前に当たらないファイルの秘密は出る。

## 類似リポジトリの調査
| 参考元の URL | ライセンス | 取り入れた点 | 切り捨てた点 |
| --- | --- | --- | --- |
| https://github.com/oikon48/prompt-rail | MIT | 考え方のみ（プロンプトの履歴をパネルに出す。58 スター） | コード全体、トランスクリプトの読み取り、ジャンプ機能 |
| https://github.com/aieo-product/claude_qamods | MIT | 考え方のみ（qa-guide: AskUserQuestion の解説を、要約・理由・選択肢ごとの影響・推奨で出す。haiku を `$.model.complete` で呼ぶ。14 スター） | コード全体、全文脈モード（`$.model.fork`） |
| https://github.com/nicolas-codemate/claude-code-mods | 未確認 | 考え方のみ（diff-review: 差分のペイン） | コード全体（ライセンス未確認のため写さない） |
| https://github.com/whyashthakker/awesome-claude-code-mods | MIT | 考え方のみ（Git の状態・差分のレビューパネル） | コード全体 |
| https://github.com/anthropics/claude-code-playground | Apache-2.0 | 考え方のみ（replay-theater・token-weather）。blast-radius は取り下げ（A-5） | コード全体 |
| https://github.com/hideosugimoto/claude-settings-guard | MIT | 考え方のみ（deny の観点） | CLI・コード |
| https://github.com/dwarvesf/claude-guardrails | MIT | 考え方のみ（deny の観点） | hook・設定一式 |
| https://github.com/Maxximiliann/claude-code-permissions-audit | CC-BY-4.0 | 考え方のみ（監査の観点） | 報告書の文章 |
- 類似なし（更新が直近 1 年以内のリポジトリが 0 件）: 定型文を残せるパネル、開発用 venv の規約、README 更新案の提示、`CLAUDE.md` の git 確認の規則、`settings.json` のテンプレート。

## 決定ログ
- 真の要望の解釈 A〜G は、ユーザーが確認した。
- A の方針（ユーザーの指示）: permissions で防ぐのは、秘密情報の閲覧・編集と、修復できない破壊的コマンドだけ。`CLAUDE.md` の「Git」の節は消す。push・tag・merge・release の ask は外す。Stop hook は現状のまま（このため、コミットと push の促しは、Stop hook が出る場面では残る）。
- 第 3 版（ユーザーの指示）: B を N1〜N5 の 5 機能（履歴・解説・定型文・変更・進捗）に書き直し、旧 B-1〜B-3・旧 C-1・旧 D-1 を取り下げ・統合した。その後、実機確認のあと、進捗（N5・B-5）を取り下げ、4 機能にした（ユーザーの判断）。
- B-2 の解説は、haiku、設定なし、1 質問につき 1 回、最大 30 回。受容は、承認時にここへ記録する。mod は 1 つ。
- 前提（置いたもの）: 履歴はセッションの中だけに残す。定型文はセッションをまたいで残す。定型文の追加は、履歴の行のボタンで行う（文字入力の欄は作らない）。差分は `git diff HEAD` で出す。タスク（TaskCreate）の進捗バーは作らない。
- blast-radius は、壊れていたためアンインストールし、取り下げた（ユーザーの判断）。
- 規則の内容を移すときは、言語を問わない部分を `plugin-rules.md` に残す（レビューで分かった）。
- `rm -r/-rf/-fr` と `git switch --discard-changes/-f/--force` を ask に追加する（A-1）。blast-radius を取り下げると、これらの確認が、どこにもなくなるため。
