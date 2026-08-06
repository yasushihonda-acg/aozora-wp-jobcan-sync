# Phase 2B — Cloud Run sync proxy deployment

Phase 2A.2 / 2A.3 で完成した FastAPI proxy を Cloud Run に deploy する手順。
**WP 統合前提**のため custom domain mapping は使用せず、Cloud Run の
service URL (`xxx.run.app`) を WP からの server-to-server fetch ターゲットに
使う。

## 前提

- GCP project: `aozora-wp-jobcan-sync` (project number 1084369586348)
- アカウント: `yasushi.honda@aozora-cg.com`
- リージョン: `asia-northeast1`
- 想定月額: **約 $0.01** (Cloud Run 無料枠内 + Artifact Registry cleanup policy 適用)

## 1. 必須 API 有効化 (初回のみ)

```bash
export CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync

gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  --project=aozora-wp-jobcan-sync
```

API 有効化は無料 (課金は実リソース使用分のみ)。`compute.googleapis.com` は
Cloud Run の前提として自動有効化されるので明示不要。`firestore.googleapis.com` /
`secretmanager.googleapis.com` / `cloudscheduler.googleapis.com` は Phase B
(定期同期) 向けに追加 (§1.5、B-6 の Cloud Scheduler 配線で使用)。

## 1.5 Secret Manager — Slack webhook URL (Phase B、初回のみ)

`sync/src/sync/notifications.py` の `notify_slack()` が読む唯一のシークレット。
closed 率サーキットブレーカー発火時のアラート等に使う (B-3)。

```bash
# 1.5a. Slack 側で Incoming Webhook を発行し、URL を控える
#   (Slack App 管理画面 → Incoming Webhooks → Add New Webhook to Workspace)

# 1.5b. Secret Manager に登録 (値は echo -n で改行なし)
echo -n "https://hooks.slack.com/services/XXXX/YYYY/ZZZZ" | \
  gcloud secrets create slack-webhook-url \
  --project=aozora-wp-jobcan-sync \
  --data-file=- \
  --replication-policy=automatic

# 1.5c. ローテーション/URL 再発行時は新バージョンを追加 (シークレット自体は削除しない)
echo -n "https://hooks.slack.com/services/新URL" | \
  gcloud secrets versions add slack-webhook-url \
  --project=aozora-wp-jobcan-sync \
  --data-file=-
```

Cloud Run (Job/Service いずれも) の実行 SA に `roles/secretmanager.secretAccessor`
を付与すること (B-6 のサービスアカウント作成手順内で実施)。

## 2. Artifact Registry repository 作成 + cleanup policy 適用 (初回のみ)

`gcp.md` MUST に従って **最新 2 件保持** の cleanup policy を必ず設定。

```bash
# 2a. Repository 作成 (DOCKER 形式、asia-northeast1)
gcloud artifacts repositories create aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --repository-format=docker \
  --description="aozora-wp-jobcan-sync proxy images"

# 2b. Cleanup policy をドライランで確認
gcloud artifacts repositories set-cleanup-policies aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --policy=infra/cleanup-policy.json \
  --dry-run

# 2c. 問題なければ適用
gcloud artifacts repositories set-cleanup-policies aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --policy=infra/cleanup-policy.json \
  --no-dry-run
```

## 3. Docker image build + push

```bash
# 3a. Artifact Registry 認証 (初回のみ)
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud auth configure-docker asia-northeast1-docker.pkg.dev --quiet

# 3b. buildx で linux/amd64 cross-build + push を一括実行
cd sync
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync \
docker buildx build --platform linux/amd64 --push \
  -t asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest .
cd ..
```

タグは `latest` 固定。再 deploy 時は同じタグで上書き、cleanup policy により
古い digest は自動削除される。

**注意点 (2026-06-19 実 deploy で検出)**:
- `CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync` を必ず明示 prefix する。bash subshell では direnv 不発火、グローバル active config が別アカウント (例: `hy.unimail.11`) のとき docker push 時に `Permission 'artifactregistry.repositories.uploadArtifacts' denied` で失敗する。
- Apple Silicon Mac (arm64 host) では `docker build` 単独ではなく **`docker buildx build --platform linux/amd64 --push`** を使う。通常の `docker build` は arm64 image を生成し、Cloud Run deploy 時に `Container manifest type 'application/vnd.oci.image.index.v1+json' must support amd64/linux` エラーで失敗する。

