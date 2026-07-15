---
updated: 2026-07-15
---

## 現在のミッション
リクルートページの基礎トンマナ全面刷新 (第2フェーズ)。コーポレートカラー(#00c4cc)をあえて外し、確立済みの江口寿史風イラスト世界観から抽出した配色に統一する。加えてスクロール演出(視差効果)の強化、AI臭さの払拭による洗練度向上を段階的に進める。

## 背景・why
決裁者から「ページ全体をみて今の色合いに変えましょう。コーポレートカラーをあえて外してリクルートページを際立たせます。もっと視差効果というか参考で渡したwebページ(tcy.co.jp/recruit, g-s.dev)のようにスクロール時にアクションやアニメーションが動くような感じにしたほうが良い。全体をもうちょっとAI臭い感じを払拭してより洗練された今のイメージによく合うものにアップデートすべき」との方針転換指示(2026-07-15)。`/impl-plan` フルモードで Stage 1(完了・PR #64)に続き、Stage 2(スクロール演出・視差効果の強化)を計画・承認・実装・本番確認まで完了(2026-07-15、決裁者「すすめて」で明示承認、PR #65)。演出パターンは「ヒーローパララックス＋stagger強化の組合せ」・強度は「控えめ・上品」を決裁者選択。Stage 3 は Stage 1・2 の結果を decision-maker が確認し、具体的な指摘を得てから個別 `/impl-plan` で着手する(現時点で未承認)。

## 完了の定義 (Stage 2: スクロール演出・視差効果の強化) — 2026-07-15 実装完了・PR #65・本番確認済み
- [x] スクロール時、ヒーロー背景がコンテンツより低速で移動する(視差比率 0.2、最大55px)（証明: Playwright `scrollTo(0,300)`/`scrollTo(0,2000)` で背景transform値の変化・上限クランプを確認）
- [x] career-ladder等の複数要素セクションで、各ステップが70ms刻みの遅延差で順次フェードインする（証明: Playwrightで各要素の `transition-delay` 実測。項目数が増えた場合のcatch-all delayも検証）
- [x] `prefers-reduced-motion: reduce` 環境でパララックス・staggerが無効化され、即時全表示される（証明: Playwright `page.emulateMedia({reducedMotion:'reduce'})`）
- [x] site.js読み込み失敗を模したケースで、全 `[data-reveal]` 要素が `is-visible` となり非表示のまま残らない(既存フォールバックの回帰なし、確認済み)
- [x] モバイル幅(375px)でレイアウト崩れ・横スクロールが発生しない（証明: Playwright 375pxフルページスクリーンショット、横スクロール0を確認）
- [x] 本番相当の環境でconsoleエラー0件、体感スクロールジャンクなし(目視確認済み)

## 進行中のtasks (Stage 2) — 全完了
- [x] タスクA: ヒーロー背景パララックス実装 (site.js + components.css)
- [x] タスクB: career-ladder / job categories にstagger遅延強化 (70ms刻み、catch-all含む)
- [x] タスクC: prefers-reduced-motion / JS失敗フォールバックの回帰確認・修正
- [x] タスクD: Playwright実機検証(通常/reduced-motion/JS失敗/複数viewport幅) + `/code-review medium`(2エージェント×2ラウンド)

### 実装メモ (3段階の検証で発見・修正した実害バグ、いずれも実機スクリーンショット/測定で確認)
- **1段目 (実装中の内部code-review)**: 初回実装は `.hero__bg` に `inset:-18%` の固定%拡張で視差余白を確保していたが、`background-size:cover` の基準軸(幅基準/高さ基準)がボックスの縦横比に依存するため、拡張により基準軸が反転し画像が意図せずズームされる実害バグを発見(スカイラインがほぼ見切れる状態)
- **2段目 (同、修正後の再レビュー)**: 固定pxオフセット + `@media (min-width:1200px)` に変更するも、1200-1390px帯(1280px/1366pxなど主要ノートPC解像度を含む)で同じ不具合が再発すると判明。`assets/js/site.js` が実行時に `sky-hero.jpg` の自然サイズと hero の実測寸法を読み込み、余白(60px)を加えても `cover` が幅基準のままであることを確認できた場合のみ視差を有効化する方式に変更(固定ブレークポイント非依存)。sky-hero.jpg は過去に複数回差し替えられており画像アスペクト比依存の実測方式が必須と判断。同時に `will-change` の常時付与→IntersectionObserverでのbind/unbind連動化、`category-card` の項目数超過時catch-all遅延値の不一致(280ms→350ms)、負の`scrollY`(iOS rubber-band)未クランプも修正
- **3段目 (PR #65作成後、4エージェント独立レビュー×3が一致指摘)**: 2段目の実測方式は画像読み込み時に安全性判定を一度だけ実行しており、有効化後にウィンドウをリサイズして危険な比率へ転じても再判定されず、まさに1段目のズームバグが再発する経路が残っていた。`resize`イベント(200msデバウンス)で安全性判定を再実行するよう修正し、実機で1440px(有効)→1280px(危険帯、自動無効化)→1440px(再有効化)の往復動作を確認。あわせて非同期コールバック(probe.onload/resize後の再判定)がtry/catchで保護されていなかった構造的ギャップも解消

## Stage 2 追加改善 (2026-07-15 決裁者フィードバック対応、PR #67〜#70・全完了・本番確認済み)
Stage 2 (PR #65) 本番反映後、決裁者から追加フィードバック4件を受け、同日中に段階的に実装・検証・マージ:
1. 「ヒーローセクションにもっとダイナミックな動画的な動きが欲しい」→ Remotion(企業向け有償ライセンス要)・AI動画生成(未導入ツール要)は不採用と判断、追加コストゼロの CSS Ken Burns ズーム(26秒ループ、scale 1→1.06)を追加 (PR #67)
2. 「トップページ全体でスクロールしたら各セクションもそれぞれ動くように」→ career-ladder/category-card のみだった70ms刻みstaggerを mission-card(Philosophy)/stat(数字)/flow__step(選考フロー)/faq__item(FAQ) にも拡張 (PR #68)
3. 「全然動きません、固定のまま。わからないならWebでベストプラクティスを調べて」→ WebSearchで2026年時点のベストプラクティスを調査、`animation-timeline: view()` (CSS Scroll-driven Animations、Chrome/Edge/Safari対応・Firefox安定版は2026-07時点で未対応のため `@supports` でIntersectionObserver版をfallback維持) に刷新。スクロール位置そのものに要素のopacity/scale/位置がリアルタイム連動するよう変更 (PR #69)
4. 「動くタイミングが速すぎる」→ `animation-range` を `entry`(要素自身の高さ基準、薄い要素で一瞬終わる欠陥)から `cover`(ビューポート高さ基準、要素の高さに関わらず安定して長め)に変更、進行速度を緩和 (PR #70)

- [x] タスクE: ヒーロー背景 Ken Burns ズームループ追加、既存パララックスと別要素に分離し競合回避 (PR #67)
- [x] タスクF: 全セクション要素(mission-card/stat/flow__step/faq__item)へのstagger演出拡張 (PR #68)
- [x] タスクG: `animation-timeline: view()` によるスクロール連動アニメーション化、非対応ブラウザへの `@supports` fallback (PR #69)
- [x] タスクH: `animation-range` を entry→cover に変更しスクロール連動の進行速度を緩和 (PR #70、実測: career-ladder__step 780px / faq__item 660px でゆっくり完了)

いずれも Playwright 実機検証(通常スクロール・`prefers-reduced-motion: reduce`・本番 GitHub Pages)を実施し、決裁者のフィードバックを受けて次PRへ反映するサイクルで進めた。次に決裁者が実機で確認し、体感速度・強度が適切か追加フィードバックを待つ状態(2026-07-15時点で最新フィードバック未着)。

## Stage 1 (完了・2026-07-15 PR #64) 履歴
配色システムの再定義(tokens.css/components.css新パレット、career-ladderコントラスト調整、CLAUDE.md更新)完了・本番確認済み。詳細diffは PR #64 参照。

### フォローアップ (Stage 1 スコープ外、decision-maker 確認後に着手)
- `mockup/jobs/*.html`(33ファイル)+カテゴリページの `<meta name="theme-color">` が旧 `#00c4cc` のまま。Stage 1 は「トップページのみ」の承認スコープのため意図的に対象外。横展開時に一括更新
- `CLAUDE.md` line 44「コーポレートカラー: ブルー #00C4CC」(メインキャラクター画像生成セクション)と `docs/specs/chatgpt-ui-prompts.md` のイラスト生成プリアンブルが、実際に採用済みのイラスト実測配色(コバルトブルー系, sky-hero.jpg 等)と乖離。イラスト生成は decision-maker 領分のクリエイティブ仕様のため、更新要否は decision-maker 判断待ち
- career-ladder level-4/5 の背景色コントラストが低い(実測 1.3:1、ほぼ同系統の濃紺)。高さの階段状レイアウトで序列は視覚的に伝わっているため非ブロッキングだが、Stage 3(コンポーネントリデザイン)で改善余地あり

## ロードマップ (Stage 3、Stage 2決裁者確認後に個別 impl-plan で仕切り直し)
- **Stage 3: コンポーネント単位のリデザイン(AI臭さの払拭)** — 最も主観的な要素のため、Stage 1・2の結果を決裁者に見せ、具体的な指摘(角丸・ソフトシャドウ・pill型ボタン等のSaaS的表現をポスター的・シャープな表現へ、等)を得てから着手。スコープ未確定

## 🔄 中断点（in-flight）
なし
