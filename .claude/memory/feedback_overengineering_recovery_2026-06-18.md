---
name: feedback-overengineering-recovery-2026-06-18
description: ACG プロジェクトで Phase 2B (本番デプロイ) を 3 分割 + WAF + IAM 認証 + WIF + Terraform 構成として過剰設計したが、本田様の指摘で「シンプルに gcloud run deploy + custom domain」へ全巻き戻し。学習教訓
metadata:
  type: feedback
---

2026-06-18 セッション、Phase 2B 計画で以下の過剰設計を積み上げた:

- Phase 2B-0 (fixture deploy + IAM 認証 + noindex)
- Phase 2B-1 (controlled live egress + Cloud Armor)
- Phase 2B-2 (本番ドメイン切替 + LB + Memorystore + uptime check)
- Terraform 4 module + WIF + GitHub Actions auto-deploy
- 計画 Codex セカンドオピニオン取得 + 修正 7 項目反映

本田様の指摘で「自社契約ジョブカンの自社情報を自社採用サイトに表示するのは普通の利用」「過剰設計だった」と判明、Phase 2B-0/2B-1 を delete、Task #31 を「gcloud run deploy + custom domain + AR cleanup」のシンプル 1 段階に書き換え (月額 ~3 円見込)。

**Why:** Phase 0 の `docs/specs/sync-strategy.md` で「Codex 指摘 Q2: 案 D は許諾が取れない場合に成立しない」と書いた条件を、自社利用にも機械的に適用してしまった。さらに Codex に「allUsers public 脅威モデル」「ID 総当たり攻撃」を質問の前提として盛り込んだため、回答も保守的に偏り (Cloud Armor / IAM 認証推奨)、それを「妥当」と評価して計画反映する悪循環が発生。CLAUDE.md MEMORY の [[feedback-project-scope-filter]] (規模フィルタ) と [[feedback-cost-benefit-before-action]] (ROI を WBS 段階で問う) を実践できていなかった。

**How to apply:**
1. ACG プロジェクトでは「ジョブカン契約者 = 本田様」が自社採用情報を自社サイトに表示する案件であり、規約照会 trigger は不要 ([[feedback-saas-self-use-no-clearance]])
2. Phase 2B 着手判断は本田様の deploy 指示のみが trigger、規約回答待ちは廃止
3. インフラ構成は **Cloud Run + Artifact Registry cleanup + custom domain mapping** の最小 3 要素のみ。Terraform / WIF / WAF / LB / Memorystore は不要 (採用サイト規模)
4. 想定月額: Cloud Run 無料枠内 + AR ~$0.01 + Egress ~$0.006 = **約 $0.02 (3 円)**
5. 将来本セッションを参照した別 AI が同じ過剰設計を提案した場合、本メモを引用して「2026-06-18 に同じ提案を全巻き戻ししている」事実を示せる

**関連:**
- グローバル: [[feedback-codex-question-threat-model-bias]] (Codex 質問設計の前提バイアス)
- グローバル: [[feedback-saas-self-use-no-clearance]] (SaaS 自社利用は規約照会不要)
- 本リポジトリ: `CLAUDE.md` の「同期方式の優先順位」セクション (規約照会 trigger の元記述を更新する必要あり)
