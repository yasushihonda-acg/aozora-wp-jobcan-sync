# 同期戦略 (Sync Strategy)

> Codex セカンドオピニオン (2026-06-16) を反映し、優先順位を「公式照会 → CSV 半自動 → HTML パース暫定」に修正。

## 1. 同期方式の優先順位

| 順位 | 方式 | 採用条件 | 想定運用 |
|---|---|---|---|
| 1 | ジョブカン公式 API / 公式エクスポート機能 | ジョブカンから書面回答で利用可能と確認 | NDA・STANDARD プラン契約後に正式採用 |
| 2 | **CSV 半自動** (管理画面エクスポート → GCS → 取込) | 主系として最初に稼働 | 週次〜日次、採用担当承認付き |
| 3 | HTML パース (公開ページクロール) | 公式照会で許容回答が得られた場合のみ、暫定・低頻度 | 6h or 12h、Crawl-delay 厳守、手動確認付き |

**重要**: HTML パースは「ジョブカン側の想定利用ではない可能性」が Codex から指摘されている。公式照会の結果を見ずに本番採用しない。

## 2. ジョブカン公式照会 — 文面ドラフト

> 用途: ジョブカン採用管理サポート (`support@ats.jobcan.ne.jp` 等) への問合せ用。ユーザー (本田) が送信。

```
件名: 公開求人ページの自動取得・自社別ドメイン再掲出の可否について

ジョブカン採用管理サポートチーム ご担当者様

いつもお世話になっております。
あおぞらケアグループ (アカウント: aozora、URL: https://recruit.jobcan.jp/aozora) の本田と申します。

このたび、自社採用サイトを WordPress で独自構築する計画を進めており、求人票管理・応募管理は引き続き
ジョブカン採用管理で運用したいと考えております。応募フォームについても、ジョブカン応募フォーム
(/aozora/entry/new/{job_id}) への直リンクを継続いたします。

つきましては、以下 3 点についてご教示いただけますと幸いです。

【1. 公開求人データの外部取得方法】
当社契約プラン (※プラン名を本田が確認) で利用可能な以下の連携方法について、それぞれの可否と概要を
お教えください。
  (1) 公開求人データ取得用の API (REST 等)
  (2) 求人マスター CSV の自動エクスポート (スケジュール出力、GCS / SFTP 等への送信)
  (3) 求人公開・更新・募集終了をトリガーとする Webhook 通知

【2. 公開ページの定期取得・再掲出の可否】
上記 (1) (2) (3) が利用できない場合、暫定措置として
"https://recruit.jobcan.jp/aozora/job_offers/{job_id}" の公開求人詳細ページを当社 GCP からクローラーで
定期取得し (Crawl-delay 3-5 秒、User-Agent 明示、頻度 6 時間に 1 回程度)、当社の別ドメイン
(recruit.aozora-cg.com) で再表示することは利用規約・運用上問題ないでしょうか。

【3. 必要な契約プラン変更・申請】
上記いずれかを公式に利用するため契約プラン変更や NDA 締結等が必要であれば、手続きの概要と
費用感をお知らせください。

お忙しいところ恐縮ですが、ご回答をお待ちしております。

----
あおぞらケアグループ
本田 泰
yasushi.honda@aozora-cg.com
```

> 送信前にユーザー側で「契約プラン名」「想定する更新頻度」を埋めて確定する。

## 3. 各方式の評価詳細

### 案 1: 公式 API / エクスポート
- 利点: 安定 / 利用規約上の明確化 / 業務継続性
- 欠点: 契約プラン依存 (STANDARD 月 3 万円〜) / NDA 必須の可能性 / 実装着手まで 1〜2 ヶ月
- 着手判断: 公式回答で「利用可能」と書面確認した瞬間に Phase C で全面移行

