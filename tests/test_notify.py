"""hooks/notify.py（ユーザーの対応が要るときにトースト通知を出す Hook）のテスト。"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hooks" / "notify.py"
TOAST = ROOT / "hooks" / "toast.ps1"
ESC = chr(27)


@pytest.fixture(scope="module")
def notify():
    spec = importlib.util.spec_from_file_location("notify", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop(message, **extra):
    return {"hook_event_name": "Stop", "cwd": "D:\\work\\proj", "last_assistant_message": message, **extra}


# --- 許可・確認の画面（N-1） ------------------------------------------------


def test_permission_prompt_notifies(notify):
    event = {
        "hook_event_name": "Notification",
        "notification_type": "permission_prompt",
        "message": "Claude needs your permission to use Bash",
        "cwd": "D:\\work\\proj",
    }
    assert notify.decide(event) == ("proj", "許可待ち: Claude needs your permission to use Bash")


@pytest.mark.parametrize("kind", ["idle_prompt", "auth_success", "elicitation_dialog", None])
def test_other_notification_types_are_ignored(notify, kind):
    event = {"hook_event_name": "Notification", "notification_type": kind, "message": "x", "cwd": "D:\\p"}
    assert notify.decide(event) is None


# --- 選択肢つきの質問（N-2） ------------------------------------------------


def test_ask_user_question_notifies_with_question(notify):
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": [{"question": "どれにしますか？"}]},
        "cwd": "D:\\work\\proj",
    }
    assert notify.decide(event) == ("proj", "質問: どれにしますか？")


def test_other_tools_are_ignored(notify):
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "D:\\p"}
    assert notify.decide(event) is None


@pytest.mark.parametrize(
    "tool_input",
    [{}, {"questions": []}, {"questions": [{"question": 5}]}, {"questions": ["x"]}, {"questions": "x"}, None, "x"],
)
def test_ask_user_question_without_a_usable_question(notify, tool_input):
    event = {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "tool_input": tool_input, "cwd": "D:\\p"}
    assert notify.decide(event) == ("p", "質問")


def test_tool_input_other_than_the_question_is_not_in_the_body(notify):
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": [{"question": "どれ？", "options": [{"label": "SECRET-OPTION"}]}], "command": "SECRET"},
        "cwd": "D:\\p",
    }
    assert "SECRET" not in notify.decide(event)[1]


# --- 文章の質問・次の提案（N-3） --------------------------------------------


@pytest.mark.parametrize(
    "last",
    ["どちらにしますか？", "どちらにしますか?", "指示をください。", "選んでください", "ユーザーに取ってほしい行動: 実機で確認する"],
)
def test_stop_notifies_when_the_last_line_needs_the_user(notify, last):
    message = f"作業を終えました。\n\n{last}\n"
    assert notify.decide(stop(message)) == ("proj", f"確認待ち: {last}")


@pytest.mark.parametrize(
    "last",
    ["完了しました。", "ユーザーに取ってほしい行動: なし", "ユーザーに取ってほしい行動：なし", "ユーザーに取ってほしい行動 : なし"],
)
def test_stop_ignores_a_plain_report_and_a_none_action(notify, last):
    assert notify.decide(stop(f"どちらにしますか？\n{last}")) is None


def test_stop_judges_only_the_last_non_empty_line(notify):
    assert notify.decide(stop("途中の質問ですか？\n完了しました。\n\n  \n")) is None
    assert notify.decide(stop("完了しました。\n\nどれですか？\n\n   \n")) == ("proj", "確認待ち: どれですか？")


@pytest.mark.parametrize("message", ["- どちらですか？", "**どちらですか？**", "> どちらですか？", "報告\r\n\r\nどちらですか？\r\n"])
def test_stop_ignores_decoration_and_crlf(notify, message):
    assert notify.decide(stop(message)) == ("proj", "確認待ち: どちらですか？")


def test_stop_is_judged_even_when_a_stop_hook_continued(notify):
    assert notify.decide(stop("どちらですか？", stop_hook_active=True)) == ("proj", "確認待ち: どちらですか？")


@pytest.mark.parametrize("message", [None, 5, "", "   \n", ["どれ？"], {"a": 1}])
def test_stop_with_an_unusable_message_is_ignored(notify, message):
    assert notify.decide(stop(message)) is None
    event = {"hook_event_name": "Stop", "cwd": "D:\\p"}
    assert notify.decide(event) is None


# --- 本文と見出し（AC-4） ---------------------------------------------------


def test_body_is_one_line_and_cut_at_100(notify):
    assert notify.clean("x" * 150) == "x" * 100
    assert notify.clean("a\n b\t\tc\x07d") == "a b c d"
    assert notify.clean(f"{ESC}[31mred{ESC}[0m text") == "red text"
    assert notify.clean(None) == ""
    assert notify.clean(5) == ""


def test_body_after_prefix_has_at_most_100_characters(notify):
    body = notify.decide(stop("あ" * 150 + "？"))[1]
    assert body.startswith("確認待ち: ")
    assert len(body.removeprefix("確認待ち: ")) == 100


@pytest.mark.parametrize(
    ("cwd", "expected"),
    [
        ("D:\\work\\proj", "proj"),
        ("D:/work/proj/", "proj"),
        ("D:\\work\\proj\\", "proj"),
        ("C:\\", "C:"),
        ("", "Claude Code"),
        (None, "Claude Code"),
        (5, "Claude Code"),
    ],
)
def test_title_is_the_folder_name(notify, cwd, expected):
    assert notify.folder_name(cwd) == expected


# --- 起動（AC-5） -----------------------------------------------------------


def run_main(notify, monkeypatch, capsys, raw, toasts):
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    monkeypatch.setattr(notify, "show_toast", lambda title, body: toasts.append((title, body)))
    code = notify.main()
    return code, capsys.readouterr()


def test_main_shows_a_toast_for_a_valid_event(notify, monkeypatch, capsys):
    toasts = []
    raw = json.dumps(stop("どれですか？"), ensure_ascii=False)
    code, out = run_main(notify, monkeypatch, capsys, raw, toasts)
    assert code == 0
    assert toasts == [("proj", "確認待ち: どれですか？")]
    assert out.out == ""


@pytest.mark.parametrize("raw", ["{broken", "", "[]", "null", "5", '"x"', '{"hook_event_name": 5}'])
def test_main_exits_zero_on_garbage(notify, monkeypatch, capsys, raw):
    toasts = []
    code, out = run_main(notify, monkeypatch, capsys, raw, toasts)
    assert code == 0
    assert toasts == []
    assert out.out == ""


def test_main_swallows_a_toast_failure(notify, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stop("どれですか？"), ensure_ascii=False)))

    def boom(title, body):
        raise OSError("no powershell")

    monkeypatch.setattr(notify, "show_toast", boom)
    assert notify.main() == 0
    assert capsys.readouterr().out == ""


def test_script_runs_as_a_hook_and_stays_silent():
    for raw in ["{broken", "", "[]", json.dumps({"hook_event_name": "Stop", "last_assistant_message": "完了しました。"})]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], input=raw.encode("utf-8"), capture_output=True, timeout=30, check=False
        )
        assert result.returncode == 0
        assert result.stdout == b""
        assert result.stderr == b""


# --- 登録（AC-6） -----------------------------------------------------------

SETTINGS_FILES = [ROOT / "settings.json", Path.home() / ".claude" / "settings.json"]
NOTIFY_COMMAND = (
    'py "$HOME/.claude/hooks/notify.py"'
    ' || python3 "$HOME/.claude/hooks/notify.py"'
    ' || python "$HOME/.claude/hooks/notify.py" || true'
)


def hook_entries(path):
    """settings.json の hooks を、（イベント, matcher, command）の一覧にする。"""
    hooks = json.loads(path.read_text(encoding="utf-8"))["hooks"]
    return [
        (event, group.get("matcher"), hook["command"])
        for event, groups in hooks.items()
        for group in groups
        for hook in group["hooks"]
    ]


@pytest.mark.parametrize("path", SETTINGS_FILES, ids=["repo", "home"])
def test_settings_register_the_three_notify_hooks(path):
    if not path.exists():
        pytest.skip(f"{path} がない")
    entries = hook_entries(path)
    notify = [(event, matcher, command) for event, matcher, command in entries if "notify.py" in command]
    assert sorted(notify, key=str) == sorted(
        [
            ("Notification", "permission_prompt", NOTIFY_COMMAND),
            ("PreToolUse", "AskUserQuestion", NOTIFY_COMMAND),
            ("Stop", None, NOTIFY_COMMAND),
        ],
        key=str,
    )
    # 既存の git_flow.py の Hook は、そのまま残る。
    git_flow = sorted(event for event, _matcher, command in entries if "git_flow.py" in command)
    assert git_flow == ["PostToolUse", "PreToolUse", "SessionStart", "Stop"]


def test_toast_script_puts_env_text_into_the_toast_with_inner_text():
    # コメントの語では通らないよう、代入の行を確かめる。InnerText は XML の記号を自動でエスケープする。
    lines = [line.strip() for line in TOAST.read_text(encoding="utf-8").splitlines()]
    code = [line for line in lines if not line.startswith("#")]
    assert "$texts.Item(0).InnerText = [string]$env:NOTIFY_TITLE" in code
    assert "$texts.Item(1).InnerText = [string]$env:NOTIFY_BODY" in code
    assert not any("InnerXml" in line or "LoadXml" in line for line in code)


def test_show_toast_starts_powershell_without_waiting_and_passes_text_by_env(notify, monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

    monkeypatch.setattr(notify.subprocess, "Popen", FakePopen)
    notify.show_toast("proj", "-質問: <a & b>")
    (command, kwargs), = calls
    assert Path(command[0]).name.lower() == "powershell.exe"
    assert command[1:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert command[-2:] == ["-File", str(TOAST)]
    assert "-質問" not in " ".join(command)
    assert kwargs["env"]["NOTIFY_TITLE"] == "proj"
    assert kwargs["env"]["NOTIFY_BODY"] == "-質問: <a & b>"
    assert kwargs["stdout"] == kwargs["stderr"] == kwargs["stdin"] == subprocess.DEVNULL
