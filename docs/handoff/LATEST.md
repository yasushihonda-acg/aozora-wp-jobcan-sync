# Handoff — 2026-07-26 (スクロールreveal演出の全面改修、PR #106〜#109)

## TL;DR

**トップページのスクロール演出について決裁者から4回のフィードバックを受け、同日中に4PRで段階的に改善。①段差(stagger)演出が主要ブラウザで完全に無効化されていたバグ+変化量拡大(PR #106) ②「数字で見る」セクションが`overflow: hidden`のせいで固まっていたバグ(PR #107) ③スクロール連動scrub方式(`animation-timeline: view()`)を、決裁者要望「途中で止まらず動ききってほしい」に応えるため個別カード監視+時間ベースtransition方式へ全面刷新(PR #108、`/codex review-diff`でJS障害時フォールバック漏れのP1バグも検出・同PR内で修正) ④easing/durationをより「じわっとゆったり」した質感へ調整(PR #109)。すべてPlaywright実機検証・番号単位認可を経てマージ済み、本番反映確認済み。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🔗 チャットボットAPI: https://aozora-chatbot-1084369586348.asia-northeast1.run.app

## 今セッションで完了したこと

### マージ済 PR (4件)

| PR | タイトル | 内容 |
|---|---|---|
| #106 | `fix(mockup): スクロール時のセクション演出をより明確に体感できる強度へ強化` | `transition: none`が`transition-delay`を無効化していたstaggerバグ修正+移動量/スケール変化拡大 (1 files, +44/-3) |
| #107 | `fix(mockup): 数字セクションのスクロールアニメーションが完全に固まる実害バグを修正` | `.section--band`の`overflow: hidden`が子要素`.stat`の`animation-timeline: view()`を破壊するバグ修正 (1 files, +5/-1) |
| #108 | `fix(mockup): スクロール演出をscroll-scrub方式から確実に動ききる方式へ変更` | `animation-timeline: view()`を撤去、カード個別IntersectionObserver監視+時間ベースtransitionへ全面刷新。`/codex review-diff`のP1指摘(onerrorフォールバック漏れ)も同PR内で修正 (3 files, +73/-148) |
| #109 | `fix(mockup): スクロールreveal演出をよりゆったり・じわっとした質感へ調整` | easing(ease-out-expo→ease-out-cubic)+duration(550ms→1100ms)+stagger間隔(70ms→130ms)を調整 (1 files, +14/-8) |

### 実装内容（時系列）

- **PR #106（着手前の調査）**: 本番サイトをPlaywrightで実測し、①Chrome/Edge/Safari等`animation-timeline: view()`対応ブラウザでは`@supports`ブロックの`transition: none`が同じ行の`transition-delay`(70ms刻み)を巻き添えで無効化し、同一行の複数カードが完全に同時出現していた ②変化量(translateY 40-56px, scale 0.92-0.96)が小さくスクロール距離540-780pxかけて非常にゆるやかに変化するため「動いた」実感が薄い、の2点を特定。段差は`animation-range`をnth-childごとにずらす方式で修正、変化量は拡大(translateY 64-90px, scale 0.82-0.88)
- **PR #107（決裁者スクリーンショット報告を受けて）**: 「数字で見る、あおぞら」セクションの実測で、`.stat`要素のopacityがスクロールしても固定値(0.83/0.66/0.48/0.30)のまま一切追従しないことを発見。`overflow: hidden`を持つ祖先要素があると`animation-timeline: view()`の進捗計算がその要素基準に壊れることを`overflow: visible`へ一時変更した実験で確認。`.section--band`の`overflow: hidden`は`::before`(inset:0で自己完結)のクリップに不要だったため削除
- **PR #108（「モッサリ」「動ききってほしい」フィードバックへの対応）**:
  - `animation-timeline: view()`はスクロール位置に直結するscrub方式のため、仕組み上「スクロールを止めると演出も途中で止まる」ことが判明
  - 加えて表示トリガーが親`[data-reveal]`セクション単位だったため、丈の高いセクションではセクション先頭が視界に入った瞬間に配下カード全部が「表示済み」判定され、実際にカードが画面に現れる頃にはアニメーションが完了して見える構造的バグも発見
  - `animation-timeline: view()`関連コードを全撤去し、site.jsでカード単体(`.career-ladder__step`等6種)を個別にIntersectionObserver監視(rootMargin `-5%`→`-15%`で視認しやすいタイミングに遅延)、時間ベースのCSS transitionで確実に完了する方式に統一
  - **`/codex review-diff`(Bash版、`--base main`、effort=high)でP1指摘1件**: 「`site.js`読み込み失敗時の`onerror`フォールバックが`[data-reveal]`親要素のみを対象としており、新しく独立させたカードセレクタが対象外のため、JS障害時にホームページの主要コンテンツが非表示のまま固まる」
  - 実装(`mockup/index.html:428`)を確認し指摘が正確であることを検証、フォールバックのセレクタをsite.js側と一致させて同PR内で修正、Playwright実機検証(site.js読み込みを意図的に失敗させ全28要素が正しく表示されることを確認)
- **PR #109（「いいですね、速度が速すぎる」フィードバックへの対応）**: PR #108のトリガー方式(特定位置で一気に動く)自体は決裁者から評価されたため維持。動きの質感のみを調整: 初速が非常に速いease-out-expo系カーブ(0.16,1,0.3,1)を初速の穏やかなease-out-cubic系(0.33,1,0.68,1)へ、duration 550ms→1100ms(約2倍)、段差70ms→130ms刻みへ比例調整。Playwright実機検証でopacity推移が0.17→0.39→0.56→0.70→0.85→0.94→1.00となだらかに収束することを確認

各PRとも、`prefers-reduced-motion: reduce`・モバイル幅(375px)の回帰確認をPlaywrightで実施。ローカルdevサーバーでの検証時、ブラウザHTTPキャッシュが古いCSS/JSを返す問題に複数回遭遇したため、`page.route()`によるキャッシュ完全回避(fetchしてno-storeヘッダー付きでfulfill)を確立し以降の検証はこの方式で統一した。

### その他（git非管理、ephemeral）

セッション冒頭、`/catchup`が提示した5件の条件待ちタスクを可視化するHTMLレポートをローカルscratchpadに生成(アコーディオンUI + 進捗報告コピー機能付き)。プロジェクトの内部下書きのためArtifact公開はせずローカルブラウザ表示に留めた。git管理外・恒久化なし。

### 決裁者への確認ポイント（すべて明示合意済み）

| タイミング | 確認内容 | 決定 |
|---|---|---|
| PR #106 | 番号単位の明示認可 | マージする(推奨)を選択・承認 |
| PR #107 | 番号単位の明示認可 | マージする(推奨)を選択・承認 |
| PR #108 | `/codex review-diff`実行の明示指示 | Bash版・`--base main`・effort=highで実行 |
| PR #108 | 番号単位の明示認可(Codex指摘修正後) | マージする(推奨)を選択・承認 |
| PR #109 | 番号単位の明示認可 | マージする(推奨)を選択・承認 |

## 次のアクション

### 即着手タスク
即着手タスクなし

### 条件待ち（明示 trigger 付き）

| # | 項目 | trigger（充足条件） | 充足時のタスク |
|---|------|------------------|--------------|
| 1 | [GOAL.md] ③ 外国人採用特設ページ | decision-makerが法務/人事部門確認の上で着手指示 | 内容仕様のヒアリング→plan mode |
| 2 | [GOAL.md] ⑤ スタッフインタビュー再考 | decision-makerが2026-07-14廃止決定の再考について指示 | 復活する場合、イニシャル+AI生成画像の仕様を軽量プランで提示 |
| 3 | GHA WIF自動デプロイ化 | 手動デプロイ頻度増でROIが見合う、またはgcloud認証切れの手間が続くと判断された場合(decision-maker負担ゼロのため急ぐ理由なし) | `.github/workflows/deploy-chatbot.yml`新設（スコープ大のためplan mode必須） |
| 4 | `google.maps.Marker`→`AdvancedMarkerElement`移行 | decision-makerから移行指示、またはレガシーMarkerの将来的な廃止アナウンス | Map ID発行+Cloud Console側スタイル設定を追加した上で移行 |
| 5 | チャットボット応答ストリーミング(SSE化) | UXの体感速度改善が優先度として上がった場合 | Gemini側のstreaming API対応状況を再確認した上でplan mode |
| 6 | スクロール演出への追加フィードバック | 決裁者がPR #109反映後の本番を確認し、追加の速度/強度調整指示があった場合 | 該当パラメータ(duration/easing/stagger間隔)を軽量プランで調整 |

### 却下候補（記録のみ）
却下候補なし

## 再開可能性判定
✅ **再開可能** - ドキュメントから開発再開できます

---

## Issue Net 変化
- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件（本セッションはIssue非経由の直接タスクのみ）

## 最終結論

✅ **セッション終了可** — 残作業ゼロ、クリーン状態達成

- OPEN PR: 0件 / active Issue: 0件
- Git: clean、main、リモートと同期済み(headSha `144dcf1`)
- 即着手タスク: 0件 / 条件待ち: 6件（すべてdecision-maker判断待ちまたは実運用トリガー待ち。今セッションでは既存5件のtrigger充足なし、スクロール演出への追加フィードバック待ちを新規に1件追加）
- 残留プロセス: なし（検証用ローカルサーバーはPlaywright確認後に都度停止済み）。※`cleanup-node.sh`が検出した`sanwa-houkai-app`(port 3007)は別プロジェクトの並行セッション由来と推測されるプロセスで、本プロジェクトのスコープ外(マシン全体チェックのため検出、停止提案は保留)
- 既知の blocker: なし
- 同根再発スキャン(§4.6): 本セッションの4PRはすべて同一機能領域(トップページのスクロールreveal演出、`mockup/assets/css/components.css`)を対象としており、機械的な「同根候補」基準(共有ファイルを複数PRが参照)には該当する。ただし各PRは実測で個別に検証された異なる根本原因(stagger無効化バグ/overflow:hidden破壊/scroll-scrub方式の構造的限界/主観的な質感調整)を持ち、決裁者の実機フィードバックを都度受けて反映する正当な反復チューニングプロセスであり、「原因不明のまま同じ不具合が再発している」パターンではないと判断。なお過去7日のarchive(2026-07-15)にも同じ機能領域の反復調整(PR #67〜#70)が記録されており、このスクロール演出機能は複数セッションにまたがり継続的な質感調整を要する領域であることが伺える(次回フィードバックが来ても異常ではない)
- 対症療法判定(§4.7): 該当なし — 4PRいずれも実測(Playwright computed style測定、`overflow`切替実験等)による構造的根本原因の特定を経ての修正であり、retry/timeout/fallback等の症状遮断ではない。PR #108では`/codex review-diff`による独立したセカンドオピニオンも実施し、指摘を実装ファイルで直接検証した上で反映しており単体テストのみの楽観判定でもない
