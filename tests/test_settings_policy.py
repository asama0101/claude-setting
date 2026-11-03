"""settings.json の permissions 方針（SPEC A-1〜A-3, A-6）のテスト。

方針: permissions で防ぐのは、秘密情報の閲覧・編集と、修復できない破壊的コマンドだけ。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

ASK = {
    "Bash(git reset --hard *)", "Bash(git clean *)", "Bash(git checkout -- *)", "Bash(git restore *)",
    "Bash(git checkout .)", "Bash(rm -r *)", "Bash(rm -rf *)", "Bash(rm -fr *)",
    "Bash(git switch --discard-changes *)", "Bash(git switch -f *)", "Bash(git switch --force *)",
}
ASK_REMOVED = {"Bash(git push *)", "Bash(git tag *)", "Bash(gh pr merge *)", "Bash(gh release create *)"}
ALLOW_ADDED = {
    "Bash(py -m pytest *)", "Bash(py -m ruff *)", "Bash(git add *)", "Bash(git switch *)", "Bash(git commit *)",
}
DENY_ADDED = {
    "Read(**/.aws/config)", "Read(**/.git/config)", "Read(**/*.jks)", "Read(**/*.keystore)",
    "Read(**/credentials*)",
    "Edit(**/AppData/Local/Microsoft/Credentials/**)", "Edit(**/AppData/Roaming/Microsoft/Credentials/**)",
    "Edit(**/AppData/Roaming/Microsoft/Protect/**)", "Edit(**/System32/config/SAM)",
    "Edit(**/System32/config/SYSTEM)", "Edit(**/System32/config/SECURITY)", "Edit(**/NTUSER.DAT)",
}


@pytest.fixture(scope="module")
def settings():
    return json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))


def test_askは修復できない破壊的コマンドだけで11件(settings):
    ask = settings["permissions"]["ask"]
    assert set(ask) == ASK
    assert len(ask) == 11
    assert not ASK_REMOVED & set(ask)


def test_allowに追加した5件があり16件(settings):
    allow = settings["permissions"]["allow"]
    assert ALLOW_ADDED <= set(allow)
    assert len(allow) == 16
    assert len(set(allow)) == len(allow)


def test_denyは既存56件に12件を足した68件で重複がない(settings):
    deny = settings["permissions"]["deny"]
    assert DENY_ADDED <= set(deny)
    assert len(deny) == 68
    assert len(set(deny)) == 68


def test_denyの既存56件が残っている(settings):
    deny = set(settings["permissions"]["deny"])
    for pattern in ("Read(**/.env)", "Edit(**/.ssh/**)", "Bash(sudo *)", "Edit(**/Windows/System32/**)",
                    "Read(**/System32/config/SAM)", "Read(**/NTUSER.DAT)"):
        assert pattern in deny, pattern


def test_readme_guardはhooksに登録されていない(settings):
    commands = [h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]]
    assert not [c for c in commands if "readme_guard" in c]


def test_git_flowの4種とnotifyの3種のhookだけが残っている(settings):
    commands = [h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]]
    assert len(commands) == 7  # git_flow の 4 件 + notify の 3 件（通知 Hook の SPEC）
    for sub in ("session-start", "pre-tool", "post-tool", "stop"):
        assert sum(f'git_flow.py" {sub}' in c for c in commands) == 1, sub
    assert sum("notify.py" in c for c in commands) == 3


def test_readme_guardのファイルは残っている():
    assert (ROOT / "hooks" / "readme_guard.py").exists()
