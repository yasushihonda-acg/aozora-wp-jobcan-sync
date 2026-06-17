# 同期戦略 (Sync Strategy)

> **2026-06-17 大幅更新 (Codex セカンドオピニオン 2 回目反映)**:
> 案 D (動的プロキシ + 自社テンプレ再表示) を採用方針に格上げ。WP CPT 不要、データ複製不要、応募導線はジョブカン直リンクで温存。
>
> **公式照会を Phase 4 → Phase 1 (早期ゲート) に格上げ**: 案 D は許諾が取れない場合に成立しない設計であり、Phase 2 以降の Cloud Run / Terraform / Memorystore 投資を始める前に許諾範囲を確定させる必要がある。

## 0. 採用方針 (2026-06-17 確定)

**案 D: 動的プロキシ + HTML 書き換え**

- Cloud Run (Python 3.12 + httpx + BeautifulSoup + Jinja2) が `https://recruit.aozora-cg.com/jobs/{id}` を受信
- ジョブカン `recruit.jobcan.jp/aozora/job_offers/{id}` を httpx で取得 → BeautifulSoup でパース → Pydantic 正規化 → bleach で sanitize → Jinja2 自社テンプレに埋め込み → 配信
- 応募ボタンは `recruit.jobcan.jp/aozora/entry/new/{id}` 直リンク (ジョブカン側で完結、コンバージョン計測そのまま)
- WP は求人ページから外す (Phase 4 で「ブログ・お知らせ」のみ別ホスティング)
- 月額目安: Cloud Run のみで ¥1-3k

**Phase 0 (本日完了): ローカル PoC** — `sync/` ディレクトリに最小実装、`python -m sync render <id>` で動作確認、pytest 17 件全 PASS。**本番デプロイは行わない**。

## 1. 同期方式の優先順位 (案 D 採用後の整理)

| 順位 | 方式 | 採用条件 | 想定運用 |
|---|---|---|---|
| **1 (採用)** | **案 D: 動的プロキシ + 自社テンプレ再表示** | **公式照会で「HTMLパースして自社テンプレで再配信」が許諾されること** | Cloud Run + 5 分 TTL キャッシュ、フォールバック 302 |
| 2 (fallback) | 案 A: 手動 CSV エクスポート → GCS → 取込 | 案 D が許諾されない場合の代替 | 週次、採用担当 5 分/週 |
| 3 (将来) | 案 C: ジョブカン公式 API / Webhook | 公式照会で提供有と回答 + 契約条件 OK | Phase C 以降で全面移行 |
| - (却下) | 案 B: HTML パース cron → Firestore → WP CPT | データ複製コスト過大 | - |

**重要**: 案 D は「公開HTMLの再整形配信」であり、許諾が取れない場合に成立しない (Codex 指摘 Q2 ❌ 重大な懸念)。本番デプロイ前に公式照会で書面確認が必須。

## 2. ジョブカン公式照会 — 文面ドラフト (2026-06-17 Codex 指摘 5 項目を反映)

> 用途: ジョブカン採用管理サポート (`support@ats.jobcan.ne.jp` 等) への問合せ用。ユーザー (本田) が送信。
>
> Codex 指摘 (Q2): 「曖昧にしない、許諾範囲は『iframe 埋め込み / リンク / API / HTML 加工再配信』でかなり違う」。下記文面では【4】を新設して案 D を明示確認する。

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

【4. 動的プロキシ + 自社テンプレ再表示の可否 (採用予定の方式)】
当社で技術的に最有力としている方式について、可否を具体的にご教示ください。
  (1) "https://recruit.jobcan.jp/aozora/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
      の公開求人 HTML を当社サーバー (Google Cloud Run) が定期取得 (5 分キャッシュ) し、
      当社ドメイン (recruit.aozora-cg.com) 上で自社デザイン (Jinja2 テンプレ) に再表示することの可否
  (2) 上記に伴う以下の前提条件への評価:
        - 応募ボタンはジョブカン側 URL (/aozora/entry/new/{job_id}) に直リンク (応募完了率・コンバージョン計測は不変)
        - 取得 HTML 内の本文部分のみを sanitize の上で再表示、script / form / style はすべて削除
        - canonical タグはジョブカン側 URL を指す設定 (SEO duplicate content 回避)
        - HTML 構造変更時はジョブカン側 URL へ自動 302 redirect (フォールバック)
        - 想定アクセス頻度: キャッシュにより 1 求人あたり 5 分に 1 回まで
  (3) 上記方式が NG の場合の代替として、案 (1)〜(3) のうちどれが推奨されるか

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
