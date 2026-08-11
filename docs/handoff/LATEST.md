# Handoff — 2026-08-11（求人カード画像マッピング根本修正 + 同一職種内バリエーション追加）

## TL;DR

**決裁者から「PR #159で直したはずの求人カード画像が、選択した職種タグの意味とまだ合っていない。訪問介護=ホームヘルパーのように意味が近い職種は同じ画像にすべき。また以前は1職種内で複数画像を使い分けていたはずで、それも直してほしい」との指摘。調査の結果、PR #159がカード色分け用の粗い4系統グルーピングをそのまま画像選択にも流用しており、専用生成済みだった`illust-job-visit.png`(訪問介護)・`illust-job-consultant.png`(相談員)が本番マッピングで一度も使われていなかったことが判明。6系統への再分割(PR #165)+ job_id決定的ハッシュによる同一職種内バリエーション機能(PR #166)を実装し、Docker再ビルド・Cloud Run Job更新・手動トリガーまで実施、本番実機で両方とも反映を確認済み。**

🔗 公開モック(Phase A、37件サンプル、Cloud Runへ自動リダイレクト化済み): https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 Phase B本番(382件全件、まだ`recruit.aozora-cg.com`未接続): https://aozora-sync-flry56mxwa-an.a.run.app/
🔗 チャットボットAPI(sync連携済み): https://aozora-chatbot-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (2件)

| PR | タイトル | 内容 |
|---|---|---|
| #165 | `fix(sync): 求人カード画像の職種マッピングを意味の近さで再分割` | `selectors.yaml`の`thumbnail_categories`を4→6系統(care/visit/consultant/nurse/office/it)へ再分割 |
| #166 | `feat(sync): 求人カード画像に同一職種内バリエーションを追加` | `image: str`→`images: list[str]`(プール化)、`sha256(job_id)`による決定的バリエーション選択を追加 |

### PR #165 — 求人カード画像マッピングの根本修正

PR #159(2026-08-10)は17区分のシノニム漏れによる`default_image`大量フォールバックを解消したが、修正時に**カード色分け用の4系統グルーピング(`list_sections.LABEL_TO_CATEGORY`)をそのまま画像選択にも流用**していた。色分けは4系統(介護/看護/事務/IT、専用CSS修飾子が4種のみのため)で正しいが、画像選択は意味の近さで分けるべきで、ホームヘルパー・相談員・ケアマネジャー・サービス提供責任者・サービス管理責任者・世話人・夜勤専従・サポート職・施設長候補の10種類が全て同じ介護シーン画像(`illust-job-care.png`)になっていた。一方で専用イラスト`illust-job-visit.png`(訪問介護員/ヘルパー、SCENE #14)・`illust-job-consultant.png`(相談員/ケアマネジャー、SCENE #2)は既に生成済みだったが本番マッピングで一度も使われていなかった。

6系統(care/visit/consultant/nurse/office/it)へ再分割し、上記2画像を活用。2ファイル・48行の小規模修正のため手動チェックリストレビュー(codex review省略基準内)。実データロードで17タグ全件がマッチ漏れなく解決されることを確認、pytest 532件全PASS。

**本番反映**: PR #159のときは次回自動クロール待ちの方針だったが、今回は決裁者から「いますぐ対応してください」の明示指示を受け、Docker再ビルド(`sync/Dockerfile.job`)→Artifact Registry push→`gcloud run jobs update`(本田様実行、自動モード分類器がブロックしたためAskUserQuestionで承認後に本田様がbash-inputで実行)→Cloud Scheduler手動トリガー→本番実機確認、まで完了。`/jobs/?category_id=18986`(ホームヘルパー)で`illust-job-visit.png`、`/jobs/?category_id=18984`(相談員)で`illust-job-consultant.png`への切り替わりを確認。

### PR #166 — 同一職種内バリエーション機能の追加

決裁者から「以前は1職種内でも求人カードごとに違う画像を使っていたはず」との追加指摘。調査の結果、Phase A(旧静的モック生成スクリプト`scripts/mockup-rebuild/rewrite_jobs_html.py`)には`CATEGORY_VARIANTS`+ラウンドロビンカウンタによる画像分散機構が実在したが、Phase B(Firestore、6時間ごと自動再同期)への移植時に欠落していたと判明。

