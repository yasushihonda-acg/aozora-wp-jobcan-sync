# aozora-chatbot — 採用サイト FAQ チャットボット (Vertex AI Gemini)

`mockup/` の採用サイトモックに埋め込むチャットウィジェットのバックエンド。求人情報の
FAQ にのみ回答するスコープで、Vertex AI Gemini + Cloud Run で構成する。`sync/`（ジョブカン
プロキシ）とは別concernの独立サービス（デプロイ・スケーリング・障害を分離するため）。

## モデル / エンドポイント（要 ground truth 再確認）

**2026-07-24 実測**: `gemini-3.5-flash-lite` は asia-northeast1 リージョナルエンドポイント
で HTTP 404（パブリッシャーモデル未登録）、global エンドポイントで HTTP 200。本サービスは
求人 FAQ のみを扱い個人情報スコープ外のため、データレジデンシー要件を理由に
`VERTEX_LOCATION=global` を既定値としている（`src/chatbot/config.py`）。

Gemini モデルの GA 状況・リージョン可用性は変わりやすい。モデル切り替えや新しい GCP
プロジェクトへの展開時は、思い込みで進めず `scripts/probe_model.py` で再確認すること。

```bash
gcloud auth application-default login
GCP_PROJECT=aozora-wp-jobcan-sync uv run python scripts/probe_model.py
```

## 知識ベースの鮮度（2026-08-09 sync連携・定期リフレッシュへ移行）

`src/chatbot/knowledge/faq.yaml` はコンテナイメージに同梱される（RAG なし、更新頻度が
ほぼゼロなためフェッチ対象に含めない）。**求人データには同梱ファイルが一切存在しない**
（旧 `jobs_detail.json` + `scripts/build_jobs_detail.py` の手動更新パイプラインは
2026-08-09 に完全削除 — Phase A の静的37件から更新が止まっていた本番不具合の根治）。
求人データは唯一 `sync`（ジョブカンプロキシ、Cloud Run + Firestore、6時間ごと自動同期）
の `GET /jobs/chatbot-knowledge.json`（`DEFAULT_JOBS_DETAIL_URL`）から取得する
（`knowledge.fetch_knowledge`）。取得は2段構え:

1. **起動時**: `app.py` の lifespan startup で1回（`_refresh_knowledge`）
2. **定期**: 起動後は `KNOWLEDGE_REFRESH_INTERVAL_SECONDS`（既定 3600 秒 = 1 時間）ごとに
   asyncio バックグラウンドタスクで再取得し続ける（`_periodic_refresh`、常時起動中の
   インスタンスが `sync` の 6 時間サイクルを取りこぼさないため）。lifespan shutdown で
   タスクは cancel される

取得に成功すればそれを採用し、ネットワークエラー・タイムアウト・404・不正 JSON・
スキーマ不一致・空配列のいずれでも**直前まで保持していた知識ベースを維持してアプリは
稼働を継続する**（起動直後の初回取得が失敗した場合のみ、後述の FAQ オンリー状態になる）。
`/health` の `knowledge.source` が `"fetched"` / `"bundled"` のどちらだったかを返す。

**`bundled_knowledge()` は FAQ のみ**: 求人データの同梱フォールバックは存在しないため、
`sync` 側が一度も取得に成功していない cold start 直後は求人 0 件（`job_count: 0`）で
起動する。この状態のシステムプロンプトは「求人情報を取得できていません」と明記し、
Gemini に求人推薦を行わせない（`knowledge._render_context` の空データ分岐）。

**反映フロー**: `sync` 側の6時間ごと自動同期がそのまま知識ベースの更新になる。人手の
作業（スクリプト実行・`git push`・再デプロイ）は一切不要。

**反映タイミング**: 最悪ケースで「`sync`側の同期完了」+「chatbot側の次回定期リフレッシュ
（最大 `KNOWLEDGE_REFRESH_INTERVAL_SECONDS`）」の合計遅延。即時反映が必要な場合は
`gcloud run services update aozora-chatbot --update-env-vars` 等でインスタンスを
再起動させれば、次の起動時取得ですぐ反映される。

**キルスイッチ**: `JOBS_DETAIL_URL=`（空文字）で起動時・定期リフレッシュの両方を無効化
できる（`gcloud run services update aozora-chatbot --update-env-vars JOBS_DETAIL_URL=`）。
`KNOWLEDGE_REFRESH_INTERVAL_SECONDS=0` は定期リフレッシュのみ無効化（起動時取得は残る）。
ローカル開発でオフラインにしたい場合も前者を使う。

**信頼境界**: 取得した JSON は Gemini の system prompt に直接埋め込まれ、`resolve_jobs`
のホワイトリストにもなるため、`knowledge.parse_jobs_detail` で構造検証する（pydantic、
`chatbot/tests/test_knowledge.py` / `test_startup_refresh.py` / `test_periodic_refresh.py`
参照）。特に `url` フィールドは取得値を採用せず `id` から `jobs/{id}`（`sync` の正規
求人詳細ルート）を再計算する — `chat-widget.js` が `job.url` をそのまま `<a href>` に
使うため、取得元 JSON を信頼境界の外として扱う。

