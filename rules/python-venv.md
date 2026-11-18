---
paths:
  - "**/*.py"
---

# Python の venv の規則

開発用の venv を作る・使うときに従う規則。

- 必須を外すときは、利用者に理由を示して了承を得る。
- 確認方法を〔機械〕（コマンド）か〔目視〕（レビュー）で示す。

## 開発用の venv

### リポジトリ直下の `.venv/` に作る（必須）

- `python -m venv .venv` で作り、`.gitignore` に `.venv/` を入れる。〔機械: `git check-ignore .venv`〕
