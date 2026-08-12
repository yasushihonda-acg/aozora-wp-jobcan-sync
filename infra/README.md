# Phase 2B — Cloud Run sync proxy deployment

Phase 2A.2 / 2A.3 で完成した FastAPI proxy を Cloud Run に deploy する手順。

**2026-08-08 更新 (Stage 1: Cloud Run 全面集約)**: 「WP 統合前提」という
上記の旧方針は決裁者判断で撤回済み。社長から「実際のJobcan(382件)より少ない
件数(37件)を求人一覧として公開し続けるのはまずいのでは」との指摘を受け、
Phase A(GitHub Pages、37件のみのサンプル)を Phase B(この Cloud Run
サービス、382件全件を Firestore 経由で自動反映)へ本番切替する方針に転換した。
トップページ・静的アセット(`mockup/assets`)もこのサービスに同梱し、
`recruit.aozora-cg.com` を最終的に直接このサービスへ向ける(custom domain
mapping は Stage 5 で対応、それまでは `xxx.run.app` の service URL が唯一の
公開先)。段階リリース(Stage 1: 静的配信基盤+トップページ移植 → Stage 2:
求人詳細デザインパリティ → Stage 3: 求人一覧デザインパリティ → Stage 4:
本番公開前の健全性対応 → Stage 5: ドメイン切替)の詳細は
`docs/handoff/GOAL.md` を参照。

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

## 1.5 Secret Manager — 運用通知 webhook URL (Google Chat) (Phase B、初回のみ)

`sync/src/sync/notifications.py` の `notify_ops()` が読む唯一のシークレット。
closed 率サーキットブレーカー発火時のアラート等に使う (B-3)。運用チャンネルは
Google Chat (Slack ではない)。

```bash
# 1.5a. Google Chat 側で Incoming Webhook を発行し、URL を控える
#   Google Chat で対象スペースを開く → スペース名クリック → アプリと連携
#   → Webhook → 名前を付けて追加 → 表示された URL をコピー
#   (組織ポリシーにより Chat アプリ/Webhook の追加が管理者に制限されている場合が
#    あるため、メニューが出ない場合は Workspace 管理者に有効化を依頼すること)

# 1.5b. Secret Manager に登録 (値は echo -n で改行なし。key/token クエリまで含めた
#       URL 全体を登録する — Google Chat はこのクエリで認証する)
echo -n "https://chat.googleapis.com/v1/spaces/AAAA/messages?key=XXXX&token=YYYY" | \
  gcloud secrets create ops-webhook-url \
  --project=aozora-wp-jobcan-sync \
  --data-file=- \
  --replication-policy=automatic

# 1.5c. ローテーション/URL 再発行時は新バージョンを追加 (シークレット自体は削除しない)
echo -n "https://chat.googleapis.com/v1/spaces/AAAA/messages?key=新key&token=新token" | \
  gcloud secrets versions add ops-webhook-url \
  --project=aozora-wp-jobcan-sync \
  --data-file=-
```

Cloud Run (Job/Service いずれも) の実行 SA に `roles/secretmanager.secretAccessor`
を付与すること (B-6 のサービスアカウント作成手順内で実施)。

## 1.6 Secret Manager — ジョブカンCSV自動取得用パスワード (CSV移行、初回のみ)

HTML解析方式からCSV自動取得方式への移行(2026-08-10開始、`docs/handoff/GOAL.md`
参照)で使う、閲覧限定権限の専用アカウント `jobcan-sync@aozora-cg.com` の
ログインパスワード。メールアドレス自体は非機密(既にドキュメント上に平文で
複数箇所記載済み)なのでシークレット化せず、パスワードのみを Secret Manager
へ格納する。

シークレットコンテナと IAM 権限(実行SA: `aozora-sync-job`、既存の6時間ごと
定期クロールJobと同じ基盤に統合する想定)は作成済み(2026-08-10):

