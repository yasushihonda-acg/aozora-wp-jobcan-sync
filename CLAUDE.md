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
- 採用トップのセクション順: hero → philosophy → categories → numbers → staff → flow → faq → **育休ブログ** → **お知らせ・コラム** → entry-cta (tcy.co.jp/recruit 参考)

### イラスト方針 (統一 — 2026-07-01 決裁者最終指示 Phase 1.5 で editorial illustration 方向に精緻化)
mockup 内のキャラ含みイラスト (求人カード + philosophy / flow 挿絵 + スタッフ紹介・ブログ挿絵の将来分) は、**すべて aozora-illust スキル経由で `illustration-baseline.png` / `illustration-baseline-character-closeup.png` を踏襲して生成**する。旧「本家フラットベクター調」方針 (2026-06-18) と Phase 1 の polished anime 記述 (2026-07-01 前半) は廃止。
- **NG**: フラットベクター簡略化、透明水彩フラット塗り、AI 生成丸出しの不自然な顔、過剰なグラデーション・装飾、テキスト・ロゴ混入、commercial anime 寄り (thick outline + glossy shading)
- **OK**: **editorial magazine illustration in the vein of Eguchi Hisashi 江口寿史** (極めて繊細で優雅な細線、cel-shading 最小限、magazine printed feel)、暖色肌、黒髪 (restrained highlight のみ)、白〜淡ベージュ背景、木製家具・観葉植物・タブレット/クリップボード等の親しみアクセント
- **アクセサリー**: 職種別ルール準拠 (`aozora-illust/prompts/outfit-spec.txt` の ACCESSORIES RULES 参照)。care/nurse ではピアス NG、consultant/office/it は小スタッド OK
- **人物なし挿絵** (`illust-numbers.jpg` 等) は現状維持。パレット追従は Phase A 承認後の別作業。

### メインキャラクター画像生成 (求人カード + シーン挿絵 + 将来のブログ挿絵)
- **MUST**: メインキャラ (**20 代後半〜30 代前半女性、べっ甲丸縁眼鏡、黒 V-neck スクラブ + 青ランヤード + ID badge**) の画像生成は **必ず `.claude/skills/aozora-illust/` スキル経由**。`gpt-image` (text-only `v1/images/generations`) や curl 直叩きは禁止 — 同一キャラ再現が原理的に困難 (2026-06-29 実証)
- 唯一の正解手法 = `v1/images/edits` + baseline + close-up reference + 詳細プロンプト断片。スキルが固定化
- **真理ソース** (decision-maker 領分、番号単位明示認可なしに改変禁止):
  - `.claude/memory/reference_illustration_baseline.md` (キャラ仕様 + 10 項目 Pass/Fail 検証チェックリスト)
  - `.claude/memory/illustration-baseline.png` (フルシーン基準、2026-07-01 版: 立ち姿、黒 scrub、青ランヤード)
  - `.claude/memory/illustration-baseline-character-closeup.png` (顔基準、2026-07-01 版: 斜め横向き微笑)
  - `.claude/memory/archive/*-2026-06-29.png` (旧 baseline、履歴参照のみ)
- 使い方: `bash .claude/skills/aozora-illust/scripts/gen.sh --mode=single --category=<key> --scene="<英語シーン>"` または `--mode=sheet` (6 パネル同一性検証)
- スキル内 `prompts/*.txt` は真理由来。「もっと良くなりそう」で自己判断改変 NG。ズレはシーン記述側で局所調整
- 出力 → `generated-images/` → baseline と並置レビュー (`preview.html`) → ユーザー認可 → `mockup/assets/img/illust-*.png` に採用

### デザイン (aozora-cg.com 実物 computed style から確定)
- Primary accent: `#00c4cc` (シアン) — 本家のリンク・ナビ実使用色
- Heading `#333333` / 本文 `#020201` / Footer `#323232` / 薄背景 `#f0f0f0`
- フォント: **Noto Sans JP のみ** (Public Sans は本家でも使われていない)
- ロゴ: 公式 PNG `mockup/assets/img/logo-acg-light.png`。フッターは `filter: invert(1) brightness(1.6)` で白反転
- ヒーロー背景: `mockup/assets/img/sky-hero.jpg` (本家 `mainvisual_E.jpg` 流用)
- トークン定義: `mockup/assets/css/tokens.css`、components / pages もこの 3 ファイル構成

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
