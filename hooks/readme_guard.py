"""README 更新の確認を促す Hook。

使い方（settings.json の hooks から呼ぶ。入力は stdin の JSON）:
  readme_guard.py record  PostToolUse（Edit|Write）用。編集したファイルをセッションごとに記録する
  readme_guard.py check   Stop 用。README 未更新のまま対象ファイルが編集されていれば、1回だけ block する

Hook の失敗で作業を止めないため、予期しない例外は握りつぶして正常終了する。
"""
import json
import os
import re
import sys
import tempfile
import time

STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-readme-guard")
STATE_TTL_SEC = 7 * 24 * 3600

# README 更新の対象外とする編集
EXCLUDE_EXT = {".md", ".mdx", ".rst", ".txt", ".log", ".lock"}
EXCLUDE_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock",
    "cargo.lock", "gemfile.lock", "composer.lock", ".gitignore", ".gitattributes",
}
EXCLUDE_DIRS = {
    ".git", "node_modules", "docs", "test", "tests", "__tests__", "spec", "specs",
    "__pycache__", ".venv", "venv", "dist", "build",
}
EXCLUDE_NAME_PATTERNS = [
    re.compile(r"^test_.*"), re.compile(r".*_test\.[^.]+$"),
    re.compile(r".*\.(test|spec)\.[^.]+$"),
]

REASON = (
    "README.md があるプロジェクトで、README を更新せずにソース／設定ファイルを編集しました。"
    "編集内容を確認し、README.md の更新が必要なら更新してください。"
    "不要なら、その理由を一言述べてから終了してください。"
    "編集したファイル: {files}"
)


def project_root(data):
    return os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())


def find_readme(root):
    """プロジェクト直下の README.md（大文字小文字は問わない）のパスを返す。なければ None。"""
    try:
        for name in os.listdir(root):
            if name.lower() == "readme.md" and os.path.isfile(os.path.join(root, name)):
                return os.path.normcase(os.path.join(root, name))
    except OSError:
        pass
    return None


def is_target(rel_path):
    """README 更新の対象とみなすソース／設定ファイルか。"""
    parts = rel_path.replace("\\", "/").split("/")
    name = parts[-1].lower()
    if any(p.lower() in EXCLUDE_DIRS for p in parts[:-1]):
        return False
    if name in EXCLUDE_NAMES or os.path.splitext(name)[1] in EXCLUDE_EXT:
        return False
    return not any(p.match(name) for p in EXCLUDE_NAME_PATTERNS)


def state_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return os.path.join(STATE_DIR, safe + ".json")


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"pending": []}


def save_state(path, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def prune_old_states():
    try:
        now = time.time()
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if now - os.path.getmtime(p) > STATE_TTL_SEC:
                os.remove(p)
    except OSError:
        pass


def record(data):
    file_path = (data.get("tool_input") or {}).get("file_path")
    if not file_path:
        return
    root = project_root(data)
    target = os.path.abspath(file_path)
    try:
        rel = os.path.relpath(target, root)
    except ValueError:  # 別ドライブ
        return
    if rel.startswith(".."):  # プロジェクト外の編集は対象外
        return
    path = state_path(data.get("session_id"))
    state = load_state(path)
    if os.path.normcase(target) == find_readme(root):
        state["pending"] = []  # README の編集で、それ以前の編集は反映済みとみなす
    elif is_target(rel):
        if rel not in state["pending"]:
            state["pending"].append(rel)
    else:
        return
    save_state(path, state)


def check(data):
    path = state_path(data.get("session_id"))
    state = load_state(path)
    pending = state.get("pending") or []
    if not pending:
        return
    # 1回だけ block する。続行中（stop_hook_active）は通し、記録も捨てる
    state["pending"] = []
    save_state(path, state)
    if data.get("stop_hook_active") or not find_readme(project_root(data)):
        return
    reason = REASON.format(files=", ".join(pending[:10]) + (" ほか" if len(pending) > 10 else ""))
    print(json.dumps({"decision": "block", "reason": reason}))  # ensure_ascii で出力の文字コードを問わない


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if mode == "record":
        record(data)
    elif mode == "check":
        prune_old_states()
        check(data)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