## レスポンス形式（構造化出力、2026-07-24 拡張）

`POST /chat` は Gemini の構造化出力（`response_mime_type=application/json` +
`response_schema=GeminiReply`）を使い、1回の呼び出しで回答本文に加えて質問サジェストと
関連求人IDを生成する。求人IDは `knowledge.resolve_jobs()` で `jobs_detail.json` の
既知IDとのホワイトリスト照合を経てから返す（モデルが存在しないIDを挙げても弾かれる）。

```json
{
  "reply": "夜勤のないお仕事もございます。デイサービスや訪問介護、事務系の求人でお探しいただけます。",
  "blocked": false,
  "suggestions": ["未経験でも応募できますか？", "選考にはどれくらいかかりますか？"],
  "jobs": [
    {
      "id": "2264205",
      "title": "※2026年8月OPEN※福岡【パート】日勤・介護スタッフ（四箇／デイ・有料）",
      "url": "jobs/2264205.html",
      "category": "care",
      "employment": ["パート"],
      "facility": "あおぞらケアグループ四箇（デイ・有料）",
      "city": "福岡市早良区"
    }
  ]
}
```

`reply` は `**太字**` と `- ` 箇条書きのみを許可した軽量Markdown（`mockup/assets/js/chat-widget.js`
の `renderRichText` が DOM 生成でレンダリングする、innerHTML 不使用）。`suggestions` /
`jobs` は0件のこともある。

## ローカル開発

```bash
cd chatbot
uv sync
gcloud auth application-default login   # ADC、キーレス
GCP_PROJECT=aozora-wp-jobcan-sync VERTEX_LOCATION=global MODEL_ID=gemini-3.5-flash-lite \
ALLOWED_ORIGINS=http://localhost:8989 \
uv run uvicorn chatbot.app:app --reload --port 8000

curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message":"未経験でも応募できますか？"}'
```

## テスト

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

すべて Vertex AI 非依存（`create_app(generate_fn=...)` で fake 注入、`sync/tests/test_app.py`
の `client_factory` DI パターンを踏襲）。知識ベースの起動時リフレッシュも同様に
`create_app(http_transport=...)` へ `httpx.MockTransport` を注入してオフラインでテストする
（`sync/` は `respx` を使うが、単発 GET 1 本のテストでは httpx 同梱の `MockTransport` で
十分なため追加依存を避けた）。

## デプロイ（Phase A: 手動、2026-07-24 デプロイ済み）

`infra/README.md`（`sync/` 用）と同じ GCP プロジェクト・リージョンを使うが、サービス名・
サービスアカウントは分離。

- **Service URL**: `https://aozora-chatbot-1084369586348.asia-northeast1.run.app`
- ランタイム SA `chatbot-run@aozora-wp-jobcan-sync.iam.gserviceaccount.com` に
  `roles/aiplatform.user` のみ（最小権限）
- `gcloud run deploy aozora-chatbot --source .`（Apple Silicon の arm64/amd64 問題を
  Cloud Build 側ビルドで回避）
- `--allow-unauthenticated` 必須（CORS preflight の `OPTIONS` が IAM 層で弾かれるとブラウザ
  から到達できない）
- `MODEL_ID` / `VERTEX_LOCATION` / `ALLOWED_ORIGINS` は env 変数で注入、コード変更不要
- `JOBS_DETAIL_URL`（既定値あり、空文字で知識ベースの起動時リフレッシュを無効化）/
  `KNOWLEDGE_FETCH_TIMEOUT_SECONDS`（既定 `3.0`）も同様に env 変数で注入可能
- Artifact Registry の自動生成リポジトリ `cloud-run-source-deploy` に cleanup policy
  （最新2件保持、`infra/cleanup-policy.json`）適用済み

**既知の落とし穴**: `Dockerfile` の `RUN --mount=type=cache,...`（BuildKit機能）は
`gcloud run deploy --source` が使う Cloud Build のデフォルト docker ビルダー
（`gcr.io/cloud-builders/docker`）では非対応（"the --mount option requires BuildKit"で
ビルド失敗、2026-07-24実測）。`sync/Dockerfile` はローカル `docker buildx build`
（常にBuildKit）でビルド後 push する運用のため問題にならないが、`chatbot/` は
`--source` 前提のため `--mount=type=cache` を使わない形に変更済み（純粋なビルド速度の
トレードオフ、機能的な差はなし）。

## 既知の制約

- レート制限（`src/chatbot/ratelimit.py`）はインスタンス単位の in-memory カウンタ。コスト
  暴走の粗いブレーキであり、真の防御ではない（`--max-instances` が実質的な上限）
- 応答はストリーミングでなく一括（Phase A のシンプル化判断、follow-up で SSE 化を検討）
