---
status: 完了
plan: docs/grill-form/plans/2026-11-03-notify-hooks.md
---
# SPEC: ユーザーの対応が要るときに、トースト通知を出す Hook

## 概要

### 目的
別の作業をしている間に、Claude Code が止まって待っているのに気づけず、時間が無駄になる。これを防ぐため、**ユーザーの対応が要る止まり方のときだけ**、Windows のトースト通知を出す。

### 入力（依頼の要約）
- 依頼: 「Claude がユーザーへ確認・入力・質問のタイミングで通知を出す Hooks がほしい」。
- 困りごと: Claude に依頼して別作業をしていると、ターミナルを見ないため、次の 3 つの止まり方に気づけない。
  1. 許可・確認の画面で止まる。
  2. 作業の区切りで、「次にやること」を示して止まる。
  3. 選択肢つきの質問を出して止まる。
- 普段は、ブラウザを見ている。複数のターミナルで Claude を同時に動かす。

### 決めたこと（ユーザーの回答）
| 項目 | 決定 |
| --- | --- |
| 通知の形 | Windows のトースト通知 |
| 通知する場面 | 許可・確認の画面、選択肢つきの質問、文章での質問や「次にやること」で止まるとき（文章の質問は、見分けの誤りがありうることを承知のうえで、通知する） |
| 通知しない場面 | 作業が終わっただけで、質問も次の提案もないとき |
| 複数のターミナル | 本文にフォルダ名（プロジェクト名）と、止まった理由を入れる |
| クリック | 何も起こさない |

### 流れ
1. Claude Code が、3 つの場面のいずれかで止まる。
2. Claude Code が、`settings.json` に登録した Hook（`hooks/notify.py`）を呼ぶ。入力は stdin の JSON。
3. `notify.py` が、通知が要る場面かを判定する。要らなければ、何もせず終了コード 0 で終わる。
4. 要る場面なら、`notify.py` が `hooks/toast.ps1` を呼び、トースト通知を出す。

### 通知する場面と、使う Hook
| 場面 | Hook | 判定 | 通知の本文（案） |
| --- | --- | --- | --- |
| N-1 許可・確認の画面 | `Notification`（`matcher: permission_prompt`） | 入力の `notification_type` が `permission_prompt` | 見出し: `<フォルダ名>`。本文: 「許可待ち」＋入力の `message`（ツール名など） |
| N-2 選択肢つきの質問 | `PreToolUse`（`matcher: AskUserQuestion`） | `tool_name` が `AskUserQuestion` | 見出し: `<フォルダ名>`。本文: 「質問」＋ `tool_input.questions[0].question` の先頭 |
| N-3 文章の質問・次の提案 | `Stop` | `last_assistant_message` に、次のいずれかがある（下の「見分け方」） | 見出し: `<フォルダ名>`。本文: 「確認待ち」＋最後の段落の先頭 |

**N-3 の見分け方**（私の案。確実ではない）: `last_assistant_message` の**最後の空でない行**（先頭の空白・箇条書きの記号・`**` を除く）が、次のいずれかを満たすとき、対応が要ると判定する。
- (a) 末尾が `？` または `?` である。
- (b) 末尾が `ください。` または `ください` である（「指示をください」「選んでください」など）。
- (c) 行が `ユーザーに取ってほしい行動` で始まり、その後ろが `なし`（`: なし`、`：なし` を含む）だけではない。
- `Stop` の入力の `stop_hook_active` が真でも、判定する（Stop Hook が続行させた後の、最終の応答を見逃さないため）。続行の前後で同じ内容が 2 回出うるが、許容する。
- 既存の `git_flow.py` の `stop` Hook は並列で実行され、`notify.py` はその結果を参照しない。

### 通知の本文の規則
- 見出しは、作業フォルダ（`cwd`）の最後の名前。
- 本文は 1 行で、先頭 100 文字までに切る。改行と制御文字は、空白に置き換える。
- 本文に、ツールの引数（コマンド、ファイルの中身）は入れない。画面やロック画面に出るため。

