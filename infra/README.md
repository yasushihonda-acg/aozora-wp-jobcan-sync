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

**2026-08-07 判明**: このブロックは Phase B 実装 (B-1〜B-7) 時点で一度も実行
されておらず、`gcloud services list --enabled` で確認したところ
`artifactregistry` / `datastore` / `run` の3つのみが有効化済みだった
(`firestore` / `secretmanager` / `cloudscheduler` は未有効化)。**下記 §1a
(Firestore データベース本体の作成) を含め、§1 全体を配信層統合 (B-8) の
最初のステップとして実際に実行すること。**

### 1a. Firestore データベース作成 (初回のみ、B-8)

API 有効化だけではデータベース自体は作られない。日本リージョンに Native
mode で作成する (`.claude/memory/feedback_firestore_default_location_japan.md`
の日本コンプライアンス方針に従う):

```bash
gcloud firestore databases create \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --type=firestore-native
```

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

**B-8 (2026-08-07) で配信層を Firestore 単一ソースへ書き換えた**ため、
`JOBCAN_FETCH_ENABLED` は意味を失い削除。代わりに Firestore **読み取り専用**
権限を持つ専用サービスアカウントと、プロジェクト/DB を指す env var が必要。
デフォルトの Compute Engine SA (これまでの実運用アカウント) へは付与しない
— 最小権限の原則で専用 SA を切る。

```bash
# 4a. 専用サービスアカウント作成 (初回のみ、Web サービス用 — B-6 の
#     aozora-sync-job とは別物。Job は read/write、Web は read-only)
gcloud iam service-accounts create aozora-sync-web \
  --project=aozora-wp-jobcan-sync \
  --display-name="aozora-sync Cloud Run Service (Firestore read-only proxy)"

gcloud projects add-iam-policy-binding aozora-wp-jobcan-sync \
  --member="serviceAccount:aozora-sync-web@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/datastore.viewer"

# 4b. デプロイ
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run deploy aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=aozora-sync-web@aozora-wp-jobcan-sync.iam.gserviceaccount.com \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --concurrency=10 \
  --timeout=30s \
  --set-env-vars=GCP_PROJECT_ID=aozora-wp-jobcan-sync,FIRESTORE_DATABASE="(default)"
```

設定根拠:
- `min-instances=0`: 検証用、cold start を受け入れる代わりにアイドル課金ゼロ
- `max-instances=1`: 求人34件程度の規模を踏まえた低コスト固定 (Firestore read
  のみで Jobcan への負荷は既に存在しない)
- `memory=512Mi`: uvicorn + Jinja2 の安定動作下限
- `cpu=1`: Cloud Run 仕様 `cpu < 1 は concurrency > 1 と組み合わせ不可` への対応 (2026-06-19 deploy 時に検出)
- `concurrency=10`: cachetools の `threading.Lock` 直列実行を踏まえた現実値
- `timeout=30s`: Firestore read + render の上限想定 (旧 Jobcan fetch 前提より大幅に余裕あり)
- `service-account=aozora-sync-web@...` + `GCP_PROJECT_ID`/`FIRESTORE_DATABASE`: B-8 で Firestore 読み取りが必要になったための追加
- `allow-unauthenticated`: 採用サイトは public、自社契約 ATS の自社利用範囲
  ([feedback_saas_self_use_no_clearance.md](../.claude/memory/feedback_saas_self_use_no_clearance.md))。Firestore への書き込み権限を持たない read-only SA なので、公開エンドポイントであること自体のリスクは変わらず低い

deploy 完了後、コマンド出力末尾に Service URL が出る:
`https://aozora-sync-XXXX-an.a.run.app` (新形式) または
`https://aozora-sync-1084369586348.asia-northeast1.run.app` (project number 形式、両方とも有効)。

## 5. 動作確認

**B-8 以降、`/jobs/{id}` と `/jobs/?category_id=` は Firestore `job_cache` に
実際にドキュメントが存在しないと空振りする** (404 または0件の一覧)。§8 の
Cloud Run Job を最低1回実行して Firestore を populate してから確認すること。