## 4. Cloud Run deploy

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run deploy aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --concurrency=10 \
  --timeout=30s \
  --set-env-vars=JOBCAN_FETCH_ENABLED=true
```

設定根拠:
- `min-instances=0`: 検証用、cold start を受け入れる代わりにアイドル課金ゼロ
- `max-instances=1`: ID 総当たり攻撃時の Jobcan 側負荷を低レベルに固定
- `memory=512Mi`: uvicorn + httpx + BeautifulSoup の安定動作下限
- `cpu=1`: Cloud Run 仕様 `cpu < 1 は concurrency > 1 と組み合わせ不可` への対応 (2026-06-19 deploy 時に検出)
- `concurrency=10`: cachetools の `threading.Lock` 直列実行を踏まえた現実値
- `timeout=30s`: Jobcan fetch + parse + render の上限想定
- `JOBCAN_FETCH_ENABLED=true`: live mode (WP からの fetch を実機構成で受ける)
- `allow-unauthenticated`: 採用サイトは public、自社契約 ATS の自社利用範囲
  ([feedback_saas_self_use_no_clearance.md](../.claude/memory/feedback_saas_self_use_no_clearance.md))

deploy 完了後、コマンド出力末尾に Service URL が出る:
`https://aozora-sync-XXXX-an.a.run.app` (新形式) または
`https://aozora-sync-1084369586348.asia-northeast1.run.app` (project number 形式、両方とも有効)。

## 5. 動作確認

```bash
SERVICE_URL=$(CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run services describe aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --format='value(status.url)')

# 5a. ヘルスチェック (現状 GFE で 404 になる known issue、§7 参照)
curl "${SERVICE_URL}/healthz"
# → 期待値: {"status":"healthy"}
# → 実測値 (2026-06-19): HTTP 404 (GFE で intercepted、Cloud Run app に届かない)

# 5b. 詳細ページ (Jobcan の実データ取得)
curl -o /tmp/job.html "${SERVICE_URL}/jobs/1777023"
grep "sync-job-detail" /tmp/job.html  # 自社 BEM class 確認

# 5c. 一覧ページ
curl -o /tmp/list.html "${SERVICE_URL}/jobs/?category_id=18773"
grep "sync-job-list" /tmp/list.html
```

## 6. Cloud Billing budget alert (推奨)

予期せぬ課金スパイク対策として $5 budget alert を設定:

- 紐付け済 billing account ID: `01F6B4-48EE02-E5EFB8`
- 設定 URL: https://console.cloud.google.com/billing/01F6B4-48EE02-E5EFB8/budgets

CLI から `gcloud billing budgets create` も可能だが、Billing Account Admin の追加権限が必要。
個人 GCP では Cloud Console UI 経由が容易。

## 7. Known issues (2026-06-19 deploy で検出)

### 7.1 `/healthz` が GFE で 404 になる

- 症状: `GET /healthz` が HTTP 404 + Google's `Error 404 (Not Found)!!1` page を返す。Cloud Run app のログにリクエスト痕跡なし
- 原因仮説: Cloud Run / GFE 側で `/healthz` を予約 path として handling している可能性
- 影響: 採用サイト本番運用 (`/jobs/{id}` と `/jobs/?category_id=...` のみ呼ぶ WP 統合) には**影響なし**
- 対処: `sync/src/sync/app.py` の `/healthz` → `/health` 等にリネーム + redeploy で解消見込。Phase 2B-exec の追加修正として後日対応 (現状 deploy のままでも core 機能は動作)

## 8. Phase B — Cloud Run Job + Cloud Scheduler (定期同期、B-6)

`sync-run` (`python -m sync sync-run`、`sync/src/sync/cli.py`) が日次実行する
バッチ本体。§4 の FastAPI proxy サービスとは**別プロセス** (Cloud Run Job) —
プロキシは求人ページの動的配信、Job はクロール→Firestore 書込みのみを行う。

Terraform モジュール化はしない (2026-06-18 の過剰設計巻き戻し方針、
`.claude/memory/feedback_overengineering_recovery_2026-06-18.md` 参照)。`gcloud`
コマンドを直接実行する。

