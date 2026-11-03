"""ユーザーの対応が要るときだけ、Windows のトースト通知を出す Hook。

settings.json の hooks から呼ぶ（入力は stdin の JSON）:
  Notification（matcher: permission_prompt）  許可・確認の画面で止まったとき
  PreToolUse（matcher: AskUserQuestion）      選択肢つきの質問を出したとき
  Stop                                         最後の応答が、質問や依頼で終わるとき

作業が終わっただけの応答では通知しない。Claude Code の動作を止めないため、
どんな失敗でも標準出力・標準エラー出力に何も書かず、終了コード 0 で終わる。
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOAST_SCRIPT = Path(__file__).resolve().with_name("toast.ps1")
LIMIT = 100
DEFAULT_TITLE = "Claude Code"
ACTION_LABEL = "ユーザーに取ってほしい行動"
ASK_ENDINGS = ("？", "?", "ください。", "ください")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")
MARKS = re.compile(r"^(?:[-*+#>]+\s*)+")
BLANKS = re.compile(r"\s+")


def clean(text: object) -> str:
    """通知に出せる 1 行にする。文字列でなければ空。ANSI と制御文字を空白にし、LIMIT 文字で切る。"""
    if not isinstance(text, str):
        return ""
    text = CONTROL.sub(" ", ANSI.sub("", text))
    return BLANKS.sub(" ", text).strip()[:LIMIT]


def folder_name(cwd: object) -> str:
    """作業フォルダの最後の名前。取れなければ既定の見出し。"""
    if not isinstance(cwd, str):
        return DEFAULT_TITLE
    name = cwd.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return clean(name) or DEFAULT_TITLE


def last_line(text: object) -> str:
    """最後の空でない行から、箇条書きなどの記号と太字の印（**）を除いたもの。"""
    if not isinstance(text, str):
        return ""
    for line in reversed(text.splitlines()):
        line = MARKS.sub("", line.strip()).replace("**", "").strip()
        if line:
            return line
    return ""


def needs_action(text: object) -> bool:
    """最後の行が、質問・依頼で終わる、または「ユーザーに取ってほしい行動」の行なら真。"""
    line = last_line(text)
    if line.endswith(ASK_ENDINGS):
        return True
    if line.startswith(ACTION_LABEL):
        rest = line.removeprefix(ACTION_LABEL).lstrip(" :：　\t").rstrip("。 ")
        return rest not in ("", "なし")
    return False


def with_label(label: str, text: object) -> str:
    """「ラベル: 本文」の形にする。本文が空ならラベルだけ。"""
    body = clean(text)
    return f"{label}: {body}" if body else label


def first_question(tool_input: object) -> object:
    """AskUserQuestion の入力から、先頭の質問文を取り出す。なければ None。"""
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    first = questions[0] if isinstance(questions, list) and questions else None
    return first.get("question") if isinstance(first, dict) else None


def decide(event: object) -> tuple[str, str] | None:
    """入力の JSON から、通知の（見出し, 本文）を決める。通知しないときは None。"""
    if not isinstance(event, dict):
        return None
    name = event.get("hook_event_name")
    title = folder_name(event.get("cwd"))
    if name == "Notification" and event.get("notification_type") == "permission_prompt":
        return title, with_label("許可待ち", event.get("message"))
    if name == "PreToolUse" and event.get("tool_name") == "AskUserQuestion":
        return title, with_label("質問", first_question(event.get("tool_input")))
    if name == "Stop" and needs_action(event.get("last_assistant_message")):
        return title, with_label("確認待ち", last_line(event.get("last_assistant_message")))
    return None


def show_toast(title: str, body: str) -> None:
    """toast.ps1 を起動してトースト通知を出す。終わりを待たない。文字は環境変数で渡す。"""
    powershell = shutil.which("powershell.exe") or "powershell.exe"
    env = {**os.environ, "NOTIFY_TITLE": title, "NOTIFY_BODY": body}
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TOAST_SCRIPT)]
    # 引数は固定（利用者の入力は環境変数で渡す）ので、S603 は問題にならない。
    subprocess.Popen(  # noqa: S603
        command,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    """stdin の JSON を読み、通知が要れば出す。通知の失敗で Claude Code を止めないため、常に 0。"""
    # 通知は補助の機能なので、失敗を握りつぶす（仕様: SPEC の「実装の方針」）。
    with contextlib.suppress(Exception):
        reconfigure = getattr(sys.stdin, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
        notice = decide(json.loads(sys.stdin.read()))
        if notice:
            show_toast(*notice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