### 案 2: CSV 半自動 (主系として推奨)
- フロー:
  1. 採用担当が ジョブカン採用画面 > 求人一覧 > 一括アクション > CSV ダウンロード (UTF-8)
  2. CSV を GCS バケット (`gs://aozora-wp-jobcan-sync-csv/inbox/`) にアップロード (Cloud Console or `gsutil cp`)
  3. Cloud Run Job が GCS ファイル検知 → パース → Firestore に正規化保存
  4. **差分プレビュー** を採用担当に通知 (Slack or メール)
  5. 採用担当が承認 → WP REST API へ POST/PUT/private 化
- 頻度: 週 1 (求人更新がある週)、または変更時に都度
- 利点: 法務リスクほぼゼロ / 採用担当の作業時間 5 分/週 / 完全に自動化はしないので誤同期リスク最小
- 欠点: 完全自動ではない、手動運用が残る

### 案 3: HTML パース (暫定のみ)
- 採用条件: ジョブカンから公式照会で「明示的に許容」または「許容も禁止もしない」と回答があった場合のみ
- 制約:
  - Crawl-delay 3〜5 秒、`User-Agent: AozoraJobcanSync/1.0 (+contact@aozora-cg.com)`
  - 頻度 6h or 12h
  - 取得結果を **必ず Firestore キャッシュ + content_hash で差分検出**
  - 連続 2 回不在で初めて closed、closed 率 > 30% で同期中止 + Slack アラート
  - WP 反映前に必ず差分プレビュー (初期 1 ヶ月)
- 不採用条件: ジョブカンから「自動取得を控えてほしい」回答 → 即座に中止し案 2 のみで運用

## 4. 共通: 認証・Secret 管理

- WordPress: Application Password (`wp-app-password`) を Secret Manager に保存
- Cloud Run Job: Workload Identity で Secret Manager / Firestore / GCS にアクセス
- Slack: 通知用 Incoming Webhook URL を Secret Manager に
- ジョブカン (案 1 採用時): API トークンを Secret Manager に
- ローテーション: 90 日サイクル (CLAUDE.md グローバル方針に従う)

## 5. 復旧設計 (Codex 指摘 #6 反映)

| シナリオ | 検知 | 対処 |
|---|---|---|
| 同期で全求人 closed 化 | closed 率 > 30% | 同期中止 + Slack アラート + 採用担当へエスカレート |
| 応募リンクが壊れた | link checker (日次 HEAD) | 該当求人を private 化 + 通知 |
| WP データ破損 | WP 側監視 + Cloud SQL or マネージド WP のバックアップ | Firestore 前回スナップショットから復元 |
| ジョブカン側 HTML 変更で取得失敗 | Cloud Logging error rate | 同期中止 + 手動 CSV 運用に切替 |
| Cloud Run Job IP が遮断 | 連続 5xx / 429 | Crawl-delay 倍増 + UA 確認 + ジョブカンに連絡 |

## 6. データモデル (Phase B 詳細)

```
Firestore: job_cache/{job_id}
  - source: "csv" | "html_parse" | "api"
  - raw_html_or_csv_row: string
  - content_hash: sha256
  - normalized: { title, salary, location, employment_type, job_type, ... }
  - source_url: string
  - apply_url: string
  - last_seen_at: timestamp
  - sync_status: "active" | "closed" | "pending_review"

WordPress: CPT job_offer
  - post_title: 求人タイトル
  - post_content: 仕事内容 (原文スナップショット保持)
  - meta:jobcan_job_id (ユニークキー)
  - meta:source_url
  - meta:apply_url
  - meta:salary_text, work_hours, holidays, welfare, requirements
  - meta:address, station
  - meta:content_hash
  - meta:last_synced_at
  - meta:sync_status (active/closed)
  - meta:closed_at (closed 化日時、30 日後に trash)
  - tax:job_type, employment_type, location, facility
```

## 7. ロードマップ

| 時期 | 内容 |
|---|---|
| Phase A 中 | ジョブカン公式照会 (この文面送付) → 回答待ち |
| Phase B 初期 | 案 2 (CSV 半自動) で本番稼働開始、まず週次運用 |
| Phase B 中期 | 案 3 採用可なら追加実装 (案 2 のフォールバック付き) |
| Phase C | 案 1 採用可なら全面移行 (アダプター差し替え設計で実装) |