### 8.1 サービスアカウント作成 (初回のみ)

```bash
gcloud iam service-accounts create aozora-sync-job \
  --project=aozora-wp-jobcan-sync \
  --display-name="aozora-sync Cloud Run Job (daily crawl)"

# Firestore 読み書き
gcloud projects add-iam-policy-binding aozora-wp-jobcan-sync \
  --member="serviceAccount:aozora-sync-job@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Secret Manager (slack-webhook-url) 読み取り — §1.5 で作成済みのシークレットに対して
gcloud secrets add-iam-policy-binding slack-webhook-url \
  --project=aozora-wp-jobcan-sync \
  --member="serviceAccount:aozora-sync-job@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 8.2 Cloud Run Job 作成 + デプロイ

§3 で push した同じイメージを使う (`app.py` の FastAPI サーバーではなく
`python -m sync sync-run` を起動コマンドとして上書きする)。

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run jobs create aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest \
  --command=python \
  --args="-m,sync,sync-run" \
  --service-account=aozora-sync-job@aozora-wp-jobcan-sync.iam.gserviceaccount.com \
  --set-env-vars=REVIEW_BYPASS=false \
  --memory=512Mi \
  --cpu=1 \
  --max-retries=0 \
  --task-timeout=600s
```

設定根拠:
- `REVIEW_BYPASS=false`: CLAUDE.md の運用計画通り初期は半自動 (`pending_review`
  → Slack 通知経由で人間承認)。運用が安定したら `gcloud run jobs update` で
  `true` に切替 (`approval.py` のフラグ、コード変更不要)
- `max-retries=0`: 失敗時に自動リトライしない — 翌日の Cloud Scheduler 実行が
  実質的な再試行になるため、同日中の多重実行は避ける
- `task-timeout=600s`: 全カテゴリ (17件、うち複数ページ) のクロール + Firestore
  書込みを想定した上限。既存 FastAPI サービスの `timeout=30s` (単一リクエスト
  想定) とは無関係

新イメージを push した後、Job にも反映するには (Cloud Run Job は Service と違い
自動で最新イメージを追わない):

```bash
gcloud run jobs update aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest
```

### 8.3 Cloud Scheduler — 日次トリガー (初回のみ)

ジョブカン側の低負荷時間帯を想定し、JST 深夜 3:00 (`cron` は UTC 基準の
Scheduler location 設定に依存するため `--time-zone` を明示):

```bash
# Cloud Run Job を起動するための実行用 SA (Scheduler -> Cloud Run Job の OIDC 認証)
gcloud iam service-accounts create aozora-scheduler-invoker \
  --project=aozora-wp-jobcan-sync \
  --display-name="Cloud Scheduler invoker for aozora-sync-daily"

gcloud run jobs add-iam-policy-binding aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --member="serviceAccount:aozora-scheduler-invoker@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud scheduler jobs create http aozora-sync-daily-trigger \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --schedule="0 3 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://asia-northeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/aozora-wp-jobcan-sync/jobs/aozora-sync-daily:run" \
  --http-method=POST \
  --oauth-service-account-email=aozora-scheduler-invoker@aozora-wp-jobcan-sync.iam.gserviceaccount.com
```

### 8.4 動作確認

```bash
# 手動トリガー (Scheduler を待たずに即時実行)
gcloud scheduler jobs run aozora-sync-daily-trigger \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1

# 実行結果確認 (exit code 5 = closed率サーキットブレーカー発火、0 = 正常)
gcloud run jobs executions list \
  --job=aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1

# ログ確認 (crawler.py / closed_detection.py の structured log を grep)
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="aozora-sync-daily"' \
  --project=aozora-wp-jobcan-sync \
  --limit=50 \
  --format=json
```

## ロールバック

新 image deploy 後に旧 revision に traffic を戻したい場合:

```bash
# 過去 revisions 一覧
gcloud run revisions list \
  --service=aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1

# 旧 revision に 100% 戻す
gcloud run services update-traffic aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --to-revisions=aozora-sync-XXXXX-yyy=100
```

## サービス削除 (検証停止時)

```bash
gcloud run services delete aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1
```

Artifact Registry repository は image storage が残るため別途削除:

```bash
gcloud artifacts repositories delete aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1
```
