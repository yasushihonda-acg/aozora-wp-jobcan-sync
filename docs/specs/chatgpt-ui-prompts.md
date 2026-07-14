# ChatGPT UI 生成用 プロンプト集 (2026-07-02)

mockup 内キャラ含みイラスト 12 枚 + ヒーロー背景 (キャラなし) 1 枚を ChatGPT UI (gpt-image) で生成する際のコピペ用テンプレート。API `v1/images/edits` の identity 保持限界により UI 経路に統一 (empirical、本セッションで確定)。

**2026-07-14 追加改訂**: 決裁者指示によりトップページのスタッフ紹介セクションを廃止し、philosophy (SCENE #11) / flow (SCENE #12) のイラストは「warm / 複数人物必須」の旧方針を撤回、求人カード群と同一の単独キャラクター・ポスタートーンに統一。併せてヒーロー背景 (SCENE #13、`sky-hero.jpg` を上書き) を新規追加し、トンマナは https://g-s.dev/ 的な大胆なポスター構図をより江口寿史風が活きる方向に寄せる。

## 使い方

1. ChatGPT UI で **新規会話** を開始
2. 下記「共通 PREAMBLE」を貼る
3. 続けて生成したい illustration の「SCENE」ブロックを貼る
4. 生成された画像を本田様が確認 → 私 (Claude) に送信 → 私が 10 項目採点 + ファイル配置 + mockup 反映 + commit

各 illustration は **独立した会話** で生成する。同一会話で複数生成すると context が汚れて identity drift する可能性あり。

## 共通 PREAMBLE (毎回冒頭に貼付)

**併せて添付**: `.claude/memory/illustration-baseline.png` (2026-07-14 版 = 決裁者指定 reference: シティポップ×無機質ポスター調、歩行付き添いシーン) を UI 会話にアタッチして "match this character's identity and this art style exactly" と明示すると drift 最小化。2026-07-14 以降は baseline が新画風そのものなので、**identity と画風の両方の参照**として使える。

**運用注意**:
- ChatGPT UI が実在作家名の指定を拒否した場合は、作家名の行を外し、続く具体的な画風記述 (細く均一な輪郭線 / フラットなセル塗り / シティポップ期ポスターイラスト等) のみで再実行する

```
あおぞらケアグループの求人サイト・採用サイトで使うイラストを生成してください。以下の条件を最優先で守ってください。

【目的】
あおぞらケアグループの求人サイトで使える、統一感のあるイメージキャラクターのイラスト。介護スタッフ、相談員、看護、事務、IT、採用面談、施設紹介、理念ページなど、いろいろな場面に差し込めるキャラクター。

【全体の世界観 (2026-07-14 決裁者指定)】
・シティポップ、さわやか、無機質
・ポスター的・広告的なビジュアル (採用ブランディングのキービジュアル)
・**「医療・介護 = 温かい、ほっこり」という固定観念のイメージは一切入れない**。介護特有の生活感・福祉感を排除する
・都会的、洗練、クール、清潔
・幼すぎず、大人っぽい
・働く人の誇りや専門性が伝わる
・「やりがい搾取」ではなく、「ケアスタッフにやりがいと経済的豊かさを」という思想に合う

【イラストの方向性】
イラストレーター江口寿史さんの画風に寄せてください (2026-07-02 決裁者指示、2026-07-14 reference 画像で方向確定)。具体的には、
「1980-90 年代シティポップ時代の日本の雑誌・レコードジャケット・ポスターイラストの雰囲気」
「自信のある細く均一なクリーンな輪郭線、フラットなセル塗り、陰影は最小限」
「コバルトブルー×白の大胆な幾何学的色面で構成された無機質でモダンな背景 + 窓外の澄んだ青空と都市のスカイライン」
「さわやかで洗練された美人画、ポスター・広告ビジュアルのような大胆な構図」
「クリスプな色面、白とブルーの余白を活かす」
を目指してください。

【イメージキャラクター】
・日本人女性
・20代後半〜30代前半くらい
・知的で、洗練され、涼しげで落ち着いた雰囲気 (ほっこり感は不要)
・若すぎず、子どもっぽくしない
・流行りのメガネをかけている (べっ甲丸縁、tortoiseshell)
・黒髪を低い位置でゆるくまとめたシニヨン + ウィスピーバング
・清潔感があり、仕事ができそう
・介護現場にも、相談員にも、事務にも、採用広報にも使える汎用性のある女性キャラクター
・表情は控えめな微笑〜涼しげな自然な表情。大げさな笑顔・ほっこりした演出は NG

【制服 (統一)】
・あおぞらケアグループの制服は「黒」
・服の種類は「黒のポロシャツ」(襟 + 2-3 ボタン placket)
・ブルーの服ではなく、黒ポロシャツを基本にする
・青ランヤード + クリアケース ID バッジを首から下げる
・ブルーは服本体ではなく、差し色として使う
  例: 名札、ストラップ、背景アクセント、小物、施設内装の一部など

【装飾品・ピアス】
職種に応じて変化させてください。

・介護スタッフ、看護など現場系
  - ピアス、指輪などは無し、またはかなり控えめ
  - 安全面・衛生面に配慮
  - 爪は短く自然
  - 髪は清潔感のあるまとめ髪、または邪魔にならない髪型

・相談員、事務、IT、採用面談など
  - 小ぶりで上品なピアスや時計は可
  - 派手すぎる装飾は避ける
  - 仕事感とおしゃれさのバランスを取る

【トーン・情感 — 2026-07-14 決裁者指定 (reference 画像で確定)】
・シティポップ的なさわやかさと無機質なクールさ。感情演出は控えめで静か
・澄んだ青空、ガラス張りの明るいモダンな空間、幾何学的な光と影の色面 (斜めの光のバンド等)
・ブルーの色面×白のハイコントラストで、ポスターとして目を引くグラフィック性
・人物の表情は控えめな微笑〜涼しげな自然な表情。ほっこり感・過剰な笑顔は不要
・「ふとした瞬間」の candid な間は維持しつつ、演出はクールに
・NG: 夕方の暖色ノスタルジー (2026-07-02 の旧指示、廃止)、温かさを強調した介護らしい演出、涙・ドラマチック誇張

【あおぞらケアグループのコーポレートカラー】
以下の色を意識してください。ただし、機械的なベタ塗りではなく、自然に馴染ませてください。
・ブルー: #00C4CC
・グレー: #575656
・ベージュ: #f8f5ee

使い方の優先イメージ (2026-07-14 更新):
・黒ポロシャツが主役
・ブルーは差し色に限定せず、**背景の大胆な幾何学的色面・都市スカイライン・床の反射などに面で使って良い** (reference 画像のコバルトブルー×白の構成)
・ランヤード・名札のブルーは維持
・グレー #575656 は文字や小物、落ち着いた影色
・白・ベージュ #f8f5ee は色面構成の明部・余白

【避けたいもの】
・**介護特有の温かい・ほっこりした固定観念の演出** (2026-07-14 決裁者指定: 「医療介護 = 温かい」の固定観念は排除)
・生活感のある古い介護施設の内装、福祉感の強い小道具
・夕方の暖色ノスタルジー演出 (2026-07-02 旧指示、廃止)
・アニメっぽすぎる大きな目
・子どもっぽいキャラクター
・派手すぎる装飾
・医療ドラマ風の過剰演出
・青い制服
・白衣っぽすぎる表現
・読めない文字や不自然な日本語テキスト
・ロゴや文字の無理な生成
・V ネックスクラブ (旧 Phase 1.5 版、廃止)
・ターコイズ / cyan / teal 系の制服 (最旧版、廃止)
・commercial anime のグロス感、透明水彩フラット、フラットベクター

【アスペクト比】
横長 (3:2 or 16:9)、求人カードやウェブサイトの crop に耐える中央配置。テキストやロゴは入れない。

続けて specific SCENE を提示するので、上記条件でイラストを生成してください。
```

## 13 枚の SCENE ブロック (最小条件版)

**方針変更 (2026-07-02)**: 詳細な SCENE 指定は AI (Claude) の想定バイアスを注入するリスクあり。ChatGPT UI 側の業界知識に委ねる方が variant 多様性と自然さで優れる (実証: 本セッション 8 回試行で raw API では届かなかった品質を UI は少数回で達成)。よって **職種 + accessory rule + composition の最小条件のみ渡し**、SCENE は UI の判断に任せる。

SCENE 1〜12 (キャラクターを含むもの) は PREAMBLE の直後に貼る。**1 会話 = 1 illustration** で運用。SCENE 13 (ヒーロー背景、人物なし) のみ例外で、PREAMBLE を貼らず単独プロンプトとして新規会話で使う。

---

### 1. `illust-job-care.png` — 求人カード care

```
JOB CATEGORY: Eldercare direct-support staff (介護スタッフ) — hands-on daily care for elderly residents.

ACCESSORY RULE: NO earring visible on the character. NO rings on either hand. Short natural nails. This is a strict eldercare industry hygiene rule.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered so the illustration survives job-card cropping. Environmental scene with the character actively engaged in visible eldercare work — depict a specific care action that clearly reads as elderly-care (not consultation, not office work, not medical examination).

Please generate one illustration.
```

### 2. `illust-job-consultant.png` — 求人カード 相談員 / ケアマネジャー

```
JOB CATEGORY: Care manager / consultation staff (相談員 / ケアマネジャー) — care planning, family meetings, service coordination.

ACCESSORY RULE: Small subtle stud earring OK (close to earlobe, no dangle). No hoop, no drop. Simple watch OK. No ring on the active-work hand.

OUTFIT VARIATION: keep the black polo shirt as base, but she MAY wear a subtle charcoal or muted-navy cardigan open over it in this scene (optional, use if it fits the composition).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Environmental scene showing consultation / planning work with a family member or resident.

Please generate one illustration.
```

### 3. `illust-job-nurse.png` — 求人カード 訪問看護

```
JOB CATEGORY: Visiting home-care nurse (訪問看護師) — in-home nursing visits to elderly residents.

ACCESSORY RULE: NO earring ideally; tiny dot stud maximum. NO hoop, NO drop, NO dangle. Simple medical-appropriate watch OK.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Environmental scene showing a specific home-nursing action (e.g. vitals check, wound care, medication guidance, health interview — you choose what best fits).

Please generate one illustration.
```

### 4. `illust-job-office.png` — 求人カード 事務スタッフ

```
JOB CATEGORY: Administrative office staff (事務スタッフ) — records, phones, applicant intake, scheduling, back-office support for an eldercare company.

ACCESSORY RULE: Small hoop, small drop, or stud earring OK (subtle only, nothing dangling large). Watch OK. Small subtle rings OK.

OUTFIT VARIATION: suit style — black or charcoal tailored jacket over a white collared shirt (2026-07-02 決裁者指示: 事務/バックオフィス系はスーツ系). Blue lanyard kept.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Bright office environment.

Please generate one illustration.
```

### 5. `illust-job-it.png` — 求人カード IT / システム

```
JOB CATEGORY: IT / systems staff (IT / システム) — supports the company's internal systems, scheduling software, care-record digitization, etc.

ACCESSORY RULE: Small hoop, small drop, or stud earring OK. Watch OK. Simple rings OK.

OUTFIT VARIATION: black hoodie (casual tech style, 2026-07-02 決裁者指示: it は黒パーカー). Blue lanyard + ID badge kept.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Bright work environment. No readable text on any screen (blur / silhouette only).

Please generate one illustration.
```

### 6. `illust-job-care-2.png` — 求人カード care variant 2

```
JOB CATEGORY: Eldercare direct-support staff (介護スタッフ) — same character as [illust-job-care.png] but depicting a DIFFERENT care action to avoid visual duplication.

ACCESSORY RULE: NO earring visible. NO rings. Short natural nails.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Environmental scene showing a care action distinctly different from meal-assistance and from walking-support (e.g. bathing / dressing / recreation / medication / conversation — you choose what best fits and reads as clearly different from other care cards).

Please generate one illustration.
```

### 7. `illust-job-care-3.png` — 求人カード care variant 3

```
JOB CATEGORY: Eldercare direct-support staff (介護スタッフ) — same character, yet ANOTHER distinct care action from care.png and care-2.png.

ACCESSORY RULE: NO earring visible. NO rings. Short natural nails.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Environmental scene showing a THIRD distinct care action that reads as visibly different from the other two care cards.

Please generate one illustration.
```

### 8. `illust-job-default.png` — 求人カード fallback (汎用)

```
JOB CATEGORY: Universal / unspecified role (求人カード fallback illustration when the job type has no specific illustration). Should feel warm and welcoming for any recruitment context.

ACCESSORY RULE: NO earring (safest, matches care rule).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Neutral warm illustration — the character in a calm approachable pose within a bright eldercare-adjacent interior. No job-specific tools that would tie it to one category.

Please generate one illustration.
```

### 9. `illust-job-consultant-2.png` — 求人カード 相談員 variant 2

```
JOB CATEGORY: Care manager / consultation staff (相談員 / ケアマネジャー) — same character, DIFFERENT scene from [illust-job-consultant.png] to avoid duplication.

ACCESSORY RULE: Small subtle stud earring OK. No hoop, no drop, no dangle.

OUTFIT VARIATION: cardigan-over-polo OK if it fits.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A distinctly different consultation-related scene (e.g. phone consultation / home visit / small-group meeting / documentation review).

Please generate one illustration.
```

### 10. `illust-job-office-2.png` — 求人カード 事務 variant 2

```
JOB CATEGORY: Administrative office staff (事務スタッフ) — same character, DIFFERENT scene from [illust-job-office.png].

ACCESSORY RULE: Small hoop / drop / stud OK.

OUTFIT VARIATION: suit style — black or charcoal tailored jacket over a white collared shirt (2026-07-02 決裁者指示: 事務/バックオフィス系はスーツ系). Blue lanyard kept.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A distinctly different office-work scene.

Please generate one illustration.
```

### 11. `illust-philosophy.jpg` — 理念セクション用イラスト (2026-07-14 改訂: 求人カードと同一トーンに統一)

**改訂理由**: 旧版は「warm / 複数人物必須 / intergenerational connection」を指定していたが、これは 2026-07-14 決裁者指定の「ほっこり固定観念の排除」方針と矛盾する。求人カード群 (SCENE 1〜10) と同じ単独キャラクター・ポスタートーンに統一する。

```
JOB CATEGORY: N/A — this is the corporate philosophy / mission-statement illustration for the recruitment website. Should feel confident, professional, and share the exact same city-pop poster identity as the job-card illustrations — NOT a "warm heartwarming eldercare" scene, NOT an intergenerational group scene.

ACCESSORY RULE: NO earring on the recurring character (care hygiene, matches [illust-job-care.png]).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered, the SAME single recurring character as the job-card illustrations (no second or third person). Depict her in a composed, confident pose that reads as embodying the company's professionalism and quiet pride — e.g. looking out over the city skyline through a window, or standing within the same cobalt-blue geometric interior used in the job-card scenes.

Please generate one illustration.
```

### 12. `illust-flow.jpg` — 応募フロー用 (2026-07-14 改訂: 求人カードと同一トーンに統一)

**改訂理由**: 旧版は「warm application interview conversation」の 2 人構図を指定していたが、SCENE #11 と同じ理由でトーンを撤回。求人カードと同じ単独キャラクター構図に統一する。

```
JOB CATEGORY: HR / recruitment process — the recurring character in a calm, professional moment related to the application process. This illustration appears on the application-flow section of the recruitment website. Keep the exact same cool city-pop poster tone as the job-card illustrations — NOT a "warm heartwarming interview" scene.

ACCESSORY RULE: Small subtle stud earring OK (consultant tier, matches [illust-job-consultant.png]). No hoop, no drop, no dangle.

OUTFIT VARIATION: cardigan-over-polo OK if it fits.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered, the SAME single recurring character as the job-card illustrations (no second person / no applicant character). Environmental scene suggesting the recruitment process — e.g. reviewing an application document at a desk, seated in the same modern glass-and-blue office interior used in the office job-card scenes. Composed and professional, not emotionally warm.

Please generate one illustration.
```

### 13. ヒーロー背景 / エントリー CTA 背景 (2026-07-14 新規追加、`sky-hero.jpg` を上書き)

**用途**: トップページ hero セクション full-bleed 背景、および entry-cta セクション背景 (同一ファイルを両方で参照)。人物は一切含めない環境イラスト。決裁者共有の江口寿史 画集参考 (青空 + 大きな入道雲、シャープなフラット色面の見開き) を配色・雲の描き方の参考にする。

**併せて添付推奨**: 求人カードイラストのいずれか 1 枚 (例: `illust-job-office.png`) を "match this background's art style, especially the sky / cityscape treatment" として UI 会話に添付すると、画風の一貫性が取りやすい。PREAMBLE の【イメージキャラクター】【制服】【装飾品】の指定は適用対象外 (人物が存在しないため)。

```
あおぞらケアグループの求人サイトで使う、人物なしの背景イラストを生成してください。

【用途】
求人サイトのトップページ、ヒーローセクションの full-bleed 背景画像。同じ画像をページ下部のエントリー CTA セクションの背景にも再利用します。

【世界観・画風】
・1980〜90 年代 日本のシティポップ時代の雑誌・レコードジャケット・ポスターイラストの雰囲気 (イラストレーター江口寿史さんの画風に寄せる)
・自信のある細く均一なクリーンな輪郭線、フラットなセル塗り、陰影は最小限、グラデーションは使わない
・コバルトブルー主体の大胆な青空を画面の大部分に占める大きな入道雲 (積雲) で構成。雲の輪郭はシャープでクリーン、写実的なグラデーション表現は避ける
・画面下部にごく細い帯として、モダンな都市のスカイラインのシルエットを配置
・ポスター・広告ビジュアルのような大胆でクリスプな構図

【コンポジション】
横長 16:9 以上のワイド構図。左側 (テキストが重なるエリア) は色面が比較的シンプルで、テキストオーバーレイに耐える余白を確保してください。

【避けたいもの】
・写真的な空、写実的な雲、エアブラシ調のグラデーション
・夕方の暖色ノスタルジー演出
・読めない文字、ロゴ
・人物 (この背景イラストには人物を含めない)

続けて具体的なアスペクト比などの制約があれば追加しますが、まずは上記の条件で 1 枚生成してください。
```

## 生成後の運用

各生成完了後:

1. 本田様が Claude セッション (私) に画像を送信
2. Claude が **10 項目 Pass/Fail 判定** (verification-checklist.md 準拠) を実施
3. Pass → `mockup/assets/img/<filename>` に配置 + necessary alt テキスト調整
4. 全 13 枚集まったら **Phase 4 feature branch → PR → code-review → 認可 → squash merge**
5. Fail → SCENE 微調整案を提示、本田様が UI 再生成

## Fallback

ChatGPT UI で identity drift が起きた場合の対処:
- 会話冒頭で PREAMBLE を再貼付
- Image #2 (証明済み好例) を UI 会話に添付して "match this character's identity" 指示
- それでも drift する場合 → 現状 API 経路より確実な代替なし。次の一手は本田様判断
