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

### 同期方式の優先順位 (Codex 指摘反映)
1. ジョブカン公式回答 (API / 公式エクスポート機能)
2. CSV 半自動 (管理画面エクスポート → GCS → 取込) を主系
3. HTML パースは暫定・低頻度・手動確認付きに限定

→ Phase B 着手前にジョブカン公式照会必須。文面ドラフトは `docs/specs/sync-strategy.md`

### Phase A モックの設計規約
- ブロック単位 BEM 命名 (`.job-card`, `.job-list-filter`, `.entry-cta`, `.blog-card`, `.news-item` 等) で Phase B 流用率向上
- HTML 構造は WordPress ブロックエディタの構造 (`<section><div class="container">...`) に寄せる
- ダミーデータは `recruit.jobcan.jp/aozora` から職種・勤務地・雇用形態のばらつきを反映した実求人 10 件をサンプリング
- 画像は `<img>` 直書き (`<picture>` の webp `<source>` は webp ファイル未生成のため Safari で broken。alt 必須)
- 採用トップのセクション順: hero → philosophy → categories → numbers → staff → flow → faq → **育休ブログ** → **お知らせ・コラム** → entry-cta (tcy.co.jp/recruit 参考)

### イラスト方針 (全イラスト共通)
- **基準**: 本家コーポレートサイト `aozora-cg.com` のトンマナ (フラットベクター調、温かみのある肌色多様性、淡い背景)。基準サンプル = flow セクション「Selection Flow / 応募から内定まで、2〜3 週間」の面接イラスト (2026-06-18 ユーザー指示)
- **NG**: 水彩タッチ、AI 生成丸出しの不自然な顔、肌色一辺倒、過剰なグラデーション・装飾
- **OK**: 平面塗り (シェーディング最小)、暖色多様な肌色 (PR #8 で確立)、木製家具・観葉植物・コーヒー等の親しみアクセント
- **配置済 (差し替え済)**: philosophy / numbers / flow / hero overlay は PR #6→#7→#8 で本家トンマナに整合済 (`mockup/assets/img/illust-*.png`)
- **追加・差し替え時**: nano-banana 2 で flow イラスト (`mockup/assets/img/illust-flow.png` 周辺) を参考プロンプトに含めて生成 → Playwright で並べて視認 → 整合性確認後コミット

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
