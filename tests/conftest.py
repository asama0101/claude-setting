"""git_flow.py のテスト用フィクスチャ。

一時フォルダに Git リポジトリを作り、フックのスクリプトを実際に起動して確かめる。
外部のコマンド（gh）だけをテスト用の代替に置き換える。
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hooks" / "git_flow.py"

FAKE_GH = '''\
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["pr", "list"]:
    print(os.environ.get("FAKE_GH_PR_LIST", "[]"))
elif args[:2] == ["pr", "view"]:
    print(json.dumps({"title": os.environ.get("FAKE_GH_PR_TITLE", "")}))
else:
    sys.exit(1)
'''


def _install_fake_gh(bin_dir: Path) -> None:
    """PATH の先頭に置く偽の gh を作る（Windows は gh.cmd、それ以外はシェルスクリプト）。"""
    bin_dir.mkdir()
    (bin_dir / "fake_gh.py").write_text(FAKE_GH, encoding="utf-8")
    py = Path(sys.executable).as_posix()
    if os.name == "nt":
        (bin_dir / "gh.cmd").write_text(
            f'@"{sys.executable}" "%~dp0fake_gh.py" %*\r\n', encoding="utf-8"
        )
    else:
        gh = bin_dir / "gh"
        gh.write_text(f'#!/bin/sh\nexec "{py}" "$(dirname "$0")/fake_gh.py" "$@"\n', encoding="utf-8")
        gh.chmod(0o755)


@pytest.fixture
def env(tmp_path):
    """Git の設定・一時フォルダ・gh を、テスト専用に隔離した環境変数。"""
    state_tmp = tmp_path / "state-tmp"
    state_tmp.mkdir()
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = t\n\temail = t@example.com\n"
        "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    _install_fake_gh(tmp_path / "bin")
    e = dict(os.environ)
    e.update(
        TMP=str(state_tmp), TEMP=str(state_tmp), TMPDIR=str(state_tmp),
        GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0", PYTHONUTF8="1",
        PATH=str(tmp_path / "bin") + os.pathsep + e.get("PATH", ""),
    )
    return e


@pytest.fixture
def git(env):
    def run(cwd, *args, check=True):
        r = subprocess.run(
            ["git", "-C", str(cwd), *args], env=env, capture_output=True, check=check,
        )
        return r.stdout.decode("utf-8", errors="replace").strip()
    return run


@pytest.fixture
def make_repo(tmp_path, git):
    """リポジトリを作る。github=True なら origin の URL を github.com にし、実体はローカルの bare にする。"""
    def make(name="work", remote="github"):
        work = tmp_path / name
        work.mkdir()
        git(work, "init", "-b", "main")
        (work / "README.md").write_text("# t\n", encoding="utf-8")
        git(work, "add", "-A")
        git(work, "commit", "-m", "chore: 初回")
        bare = tmp_path / (name + "-remote.git")
        if remote:
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            url = "https://github.com/test/repo.git" if remote == "github" else bare.as_posix()
            git(work, "remote", "add", "origin", url)
            if remote == "github":
                git(work, "config", f"url.{bare.as_posix()}.insteadOf", url)
            git(work, "push", "-u", "origin", "main")
            git(work, "remote", "set-head", "origin", "main")
        return SimpleNamespace(path=work, bare=bare)
    return make


@pytest.fixture
def repo(make_repo):
    return make_repo()


@pytest.fixture
def hook(env):
    """git_flow.py をサブコマンドで起動し、(終了コード, 標準出力, 標準エラー, JSON) を返す。"""
    def run(sub, payload=None, args=()):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), sub, *args], env=env, capture_output=True,
            input=json.dumps(payload or {}).encode("utf-8"), timeout=60, check=False,
        )
        out = r.stdout.decode("utf-8")
        return SimpleNamespace(
            rc=r.returncode, out=out, err=r.stderr.decode("utf-8"),
            json=json.loads(out) if out.startswith("{") else None,
        )
    return run


def tool_payload(cwd, tool, sid="s1", event="PreToolUse", **tool_input):
    return {
        "session_id": sid, "cwd": str(cwd), "hook_event_name": event,
        "tool_name": tool, "tool_input": tool_input,
    }


def denied(result):
    """PreToolUse の拒否なら理由を返す。拒否でなければ None。"""
    if not result.json:
        return None
    o = result.json["hookSpecificOutput"]
    return o["permissionDecisionReason"] if o["permissionDecision"] == "deny" else None
