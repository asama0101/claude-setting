"""Git/GitHub のフロー（GitHub Flow）を促し、守らせる Hook。

使い方（settings.json の hooks から呼ぶ。入力は stdin の JSON）:
  git_flow.py session-start  SessionStart 用。ブランチ・未コミット・リモートとの差を知らせる
  git_flow.py pre-tool       PreToolUse 用。ブランチ確認、フロー違反、gh pr merge（常に拒否）、タグ名を検査する
  git_flow.py post-tool      PostToolUse 用。編集の記録
  git_flow.py stop           Stop 用。編集があれば、コミット・push・PR を促す

Claude が Bash で実行するコマンド（Hook の拒否理由が、引数ごと示す）:
  git_flow.py allow-main <session_id>  このセッションだけ、ブランチ確認と main 直コミットの拒否を外す

Git 管理外のフォルダでは何もしない。Hook の失敗で作業を止めないため、
予期しない例外は標準エラー出力に1行書いて、終了コード 0 で終わる。
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from functools import cache
from pathlib import Path

SCRIPT = Path(__file__).resolve()
STATE_DIR = Path(tempfile.gettempdir()) / "claude-git-flow"
STATE_TTL_SEC = 7 * 24 * 3600
GIT_TIMEOUT = 5
RETRIES = 10
RETRY_WAIT_SEC = 0.02
FETCH_TIMEOUT = 5
KILL_TIMEOUT = 2
MAX_LINES = 10  # 理由に列挙する行数の上限

TAG_RE = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
TAG_PATTERN = r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
TYPE_RE = re.compile(r"^(\w+)(?:\([^)]*\))?(!)?:")
BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)
PATCH_TYPES = {"fix", "perf", "refactor"}

FILE_TOOLS = {"Edit", "Write", "NotebookEdit"}
FILE_OP_COMMANDS = {"rm", "mv", "remove-item"}
NEW_BRANCH_FLAGS = {"-c", "-C", "--create", "-b", "-B"}
SEPARATORS = set(";&|()")
LIST_TAG_FLAGS = {"-l", "--list", "-d", "--delete", "-v", "--verify", "--contains",
                  "--no-contains", "--merged", "--no-merged", "--points-at", "--sort", "--format"}
TAG_VALUE_FLAGS = {"-m", "-F", "-u", "--message", "--file", "--local-user"}


# --- Git の呼び出し ---------------------------------------------------------


def run(argv: list[str], cwd: str | Path, timeout: int = GIT_TIMEOUT) -> tuple[int, str] | None:
    """外部コマンドを実行し、(終了コード, 標準出力) を返す。起動できない・時間切れなら None。"""
    try:
        r = subprocess.run(  # noqa: S603
            argv, cwd=str(cwd), capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.returncode, r.stdout.decode("utf-8", errors="replace").rstrip()


def fetch(d: str) -> bool:
    """`git fetch` を FETCH_TIMEOUT 秒だけ待つ。成功したら True。時間切れなら、子プロセスごと止めて False。

    出力のパイプを使わない。子の git-remote-http がパイプを握ると、親を止めても終了を待ち続けるため。
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        proc = subprocess.Popen(  # noqa: S603
            ["git", "fetch", "--quiet"],  # noqa: S607
            cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
        )
    except OSError:
        return False
    try:
        return proc.wait(FETCH_TIMEOUT) == 0
    except subprocess.TimeoutExpired:
        # 子プロセスごと止める。止められなくても（taskkill がない、権限がない）、親は止めて待たずに戻る
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],  # noqa: S603, S607
                               capture_output=True, check=False, timeout=KILL_TIMEOUT)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(KILL_TIMEOUT)
        return False


@cache
def ok(cwd: str, *args: str) -> str | None:
    """`git <args>` が成功したときの標準出力。失敗したら None。同じ呼び出しは1回だけ実行する。"""
    r = run(["git", *args], cwd)  # noqa: S607
    return r[1] if r and r[0] == 0 else None


def is_work_tree(d: str | Path) -> bool:
    return ok(str(d), "rev-parse", "--is-inside-work-tree") == "true"


def current_branch(d: str) -> str | None:
    return ok(d, "symbolic-ref", "--short", "-q", "HEAD")


def has_commits(d: str) -> bool:
    return ok(d, "rev-parse", "--verify", "-q", "HEAD") is not None


