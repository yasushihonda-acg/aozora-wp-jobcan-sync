---
name: reference-illustration-baseline
description: aozora-wp-jobcan-sync プロジェクト唯一のメインキャラクター + 画風 + トンマナ基準 (2026-07-01 決裁者最終指示で全面刷新)
metadata:
  type: reference
---

# プロジェクトメインキャラクター + 画風基準 (2026-07-01 決裁者最終指示)

## 最重要原則 (最終版)

**baseline 2 枚 (`illustration-baseline.png` フルシーン + `illustration-baseline-character-closeup.png` 顔クローズアップ) を 100% 踏襲する。**
キャラクター・絵のタッチ・色調・トンマナ全てが基準。逸脱した試作は採用不可。

決裁者指示 (2026-07-01):
> 「このキャラクターの顔やタッチを完全再現する必要があり、
> 今のまだそれが出来ていないので全てやり直し。」

つまり:
- ✅ MUST: キャラクター (顔・髪・眼鏡・体格) を厳密に一致
- ✅ MUST: 絵のタッチ (**editorial magazine illustration in the vein of Eguchi Hisashi 江口寿史、極めて繊細で優雅な細線、cel-shading 最小限、magazine printed feel**)
- ✅ MUST: 色調 (**warm peach 肌、black scrub、blue lanyard アクセント、白〜淡ベージュ背景**)
- ✅ MUST: 全体トンマナ (清潔感、知的・親しみ、大人の落ち着き、過剰な装飾なし、editorial elegance)
- ✅ MUST: **アクセサリー職種別ルール** (2026-07-01 決裁者指示): care / nurse ではピアス NG、consultant / office / it は小スタッド OK。詳細は `.claude/skills/aozora-illust/prompts/outfit-spec.txt` ACCESSORIES RULES
- 🟢 OK: シーン (利用者様の年齢/服装、背景の小道具、職務動作)
- 🟢 OK: 服装の細部 (**BLACK V ネックスクラブ既定**、職種により襟付き等の派生は許容)

## 基準ファイル

| ファイル | 内容 |
|--------|-----|
| `.claude/memory/illustration-baseline.png` | フルシーン基準 (立ち姿、黒 scrub、blue lanyard + ID badge、タブレット/クリップボード保持) |
| `.claude/memory/illustration-baseline-character-closeup.png` | 顔クローズアップ基準 (斜め横向き、微笑、淡い水色空 + 若干の緑) |
| `.claude/memory/archive/*-2026-06-29.png` | 旧 baseline (2026-06-29 版、ターコイズスクラブ + 透明水彩、参照履歴のみ) |

## メインキャラクター仕様 (顔造形 — Image #6 close-up 詳細観察)

### 全体
- 日本人女性、**20 代後半〜30 代前半 (mature, composed, intelligent, approachable)**
- 柔らかい卵型の輪郭、顎は細く優雅にすぼまる (gracefully tapered jaw)
- 頬骨にうっすら定義 (subtle cheekbone)、丸顔ではない
- 印象: **知的・落ち着き・控えめな大人っぽさ + 親しみやすさ** (無邪気・幼さ NG)

### 眼 (最重要識別要素)
- **細長めのアーモンド型** (丸すぎない、大きすぎない、若々しすぎない)
- 瞳: 明るい茶色 (warm brown)、瞳孔は黒、繊細なハイライト 1 点
- **目尻がやや下がる** (softly downturned outer corners、優しい大人の印象の要因)
- 二重幅は浅い〜奥二重 (くっきりした二重ではない)
- 上まぶたに繊細なまつ毛 (細い短い線で表現、束感はなし)
- 白目部分は清く、虹彩の輪郭線はくっきり描かれる
- 視線: viewer 向きの正面 or やや斜め、温かく落ち着いた目線

### 眉
- 細く短く整っている (細眉)
- 控えめな緩いアーチ、眉尻は自然に下がる
- 眉色は黒、線で軽く表現

