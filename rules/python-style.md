---
paths:
  - "**/*.py"
---

# Python の書き方の規則

Python のコードを書く、または変更するときに従う規則。PEP 8・PEP 257・PEP 484 などの型ヒント・ruff の既定に従う。ここには、標準が定めないプロジェクトの決定だけを書く。

- 次は、ここに重ねて書かない。
  - テスト: `~/.claude/rules/python-testing.md`
  - venv・終了コード・依存の固定: `~/.claude/rules/python-venv.md`
- 既存のコードには、新規と変更したファイルから適用する。一括で直さない。

## 1. 道具

### 1-1. ruff で lint と整形をそろえる（必須）

- **規則**: `ruff check` と `ruff format --check` が通ること。設定は `pyproject.toml` に 1 か所だけ置く。
- ルールを外す（`ignore`）ときは、理由をコメントに書く。
- **設定**: 次を既定とする。

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "B", "UP", "SIM", "S", "PT", "PTH", "BLE"]
extend-select = ["PLW1514"]  # open の encoding 省略（preview のルール）
preview = true
explicit-preview-rules = true  # コードを指定した preview のルールだけ有効にする

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "S108", "S603", "S607"]
```

- **理由**: 書き方の議論を道具に任せる。〔機械: `ruff check` と `ruff format --check`〕

### 1-2. 対象の Python の版を書く（必須）

- **規則**: `pyproject.toml` に `requires-python` を書く（PEP 621）。
- **理由**: ruff の `UP` が、`requires-python` から書き換え先の版を決める。〔機械: `requires-python` の存在〕

## 2. Windows での書き方

### 2-1. ファイルの文字コードを明示する（必須）

- **規則**: テキストの読み書きは `encoding="utf-8"` を明示する。
- **理由**: Windows の既定（cp932）に依存すると、日本語の読み書きが環境で変わる。〔機械: ruff の `PLW1514`〕

### 2-2. 改行は LF に固定する（必須）

- **規則**: リポジトリに `.gitattributes`（`* text=auto eol=lf`）を置く。
- **理由**: CRLF が混ざると、差分が全行になる。〔機械: `git diff --check`・`.gitattributes` の存在〕

## 3. チェックリスト

- [ ] 1-1 `ruff check` と `ruff format --check` が通る〔機械〕
- [ ] 1-2 `requires-python` を書いている〔機械〕
- [ ] 2-1 `encoding="utf-8"` を明示している〔機械〕
- [ ] 2-2 `.gitattributes` があり、`git diff --check` が通る〔機械〕

## 出典

- PEP 8: <https://peps.python.org/pep-0008/>
- PEP 257: <https://peps.python.org/pep-0257/>
- PEP 484: <https://peps.python.org/pep-0484/>
- PEP 621: <https://peps.python.org/pep-0621/>
- ruff の設定: <https://docs.astral.sh/ruff/settings/>
