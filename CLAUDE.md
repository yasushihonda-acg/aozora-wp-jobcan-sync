# CLAUDE.md — aozora-wp-jobcan-sync

このプロジェクトで Claude Code が作業する際のコンテキスト。グローバル `~/.claude/CLAUDE.md` + 本ファイルで動作。

## プロジェクト要旨

ACG 採用サイトのフロントを WordPress で独自構築、バックはジョブカン ATS 継続、GCP で求人データ自動同期。直近は Phase A (静的 HTML モック → 決裁者承認) に注力。

## ローカル開発・公開 URL

- **公開モック**: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
- **GitHub repo**: https://github.com/yasushihonda-acg/aozora-wp-jobcan-sync (public)
- **ローカル確認**: `cd mockup && python3 -m http.server 8989` → http://localhost:8989/ (使用後は必ず停止: dev server 放置禁止)
- Pages 設定: Source `main` / path `/`、build 完了 ~20-60 秒

## 重要な制約・方針

### 個人情報・組織方針
- 介護事業者として個人情報 (応募者・スタッフ等) を扱う組織方針: ismap 準拠 GCP 内完結が原則
- ただし採用サイト本体が個人情報を保存しない設計 (応募フォームはジョブカン直リンク) のため、適用範囲はホスティング選定時に再判定 → `docs/specs/hosting-comparison.md`
- 外部 SaaS (Sentry / Datadog 等) は不採用

### 同期方式の優先順位 (2026-06-18 シンプル化、過剰設計巻き戻し)
- **採用**: 案 D = 動的プロキシ (Cloud Run + httpx + BeautifulSoup + Jinja2)
- ジョブカン契約者 (本田様) の自社採用情報を自社サイトに表示する **標準的 ATS 統合ユースケース**
- 規約照会 trigger 廃止 (`.claude/memory/feedback_overengineering_recovery_2026-06-18.md` 参照、自社契約 SaaS の自社利用は通常利用範囲)
- 代替案 (CSV 半自動 / 公式 API) は案 D が技術的に成立しない場合の fallback として記録のみ、現時点では未採用

### Phase A モックの設計規約
- ブロック単位 BEM 命名 (`.job-card`, `.job-list-filter`, `.entry-cta`, `.blog-card`, `.news-item` 等) で Phase B 流用率向上
- HTML 構造は WordPress ブロックエディタの構造 (`<section><div class="container">...`) に寄せる
- ダミーデータは `recruit.jobcan.jp/aozora` から職種・勤務地・雇用形態のばらつきを反映した実求人 10 件をサンプリング
- 画像は `<img>` 直書き (`<picture>` の webp `<source>` は webp ファイル未生成のため Safari で broken。alt 必須)
- 採用トップのセクション順: hero → philosophy → categories → career (入社からのキャリアアップモデル、2026-07-15 追加) → numbers → flow → faq → entry-cta (tcy.co.jp/recruit 参考)。**スタッフ紹介・育休ブログ・お知らせ/コラムの各セクションは 2026-07-14 決裁者指示で廃止**(スタッフ紹介は実写ポートレートがイラスト主体のポスタートンマナと不整合、育休ブログ/お知らせ・コラムはトップページの情報を絞り込む方針のため)

