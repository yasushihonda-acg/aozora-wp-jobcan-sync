# Phase A モック (静的 HTML)

ACG 採用サイト刷新の方向性確認用、決裁者レビュー向けの静的 HTML モック。

## 公開予定 URL

- (未確定): GitHub Pages で公開予定 (新規リポジトリ or `wp-acg-hp` 内併設 — 計画書 未確定 #9)

## ページ構成

| ファイル | URL | 内容 |
|---|---|---|
| `index.html` | `/` | 採用トップ (MV / 理念 / 募集職種 / 数字 / 選考フロー / FAQ / CTA) |
| `jobs.html` | `/jobs/` | 募集職種一覧 (フィルタ UI + 求人カード 10 件サンプル) |
| `jobs/sample-care-staff.html` | `/jobs/sample-care-staff/` | 求人詳細サンプル (1 件、特養介護スタッフ) |

## ローカル確認

```bash
# プロジェクトディレクトリで
open mockup/index.html
# or 任意の静的サーバーで
cd mockup && python3 -m http.server 8080
# → http://localhost:8080/
```

## 決裁者レビュー時のチェックポイント (要旨)

詳細は `/docs/specs/acceptance-criteria.md` 参照。

### A. デザイン
- ACG コーポレートサイト ([aozora-cg.com](https://aozora-cg.com/)) とのトンマナ一致
- レスポンシブ (iPhone SE / iPad / PC) で崩れなし

### B. 情報設計
- 募集職種カテゴリーが現状ジョブカン公開求人と過不足なく対応
- 求人カードの表示項目 (職種/勤務地/給与/雇用形態/募集要約) が決裁者合意
- 求人詳細の項目セット (仕事内容/必須資格/勤務時間/休日/福利厚生/応募方法) が決裁者合意

### C. 応募導線
- 応募ボタン → ジョブカン応募フォーム (`/aozora/entry/new/{job_id}`) パターン
- 応募フォーム障害時の **代替導線 (電話 / 問い合わせ)** が明示
- **CTA 固定表示** (モバイルでもスクロール時に応募ボタンが見える)

### D. SEO
- canonical 方針 (recruit.aozora-cg.com を canonical 想定)
- JobPosting 構造化データ (求人詳細に JSON-LD 出力済 — Phase A 雛形)
- ジョブカン元ページとの重複対策方針

### E. 運用
- 同期方式の最終決定 (要 ジョブカン公式照会結果)
- 応募リンク死活監視の方針

### F. 法務
- 個人情報棚卸し → ismap 適用範囲確定

## モック内のダミー情報

- 求人 10 件はサンプル (recruit.jobcan.jp/aozora の実データを参考にサンプリング)
- 求人 ID `12345` 等はダミー、応募ボタンのリンク先 URL パターンの確認のみ
- スタッフインタビュー (中村さん・佐々木さん・田中さん) は仮原稿
- 電話番号 `092-000-0000` はダミー
- メールアドレス `recruit@aozora-cg.com` は予定

## 既知の TODO (Phase A 内で詰める)

- [ ] `aozora-cg.com` 実物のスクショ取得 → カラーパレット (アクセント色) 確定 → `tokens.css` に反映
- [ ] 実物のフォントファミリー確認 (Noto Sans JP かどうか)
- [ ] スタッフインタビューの実取材 (Phase A はダミーで進行 — 未確定 #8)
- [ ] キービジュアル素材 (新規撮影 or 既存流用 — 未確定 #7)
- [ ] 電話番号・メールの実値 (未確定)
- [ ] ジョブカン公式照会の文面送付 (`docs/specs/sync-strategy.md` のドラフト使用)
- [ ] WP ホスティング比較表に基づく組織判断 (`docs/specs/hosting-comparison.md`)

## リビジョン履歴

### phase-a-v0.1 (2026-06-16)
- 初版作成 (Codex セカンドオピニオン反映済)
- CSS 3 ファイル (tokens / components / pages) + HTML 3 ページ
- 求人 10 件サンプル + 求人詳細 1 件サンプル
- JobPosting 構造化データ雛形
- CTA 固定表示 (モバイル)、代替導線 (電話 / メール) 明示
- 設計文書 5 本 (design-tokens / sync-strategy / acceptance-criteria / draft-review-flow / hosting-comparison)
