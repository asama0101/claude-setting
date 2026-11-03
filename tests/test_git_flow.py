"""hooks/git_flow.py と、それを登録する settings.json のテスト。"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT, SCRIPT, denied, tool_payload


@pytest.fixture(scope="module")
def gf():
    spec = importlib.util.spec_from_file_location("git_flow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def start_text(result):
    """session-start の出力から (systemMessage, additionalContext) を取り出す。"""
    return result.json["systemMessage"], result.json["hookSpecificOutput"]["additionalContext"]


def edit_in(repo, sid="s1", event="PreToolUse"):
    return tool_payload(repo.path, "Edit", sid, event, file_path=str(repo.path / "README.md"))


def bash_in(repo, command, sid="s1", event="PreToolUse"):
    return tool_payload(repo.path, "Bash", sid, event, command=command)


# --- 受入条件 1: Git 管理外 -------------------------------------------------


@pytest.fixture(params=["通常のフォルダ", ".git の中", "bare リポジトリ"])
def not_work_tree(request, tmp_path, repo):
    if request.param == "通常のフォルダ":
        d = tmp_path / "plain"
        d.mkdir()
        return d
    return repo.path / ".git" if request.param == ".git の中" else repo.bare


@pytest.mark.parametrize("sub", ["session-start", "pre-tool", "post-tool", "stop"])
def test_git管理外では何も出さず終了コード0(sub, not_work_tree, hook):
    payloads = [
        {"session_id": "s", "cwd": str(not_work_tree)},
        tool_payload(not_work_tree, "Bash", command="git commit -m x"),
        tool_payload(not_work_tree, "Bash", command="rm a.txt"),
        tool_payload(not_work_tree, "Edit", file_path=str(not_work_tree / "a.txt")),
    ]
    for payload in payloads:
        r = hook(sub, payload)
        assert (r.rc, r.out, r.err) == (0, "", "")


# --- 受入条件 2: session-start ---------------------------------------------


def test_session_start_ブランチと未コミットとリモート差を2か所に出す(repo, hook, git):
    (repo.path / "new.txt").write_text("x", encoding="utf-8")
    git(repo.path, "commit", "--allow-empty", "-m", "chore: 先行")
    r = hook("session-start", {"session_id": "s", "cwd": str(repo.path)})
    assert r.json["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    for text in start_text(r):
        assert "ブランチ: main / 未コミット: 1件 / リモート差: ahead 1・behind 0" in text


def test_session_start_上流のない作業ブランチは既定ブランチとの差を出す(repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    r = hook("session-start", {"session_id": "s", "cwd": str(repo.path)})
    for text in start_text(r):
        assert "リモート差: ahead 1・behind 0（上流なし。origin/main と比較）" in text


def test_session_start_リモートがなければ差を出さない(make_repo, hook):
    repo = make_repo(remote=None)
    r = hook("session-start", {"session_id": "s", "cwd": str(repo.path)})
    for text in start_text(r):
        assert "ブランチ: main / 未コミット: 0件" in text
        assert "リモート差" not in text


def test_session_start_fetchできないときは取得できずと明記して前回の差を出す(repo, hook):
    for p in repo.bare.rglob("*"):
        p.chmod(0o700)  # Windows は読み取り専用のファイルを消せない
    shutil.rmtree(repo.bare)
    r = hook("session-start", {"session_id": "s", "cwd": str(repo.path)})
    for text in start_text(r):
        assert "取得できず" in text
        assert "ahead 0・behind 0" in text


@pytest.mark.parametrize(
    ("tag", "subject", "expected"),
    [
        ("v0.1.0", "feat: 機能", "最新タグ v0.1.0 より 1 コミット新しい。リリース未作成"),
        ("v0.1.0", "docs: 文書だけ", None),
        (None, "feat: 機能", None),
    ],
    ids=["feat はリリース未作成を出す", "docs だけなら出さない", "タグがなければ出さない"],
)
def test_session_start_未リリースの1行(tag, subject, expected, repo, hook, git):
    if tag:
        git(repo.path, "tag", tag)
    git(repo.path, "commit", "--allow-empty", "-m", subject)
    git(repo.path, "push", "origin", "main")
    r = hook("session-start", {"session_id": "s", "cwd": str(repo.path)})
    for text in start_text(r):
        assert ("リリース未作成" in text) == (expected is not None)
        if expected:
            assert expected in text


# --- 受入条件 3・4: ブランチ確認と免除 --------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        ("Edit", {"file_path": "README.md"}),
        ("Write", {"file_path": "new.txt"}),
        ("NotebookEdit", {"notebook_path": "n.ipynb"}),
        ("Bash", {"command": "rm README.md"}),
        ("Bash", {"command": "git rm README.md"}),
        ("Bash", {"command": "mv README.md b.md"}),
        ("Bash", {"command": "Remove-Item README.md"}),
    ],
    ids=["Edit", "Write", "NotebookEdit", "rm", "git rm", "mv", "Remove-Item"],
)
def test_既定ブランチ上の作成削除編集はブランチ確認で止める(case, repo, hook):
    tool, tool_input = case
    for key in ("file_path", "notebook_path"):
        if key in tool_input:
            tool_input[key] = str(repo.path / tool_input[key])
    r = hook("pre-tool", tool_payload(repo.path, tool, "sess-9", **tool_input))
    reason = denied(r)
    assert reason is not None
    for expected in ("AskUserQuestion", "git switch -c", "allow-main sess-9"):
        assert expected in reason


def test_作業ブランチやリポジトリ外のファイルや読み取りでは止めない(repo, hook, git, tmp_path):
    outside = tmp_path / "outside" / "x.txt"
    assert denied(hook("pre-tool", tool_payload(repo.path, "Edit", file_path=str(outside)))) is None
    assert hook("pre-tool", bash_in(repo, "git status")).out == ""
    git(repo.path, "switch", "-c", "feat/x")
    assert hook("pre-tool", edit_in(repo)).out == ""
    assert hook("pre-tool", bash_in(repo, "rm README.md")).out == ""


def test_allow_mainの後は同じセッションだけ止めない(repo, hook):
    assert denied(hook("pre-tool", edit_in(repo, "s1"))) is not None
    r = hook("allow-main", args=("s1",))
    assert r.rc == 0
    for payload in (edit_in(repo, "s1"), bash_in(repo, "git commit -m x", "s1"),
                    bash_in(repo, "git push origin main", "s1")):
        assert hook("pre-tool", payload).out == ""
    assert denied(hook("pre-tool", edit_in(repo, "s2"))) is not None


# --- 受入条件 5・6: フロー違反 ---------------------------------------------

MAIN_VIOLATIONS = [
    "git commit -m x", "git commit -am x", "git merge feat/x", "git push",
    "git push origin main", "git push origin HEAD:main", "git push origin feat/x:main",
    "git -C . commit -m x",
]


@pytest.mark.parametrize("command", MAIN_VIOLATIONS)
def test_既定ブランチ上のcommit_merge_pushは拒否する(command, repo, hook):
    reason = denied(hook("pre-tool", bash_in(repo, command)))
    assert reason is not None
    assert "ブランチを切" in reason


@pytest.mark.parametrize(
    "command",
    ["git commit -m x", "git push", "git push -u origin feat/x", "git merge --abort"],
)
def test_作業ブランチ上のcommit_pushは拒否しない(command, repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    assert hook("pre-tool", bash_in(repo, command)).out == ""


@pytest.mark.parametrize(
    "command",
    ["git switch -c feat/x && git commit -m hi", "git checkout -b feat/x && git add . && git commit -m hi",
     "git switch -c feat/x; rm README.md"],
)
def test_同じ行でブランチを切った後のcommitや削除は拒否しない(command, repo, hook):
    assert hook("pre-tool", bash_in(repo, command)).out == ""


def test_同じ行でブランチを切っても既定ブランチへのpushは拒否する(repo, hook):
    reason = denied(hook("pre-tool", bash_in(repo, "git switch -c feat/x && git push origin HEAD:main")))
    assert reason is not None


def test_リポジトリ外のファイルのrmとmvは止めず_リポジトリ内は止める(repo, hook, tmp_path):
    outside = (tmp_path / "outside" / "x.txt").as_posix()
    assert hook("pre-tool", bash_in(repo, f"rm {outside}")).out == ""
    assert hook("pre-tool", bash_in(repo, f"mv {outside} {outside}.bak")).out == ""
    assert denied(hook("pre-tool", bash_in(repo, "rm -rf node_modules"))) is not None
    assert denied(hook("pre-tool", bash_in(repo, f"mv {outside} README.md"))) is not None


def test_cdで別のフォルダに移った後のcommitはそのフォルダで判定する(repo, hook, tmp_path):
    (repo.path / "sub").mkdir()
    assert denied(hook("pre-tool", bash_in(repo, "cd sub && git commit -m x"))) is not None
    other = tmp_path / "other"
    other.mkdir()
    assert hook("pre-tool", bash_in(repo, f"cd {other} && git commit -m y")).out == ""
    assert denied(hook("pre-tool", bash_in(repo, f"cd {repo.path} && git commit -m y"))) is not None


def test_パスにバックスラッシュを含むgit_Cでもその場所のリポジトリで判定する(repo, hook, tmp_path):
    payload = tool_payload(tmp_path, "Bash", command=f"git -C {repo.path} commit -m y")
    assert denied(hook("pre-tool", payload)) is not None
    outside = tmp_path / "outside" / "x.txt"
    assert hook("pre-tool", tool_payload(repo.path, "Bash", command=f"rm {outside}")).out == ""


@pytest.mark.parametrize("command", ["cd - && git commit -m x", "cd $PWD && git commit -m x",
                                     "cd -P sub && git commit -m x"])
def test_cdの行き先が分からないときは元のフォルダで判定する(command, repo, hook):
    (repo.path / "sub").mkdir()
    assert denied(hook("pre-tool", bash_in(repo, command))) is not None


def test_サブシェルや_または_の中のcdは作業フォルダを変えない(repo, hook, tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    for command in (f"(cd {outside} && ls); git commit -m x", f"cd {outside} || git commit -m x"):
        assert denied(hook("pre-tool", bash_in(repo, command))) is not None, command


def test_括弧や_または_を含む行でも_cd先のリポジトリのcommitを拒否する(repo, make_repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    other = make_repo("other", remote=None)  # other は main
    for command in (f'cd {other.path} && git commit -m "feat(core): x"', f"(cd {other.path} && git commit -m x)",
                    f"cd {other.path} || true; git commit -m x"):
        assert denied(hook("pre-tool", bash_in(repo, command))) is not None, command


def test_サブシェルの中で切ったブランチは_外のcommitを許可しない(repo, make_repo, hook):
    other = make_repo("other", remote=None)
    for command in (f"(cd {other.path} && git switch -c n); git commit -m x",
                    f"(cd {other.path} && git switch -c n) && git commit -m x"):
        assert denied(hook("pre-tool", bash_in(repo, command))) is not None, command


def test_commitメッセージの括弧はサブシェルとみなさず_ブランチ作成後は許可する(repo, hook):
    command = 'git switch -c foo && git commit -m "feat(core): x"'
    assert hook("pre-tool", bash_in(repo, command)).out == ""


def test_ブランチを切った後にサブフォルダへcdしても新しいブランチ上として扱う(repo, hook):
    (repo.path / "sub").mkdir()
    for command in ("git switch -c foo && cd sub && git commit -m x",
                    "git switch -c foo && cd sub && cd .. && git commit -m x"):
        assert hook("pre-tool", bash_in(repo, command)).out == "", command


def test_別のリポジトリでブランチを切っても元のリポジトリのcommitは拒否する(repo, make_repo, hook):
    other = make_repo("other", remote=None)
    switched_other = f"git -C {other.path} switch -c foo && git commit -m x"
    assert denied(hook("pre-tool", bash_in(repo, switched_other))) is not None
    moved_to_other = f"git switch -c foo; cd {other.path} && git commit -m x"
    assert denied(hook("pre-tool", bash_in(repo, moved_to_other))) is not None


def test_状態ファイルの置き換えがロックで失敗しても再試行して保存する(gf, tmp_path, monkeypatch):
    monkeypatch.setattr(gf, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(gf, "RETRY_WAIT_SEC", 0)
    real_replace, calls = Path.replace, []

    def locked_twice(self, target):
        calls.append(target)
        if len(calls) < 3:
            raise PermissionError(13, "locked")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", locked_twice)
    gf.save_state("s1", {"allow_main": True})
    assert len(calls) == 3
    assert gf.load_state("s1") == {"allow_main": True}


def test_既定ブランチ上のff_onlyによるリモート追従は拒否しない(repo, hook):
    assert hook("pre-tool", bash_in(repo, "git merge --ff-only origin/main")).out == ""
    assert denied(hook("pre-tool", bash_in(repo, "git merge --ff-only feat/x"))) is not None


@pytest.mark.parametrize("command", ["git push origin v1.0.0", "git push --tags", "git status"])
def test_既定ブランチ上でもタグのpushや読み取りは拒否しない(command, repo, hook):
    assert hook("pre-tool", bash_in(repo, command)).out == ""


def test_コミットが1つもないリポジトリの最初のコミットと編集は拒否しない(tmp_path, hook, env):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(empty)], env=env, check=True, capture_output=True)
    payload = tool_payload(empty, "Bash", command="git commit -m 'chore: 初回'")
    assert hook("pre-tool", payload).out == ""
    assert hook("pre-tool", tool_payload(empty, "Write", file_path=str(empty / "a.txt"))).out == ""


FORCE_PUSHES = [
    "git push --force", "git push -f origin feat/x", "git push --force-with-lease origin feat/x",
    "git push origin +feat/x", "git push -fu origin feat/x",
]


@pytest.mark.parametrize("command", FORCE_PUSHES)
def test_force_pushは免除があっても作業ブランチでも拒否する(command, repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    hook("allow-main", args=("s1",))
    assert denied(hook("pre-tool", bash_in(repo, command))) is not None


# --- 受入条件 7・8: gh pr merge ---------------------------------------------


def prepare_release(repo, git, env):
    git(repo.path, "tag", "v0.1.0")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: 先行機能")
    git(repo.path, "push", "origin", "main", "v0.1.0")
    git(repo.path, "switch", "-c", "feat/x")
    env["FAKE_GH_PR_TITLE"] = "fix: 直し"


def test_記録のないgh_pr_mergeは最新タグと提案する版とallow_mergeを示して拒否する(repo, hook, git, env):
    prepare_release(repo, git, env)
    reason = denied(hook("pre-tool", bash_in(repo, "gh pr merge --squash", "sess-7")))
    assert reason is not None
    for expected in ("v0.1.0", "v0.2.0", "allow-merge sess-7", "feat: 先行機能"):
        assert expected in reason


@pytest.mark.parametrize("command", ["gh pr merge --merge", "gh pr merge", "gh pr merge --squash --auto"])
def test_squash以外とautoのgh_pr_mergeは記録があっても拒否する(command, repo, hook):
    hook("allow-merge", args=("s1", "v0.2.0"))
    assert denied(hook("pre-tool", bash_in(repo, command))) is not None


def test_allow_mergeの後のマージは通りマージ後に記録が消える(repo, hook, git, env):
    prepare_release(repo, git, env)
    hook("allow-merge", args=("s1", "v0.2.0"))
    assert hook("pre-tool", bash_in(repo, "gh pr merge 12 --squash")).out == ""
    post = hook("post-tool", bash_in(repo, "gh pr merge 12 --squash", event="PostToolUse"))
    context = post.json["hookSpecificOutput"]["additionalContext"]
    for expected in ("git tag v0.2.0 origin/main", "git push origin v0.2.0",
                     "gh release create v0.2.0 --generate-notes", "MERGED"):
        assert expected in context
    assert denied(hook("pre-tool", bash_in(repo, "gh pr merge 12 --squash"))) is not None


def test_skipを選んだマージではタグの指示を出さず記録だけ消す(repo, hook):
    hook("allow-merge", args=("s1", "skip"))
    assert hook("pre-tool", bash_in(repo, "gh pr merge --squash")).out == ""
    assert hook("post-tool", bash_in(repo, "gh pr merge --squash", event="PostToolUse")).out == ""
    assert denied(hook("pre-tool", bash_in(repo, "gh pr merge --squash"))) is not None


def test_github以外のリモートではgh_pr_mergeを拒否しない(make_repo, hook):
    repo = make_repo(remote="other")
    assert hook("pre-tool", bash_in(repo, "gh pr merge --squash")).out == ""


# --- 受入条件 14: 版の書式の検査 ---------------------------------------------


@pytest.mark.parametrize(("version", "rc"), [
    ("v1.2.3", 0), ("v0.1.0", 0), ("skip", 0),
    ("1.2.3", 2), ("V1.2.3", 2), ("v1.2", 2), ("v01.2.3", 2), ("v1.2.3-rc.1", 2),
])
def test_allow_mergeは版の書式を検査する(version, rc, hook):
    assert hook("allow-merge", args=("s1", version)).rc == rc


@pytest.mark.parametrize("command", ["git tag v1.2.3", "git tag -a v1.2.3 -m x", "git tag -l",
                                     "git tag -d v1.2.3", "git tag --list 'v*'", "git tag"])
def test_書式に合うタグの作成と一覧削除は拒否しない(command, make_repo, hook):
    repo = make_repo(remote=None)
    assert hook("pre-tool", bash_in(repo, command)).out == ""


@pytest.mark.parametrize("command", ["git tag 1.2.3", "git tag release", "git tag -a foo -m x",
                                     "git tag v1.2", "git tag V1.2.3"])
def test_書式に合わないタグの作成は拒否する(command, make_repo, hook):
    repo = make_repo(remote=None)
    reason = denied(hook("pre-tool", bash_in(repo, command)))
    assert reason is not None
    assert "vMAJOR.MINOR.PATCH" in reason


# --- 受入条件 9: stop -------------------------------------------------------


def mark_edit(hook, repo, sid):
    hook("post-tool", edit_in(repo, sid, "PostToolUse"))


def stop(hook, repo, sid, **extra):
    return hook("stop", {"session_id": sid, "cwd": str(repo.path), **extra})


def test_stop_編集後の未コミットはコミットを促し同じ状態では1回だけ(repo, hook):
    (repo.path / "README.md").write_text("# 変更\n", encoding="utf-8")
    mark_edit(hook, repo, "s1")
    r = stop(hook, repo, "s1")
    assert r.json["decision"] == "block"
    assert "コミット" in r.json["reason"]
    assert "README.md" in r.json["reason"]
    assert stop(hook, repo, "s1").out == ""


def test_stop_編集のないセッションとstop_hook_activeでは何も返さない(repo, hook):
    (repo.path / "README.md").write_text("# 変更\n", encoding="utf-8")
    assert stop(hook, repo, "no-edit").out == ""
    mark_edit(hook, repo, "active")
    assert stop(hook, repo, "active", stop_hook_active=True).out == ""


def test_stop_bashの削除も編集として数える(repo, hook):
    (repo.path / "README.md").unlink()
    hook("post-tool", bash_in(repo, "rm README.md", "s1", "PostToolUse"))
    assert "コミット" in stop(hook, repo, "s1").json["reason"]


def test_stop_コミット済みで未pushならpushを促す(repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    mark_edit(hook, repo, "s1")
    reason = stop(hook, repo, "s1").json["reason"]
    assert "push" in reason
    assert "コミットしてください" not in reason


def test_stop_push済みでprがなければprを促し_あれば何も返さない(repo, hook, git, env):
    git(repo.path, "switch", "-c", "feat/x")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    git(repo.path, "push", "-u", "origin", "feat/x")
    env["FAKE_GH_PR_LIST"] = "[]"
    mark_edit(hook, repo, "no-pr")
    assert "PR" in stop(hook, repo, "no-pr").json["reason"]
    env["FAKE_GH_PR_LIST"] = json.dumps([{"number": 1}])
    mark_edit(hook, repo, "has-pr")
    assert stop(hook, repo, "has-pr").out == ""


def test_stop_未コミットとpush待ちが両方あればコミットを先に促す(repo, hook, git):
    git(repo.path, "switch", "-c", "feat/x")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    (repo.path / "new.txt").write_text("x", encoding="utf-8")
    mark_edit(hook, repo, "s1")
    assert "コミット" in stop(hook, repo, "s1").json["reason"]


def test_stop_既定ブランチ上では免除がなければpushを促さない(repo, hook, git):
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    mark_edit(hook, repo, "s1")
    assert stop(hook, repo, "s1").out == ""
    hook("allow-main", args=("s2",))
    mark_edit(hook, repo, "s2")
    assert "push" in stop(hook, repo, "s2").json["reason"]


def test_stop_github以外のリモートではpushやprを促さない(make_repo, hook, git):
    repo = make_repo(remote="other")
    git(repo.path, "switch", "-c", "feat/x")
    git(repo.path, "commit", "--allow-empty", "-m", "feat: x")
    mark_edit(hook, repo, "s1")
    assert stop(hook, repo, "s1").out == ""


# --- 版の決め方 -------------------------------------------------------------


@pytest.mark.parametrize(
    ("latest", "messages", "expected"),
    [
        ("v1.2.3", ["feat: a", "fix: b"], "v1.3.0"),
        ("v1.2.3", ["fix: a", "docs: b"], "v1.2.4"),
        ("v1.2.3", ["perf: a"], "v1.2.4"),
        ("v1.2.3", ["refactor(core): a"], "v1.2.4"),
        ("v1.2.3", ["docs: a", "chore: b", "test: c", "ci: d", "style: e", "build: f"], "skip"),
        ("v1.2.3", ["feat!: a"], "v2.0.0"),
        ("v1.2.3", ["fix: a\n\nBREAKING CHANGE: b"], "v2.0.0"),
        ("v0.3.0", ["feat!: a"], "v0.4.0"),
        ("v0.3.4", ["fix: a\n\nBREAKING CHANGE: b"], "v0.4.0"),
        ("v0.3.0", ["feat: a"], "v0.4.0"),
        (None, ["docs: a"], "v0.1.0"),
        ("v1.2.3", ["メッセージに type がない"], "skip"),
    ],
    ids=["feat は MINOR", "fix は PATCH", "perf は PATCH", "refactor は PATCH", "docs などだけなら skip",
         "! は MAJOR", "BREAKING CHANGE は MAJOR", "0.y.z の ! は MINOR", "0.y.z の BREAKING は MINOR",
         "0.y.z の feat は MINOR", "タグなしは v0.1.0", "type なしは数えない"],
)
def test_次の版の決め方(latest, messages, expected, gf):
    assert gf.next_version(latest, messages) == expected


# --- 受入条件 10〜13・16: 設定と文書 -----------------------------------------


@pytest.fixture(scope="module")
def settings():
    return json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))


def all_hook_commands(settings):
    return [h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]]


def test_settings_新しいhookが登録されている(settings):
    hooks = settings["hooks"]
    expected = {
        "SessionStart": 'git_flow.py" session-start',
        "PreToolUse": 'git_flow.py" pre-tool',
        "PostToolUse": 'git_flow.py" post-tool',
        "Stop": 'git_flow.py" stop',
    }
    for event, needle in expected.items():
        commands = [h["command"] for g in hooks[event] for h in g["hooks"]]
        assert any(needle in c for c in commands), event


def test_settings_hookのコマンドはすべてpy_python3_pythonの順に試す形(settings):
    commands = all_hook_commands(settings)
    assert len(commands) == 6
    for c in commands:
        m = re.fullmatch(
            r'py (?P<a>"[^"]+"[^|]*?) 2>/dev/null \|\| python3 (?P=a) 2>/dev/null '
            r'\|\| python (?P=a) 2>/dev/null \|\| true', c,
        )
        assert m, c


def test_settings_ベアな環境でも各hookはエラー出力なしで終了コード0(settings, tmp_path):
    candidates = [p / "bin" / "bash.exe" for p in Path(shutil.which("git")).parents] + [Path("/bin/bash")]
    bash = next((p for p in candidates if p.exists()), None)
    if bash is None:
        pytest.skip("git に同梱の bash か /bin/bash が見つからない（環境要因）")
    bare_env = {"PATH": str(bash.parent), "HOME": str(tmp_path)}
    if os.environ.get("SYSTEMROOT"):
        bare_env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    for c in all_hook_commands(settings):
        r = subprocess.run([str(bash), "-c", c], env=bare_env, capture_output=True, input=b"{}",
                           timeout=60, check=False)
        assert (r.returncode, r.stdout, r.stderr) == (0, b"", b""), c


def test_settings_permissions_askにgh_release_createがあり件数がreadmeと一致する(settings):
    ask = settings["permissions"]["ask"]
    assert "Bash(gh release create *)" in ask
    assert len(ask) == 11
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "| `permissions.ask` | 11 件 |" in readme


def test_uncommitted_warnは削除され参照が残っていない():
    assert not (ROOT / "hooks" / "uncommitted_warn.py").exists()
    for name in ("settings.json", "README.md", "global-CLAUDE.md", "statusline.py"):
        assert "uncommitted_warn" not in (ROOT / name).read_text(encoding="utf-8"), name
    for p in (ROOT / "hooks").glob("*.py"):
        assert "uncommitted_warn" not in p.read_text(encoding="utf-8"), p.name


def test_docs_git_flowに必要な内容がある():
    text = (ROOT / "docs" / "git-flow.md").read_text(encoding="utf-8")
    steps = re.findall(r"^[1-8]\. ", text.split("## 基本フロー")[1].split("##")[0], re.MULTILINE)
    assert len(steps) == 8
    for expected in ("## バージョン表記の定義", r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
                     "## 各段階を Hook がどう扱うか", "feat/", "fix/", "docs/", "chore/", "--squash"):
        assert expected in text, expected