### イラスト方針 (統一 — 2026-07-02 決裁者最終指示、ChatGPT UI 経路 + 黒ポロシャツ制服 spec)
mockup 内のキャラ含みイラスト (求人カード + philosophy / flow 挿絵 + スタッフ紹介・ブログ挿絵の将来分) は、**すべて ChatGPT UI で生成する** (`docs/specs/chatgpt-ui-prompts.md` の PREAMBLE + SCENE ブロック運用)。旧 API `v1/images/edits` 経路 (Phase 1〜1.5、aozora-illust スキル) は identity 保持限界で character-critical illustration では非採用。
- **NG**: フラットベクター簡略化、透明水彩フラット塗り、AI 生成丸出しの不自然な顔、過剰なグラデーション・装飾、テキスト・ロゴ混入、commercial anime 寄り (thick outline + glossy shading)、青い制服、白衣っぽすぎる表現
- **OK** (2026-07-14 決裁者指定、reference 3 枚で確定): **江口寿史風 + シティポップ・さわやか・無機質・ポスター/広告的**。コバルトブルー×白の大胆な幾何学色面背景 + 都市スカイライン、細く均一なクリーン輪郭線 + フラットセル塗り、涼しげで控えめな表情。「医療介護 = 温かい・ほっこり」の固定観念イメージは一切排除 (介護特有の生活感・福祉感 NG)。ブルーは差し色限定を解除し背景の色面に面で使用可
- 旧「エモさ (golden hour 暖色ノスタルジー)」指示 (2026-07-02) は廃止済み
- **2026-07-14/15 トップページ トンマナ全面刷新 (完了)**: 決裁者指示で https://g-s.dev/ のようなポスター的トンマナへ寄せる方針のもと、①ヒーロー背景を `hero-main.jpg` 実写から江口寿史風の青空+入道雲+都市スカイラインの人物なしイラストへ (SCENE #13、`sky-hero.jpg` 上書き、entry-cta 背景も同一ファイル共用) ②philosophy (SCENE #11) / flow (SCENE #12) を「warm・複数人物必須」から求人カード群と同一の単独キャラクター・ポスタートーンへ ③募集職種カード実写 6 枚 (`category-*.jpg`) を求人カードイラストへ差替え、専用イラストが無かった「訪問介護員 (ヘルパー)」向けに SCENE #14 (`illust-job-visit.png`、洗濯物たたみシーン) を新規生成。すべて 2026-07-15 までに採用・配置完了。予備バリエーション (SCENE #15 食事介助 / #16 歩行介助) も生成済みだが現状表示スロットなし。詳細は `docs/specs/chatgpt-ui-prompts.md` 参照
- **2026-07-15 実機フィードバック対応 (第2ラウンド)**: 決裁者が GitHub Pages 実機を確認し追加指摘。①ヒーロー見出し `<em>` の白マーカー背景 + リード文の視認性不足を CSS 修正 (`mockup/assets/css/components.css` の `.hero`/`.hero__title em`/`.hero__lead`、マーカーはブランドカラーの下線アクセントに変更、ヒーロー全体にディレクショナルスクリムを追加) ②ヒーロー背景の新バリエーション候補 2 枚のうち可読性の高い方を採用し `sky-hero.jpg` へ反映済み(Image #2 相当、雲が少なく単色の濃紺空が左〜中央に広がる構図、entry-cta 背景も同一ファイル共用) ③「数字で見る、あおぞら」の `illust-numbers.jpg` (旧 Phase 1 フラットベクター町並み、他セクションとトンマナ不統一と決裁者指摘) を index.html から除去し `.section--band` の色面レイアウトへ変更、ファイル自体は将来の再生成用に保管 (バックログ: `docs/specs/chatgpt-ui-prompts.md` SCENE #17) ④「入社からのキャリアアップモデル」セクションを新設 (`.career-ladder`、kamakura-kdi.com/recruit-business.html 参考、役職 5 段階の階段状ブロック。**年数・年収帯は Phase A ダミーデータ、決裁者確認後に実データへ差し替え**) ⑤ tcy.co.jp/recruit・g-s.dev を参考に IntersectionObserver ベースのスクロールフェードイン (`mockup/assets/js/site.js`、`data-reveal` 属性、`prefers-reduced-motion` 対応、JS 無効時は常時表示にフォールバック) を主要セクションに適用
- **制服**: **黒ポロシャツ (襟 + ボタンあり)** + **青ランヤード + ID badge**、青は差し色として名札・小物・背景アクセント等に配置。派生: consultant はニュートラルカーディガン重ね着可、office はスーツ系 (黒/charcoal テーラードジャケット + 白襟シャツ、2026-07-02 決裁者指示)、it は黒パーカー (2026-07-02 決裁者指示)
- **コーポレートカラー (イラスト生成用、要 decision-maker 確認)**: ブルー `#00C4CC` (差し色) / グレー `#575656` (文字・影) / ベージュ `#f8f5ee` (背景ベース)。**注意 (2026-07-15)**: サイトUIのアクセントカラーは同日デシジョンで `#0a52b8` (コバルトブルー) へ刷新済み (下記デザインセクション参照)。既に採用済みのイラスト実測配色 (`sky-hero.jpg` 等) も `#00C4CC` より濃いコバルトブルー系のため、本行の値は現行イラストの実態と乖離している。`docs/specs/chatgpt-ui-prompts.md` のプリアンブルも同様の乖離があり、今後のイラスト生成 (SCENE #15〜) で値を更新するか本行だけ残すかは decision-maker 判断待ち
- **アクセサリー**: 職種別ルール準拠 (`aozora-illust/prompts/outfit-spec.txt` の ACCESSORIES RULES 参照)。care/nurse ではピアス NG、consultant/office/it は小スタッド OK
- **人物なし挿絵** (`illust-numbers.jpg` 等) は現状維持。パレット追従は Phase A 承認後の別作業。

### メインキャラクター画像生成 (求人カード + シーン挿絵 + 将来のブログ挿絵)
- **MUST**: メインキャラ (**20 代後半〜30 代前半女性、べっ甲丸縁眼鏡、黒ポロシャツ + 青ランヤード + ID badge**) の画像生成は **決裁者判断 (2026-07-02) により ChatGPT UI 経路で行う**。API `v1/images/edits` (aozora-illust スキル経由) は identity 再現限界により character-critical illustration では非採用 (本セッションで 8 回試行後実証)
- ChatGPT UI 経路の運用: `docs/specs/chatgpt-ui-prompts.md` の PREAMBLE + SCENE ブロックをコピペ、baseline PNG を UI 会話に添付、生成物を Claude に送信 → 10 項目採点 → mockup 配置 + PR
- **真理ソース** (decision-maker 領分、番号単位明示認可なしに改変禁止):
  - `.claude/memory/reference_illustration_baseline.md` (キャラ仕様 + 10 項目 Pass/Fail 検証チェックリスト)
  - `.claude/memory/illustration-baseline.png` (フルシーン基準、2026-07-02 版: 歩行介助シーン、**黒ポロシャツ + 青ランヤード + ID badge**、明るい介護施設内装 + 青アクセント背景)
  - `.claude/memory/archive/illustration-baseline-2026-07-01.png` (旧 Phase 1.5 baseline、V-neck scrub 版、履歴参照のみ)
  - `.claude/memory/archive/*-2026-06-29.png` (最旧 baseline、履歴参照のみ)
- aozora-illust スキル (`gen.sh` + Codex rewrite) は **人物なし挿絵 or 実験用途に限定して保持**。character-critical illustration には使用しない
- 出力 → 本田様が UI で生成 → 私 (Claude) に送信 → 10 項目採点 → `mockup/assets/img/illust-*.png` に採用 → 全 14 枚集めて Phase 4 PR (最新数は `docs/specs/chatgpt-ui-prompts.md` の SCENE ブロック数が正)

### デザイン
- **Primary accent: `#0a52b8` (コバルトブルー、2026-07-15 決裁者指示で刷新)**。aozora-cg.com 本家のコーポレートカラー `#00c4cc` (シアン) はあえて不採用とし、確立済みの江口寿史風イラスト群 (sky-hero.jpg / illust-philosophy.jpg 等) から実測した配色に統一。リクルートページを本家コーポレートサイトのトンマナから意図的に差別化する決裁者判断。`--color-accent` 系トークンは `mockup/assets/css/tokens.css` で一元管理 (`--color-accent` `#0a52b8` / `--color-accent-dark` `#063c89` / `--color-accent-light` `#d9e8fd` / `--color-accent-soft` `#ecf3fe` / `--color-accent-deep` `#02275a` / `--color-accent-ink` `#021127`)。旧 `#00c4cc` 系は `docs/handoff/LATEST.md` に履歴として記録
- Heading `#333333` / 本文 `#020201` / Footer `#323232` / 薄背景 `#f0f0f0` (本家 aozora-cg.com computed style 準拠、変更なし)
- フォント: **Noto Sans JP のみ** (Public Sans は本家でも使われていない)
- ロゴ: 公式 PNG `mockup/assets/img/logo-acg-light.png`。フッターは `filter: invert(1) brightness(1.6)` で白反転
- ヒーロー背景: `mockup/assets/img/sky-hero.jpg` (2026-07-14 江口寿史風イラストへ刷新済み、SCENE #13、entry-cta 背景も同一ファイル共用。旧: 本家 `mainvisual_E.jpg` 流用の実写)
- トークン定義: `mockup/assets/css/tokens.css`、components / pages もこの 3 ファイル構成
- **2026-07-15 リクルートページ基礎トンマナ刷新 (第2フェーズ、進行中)**: 決裁者指示で①コーポレートカラー離脱・イラスト由来配色への統一 ②tcy.co.jp/recruit・g-s.dev 的な視差効果・スクロール演出の強化 ③AI臭さの払拭による洗練度向上、を段階的に実施。Stage 1 (配色システム再定義) 完了、Stage 2 (視差効果) / Stage 3 (コンポーネントリデザイン) はロードマップ。詳細は `docs/handoff/GOAL.md` 参照

### CPT / ACF (Phase B)
- CPT: `job_offer`、Taxonomy: `job_type` / `employment_type` / `location` / `facility`
- 項目は 2 層構造: 正規化項目 (検索・絞り込み用) + 原文スナップショット (HTML/テキスト保持) で項目変更耐性確保

### 同期復旧設計 (Phase B)
- 初期 1 ヶ月は半自動運用: 取得 → Firestore スナップショット → 差分プレビュー → 採用担当承認 → WP 反映
- 連続 2 回不在で closed、closed 率 > 30% で同期中止 + Slack アラート
- 募集終了は WP 側 `private` 化 (削除しない、SEO/被リンク維持) → 30 日後 trash

## 参考プロジェクト

| プロジェクト | パス | 役割 |
|---|---|---|
| wp-acg-hp | `/Users/yyyhhh/Projects/ACG/wp-acg-hp/` | CSS 変数引き継ぎ元 (初期参考のみ、現在は本家 computed style 優先) |
| aozora-sns-auto | `/Users/yyyhhh/Projects/ACG/aozora-sns-auto/` | GCP Cloud Run + Scheduler + Firestore + Terraform 構成の前例 |

## 運用ルール

### 決裁者承認フロー
- Phase A ゲート 1: デザイン / 情報設計 / 応募導線 / SEO / 運用障害対応 / 法務 (`docs/specs/acceptance-criteria.md`)
- 共有: GitHub Pages の URL + Loom ウォークスルー動画 (5 分)
- リビジョン: 2〜3 回想定、変更履歴は git で管理

### 本番反映
- ドメイン: `recruit.aozora-cg.com` 確定
- DNS 切替時 TTL 60 秒、ロールバック容易化
- 旧 ジョブカン URL → 新 URL の 301 はジョブカン側次第

### PR ワークフロー
- アカウント: `yasushihonda-acg` (ACG 用、個人 `yasushi-honda` ではない)
- `feature/...` or `fix/...` ブランチで作業 → push → `gh pr create`
- マージは **ユーザー番号単位明示認可** 必須: 「PR #番号 — タイトル (N files, +X/-Y) でマージしてよいか?」形式で確認
- 承認後 `gh pr merge {N} --squash --delete-branch` → ローカル `git checkout main && git fetch origin && git reset --hard origin/main` で同期 (`pull --rebase` 禁止)
- merge 後 Pages は ~20-60 秒で自動 re-build

## 未確定事項 (Phase A 中に詰めたい)

優先順:
1. ジョブカンへの公式照会結果
2. WP ホスティング (Cloud Run 自前 vs マネージド WP)
3. 個人情報棚卸し → ismap 適用範囲
4. 決裁者の特定 (経営層 / 採用部門 / 法務、人数)
5. 公開希望時期
6. キービジュアル素材の最終形 (現状: nano-banana 生成、本番取材するか?)
7. スタッフインタビュー原稿 (現状ダミー、本番取材時期)
8. ジョブカン ATS 契約プラン (LITE / STANDARD / PROFESSIONAL)
9. ACF Pro / WP ライセンス予算
10. GCP / WP 月額予算上限
11. 法務レビュー所要期間

解決済 (履歴):
- aozora-cg.com 実物カラー → `#00c4cc` 確定 (セッション中)
- GitHub Pages 公開先 → `yasushihonda-acg/aozora-wp-jobcan-sync` (セッション中)

## グローバル方針との関係

- グローバル `~/.claude/CLAUDE.md` の CRITICAL ルール (3 ステップ以上 → `/impl-plan`、3 ファイル以上 → `/safe-refactor` + `/code-review`、destructive 操作は番号単位認可) を遵守
- git 管理開始済 (`yasushihonda-acg/aozora-wp-jobcan-sync`)。`main` 直 push は新規リポ初期化を除き禁止、feature ブランチ → PR → 認可 → squash merge → `reset --hard` 同期
