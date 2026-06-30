# Handoff — 2026-06-30 (Phase A モック整形 5 PR + 機械生成パイプライン構築)

## TL;DR

本セッションで **Phase A モック (jobs.html + 詳細 34 件) を ジョブカン正本データで全面整形**。一覧/詳細とも給与・勤務時間・年間休日・福利厚生・応募資格・選考フローを表示、ハッシュタグ羅列+本文ベタ流しを解消。詳細ページに「← 求人一覧へ戻る」ナビ追加。sync の parser を経由した機械生成スクリプト (`scripts/mockup-rebuild/`) を構築、Phase A 中の追加対応 / Jobcan 更新反映に再利用可能。

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run (Phase 2B-exec): https://aozora-sync-flry56mxwa-an.a.run.app (前セッションで稼働開始)

## 今セッションで完了したこと

### マージ済 PR (5 件)

| PR | タイトル | 内容 |
|---|---|---|
| #34 | `aozora-illust --ref-mode=face-only + illust-job v4` | スキルに `--ref-mode=both\|face-only` 追加、close-up reference のみ渡すモード追加。illust-job 4 枚 v4 (office/it シーン差別化成功、care/nurse は単独 portrait + カード見出しテキストで職種識別) |
| #35 | `求人カード/詳細ページの情報設計刷新 (3 件試作)` | 詳細 3 件 (2199420 介護OPEN / 1777023 介護博多 / 452341 IT) を hero (タグ+リード+ハッシュタグ chip) + summary 8 項目 + 仕事内容 + 応募資格 + 待遇・福利厚生 + 選考フロー で再構成。CSS コンポーネント (`.job-hashtags` / `.is-accent` / `.job-benefits` / `.job-qualification__row` / `.selection-flow__step` / `.job-card__meta-grid`) を `components.css` に追加 |
| #36 | `jobs.html 一覧 34 件カードを正本データで統一` | sync の `JobcanClient + parser` で 34 件 fetch (0 errors) → ヘルパー (`scripts/mockup-rebuild/fetch_all.py` + `rewrite_jobs_html.py`) で機械整形 (給与/年休 chip、市区名 ／ 施設名、ハッシュタグ除去リード文) |
| #37 | `job-detail 34 件を機械生成パイプラインで統一` | `scripts/mockup-rebuild/rewrite_job_details.py` 新規作成、34 件詳細を統一パターンで再生成 (試作 3 件も上書き)。aside/footer/header/breadcrumb/entry-cta は維持 |
| #38 | `詳細ページに「← 求人一覧へ戻る」ボタンを 34 件全件追加` | hero 直上にターコイズ pill ボタン追加 (CSS `.job-detail__back-link`)、breadcrumb は維持。スクリプト改修 + 34 件再生成で冪等対応 |

### 確立した機械生成パイプライン

```
scripts/mockup-rebuild/
├── README.md                  # 使い方
├── job_ids.txt                # 対象 34 件 ID
├── fetch_all.py               # JobcanClient + parser で正本 fetch → jobs_data.json
├── rewrite_jobs_html.py       # 一覧 jobs.html カード再生成
└── rewrite_job_details.py     # 詳細 34 件再生成 (hero/summary/sections + back-nav)
```

- Phase B (Cloud Run + sync の `job_list.html` / `job_detail.html` template) 稼働後は本ヘルパーは不要
- Phase A 中の追加ジョブ / Jobcan 側更新 / 文言調整時に再実行可能 (冪等)

### 創作有無の判定 (本田様 2 度の確認質問への対応)

- **全数値・福利厚生・休暇制度・必須/歓迎資格・選考フロー**: ジョブカン正本一致 (sync の parser.py 経由)
- **リード文 / 仕事内容の箇条書き分解**: `body_html` の機械整形のみ (ハッシュタグ羅列除去 / 〇/□/●/★ マーカー → `<li>` 変換 / 句点切り)
- **"必須"/"歓迎"/"休暇制度" 等のラベル**: 構造ラベル (機械生成側で付与)
- **address の「市区名 ／ 施設名」形式**: 機械抽出 (extras.募集拠点 から正規表現) + 連結のみ

## 重要な設計判断 (本セッション)

### アプローチ A (段階的: 3 件試作 → 34 件統一) → さらに展開して全件

