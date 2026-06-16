# Design Tokens (仮案 v0.1)

> Phase A 着手前に、決裁者と「色・フォント・余白・ボタン・写真トーン」を 1 枚で握るためのドラフト。`aozora-cg.com` 実物のスクショ取得後 (Phase A 内タスク) に v0.2 で確定する。

## 確定済 / 仮 / TBD

| 区分 | 項目 | 状態 |
|---|---|---|
| 確定 | 公開ドメイン | `recruit.aozora-cg.com` |
| 仮 | アクセント色 | `--color-accent: #00c4cc` (wp-acg-hp 由来) — 実物比較で要再判定 |
| TBD | 実物 aozora-cg.com の Primary/Accent カラー (グレートーン基調らしい) | スクショ取得 → 抽出 |
| TBD | フォント (実物 metadata) | WebFetch / DevTools で確認 |

## 1. 色 (仮)

```css
/* Brand */
--color-primary:        #1a1a1a;       /* テキスト / 見出し基調 (wp-acg-hp 由来) */
--color-accent:         #00c4cc;       /* CTA / リンク (要再判定) */
--color-accent-dark:    #00a8b0;       /* ホバー / アクティブ */
--color-accent-light:   #e6f9fa;       /* バッジ背景 / 強調パネル */

/* Semantic */
--color-text:           #1a1a1a;
--color-text-muted:     #5c6266;
--color-text-on-dark:   #ffffff;
--color-bg:             #ffffff;
--color-bg-alt:         #f6f7f9;       /* セクション交互背景 */
--color-border:         #e3e5e8;
--color-success:        #2f9e4f;
--color-warning:        #d96a4a;       /* 「新着」「募集中」バッジ (wp-acg-hp `--color-new`) */
--color-danger:         #c83232;
```

採用予定パレット (例):
- 本文: `#1a1a1a` on `#ffffff`
- セクション区切り: `#f6f7f9`
- CTA ボタン: `#00c4cc` 背景 / 白文字、ホバーで `#00a8b0`
- バッジ「新着」: `#d96a4a` 背景

## 2. フォント

```css
--font-base:    "Noto Sans JP", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
--font-heading: "Noto Sans JP", system-ui, sans-serif; /* 同一ファミリーで weight だけ変える */

/* Weight */
--weight-regular: 400;
--weight-medium:  500;
--weight-bold:    700;

/* Size scale (rem, ベース 16px) */
--text-xs:    0.75rem;   /* 12 */
--text-sm:    0.875rem;  /* 14 */
--text-base:  1rem;      /* 16 */
--text-lg:    1.125rem;  /* 18 */
--text-xl:    1.25rem;   /* 20 */
--text-2xl:   1.5rem;    /* 24 */
--text-3xl:   1.875rem;  /* 30 */
--text-4xl:   2.25rem;   /* 36 */
--text-5xl:   3rem;      /* 48 (PC ヒーロー) */

/* Line height */
--lh-tight:  1.25;
--lh-normal: 1.6;
--lh-loose:  1.85;
```

## 3. 余白スケール

```css
--space-1:  0.25rem;  /* 4  */
--space-2:  0.5rem;   /* 8  */
--space-3:  0.75rem;  /* 12 */
--space-4:  1rem;     /* 16 */
--space-5:  1.5rem;   /* 24 */
--space-6:  2rem;     /* 32 */
--space-8:  3rem;     /* 48 */
--space-10: 4rem;     /* 64 */
--space-12: 6rem;     /* 96 (大セクション間) */
```

## 4. レイアウト

```css
--container-max:   1200px;
--container-pad:   1.25rem;
--header-h:        80px;
--header-h-mobile: 60px;
--radius-sm:       6px;
--radius-md:       12px;
--radius-lg:       20px;
--shadow-card:     0 4px 16px rgba(20, 20, 30, 0.06);
--shadow-cta:      0 6px 18px rgba(0, 196, 204, 0.25);
```

## 5. ボタン

| 種別 | 用途 | サイズ |
|---|---|---|
| Primary | エントリー CTA / 応募ボタン | h=52px (PC) / 48px (mobile) |
| Secondary | カード内「詳細を見る」 | h=44px |
| Ghost | フィルタ "クリア" 等 | h=36px |
| Pill | カテゴリーバッジ | h=24-28px |

例:
```css
.btn-primary {
  height: 52px;
  padding: 0 var(--space-6);
  background: var(--color-accent);
  color: #fff;
  border-radius: var(--radius-md);
  font-weight: var(--weight-bold);
  box-shadow: var(--shadow-cta);
}
.btn-primary:hover { background: var(--color-accent-dark); }
```

## 6. 写真トーン (要決裁合意)

- **人物**: 笑顔・自然光・施設内 / 訪問先での実シーン (ステージング撮影は避ける) — 介護のリアルが伝わる
- **施設**: 明るく清潔感、無人で空間構造が分かるアングル
- **配色加工**: 大幅な色加工は避け、自然色のまま。アクセント色のオーバーレイは使わない
- **アスペクト**: ヒーロー 16:9 / 21:9、カード 4:3、サムネ 1:1

→ 実素材は未確定 #7 (新規撮影 or 既存流用) で確定する

## 7. アクセシビリティ

- コントラスト比: 本文 4.5:1 以上、CTA 7:1 以上
- フォーカスリング: 2px solid `--color-accent` + outline-offset 2px、`:focus-visible` で表示
- alt 属性は必須、装飾画像は `alt=""`
- フォーム入力は label を明示

## 8. v0.2 で確定すること (TBD)

- [ ] `aozora-cg.com` 実物スクショから Primary / Accent / Background の hex 抽出
- [ ] 実物のフォントファミリー確認 (Noto Sans JP かどうか)
- [ ] 実物の見出しスタイル (sub-heading の英字併用パターン等)
- [ ] 写真素材方針 (新規撮影 or 既存流用)
- [ ] CTA 色の決裁者承認 (シアン継続 or グレートーン寄せ)
