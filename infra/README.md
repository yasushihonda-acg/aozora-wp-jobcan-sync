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
  --project=aozora-wp-jobcan-sync
```

API 有効化は無料 (課金は実リソース使用分のみ)。`compute.googleapis.com` は
Cloud Run の前提として自動有効化されるので明示不要。

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
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# 3b. Build + push (sync/Dockerfile を使用)
cd sync
docker build -t asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest .
docker push asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest
cd ..
```

タグは `latest` 固定。再 deploy 時は同じタグで上書き、cleanup policy により
古い digest は自動削除される。

## 4. Cloud Run deploy

```bash
gcloud run deploy aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=0.5 \
  --concurrency=10 \
  --timeout=30s \
  --set-env-vars=JOBCAN_FETCH_ENABLED=true
```

設定根拠:
- `min-instances=0`: 検証用、cold start を受け入れる代わりにアイドル課金ゼロ
- `max-instances=1`: ID 総当たり攻撃時の Jobcan 側負荷を低レベルに固定
- `memory=512Mi`: uvicorn + httpx + BeautifulSoup の安定動作下限
- `cpu=0.5`: 同上、Phase 2B-1 (live egress) で必要に応じて増強
- `concurrency=10`: cachetools の `threading.Lock` 直列実行を踏まえた現実値
- `timeout=30s`: Jobcan fetch + parse + render の上限想定
- `JOBCAN_FETCH_ENABLED=true`: live mode (WP からの fetch を実機構成で受ける)
- `allow-unauthenticated`: 採用サイトは public、自社契約 ATS の自社利用範囲
  ([feedback_saas_self_use_no_clearance.md](../.claude/memory/feedback_saas_self_use_no_clearance.md))

deploy 完了後、コマンド出力末尾に Service URL が出る:
`https://aozora-sync-XXXX-an.a.run.app`

## 5. 動作確認

```bash
SERVICE_URL=$(gcloud run services describe aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --format='value(status.url)')

# 5a. ヘルスチェック
curl "${SERVICE_URL}/healthz"
# → {"status":"healthy"}

# 5b. 詳細ページ (Jobcan の実データ取得)
curl -o /tmp/job.html "${SERVICE_URL}/jobs/1777023"
grep "job-detail" /tmp/job.html  # 自社デザイン HTML 確認

# 5c. 一覧ページ
curl -o /tmp/list.html "${SERVICE_URL}/jobs/?category_id=18773"
grep "job-list" /tmp/list.html
```

## 6. Cloud Billing budget alert (推奨)

予期せぬ課金スパイク対策として $5 budget alert を設定:

```bash
# 既存 billing account ID を取得
gcloud billing accounts list

# Billing alert は Cloud Console UI でも設定可:
# https://console.cloud.google.com/billing/<BILLING_ID>/budgets
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
