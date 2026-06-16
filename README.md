# aozora-wp-jobcan-sync

ACG (あおぞらケアグループ) 採用サイト刷新プロジェクト。フロントを WordPress で独自構築、バックエンドはジョブカン ATS を継続。GCP で求人データを自動同期する構成。

## 概要

| 領域 | 採用技術 / 方針 |
|---|---|
| フロント | WordPress (ACG コーポレートサイト `https://aozora-cg.com/` のトンマナ踏襲) |
| 項目構成参考 | `https://tcy.co.jp/recruit/` |
| バックエンド (ATS) | ジョブカン (求人票管理・応募管理・選考管理) |
| 応募フォーム | ジョブカン直リンク (`https://recruit.jobcan.jp/aozora/entry/new/{job_id}`) を継続 |
| 自動同期 | GCP プロジェクト `aozora-wp-jobcan-sync` (詳細は `docs/specs/sync-strategy.md`) |
| 公開ドメイン | `recruit.aozora-cg.com` (サブドメイン) |

## 段階

| Phase | 内容 | 状況 |
|---|---|---|
| **A. 静的 HTML モック** | 採用トップ / 求人一覧 / 求人詳細 1 件を作成、決裁者承認用 | 🔄 着手中 |
| **B. WordPress 本番構築** | ホスティング選定 → テーマ / CPT / ACF 実装 → GCP 同期コンポーネント | ⏳ Phase A 承認後 |
| **C. 拡張 / 移行** | ジョブカン公式 API 移行 / 複数事業所 / 検索強化 / 観測性 | ⏳ 3 ヶ月以降 |

詳細な実装計画: `/Users/yyyhhh/.claude/plans/wordpress-wp-acg-hp-https-recruit-jobca-memoized-catmull.md`

## ディレクトリ構成

```
aozora-wp-jobcan-sync/
├ README.md                         この概要
├ CLAUDE.md                         プロジェクト固有コンテキスト・運用方針
├ docs/
│  ├ specs/                         Phase 仕様 (デザイン / 同期 / 受入基準 / 承認フロー / ホスティング比較)
│  └ adr/                           設計判断 (Phase B 以降に追加)
└ mockup/                           Phase A: 静的 HTML モック
   ├ index.html                     採用トップ
   ├ jobs.html                      求人一覧
   ├ jobs/sample-care-staff.html    求人詳細サンプル
   └ assets/{css,img}/
```

## 着手前に確認が必要な 3 点 (Codex セカンドオピニオン指摘)

1. **ジョブカンへの公式照会**: 公開求人ページの定期自動取得・自社別ドメインでの再掲出が許容されるか文書確認 → 結果次第で同期方式の主系を確定。照会文ドラフトは `docs/specs/sync-strategy.md` に格納予定。
2. **WordPress ホスティング再判定**: Cloud Run 自前運用 vs マネージド WP の運用観点比較 → `docs/specs/hosting-comparison.md`。
3. **個人情報棚卸し**: WP に保存する情報 / アクセスログ / GA4 / 応募リンククリックログを分類し、ismap 適用範囲を確定。

## 参考プロジェクト

- `/Users/yyyhhh/Projects/ACG/wp-acg-hp/` — ACG コーポレートサイト関連、CSS 変数引き継ぎ元
- `/Users/yyyhhh/Projects/ACG/aozora-sns-auto/` — GCP (Cloud Run + Cloud Scheduler + Firestore + Terraform) 構成の前例。Phase B で参考にする

## 参考サイト

- 現状求人サイト: <https://recruit.jobcan.jp/aozora>
- トンマナ参考: <https://aozora-cg.com/>
- 項目構成参考: <https://tcy.co.jp/recruit/>