```bash
# 既に実行済み — 再実行不要 (idempotent ではないため二重実行するとエラーになる)
gcloud secrets create jobcan-sync-password \
  --project=aozora-wp-jobcan-sync \
  --replication-policy=automatic

gcloud secrets add-iam-policy-binding jobcan-sync-password \
  --project=aozora-wp-jobcan-sync \
  --member="serviceAccount:aozora-sync-job@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**パスワード本体(シークレットのバージョン)は、値を Claude Code のセッション
(このファイル・チャット履歴含む)に一切経由させず、decision-maker が自身で
登録すること。**

**2026-08-10 実施結果: `gcloud secrets versions add` は使えなかった。** zsh
では `read -s -p` の `-p` がコプロセス入力の意味になり構文エラーになる
(zshでプロンプト付きで読むには `read -s "VAR?プロンプト"` 形式を使う)。
さらに `--data-file=-` でパイプ経由にすると stdin が塞がるため、Google
アカウントの reauth (機微操作の再認証) が要求された際にプロンプトを出せず
`Reauthentication required. Please enter your password` を繰り返すだけで
失敗する。この reauth はパスワード入力方式のみに対応しており、
SSO/2段階認証で運用しているアカウント(本プロジェクトの
`yasushi.honda@aozora-cg.com` を含む)には有効なパスワードが存在しないため、
`gcloud auth revoke` → `gcloud auth login` でブラウザ経由の再ログインを
完全にやり直しても解消しなかった(CLIの構造的な制限、次回も同じ壁に当たる
想定でよい)。

**実際に機能したのは GCP コンソール(ブラウザ)経由での登録:**

1. ブラウザで `https://console.cloud.google.com/security/secret-manager?project=aozora-wp-jobcan-sync` を開く(SSOログイン済みのタブでよい)
2. `jobcan-sync-password` をクリック → 「新しいバージョン」
3. 「シークレットの値」欄にパスワードを入力して保存

ローテーション時も同じ手順でよい(コンソールの「新しいバージョン」は
既存バージョンを消さず追加するのみ)。

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

**2026-08-08 更新 (Stage 1)**: `sync/Dockerfile` はトップページ+静的アセット
(`mockup/assets`, `mockup/index.html`) も同梱するため、build context が
`sync/` から**リポジトリルート**に変わった(`-f sync/Dockerfile` で
Dockerfile の場所を明示、`.dockerignore` もリポジトリルートへ移動済み)。
`cd sync` していた旧手順との違いに注意。

```bash
# 3a. Artifact Registry 認証 (初回のみ)
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud auth configure-docker asia-northeast1-docker.pkg.dev --quiet

# 3b. buildx で linux/amd64 cross-build + push を一括実行 (リポジトリルートから実行)
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync \
docker buildx build --platform linux/amd64 --push \
  -f sync/Dockerfile \
  -t asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest .
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
  --set-env-vars=GCP_PROJECT_ID=aozora-wp-jobcan-sync,FIRESTORE_DATABASE="(default)",PUBLIC_BASE_URL="https://aozora-sync-flry56mxwa-an.a.run.app"
```

`PUBLIC_BASE_URL` (2026-08-08 Stage 1 追加): canonical URL をこのサービス自身
のURLで組み立てるための値(末尾スラッシュなし)。`gcloud run services describe
aozora-sync --format='value(status.url)'` が返す値(ハッシュ形式)を使う —
project number 形式(`https://aozora-sync-1084369586348.asia-northeast1.run.app`)
も疎通するが(§5 動作確認と同じ「両方とも有効」)、`gcloud describe` の報告値
をそのまま使うのが取り違え防止として最も確実。**Stage 5 でドメインを
`recruit.aozora-cg.com` に切り替えたら、この値も合わせて更新すること**
(忘れると canonical が古い `*.run.app` URLを指したままになる)。
`STATIC_ASSETS_DIR`/`INDEX_HTML_PATH` は `Dockerfile` の `ENV` で固定済みの
ため `--set-env-vars` に含める必要はない。

