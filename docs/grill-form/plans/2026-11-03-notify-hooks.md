status: 未対応
spec: docs/grill-form/specs/2026-11-03-notify-hooks-design.md

# 通知 Hook 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans（このセッションで、順に実装する）。手順はチェックボックス（`- [ ]`）で追う。

**Goal:** ユーザーの対応が要る 3 つの止まり方（許可画面・AskUserQuestion・文章の質問）のときだけ、Windows のトースト通知を出す Hook を作る。

**Architecture:** 判定は Python の純粋関数 `decide(event)`（テストできる）。表示は `toast.ps1`（PowerShell 5.1、標準機能のみ）。`notify.py` の `main()` が stdin の JSON を読み、`decide` の結果があれば `toast.ps1` を起動して、必ず終了コード 0 で終わる。

**Tech Stack:** Python 3.14（標準ライブラリのみ）、PowerShell 5.1（`powershell.exe`）、pytest。

**Spec:** `docs/grill-form/specs/2026-11-03-notify-hooks-design.md`

## Global Constraints
- どんな失敗でも終了コード 0。標準出力には何も書かない（SPEC「実装の方針」）。
- 通知の本文は 1 行・先頭 100 文字まで。改行・制御文字・ANSI エスケープを空白に置き換える。ツールの引数は入れない（SPEC「通知の本文の規則」）。
- 追加モジュール（BurntToast など）は使わない。`powershell.exe -NoProfile` で呼ぶ。
- 既存の `git_flow.py` の Hook と `permissions` は変えない。
- 登録は `git_flow.py` と同じ形（`py`・`python3`・`python` の順、`$HOME/.claude/hooks/notify.py`）。リポジトリを原本とし、`~\.claude\hooks\` にコピーする。
- 文書・コメントは日本語。テストの規則は `~\.claude\rules\python-testing.md`、書き方は `python-style.md` に従う。

## Review Focus
SPEC が暗に求めるが、どのタスクのテストにもない、人が遭いやすい入力。各行に、持ち主のタスクでテストを足す。
1. `last_assistant_message` が空・`None`・文字列でない → 通知しない（落ちない）。（Task 1）
2. 最後の行が `- ` や `**` で飾られている、末尾が全角コロンの `ユーザーに取ってほしい行動：なし`、CRLF → 判定が崩れない。（Task 1）
3. `AskUserQuestion` の `questions` が空・欠落・質問文が非文字列 → 落ちずに、質問文なしの通知か、通知なし。（Task 1）
4. `cwd` が空・末尾が `\`・ドライブの直下（`C:\`） → 見出しが空にならない。（Task 1）
5. 本文が `-` で始まる、`<`・`&` を含む、日本語を含む → `toast.ps1` に渡って壊れない。（Task 2）

---

### Task 1: 判定 `decide`（AC-1〜AC-4）

**Files:**
- Create: `hooks/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Produces: `decide(event: dict) -> tuple[str, str] | None`（`(見出し, 本文)`。通知しないときは `None`）。補助: `clean(text: object, limit: int = 100) -> str`、`needs_action(text: object) -> bool`、`folder_name(cwd: object) -> str`。

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_notify.py`。`git_flow.py` のテストと同じく、`importlib` でモジュールを読み込む `notify` フィクスチャを置く）。テスト名と主な assert:
  - `test_permission_prompt_notifies`: `{"hook_event_name":"Notification","notification_type":"permission_prompt","message":"Claude needs your permission to use Bash","cwd":"D:\\work\\proj"}` → `("proj", "許可待ち: Claude needs your permission to use Bash")`。
  - `test_other_notification_types_are_ignored`: `idle_prompt`・`auth_success`・`elicitation_dialog` → `None`。
  - `test_ask_user_question_notifies_with_question`: `PreToolUse`・`tool_name="AskUserQuestion"`・`tool_input={"questions":[{"question":"どれにしますか？"}]}` → 本文が `質問: どれにしますか？`。別のツール名（`Bash`）→ `None`。
  - `test_ask_user_question_without_questions`: `questions` が空・欠落・質問文が数値 → 落ちず、本文は `質問` だけ（通知はする）。
  - `test_stop_notifies_when_last_line_asks`: 最後の行が `どちらにしますか？`・`どちらにしますか?`・`指示をください。`・`選んでください` → 通知する。本文は `確認待ち: <最後の行>`。
  - `test_stop_notifies_on_action_line`: 最後の行が `ユーザーに取ってほしい行動: 実機で確認する` → 通知。
  - `test_stop_ignores_plain_report_and_none_action`: 最後の行が `完了しました。`・`ユーザーに取ってほしい行動: なし`・`ユーザーに取ってほしい行動：なし`（全角コロン）→ `None`。
  - `test_stop_judges_last_nonempty_line_only`: 途中に `？` があっても、最後の行が `完了しました。` なら `None`。末尾の空行・空白は無視。
  - `test_stop_ignores_decoration_and_crlf`: `- どちらですか？`・`**どちらですか？**`・CRLF 区切りでも通知。
  - `test_stop_active_flag_still_judged`: `stop_hook_active=True` でも通知する。
  - `test_stop_bad_message_is_ignored`: `last_assistant_message` が欠落・`None`・数値・空 → `None`。
  - `test_body_is_one_line_and_cut_at_100`: 本文が 100 文字以内（`…` を含めない、切るだけ）。改行・`\x1b[31m` 付きの文字列・制御文字が空白に置き換わる。
  - `test_title_is_folder_name`: `cwd` が `D:\\work\\proj`・`D:/work/proj/`・`D:\\work\\proj\\`→ `proj`。`C:\\` → `C:`。空・欠落・数値 → `Claude Code`。
  - `test_no_tool_input_in_body`: `PreToolUse` の `tool_input` に `command` があっても、通知の本文に出ない（AskUserQuestion の質問文以外を入れない）。
- [ ] **Step 2: 失敗を確かめる**: `py -m pytest tests/test_notify.py -q` → すべて FAIL（`notify.py` がない）。
- [ ] **Step 3: `hooks/notify.py` に上の関数を実装する**。方針: `needs_action` は最後の空でない行から、先頭の空白・`-`・`*`・`#`・`>` の記号と `**` を除いて判定する。判定は (a) 末尾が `？`・`?` (b) 末尾が `ください。`・`ください` (c) `ユーザーに取ってほしい行動` で始まり、その後ろから区切り（`:`・`：`・空白）を除くと `なし` ではない、の 3 つ。`clean` は、制御文字と ANSI エスケープ（`ESC [ ... 英字`）を空白にし、連続する空白を 1 つにして、先頭 100 文字に切る。
- [ ] **Step 4: 通ることを確かめる**: `py -m pytest tests/test_notify.py -q` → すべて PASS。

### Task 2: 起動 `main` と表示 `toast.ps1`（AC-5、AC-7 の準備）

**Files:**
- Modify: `hooks/notify.py`
- Create: `hooks/toast.ps1`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `decide`（Task 1）。
- Produces: `main() -> int`（常に 0）、`show_toast(title: str, body: str) -> None`。`toast.ps1` は環境変数 `NOTIFY_TITLE`・`NOTIFY_BODY` を読む（引数にしない: `-` で始まる値と文字コードの問題を避けるため）。

- [ ] **Step 1: 失敗するテストを書く**: 
  - `test_main_shows_toast_for_valid_event`: `sys.stdin` を差し替え、`notify.show_toast` を記録用に差し替えて `main()` を呼ぶ → 戻り値 0、記録に `(見出し, 本文)` が 1 件、標準出力が空。
  - `test_main_exits_zero_on_garbage`: 壊れた JSON・空の入力・JSON の配列・`null`・想定外の型 → 戻り値 0、`show_toast` は呼ばれない、標準出力が空。
  - `test_main_swallows_toast_failure`: `show_toast` が例外を投げても 0。
  - `test_script_runs_as_hook_and_stays_silent`: `py hooks/notify.py` を `subprocess` で、壊れた JSON を stdin に流して起動 → 終了コード 0、stdout・stderr が空。
  - `test_toast_script_exists_and_reads_env`: `toast.ps1` が `NOTIFY_TITLE`・`NOTIFY_BODY` を読み、`CreateTextNode` ではなく `InnerText`（XML を自動でエスケープする方法）で本文を入れていることを、文字列で確かめる。
- [ ] **Step 2: 失敗を確かめる**: `py -m pytest tests/test_notify.py -q` → 新しいテストが FAIL。
- [ ] **Step 3: `main`・`show_toast` を実装する**。`show_toast` は `subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",<toast.ps1 の絶対パス>], env={**os.environ,"NOTIFY_TITLE":title,"NOTIFY_BODY":body}, stdin/stdout/stderr=DEVNULL, creationflags=CREATE_NO_WINDOW)` で起動し、待たない。`main` は `try/except Exception` で全体を囲み、必ず 0 を返す。`if __name__ == "__main__": sys.exit(main())`。標準入力は UTF-8 で読む。
- [ ] **Step 4: `hooks/toast.ps1` を書く**。Windows のトースト通知（`Windows.UI.Notifications`）を、PowerShell 標準の AppUserModelID（`{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`）で出す。テンプレートは `ToastText02`（見出し 1 行・本文 1 行）。`InnerText` で文字を入れる。音は既定のまま。失敗しても何も出力しない。
- [ ] **Step 5: 通ることを確かめる**: `py -m pytest tests/test_notify.py -q` → すべて PASS。
- [ ] **Step 6: 画面に出ることを手で確かめる**: `$env:NOTIFY_TITLE='proj'; $env:NOTIFY_BODY='-質問: <a & b> 日本語'; powershell.exe -NoProfile -File hooks\toast.ps1` → トースト通知が出て、本文が崩れない（日本語・`<`・`&`・先頭の `-`）。出ないときは、Windows の通知設定（PowerShell）と集中モードを確かめる。〔操作。できなければ「未検証」と理由を記録する〕

### Task 3: 登録とコピー（AC-6）

**Files:**
- Modify: `settings.json`（リポジトリ）、`C:\Users\sioay\.claude\settings.json`
- Copy: `hooks/notify.py`・`hooks/toast.ps1` → `C:\Users\sioay\.claude\hooks\`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: Task 2 の `notify.py`・`toast.ps1`。

- [ ] **Step 1: 失敗するテストを書く**: `test_settings_register_notify_hooks`: リポジトリの `settings.json` の `hooks` に、(1) `Notification`・`matcher=permission_prompt`、(2) `PreToolUse`・`matcher=AskUserQuestion`、(3) `Stop` の 3 つが、それぞれ `notify.py` を呼ぶ `command` として入っている。`command` が `py`・`python3`・`python` の順で、`$HOME/.claude/hooks/notify.py` を指す。`git_flow.py` を呼ぶ既存の 4 つの Hook が残っている。`permissions` が変わっていない（`allow` 16・`ask` 11・`deny` 68）。`~\.claude\settings.json` の `hooks` でも同じ 3 つがある（ファイルがあるときだけ検査）。
- [ ] **Step 2: 失敗を確かめる**: `py -m pytest tests/test_notify.py::test_settings_register_notify_hooks -q` → FAIL。
- [ ] **Step 3: 両方の `settings.json` に 3 つの Hook を足す**（既存の `git_flow.py` の登録の `command` の形を写す。`timeout` は 10）。`Edit` ツールで、足す箇所だけを書き換える。
- [ ] **Step 4: ファイルをコピーする**: `cp hooks/notify.py hooks/toast.ps1 ~/.claude/hooks/`。
- [ ] **Step 5: 検証**: `py -m pytest -q`（全テスト）→ すべて PASS。`cmp hooks/notify.py ~/.claude/hooks/notify.py`・`cmp hooks/toast.ps1 ~/.claude/hooks/toast.ps1` → 同一。`git diff --check` → 問題なし。`claude plugin validate` は対象外（プラグインではない）。
- [ ] **Step 6: コミット（ユーザーの確認後）**: `feat: ユーザーの対応が要るときにトースト通知を出す Hook を足す`。

### Task 4: 実機確認（AC-7、AC-8）— ユーザーの操作

- [ ] **Step 1: 新しいセッションで、次を確かめる**（`~\.claude\settings.json` は起動時に読まれる）。
  1. N-1: 許可が要る操作（例: `ask` の `rm -r`）を頼む → 約 6 秒後にトースト（`許可待ち`、フォルダ名つき）。
  2. N-2: 選択肢を出させる（例:「AskUserQuestion で A か B を聞いて」）→ トースト（`質問: …`）。**1 回だけ**出る（AC-8）。
  3. N-3: 「最後に質問で終わって」と頼む → トースト（`確認待ち: …`）。
  4. 終了報告だけの応答 → トーストが出ない。
  5. 日本語の本文が文字化けしない。複数のターミナルで、見出しのフォルダ名が違う。
- [ ] **Step 2: AC-8 で重複が出たときだけ**（Task 5 へ）。出なければ、Task 5 は作らない。

### Task 5（条件つき）: 重複の抑止

AC-8 で、N-2 の通知が 2 回出たときだけ行う。

**Files:** Modify `hooks/notify.py`、Test `tests/test_notify.py`

- [ ] **Step 1: 失敗するテストを書く**: `test_duplicate_within_15_seconds_is_skipped`: 同じ `session_id` で、前の通知から 15 秒以内の 2 回目は `show_toast` が呼ばれない。16 秒後は呼ばれる。`session_id` が違えば呼ばれる。時刻の記録先は、テストでは一時フォルダに差し替える。
- [ ] **Step 2: 失敗を確かめる** → FAIL。
- [ ] **Step 3: 実装する**: `main` の中で、`tempfile.gettempdir()/claude-notify/<session_id>` に直前の時刻を書く。ファイルが壊れていたら無視する。
- [ ] **Step 4: 通ることを確かめる**: `py -m pytest -q` → すべて PASS。コピーをやり直し、AC-8 を再確認する。

### 完了前のレビュー（計画の外の、必須の手順）
ファイル数が 2 以上で、条件分岐を足す変更のため、完了報告の前に、文脈を共有しない新規サブエージェント 2 体（正しさと要件、過剰実装とリスク）にレビューさせる。指摘は検証して、依頼の範囲内のものを直す。

---

## 自己点検
- SPEC の網羅: AC-1〜AC-5 は Task 1・2、AC-6 は Task 3、AC-7・AC-8 は Task 4（重複の対処は Task 5）。N-1・N-2・N-3 は Task 1。登録とコピーは Task 3。
- 型の整合: `decide` は `tuple[str, str] | None`、`show_toast(title, body)`、`main() -> int` を、全タスクで同じ名前で使っている。
- 長さ: 計画は SPEC より短く、コードの本体は書いていない（関数の名前・テスト・方針だけ）。
