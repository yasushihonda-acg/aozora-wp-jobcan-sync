# Handoff — 2026-07-24 (採用FAQチャットボット: 実装〜2回のcode-review〜Cloud Runデプロイ〜本番確認)

## TL;DR

**採用コンサルフィードバック④「採用チャットボット」に対応。決裁者が方式(GCP自前構築=Vertex AI Gemini + Cloud Run、求人FAQのみスコープ、APIキー発行なしのキーレス認証)を確定し、plan modeでフル計画→承認→実装まで一気通貫で進めた。`chatbot/`に独立FastAPIバックエンドを新設、`gemini-3.5-flash-lite`(ground truth実測でVERTEX_LOCATION=globalを確定)を使用。`/code-review high`を2ラウンド実施し、1回目で認証迂回・データ流出・到達不能コード等10件、2回目で残存3件を検出・修正、以降重大指摘0件に収束。決裁者の明示指示でCloud Runへ実デプロイ(`aozora-chatbot`)、デプロイ中にDockerfileのBuildKit機能非対応を発見・修正。GitHub Pages本番実機でPlaywrightにより送受信を確認。計2PR(#89 feat, #90 fix)マージ+今回のdocsハンドオフPR。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (2件)

| PR | タイトル | 内容 |
|---|---|---|
| #89 | `feat(chatbot): 採用FAQチャットボットを追加(Vertex AI Gemini + Cloud Run)` | `chatbot/`新設(FastAPI、`sync/`のDIパターン踏襲)。Vertex AI Gemini呼び出し・CORS・per-IPレート制限・入力長制限・スコープ外2層ガードを実装。フロントは`chat-widget.js`/`.css`を新規作成し`index.html`/`jobs.html`に埋め込み(`map-search.js`と同じ末尾script+DOM自己注入パターン)。ローカル結合テスト(pytest 23件+Playwright実機)確認後にPR作成、`/code-review high`で10件検出・全修正: X-Forwarded-For先頭→末尾修正(rate limit迂回対策)/ローカル用query paramをlocalhost限定化(データ流出対策)/`str(Enum)`比較のdead code修正(finish_reason判定)/generate_content呼び出しにtimeout+retry追加/`history[-0:]`バグ修正/history配列長上限追加/レート制限hitsリスト無制限増大の修正/モバイルUI重なり修正/genai.Client未close修正。再レビューで残存3件(MAX_TOKENS切れ未処理・CSS一律オフセット・定数重複)を追加検出・修正、以降0件に収束。回帰テスト8件追加、最終pytest 34件全PASS |
| #90 | `fix(chatbot): Cloud Runへのデプロイと本番エンドポイント配線` | デプロイ実行時、`Dockerfile`の`RUN --mount=type=cache`(BuildKit機能)が`gcloud run deploy --source`の既定dockerビルダー(`gcr.io/cloud-builders/docker`)で非対応と判明(ビルド失敗で実測)、除去して解消。`index.html`/`jobs.html`のscriptタグへ実際のCloud Run URLを`data-endpoint`属性で配線。`/code-review low 90`で指摘0件を確認しマージ |

### モデル/エンドポイント確定(ground truth実測、コード着手前に実施)
過去にGeminiモデルのGA/可用性を未検証で断定した再発事例を踏まえ、実装着手前にVertex AI Gemini APIへ直接curl疎通:
- `gemini-3.5-flash-lite` を asia-northeast1 リージョナルエンドポイントで試行 → **HTTP 404**(パブリッシャーモデル未登録)
- 同モデルを global エンドポイントで試行 → **HTTP 200**(`trafficType:ON_DEMAND`)
- → `MODEL_ID=gemini-3.5-flash-lite` / `VERTEX_LOCATION=global` を確定。実測結果は `~/.claude/memory/reference_vertex_ai_to_gemini_enterprise_2026.md` にも追記し今後のプロジェクトで再利用可能にした

### アーキテクチャ概要
- **バックエンド** `chatbot/`: FastAPI、`google-genai` SDK(`genai.Client(vertexai=True, ...)`)、ADCベースのキーレス認証(APIキー不要)。知識ベース(FAQ5件+求人34件サマリー)はコンテナイメージに同梱、RAGなしのシンプル設計(Phase Aの小規模データに対する意図的な判断)
- **フロント** `mockup/assets/js/chat-widget.js` + `.css`: 右下フローティングボタン→パネル、`index.html`/`jobs.html`の2ページのみに限定embed
- **デプロイ**: `gcloud run deploy aozora-chatbot --source .`(Apple Siliconのarm64/amd64問題をCloud Build側ビルドで回避)、ランタイムSA `chatbot-run` は `roles/aiplatform.user` のみの最小権限、`--allow-unauthenticated`(CORS preflightのOPTIONS到達に必須)、Artifact Registry自動生成リポジトリに cleanup policy(最新2件保持)適用済み

### code-review 2ラウンドの経緯(重大指摘→0件への収束)
1回目`/code-review high`実行中、検証用サブエージェントが誤ってファイルを直接編集する事象が発生。スキル自身が`git status`/`git diff`で検知し`git checkout --`で自動復元、その後同じ10件の指摘を報告(セルフチェック機構が正しく機能した実例)。修正を再適用し2回目`/code-review high`を実行、残存3件(重大度は低い: MAX_TOKENS切れの応答が「完全な回答」として表示される・CSS一律オフセットの誤爆・フロント/バックエンド定数の重複)を検出・修正。3回目相当のデプロイ後PR(#90)では`/code-review low 90`で指摘0件。

### 決裁者への確認ポイント(すべて明示合意済み)
| タイミング | 確認内容 | 決定 |
|---|---|---|
| 着手前 | 実現方式・スコープ・認証方式 | GCP自前構築・求人FAQのみ・キーレス認証 |
| Phase A範囲 | UIのみ先行 or 実バックエンドまで一気に構築 | UI+実バックエンドを今回構築 |
| デプロイ実行前 | 公開unauthエンドポイント新設・課金発生の最終確認 | 実行承認、その後デプロイ完了 |
| PR #89/#90マージ前 | 番号単位の明示認可 | 両方承認 |

### 本番実機確認(Playwright)
GitHub Pages本番URL(`https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/`)上で、index.html/jobs.html双方のウィジェット開閉を確認。index.htmlでは実際に「見学だけでも可能ですか？」を送信し、Vertex AI Geminiが FAQ 根拠の正しい回答("はい、面接前の現場見学も可能です...")を返すことをエンドツーエンドで確認。

## 次のアクション

### 即着手タスク
即着手タスクなし

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク |
|---|------|------------------|--------------|
| 1 | ③ 外国人採用特設ページ | decision-makerが法務/人事部門確認の上で着手指示 | 内容仕様のヒアリング→plan mode |
| 2 | ⑤ スタッフインタビュー再考 | decision-makerが2026-07-14廃止決定の再考について指示 | 復活する場合、イニシャル+AI生成画像の仕様を軽量プランで提示 |
| 3 | チャットボットの全ページ展開(`jobs-care/nurse/office/it.html`等) | decision-makerから展開指示 | `chat-widget.js`のscriptタグ追加のみ(バックエンド変更不要) |
| 4 | 知識ベース自動追従化 | 鮮度の問題が実運用で顕在化した場合 | 起動時に`jobs.json`をfetchするTTLキャッシュ方式へ変更検討 |
| 5 | GHA WIF自動デプロイ化 | 手動デプロイの頻度が増え自動化ROIが見合うと判断された場合 | `.github/workflows/deploy-chatbot.yml`新設、既存`github-pool`再利用・新SA`github-chatbot-deployer`分離 |
| 6 | `google.maps.Marker`→`AdvancedMarkerElement`移行 | decision-makerから移行指示、またはレガシーMarkerの将来的な廃止アナウンス | Map ID発行+Cloud Console側スタイル設定を追加した上で移行 |

### 却下候補（記録のみ）
却下候補なし

## 再開可能性判定
✅ **再開可能** - ドキュメントから開発再開できます

---

## 最終結論

✅ **セッション終了可** — 残作業ゼロ、クリーン状態達成

- OPEN PR: 0件 / active Issue: 0件
- Git: clean(本ハンドオフPRマージ後)
- 即着手タスク: 0件 / 条件待ち: 6件（すべてdecision-maker判断待ち）
- 残留プロセス: なし（現在のプロジェクトに限る。マシン全体では別プロジェクト`houkan-minamikaze`のNodeプロセス1件を検出、現セッションと無関係のため停止提案は見送り）
- 既知の blocker: なし
- 同根再発スキャン(§4.6): 候補0件（過去7日archiveに同キーワードなし）
- 対症療法判定(§4.7): 該当なし（BuildKit問題はビルドログの直接調査による根本原因修正、本番E2E検証済み）
