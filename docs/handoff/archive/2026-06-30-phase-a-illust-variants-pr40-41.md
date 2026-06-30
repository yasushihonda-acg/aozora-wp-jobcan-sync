# Handoff — 2026-06-30 (Phase A 求人カードイラスト多様化セッション: PR #40 + #41)

## TL;DR

本セッションで **求人カード一覧の単調さ (同カテゴリ 10 件 = 同じ絵) を解消**。aozora-illust スキル経由で複数人物 wide composition のイラストを 5 枚新規生成、一覧で cycling、詳細ページとも src を同期。**aozora-illust スキルの技法ブレイクスルー** (`ref-mode=both` + outfit override + multi-person シーン記述) を確立、Phase A 中の追加生成で踏襲予定。

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run (Phase 2B-exec): https://aozora-sync-flry56mxwa-an.a.run.app (稼働中、本セッション変更なし)

## 今セッションで完了したこと

### マージ済 PR (2 件)

| PR | タイトル | 内容 |
|---|---|---|
| #40 | `求人カードイラスト 5 枚追加 + 同カテゴリ内 cycling` | `illust-job-care-2/care-3/consultant/consultant-2/office-2.png` を新規追加、`rewrite_jobs_html.py` に `LABEL_TO_CATEGORY` + `CATEGORY_VARIANTS` + `category_counters` を追加し同カテゴリ内 cycling 実装。介護職 4-3-3 / 相談員 5-5 / 事務職 5-5 / IT 4 で thumbnail を分散、`illust-job-nurse.png` 参照を 0 件に |
| #41 | `求人一覧 → 詳細でサムネ画像を同期` | `rewrite_job_details.py` に `build_thumbnail_mapping()` を追加し jobs.html を真理ソースに job_id → src 対応表を構築、詳細ページの hero__media img を一覧と同期。34/34 件で cross-check 一致 |

### 技法ブレイクスルー (aozora-illust スキル運用知見)

**gpt-image-2 edits API の制約と突破法を実証**:

