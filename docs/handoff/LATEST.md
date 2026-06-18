# Handoff — 2026-06-18 深夜 (Phase 2A.2 完了 + Phase 2B シンプル化セッション)

## TL;DR

本日 **3 PR (PR #21/#22/#23) を main 統合**。Phase 2A.2 (FastAPI + cachetools + Dockerfile + 構造化ログ + code-review fix) 完遂 + jobs 系ページに「採用トップへ戻る」UI 追加。さらに **Phase 2B 計画の過剰設計を本田様の指摘で全巻き戻し**、ロードマップを「gcloud run deploy + custom domain + AR cleanup」の **1 段階 (月額 ~3 円)** にシンプル化。次セッションは **本田様の deploy 指示があれば Phase 2B 即着手可能**、または Phase 2A.3 (code-review cleanup) を着手可能。

🔗 決裁者向け公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/

## 今セッションで完了した変更 (3 PR)

| PR | 内容 | コミット |
|---|---|---|
| #21 | jobs 系ページに「採用トップへ戻る」UI 追加 (テンプレ + CSS + 5 ページ再生成) | `438c272` |
| #22 | Phase 2A.2 — FastAPI proxy + cachetools.TTLCache + Dockerfile + code-review fix (Codex 反映 4 件 + Pydantic/render exception catch 追加、pytest 116 件全 PASS) | `f9608a2` |
| #23 | Phase 2B 過剰設計の巻き戻し + シンプル化 (CLAUDE.md 規約照会前提撤回 + 教訓 memory) | `773cdfe` |

## 重要な学習教訓 (本セッションの最大の収穫)

**Phase 2B 計画で「3 分割 + IAM 認証 + Cloud Armor + WAF + Terraform + WIF + GitHub Actions + Memorystore + uptime check」を積み上げて、本田様に「シンプルにジョブカン HTML 取得 + 自社カスタム表示するだけでは? 過剰設計では?」と指摘され全巻き戻し**。

### 根本原因

1. `docs/specs/sync-strategy.md` 初期記述の「Codex 指摘 Q2: 案 D は許諾が取れない場合に成立しない」条件を、**自社契約 SaaS の自社利用** にも機械的に適用
2. Codex セカンドオピニオン取得時の質問に「allUsers public 脅威モデル」「ID 総当たり攻撃」を前提として盛り込み → Codex の回答も保守的に偏り → 過剰指摘を機械反映する悪循環
3. 規模フィルタ ([[feedback-project-scope-filter]]) と ROI 評価 ([[feedback-cost-benefit-before-action]]) を実践できなかった

### 記録した教訓 memory

- **グローバル** `~/.claude/memory/feedback_codex_question_threat_model_bias.md` 新規: 第三者レビュー質問の前提バイアス
- **グローバル** `~/.claude/memory/feedback_saas_self_use_no_clearance.md` 新規: SaaS 自社利用は標準ユースケース、規約照会 trigger 不要
- **プロジェクト** `.claude/memory/feedback_overengineering_recovery_2026-06-18.md` 新規: 本事例の経緯と再発防止
- グローバル MEMORY.md に index 追加

## 簡素化後のロードマップ

```
[完了] Phase 2A.1 + 2A.2 (アプリ層 + Dockerfile、Cloud Run ready)
   ↓
[Phase 2A.3 任意] code-review #3-#8 cleanup (任意、次セッション着手可能)
   ↓
[Phase 2B] (本田様の deploy 指示で即着手、月額 ~3 円):
  1. gcloud artifacts repositories create + cleanup-policy.json
  2. docker build + gcloud run deploy
  3. gcloud run domain-mappings create で recruit.aozora-cg.com 直結
  4. JOBCAN_FETCH_ENABLED=true、public、認証なし、textPayload ログ
  5. Cloud Billing alert $5 設定
  ─── 完了 ───
```

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし**。Phase 2A.3 と Phase 2B のどちらも本田様の明示指示後に着手するため、構造的に「即着手」配置可能なものはゼロ。

### 条件待ち (明示 trigger 付き、2 件)

| # | 項目 | A/B/C | trigger | 充足時のタスク |
|---|------|-------|---------|--------------|
| 1 | **#60 Phase 2A.3 (code-review #3-#8 cleanup)** | B 修正 | 本田様 → 「Phase 2A.3 着手」明示指示 | (1) get_job_detail/list の共通化 (2) _is_valid_id 共通ヘルパー化 (3) _ERROR_HTML_TEMPLATE を Jinja2 テンプレ化 (4) JobcanClient 長寿命化 (5) JobcanClient 例外に status_code 属性 (6) InMemoryCache get/set 集約。pytest 全 PASS + ruff/pyright clean を維持して PR |
| 2 | **#31 Phase 2B (gcloud run deploy + custom domain + AR cleanup)** | C | 本田様 → 「Phase 2B deploy 開始」明示指示 | (1) Artifact Registry repo 作成 + cleanup policy (gcp.md MUST) (2) docker build + push (3) gcloud run deploy (asia-northeast1, min 0 / max 1, 512Mi, JOBCAN_FETCH_ENABLED=true, public) (4) gcloud run domain-mappings で recruit.aozora-cg.com 直結 (5) DNS A レコード設定 (6) HTTPS 動作確認 (7) Playwright で本番 URL 視認 (8) Cloud Billing alert $5 設定。想定工数 30-60 分、月額 ~$0.02 |

### 却下候補 (記録のみ、4 件)

| # | 項目 | A/B/C | 着手しない理由 |
|---|------|-------|--------------|
| 1 | Phase 2B-0 (Cloud Run fixture deploy + IAM 認証) | C unclear | 2026-06-18 過剰設計と判定、廃止 |
| 2 | Phase 2B-1 (controlled live egress + Cloud Armor + allowlist) | C unclear | 同上、廃止 |
| 3 | Terraform / WIF / GitHub Actions auto-deploy | A | 採用サイト規模では過剰、`gcloud run deploy` 手動で十分 |
| 4 | Memorystore (Redis) / Cloud Monitoring uptime check / Cloud Armor | C unclear | トラフィック実績ベースで Phase 2B 完了後に再評価、現時点では不要 |

## Issue Net 変化

- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件

GitHub Issues は未使用 (本プロジェクトは Issues での tracking なし)。

## 環境状態

- Git: clean、main = `773cdfe`、リモート同期済
- 残留プロセス: なし
- Pages: build success (sha=`773cdfe`)
- pytest: 116 件全 PASS (Phase 2A.2 完了時点)
- ruff / pyright: clean

## 最終結論

🛑 **executor 領分の作業ゼロ、セッション終了推奨**

- OPEN PR: 0 件
- OPEN Issue: 0 件
- 即着手タスク: 0 件 (Phase 2A.3 / Phase 2B どちらも decision-maker 明示指示が trigger)
- 条件待ち: 2 件 (Phase 2A.3 / Phase 2B)、いずれも本田様の領分
- 却下候補: 4 件 (過剰設計巻き戻し済)
- 残留プロセス: なし
- Git clean / リモート同期済 / 包括指示「優先順にすすめて」では動けない構造

根拠: [[feedback_idle_session_skip_housekeeping]] (真の executor タスクゼロ + 条件待ち trigger 未充足 = housekeeping を能動提案せず終了)
