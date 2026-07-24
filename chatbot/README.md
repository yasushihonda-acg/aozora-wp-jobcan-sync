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

`src/chatbot/knowledge/faq.yaml` と `jobs_summary.json` はコンテナイメージに同梱され、
起動時に一度だけ読み込まれる（RAG なし、外部フェッチなし — Phase A の求人 34 件・FAQ 5 件
という小規模データに対する意図的なシンプル設計）。

**`mockup/index.html` の `#faq` や `mockup/assets/data/jobs.json` を更新しても、この
チャットボットの回答には自動反映されない。** 知識ベースを更新したら手動でこの2ファイルを
同期し、再デプロイすること。将来的に鮮度が問題になった場合は、起動時に GitHub Pages の
`jobs.json` を fetch する設計への切り替えを検討（follow-up、未実装）。

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

## デプロイ（Phase A: 手動）

`infra/README.md`（`sync/` 用）と同じ GCP プロジェクト・リージョンを使うが、サービス名・
サービスアカウントは分離する。詳細手順は実装計画（`docs/handoff/` または PR 説明）参照。

要点:
- ランタイム SA `chatbot-run@aozora-wp-jobcan-sync.iam.gserviceaccount.com` に
  `roles/aiplatform.user` のみ（最小権限）
- `gcloud run deploy aozora-chatbot --source .`（Apple Silicon の arm64/amd64 問題を
  Cloud Build 側ビルドで回避）
- `--allow-unauthenticated` 必須（CORS preflight の `OPTIONS` が IAM 層で弾かれるとブラウザ
  から到達できない）
- `MODEL_ID` / `VERTEX_LOCATION` / `ALLOWED_ORIGINS` は env 変数で注入、コード変更不要

## 既知の制約

- レート制限（`src/chatbot/ratelimit.py`）はインスタンス単位の in-memory カウンタ。コスト
  暴走の粗いブレーキであり、真の防御ではない（`--max-instances` が実質的な上限）
- 応答はストリーミングでなく一括（Phase A のシンプル化判断、follow-up で SSE 化を検討）
- 全ページ展開はせず `index.html` / `jobs.html` の2ページのみ（follow-up）