```bash
SERVICE_URL=$(CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run services describe aozora-sync \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --format='value(status.url)')

# 5a. ヘルスチェック (現状 GFE で 404 になる known issue、§7 参照)
curl "${SERVICE_URL}/healthz"
# → 期待値: {"status":"healthy"}
# → 実測値 (2026-06-19): HTTP 404 (GFE で intercepted、Cloud Run app に届かない)

# 5b. 詳細ページ (§8 の Job 実行後、実在する job_id に差し替えて実行)
curl -s -o /tmp/job.html -w "%{http_code} %{time_total}s\n" "${SERVICE_URL}/jobs/<job_id>"
grep "sync-job-detail" /tmp/job.html  # 自社 BEM class 確認
# → 200 かつ 1秒未満のはず (Jobcan への往復が無いため、旧実装より明確に速い)

# 5c. 一覧ページ (§8 の Job 実行後、実在する category_id に差し替えて実行)
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

### 8.1b クローラ dry-run 検証 (B-8、初回のみ、8.2 の前に必ず実施)

このクローラ (ページネーション walk・`.pagination-number` 検算) は**実
ジョブカンに対して実行された実績がゼロ** (フィクスチャ解析から書き起こした
コードのみ、2026-08-07 時点)。Firestore への書き込みなしで一度動作を目視
確認してから Job を作成する:

```bash
cd sync
uv run python -c "
from sync.crawler import crawl_all
from sync.jobcan_client import JobcanClient

with JobcanClient() as client:
    result = crawl_all(client)

print(f'offers={len(result.offers)} errors={len(result.errors)}')
print(f'expected_total={result.expected_total} collected_total={result.collected_total}')
print(f'fully_listed={result.fully_listed}')
"
```

期待値: `expected_total == collected_total`、`fully_listed=True`、
`errors=0`。件数がジョブカン実サイトの表示件数と一致することも目視で確認
する。ここで想定外の差異が出た場合、配信は現行の GitHub Pages 静的モック
のまま (このコマンドは Firestore に一切書き込まないため無害) で止まれる。

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
  --set-env-vars=REVIEW_BYPASS=true \
  --memory=512Mi \
  --cpu=1 \
  --max-retries=0 \
  --task-timeout=3600s
```

設定根拠:
- `REVIEW_BYPASS=true`: **2026-08-07 決裁者判断で完全自動化に確定**
  (人間承認ステップを恒久的に挟まない)。当初計画していた「初期1ヶ月は
  半自動→安定後に自動化」の段階運用は不採用。`approval.py` の
  `pending_review` ゲート自体はコードとして残すが、この env var が `true`
  である限り実際には発生しない (`compute_target_sync_status` の既存実装)
- `max-retries=0`: 失敗時に自動リトライしない — 翌日の Cloud Scheduler 実行が
  実質的な再試行になるため、同日中の多重実行は避ける
- `task-timeout=3600s`: 全17カテゴリ(実測382件、47リストページ)を
  crawl_delay 3秒で巡回すると実測約21.4分(1,287秒)。Cloud Run Job の
  課金は実実行時間のみで timeout 上限を上げてもコストは増えないため、
  リトライバックオフ等の揺らぎを吸収する余裕を持たせて1時間に設定
  (旧 `1800s` でも実測値の約1.4倍の余裕はあったが、より安全側に統一)。既存 FastAPI サービスの
  `timeout=30s` (単一リクエスト想定) とは無関係

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

## B-8 初回ロールアウト順序 (この順を守る)

Phase B のインフラは 2026-08-07 時点で何も存在しない状態から作る (§1 冒頭の
注記参照)。番号は本ドキュメントの節番号:

1. §3 でコードをビルド・push
2. §1 (API有効化) → §1a (Firestore DB作成) → §1.5 (Secret作成) → §4a (Web用 SA + IAM) → §8.1 (Job用 SA + IAM) を実行
3. §8.1b でクローラを実ジョブカンに対して dry-run 検証 (Firestore 書き込みなし)
4. §8.2 で Cloud Run Job を `REVIEW_BYPASS=true` で作成し、§8.4 の手動トリガーで **1回実行** → Firestore に全求人が `active` で入る
5. `python -m sync` 相当で Firestore の中身を確認してから §4 で Service をデプロイ (この時点で初めて配信が Firestore 由来になる)
6. §8.3 で Cloud Scheduler を作成し、以降は日次自動運用

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

B-8 (Firestore 単一ソース化) 後にロールバックする場合、B-8 より前の revision
はジョブカン直接フェッチのコードなので Firestore の状態に依存せず即座に復旧
する。逆方向 (B-8 後の revision へ再度切替) も安全 — Firestore の内容は Job
の実行結果であり、Service のデプロイでは変化しない。

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
