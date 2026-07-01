# イラスト刷新 台帳 (2026-07-01)

決裁者指定の新メインキャラ (Image #5 = full baseline / Image #6 = close-up baseline) への刷新に伴う、mockup 内全画像の対応台帳。

## 判定サマリ

- **IN スコープ**: 12 枚 (イラスト系のみ)
- **OUT スコープ**: 11 枚 (実写別レイヤー + 人物なし挿絵)
- **予算上限**: $10 (Codex 推奨、超過時停止)
- **想定生成回数**: 40 回相当

## レイヤー分離原則

プロジェクトは **写真 (photo) / イラスト (illust)** の 2 レイヤー明確分離:
- 写真レイヤー: `staff-*.jpg` / `blog-*.jpg` / `hero-main.jpg` / `category-*.jpg` — 実写素材、名前付き別人物、テーマ別
- イラストレイヤー: `illust-job-*.png` / `illust-{philosophy,flow,numbers}.jpg` — メインキャラ (or 概念) を表現

新キャラ刷新はイラストレイヤーのみに作用する。写真レイヤーは触らない。

## IN スコープ (12 枚)

| # | ファイル | 現状 | 対応 | Round |
|---|---------|------|------|-------|
| 1 | `illust-job-care.png` | 求人カード、メインキャラ | regenerate | α |
| 2 | `illust-job-consultant.png` | 求人カード、メインキャラ | regenerate | α |
| 3 | `illust-job-nurse.png` | 求人カード、メインキャラ | regenerate | β |
| 4 | `illust-job-office.png` | 求人カード、メインキャラ | regenerate | β |
| 5 | `illust-job-it.png` | 求人カード、メインキャラ | regenerate | β |
| 6 | `illust-job-care-2.png` | 求人カード、メインキャラ | regenerate | β |
| 7 | `illust-job-care-3.png` | 求人カード、メインキャラ | regenerate | β |
| 8 | `illust-job-default.png` | 求人カード fallback、メインキャラ | regenerate | γ |
| 9 | `illust-job-consultant-2.png` | 求人カード、メインキャラ | regenerate | γ |
| 10 | `illust-job-office-2.png` | 求人カード、メインキャラ | regenerate | γ |
| 11 | `illust-philosophy.jpg` | 3 人物フラットベクター (ターコイズスクラブ介護士 + 車椅子高齢者 + 家族) | regenerate (メインキャラを黒 scrub に置換、複数人シーン維持) | γ |
| 12 | `illust-flow.jpg` | 2 人物フラットベクター (ターコイズスクラブ介護士 + 応募者) | regenerate (メインキャラを黒 scrub に置換、面接シーン維持) | γ |

## OUT スコープ (11 枚)

| ファイル | 分類 | 除外理由 |
|---------|------|---------|
| `staff-nakamura.jpg` | 実写 | 別レイヤー、名前付きスタッフ (中村) の実写ポートレート |
| `staff-sasaki.jpg` | 実写 | 別レイヤー、名前付きスタッフ (佐々木) |
| `staff-tanaka.jpg` | 実写 | 別レイヤー、名前付きスタッフ (田中) |
| `blog-childcare-return.jpg` | 実写 | 育休復帰テーマ (キッチン、勤務表、子供の絵) |
| `blog-mentor-program.jpg` | 実写 | メンター制度テーマ (施設廊下、看護スタッフ後ろ姿) |
| `blog-papa-leave.jpg` | 実写 | パパ育休テーマ (父親が赤ちゃんを抱く) |
| `hero-main.jpg` | 実写 | メインヒーロー実写 (若い介護士 + 高齢者) |
| `category-care.jpg` | 実写 | カテゴリアイコン (食事介助シーン) |
| `category-nurse.jpg` | 実写 | カテゴリアイコン (訪問看護シーン) |
| `category-office.jpg` | 実写 | カテゴリアイコン (オフィスシーン) |
| `category-it.jpg` / `cm.jpg` / `visit.jpg` | 実写 | カテゴリアイコン (未確認、実写想定) |
| `illust-numbers.jpg` | イラスト、人物なし | 町並みシルエット + ターコイズアクセント屋根/風車。人物なしなのでキャラ設定と競合しない。パレット追従 (turquoise → 新アンカー) は Phase A 承認後の別作業として保留 |

## アーカイブ

旧 baseline PNG 2 枚を保管済:

```
.claude/memory/archive/illustration-baseline-2026-06-29.png
.claude/memory/archive/illustration-baseline-character-closeup-2026-06-29.png
```

新 baseline (Image #5/#6) 差替は Phase 1 で実施。

## 承認ゲート

本台帳を本田様がご承認いただき次第、Phase 1 (Atomic 真理ソース更新) に着手。
