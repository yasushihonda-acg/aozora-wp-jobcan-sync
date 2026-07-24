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

## 知識ベースの鮮度（既知のトレードオフ）

`src/chatbot/knowledge/faq.yaml` / `jobs_summary.json` / `jobs_detail.json` はコンテナ
イメージに同梱され、起動時に一度だけ読み込まれる（RAG なし、外部フェッチなし — Phase A の
求人 34 件・FAQ 5 件という小規模データに対する意図的なシンプル設計）。

**`mockup/index.html` の `#faq` や `mockup/assets/data/jobs.json` / `mockup/jobs.html` を
更新しても、このチャットボットの回答には自動反映されない。** 知識ベースを更新したら
`uv run python scripts/build_jobs_detail.py` で `jobs_detail.json` を再生成し（`jobs_summary.json`
は引き続き手動更新）、再デプロイすること。将来的に鮮度が問題になった場合は、起動時に
GitHub Pages の `jobs.json` を fetch する設計への切り替えを検討（follow-up、未実装）。

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
の `client_factory` DI パターンを踏襲）。

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
- 全ページ展開はせず `index.html` / `jobs.html` の2ページのみ（follow-up）
