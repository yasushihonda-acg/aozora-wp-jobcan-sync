# CLAUDE.md — aozora-wp-jobcan-sync

このプロジェクトで Claude Code が作業する際のコンテキスト。グローバル `~/.claude/CLAUDE.md` + 本ファイルで動作。

## プロジェクト要旨

ACG 採用サイトのフロントを WordPress で独自構築、バックはジョブカン ATS 継続、GCP で求人データ自動同期。直近は Phase A (静的 HTML モック → 決裁者承認) に注力。

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
- ブロック単位 BEM 命名 (`.job-card`, `.job-list-filter`, `.entry-cta` 等) で Phase B 流用率向上
- HTML 構造は WordPress ブロックエディタの構造 (`<section><div class="container">...`) に寄せる
- ダミーデータは `recruit.jobcan.jp/aozora` から職種・勤務地・雇用形態のばらつきを反映した実求人 10 件をサンプリング
- 画像は `<picture>` でレスポンシブ、alt 必須

### デザイン
- 起点: `wp-acg-hp/docs/style.css` の CSS 変数 (`--color-accent: #00c4cc` 等)
- 実物 `aozora-cg.com` はグレートーン基調と判定済、シアン系の流用は仮、Phase A 1st ドラフトで実物スクショと並べて決裁者と最終確定
- Phase A 着手前にデザイントークン表 (`docs/specs/design-tokens.md`) を 1 枚作って合意

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
| wp-acg-hp | `/Users/yyyhhh/Projects/ACG/wp-acg-hp/` | CSS 変数引き継ぎ元 |
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

## 未確定事項 (Phase A 中に詰めたい)

優先順:
1. ジョブカンへの公式照会結果
2. WP ホスティング (Cloud Run 自前 vs マネージド WP)
3. 個人情報棚卸し → ismap 適用範囲
4. 決裁者の特定 (経営層 / 採用部門 / 法務、人数)
5. 公開希望時期
6. aozora-cg.com 実物カラーパレット
7. キービジュアル素材 (新規撮影 or 既存流用)
8. スタッフインタビュー原稿 (Phase A ダミー可否)
9. GitHub Pages 公開先 (新規 repo or wp-acg-hp 内併設)
10. ジョブカン ATS 契約プラン (LITE / STANDARD / PROFESSIONAL)
11. ACF Pro / WP ライセンス予算
12. GCP / WP 月額予算上限
13. 法務レビュー所要期間

## グローバル方針との関係

- グローバル `~/.claude/CLAUDE.md` の CRITICAL ルール (3 ステップ以上 → `/impl-plan`、3 ファイル以上 → `/safe-refactor` + `/code-review`、destructive 操作は番号単位認可) を遵守
- 本プロジェクトはまだ git 管理外。Phase A 公開段階で git 化、その時点で PR ルール (main 直 push 回避、PR 経由) を適用開始