### 鼻
- 高さ控えめ、線で軽く示唆 (鼻筋を強調しない)
- 鼻先は小さく丸い
- 鼻翼に淡い影

### 口
- 控えめな微笑、**上歯がほんの少し覗く程度** (歯列を見せない、下歯は絶対に見せない、grin は絶対 NG)
- 上唇は薄め、下唇はふっくら
- リップ: 自然なピンク〜サーモン (warm coral pink)、控えめ
- 口角は左右やや上がる、左右対称
- ※「無邪気な子供の笑顔」ではなく「落ち着いた大人の微笑」

### 頬・肌
- 暖色 (warm peach)、清潔感、柔らかい質感
- 頬に淡いピンクの紅潮 (僅か、ぼかし)
- **subtle shading あり** (透明水彩フラットではない、顔輪郭・首元に軽い陰影)

### 眼鏡 (キャラ識別要素)
- **べっ甲フレーム** (tortoiseshell、茶色 + 黒の斑模様、まだら)
- **丸めの太縁** (medium-thick rim)、レンズはラウンド気味のオーバル
- ブリッジは細め、テンプル (つる) も細め
- 鼻パッド可視

### 髪
- 黒髪 (純黒〜墨色)、**光沢のある繊細なハイライト複数** (subtle glossy highlights, not flat)
- **低めの位置でゆるくまとめたバン (お団子)**、後頭部下部に小さくまとめる、後れ毛が自然に
- 前髪: 分け目から左右にふんわり、額が少し見える程度、**軽くウィスピーな束感**
- **顔まわりに繊細な後れ毛が複数本** (耳の前 2-3 本、額の左右、こめかみ付近)
- 髪の毛束は細い個別線で描画、塗りつぶしではない

### 耳・装飾
- **小さな金のフープピアス or ドロップピアス** (右耳側に見えれば OK)

### 表情バリエーション (今後の生成で許容する範囲)
- 微笑 (上歯少し見せ) ← baseline 既定
- 真顔・伏目 (考え込み・記入時)
- やや横向き・斜め (3/4 view) ← close-up baseline はこれ
- 笑顔 (歯を多く見せる) ← 控えめに留める
- 上記すべて、目の形・眉・鼻・口角・後れ毛・眼鏡のパターンは保持必須

### 体格・印象
- 細身でほっそりした体格
- 知的・落ち着き・親しみ
- 介護・医療事業者の「相談しやすいプロ」イメージ

### 服装 (既定: BLACK V ネックスクラブ)
- **BLACK V ネックスクラブ** (pure black or very dark charcoal、無地、パイピング/トリムなし)
- **BLUE ランヤード** (鮮やかな青、cobalt / royal blue 系) + 透明ケースの ID カード (胸元)
- 短袖、胸ポケット 1 つ (baseline に沿って)
- 手には状況に応じてタブレット・クリップボード・ノート PC 等

職種派生 (許容):
- 事務シーン: 黒スクラブの上にニュートラルカーディガン (charcoal / beige)
- 経営/管理シーン: テーラードジャケット (charcoal / navy / beige) を黒スクラブに重ね着
- ブログ・カジュアル: 黒スクラブのみ、ランヤードなしも可
- ※派生時も顔・髪・眼鏡は完全一致 (ピアスは職種別ルールに従う)

### アクセサリー職種別ルール (2026-07-01 決裁者指示、介護業界の一般的な服装規定準拠、Phase 1.5 で reference-based generation の制約を踏まえた実務的緩和版)

**共通 (全職種で絶対 NG)**: hoop / drop / dangle 系ピアス (認知症の利用者に引っ張られるリスク、医療安全、印象上の unprofessionalism)。生成物にこれが描画された場合は再生成対象。

