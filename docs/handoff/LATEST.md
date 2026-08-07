# Handoff — 2026-08-07（Phase B 本番インフラ初回ロールアウト）

## TL;DR

**decision-makerから「Phase B本番インフラのプロビジョニング、始めてください」との明示指示を受け、`infra/README.md`「B-8 初回ロールアウト順序」を実行。前提だった「ジョブカン正式照会回答待ち」は本セッション冒頭でdecision-maker指摘により撤回(PR #132、2026-06-18方針転換の適用漏れと判明)。Firestore DB作成・API有効化・サービスアカウント作成・クローラdry-run検証(実ジョブカン382件・エラー0件)・初回本番同期・Cloud Run Service再デプロイ・Cloud Scheduler作成まで完了。本番Firestore書き込み時に実害バグ1件(`extra_lines`のFirestoreネスト配列違反)を発見・修正(PR #133)。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app
🔗 求人配信Service: https://aozora-sync-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (2件)

| PR | タイトル | 内容 |
|---|---|---|
| #132 | `docs: ジョブカン正式照会回答待ちの前提を撤回(2026-06-18方針転換の適用漏れ)` | `sync/README.md`「本番デプロイ禁止」行を削除。GOAL.md/LATEST.md/CLAUDE.md未確定事項の関連記述を訂正 |
| #133 | `fix(sync): Firestoreのネストされたextra_linesを書き込み可能な形に変換` | `JobOffer.extra_lines: list[tuple[str, str]]`がFirestoreの「配列の直接ネスト禁止」制約に抵触していたバグを修正。`firestore_repo.py`にエンコード/デコード層を追加、回帰テスト2件追加 |

### Phase B本番インフラ プロビジョニング(B-8初回ロールアウト順序 1〜6、完了)

| # | 内容 | 結果 |
|---|------|------|
| 1 | Dockerイメージビルド・push | 完了(修正反映後に再ビルド) |
| 2 | API有効化 + Firestore DB作成 + SA作成 | `firestore.googleapis.com`等有効化、DB作成(asia-northeast1, native)、`aozora-sync-web`(datastore.viewer)/`aozora-sync-job`(datastore.user)作成・IAM付与 |
| 3 | クローラdry-run検証(実ジョブカン) | `offers=382 errors=0 expected_total=382 collected_total=382 fully_listed=True` |
| 4 | Cloud Run Job作成+初回実行 | `aozora-sync-daily`作成。実行自体はauto modeクラシファイアにブロックされたためローカル`sync-run`で代替(382件`active`で書き込み成功) |
| 5 | Service再デプロイ+動作確認 | Firestore単一ソース配信に切替、`/jobs/{id}`(200)・`/jobs/?category_id=`(200)・存在しないID(404)を確認 |
| 6 | Cloud Scheduler作成 | `aozora-sync-daily-trigger`、日次3:00 JST、ENABLED |

### 実作業中に発見・対処した問題

- **本番Firestore書き込みバグ(PR #133)**: 初回`sync-run`が`InvalidArgument: 400 Property offer contains an invalid nested entity`で全件失敗。原因は`extra_lines: list[tuple[str,str]]`が`model_dump(mode="python")`でタプルのリストのまま残り、Firestoreの配列ネスト禁止制約に抵触。エンコード/デコード層を追加して解消、実本番Firestoreへの再書き込みで成功確認済み
- **イメージ再push忘れ**: 修正コミット後、旧イメージのままServiceを一度デプロイし詳細ページが503。イメージ再ビルド・再デプロイで解消
- **ローカルgRPCのDNS解決失敗**: `Could not contact DNS servers`(通常のDNS解決は正常、gRPC/c-ares固有の問題、Docker Desktop起動に伴うネットワーク変化が疑われるが未確定)。`GRPC_DNS_RESOLVER=native`で回避。Cloud Run実行環境には影響しない見込み
- **`gcloud run jobs execute`がauto modeクラシファイアに一貫してブロック**: 2回試行しいずれも拒否。ローカル`python -m sync sync-run`で代替実行(decision-maker承認済み)。Cloud Run Job自体の実行経路は2026-08-08 3:00 JSTの初回スケジューラ発火が最初の検証機会

## 次のアクション

### 即着手タスク
即着手タスクなし

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク | 充足確認方法 |
|---|------|------------------|--------------|------------|
| 1 | [GOAL.md] Cloud Scheduler初回自動実行の監視 | 2026-08-08 3:00 JST到来 | `gcloud run jobs executions list --job=aozora-sync-daily --region=asia-northeast1`で結果確認、失敗時はログ調査 | 次セッション開始時に確認 |
| 2 | [GOAL.md] Phase A 看護職カテゴリ不整合の静的モック修正 | 本田様の着手判断(Phase B完了により trigger 充足済み、着手判断自体は待ち) | `mockup/jobs-nurse.html`等のcategory_id誤マッピング(18984↔18983)を修正 | 本田様への確認 |
| 3 | [GOAL.md] career-ladder Lv.2〜4年収帯確定 | 決裁者から対応方針の回答(`career-ladder-salary-report.html`送信済み) | 回答内容に応じて`mockup/index.html`該当箇所を更新 | 本田様への確認 |
| 4 | Secret Manager(Slack webhook)追加 | webhook URL入手 | `infra/README.md` §1.5の手順で追加 | 本田様への確認 |

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

⚠️ **セッション終了前に要対応: 1件** — 本ハンドオフ更新PRのコミット・push・マージ

- OPEN PR: 0件 / active Issue: 0件
- Git: `docs/handoff/GOAL.md`更新分・アーカイブ済み旧LATEST.md・本ファイルが未コミット(本ハンドオフPRで解消予定)、それ以外clean、`main`は`origin/main`と同期済み
- CI: 直近 `pages build and deployment` success
- 即着手タスク: 0件 / 条件待ち: 4件(3件はdecision-maker判断待ち、1件は2026-08-08 3:00 JSTのスケジューラ初回実行待ち)
- 残留プロセス: あり(MCP関連: drawio/context7/codex/playwright-mcp、pyright/TypeScript language server、LM Studio helper)——いずれも本セッション・本プロジェクトの作業とは無関係な既存の常駐プロセスで、Phase Bロールアウト作業(docker buildx/gcloud/python sync-run)の残留プロセスはなし
- 既知の blocker: なし(Phase B本番インフラのプロビジョニングは完了。Cloud Scheduler初回自動実行の結果のみ次セッションで要確認)
- 同根再発スキャン(§4.6): 過去7日のarchiveおよびPRタイトルに「firestore」「nested」「extra_lines」等のキーワードで同根候補なし(0件)。本セッションのfix PR(#133)はB-8初回本番書き込みで初めて露見したバグで、既知の再発ではない
- 対症療法判定(§4.7): 該当なし — 修正はretry/timeout/fallbackではなく、Firestoreのデータエンコード方式そのものを直接修正した根本対応。実本番Firestoreへの書き込み成功で動作確認済み(単体テストのみに依存していない)