plan modeで設計: Phase Aのラウンドロビン方式(出現順依存)をそのまま移植すると、求人が1件増減/並び替わるだけで**他の求人の画像まで意図せずシャッフルされる**(今回の指摘の再発になる)ため不採用。代わりに`job_id`の`sha256`ハッシュで決定的に1枚を選ぶ方式(`parser._pick_variant`)を新設 — 同じ求人は常に同じ画像、他の求人の増減で割り当てが変わらないことを保証。Python組み込みの`hash()`はプロセスごとにランダム化されるため使用禁止、という設計上の注意点をdocstring・テストの両方に明記。

`ThumbnailCategoryEntry.image: str`→`images: list[str]`(画像プール化)、care(3枚)/visit(3枚)/consultant(2枚)/office(2枚)を複数画像化。品質ゲート: `codex review --base main -c model_reasoning_effort=high`(指摘0件)+ `pr-review-toolkit`3エージェント並列セカンドオピニオン(code-reviewer/silent-failure-hunter/type-design-analyzer)。type-design-analyzerの改善提案3件中2件(`_pick_variant`の空プールガード、並べ替え契約を検証するテスト)を同PR内で反映、残り1件(既存クラスの`frozen=True`化)はPRスコープ外として見送り理由を明記。

pytest 543件全PASS(新規11件、プロセス間安定性・分布・並べ替え契約等)、ruff/pyright 0件。本番反映後、介護職(53件がcare/-2/-3に分散)・ホームヘルパー(15件)・相談員(36件)いずれも複数画像への分散を実機確認。

## 次のアクション

### 即着手タスク
即着手タスクなし(残り作業はいずれも decision-maker 判断待ち、AI 側の着手対象外)

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク | 充足確認方法 |
|---|------|------------------|--------------|------------|
| 1 | [GOAL.md] Stage 5(ドメイン切替`recruit.aozora-cg.com`) | 本田様がGoogle Search ConsoleでTXTレコード検証を完了 | `gcloud beta run domain-mappings create`実行→CNAME値取得→システム部へ2回目依頼 | 本田様からの報告 |
| 2 | [GOAL.md] Secret Manager(Google Chat webhook `ops-webhook-url`) | webhook URL入手 | `infra/README.md` §1.5の手順で追加 | 本田様への確認 |
| 3 | [GOAL.md/Issue③] 外国人採用特設ページ(特定技能・介護ビザ) | 法務/人事確認 + decision-maker指示 | 内容確定後にplan modeで実装検討 | 本田様への確認 |
| 4 | [GOAL.md/Issue⑤] スタッフインタビュー再考 | decision-makerの再判断(コンサル提案〈イニシャル+AI生成画像〉の採否) | 採用ならplan modeで実装検討 | 本田様への確認 |
| 5 | トンマナ刷新第2フェーズ Stage 3(コンポーネントリデザイン) | decision-makerが本番サイトを見て具体的指摘を出す(進行中のプロセスなし、任意タイミングで開始可能) | 具体的指摘を得て個別plan modeで着手 | 本田様への確認 |

### 却下候補（記録のみ）
今セッション内での新規却下候補なし。

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
- 即着手タスク: 0件 / 条件待ち: 5件(いずれも decision-maker 判断待ち)
- 残留プロセス: なし
- 既知の blocker: なし
- 同根再発スキャン(§4.6): `fix:`PR 1件(#165)を確認。同一テーマ(求人カード画像マッピング)の直前修正PR #159(2026-08-09)がヒット — ただし今回のPR #165は「なぜPR #159の修正が不十分だったか」を明示的に調査・特定(カード色分け用4系統グルーピングを画像選択に流用したことが根本原因)しており、症状の再発ではなく根本原因への到達。追加候補0件
- 対症療法判定(§4.7): 基準3(過去30日以内の同症状修正PR)のみ該当、基準1・2・4は明確に反証(retry/fallback等ではなく設計修正、原因調査ログあり、実データ+本番実機での構造的検証あり)。WebSearch実施(`pydantic thumbnail synonym mapping category fallback bug regression 2026`)も外部要因なし、社内固有の設計課題と確認。対症療法ではないと判断
