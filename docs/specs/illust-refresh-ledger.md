# イラスト刷新 台帳 (2026-07-02 更新)

決裁者指定の新メインキャラ (2026-07-02 版 Image #5 = 歩行介助シーン baseline、黒ポロシャツ + 青ランヤード) への刷新に伴う、mockup 内全画像の対応台帳。

## 判定サマリ

- **IN スコープ**: 12 枚 (イラスト系のみ)
- **OUT スコープ**: 11 枚 (実写別レイヤー + 人物なし挿絵)
- **生成経路**: ChatGPT UI (character-critical illustration)、`docs/specs/chatgpt-ui-prompts.md` 参照
- **OpenAI API 予算残**: $5.88 / $10 (本セッション累計 $4.12 消費、人物なし挿絵 or 実験用途に保持)

## レイヤー分離原則

プロジェクトは **写真 (photo) / イラスト (illust)** の 2 レイヤー明確分離:
- 写真レイヤー: `staff-*.jpg` / `blog-*.jpg` / `hero-main.jpg` / `category-*.jpg` — 実写素材、名前付き別人物、テーマ別
- イラストレイヤー: `illust-job-*.png` / `illust-{philosophy,flow,numbers}.jpg` — メインキャラ (or 概念) を表現

新キャラ刷新はイラストレイヤーのみに作用する。写真レイヤーは触らない。

## IN スコープ (12 枚)

| # | ファイル | 現状 | 対応 | 状態 |
|---|---------|------|------|-----|
| 1 | `illust-job-care.png` | 歩行介助シーン、黒ポロ、青ランヤード + 青アクセント背景 | **完了 (2026-07-02、Image #5 採用)** | ✅ 配置済 |
| 2 | `illust-job-consultant.png` | 相談員 (旧 V-neck scrub 版が Round α で merged、要 polo 再生成) | ChatGPT UI で再生成 | 🔄 UI 待ち |
| 3 | `illust-job-nurse.png` | 訪問看護 (旧 V-neck scrub 版が Round α で merged、要 polo 再生成) | ChatGPT UI で再生成 | 🔄 UI 待ち |
| 4 | `illust-job-office.png` | 事務 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 5 | `illust-job-it.png` | IT / システム | ChatGPT UI で生成 | 🔄 UI 待ち |
| 6 | `illust-job-care-2.png` | care variant 2 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 7 | `illust-job-care-3.png` | care variant 3 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 8 | `illust-job-default.png` | fallback 汎用 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 9 | `illust-job-consultant-2.png` | 相談員 variant 2 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 10 | `illust-job-office-2.png` | 事務 variant 2 | ChatGPT UI で生成 | 🔄 UI 待ち |
| 11 | `illust-philosophy.jpg` | 3 人物フラットベクター (ターコイズスクラブ介護士 + 車椅子高齢者 + 家族) | ChatGPT UI で再生成 (メインキャラを黒ポロに置換、複数人シーン維持) | 🔄 UI 待ち |
| 12 | `illust-flow.jpg` | 2 人物フラットベクター (ターコイズスクラブ介護士 + 応募者) | ChatGPT UI で再生成 (メインキャラを黒ポロに置換、面接シーン維持) | 🔄 UI 待ち |

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

旧 baseline PNG (履歴参照のみ):

```
.claude/memory/archive/illustration-baseline-2026-06-29.png                   # 最旧 (ターコイズスクラブ + 透明水彩)
.claude/memory/archive/illustration-baseline-character-closeup-2026-06-29.png # 最旧 close-up
.claude/memory/archive/illustration-baseline-2026-07-01.png                   # Phase 1.5 (V-neck scrub 版)
.claude/memory/archive/illustration-baseline-character-closeup-2026-07-01.png # Phase 1.5 close-up
```

現行 baseline: `.claude/memory/illustration-baseline.png` (2026-07-02 版 = Image #5 歩行介助シーン、黒ポロシャツ + 青ランヤード + 青アクセント背景)

## 進捗

- 2026-07-01: Phase 1 (Atomic 真理ソース更新)、Phase 1.5 (画風 + accessories rule) 完了
- 2026-07-02: 制服 spec pivot (V-neck scrub → 黒ポロシャツ)、生成経路 pivot (API → ChatGPT UI)、Round α care 完了 (Image #5 採用)
- 次: Round β/γ の 11 枚を ChatGPT UI で生成 → 集まり次第 Phase 4 (mockup 反映 + PR)