- 当初 PR #35 で「試作 3 件のみ改修、残り 31 件は Phase B」と決定
- 本田様指摘 (Image #4): 一覧の「給与 chip ありなしバラつき」が気になる → PR #36 で 34 件統一
- 本田様指摘 (Image #5/#6): 詳細ページの 31 件もハッシュタグ羅列のまま → PR #37 で 34 件統一
- 本田様指摘 (Image #7): 「求人一覧に戻る」 → PR #38 で navigation 補強
- **結論**: 二重投資懸念より「Phase A 決裁者承認向けに今すぐ完成度を出す」を優先、機械生成パイプライン化により Phase B 移行時も負担最小

### care/nurse 詳細シーン差別化を断念 → カード見出しテキストで識別

- PR #34 で `--ref-mode=face-only` を導入したが、close-up reference のスタイル支配が強く、prompt で「お茶/車椅子/聴診器/医療カート」を盛っても 2 回試行とも単独 portrait に収束
- 本田様判断 (AskUserQuestion): office/it だけ採用、care/nurse は単独 portrait + カード見出しテキスト識別

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし**。本セッションで本田様指摘事項 4 件を全て解消。次の着手は本田様の優先指示が trigger。

### 条件待ち (明示 trigger 付き、4 件)

| # | 項目 | カテゴリ | trigger | 充足時のタスク |
|---|------|---------|---------|--------------|
| 1 | **Phase A 決裁者承認の取得** | 新規価値創出 | 本田様 → 関係者へ公開モック URL + Loom ウォークスルー (5 分) を共有、承認/リビジョン回答到来 | リビジョン依頼があれば指示内容に応じて再整形 (機械生成スクリプト再実行で素早く対応可能) |
| 2 | **`/healthz` rename + redeploy** | 守り (修正) | 本田様 → 「/healthz 直して」明示指示 | `sync/src/sync/app.py` の `@app.get("/healthz")` を `/health` に変更 → pytest 確認 → buildx push → gcloud run deploy → curl 確認 (15-20 分、前 handoff から継続) |
| 3 | **WP 統合 (Cloud Run server-to-server fetch 組込)** | 新規価値創出 | 本田様 → 「WP に Cloud Run の URL 組込開始」明示指示 + WP 環境のアクセス情報 | WP 側で `https://aozora-sync-flry56mxwa-an.a.run.app/jobs/{id}` を fetch する PHP/プラグインを実装、採用ページに埋込、応募ボタン動作確認 |
| 4 | **Billing budget alert $5 設定** | 整理・点検 | 本田様 → 「設定したい」明示指示 (Console UI 操作なので本田様直接実施推奨) | https://console.cloud.google.com/billing/01F6B4-48EE02-E5EFB8/budgets を開いて $5 alert 作成 (5 分) |

### 却下候補 (記録のみ)

| # | 項目 | 着手しない理由 |
|---|------|--------------|
| 1 | mockup の追加 UI 機能 (検索フィルター高度化、お気に入り保存等) | Phase A 範囲外、Phase B 以降の WP プラグインで実装する想定。AI 起点の新規価値創出案発想は 4 原則 §1 違反 |
| 2 | `scripts/mockup-rebuild/` の Phase B template 移植 (parser に「ハッシュタグ抽出 / 本文構造化」拡張) | Phase B 着手時の作業、現時点 trigger なし |
| 3 | 詳細ページの aside (関連求人) 表示ロジック改修 (現状手書きで関連 3 件固定) | 現状で機能、Phase B 着手時の作業 |

## Issue Net 変化

- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件

(本セッションは本田様指摘事項に逐次対応した 5 PR の連続、Issue 化対象なし)

## 環境状態

| 項目 | 状態 |
|---|---|
| Git | clean、main 同期 (本 PR merge 後) |
| 最新 commit | `e494102` (#38 back-link 追加) |
| Cloud Run service | `aozora-sync` 稼働中 (前セッション #28 で deploy 済、revision `00002-724` traffic 100%) |
| GitHub Pages | `pages-build-deployment` success (本セッション中も逐次反映) |
| 残留プロセス | なし |
| OPEN PR | 0 件 (handoff PR を除く) |
| OPEN Issue | 0 件 |

## 構造的整合性チェック

| チェック対象 | 結果 |
|---|---|
| `/impact-analysis` (型・共有ロジック・設定) | ⏭️スキップ (HTML/CSS/Python ヘルパースクリプトの変更のみ、型・共有ロジック変更なし) |
| `/new-resource` (新規テーブル/API) | ⏭️スキップ (該当なし) |
| `/trace-dataflow` (データフロー実装) | ⏭️スキップ (mockup 静的ファイル整形、データフローなし) |
| グローバル memory scope チェック | ⏭️スキップ (`memory/` 配下変更なし) |
| 同根再発スキャン | ✅ 該当なし (本セッション feat: PR のみ、修正 PR 無し) |
| 対症療法判定 | ⏭️スキップ (修正 PR 無し) |
| 残留プロセス | ✅ なし |

## 最終結論

✅ **セッション終了可** — 本田様指摘事項 4 件 (Image #4 一覧バラつき / Image #5,#6 詳細ハッシュタグ羅列 / Image #7 戻る機能) 全て解消、PR #34-#38 マージ済、Git clean、OPEN Issue 0 件、即着手タスク 0 件、残留プロセスなし。次セッションは条件待ち 4 件の trigger 充足時 (本田様の明示指示) に着手。
