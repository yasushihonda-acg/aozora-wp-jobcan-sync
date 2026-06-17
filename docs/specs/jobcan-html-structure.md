# ジョブカン公開ページ HTML 構造 (Phase 0 検証結果)

> 2026-06-17 セッションで Playwright + curl 実機検証 + パーサー実装で確定。Phase 0 用の最小情報。Phase 1 以降の selectors 外部化 (`selectors.yaml`) や hot-patch 機構 は別途。

## 1. レンダリング方式

- **完全 SSR (Ruby on Rails アプリ)**。React/Vue/Next 等の SPA フレームワークなし。
- `httpx + BeautifulSoup` で全項目抽出可能、headless ブラウザ (Playwright) 不要。

## 2. URL パターン

| 種類 | パス | 例 |
|---|---|---|
| トップ | `/aozora` | https://recruit.jobcan.jp/aozora |
| カテゴリ一覧 | `/aozora/list?category_id={cid}` | https://recruit.jobcan.jp/aozora/list?category_id=18773 |
| 求人詳細 | `/aozora/job_offers/{job_id}` | https://recruit.jobcan.jp/aozora/job_offers/1777023 |
| 応募 | `/aozora/entry/new/{job_id}` | https://recruit.jobcan.jp/aozora/entry/new/1777023 |

求人詳細には `?hide_breadcrumb=true&hide_search=true` パラメータを推奨 (ジョブカン側が iframe 埋め込み向けに提供している示唆)。

## 3. 確定セレクタ (Phase 0)

| 項目 | CSS セレクタ | 抽出例 |
|---|---|---|
| 求人タイトル | `.job-offer-detail-title` | `【社】介護職（博多／デイ・有料）` |
| 仕事内容本文 | `.job-offer-description-full` | (HTML、`bleach` でサニタイズ) |
| 拠点 | `.job-offer-address` | `【福岡】あおぞらケアグループ博多（デイ・有料）` |
| 雇用形態ラベル | `.job-offer-label` | `介護職 正社員` |
| 応募 URL | `a[href^="/aozora/entry/new/"]` | `/aozora/entry/new/1777023` |
| 表 (勤務地/給与/他) | `.content-table-line` | (順序ベースで 勤務地 / 給与 / 募集拠点 / 必須スキル 等) |

表の各行は以下の入れ子構造:
- `.content-table-head` or `.job-offer-table-left` → 見出し
- `.td-contentTable__breakWordWrap` or `.job-offer-table-right` → 値

## 4. カテゴリ ID 一覧 (Phase 0 で取得)

| ID | 職種名 |
|---|---|
| 18773 | 介護職 |
| 18985 | ケアマネジャー・計画作成担当者 |
| 18986 | ホームヘルパー |
| 18988 | 夜勤専従（介護・看護） |
| 18990 | サービス提供責任者 |
| 22014 | サービス管理責任者 |
| 39695 | 世話人 |
| 43764 | サポート職（清掃・洗濯・調理・送迎） |
| 58859 | 事務職 |
| 69384 | IT エンジニア職 |
| 73697 | 新卒・既卒総合職 |

他: `18983, 18984, 18987, 18989, 41046, 71511` (推定: 看護師、相談員、機能訓練指導員、リハビリ、薬剤師、保育士等、未調査)

## 5. 構造変化検知方針 (Phase 0 実装済)

| 種類 | 検知 | 例外クラス | CLI exit code |
|---|---|---|---|
| 必須セレクタ欠落 | `BeautifulSoup.select_one()` が None | `JobcanStructureChangeError` | 2 |
| セレクタは見つかるが値が空 | フィールド validation | `JobcanValidationError` | 3 |
| HTTP エラー | 429/5xx/404/timeout/network | `JobcanClientError` | 1 |

**部分表示禁止** (Codex Q6 反映): 1 つでも必須項目が欠けたら全体を失敗させ、ジョブカン側 URL へのフォールバック (302) を提示する。Phase 1 で Slack 通知 + フォールバックハンドラ実装予定。

## 6. 本文 sanitize 方針 (Phase 0 実装済)

外部 HTML を自社ドメインで配信する以上、XSS 等の責任は自社側に寄る (Codex Q6 指摘)。

| 処理 | 実装 |
|---|---|
| `<script>` / `<style>` / `<form>` / `<iframe>` / `<object>` / `<embed>` | **タグごと完全削除** (中身も含む) BeautifulSoup `decompose()` |
| 上記以外のタグ | `bleach.clean` で allowlist (`p`, `br`, `ul`, `ol`, `li`, `strong`, `em`, `b`, `i`, `h2`, `h3`, `h4`) のみ通す |
| 属性 | **全削除** (`class` / `style` / `onclick` 等を含む) |
| 残った `<a>` | bleach allowlist に含めていないため除去 (応募 URL は別途 `apply_url` フィールドで管理) |

## 7. 構造変化への運用方針

### Phase 0 (現状)
- パース失敗時: CLI exit code 2 + stderr にメッセージ
- 開発者が手動で `docs/specs/jobcan-html-structure.md` (本ファイル) を確認し、セレクタ更新

### Phase 1 (公式照会回答後ゲート以降)
- Slack 通知 (Incoming Webhook、構造変化発生時)
- セレクタを `selectors.yaml` に外部化、構造変化時にコード変更なしで対応可
- Cloud Run service 側でフォールバック: パース失敗 → 302 redirect → `https://recruit.jobcan.jp/aozora/job_offers/{id}` (元 URL)

### Phase 2 以降
- 定期 health check (例: 5 分おきに 1 件パース確認)
- 構造変化を git commit でセレクタ更新 → CI で全フィクスチャ再検証 → デプロイ

## 8. 今後追加予定の検証

Phase 1 で実施:
- 看護師 / IT エンジニア / 事務職 / パート の異なる雇用形態でセレクタ妥当性を再検証
- カテゴリ一覧ページ (`/aozora/list?category_id={cid}`) の構造、ページネーション、`limit/offset` パラメータ
- トップページ (`/aozora`) のメインビジュアル / カテゴリ一覧 / 地域別一覧

## 参考

- 検証日: 2026-06-17
- 検証 URL: https://recruit.jobcan.jp/aozora/job_offers/1777023
- 検証スクリプト: `sync/tests/fixtures/jobcan_responses/job_1777023.html` (取得時の HTML スナップショット)
- パーサー実装: `sync/src/sync/parser.py`
- テスト: `sync/tests/test_parser.py` (17 ケース、構造変化検知 + バリデーション + sanitize)
