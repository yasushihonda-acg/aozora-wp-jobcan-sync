---
updated: 2026-07-15
---

## 現在のミッション
トップページ (`mockup/index.html`) のトンマナ全面ブラッシュアップ。決裁者の実機フィードバック(ヒーロー文字視認性・旧イラスト混在・動きの欠如・キャリアパス訴求不足)に対応する。

## 背景・why
決裁者が公開モックを実機確認し、①ヒーロー見出し/リード文が背景と同化して読めない箇所がある ②「数字で見る、あおぞら」の `illust-numbers.jpg` だけ旧スタイルで浮いている ③ヒーロー背景を新候補画像(Image #2)に差し替えたい ④ tcy.co.jp/recruit のような動き・g-s.dev のような洗練度が欲しい ⑤ kamakura-kdi.com/recruit-business.html のような「入社からのキャリアアップモデル」を追加したい、とフィードバック。`/impl-plan` フルモードで計画済み・承認済み(2026-07-15)。

## 完了の定義
- [x] `mockup/assets/img/sky-hero.jpg` が Image #2 由来の新イラストに置き換わっている（証明: `file mockup/assets/img/sky-hero.jpg` のバイト内容が旧版と異なる。2026-07-15 決裁者が画像再送、反映・実機確認済み）
- [x] `.hero__title em` のマーカー背景が除去され、ヒーロー文字が判読できる（証明: `grep -c "background: linear-gradient(transparent 60%" mockup/assets/css/components.css` が 0）
- [x] `illust-numbers.jpg` への参照が index.html から消えている（証明: `grep -c illust-numbers mockup/index.html` が 0）
- [x] 「入社からのキャリアアップモデル」セクションが index.html に存在する（証明: `grep -c "career-ladder" mockup/index.html` が 1 以上）
- [x] スクロールリビール実装 `mockup/assets/js/site.js` が存在し index.html から読み込まれている（証明: `test -f mockup/assets/js/site.js` かつ `grep -c "assets/js/site.js" mockup/index.html` が 1 以上）
- [x] ブラウザ console エラー 0 件（証明: Playwright `browser_console_messages` level=error が空、favicon 404 除く。ローカル確認済み）
- [x] `docs/specs/chatgpt-ui-prompts.md` と `CLAUDE.md` の記述が実装内容と整合（証明: 目視レビュー済み）

## 進行中のtasks
- [x] タスク1: `sky-hero.jpg` を Image #2 で上書き
- [x] タスク2: hero 視認性修正（マーカー除去 + スクリム強化）
- [x] タスク3: Numbers セクションからイラスト除去 + レイアウト再構成
- [x] タスク4: `.career-ladder` コンポーネント新規実装（ダミーデータ明記）
- [x] タスク5: スクロールリビール実装（`site.js` + CSS transition、`prefers-reduced-motion` 対応）
- [x] タスク6: index.html への script 配線 + `data-reveal` 属性付与
- [x] タスク7: `docs/specs/chatgpt-ui-prompts.md` 更新
- [x] タスク8: `CLAUDE.md` 更新
- [x] Playwright 実機確認（デスクトップ + モバイル）+ `/code-review medium`（5件 CONFIRMED、全修正済み: section--band WCAGコントラスト、site.js .js クラス独立性リスク、career-ladder nth-child脆弱性、career-ladder__num バッジ不整合、nth-child(1) 冗長宣言）

## 🔄 中断点（in-flight）
なし（タスク1 のみ decision-maker からの画像再送を起点とする条件待ち。それ以外は完了・PR作成待ち）