**忘れやすい関連手順 (2026-08-08 codex review で発覚)**: 埋め込み済みチャット
ボットウィジェット(`mockup/index.html` に既に組み込み済み、PR #97)がこの
サービスのオリジンから動くようにするため、`aozora-chatbot` サービスの
`ALLOWED_ORIGINS` にもこのサービスのURLを追加すること(§4.5 参照)。忘れると
チャット送信がCORSで全滅する。

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

## 4.5 チャットボット CORS の追従 (2026-08-08 Stage 1 で新規追加、codex review で発覚)

`mockup/index.html`(このサービスの `/` が配信するトップページ)には既に
チャットボットウィジェットが埋め込み済み(PR #97)。ウィジェットは別サービス
`aozora-chatbot` へ `fetch` するため、`aozora-chatbot` 側の `ALLOWED_ORIGINS`
にこのサービスの origin を追加しないと、ブラウザの CORS で全チャット送信が
失敗する(サイレント失敗 — チャット欄自体は表示されるが送信すると無反応)。

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync gcloud run services update aozora-chatbot \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --update-env-vars=ALLOWED_ORIGINS="https://yasushihonda-acg.github.io,http://localhost:8989,http://localhost:8080,https://aozora-sync-flry56mxwa-an.a.run.app,https://aozora-sync-1084369586348.asia-northeast1.run.app"
```

**Stage 5 でドメインを `recruit.aozora-cg.com` に切り替えたら、この値にも
最終ドメインを追加すること**(`PUBLIC_BASE_URL` の更新と同時に対応)。

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

# 5d. トップページ (2026-08-08 Stage 1 追加、Firestore 不要)
curl -s -o /dev/null -w "%{http_code}\n" "${SERVICE_URL}/"
# → 200

# 5e. 静的アセット (同上)
curl -s -o /dev/null -w "%{http_code}\n" "${SERVICE_URL}/assets/css/tokens.css"
# → 200
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

`sync-run` (`python -m sync sync-run`、`sync/src/sync/cli.py`) が6時間ごとに
実行するバッチ本体 (2026-08-08: 日次から変更、`docs/specs/sync-strategy.md` §3
の自己申告済み頻度「6h or 12h」およびジョブカン宛照会文面の「6時間に1回程度」
と整合させたもの)。§4 の FastAPI proxy サービスとは**別プロセス** (Cloud Run
Job) — プロキシは求人ページの動的配信、Job はクロール→Firestore 書込みのみを
行う。

Terraform モジュール化はしない (2026-06-18 の過剰設計巻き戻し方針、
`.claude/memory/feedback_overengineering_recovery_2026-06-18.md` 参照)。`gcloud`
コマンドを直接実行する。

### 8.1 サービスアカウント作成 (初回のみ)

```bash
gcloud iam service-accounts create aozora-sync-job \
  --project=aozora-wp-jobcan-sync \
  --display-name="aozora-sync Cloud Run Job (6h periodic crawl)"

# Firestore 読み書き
gcloud projects add-iam-policy-binding aozora-wp-jobcan-sync \
  --member="serviceAccount:aozora-sync-job@aozora-wp-jobcan-sync.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Secret Manager (ops-webhook-url) 読み取り — §1.5 で作成済みのシークレットに対して
gcloud secrets add-iam-policy-binding ops-webhook-url \
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
- `max-retries=0`: 失敗時に自動リトライしない — 6時間後の次回 Cloud Scheduler
  実行が実質的な再試行になるため、同一実行枠内の多重実行は避ける
  (2026-08-08: 日次→6時間ごと化に伴い根拠を更新。`task-timeout=3600s` と
  スケジュール間隔 6時間の間には十分な余裕があるため、実行時間が想定
  (約21.4分) を超えて延びても次回実行までに完了する見込み)
- `task-timeout=3600s`: 全17カテゴリ・複数ページを crawl_delay 3秒で巡回する
  実所要時間は、計画段階のPlan agent報告(実ジョブカンへの読み取り専用
  crawl、本田様への事前報告なし)によれば実求人382件・47リストページで
  約21.4分(1,287秒)。**この数値は本セッションで独立に再検証していない**
  (§8.1b の dry-run で決裁者確認のうえ確定させること)。Cloud Run Job の
  課金は実実行時間のみで timeout 上限を上げてもコストは増えないため、
  数値の不確実性を踏まえ安全側に1時間へ設定。既存 FastAPI サービスの
  `timeout=30s` (単一リクエスト想定) とは無関係

新イメージを push した後、Job にも反映するには (Cloud Run Job は Service と違い
自動で最新イメージを追わない):

```bash
gcloud run jobs update aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest
```

### 8.3 Cloud Scheduler — 6時間ごとトリガー (初回のみ、2026-08-08 日次から変更)

ジョブカン側の低負荷時間帯を想定していた JST 深夜 3:00 を起点に保ち、
そこから6時間おき (3:00 / 9:00 / 15:00 / 21:00 JST) に実行する (`cron` は
UTC 基準の Scheduler location 設定に依存するため `--time-zone` を明示)。
リソース名 (`aozora-sync-daily` / `aozora-sync-daily-trigger`) は Cloud Run
Job / Scheduler Job が rename 不可のため歴史的経緯のまま残し、改名しない
(新規作成+旧削除は本番リソースの破棄を伴い、機能上の利点がない):

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
  --schedule="0 3,9,15,21 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://asia-northeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/aozora-wp-jobcan-sync/jobs/aozora-sync-daily:run" \
  --http-method=POST \
  --oauth-service-account-email=aozora-scheduler-invoker@aozora-wp-jobcan-sync.iam.gserviceaccount.com
```

**すでに `aozora-sync-daily-trigger` が存在する環境** (2026-08-07 に日次
`0 3 * * *` で作成済み) では、`create` ではなく `update` で cron 式のみ変更する:

```bash
gcloud scheduler jobs update http aozora-sync-daily-trigger \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --schedule="0 3,9,15,21 * * *" \
  --time-zone="Asia/Tokyo"
```

コード側 (時間ベース closed 判定) が本番イメージに反映された**後**に実行する
こと — 先に間隔だけ上げると、旧「実行回数ベース」ロジックのまま 6 時間ごとの
不在が誤って早期 closed 化されるリスクがある。

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

## 9. CSV 取得経路 (ATS 自動化、CSV移行フォローアップ、2026-08-11)

`docs/handoff/GOAL.md` の CSV 移行検討を受け、HTML 解析 (`sync-run`、§8) と
並行して ATS 管理画面 (`ats.jobcan.jp`) の CSV エクスポートを Playwright で
自動取得する経路 (`sync-run-csv-live`、`sync/src/sync/jobcan_ats.py` +
`csv_ingest.py`) を追加する。**HTML 経路は削除しない** — `--args` の
書き換えだけでいつでも元に戻せることが、この節の設計全体の前提。

事前に済んでいること: `jobcan-sync@aozora-cg.com` アカウントへの
「求人の登録・編集：全て登録・編集可」権限付与 (`ats.jobcan.jp/configs/
authority_configs`、2026-08-10 決裁者承認済み — CSV ダウンロードの一括操作に
必要、閲覧専用のままだと行チェックボックスが描画されない)、
`jobcan-sync-password` シークレット登録 (§1.6)、実機での `ats-download`
2 回実行での再現性確認と `csv-diff` によるFirestore実データとの突合 (この
CLI セッションで完了、382 件完全一致・主要フィールド差分ゼロ)。

### 9.1 Artifact Registry — 別リポジトリを新設する理由

`cleanup-policy.json` は **最新 2 バージョンのみ保持**。既存の `aozora-sync`
リポジトリに Job 用イメージも push すると、Service 用 push と Job 用 push が
互いのバージョンを退避させ合い、ロールバックに必要な旧イメージが消える
リスクがある。Job 専用の別リポジトリを切る:

```bash
gcloud artifacts repositories create aozora-sync-job \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --repository-format=docker \
  --description="aozora-sync Cloud Run Job images (CSV 取得経路、Playwright 同梱)"

gcloud artifacts repositories set-cleanup-policies aozora-sync-job \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --policy=infra/cleanup-policy.json \
  --dry-run

gcloud artifacts repositories set-cleanup-policies aozora-sync-job \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1 \
  --policy=infra/cleanup-policy.json \
  --no-dry-run
```

### 9.2 Docker image build + push

`sync/Dockerfile.job` は `sync/Dockerfile` (配信用 FastAPI イメージ) とは別物
— Chromium を同梱するため `mcr.microsoft.com/playwright/python` ベース
(~1.6-2GB、配信用イメージは Chromium 非同梱のまま変更なし)。build context は
`sync/Dockerfile` と同じくリポジトリルート:

```bash
CLOUDSDK_ACTIVE_CONFIG_NAME=aozora-wp-jobcan-sync \
docker buildx build --platform linux/amd64 --push \
  -f sync/Dockerfile.job \
  -t asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync-job/aozora-sync-job:latest .
```

### 9.3 Cloud Run Job 更新

既存の `aozora-sync-job` サービスアカウント・`jobcan-sync-password` の
secretAccessor 権限は使い回す (§1.6, §8.1 で付与済み)。**メモリ/CPU を
引き上げる** — Chromium のヘッドレス実行は既存の 512Mi では不足する:

```bash
gcloud run jobs update aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync-job/aozora-sync-job:latest \
  --command=python \
  --args="-m,sync,sync-run-csv-live" \
  --memory=2Gi \
  --cpu=2 \
  --set-env-vars=REVIEW_BYPASS=true
```

`aozora-sync-daily` / `aozora-sync-daily-trigger` の名前・6 時間ごとの
Cloud Scheduler 設定 (§8.3) は変更しない — 同じ Job リソースのイメージと
起動コマンドだけを差し替える形にすることで、ロールバックを 1 コマンドに
留める。

### 9.4 ロールバック

HTML 経路(§8)へ即座に戻す — 削除していないので `--image`/`--args` の
書き換えだけで完結する:

```bash
gcloud run jobs update aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1 \
  --image=asia-northeast1-docker.pkg.dev/aozora-wp-jobcan-sync/aozora-sync/aozora-sync:latest \
  --command=python \
  --args="-m,sync,sync-run" \
  --memory=512Mi \
  --cpu=1
```

**注意 (2026-08-12)**: HTML 経路 (`crawler.crawl_all`) はカード上のラベル並び順が保証されない
(例: 夜勤専従の求人が `["介護職", "夜勤専従（介護・看護）", ...]` の順で来ることがある)。
`selectors.yaml` の `thumbnail_categories` は「document 順で最初に synonym マッチしたバケット」
を採用する (`parser._resolve_display_thumbnail`) ため、CSV 経路 (`csv_ingest.py` はカテゴリ列を
`labels[0]` に固定配置) では起きない曖昧性がロールバック後に再発しうる — 夜勤専従・施設長・
訪問看護の求人が意図した専用イラストではなく `care`/`nurse` の汎用イラストに割り当てられる
可能性がある。ロールバック後は該当3 category_id (`18987`/`18988`/`18989`) の表示を実機確認すること。

### 9.5 手動検証コマンド (本番切替前、Cloud Run 実行前にローカルで実施済み)

```bash
# ダウンロードのみ(Firestore書き込みなし)、ファイルを目視確認
cd sync && uv sync --extra ats && uv run playwright install chromium
uv run python -m sync ats-download --out-dir /tmp/ats

# Firestore実データとの差分確認(書き込みなし)
uv run python -m sync csv-diff --csv-file /tmp/ats/page_1.csv --csv-file /tmp/ats/page_2.csv \
  --csv-file /tmp/ats/page_3.csv --csv-file /tmp/ats/page_4.csv
```

### 9.6 動作確認 (§8.4 と同様)

```bash
gcloud scheduler jobs run aozora-sync-daily-trigger \
  --project=aozora-wp-jobcan-sync \
  --location=asia-northeast1

gcloud run jobs executions list \
  --job=aozora-sync-daily \
  --project=aozora-wp-jobcan-sync \
  --region=asia-northeast1

gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="aozora-sync-daily"' \
  --project=aozora-wp-jobcan-sync \
  --limit=50 \
  --format=json
```

完了条件: ログに `added=0 changed=382 unchanged=0 removed=0 newly_closed=0
ats_errors=0 crawl_errors=0 written=True`(初回切替時は`content_hash`が
HTML経路と異なるため全件changed扱い、想定内)。`/jobs/` が382件表示、
詳細ページの抜き取り確認、Firestore上のドキュメントが`source="csv"`。

## B-8 初回ロールアウト順序 (この順を守る)

Phase B のインフラは 2026-08-07 時点で何も存在しない状態から作る (§1 冒頭の
注記参照)。番号は本ドキュメントの節番号:

1. §3 でコードをビルド・push
2. §1 (API有効化) → §1a (Firestore DB作成) → §1.5 (Secret作成) → §4a (Web用 SA + IAM) → §8.1 (Job用 SA + IAM) を実行
3. §8.1b でクローラを実ジョブカンに対して dry-run 検証 (Firestore 書き込みなし)
4. §8.2 で Cloud Run Job を `REVIEW_BYPASS=true` で作成し、§8.4 の手動トリガーで **1回実行** → Firestore に全求人が `active` で入る
5. `python -m sync` 相当で Firestore の中身を確認してから §4 で Service をデプロイ (この時点で初めて配信が Firestore 由来になる)
6. §8.3 で Cloud Scheduler を作成し、以降は6時間ごとの自動運用

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
