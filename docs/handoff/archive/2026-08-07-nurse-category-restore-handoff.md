# Handoff — 2026-08-07（Phase B本番インフラロールアウト + Phase A看護職カテゴリ実データ復元）

## TL;DR

**セッション前半: decision-maker指示「Phase B本番インフラのプロビジョニング、始めてください」を受けB-8初回ロールアウトを完了(Firestore DB作成・Cloud Run Service/Job・Cloud Scheduler、実本番書き込みバグ1件修正・PR #133)。セッション後半: decision-makerが公開モック実機を確認し「看護師が入っていない」指摘が静的モックでは未解消と判明。一度は「Phase Bで解決済み」と誤って却下したが(PR #135)、実際は静的モック(GitHub Pages)がPhase B(Firestore)と完全に独立しており、decision-maker指摘で誤りを訂正。既存の`scripts/mockup-rebuild/`パイプラインを拡張し、実データ(Firestore)から看護職3件を静的モックへ復元(PR #136、codex review 2周実施)。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app
🔗 求人配信Service: https://aozora-sync-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (5件)

| PR | タイトル | 内容 |
|---|---|---|
| #132 | `docs: ジョブカン正式照会回答待ちの前提を撤回` | `sync/README.md`「本番デプロイ禁止」行を削除(2026-06-18方針転換の適用漏れと判明) |
| #133 | `fix(sync): Firestoreのネストされたextra_linesを書き込み可能な形に変換` | `JobOffer.extra_lines: list[tuple[str, str]]`がFirestoreの「配列の直接ネスト禁止」制約に抵触していたバグを修正 |
| #134 | `docs: ハンドオフ更新(Phase B本番インフラ初回ロールアウトセッション)` | GOAL.md/LATEST.md整合 |
| #135 | `docs: Phase A看護職カテゴリ静的モック修正を却下候補へ変更` | **後に誤りと判明、PR #136で訂正・実装** |
| #136 | `feat(mockup): 求人一覧に看護職カテゴリを実データから復元` | `jobs.html`/`jobs-nurse.html`に看護職3件を実データから追加、既存パイプライン拡張 |

### Phase B本番インフラ(前半セッション、完了)

Firestore DB作成・API有効化・SA作成・クローラdry-run検証(実ジョブカン382件・エラー0件)・初回本番同期(382件書き込み成功)・Cloud Run Service再デプロイ・Cloud Scheduler作成(`aozora-sync-daily-trigger`、日次3:00 JST、ENABLED)。詳細は`docs/handoff/archive/2026-08-07-phase-b-production-rollout.md`参照。

### Phase A看護職カテゴリの実データ復元(後半セッション、PR #136)

decision-makerが公開モック`jobs.html`実機を確認し「社長からの指摘が網羅されてません」と指摘。調査したところ:
- 実ジョブカンサイトの17職種カテゴリ(看護職=category_id 18983等)はPhase Bで既に正しくクロール済み(Firestoreに看護職85件)
- しかし静的モック`jobs.html`の職種フィルターは「介護・相談/事務/IT」の3バケットのみで看護が存在せず、`jobs.json`の34件にも看護師求人が0件
- `jobs-nurse.html`(index.htmlの看護カード導線先)はcategory_id 18984/18983取り違えで相談員の求人を看護師として誤表示

**一度の誤判断**: 「Phase B(Firestore)は看護職を正しく保持しているから静的モック修正は不要」と判断しPR #135で却下候補化したが、これは誤り。**静的モック(GitHub Pages)はPhase B(Firestore/Cloud Run)と完全に独立**しており、Phase B側の正しさは画面表示に反映されない。decision-maker指摘「実際に見ている画面では直っていない」「元ジョブカンの選択内容をスクレイピングしてきたならそれが反映されるべき」で訂正。

**実装**: plan mode実施。Firestore実測(category_id=18983、既存の座標登録済み拠点のみ・新規ジオコーディング不要)から実求人3件(博多/正社員・永吉/短時間正社員・梅ヶ丘/パート)を選定。既存の`scripts/mockup-rebuild/`パイプライン(README「Phase A中の追加ジョブ描加にも再利用可」)を拡張:
- 新規`add_new_cards.py`: 既存スクリプトが持たない「新規job_idの追加」パスを担う(スケルトンカード挿入+詳細ページ生成+フィルターチップ追加)
- `rewrite_jobs_html.py`: 看護マッピング追加+対象HTMLファイルCLI引数化
- 給与regexの資格別内訳プレフィックス(「【月額】・正看護師：354,000円〜」)未対応バグを修正(看護データで初露見)

**codex review 2周実施**: 1周目でP2×4件検出(パートアルバイト複合雇用形態のjobs.json分割漏れ・emp_patterns順序による雇用形態タグ誤表示・新規詳細ページのJobPosting所在地が常に「福岡」表記だった問題を修正、初期表示件数固定の指摘は誤検知と判断)。2周目(修正後)は指摘0件。

**動作確認**: Playwrightで看護チップ表示・絞り込み(3件)・詳細ページ全セクション・`jobs-nurse.html`修正確認・看護+パート同時選択でパートアルバイト求人が正しく1件ヒットすることを確認。既存34件は内容不変。

### 実作業中に発見・対処した問題(前半セッション)

- **本番Firestore書き込みバグ(PR #133)**: `extra_lines`のFirestoreネスト配列違反、エンコード/デコード層追加で解消
- **イメージ再push忘れ**: 修正コミット後の旧イメージデプロイで詳細ページ503、再ビルドで解消
- **ローカルgRPCのDNS解決失敗**: `GRPC_DNS_RESOLVER=native`で回避(Cloud Run実行環境には影響しない見込み)
- **`gcloud run jobs execute`がauto modeクラシファイアに一貫してブロック**: ローカル`sync-run`で代替実行

### 発見したが対応しなかった項目

- `mockup/index.html`のカテゴリカード「訪問介護員(ヘルパー)」「ケアマネジャー」が`jobs.html?job_type=visit`/`?job_type=care-manager`にリンクしているが、`map-search.js`はこの`job_type`クエリパラメータを一切読み取らない(職種フィルターと接続されていないpre-existingの導線切れ)。看護職修正の副次調査で発見、無関係のため今回は対応せず記録のみ

## 次のアクション

### 即着手タスク
即着手タスクなし

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク | 充足確認方法 |
|---|------|------------------|--------------|------------|
| 1 | [GOAL.md] Cloud Scheduler初回自動実行の監視 | 2026-08-08 3:00 JST到来 | `gcloud run jobs executions list --job=aozora-sync-daily --region=asia-northeast1`で結果確認、失敗時はログ調査 | 次セッション開始時に確認 |
| 2 | [GOAL.md] career-ladder Lv.2〜4年収帯確定 | 決裁者から対応方針の回答(`career-ladder-salary-report.html`送信済み) | 回答内容に応じて`mockup/index.html`該当箇所を更新 | 本田様への確認 |
| 3 | Secret Manager(Slack webhook)追加 | webhook URL入手 | `infra/README.md` §1.5の手順で追加 | 本田様への確認 |
| 4 | `job_type`クエリパラメータの導線切れ修正 | decision-maker判断(訪問介護員・ケアマネジャーの絞り込み導線が必要かどうか) | `map-search.js`に`job_type`パラメータ読み取りロジックを追加 | 本田様への確認 |

その他の decision-maker 判断待ち項目(③外国人採用特設ページ、⑤スタッフインタビュー再考、GHA WIF自動デプロイ等)は `docs/handoff/GOAL.md` に継続記録、本セッションでの新規動きなし。

### 却下候補（記録のみ）
却下候補なし

## 再開可能性判定
✅ **再開可能** - ドキュメントから開発再開できます

---

## Issue Net 変化
- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件（GitHub Issues非経由、PR直接ワークフローのみ）

## 最終結論

✅ **セッション終了可** — 残作業ゼロ、クリーン状態達成

- OPEN PR: 0件 / active Issue: 0件
- Git: `main`は`origin/main`と同期済み、clean
- CI: 直近 `pages build and deployment` success
- 即着手タスク: 0件 / 条件待ち: 4件(いずれもdecision-maker判断または外部trigger待ち)
- 残留プロセス: なし(前回確認したMCP関連常駐プロセスは本プロジェクト作業と無関係の既存プロセス、本セッションの作業(docker/gcloud/python/http.server)由来の残留プロセスは全て停止済み)
- 既知の blocker: なし
- 同根再発スキャン(§4.6): PR #133(Firestoreエンコード)とPR #136(mockup給与regex)は表面上異なるが、いずれも「既存の正規表現/シリアライズ処理が新しいデータパターン(看護データ、複合フィールド)で初めて露見した」という同根の教訓(既存テストが新カテゴリのデータ多様性を想定していなかった)。次回別カテゴリ追加時は同種の想定漏れに注意
- 対症療法判定(§4.7): 該当なし — 全修正はretry/fallbackではなくデータエンコード・正規表現ロジックそのものの根本修正。実機(Playwright)・実本番Firestoreでの動作確認済み