### 実装の方針（私の判断）
- 判定は Python（`hooks/notify.py`）で書き、既存の `git_flow.py` と同じ作りにする（テストを書ける）。
- トースト通知の表示は、PowerShell の標準機能だけで行う（追加のモジュールは入れない）。`powershell.exe`（5.1、Windows 標準）を `-NoProfile -File` で呼び、見出しと本文は環境変数（`NOTIFY_TITLE`・`NOTIFY_BODY`）で渡す（先頭が `-` の値や日本語が、引数だと崩れるため）。日本語が文字化けしないことを AC-7 で確かめる。
- 重複の対処（AC-8 で重複が分かった場合だけ入れる）: 同じ `session_id` で、直前の通知から 15 秒以内の 2 回目は出さない。直前の時刻は、一時フォルダの小さなファイルに記録する。
- 登録は `git_flow.py` と同じ形にする（`py`・`python3`・`python` の順に試し、`$HOME/.claude/hooks/notify.py` を呼ぶ）。リポジトリの `hooks\` を原本とし、`~\.claude\hooks\` にコピーする。リポジトリの `settings.json` は原本で、Claude Code が読むのは `~\.claude\settings.json` だけなので、Hook は二重に動かない。
- どんな失敗でも、終了コード 0 で終わり、Claude Code の動作を止めない。標準出力には何も書かない。
- 登録先は `settings.json` の `hooks`。リポジトリの `settings.json` と `~\.claude\settings.json` の両方に、同じ変更を入れる。`notify.py`・`toast.ps1` は、リポジトリの `hooks\` と `~\.claude\hooks\` に置く。

## 受入条件
| 番号 | 条件 | 確認 |
| --- | --- | --- |
| AC-1 | `permission_prompt` の入力で、通知の要求が出る。`idle_prompt`・`auth_success` など、ほかの `notification_type` では出ない | テスト〔機械〕 |
| AC-2 | `AskUserQuestion` の入力で、質問文を含む通知の要求が出る。ほかのツールでは出ない | テスト〔機械〕 |
| AC-3 | `Stop` で、最後の空でない行が (a) `？`・`?` で終わる、(b) `ください。`・`ください` で終わる、(c) `ユーザーに取ってほしい行動` で始まり `なし` だけではない、のいずれかのとき、通知の要求が出る。終了報告だけ（これらに当たらない）では出ない。`ユーザーに取ってほしい行動: なし` では出ない。`stop_hook_active` が真でも判定する | テスト〔機械〕 |
| AC-4 | 本文が 100 文字以内で、改行・制御文字・ANSI エスケープを含まず、ツールの引数を含まない | テスト〔機械〕 |
| AC-5 | 壊れた JSON、空の入力、想定外の項目でも、終了コード 0 で、標準出力が空 | テスト〔機械〕 |
| AC-6 | 両方の `settings.json` に、3 つの Hook が登録され、既存の Hook と `permissions` は変わらない | スクリプトで照合〔機械〕 |
| AC-7 | 実機で、N-1・N-2・N-3 の 3 場面でトースト通知が出る。終了報告だけの応答では出ない。本文のフォルダ名が、起動したフォルダと一致する | ユーザーの操作〔操作〕。できなければ「未検証」と理由 |
| AC-8 | 実機で、N-2 の質問のとき、通知が 2 回出ない（`Notification` が `AskUserQuestion` でも発火して、重複しないこと） | ユーザーの操作〔操作〕 |

## 非目標
- 作業が終わっただけの通知。
- 通知のクリックで、ウィンドウを前面に出す、タブを開く。
- 音の設定、通知の ON/OFF の切り替え、通知の履歴。
- `idle_prompt`（応答後およそ 60 秒の通知）の利用。終了のたびに出てしまうため。
- BurntToast などの追加モジュール。
- Windows 以外の OS、スマートフォンや Slack への通知。
- サブエージェントの終了（`SubagentStop`）の通知。
- 既存の Hook（`git_flow.py`）と `permissions` の変更。

## リスク
- **N-3 の見分けが外れる**: 文章の質問を、最後の行の末尾（`？`・`ください`）と決まった行で見分ける。別の形で止まると、通知が出ない（見逃し）。説明文が `？` や `ください` で終わると、通知が出る（誤通知）。最後の行しか見ないので、途中に質問があっても、最後が別の文なら出ない。
- **`Notification` が `AskUserQuestion` で発火するか**: 公式文書に記載がなく、未確認。発火すると、N-2 の通知が 2 回出うる（AC-8 で確認する）。
- **auto mode での `permission_prompt`**: auto mode で許可の画面が出ないときは、発火しない（当然）。出るときの発火は、実機で確認する。
- **`permission_prompt` の遅れ**: 画面が出てから、およそ 6 秒後に発火する（公式）。通知が少し遅れる。
- **Windows の通知設定**: PowerShell の通知がオフ、または集中モード（おやすみモード）のとき、トーストが出ない。実機の AC-7 で確認し、README に前提を書く。
- **Stop の繰り返し**: 既存の Stop Hook が応答を続けさせると、`Stop` が連続して発火する。そのたびに判定するので、通知が続けて出うる。
- **画面への内容の表示**: 質問文の先頭 100 文字が、画面に出る。画面共有中は、内容が映る。
- **失敗が見えない**: 失敗しても終了コード 0 で終わるため、通知が出ないとき、原因が分かりにくい。

## 類似リポジトリの調査
検索日: 2026-11-03。検索語: `claude code notification`・`notify`・`hooks notification`・`toast`・`windows notification`・`alert`・`notification hook sound`（GitHub、重複を除いて 99 件）。更新が直近 1 年以内のものを、スター数の降順に並べた上位 10 件と、更新停止の 1 件。

| 参考元の URL | ライセンス | 取り入れた点 | 切り捨てた点 |
| --- | --- | --- | --- |
| https://github.com/farouqaldori/vibe-notch（2526） | Apache-2.0 | 考え方のみ（README 未確認。説明文は「切り替えなしの通知」） | 全部（macOS のノッチ向けの別物） |
| https://github.com/wyattjoh/claude-code-notification（95） | MIT | 考え方のみ（説明文は macOS の通知 Hook） | 全部（macOS 専用） |
| https://github.com/soulee-dev/claude-code-notify-powershell（92） | MIT | 考え方のみ。PowerShell の標準機能だけで、トースト通知を出す方針。`Notification` と `Stop` を登録する形 | コード。終了のたびの通知 |
| https://github.com/chuilishi/claude-code-notify（37） | MIT | 考え方のみ（README 確認）。Windows のネイティブなトースト通知 | クリックで前面に出す機能、実行ファイルの同梱 |
| https://github.com/flaviomartil/claude-code-toast（37） | MIT | 考え方のみ（説明文は WSL2 向け） | 全部（WSL2 向け） |
| https://github.com/polyphilz/ccnotifs（22） | MIT | 考え方のみ（説明文は macOS・tmux 向け） | 全部 |
| https://github.com/BND-1/claude-code-hooks-notification（18） | なし | 考え方のみ（ライセンスなしのため、写さない） | 全部 |
| https://github.com/rvcas/claude-zellij-whip（14） | MIT | 考え方のみ（説明文は Zellij 向け） | 全部 |
| https://github.com/starpipi/claude-code-notify（11） | Apache-2.0 | 考え方のみ（説明文は「タスク完了の通知」） | 全部 |
| https://github.com/TianqiZhang/claude-code-toast（10） | MIT | 考え方のみ（説明文は BurntToast を使う Windows のトースト通知） | BurntToast への依存 |
| https://github.com/enescaakir/notify（9） | MIT | 考え方のみ（README 確認）。許可待ちを通知するという目的 | `PreToolUse` で 3 秒待つ方式（公式の `permission_prompt` があるため）、BurntToast への依存、完了の通知 |
| https://github.com/dazuiba/CCNotify（214、更新停止） | MIT | 考え方のみ（説明文は「デスクトップ通知」） | 全部（更新停止） |

- 取り入れる点は、すべて「考え方のみ」。コードと文章は写さない（コピー元の著作権表示の義務を負わない）。
- 先行例の多くは、終了のたびに通知する。この SPEC の「対応が要るときだけ」とは違う。
- 「README 未確認」と書いたものは、説明文だけを根拠にしている。

## 決定ログ
- 通知は、対応が要るときだけ（ユーザーの回答）。終了だけなら通知しない。
- 文章での質問も通知する（ユーザーの回答。見分けの誤りがありうることを説明したうえでの選択）。
- 通知のクリックでは、何も起こさない（ユーザーの回答）。
- 私の判断: 判定は Python、表示は PowerShell。追加モジュールは使わない。音は、トースト通知の既定のまま、別には設定しない。`idle_prompt` は使わない。
- 私の判断: N-3 の見分けは、最後の空でない行の (a) `？` (b) `ください` (c) `ユーザーに取ってほしい行動`（`なし` を除く）の 3 つ。`stop_hook_active` が真でも判定する。
- 私の判断: 重複したときは、同じセッションの 15 秒以内の 2 回目を出さない（AC-8 で重複が分かった場合だけ入れる）。PowerShell は `powershell.exe`（5.1）に固定する。登録は `git_flow.py` と同じ形で、リポジトリを原本としてコピーする。
- ビルダー確認（別のレビュアーが SPEC を読んだ）で出た質問 7 件は、上の判断で答えた。ユーザーに聞く質問は残っていない。

## 公式の仕様（確認した点と、未確認の点）
出典: https://code.claude.com/docs/en/hooks.md（2026-11-03、サブエージェントが確認）。
- `Notification` の `matcher` に `permission_prompt` がある。承認を求めて約 6 秒待たれたときに発火する。入力に `message`・`notification_type` がある。
- `PreToolUse` は `matcher: AskUserQuestion` で捉えられる。質問文は `tool_input.questions[].question` に入る。
- `Stop` の入力に `last_assistant_message` がある。
- 通知用の Hook は、終了コード 0 で何も出力しなければ、何も起こさない。同じイベントに複数の Hook があるときは、すべて並列で実行される。
- 未確認: `Notification` が `AskUserQuestion` で発火するか。auto mode で `permission_prompt` が発火するか。Windows のトースト通知の実装例は、公式にない。

## 後続の手順
1. 実装計画を作るときは、保存先を `docs/grill-form/plans/2026-11-03-notify-hooks.md` にする（フォルダがなければ作る）。計画の先頭に `status: 未対応` と `spec: docs/grill-form/specs/2026-11-03-notify-hooks-design.md` を書く。
2. 計画を保存したら、この SPEC の先頭を `status: 完了` にし、`plan:` に `docs/grill-form/plans/2026-11-03-notify-hooks.md` を書く。
3. 計画の実装がすべて終わったら、計画の先頭を `status: 完了` にする。
