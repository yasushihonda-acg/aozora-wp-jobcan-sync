# mockup-rebuild — 求人カード一括再生成スクリプト

mockup の `jobs.html` 一覧カード (34 件) を、ジョブカン正本データから給与・年休 chip 付きで再生成するためのヘルパー。Phase A 中の追加ジョブ描加 / Jobcan 側の更新反映時にも再利用可。

Phase B (Cloud Run + sync の job_list.html template) が稼働すれば本ヘルパーは不要になる。

## 前提

- `sync/.venv/` が用意済 (uv sync 実行済)
- `scripts/mockup-rebuild/job_ids.txt` に対象 job_id を 1 行 1 件で列挙

## 使い方

```bash
# 1) ジョブカン正本を fetch → jobs_data.json
./sync/.venv/bin/python scripts/mockup-rebuild/fetch_all.py

# 2) jobs.html の 34 件カードを一括書き換え (冪等)
./sync/.venv/bin/python scripts/mockup-rebuild/rewrite_jobs_html.py
```

## 出力物

| ファイル | 説明 |
|---|---|
| `scripts/mockup-rebuild/jobs_data.json` | parser 出力の正本 JSON (ローカル作業用、`.gitignore` 推奨) |
| `mockup/jobs.html` | カード 34 件が新デザイン (給与/年休 chip + 整形 description) に統一 |

## 整形ロジック

- **address** → 都道府県カット、「市区名 ／ 施設名」(例: `鹿児島市 ／ あおぞらケアグループ永吉（デイ・有料）`)
- **description** → `body_html` → ハッシュタグ羅列除去 → 130 字で句点切り
- **月給 chip** → 「【月額】265,000円〜内訳:...」→「26.5 万円〜」 / レンジ→「34.6〜85.6 万円」 / 「【時給】1,500円〜※...」→「時給 1,500 円〜」
- **年休 chip** → フルタイム→「110 / 157 / 105 日」 / パート→「週 1〜5 日」 / フォールバック→「週休 N 日制」

全数値はジョブカン正本一致。リード文は body_html を機械整形 (ハッシュタグ除去 + 句点切り) のみで創作なし。
