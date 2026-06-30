# Handoff — 2026-06-19 朝 (Phase 2B-exec 実 GCP デプロイ完了セッション)

## TL;DR

本セッションで **Phase 2B-exec (実 GCP リソース作成 + Cloud Run deploy + 動作確認) を完遂**。Service URL `https://aozora-sync-flry56mxwa-an.a.run.app` が稼働中、`/jobs/{id}` と `/jobs/?category_id=...` は HTTP 200 + 自社 BEM デザインで応答。実 deploy で検出した 4 件の修正点を `infra/README.md` に反映 + 1 件の known issue (`/healthz` GFE 404) を記録。次セッションは **(a) `/healthz` rename** または **(b) WP 統合 (server-to-server fetch ターゲット組込)** から本田様の指示で着手可能。

🔗 決裁者向け公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run service: https://aozora-sync-flry56mxwa-an.a.run.app

## 今セッションで完了したこと

### Phase 2B-exec 実行結果 (6 step)

| Step | 結果 | 検出された修正点 |
|---|---|---|
| 1. API 有効化 | ✅ 成功 | (なし) |
| 2. AR repo + cleanup policy | ✅ 成功 | (なし) |
| 3. docker build/push | ✅ (2 修正) | (a) docker push に `CLOUDSDK_ACTIVE_CONFIG_NAME` prefix なしで permission denied (bash subshell で direnv 不発火) (b) Apple Silicon の `docker build` は arm64 image を生成、Cloud Run が拒否 → buildx + `--platform linux/amd64 --push` で解決 |
| 4. Cloud Run deploy | ✅ (1 修正) | `cpu=0.5` + `concurrency=10` は Cloud Run 仕様で不可 (cpu<1 は concurrency=1 必須) → `cpu=1` で解決 |
| 5. 動作確認 | ⚠️ partial | `/jobs/1777023` HTTP 200 (6755 bytes, sync-job-detail BEM 確認), `/jobs/?category_id=18773` HTTP 200 (21482 bytes, sync-job-list 確認), `/healthz` HTTP 404 (GFE intercepted、known issue) |
| 6. Billing alert | ⏭ 手動 | billing account `01F6B4-48EE02-E5EFB8` に紐付け済、$5 alert 設定は本田様の Console 手動操作 |

### Cloud Run 稼働状態

- Service URL (新形式、推奨): `https://aozora-sync-flry56mxwa-an.a.run.app`
- Service URL (project number 形式): `https://aozora-sync-1084369586348.asia-northeast1.run.app`
- 両 URL とも同じ Cloud Run service にルーティングされ HTTP 200 を返す
- Revision: `aozora-sync-00002-724` (traffic 100%、`cpu=1` / `concurrency=10` / `memory=512Mi` / `JOBCAN_FETCH_ENABLED=true`)
- 想定月額: **約 $0.01** (Cloud Run 無料枠内 + AR cleanup policy keep-latest-2)

### infra/README.md 修正 (5 点を本 PR に集約)

1. Step 3 全コマンドに `CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync` prefix を明示
2. Step 3b: `docker build` → `docker buildx build --platform linux/amd64 --push` (cross-build + push 一括)
3. Step 4: `cpu=0.5` → `cpu=1` (Cloud Run 仕様準拠)
4. Step 5: `/healthz` 期待値 と 実測値 (404) を併記、§7 known issues に詳細
5. Step 6: billing account ID `01F6B4-48EE02-E5EFB8` を明示

## 重要な設計判断 (本セッション)

### `/healthz` 404 は WP 統合に影響なし → 後日対応

- 採用サイト本番運用で呼ばれる URL は `/jobs/{id}` と `/jobs/?category_id=...` の 2 系統のみ
- `/healthz` はデバッグ・監視用 (本田様向け)、欠落しても core 機能影響ゼロ
- 原因 (GFE / Cloud Run 予約 path の可能性) の真因究明より、`/healthz` → `/health` 等への rename + redeploy で実用解決の方が ROI 高い
- Phase 2B-exec の主目的 (Jobcan proxy が稼働して自社 BEM HTML を返す) は達成済

## 簡素化後のロードマップ