| ref-mode | outfit override | 生成結果 |
|---|---|---|
| `face-only` | あり/なし | **常に正面ポートレートに収束** (close-up reference の構図支配が強すぎる、v1/v2/v4 全試行で確認) |
| `both` | あり | **多人物 wide composition + 服装維持が可能** (v5 で確立、PR #40 で採用) |

**Phase A 中の追加生成では `ref-mode=both` + 黒ポロ強制 outfit override + 明示的 multi-person シーン記述 を踏襲する**。

### サムネ確認のサンプル (本番)

- 介護職: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/jobs/2264134.html (care-2 デイサービス recreation 5人)
- 相談員: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/jobs/90447.html (consultant-2 ケアマネ + 同僚)
- 事務職: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/jobs/2267327.html (office-2 whiteboard + 同僚)

## 重要な設計判断 (本セッション)

### 服装は変えない、ポーズ・角度・人数構図のみで多様化

- 本田様判断 (中盤): v3 で beige cardigan を試したが NG、「変えてよいのは角度やポーズが主」
- v4 で BACK VIEW / CROUCHING / SIDE PROFILE / OVERHEAD / LOW ANGLE をディレクティブ強化したが、`face-only` ref-mode が portrait に lock する制約で全部正面に収束
- v5 で `ref-mode=both` + outfit override (黒ポロ強制) + multi-person シーンに切替 → 服装維持 + 構図多様化を両立

### 一覧 cycling は thumbnail src 書き換えで実装、jobs.html を真理ソースに

- `rewrite_jobs_html.py` 内で同カテゴリカードに variant を順に割当 (`category_counters`)
- `rewrite_job_details.py` は jobs.html を parse して job_id → src の mapping を構築し、詳細ページの hero img を同期
- jobs.html → 詳細ページの単方向同期 (rewrite_jobs_html.py を先に実行する前提を `FileNotFoundError` で強制)

### `illust-job-nurse.png` は物理保持 (使用停止のみ)

- 本田様判断 (中盤): 「将来看護職カテゴリが出てきたら再利用可」として物理削除せず、jobs.html / 詳細ページの参照のみ 0 件に
- mockup/assets/img/illust-job-nurse.png は git 管理下で保持

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし**。本セッションで本田様指示の「絵のバリエーション増やしたい」「一覧と詳細のサムネを揃えたい」両方を完遂。次の着手は本田様の優先指示が trigger。

### 条件待ち (明示 trigger 付き、4 件 — 前 handoff から継承)

| # | 項目 | カテゴリ | trigger | 充足時のタスク |
|---|------|---------|---------|--------------|
| 1 | **Phase A 決裁者承認の取得** | 新規価値創出 | 本田様 → 関係者へ公開モック URL + Loom ウォークスルー (5 分) を共有、承認/リビジョン回答到来 | リビジョン依頼内容に応じて機械生成スクリプト再実行で再整形 |
| 2 | **`/healthz` rename + redeploy** | 守り (修正) | 本田様 → 「/healthz 直して」明示指示 | `sync/src/sync/app.py` の `@app.get("/healthz")` を `/health` に変更 → pytest → buildx push → gcloud run deploy → curl 確認 (15-20 分) |
| 3 | **WP 統合 (Cloud Run server-to-server fetch 組込)** | 新規価値創出 | 本田様 → 「WP に Cloud Run の URL 組込開始」明示指示 + WP 環境のアクセス情報 | WP 側で `https://aozora-sync-flry56mxwa-an.a.run.app/jobs/{id}` を fetch する PHP/プラグインを実装、採用ページに埋込 |
| 4 | **Billing budget alert $5 設定** | 整理・点検 | 本田様 → 「設定したい」明示指示 (Console UI 操作なので本田様直接実施推奨) | GCP Console で budgets `$5` alert 作成 (5 分) |

### 却下候補 (記録のみ)

| # | 項目 | 着手しない理由 |
|---|------|--------------|
| 1 | mockup の追加 UI 機能 (検索フィルター高度化、お気に入り保存等) | Phase A 範囲外、Phase B 以降の WP プラグインで実装する想定。AI 起点の新規価値創出案発想は 4 原則 §1 違反 |
| 2 | `scripts/mockup-rebuild/` の Phase B template 移植 | Phase B 着手時の作業、現時点 trigger なし |
| 3 | 詳細ページの aside (関連求人) 表示ロジック改修 | 現状で機能、Phase B 着手時の作業 |
| 4 | aozora-illust スキル本体に v5 技法 (`ref-mode=both` + outfit override + multi-person) のドキュメント追記 | 整理・点検カテゴリ、本田様明示指示なき限り提案にとどめる。本 handoff に技法を記録済みなので参照は可能 |
| 5 | 追加カテゴリのイラスト生成 (看護職 / 訪問介護 / リハビリ等) | 現時点で該当カテゴリの求人なし、ジョブカン側に該当カテゴリが追加されたら trigger 化 |

## Issue Net 変化

- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件

(本セッションは本田様指示に逐次対応した 2 PR の連続、Issue 化対象なし)

## 環境状態

| 項目 | 状態 |
|---|---|
| Git | clean、main 同期 (PR #40 + #41 merge 済) |
| 最新 commit | `90f582c` (#41 一覧→詳細サムネ同期) |
| Cloud Run service | `aozora-sync` 稼働中 (revision `00002-724` traffic 100%、本セッション変更なし) |
| GitHub Pages | `pages-build-deployment` success (commit `90f582c`、2026-06-30T07:06:10Z 完了) |
| 残留プロセス | なし |
| OPEN PR | 0 件 |
| OPEN Issue | 0 件 |

## 構造的整合性チェック

| チェック対象 | 結果 |
|---|---|
| `/impact-analysis` (型・共有ロジック・設定) | ⏭️スキップ (PNG 5 枚追加 + Python ヘルパースクリプトの変更のみ、型・共有ロジック変更なし) |
| `/new-resource` (新規テーブル/API) | ⏭️スキップ (該当なし) |
| `/trace-dataflow` (データフロー実装) | ⏭️スキップ (mockup 静的ファイルの thumbnail 同期、データフローなし) |
| グローバル memory scope チェック | ⏭️スキップ (`memory/` 配下変更なし) |
| 同根再発スキャン | ✅ 該当なし (本セッション feat PR のみ、修正 PR ナシ) |
| 対症療法判定 | ⏭️スキップ (修正 PR ナシ) |
| 残留プロセス | ✅ なし |

## 最終結論

🛑 **executor 領分の作業ゼロ、即時終了推奨**

- OPEN PR / Issue 0 件、Git clean、Pages build success (`90f582c`)
- 即着手タスク = 0 件、条件待ち = 4 件 (全て本田様明示指示が trigger、現時点未充足)
- 残留プロセスなし
- 同根再発・対症療法判定: 該当なし (本セッション feat PR のみ)
- 次セッションは本田様の優先指示 (Phase A 決裁者承認進行 / /healthz / WP 統合 / budget alert の何れか) が trigger
