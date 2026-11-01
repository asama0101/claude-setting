import json
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
GRAY = "\033[90m"

BAR_WIDTH = 5
SEP = "{} │ {}".format(GRAY, RESET)

BOLD = "\033[1m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD_MAGENTA = "\033[1;35m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_CYAN = "\033[96m"

# モデル名に含まれる系統名で色を分ける（小文字で判定。該当なしは MODEL_DEFAULT）
MODEL_COLORS = (
    ("opus", MAGENTA),
    ("sonnet", CYAN),
    ("haiku", BRIGHT_BLUE),
    ("fable", BRIGHT_CYAN),
)
MODEL_DEFAULT = CYAN
# effort は強さの段階で濃淡を付ける。該当なしは灰色
EFFORT_COLORS = {
    "low": GRAY,
    "medium": "",
    "high": CYAN,
    "xhigh": MAGENTA,
    "max": BOLD_MAGENTA,
}

ICON_MODEL = "🤖"
ICON_DIR = "📁"
ICON_BRANCH = "🌿"
ICON_DIRTY = "●"
ICON_PR = "🔀"
ICON_SESSION = "🏷"

# メーターごとの (絵文字, ラベル, ラベル色)。バーと数値は使用率の色、ラベルは灰色
CTX = ("💬", "ctx", GRAY)
FIVE = ("⏳", "5h", GRAY)
WEEK = ("📅", "7d", GRAY)


def paint(color, text):
    return "{}{}{}".format(color, text, RESET)


def model_color(name):
    lower = str(name).lower()
    for key, color in MODEL_COLORS:
        if key in lower:
            return color
    return MODEL_DEFAULT


def level_color(pct):
    if pct >= 80:
        return RED
    if pct >= 60:
        return YELLOW
    return GREEN


def bar(pct):
    filled = max(0, min(BAR_WIDTH, round(pct / 100 * BAR_WIDTH)))
    return "▓" * filled + "░" * (BAR_WIDTH - filled)


def meter(spec, pct, resets_at=None):
    # 取れない値は項目ごと省略する（ctx のみ呼び出し側で "--" を渡す）
    if not isinstance(pct, (int, float)):
        return None
    icon, label, label_color = spec
    color = level_color(pct)
    out = "{} {} {}".format(icon, paint(label_color, label), paint(color, "{:.0f}% {}".format(pct, bar(pct))))
    left = remaining(resets_at)
    if left:
        out += " " + paint(GRAY, left)
    return out


def remaining(resets_at):
    if not isinstance(resets_at, (int, float)):
        return ""
    sec = int(resets_at - time.time())
    if sec <= 0:
        return "0m"
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "{}d{}h".format(d, h)
    if h:
        return "{}h{}m".format(h, m)
    return "{}m".format(m)


def git_branch(cwd):
    if not cwd:
        return None
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v1", "--branch"],
            capture_output=True, text=True, encoding="utf-8", timeout=3,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    lines = r.stdout.splitlines()
    if not lines or not lines[0].startswith("## "):
        return None
    name = lines[0][3:].split("...")[0]
    if name.startswith("No commits yet on "):
        name = name[len("No commits yet on "):]
    dirty = len(lines) > 1
    return name, dirty


def sub(obj, key):
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, dict) else {}


try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}

model = sub(data, "model").get("display_name") or "?"
effort = sub(data, "effort").get("level")
cwd = sub(data, "workspace").get("current_dir") or data.get("cwd") or ""
cwd = str(cwd).replace("\\", "/")

# 1行目: モデル / effort、ディレクトリ、ブランチ、PR
head = ICON_MODEL + " " + paint(BOLD + model_color(model), model)
if effort:
    head += paint(GRAY, " / ") + paint(EFFORT_COLORS.get(str(effort).lower(), GRAY), effort)
line1 = [head]

if cwd:
    line1.append("{} {}".format(ICON_DIR, paint(GRAY, cwd)))

branch = git_branch(cwd)
if branch:
    name, dirty = branch
    git = ICON_BRANCH + " " + paint(CYAN, name)
    if dirty:
        git += " " + paint(YELLOW, ICON_DIRTY)
    line1.append(git)

pr = sub(data, "pr")
if pr.get("number"):
    label = "MR" if pr.get("kind") == "mr" else "PR"
    state = pr.get("review_state")
    text = ICON_PR + " " + paint(CYAN, "{} #{}".format(label, pr["number"]))
    if state:
        state_color = {"approved": GREEN, "changes_requested": RED}.get(state, YELLOW)
        text += " " + paint(state_color, state)
    line1.append(text)

# 2行目: ctx、5h、7d、セッション名
limits = sub(data, "rate_limits")
five = sub(limits, "five_hour")
week = sub(limits, "seven_day")
ctx = sub(data, "context_window").get("used_percentage")

line2 = [meter(CTX, ctx) or "{} {} {}".format(CTX[0], paint(CTX[2], CTX[1]), paint(GRAY, "--"))]
for spec, window in ((FIVE, five), (WEEK, week)):
    item = meter(spec, window.get("used_percentage"), window.get("resets_at"))
    if item:
        line2.append(item)

session_name = data.get("session_name")
if session_name:
    line2.append(ICON_SESSION + " " + paint(GRAY, session_name))

for line in (line1, line2):
    if line:
        print(SEP.join(line))