```
[完了] Phase 2A.1 + 2A.2 + 2A.3 (アプリ層完成、cleanup 済)
   ↓
[完了] Phase 2B リポジトリ側 (infra/README.md + cleanup-policy.json)
   ↓
[完了] Phase 2B-exec (実 GCP デプロイ、本セッション)
   ↓
[Phase 2B 追補 / Phase 3 WP 統合] (本田様の指示で着手):
  (a) /healthz rename + redeploy (10 分): app.py の path 変更 → buildx push → gcloud run deploy → curl 確認
  (b) WP 統合 (採用ページから server-to-server fetch): WP 側 PHP (or WP プラグイン) で
      https://aozora-sync-flry56mxwa-an.a.run.app/jobs/{id} を fetch → 自社採用ページに埋込
      応募ボタンは https://recruit.jobcan.jp/aozora/entry/new/{id} へ直リンク (温存)
  (c) Billing budget alert $5 を Cloud Console UI で設定
   ─── Phase 4 (公式照会回答後、本番ドメイン切替): recruit.aozora-cg.com マッピング ───
```

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし**。下記いずれも条件待ち (本田様の優先順位指示が trigger)。

### 条件待ち (明示 trigger 付き、3 件)

| # | 項目 | A/B/C | trigger | 充足時のタスク |
|---|------|-------|---------|--------------|
| 1 | **/healthz → /health rename + redeploy** | C | 本田様 → 「/healthz 直して」明示指示 | `sync/src/sync/app.py` の `@app.get("/healthz")` を `/health` に変更 → pytest 確認 → buildx push → gcloud run deploy → curl 確認 (15-20 分) |
| 2 | **WP 統合 (server-to-server fetch 組込)** | C | 本田様 → 「WP に Cloud Run の URL 組込開始」明示指示 + WP 環境のアクセス情報 | WP 側で `https://aozora-sync-flry56mxwa-an.a.run.app/jobs/{id}` を fetch する PHP/プラグインを実装、採用ページに埋込、応募ボタン動作確認 (時間は WP 構成次第) |
| 3 | **Billing budget alert $5 設定** | A | 本田様 → 「設定したい」明示指示 (Console UI 操作なので本田様が直接実施推奨) | https://console.cloud.google.com/billing/01F6B4-48EE02-E5EFB8/budgets を開いて $5 alert を作成 (5 分) |

### 却下候補 (記録のみ、過去セッションの過剰設計記録)

| # | 項目 | 着手しない理由 |
|---|------|--------------|
| 1 | Cloud Run custom domain mapping | WP 統合前提のため不要 (本田様 2026-06-18 判断) |
| 2 | Phase 2B-0 / 2B-1 / 2B-2 の 3 分割 | 2026-06-18 過剰設計と判定、廃止 (PR #23) |
| 3 | Terraform / WIF / GitHub Actions auto-deploy | 採用サイト規模では過剰、`gcloud run deploy` 手動で十分 |
| 4 | Memorystore / Cloud Armor / Cloud LB / Monitoring uptime | トラフィック実績ベースで Phase 2B-exec 完了後に再評価、現時点では不要 |
| 5 | `/healthz` 404 の真因究明 (Cloud Run 予約 path 調査) | rename で実用解決可能、真因究明より ROI 低い |

## Issue Net 変化

- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件

## 環境状態

- Git: clean (本 PR merge 後)、main 同期想定
- Cloud Run service: `aozora-sync` 稼働中 (revision `00002-724`、traffic 100%)
- AR repository: `asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest` (image manifest list `sha256:78cb05414749...498db1a8`)
- Billing: project 紐付け済 (billing account `01F6B4-48EE02-E5EFB8`)、budget alert 未設定
- 残留プロセス: なし
- pytest: 115 件全 PASS (Phase 2A.3 完了時点、本 PR では実コード変更なし)
- ruff / pyright: clean

## 最終結論

🛑 **executor 領分の作業ゼロ、セッション終了推奨**

- OPEN PR: 1 件 (本 PR、merge 後 0 件想定)
- OPEN Issue: 0 件
- 即着手タスク: 0 件
- 条件待ち: 3 件 (いずれも本田様の指示が trigger)
- 却下候補: 5 件 (過剰設計巻き戻し + /healthz 真因究明)
- Phase 2B-exec の主目的 (Cloud Run で Jobcan proxy が稼働) は達成

根拠: [[feedback_idle_session_skip_housekeeping]] (真の executor タスクゼロ + 条件待ち trigger 未充足 = housekeeping を能動提案せず終了)
