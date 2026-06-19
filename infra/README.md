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