| 職種 | ピアス | ネイル | ウォッチ | リング |
|------|-------|--------|---------|-------|
| **care / care-2 / care-3** | 描画されない方が理想。**極小 stud (dot-size, close to earlobe)** まで許容。hoop/dangle 絶対 NG | 短く、装飾 NG | NG (ゴム/シリコンのみ) | NG |
| **nurse (訪問看護含む)** | 同上 (nothing 理想、極小 stud まで許容、hoop/dangle 絶対 NG) | 短く、装飾 NG | 医療用のみ or NG | NG |
| **consultant / consultant-2** | 小 stud OK (subtle, close-to-ear) | 落ち着いた色 OK | OK | active-work hand は NG |
| **office / office-2** | 小 hoop/drop OK (subtle) | OK | OK | 小さめ OK |
| **it** | 小 hoop/drop OK | OK | OK | OK |
| **default (fallback)** | care と同じ | 短く | 控えめ | NG |
| **philosophy / flow 挿絵** | シーンの役割による (介護シーンでは nothing 理想 or 極小 stud、相談シーンでは小 stud OK) | 同上 | 同上 | 同上 |

**identity locks から earring を除外** (顔・髪・眼鏡・目・輪郭・肌の 6 点のみ)。ピアスはシーン記述で明示された時のみ描画、なければ非描画が既定。

**Baseline PNG 側の対応 (2026-07-01 Phase 1.5)**: `illustration-baseline.png` と `illustration-baseline-character-closeup.png` の元画像に earring が描画されていたため、reference-based generation で inherit されないよう **canvas patch で耳付近を bare 化**した (`archive/*-2026-06-29.png` に旧版保管)。identity にはほぼ影響なし (顔・髪・眼鏡・skin tone は保持)。

## 画風 (厳密一致、2026-07-01 決裁者指示で editorial illustration 方向に精緻化)

