# Handoff — 2026-08-08（mockup反映漏れ修正 + Phase B Stage1 本番デプロイ）

## TL;DR

**社長から「実際のJobcan(382件)より少ない件数(37件)を求人一覧として見せているのはまずいのでは」との指摘。全ページ突合調査で①`jobs-care.html`10件欠落・チャットボット知識ベース3件欠落を発見・修正(PR #141) ②Firestore突合でPhase Aモックが実際は382件中37件(9.7%)のみのサンプル設計だったことが判明。decision-maker判断でPhase B(Cloud Run+Firestore)への本番切替を前倒し、トップページもCloud Runへ全面集約する方針を決定。Stage 1(静的配信基盤+トップページ移植)を実装・4ラウンドの品質ゲートを経て本番デプロイまで完了(PR #142)。**

🔗 公開モック(Phase A、37件サンプル、Stage 5まで並行稼働): https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 Phase B検証URL(382件全件、まだ`recruit.aozora-cg.com`未接続): https://aozora-sync-flry56mxwa-an.a.run.app/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (2件) + 本番デプロイ

| PR | タイトル | 内容 |
|---|---|---|
| #141 | `fix: mockup/chatbotの求人データ反映漏れを修正` | `jobs-care.html`介護カテゴリ20件中10件欠落・チャットボット知識ベース3件欠落を復元。復元スクリプトの根本バグ(相談員求人が未定義CSSクラスに分類)も修正。codex review×2 + セカンドオピニオン×2 |
| #142 | `feat(sync): Phase B本番切替 Stage1 — 静的配信基盤+トップページのCloud Run集約` | `/assets`静的配信+`/`トップページルート追加、canonical/CSSパスの絶対化、`mockup/index.html`リンクのサーバ側書き換え。codex review×3 + セカンドオピニオン×2(4ラウンド) |
| — | 本番デプロイ実行 | `aozora-sync`リビジョン`aozora-sync-00005-mkw`(トラフィック100%)、`aozora-chatbot`のALLOWED_ORIGINS更新。Playwright実機確認済み |

### 発見した構造的事実(このセッションの核心)

Firestore job_cache(Phase B、6時間ごと自動クロール)をground truthとして突合した結果、**現在Jobcan上でactiveな求人は382件**、Phase A静的モックは**37件(約9.7%)**のみを反映するサンプル設計だったことが判明。これはPhase A設計当初(決裁者承認用モック)からの意図的なサンプリングでバグではないが、GitHub Pagesが既に一般公開URLである以上「実際より少ない件数を求人一覧として見せ続けている」というリスクは実在すると判断し、decision-makerがPhase B本番切替の前倒しを決定した。

### 品質ゲートで発見・修正した実害バグ(PR #142、4ラウンド)

- `mockup/index.html`のロゴ・ナビ・フッター自己リンク(`href="index.html"`)が書き換え対象から漏れ404
- チャットボット関連求人カードのリンク(`jobs/{id}.html`形式、相対パス)が新デプロイ先で404 → `/jobs/{id}.html`→`/jobs/{id}`の308リダイレクト追加
- `/assets/*`静的アセットに一律`no-store`が付与されキャッシュ不能、かつ404レスポンスまでキャッシュされる二重バグ
- `check_dir=False`のコメントが「404になる」と主張していたが実際はStarletteの`RuntimeError`(実測確認、コメントと実装が乖離)
- `/`ルートだけがファイル自身の設計原則(同期I/Oは`run_in_threadpool`経由)に従っていなかった
- トップページのcanonicalが`PUBLIC_BASE_URL`に追従せずStage 5時点の最終ドメインをハードコードしたまま

いずれもcodex review(strict-config含む)とセカンドオピニオンエージェント(うち1回は実際にTestClientで挙動を検証する実測ベースのレビューで35分要した)の組み合わせで発見。

## 次のアクション

### 即着手タスク
即着手タスクなし(Stage 2着手はdecision-maker判断待ち、下記条件待ち参照)

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク | 充足確認方法 |
|---|------|------------------|--------------|------------|
| 1 | [GOAL.md] Stage 2着手(求人詳細デザインパリティ) | decision-makerの「進めて」等の明示指示 | `job_detail.html`にsite-header/footer・パンくず・JSON-LD構造化データ・entry-cta・チャットボット埋め込みを追加(`mockup/jobs/*.html`が正本) | 次セッション冒頭で本田様へ確認 |
| 2 | [GOAL.md] Secret Manager(Slack webhook)追加 | webhook URL入手 | `infra/README.md` §1.5の手順で追加 | 本田様への確認 |
| 3 | [GOAL.md] career-ladder Lv.2〜4年収帯確定 | 決裁者から対応方針の回答 | `mockup/index.html`該当箇所を更新 | 本田様への確認 |

その他の decision-maker 判断待ち項目(③外国人採用特設ページ、⑤スタッフインタビュー再考、GHA WIF自動デプロイ、Stage 3〜5等)は `docs/handoff/GOAL.md` に継続記録、本セッションでの新規動きなし。

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
- 即着手タスク: 0件 / 条件待ち: 3件(いずれもdecision-maker判断または外部trigger待ち)
- 残留プロセス: なし
- 既知の blocker: なし(Phase B検証URLは稼働中、`recruit.aozora-cg.com`未接続のためStage 5まで一般求職者への影響なし)
- 同根再発スキャン(§4.6): PR #141(mockup反映漏れ)とPR #142(Phase Bルーティング)は表面上異なるが、いずれも「正本データ/設計原則と実際の出力が静かに乖離していた」という同根の教訓(手動同期パイプラインの取りこぼし・コメントと実装の乖離)。次回Stage 2以降の同種テンプレート移植でも同じ想定漏れパターンに注意
- 対症療法判定(§4.7): 該当なし — 全修正はretry/fallbackではなく根本原因(スクリプトの分類バグ、パス解決ロジック、Starlette実装の誤解)そのものの修正。実機(Playwright)・実本番Cloud Run/Firestoreでの動作確認済み
