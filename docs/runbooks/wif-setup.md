# Workload Identity Federation (WIF) セットアップ

`.github/workflows/setup-maps-api.yml` が参照する `secrets.WIF_PROVIDER` / `secrets.DEPLOY_SA` / `secrets.GCP_PROJECT` の設定内容と手順。`aozora-sns-auto` の同名runbookと同一パターン(1リポジトリ=1pool、SA Keyレス)。

## なぜ WIF か / 前提条件

`aozora-sns-auto/docs/runbooks/wif-setup.md` と同じ理由(キーレス・監査証跡)。本プロジェクト固有の前提:

- GCP プロジェクト ID: `aozora-wp-jobcan-sync` (project number `1084369586348`)
- GitHub リポジトリ: `yasushihonda-acg/aozora-wp-jobcan-sync`(**public** repo)
- 用途: Google Maps JavaScript API の有効化 + referrer制限付きAPIキー発行のみ(デプロイ用途ではない)

## セットアップ済みの内容(2026-07-24 実施)

### SA と権限(最小権限、Maps API管理に限定)

```
SA: github-maps-admin@aozora-wp-jobcan-sync.iam.gserviceaccount.com
roles:
  - roles/serviceusage.serviceUsageAdmin   (API有効化)
  - roles/serviceusage.apiKeysAdmin        (APIキー作成・管理)
```

`aozora-sns-auto` の `github-deployer` (Cloud Run/Artifact Registry権限) とは別用途のため権限を分離。同じSAを使い回さない。

### WIF プール・プロバイダ

```
POOL:     projects/1084369586348/locations/global/workloadIdentityPools/github-pool
PROVIDER: projects/1084369586348/locations/global/workloadIdentityPools/github-pool/providers/github-provider
attribute-condition: assertion.repository=='yasushihonda-acg/aozora-wp-jobcan-sync'
```

`attribute-condition` は本リポジトリに厳密限定(他リポジトリからのimpersonateは不可)。

### GitHub Secrets(登録済み)

| Secret 名 | 値 |
|---|---|
| `WIF_PROVIDER` | `projects/1084369586348/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `DEPLOY_SA` | `github-maps-admin@aozora-wp-jobcan-sync.iam.gserviceaccount.com` |
| `GCP_PROJECT` | `aozora-wp-jobcan-sync` |

## 再現手順(別環境で再構築する場合)

`aozora-sns-auto/docs/runbooks/wif-setup.md` の §1.1〜1.6 と同一の gcloud コマンド群。SA名を `github-maps-admin`、付与ロールを上記2件に読み替え、`GITHUB_ORG=yasushihonda-acg` / `GITHUB_REPO=aozora-wp-jobcan-sync` を使用。

## 検証

```bash
gh workflow run "Setup Maps API" --repo yasushihonda-acg/aozora-wp-jobcan-sync
```

成功すると Job Summary に Maps JavaScript API キーの値が出力される(referrer制限済みのクライアントキーのため、そのまま `mockup/jobs.html` に埋め込んで使用する。Secret化は不要)。

## 撤回(緊急時)

```bash
PROJECT_ID=aozora-wp-jobcan-sync
SA_EMAIL="github-maps-admin@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_ID="projects/1084369586348/locations/global/workloadIdentityPools/github-pool"

# SAからWIF bindingを削除(最速の遮断手段)
gcloud iam service-accounts remove-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/yasushihonda-acg/aozora-wp-jobcan-sync"

# 発行済みAPIキーを無効化する場合
gcloud services api-keys list --project="$PROJECT_ID" --filter="displayName=jobs-map-embed"
gcloud services api-keys delete <KEY_ID> --project="$PROJECT_ID"
```

## 参考

- `aozora-sns-auto/docs/runbooks/wif-setup.md`(同一パターンの元ネタ)
- [google-github-actions/auth](https://github.com/google-github-actions/auth)
- [Workload Identity Federation 公式ドキュメント](https://cloud.google.com/iam/docs/workload-identity-federation)