決裁者指定の雰囲気イメージ (Image #7/#8) に基づく画風スペック:
- **editorial magazine illustration in the vein of Eguchi Hisashi (江口寿史)** — 洗練された誌面 illustration の空気感、magazine printed feel
- **極めて繊細で優雅な細線** (extremely thin refined pen-work、機械的でも厚くもない、editorial pen-drawing quality)
- **cel-shading は最小限** (mostly flat with only subtlest tonal work — 顎下・首元の陰影と髪の thin highlight strokes のみ、glossy shine は NG)
- **crisp clean edges** (線・色のにじみは最小、シャープ)
- **少し elongated で elegant な proportion** (大人の refined 感、chibi/anime 幼型 NG)
- **color temperature: 暖色寄り** (warm peach 肌、warm coral lips、暖かい表情)
- **background: 白、淡ベージュ、僅かな緑の hint** (シンプル、キャラを引き立てる、複雑な背景 NG)
- **NG**: 過度な透明水彩ぼかし、フラットベクター簡略化、アニメ調の巨大黒目、油彩風厚塗り、3D 風シェーディング、commercial anime 寄り (thick outline + glossy shading)

## 副役・小道具 (柔軟可だが画風統一)

- 利用者様 (高齢者、淡いベージュ系の柔らかい服装、白髪)
- 同僚スタッフ (色違いスクラブ or 同色)
- 小道具: タブレット / クリップボード / カルテ / ラップトップ / 観葉植物 / 木製家具

## 用途

- カテゴリ別求人カードのサムネ (care / nurse / office / it / 経営 / その他)
- 求人詳細ページ hero 画像
- index ページの挿絵 (hero / philosophy / numbers / flow / staff intro)
- 採用ブログのアイキャッチ (将来)

## How to apply

**MUST**: テキストプロンプトのみの `v1/images/generations` は使用禁止。同一キャラクター再現が原理的に困難 (2026-06-29 実証)。

**唯一の正解手法**: `.claude/skills/aozora-illust/` スキル経由で `v1/images/edits` を使い、baseline 2 枚 (`illustration-baseline.png` + `illustration-baseline-character-closeup.png`) を `image[]` に渡す reference-based generation。

## 10 項目 Pass/Fail 検証チェックリスト

新規生成物の採用可否は、以下 10 項目 **すべて Pass** が条件:

| # | 項目 | Pass 基準 |
|---|------|----------|
| 1 | 顔 (目・鼻・口・輪郭) | close-up baseline と目視同一 (アーモンド細長目、下がり目、微笑) |
| 2 | 髪 | 黒髪 + 低い位置のシニヨン + 後れ毛 + ウィスピーバング + glossy highlights |
| 3 | 眼鏡 | べっ甲丸縁太フレーム、レンズはラウンドオーバル |
| 4 | 年齢感 | 20 代後半〜30 代前半、大人の落ち着き (幼く見えない) |
| 5 | 衣装 | BLACK V ネックスクラブ + BLUE lanyard + ID badge (指定シーンで allowed 派生あれば派生も OK) |
| 6 | 画風 | polished anime/manga touch、fine detailed linework、subtle shading (フラット水彩 NG、ベクター NG) |
| 7 | 手指 | 破綻なし (6 本指・融合・不自然な曲がり NG) |
| 8 | 文字混入 | 画像内にテキスト・ロゴ・シンボルなし (シーンの必要小道具のみ) |
| 9 | 職務内容整合 | シーン記述 (nurse=医療、office=デスク、care=食事介助 等) と描画内容が一致 |
| 10 | クロップ | 用途アスペクト比 (16:9 / 4:5 / 16:10) に耐える構図、主要要素が中央付近 |

Round B (キャラ検証) 以降は本チェックリストで全項目を Pass 判定してから承認。

## ユーザーフィードバック履歴

| 回 | 日付 | フィードバック | 反映 |
|----|------|--------------|-----|
| 1 | 2026-06-29 | 「江口寿史風で」 | プロンプトに江口寿史キーワード追加 |
| 2 | 2026-06-29 | 「むしろ参考画像のまますすめて」 | 江口寿史撤回、水彩寄りに |
| 3 | 2026-06-29 | 「これを覚えて (nurse)」 | nurse を baseline 指定 |
| 4 | 2026-06-29 | 「Image #13 #14 は違う」 | care/office を水彩強化で再生成 |
| 5 | 2026-06-29 | 「キャラクターが主役、画風は柔軟可」 | 一時的に画風を柔軟化 |
| 6 | 2026-06-29 | 「絵のタッチも全て覚えて。この絵以外は全て駄目」 | 画風も baseline 厳密一致に確定 (旧 baseline) |
| 7 | **2026-07-01** | **決裁者「このキャラの顔とタッチを完全再現、今できていないので全てやり直し」** | **baseline PNG 差替 (黒 scrub + blue lanyard + polished anime touch)、全 spec 刷新、全キャラ含みイラスト 12 枚 regenerate** |

## 旧 baseline との差分サマリ (2026-06-29 → 2026-07-01)

| 項目 | 2026-06-29 版 | 2026-07-01 版 (Phase 1) | 2026-07-01 版 (Phase 1.5、決裁者再指示) |
|------|--------------|----------------------|--------------------------------|
| 服装 | ターコイズ V ネックスクラブ + 白パイピング + 白 ID ストラップ | **BLACK V ネックスクラブ + BLUE lanyard + ID badge** | 継続 (Phase 1 と同) |
| 画風 | 透明水彩淡彩、フラット塗り、シェーディング最小 | polished anime/manga touch、fine detailed linework、subtle glossy shading | **editorial magazine illustration in the vein of Eguchi Hisashi、極めて繊細な細線、cel-shading 最小、magazine printed feel** |
| パレット anchor | ターコイズ `#00c4cc` | BLACK scrub + BLUE lanyard 対比 | 継続 (Phase 1 と同) |
| 背景 | 淡い緑背景、木製家具、ターコイズランプ/マグ | 白〜淡ベージュ minimal background、シーン別小道具のみ | 継続 (editorial illustration の空気感で更に簡素化) |
| 顔・髪・眼鏡 | 継続 | 継続 | 継続 (核となる特徴は不変) |
| ピアス | 継続 (identity lock) | 継続 (identity lock) | **職種別ルール**: care/nurse は NG、consultant/office/it は小スタッド OK。**identity lock から除外** |
