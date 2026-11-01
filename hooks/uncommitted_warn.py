"""未コミットの変更を警告する Hook（block はしない）。

使い方（settings.json の Stop hook から呼ぶ。入力は stdin の JSON）:
  uncommitted_warn.py  Git リポジトリで未コミットの変更があれば、systemMessage で警告する

Stop は応答のたびに走るため、同じ変更内容では同じセッション中に1回しか警告しない。
Hook の失敗で作業を止めないため、予期しない例外は握りつぶして正常終了する。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-commit-warn")
STATE_TTL_SEC = 7 * 24 * 3600
MAX_FILES = 10  # 警告に列挙するファイル数の上限


def git_status(cwd):
    """`git status --porcelain` の出力を返す。Git リポジトリでない、または失敗したら None。"""
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def state_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return os.path.join(STATE_DIR, safe + ".txt")


def prune_old_states():
    try:
        now = time.time()
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if now - os.path.getmtime(p) > STATE_TTL_SEC:
                os.remove(p)
    except OSError:
        pass


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    prune_old_states()
    status = git_status(cwd)
    if not status or not status.strip():
        return
    digest = hashlib.sha256(status.encode("utf-8")).hexdigest()
    path = state_path(data.get("session_id"))
    try:
        with open(path, encoding="utf-8") as f:
            if f.read().strip() == digest:
                return  # 同じ変更内容は警告済み
    except OSError:
        pass
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(digest)
    lines = status.splitlines()
    shown = ["  " + line for line in lines[:MAX_FILES]]
    if len(lines) > MAX_FILES:
        shown.append("  ほか %d 件" % (len(lines) - MAX_FILES))
    message = "未コミットの変更が %d 件あります。\n%s" % (len(lines), "\n".join(shown))
    print(json.dumps({"systemMessage": message}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
