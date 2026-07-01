---
name: aozora-illust
description: aozora-wp-jobcan-sync メインキャラクターを厳密に再現してイラスト生成。baseline + close-up reference + 詳細プロンプトで edits API を叩く。本プロジェクト内のキャラ画像生成は必ず本スキル経由。
---

# aozora-illust

ACG 採用サイト用、メインキャラクターを厳密に再現して画像生成するプロジェクト内ハーネス。

## なぜ専用スキルか

- 単純な `gpt-image` (text-only `v1/images/generations`) では **同一キャラクター再現が原理的に困難** (2026-06-29 実証)。
- 唯一の正解手法 = `v1/images/edits` に baseline (full scene) + close-up (顔詳細) の 2 枚を `image[]` として渡し、詳細顔特徴プロンプトを併用する reference-based generation。
- 60+ 行のプロンプト断片 (face / style / outfit) を毎回手で書くと、ばらつき・抜けが発生する。本スキルで固定化する。

## 真理ソース

| ファイル | 役割 |
|---|---|
| `.claude/memory/reference_illustration_baseline.md` | キャラクター仕様 + 画風 + トンマナの **真理** (decision-maker 領分)。本スキルはここから派生 |
| `.claude/memory/illustration-baseline.png` | フルシーン baseline (立ち姿、黒 scrub + 青ランヤード + ID badge、タブレット/クリップボード保持) |
| `.claude/memory/illustration-baseline-character-closeup.png` | 顔クローズアップ baseline (斜め横向き、微笑) |
| `.claude/memory/archive/*-2026-06-29.png` | 旧 baseline (履歴参照のみ) |
| `prompts/face-spec.txt` | 顔造形プロンプト断片 (baseline.md から抽出) |
| `prompts/style-spec.txt` | 画風プロンプト断片 |
| `prompts/outfit-spec.txt` | 服装プロンプト断片 + 派生バリエーション |
| `scripts/gen.sh` | edits API ラッパー (リトライ + base64 デコード) |

**baseline 画像 2 点 (+ 履歴 archive) の差し替えは decision-maker (本田様) 領分。番号単位明示認可なしに改変禁止。**

## 使い方

### Phase 1: モード判定

呼び出し時に必ず確認:

- **single mode** (1 シーン 1 枚): `--mode=single --category=<key> --scene="<英語シーン記述>"`
  - 用途: カテゴリ別求人カード、index ページ挿絵、ブログアイキャッチ
  - 出力: `generated-images/gpt-image-<category>-<timestamp>.png` (1536x1024)
- **sheet mode** (6 パネル model sheet): `--mode=sheet`
  - 用途: 同一性検証、キャラ仕様レビュー、新規シーン展開前の角度・表情確認
  - 出力: `generated-images/gpt-image-character-sheet-<timestamp>.png` (1536x1024)

### Phase 2: シーン記述 (single mode)

英語で具体的に。以下の要素を含めると安定:

- 場所 (e.g. "modern Japanese eldercare facility dining room")
- 動作 (e.g. "reviewing a resident's care record on a tablet")
- 副役 (e.g. "elderly woman in pale beige cardigan seated at the table")
- 小道具 (e.g. "potted greenery, large window with soft daylight")

**キャラクター指定は不要** (face-spec.txt が自動付与)。
**服装変更時のみ** `--outfit="..."` で上書き。

#### Codex prompt rewriting (default ON、2026-06-30 PR #43 で導入)

`gen.sh` は default で `--codex-rewrite=on` で動作し、SCENE 文字列を **Codex (GPT-5.5) で ChatGPT UI 風に自動 rewrite** してから画像生成 API に渡す。

**実証された効果** (PR #43 比較実験):
- ChatGPT UI 直接生成と同等のクオリティが得られる
- 高齢者などの副役に "small, natural variations in pose, expression, age, and appearance" を自動付与
- 環境描写 (窓・植物・床・家具) を自然に拡張
- "candid, welcoming, lively, and professionally photographed" 等の雰囲気指定を自動追加
- 構図平準化 ("balanced visual emphasis across the entire group rather than a portrait-centered composition")

**コスト感覚**: Codex 1 call (~10s, 数 ¢) + 通常の画像生成。品質向上対比でほぼ無視できる差分。

**OFF にする場面**:
- `--mode=sheet` (6 パネル構図厳密指定が必要、自動で OFF 強制)
- SCENE が既に最適化済 (二重 rewrite 防止)
- Codex CLI 未インストール / Codex API 障害時 (gen.sh は自動 fallback)

### Phase 3: 実行

```bash
# 通常 (Codex rewriting on)
bash .claude/skills/aozora-illust/scripts/gen.sh \
  --mode=single \
  --category=office \
  --scene="modern eldercare facility back office, character at a wooden desk reviewing care records on a laptop, sunlight from the side window, potted plant in the background"

# Codex rewriting を明示 OFF (従来動作)
bash .claude/skills/aozora-illust/scripts/gen.sh \
  --mode=single \
  --category=office \
  --codex-rewrite=off \
  --scene="..."
```

または:

```bash
bash .claude/skills/aozora-illust/scripts/gen.sh --mode=sheet  # codex-rewrite は自動 OFF
```

長尺になるので **必ず `run_in_background=true` で実行**。完了通知が来てから保存先 PNG を Read で確認。

### Phase 4: 評価

baseline と並べて確認:

- ✅ 顔の同一性 (目の形・下がり目・口元・輪郭)
- ✅ 髪型 + 眼鏡 (べっ甲)、ピアスは職種別ルール準拠
- ✅ 衣装 (黒ポロシャツ + 青ランヤード + ID badge)
- ✅ 画風 (現代的エディトリアル、細い線、清潔感、雑誌挿絵レベルの洗練感)
- ✅ 色調 (暖色肌、warm coral lips、黒髪、白〜淡ベージュ背景、コーポレートカラー #00C4CC を差し色として自然に配置)
- ❌ テキスト混入なし
- ❌ 旧要素 (ターコイズスクラブ、V-neck scrub、透明水彩フラット塗り、フラットベクター) の混入なし

詳細は `.claude/memory/reference_illustration_baseline.md` の「10 項目 Pass/Fail 検証チェックリスト」参照。

ズレがあれば `prompts/*.txt` を更新せず、シーン記述側で局所調整して再実行 (prompts/ は真理由来なので軽率に変えない)。

### Phase 5: 採用判定

ユーザー (decision-maker) に baseline と並置して見せ、明示認可を得てから:

1. 採用イラストを `mockup/assets/img/illust-<用途>.png` にコピー
2. feature ブランチ → PR (番号単位明示認可形式で要約)

## NG パターン (やってはいけない)

- ❌ text-only `v1/images/generations` で「同じキャラっぽい」絵を生成して採用
- ❌ baseline 画像 2 点を断りなく差し替え
- ❌ prompts/*.txt を「もっと良くなりそう」で自己判断で改変
- ❌ シーン記述に「young」「cute」「3D」「flat vector」「watercolor」「turquoise scrub」を含める
- ❌ 1 ターンで複数カテゴリを直列実行 (並列化必須、コストと所要時間)

## コスト

- 1 枚 (1536x1024, quality=high): 約 USD 0.16
- model sheet (1536x1024 同設定): 約 USD 0.16

## 関連

- `.claude/memory/reference_illustration_baseline.md` — 仕様の真理
- `generated-images/preview.html` — 生成結果比較ビュー (port 8989)
- `~/.claude/skills/gpt-image/SKILL.md` — 汎用 gpt-image スキル (text-only 限定、本スキルが置き換える)