def default_branch(d: str) -> str | None:
    """既定ブランチ。origin/HEAD が指すブランチ。なければ main、master の順に存在するもの。"""
    head = ok(d, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.split("/", 1)[-1]
    for name in ("main", "master"):
        if ok(d, "show-ref", "--verify", "--quiet", "refs/heads/" + name) is not None:
            return name
    return None


def is_github(d: str) -> bool:
    """origin の URL（設定の値そのまま）に github.com を含むか。"""
    return "github.com" in (ok(d, "config", "--get", "remote.origin.url") or "")


def ahead_behind(d: str, base: str = "@{u}") -> tuple[int, int] | None:
    """base（既定は上流ブランチ）との差 (ahead, behind)。base がなければ None。"""
    out = ok(d, "rev-list", "--left-right", "--count", f"HEAD...{base}")
    if not out:
        return None
    ahead, behind = out.split()
    return int(ahead), int(behind)


def status_lines(d: str) -> list[str]:
    return (ok(d, "status", "--porcelain") or "").splitlines()


def nearest_dir(path: Path) -> Path:
    """ファイルの親フォルダ。まだなければ、存在する最も近い上位のフォルダ。"""
    d = path.parent
    while not d.is_dir() and d != d.parent:
        d = d.parent
    return d


def release_ref(d: str, default: str) -> str:
    return f"origin/{default}" if ok(d, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{default}") else default


def latest_tag(d: str, ref: str) -> str | None:
    tags = (ok(d, "tag", "--list", "v*", "--merged", ref, "--sort=-v:refname") or "").splitlines()
    return next((t for t in tags if TAG_RE.fullmatch(t)), None)


def commit_messages(d: str, ref: str, since: str | None) -> list[str]:
    out = ok(d, "log", "--format=%B%x00", f"{since}..{ref}" if since else ref) or ""
    return [m.strip() for m in out.split("\x00") if m.strip()]


# --- 版の決め方 -------------------------------------------------------------


def next_version(latest: str | None, messages: list[str]) -> str:
    """前のタグとコミット件名から、次の版（`vX.Y.Z`）または `skip` を返す。reference/git-flow.md の定義に従う。"""
    if latest is None:
        return "v0.1.0"
    major, minor, patch = (int(x) for x in latest[1:].split("."))
    level = 0  # 1: PATCH、2: MINOR、3: 破壊的変更
    for msg in messages:
        m = TYPE_RE.match(msg)
        if BREAKING_RE.search(msg) or (m and m.group(2)):
            level = max(level, 3)
        elif m:
            level = max(level, 2 if m.group(1) == "feat" else 1 if m.group(1) in PATCH_TYPES else 0)
    if level == 0:
        return "skip"
    if level == 3:
        return f"v{major + 1}.0.0" if major >= 1 else f"v0.{minor + 1}.0"
    return f"v{major}.{minor + 1}.0" if level == 2 else f"v{major}.{minor}.{patch + 1}"


# --- セッションの状態 -------------------------------------------------------


def state_file(sid: str | None) -> Path:
    return STATE_DIR / (re.sub(r"[^A-Za-z0-9_-]", "_", sid or "unknown") + ".json")


def retry_if_locked(action):
    """Windows では、別のプロセスが開いているファイルへの操作が PermissionError になる。短く待って再試行する。"""
    for _ in range(RETRIES):
        try:
            return action()
        except PermissionError:
            time.sleep(RETRY_WAIT_SEC)
    return action()


def load_state(sid: str | None) -> dict:
    try:
        return json.loads(retry_if_locked(lambda: state_file(sid).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def save_state(sid: str | None, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_DIR / f"{os.getpid()}.tmp"  # 並列の Hook が、書きかけのファイルを読まないようにする
    tmp.write_text(json.dumps(state), encoding="utf-8")
    retry_if_locked(lambda: tmp.replace(state_file(sid)))


def prune_old_states() -> None:
    now = time.time()
    for p in [*STATE_DIR.glob("*.json"), *STATE_DIR.glob("*.tmp")]:
        try:
            if now - p.stat().st_mtime > STATE_TTL_SEC:
                p.unlink()
        except OSError:
            continue


def helper_command(sub: str, *args: str) -> str:
    return " ".join([f'"{Path(sys.executable).as_posix()}"', f'"{SCRIPT.as_posix()}"', sub, *args])


# --- Bash コマンドの解析 ----------------------------------------------------


def tokenize(command: str) -> list[str]:
    """Bash のコマンド行を、単語と、`&&`・`;`・`|`・`(` などの演算子に分ける。"""
    text = command.replace("\n", " ; ")
    if os.name == "nt":
        text = text.replace("\\", "/")  # shlex は、引用符の外のバックスラッシュを消す
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return text.split()


def is_operator(token: str) -> bool:
    return bool(token) and set(token) <= SEPARATORS


def split_commands(command: str) -> list[list[str]]:
    """Bash のコマンド行を、`&&`・`;`・`|` などで区切った単語の列にする。"""
    segments: list[list[str]] = [[]]
    for t in tokenize(command):
        if is_operator(t):
            segments.append([])
        else:
            segments[-1].append(t)
    return [seg for seg in segments if seg]


def has_grouping(command: str) -> bool:
    """引用符の外に、サブシェルの括弧か `||` があるか。そこでの cd やブランチ作成は、後ろに効くとは限らない。"""
    return any(is_operator(t) and ("(" in t or ")" in t or "||" in t) for t in tokenize(command))


def strip_env(words: list[str]) -> list[str]:
    i = 0
    while i < len(words) and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", words[i]):
        i += 1
    return words[i:]


def parse_git(words: list[str]) -> tuple[str, list[str], str | None] | None:
    """`git [-C dir] <サブコマンド> <引数>` を (サブコマンド, 引数, -C のフォルダ) にする。"""
    if not words or Path(words[0]).name.lower() not in ("git", "git.exe"):
        return None
    i, cdir = 1, None
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            cdir, i = words[i + 1], i + 2
        elif words[i] == "-c":
            i += 2
        else:
            i += 1
    return (words[i], words[i + 1:], cdir) if i < len(words) else None


def is_gh_pr_merge(words: list[str]) -> bool:
    """`gh pr merge ...` か。フラグは位置に関係なく読み飛ばす（-R・--repo は値も飛ばす）。"""
    if not words or Path(words[0]).name.lower() not in ("gh", "gh.exe"):
        return False
    positional, skip = [], False
    for w in words[1:]:
        if skip:
            skip = False
        elif w in ("-R", "--repo"):
            skip = True
        elif not w.startswith("-"):
            positional.append(w)
    return positional[:2] == ["pr", "merge"]


def analyze_push(args: list[str], branch: str | None, default: str) -> tuple[bool, bool]:
    """`git push` の引数から (force か, 既定ブランチへの push か) を返す。"""
    force, flags, positional = False, set(), []
    for a in args:
        if a in ("--force", "-f") or a.startswith(("--force-with-lease", "--force-if-includes")):
            force = True
        elif a.startswith("--"):
            flags.add(a)
        elif a.startswith("-") and len(a) > 1:
            force = force or "f" in a[1:]
        else:
            positional.append(a)
    refspecs = positional[1:]
    force = force or any(r.startswith("+") for r in refspecs)
    if "--all" in flags or "--mirror" in flags:
        return force, True
    if refspecs:
        dsts = [r.lstrip("+").split(":")[-1].removeprefix("refs/heads/") for r in refspecs]
        return force, any((branch if d == "HEAD" else d) == default for d in dsts)
    return force, "--tags" not in flags and branch == default


# --- 拒否・促しの文面 -------------------------------------------------------


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))


def branch_question(sid: str | None, default: str, header: str) -> str:
    return (
        f"{header}\n"
        "次の順で進めてください。\n"
        "1. AskUserQuestion でユーザーに「ブランチを切る（推奨）／切らない」を聞く"
        "（先頭の選択肢は「ブランチを切る（推奨）」）。"
        "質問できないとき（非対話実行、質問ツールがないサブエージェント）は、作業を止めてユーザーに報告する。\n"
        "2. 「切る」なら、作業内容に合う名前（feat/…・fix/…・docs/…・chore/…）で "
        "`git switch -c <名前>` を実行し、元の操作をやり直す。\n"
        f"3. 「切らない」なら `{helper_command('allow-main', str(sid))}` を Bash ツールで実行し、元の操作をやり直す"
        f"（このセッションの間、この確認と、{default} への commit・push の拒否が外れる）。"
    )


def tag_reason(args: list[str]) -> str | None:
    """新しいタグを作る `git tag` で、タグ名が書式に合わないときの理由。一覧・削除などは None。"""
    names, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a in LIST_TAG_FLAGS or a.startswith(("--list", "--delete", "--contains", "-n")):
            return None
        elif a in TAG_VALUE_FLAGS:
            skip = True
        elif not a.startswith("-"):
            names.append(a)
    if not names or TAG_RE.fullmatch(names[0]):
        return None
    return (f"タグ名 {names[0]} は、書式 vMAJOR.MINOR.PATCH（正規表現 {TAG_PATTERN}）に合いません。"
            "reference/git-flow.md の「バージョン表記の定義」に合わせた名前にしてください。")


# --- 契機ごとの処理 ---------------------------------------------------------


def segment_dir(cwd: Path, cdir: str | None) -> str:
    if not cdir:
        return str(cwd)
    return str(Path(cdir) if Path(cdir).is_absolute() else cwd / cdir)


def edit_gate(d: str, sid: str | None, state: dict, new_branch: bool = False) -> str | None:
    """ファイルの作成・削除・編集の前に、ブランチを切るか確認させる理由。確認が要らなければ None。"""
    if new_branch:
        return None
    branch, default = current_branch(d), default_branch(d)
    if default and branch == default and has_commits(d) and not state.get("allow_main"):
        return branch_question(
            sid, default,
            f"現在 {branch}（既定ブランチ）です。ファイルの作成・削除・編集の前に、ブランチを切るか確認します。")
    return None


def expand_path(word: str) -> Path:
    """`$VAR`・`${VAR}`・`~` を展開したパス。未定義の変数と、cd で変わる PWD・OLDPWD は、そのまま残す。"""
    def value(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        found = None if name in ("PWD", "OLDPWD") else os.environ.get(name)
        if name == "HOME" and not found:
            found = str(Path.home())
        if found is None:
            return m.group(0)
        if os.name == "nt" and re.match(r"/[A-Za-z](/|$)", found):  # msys 形式（/c/Users/…）を C:/Users/… にする
            found = f"{found[1].upper()}:{found[2:] or '/'}"
        return found

    return Path(re.sub(r"\$(?:\{(\w+)\}|(\w+))", value, word)).expanduser()


def is_file_op(words: list[str], g: tuple[str, list[str], str | None] | None) -> bool:
    return bool(g and g[0] in ("rm", "mv")) or words[0].lower() in FILE_OP_COMMANDS


def file_op_dir(words: list[str], g: tuple[str, list[str], str | None] | None, cwd: Path) -> str | None:
    """rm・mv などの対象が Git の作業ツリーにあれば、その親フォルダ。すべて作業ツリーの外なら None。"""
    base = segment_dir(cwd, g[2] if g else None)
    targets = g[1] if g else words[1:]
    paths = [Path(base, expand_path(t)) for t in targets if not t.startswith("-")]
    for p in paths or [Path(base) / "."]:
        d = str(nearest_dir(p))
        if is_work_tree(d):
            return d
    return None


def repo_root(d: str) -> str | None:
    return ok(d, "rev-parse", "--show-toplevel")


def created_branch_repo(words: list[str], cwd: Path) -> str | None:
    """`git switch -c` などでブランチを切るコマンドなら、切ったリポジトリのルート。"""
    g = parse_git(words)
    if g and g[0] in ("switch", "checkout") and NEW_BRANCH_FLAGS & set(g[1]):
        return repo_root(segment_dir(cwd, g[2]))
    return None


def after_cd(words: list[str], cwd: Path) -> Path:
    """`cd <フォルダ>` の後の作業フォルダ。オプションは読み飛ばす。行き先が分からないときは変えない。"""
    targets = [w for w in words[1:] if not w.startswith("-")]
    if words[0] != "cd" or not targets:
        return cwd
    dest = Path(cwd, expand_path(targets[0]))
    return dest if dest.is_dir() else cwd


def refuse(sid: str | None, default: str, what: str) -> str:
    header = f"{what}は拒否します（GitHub Flow は、作業ブランチを PR 経由でマージします）。"
    return branch_question(sid, default, header)


def check_segment(words: list[str], cwd: Path, sid: str | None, state: dict, new_branch: bool = False) -> str | None:
    """Bash の1コマンドを検査し、拒否するときの理由を返す。new_branch は、同じ行の前の部分でブランチを切ったか。"""
    g = parse_git(words)
    gh_merge = is_gh_pr_merge(words)
    if is_file_op(words, g):
        d = file_op_dir(words, g, cwd)
        return edit_gate(d, sid, state, new_branch) if d else None
    d = segment_dir(cwd, g[2] if g else None)
    if not (g or gh_merge) or not is_work_tree(d):
        return None
    if gh_merge:
        return merge_gate(d)
    sub, args, _ = g
    branch, default = (None if new_branch else current_branch(d)), default_branch(d)
    ready = bool(default) and has_commits(d) and not state.get("allow_main")
    if sub == "tag":
        return tag_reason(args)
    if sub == "push":
        force, to_default = analyze_push(args, branch, default or "")
        if force:
            return "force push は拒否します。必要なときは、ユーザーが `!` を付けて自分の端末で実行してください。"
        return refuse(sid, default, f"{default} への push") if to_default and ready else None
    if sub == "merge" and "--ff-only" in args and {f"origin/{default}", "@{u}", "@{upstream}"} & set(args):
        return None  # ローカルの既定ブランチを、リモートに追従させる操作
    if sub == "commit" or (sub == "merge" and not {"--abort", "--continue", "--quit"} & set(args)):
        return refuse(sid, default, f"{default} 上の git {sub}") if ready and branch == default else None
    return None


def merge_gate(d: str) -> str | None:
    """GitHub のリモートでは、gh pr merge を常に拒否する。マージはユーザーが行う。"""
    if not is_github(d) or not default_branch(d):
        return None
    return ("gh pr merge は拒否します。マージはユーザーが行います（PR の画面、または `! gh pr merge <番号> --squash`）。"
            "PR の URL をユーザーに伝えて、止まってください。")


def pre_tool(data: dict) -> None:
    tool, ti = data.get("tool_name"), data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or Path.cwd())
    sid = data.get("session_id")
    state = load_state(sid)
    if tool in FILE_TOOLS:
        raw = ti.get("file_path") or ti.get("notebook_path")
        d = str(nearest_dir(Path(raw) if Path(raw).is_absolute() else cwd / raw)) if raw else None
        reason = edit_gate(d, sid, state) if d and is_work_tree(d) else None
    elif tool == "Bash":
        command = ti.get("command") or ""
        follow_cd = not has_grouping(command)
        # サブシェルや || の中の cd は、後ろに効くとは限らない。その行では、cd の前後のフォルダを両方検査する
        cwds, reason, created = [cwd], None, set()
        for words in filter(None, map(strip_env, split_commands(command))):
            for c in cwds:
                g = parse_git(words)
                here = repo_root(segment_dir(c, g[2] if g else None))
                reason = check_segment(words, c, sid, state, here in created)
                if reason:
                    break
            if reason:
                break
            if follow_cd:
                created.update(filter(None, (created_branch_repo(words, c) for c in cwds)))
            moved = [after_cd(words, c) for c in cwds]
            cwds = moved if follow_cd else list(dict.fromkeys([*cwds, *moved]))
    else:
        reason = None
    if reason:
        deny(reason)


def post_tool(data: dict) -> None:
    tool, ti = data.get("tool_name"), data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or Path.cwd())
    sid = data.get("session_id")
    state = load_state(sid)
    edited = False
    if tool in FILE_TOOLS:
        raw = ti.get("file_path") or ti.get("notebook_path")
        if raw:
            path = Path(raw) if Path(raw).is_absolute() else cwd / raw
            edited = is_work_tree(nearest_dir(path))
    elif tool == "Bash":
        for words in split_commands(ti.get("command") or ""):
            words = strip_env(words)
            if not words:
                continue
            g = parse_git(words)
            if is_file_op(words, g):
                edited = edited or file_op_dir(words, g, cwd) is not None
    if edited and not state.get("edited"):
        state = load_state(sid)
        state["edited"] = True
        save_state(sid, state)


def session_start(data: dict) -> None:
    d = str(data.get("cwd") or Path.cwd())
    if not is_work_tree(d):
        return
    prune_old_states()
    parts = [f"ブランチ: {current_branch(d) or '(detached)'}", f"未コミット: {len(status_lines(d))}件"]
    if ok(d, "remote"):
        fetched = fetch(d)
        ab, note = ahead_behind(d), ""
        default = default_branch(d)
        if ab is None and default:
            ab, note = ahead_behind(d, f"origin/{default}"), f"（上流なし。origin/{default} と比較）"
        text = f"ahead {ab[0]}・behind {ab[1]}{note}" if ab else "上流ブランチなし"
        if not fetched:
            text += "（取得できず。前回取得時点の差）"
        parts.append("リモート差: " + text)
    lines = [" / ".join(parts)]
    default = default_branch(d)
    if is_github(d) and default:
        ref = release_ref(d, default)
        latest = latest_tag(d, ref)
        count = ok(d, "rev-list", "--count", f"{latest}..{ref}") if latest else None
        version = next_version(latest, commit_messages(d, ref, latest))
        if count and int(count) > 0 and version != "skip":
            lines.append(f"最新タグ {latest} より {count} コミット新しい。リリース未作成（提案する版: {version}）")
    msg = "\n".join(lines)
    print(json.dumps({"systemMessage": msg, "hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": msg}}))


def pending_stage(d: str, allow_main: bool) -> tuple[str, list[str]] | None:
    """促す段階（commit・push・pr）と、理由に載せる行。促すものがなければ None。"""
    lines = status_lines(d)
    if lines:
        return "commit", lines
    branch, default = current_branch(d), default_branch(d)
    if not (is_github(d) and branch and default):
        return None
    ab = ahead_behind(d)
    if (ab is None and branch != default and has_commits(d)) or (
            ab and ab[0] > 0 and (branch != default or allow_main)):
        return "push", []
    gh = shutil.which("gh")
    if ab is not None and branch != default and gh:
        r = run([gh, "pr", "list", "--head", branch, "--state", "all", "--json", "number"], d)
        try:
            if r and r[0] == 0 and json.loads(r[1]) == []:
                return "pr", []
        except ValueError:
            return None
    return None


STAGE_TEXT = {
    "commit": "未コミットの変更が {n} 件あります。\n{files}\nユーザーにコミットするかを確認してください"
              "（形式は Conventional Commits。件名の type は英語、説明は日本語）。",
    "push": "コミット済みで、まだ push していない変更があります。ユーザーに push するかを確認してください。",
    "pr": "push 済みのブランチに、PR がありません。ユーザーに PR を作るかを確認してください"
          "（タイトルは Conventional Commits の形式）。",
}


def stop(data: dict) -> None:
    if data.get("stop_hook_active"):
        return
    sid = data.get("session_id")
    state = load_state(sid)
    d = str(data.get("cwd") or Path.cwd())
    if not state.get("edited") or not is_work_tree(d):
        return
    stage = pending_stage(d, bool(state.get("allow_main")))
    if stage is None:
        return
    name, lines = stage
    digest = hashlib.sha256("|".join([name, ok(d, "rev-parse", "HEAD") or "", *lines]).encode("utf-8")).hexdigest()
    if state.get("last_stop") == digest:
        return
    state["last_stop"] = digest
    save_state(sid, state)
    shown = "\n".join("  " + ln for ln in lines[:MAX_LINES])
    if len(lines) > MAX_LINES:
        shown += f"\n  ほか {len(lines) - MAX_LINES} 件"
    reason = STAGE_TEXT[name].format(n=len(lines), files=shown)
    print(json.dumps({"decision": "block", "reason": reason}))


# --- Claude が実行するコマンドと入口 ----------------------------------------


def cli(sub: str, args: list[str]) -> int:
    if sub == "allow-main" and len(args) == 1:
        state = load_state(args[0])
        state["allow_main"] = True
        save_state(args[0], state)
        print("OK: このセッションでは、ブランチ確認と既定ブランチへの commit・push の拒否を外しました。")
        return 0
    print(f"使い方: git_flow.py {sub} <session_id>", file=sys.stderr)
    return 2


HOOKS = {"session-start": session_start, "pre-tool": pre_tool, "post-tool": post_tool, "stop": stop}


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sub = argv[1] if len(argv) > 1 else ""
    if sub == "allow-main":
        return cli(sub, argv[2:])
    handler = HOOKS.get(sub)
    if handler is None:
        return 0
    try:
        handler(json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}"))
    except Exception as exc:  # noqa: BLE001 - Hook の失敗で作業を止めない
        print(f"git_flow.py {sub}: {exc!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
