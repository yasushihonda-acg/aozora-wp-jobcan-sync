# Handoff — 2026-08-09（Phase B Stage 3 求人一覧デザインパリティ）

## TL;DR

**decision-maker指示「Stage 3を進めて」を受け、スコープを「検索/地図/GPSも含めてフルパリティ」に確定してplan mode実装。Phase Aの`mockup/jobs.html`が持つ条件検索(職種/雇用形態/エリアチップ+フリーワード)+ Google Maps地図 + GPS距離順並べ替えをPhase B(Cloud Run+Firestore全382件)へ移植。実装過程で拠点ジオコーディングが13拠点しかなく実際は27拠点必要と判明し追加ジオコーディング、codex review 2回 + pr-review-toolkit 3エージェント並列で実害バグ2件・サイレント失敗3件を検出・修正し、本番デプロイまで完了(PR #148)。**

🔗 公開モック(Phase A、37件サンプル、Stage 5まで並行稼働): https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 Phase B検証URL(382件全件、まだ`recruit.aozora-cg.com`未接続): https://aozora-sync-flry56mxwa-an.a.run.app/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (1件) + 本番デプロイ

| PR | タイトル | 内容 |
|---|---|---|
| #148 | `feat(sync): Phase B Stage 3 — 求人一覧ページのデザインパリティ` | 検索/地図/GPS込みフルパリティ実装。16 files, +1361/-55。codex review×2 + pr-review-toolkit 3エージェント並列 |
| — | 本番デプロイ実行 | `aozora-sync`リビジョン`aozora-sync-00007-42c`(トラフィック100%)。Playwright実機確認済み |

### 実装内容(承認済みplanに基づく)

- `sync/src/sync/facility_geo.py`(新規): 拠点名→緯度経度の対応表。13拠点(既存)+14拠点(新規ジオコーディング)= 27拠点
- `sync/src/sync/list_sections.py`(新規): 職種ラベル→カテゴリ4色マッピング(17種類全職種対応)、カード用ビューモデル`JobListCardView`
- `sync/src/sync/search_index.py`(新規): Firestore全件から検索/地図用JSON(`GET /jobs/search-index.json`)を構築する純粋関数
- `sync/src/sync/app.py`: `/jobs/`の`category_id`を任意化(無指定=全件検索ページ)、新規ルートを`/jobs/{job_id}`より前に登録(ルーティング衝突回避)
- `sync/src/sync/cache.py`: `get_json`/`set_json`をTTLキャッシュに追加
- `sync/src/sync/renderer.py`/`templates/job_list.html`: カテゴリ色分け+meta-grid、検索パネル+地図UI追加。CLIの`list`サブコマンド等既存呼び出し元との後方互換性を維持(`cards_by_job_id`によるオーバーレイ方式)
- `mockup/assets/js/map-search.js`: `data-jobs-endpoint`属性でPhase A/B間のデータソースを切替
- Google Maps APIキーのリファラー制限にCloud Run originを追加

### 発覚した想定外の事実(このセッションの核心)

Phase Aの地図拠点データ(`FACILITY_COORDS`)は13拠点のみだったが、Firestore全382件を突合すると**実在拠点は28箇所**(うち27箇所は単一住所を持ち地図ピン可能、1箇所「共同生活援助」は12事業所を横断する求人のため単一住所なし)。decision-maker確認の上、社内の「事業所マスタ」Googleスプレッドシート(Playwright MCPでアクセス、CSVエクスポートで取得)から14拠点分の正確な住所を特定し、国土地理院APIで新規ジオコーディングした。

### 品質ゲートで発見・修正した実害バグ

**codex review(2回、指摘計2件)**:
- 雇用形態ラベルの抽出が`labels[1:]`(先頭が必ずカテゴリという前提)でラベル順序に依存していた → `LABEL_TO_CATEGORY`に含まれないラベルを抽出する順序非依存の方式に修正
- Phase A(`mockup/jobs.html`)側に検索読み込み失敗通知の対象要素が無く、Phase B側にのみ追加していたため片方でサイレント失敗が再現 → 両方に同じ要素を追加

**pr-review-toolkit(3エージェント並列、実害バグ2件+サイレント失敗3件)**:
- `facility_key()`が括弧より前の地名だけでキー生成していたため、「博多(デイ・有料)」と新規追加「博多(訪問介護/訪問看護・居宅)」(別住所)が同一キーに衝突し地図ピン・件数が誤ってマージされる実害バグ → 括弧内も含めてキー化、一意性テスト追加
- 地図ピン表示名が生の郵便住所になっていた(Phase Aは施設表示名) → 修正
- `map-search.js`のfetch失敗catchが完全無音だった(Phase Aの静的JSONと違いPhase Bの動的エンドポイントは実際に失敗しうる) → console.error追加+画面上フォールバック通知を追加
- 未知の施設住所/職種ラベルによるサイレント縮退(地図ピンなし/色分けなし)を検知不能 → `build_search_index`の戻り値をtupleにしwarningsとして集約ログ出力

型設計改善提案(戻り値のpydanticモデル化、`Literal`型導入等)は実害なしのため今回は見送り(判断の記録のみ)。

## 次のアクション

### 即着手タスク
即着手タスクなし(Stage 4着手はdecision-maker判断待ち、下記条件待ち参照)

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク | 充足確認方法 |
|---|------|------------------|--------------|------------|
| 1 | [GOAL.md] Stage 4着手(本番公開前の健全性対応) | decision-makerの「進めて」等の明示指示 | スコープ未確定、着手前にplan modeで個別計画 | 次セッション冒頭で本田様へ確認 |
| 2 | [GOAL.md] Secret Manager(Slack webhook)追加 | webhook URL入手 | `infra/README.md` §1.5の手順で追加 | 本田様への確認 |
| 3 | [GOAL.md] career-ladder Lv.2〜4年収帯確定 | 決裁者から対応方針の回答 | `mockup/index.html`該当箇所を更新 | 本田様への確認 |

その他の decision-maker 判断待ち項目(③外国人採用特設ページ、⑤スタッフインタビュー再考、GHA WIF自動デプロイ、Stage 5等)は `docs/handoff/GOAL.md` に継続記録、本セッションでの新規動きなし。

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
- 即着手タスク: 0件 / 条件待ち: 3件(いずれもdecision-maker判断または外部trigger待ち)
- 残留プロセス: なし(ローカルuvicorn検証サーバーは都度停止済み)
- 既知の blocker: なし(Phase B検証URLは稼働中、`recruit.aozora-cg.com`未接続のためStage 5まで一般求職者への影響なし)
- 同根再発スキャン(§4.6): `fix:`コミット2件(cd0654a雇用形態ラベル順序依存、1d1c5ef施設キー衝突等)はいずれも同一PR内の品質ゲート指摘への即時対応であり、過去セッションとの同根再発ではない(新規実装コードの初回レビューで発見された問題)
- 対症療法判定(§4.7): 該当なし — 全修正は根本原因(ラベル順序への誤った依存、キー生成ロジックの衝突、無音catchブロック)そのものの修正であり、retry/fallbackではない
