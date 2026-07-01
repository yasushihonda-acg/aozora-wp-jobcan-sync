---
name: reference-illustration-baseline
description: aozora-wp-jobcan-sync プロジェクト唯一のメインキャラクター + 画風 + トンマナ基準 (2026-07-02 決裁者最終指示、制服 spec を黒ポロシャツに pivot + ChatGPT UI 経路に統一)
metadata:
  type: reference
---

# プロジェクトメインキャラクター + 画風基準 (2026-07-02 決裁者最終指示)

## 最重要原則 (最終版)

**baseline PNG `illustration-baseline.png` (Image #5 = 歩行介助シーン、黒ポロシャツ + 青ランヤード + ID badge、明るい介護施設内装) を新規生成の identity reference として ChatGPT UI 会話に必ず添付する。** キャラクター・絵のタッチ・色調・トンマナ全てが基準。

決裁者指示 (2026-07-02):
- 制服は「黒のポロシャツ」で確定 (旧 Phase 1.5 の V-neck scrub は廃止)
- 青は差し色として使う (名札・ストラップ・背景アクセント・小物・施設内装の一部)
- キャラは介護スタッフにも相談員にも事務にも採用広報にも使える汎用性のある女性キャラクター
- 「やりがい搾取ではなく、ケアスタッフにやりがいと経済的豊かさを」の思想に合う洗練感

つまり:
- ✅ MUST: キャラクター (顔・髪・眼鏡・体格) を厳密に一致
- ✅ MUST: 絵のタッチ (**現代的でおしゃれな日本のエディトリアル系イラスト、細い線、清潔感、少しレトロポップ、都会的、介護求人に合う温かさ、雑誌の挿絵や採用サイトのキービジュアルに使える洗練された雰囲気**)。実在作家の画風を直接指定しない
- ✅ MUST: 色調 (**warm peach 肌、黒ポロシャツ、blue lanyard アクセント、白〜淡ベージュ背景、コーポレートカラー #00C4CC を差し色として自然に配置**)
- ✅ MUST: 全体トンマナ (清潔感、知的・親しみ、大人の落ち着き、過剰な装飾なし、editorial elegance)
- ✅ MUST: **アクセサリー職種別ルール**: care / nurse ではピアス NG、consultant / office / it は小スタッド OK。詳細は `.claude/skills/aozora-illust/prompts/outfit-spec.txt` ACCESSORIES RULES
- 🟢 OK: シーン (利用者様の年齢/服装、背景の小道具、職務動作)
- 🟢 OK: 服装の派生 (**黒ポロシャツ既定**、consultant/office はニュートラルカーディガン重ね着可、it はテーラードジャケット重ね着可)

## 基準ファイル

| ファイル | 内容 |
|--------|-----|
| `.claude/memory/illustration-baseline.png` | フルシーン基準 (2026-07-02 版 = Image #5: 歩行介助シーン、黒ポロシャツ + 青ランヤード + ID badge、明るい介護施設内装 + 青アクセント背景) |
| `.claude/memory/archive/illustration-baseline-2026-07-01.png` | 旧 Phase 1.5 baseline (立ち姿、V-neck scrub 版、履歴参照のみ) |
| `.claude/memory/archive/illustration-baseline-character-closeup-2026-07-01.png` | 旧 Phase 1.5 close-up (履歴参照のみ) |
| `.claude/memory/archive/*-2026-06-29.png` | 最旧 baseline (ターコイズスクラブ + 透明水彩、履歴参照のみ) |

**注**: 2026-07-02 版では close-up baseline は未生成 (Image #5 のみ)。identity drift が生じた場合は次セッションで decision-maker と協議して close-up を用意する。

## メインキャラクター仕様 (Image #5 準拠)

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
- **subtle shading あり** (フラット塗りではない、顔輪郭・首元に軽い陰影)

### 眼鏡 (キャラ識別要素)
- **べっ甲フレーム** (tortoiseshell、茶色 + 黒の斑模様、まだら)
- **丸めの太縁** (medium-thick rim)、レンズはラウンド気味のオーバル
- ブリッジは細め、テンプル (つる) も細め
- 鼻パッド可視

### 髪
- 黒髪 (純黒〜墨色)、**繊細なハイライト複数** (subtle highlights, not flat, not glossy)
- **低めの位置でゆるくまとめたバン (お団子)**、後頭部下部に小さくまとめる、後れ毛が自然に
- 前髪: 分け目から左右にふんわり、額が少し見える程度、**軽くウィスピーな束感**
- **顔まわりに繊細な後れ毛が複数本** (耳の前 2-3 本、額の左右、こめかみ付近)
- 髪の毛束は細い個別線で描画、塗りつぶしではない

### 耳・装飾
- 職種別ルールに従う (下記参照)。care/nurse ではピアス描画なしが理想

### 表情バリエーション (許容範囲)
- 微笑 (上歯少し見せ) ← baseline 既定
- 真顔・伏目 (考え込み・記入時)
- やや横向き・斜め (3/4 view)
- 笑顔 (歯を多く見せる) ← 控えめに留める
- 上記すべて、目の形・眉・鼻・口角・後れ毛・眼鏡のパターンは保持必須

### 体格・印象
- 細身でほっそりした体格
- 知的・落ち着き・親しみ
- 介護・医療事業者の「相談しやすいプロ」イメージ

### 服装 (既定: 黒ポロシャツ)
- **BLACK 半袖ポロシャツ** (襟 + 2-3 button placket、pure black or very dark charcoal、無地、パイピング/トリムなし)
- **BLUE ランヤード** (鮮やかな青、cobalt / royal blue 系) + 透明ケースの ID カード (胸元)
- 半袖、任意で胸ポケット 1 つ
- 手には状況に応じて小道具 (タブレット / クリップボード / ノート PC / 小物)

職種派生 (許容):
- 事務シーン: 黒ポロの上にニュートラルカーディガン (charcoal / beige)
- 経営/管理シーン: テーラードジャケット (charcoal / navy / beige) を黒ポロに重ね着
- IT シーン: テーラードダーク navy or charcoal blazer を黒ポロに重ね着
- ブログ・カジュアル: 黒ポロのみ、ランヤードなしも可
- ※派生時も顔・髪・眼鏡は完全一致 (ピアスは職種別ルールに従う)

### アクセサリー職種別ルール (2026-07-02 決裁者指示)

**共通 (全職種で絶対 NG)**: hoop / drop / dangle 系ピアス。生成物にこれが描画された場合は再生成対象。

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

## 画風 (2026-07-02 決裁者最終指示)

- **現代的でおしゃれな日本のエディトリアル系イラスト**
- **細い線、清潔感、少しレトロポップ、都会的、介護求人に合う温かさ**
- **雑誌の挿絵や採用サイトのキービジュアルに使える洗練された雰囲気**
- **cel-shading は最小限** (mostly flat with only subtlest tonal work — 顎下・首元の陰影と髪の thin highlight strokes のみ、glossy shine は NG)
- **crisp clean edges** (線・色のにじみは最小、シャープ)
- **少し elongated で elegant な proportion** (大人の refined 感、chibi/anime 幼型 NG)
- **color temperature: 暖色寄り** (warm peach 肌、warm coral lips、暖かい表情)
- **background: 白、淡ベージュ、僅かな緑の hint** (シンプル、キャラを引き立てる、複雑な背景 NG)
- **NG**: アニメっぽすぎる大きな目、子どもっぽいキャラクター、派手すぎる装飾、医療ドラマ風の過剰演出、古い介護施設の暗い雰囲気、青い制服、白衣っぽすぎる表現、読めない文字や不自然な日本語テキスト、ロゴや文字の無理な生成、**実在作家の画風をそのまま模倣する表現**

## コーポレートカラー (自然に馴染ませる)

| 色 | HEX | 使い方 |
|----|-----|--------|
| ブルー | `#00C4CC` | 差し色 (名札・ストラップ・背景アクセント・施設内装の一部) |
| グレー | `#575656` | 文字・小物・落ち着いた影色 |
| ベージュ | `#f8f5ee` | 背景・空間のやさしいベース |

**機械的なベタ塗りではなく、自然に馴染ませる**。

## 副役・小道具 (柔軟可だが画風統一)

- 利用者様 (高齢者、淡いベージュ系の柔らかい服装、白髪)
- 同僚スタッフ (色違いのポロ or 同色)
- 応募者 (若い日本人、カジュアル〜professional 寄り)
- 家族 (中年日本人、warm な家族らしい服装)
- 小道具: タブレット / クリップボード / カルテ / ラップトップ / 観葉植物 / 木製家具 / 車椅子 / 医療キット等

## 用途

- カテゴリ別求人カードのサムネ (care / nurse / office / it / 相談 / 事務 / その他)
- 求人詳細ページ hero 画像
- index ページの挿絵 (hero / philosophy / numbers / flow / staff intro)
- 採用ブログのアイキャッチ (将来)

## How to apply (2026-07-02 更新: ChatGPT UI 経路)

**MUST**: character-critical illustration は **ChatGPT UI 経路** で生成する。API `v1/images/edits` は identity 再現限界で non-recommended (本セッション 8 回試行後実証)。

**運用**:
1. ChatGPT UI で新規会話を開く
2. `docs/specs/chatgpt-ui-prompts.md` の PREAMBLE をコピペ
3. 生成対象の SCENE ブロックをコピペ
4. `illustration-baseline.png` (Image #5) を UI 会話に添付 (identity drift 最小化)
5. 生成物を Claude に送信 → 10 項目採点 → mockup 配置 + PR
6. **1 会話 = 1 illustration** で運用 (同一会話で複数生成すると identity drift の可能性)

**aozora-illust スキル** は人物なし挿絵 (illust-numbers 等) or 実験用途に保持。

## 10 項目 Pass/Fail 検証チェックリスト

新規生成物の採用可否は、以下 10 項目 **すべて Pass** が条件:

| # | 項目 | Pass 基準 |
|---|------|----------|
| 1 | 顔 (目・鼻・口・輪郭) | baseline と目視同一 (アーモンド細長目、下がり目、微笑、oval face with tapered jaw) |
| 2 | 髪 | 黒髪 + 低い位置のシニヨン + 後れ毛 + ウィスピーバング + subtle highlights |
| 3 | 眼鏡 | べっ甲丸縁太フレーム、レンズはラウンドオーバル |
| 4 | 年齢感 | 20 代後半〜30 代前半、大人の落ち着き (幼く見えない) |
| 5 | 衣装 | **黒ポロシャツ (襟 + ボタン)** + **青ランヤード + ID badge** (職種別派生 OK: カーディガン / ジャケット重ね着) |
| 6 | 画風 | 現代的おしゃれエディトリアル、細い線、清潔感、雑誌挿絵レベルの洗練感 (フラット水彩 NG、ベクター NG、アニメ調 NG、青い制服 NG) |
| 7 | 手指 | 破綻なし (6 本指・融合・不自然な曲がり NG) |
| 8 | 文字混入 | 画像内にテキスト・ロゴ・シンボルなし (シーンの必要小道具のみ) |
| 9 | 職務内容整合 | シーン記述 (nurse=医療、office=デスク、care=介護 action 等) と描画内容が一致 |
| 10 | クロップ | 用途アスペクト比 (16:9 / 4:5 / 16:10) に耐える構図、主要要素が中央付近 |

全項目 Pass で採用。1 項目でも Fail は再生成 or シーン記述側で局所調整。

## ユーザーフィードバック履歴

| 回 | 日付 | フィードバック | 反映 |
|----|------|--------------|-----|
| 1 | 2026-06-29 | 「江口寿史風で」 | プロンプトに江口寿史キーワード追加 |
| 2 | 2026-06-29 | 「むしろ参考画像のまますすめて」 | 江口寿史撤回、水彩寄りに |
| 3 | 2026-06-29 | 「これを覚えて (nurse)」 | nurse を baseline 指定 |
| 4 | 2026-06-29 | 「Image #13 #14 は違う」 | care/office を水彩強化で再生成 |
| 5 | 2026-06-29 | 「キャラクターが主役、画風は柔軟可」 | 一時的に画風を柔軟化 |
| 6 | 2026-06-29 | 「絵のタッチも全て覚えて。この絵以外は全て駄目」 | 画風も baseline 厳密一致に確定 (旧 baseline) |
| 7 | 2026-07-01 | 決裁者「このキャラの顔とタッチを完全再現、今できていないので全てやり直し」 | baseline PNG 差替 (黒 V-neck scrub + blue lanyard + polished anime touch)、全 spec 刷新 |
| 8 | 2026-07-01 | 決裁者「江口寿史風エディトリアル」 | Phase 1.5 で画風を polished anime → editorial thin-line に精緻化 + 職種別アクセサリールール |
| 9 | **2026-07-02** | **決裁者「制服は黒のポロシャツで」「実在作家の画風を直接指定しない」「コーポレートカラー #00C4CC #575656 #f8f5ee を自然に馴染ませる」** | **制服 spec pivot (V-neck scrub → polo shirt)、画風スペックから江口寿史等の作家名を除外、コーポレートカラー明示、baseline PNG を Image #5 (歩行介助シーン) に差替、生成経路を ChatGPT UI に統一** |

## baseline 差分サマリ (2026-06-29 → 2026-07-01 → 2026-07-02)

| 項目 | 2026-06-29 版 | 2026-07-01 版 (Phase 1) | 2026-07-01 版 (Phase 1.5) | **2026-07-02 版 (現行)** |
|------|--------------|----------------------|------------------------|-----------------------|
| 服装 | ターコイズ V ネックスクラブ + 白パイピング + 白 ID ストラップ | 黒 V-neck スクラブ + 青 lanyard | 継続 | **黒ポロシャツ (襟 + ボタン) + 青 lanyard + ID badge** |
| 画風 | 透明水彩淡彩、フラット塗り | polished anime/manga touch | editorial magazine illustration (江口寿史 esque) | **現代的おしゃれエディトリアル、細い線、清潔感、雑誌挿絵レベルの洗練感 (作家名を直接指定しない)** |
| パレット anchor | ターコイズ `#00c4cc` | 黒 scrub + 青 lanyard 対比 | 継続 | **コーポレートカラー明示: `#00C4CC` (差し色) + `#575656` (影) + `#f8f5ee` (背景ベース)** |
| baseline PNG | 多人数タブレット相談シーン | 立ち姿 solo full-body portrait | earring 除去 patch 版 | **Image #5 = 歩行介助シーン (青アクセント背景、黒ポロ)** |
| close-up PNG | あり | あり | earring 除去 patch 版 | **未生成 (identity drift 生じた場合に用意)** |
| 生成経路 | API `v1/images/edits` + baseline reference | 継続 | 継続 | **ChatGPT UI 経路** (API は identity 保持限界で非採用) |
| 顔・髪・眼鏡 | 継続 | 継続 | 継続 | 継続 |
| ピアス | identity lock | identity lock | 職種別ルール、identity lock から除外 | 継続 |
