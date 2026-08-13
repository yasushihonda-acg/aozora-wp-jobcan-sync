# ChatGPT UI 生成用 プロンプト集 (2026-07-02)

mockup 内キャラ含みイラスト 15 枚 + ヒーロー背景 (キャラなし) 1 枚を ChatGPT UI (gpt-image) で生成する際のコピペ用テンプレート。API `v1/images/edits` の identity 保持限界により UI 経路に統一 (empirical、本セッションで確定)。

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

## 16 枚の SCENE ブロック (最小条件版)

**方針変更 (2026-07-02)**: 詳細な SCENE 指定は AI (Claude) の想定バイアスを注入するリスクあり。ChatGPT UI 側の業界知識に委ねる方が variant 多様性と自然さで優れる (実証: 本セッション 8 回試行で raw API では届かなかった品質を UI は少数回で達成)。よって **職種 + accessory rule + composition の最小条件のみ渡し**、SCENE は UI の判断に任せる。

SCENE 1〜16 のうち SCENE 13 (ヒーロー背景、人物なし) を除く全て (キャラクターを含むもの) は PREAMBLE の直後に貼る。**1 会話 = 1 illustration** で運用。SCENE 13 のみ例外で、PREAMBLE を貼らず単独プロンプトとして新規会話で使う。

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

### 11. `illust-philosophy.jpg` — 理念セクション用イラスト (2026-07-14 改訂 → **採用済み**)

**改訂理由**: 旧版は「warm / 複数人物必須 / intergenerational connection」を指定していたが、これは 2026-07-14 決裁者指定の「ほっこり固定観念の排除」方針と矛盾する。求人カード群 (SCENE 1〜10) と同じ単独キャラクター・ポスタートーンに統一する。

**採用記録**: 2026-07-14、1 回目生成は縦長ポートレート構図で COMPOSITION 指定 (横長 3:2/16:9) と不一致のため再生成を依頼。2 回目生成で横長構図に修正されたことを確認 → 採用、`illust-philosophy.jpg` に配置済み。

```
JOB CATEGORY: N/A — this is the corporate philosophy / mission-statement illustration for the recruitment website. Should feel confident, professional, and share the exact same city-pop poster identity as the job-card illustrations — NOT a "warm heartwarming eldercare" scene, NOT an intergenerational group scene.

ACCESSORY RULE: NO earring on the recurring character (care hygiene, matches [illust-job-care.png]).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered, the SAME single recurring character as the job-card illustrations (no second or third person). Depict her in a composed, confident pose that reads as embodying the company's professionalism and quiet pride — e.g. looking out over the city skyline through a window, or standing within the same cobalt-blue geometric interior used in the job-card scenes.

Please generate one illustration.
```

### 12. `illust-flow.jpg` — 応募フロー用 (2026-07-14 改訂 → **採用済み**)

**改訂理由**: 旧版は「warm application interview conversation」の 2 人構図を指定していたが、SCENE #11 と同じ理由でトーンを撤回。求人カードと同じ単独キャラクター構図に統一する。

**2026-07-15 OUTFIT VARIATION 改訂 (決裁者判断)**: 1 回目生成は「カーディガン重ね着可」の指定に対し、どちらでもない中途半端な長袖シャツになった。人事/採用担当として応募書類を確認するシーンは OL 的な事務シーンとして自然なため、`illust-job-office.png` と同じ「スーツ系 (黒/charcoal テーラードジャケット + 白襟シャツ)」へ変更。

**採用記録**: 2026-07-15、2 回目生成 (スーツ系指定後) を評価 → キャラクターidentity・衣装・画風・アスペクト比とも house style に合致 → 採用、`illust-flow.jpg` に配置済み。

```
JOB CATEGORY: HR / recruitment process — the recurring character in a calm, professional moment related to the application process. This illustration appears on the application-flow section of the recruitment website. Keep the exact same cool city-pop poster tone as the job-card illustrations — NOT a "warm heartwarming interview" scene.

ACCESSORY RULE: Small subtle stud earring OK (consultant tier, matches [illust-job-consultant.png]). No hoop, no drop, no dangle.

OUTFIT VARIATION: suit style — black or charcoal tailored jacket over a white collared shirt (matches [illust-job-office.png]). Blue lanyard kept. NOT a plain long-sleeve black shirt/blouse, NOT a cardigan.

COMPOSITION: horizontal 3:2 or 16:9 wide (WIDE landscape, NOT a tall portrait). Main subject centered, the SAME single recurring character as the job-card illustrations (no second person / no applicant character). Environmental scene suggesting the recruitment process — e.g. reviewing an application document at a desk, seated in the same modern glass-and-blue office interior used in the office job-card scenes. Composed and professional, not emotionally warm.

Please generate one illustration.
```

### 13. ヒーロー背景 / エントリー CTA 背景 (2026-07-14 新規追加 → **採用済み**、`sky-hero.jpg` に配置済み)

**用途**: トップページ hero セクション full-bleed 背景、および entry-cta セクション背景 (同一ファイルを両方で参照)。人物は一切含めない環境イラスト。決裁者共有の江口寿史 画集参考 (青空 + 大きな入道雲、シャープなフラット色面の見開き) を配色・雲の描き方の参考にする。

**併せて添付推奨**: 求人カードイラストのいずれか 1 枚 (例: `illust-job-office.png`) を "match this background's art style, especially the flat cel-shaded line work — NOT a soft airbrushed anime sky" として UI 会話に添付すると、画風の一貫性が取りやすい。PREAMBLE の【イメージキャラクター】【制服】【装飾品】の指定は適用対象外 (人物が存在しないため)。

**2026-07-14 1 回目生成の結果と改訂 (決裁者評価)**: 初回生成は「雲がソフトなグラデーション陰影のアニメ調」「都市スカイラインが描かれていない」の 2 点で house style と乖離。プロンプトへ CRITICAL 行を追記し、2 回目生成で両方解消を確認 → 採用。

**採用記録**: 2026-07-14、2 回目生成物を Claude が評価 (フラットセル塗りの雲・都市スカイラインシルエットとも house style に合致) → 決裁者が Finder 経由でファイル実体を提供 → `mockup/assets/img/sky-hero.jpg` に配置 (hero セクション full-bleed 背景 + entry-cta 背景の両方に反映)。

**2026-07-15 差し替え完了**: 決裁者からトップページ実機レビューでヒーロー文字の視認性課題を指摘され、新バリエーション候補 2 枚 (画面左〜中央に雲のない濃紺の単色空が大きく広がる構図/雲が画面全体に広がる構図) を追加提供。可読性の観点から前者を採用決定し、`mockup/assets/img/sky-hero.jpg` に反映済み (entry-cta 背景も同一ファイル共用)。ヒーロー側のテキスト視認性は `.hero__title em` のマーカー除去 + `.hero` へのディレクショナルスクリム追加(`mockup/assets/css/components.css`) でも別途対処済み。Playwright 実機確認で判読性を確認済み。

```
SUBJECT: N/A — pure background / environment illustration for the recruitment website, no character. Reused as both the hero section's full-bleed background and the entry-cta section's background.

STYLE ANCHOR: Same 1980s-90s Japanese city-pop poster illustration style as the job-card illustrations (thin clean outlines, flat cel shading, no gradient) — a bold cobalt-blue sky filling most of the frame with large flat-shaded white cumulus clouds (crisp clean edges, no photorealistic/airbrush gradient), plus a thin modern-city-skyline silhouette along the bottom edge.

CRITICAL — avoid these two mistakes from a previous attempt:
1. The clouds MUST be flat, crisp-edged cel-shaded shapes with at most 2 flat tones (white + one light gray-blue shadow tone) — NOT soft airbrushed/gradient-shaded anime clouds with painterly volume. Think screen-printed poster illustration, not a realistic sky render.
2. A city skyline silhouette (simple flat dark silhouette of modern building shapes) MUST be visible as a thin band along the bottom edge of the frame. Do not omit it.

COMPOSITION: WIDE horizontal 16:9 or wider. Keep the left-center area relatively open/uncluttered — page text will be overlaid there. No people, no readable text, no logo, no warm sunset colors.

Please generate one illustration.
```

### 14. `illust-job-visit.png` — 求人カード 訪問介護員 (ヘルパー) (2026-07-14 新規追加 → **採用済み**)

**追加理由**: トップページの募集職種カードを求人カード群と同一イラストへ統一する過程で、「訪問介護員 (ヘルパー)」だけ専用イラストが無いことが判明 (暫定で `illust-job-care-3.png` を流用中)。訪問介護は施設内介護と異なり利用者宅を訪問する業務のため、専用 SCENE を新規追加する。

**採用記録**: 2026-07-15、1 回のプロンプトから「食事介助 (illust-job-visit-2.png)」「洗濯物たたみ (illust-job-visit.png)」「歩行介助 (illust-job-visit-3.png)」の 3 案が生成された。`illust-job-care.png` (求人カード「介護スタッフ」) が既に歩行介助シーンのため、重複を避け「洗濯物たたみ (生活援助)」を主イラストとして採用。他 2 案は他求人カードと同様、予備バリエーションとして保存。

```
JOB CATEGORY: Home-visit care helper (訪問介護員 / ヘルパー) — visits clients' own homes to provide daily living support and personal care, distinct from facility-based eldercare staff.

ACCESSORY RULE: NO earring visible on the character. NO rings on either hand. Short natural nails. This is a strict eldercare industry hygiene rule (matches [illust-job-care.png]).

COMPOSITION: horizontal 3:2 or 16:9 wide (WIDE landscape, NOT a tall portrait). Main subject centered so the illustration survives job-card cropping. Environmental scene set inside an ordinary Japanese home/apartment (not a care facility) — depict a specific home-visit action (e.g. helping with a meal, light housework, mobility assistance) that clearly reads as visiting a client's private home rather than working in a facility.

Please generate one illustration.
```

### 15. `illust-job-visit-2.png` — 求人カード 訪問介護員 variant 2 (食事介助、2026-07-15 採用済み)

SCENE #14 と同一プロンプトから生成された食事介助シーン。予備バリエーションとして保存 (現時点で表示スロットなし、`jobs.html` に訪問介護員の求人データが追加された場合の利用を想定)。

### 16. `illust-job-visit-3.png` — 求人カード 訪問介護員 variant 3 (歩行介助、2026-07-15 採用済み)

SCENE #14 と同一プロンプトから生成された歩行介助シーン。予備バリエーションとして保存 (現時点で表示スロットなし)。

### 17. `illust-numbers.jpg` 後継 — 「数字で見る、あおぞら」セクション用 (バックログ、2026-07-15 追加・未着手)

**経緯**: 既存 `illust-numbers.jpg` (町並み+時計塔+風車のフラットベクター、Phase 1 旧トンマナ) が、Philosophy/求人カード/Flow で統一されている江口寿史風シティポップポスター調と明確に不統一と決裁者から指摘 (2026-07-15)。トップページ実機ブラッシュアップの一環として、`mockup/index.html` の Numbers セクションからは一旦イラスト自体を除去し (`.section--band` の色面レイアウトで代替)、`illust-numbers.jpg` ファイル自体は削除せず保管。本 SCENE は新画風での再生成が必要になった場合の着手用メモであり、**現時点では生成着手しない (決裁者からの明示指示待ち)**。

**方向性メモ (次回着手時の起点)**: 人物なし・環境イラストである点は SCENE #13 (ヒーロー背景) に近い。「数字で見る、あおぞら」は年間休日・新規入職者数・拠点数・平均勤続年数という定量データセクションのため、単なる町並みではなく、統計/成長を示唆する構図 (例: 複数の建物・拠点を俯瞰するスカイライン、または SCENE #13 と対になる構図) を SCENE #13 の CRITICAL 制約 (フラットセル塗り・都市スカイラインシルエット必須) を踏襲して検討する。

### 18. `illust-job-visiting-nurse.png` — 求人カード 訪問看護 (2026-08-11 新規追加 → **2026-08-12 採用済み**、決裁者フィードバック対応)

**経緯**: トップページ「募集中の職種」に入口のない職種が11件あるとの決裁者指摘 (2026-08-11)、うち訪問看護 (category_id=18987、15件) が名指しで指摘された。既存 SCENE #3 `illust-job-nurse.png` は JOB CATEGORY 記述上「訪問看護師」だが、実際は「看護職」(category_id=18983、施設内看護含む) カードで使用中のため、本 SCENE は視覚的に明確に区別できる別シーンを指定する。

**採用結果 (2026-08-12)**: 本田様が ChatGPT UI で3枚生成、全て10項目 Pass。メイン (血圧測定シーン) を `illust-job-visiting-nurse.png` としてトップページ「訪問看護」カードに採用、残り2枚は `illust-job-visiting-nurse-2.png` (服薬指導) / `illust-job-visiting-nurse-3.png` (聴診器チェック) として保存。**2026-08-12 (2nd)**: 3枚とも `/jobs/` 求人一覧の `selectors.yaml` `thumbnail_categories.visiting-nurse` バケット (旧 `nurse` から「訪問看護」synonym を分離・移動) の画像プールとして採用、表示スロット確保済み。

```
JOB CATEGORY: Visiting nurse making a home visit (訪問看護) — traveling to a patient's own home to provide nursing care, distinct from facility/clinic-based nursing.

ACCESSORY RULE: NO earring ideally; tiny dot stud maximum. NO hoop, NO drop, NO dangle. Simple medical-appropriate watch OK.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Environmental scene showing a specific in-home nursing action that reads as clearly different from [illust-job-nurse.png] (e.g. blood pressure check with a portable device at the patient's dining table, medication management guidance, wound dressing change — you choose what best fits and looks visibly distinct).

Please generate one illustration.
```

### 19. `illust-job-night-shift.png` — 求人カード 夜勤専従（介護・看護） (2026-08-12 新規追加 → **同日採用済み**)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、求人数最多 (41件) の夜勤専従を次の対象に選定。既存の care/nurse 系カードは全て昼間の青空シーンのため、本 SCENE は「夜」を明確に打ち出し視覚的に区別する。PREAMBLE の「澄んだ青空」制約から意図的に逸脱する初めてのシーンであるため、下記 NIGHT SETTING 指定を通常の PREAMBLE 直後に必ず貼ること。

**採用結果 (2026-08-12)**: 本田様が ChatGPT UI で3枚生成、全て10項目 Pass。ベッドサイドでタブレット服薬確認を行うシーンをメイン (`illust-job-night-shift.png`) としてトップページ「夜勤専従（介護・看護）」カードに採用 (他カードとの構図重複が最も少なく、暖色照明×夜の対比が明瞭なため選定)。残り2枚は `illust-job-night-shift-2.png` (施設内廊下の歩行介助巡回) / `illust-job-night-shift-3.png` (夜間の在宅血圧測定) として保存。**2026-08-12 (2nd)**: `/jobs/` 求人一覧の `selectors.yaml` `thumbnail_categories.night-shift` バケット (旧 `care` から「夜勤専従（介護・看護）」synonym を分離・移動) には `illust-job-night-shift.png` / `-2.png` の2枚のみ採用。`-3.png` (夜間の在宅血圧測定) は `illust-job-visiting-nurse.png` (在宅の血圧測定シーン) と構図がほぼ同一で、一覧上で並ぶと「同じ絵の昼夜違い」に見えるため意図的に除外 (現時点で表示スロットなし、他シーンへの再利用可否は未検討)。

```
JOB CATEGORY: Night-shift care and nursing staff (夜勤専従、介護・看護) — overnight duty at an eldercare facility, covering both nursing and care work during night hours (e.g. rounds, monitoring, care recording, resident check-ins).

ACCESSORY RULE: NO earring ideally; tiny dot stud maximum. NO hoop, NO drop, NO dangle. Short natural nails.

NIGHT SETTING (IMPORTANT DEPARTURE FROM DAYTIME SCENES): unlike the other cards, this is a NIGHT scene. Outside the window: a dark navy night sky (deep cobalt blue, not black), a few soft city lights/window lights in the skyline, optionally a crescent moon. Inside: warm, calm interior lighting (a desk lamp or corridor nightlight) against the cool blue night outside — keep the crisp flat-cel, thin-line style and cobalt-blue/white geometric composition, just shifted to a night palette. Calm and composed, NOT eerie or dramatic.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A specific night-duty action (e.g. checking a resident quietly with a small handheld light, writing an overnight care record at a softly-lit desk, a calm nighttime corridor check).

Please generate one illustration.
```

### 20. `illust-job-facility-manager.png` — 求人カード 施設長・管理者候補 (2026-08-12 新規追加 → 1回目生成はACCESSORY RULE違反で不採用 → **2回目生成を同日採用済み**)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、求人数2位 (38件) の施設長・管理者候補を次の対象に選定。マネジメント職として、既存の相談員/ケアマネジャー (1対1の相談シーン) や事務スタッフ (デスクワーク) と明確に区別できる「統率・マネジメント」の構図を指定する。

**1回目生成の不採用理由 (2026-08-12)**: 本田様がChatGPT UIで3枚生成、10項目採点では全てPassと判定し一度トップページに反映したが、`codex review`(PR #174)が3枚全てに耳元の垂れ下がるピアス(ACCESSORY RULE違反)を検出。Claudeの目視採点で見落としていた実害バグ(サムネイル表示のみで細部を確認していなかった)。PR #174はクローズ、以下のACCESSORY RULEを強化した上で再生成を依頼した。

**採用結果 (2026-08-12、2回目生成)**: 本田様が新規ChatGPT UI会話で1枚生成、耳がほぼ髪に隠れピアス描画なしを拡大確認のうえ10項目Pass。施設ロビーでタブレットと書類を確認するシーンを `illust-job-facility-manager.png` としてトップページ「施設長・管理者候補」カードに採用(バリエーションなし、1枚のみで進める決裁者判断)。OUTFIT VARIATION指定のテーラードジャケットは今回も反映されず黒ポロシャツ単体だが、コアidentityは維持のため許容。**2026-08-12 (2nd)**: `/jobs/` 求人一覧の `selectors.yaml` `thumbnail_categories.facility-manager` バケット (旧 `care` から「施設長・管理者候補」synonym を分離・移動) にも同ファイルを1枚プールのまま採用、本番38件のカードは全て同一画像になる。バリエーション2枚の生成は次タスクとして `docs/handoff/GOAL.md` に記録 (決裁者判断: 1枚で先行反映、追加生成依頼は後日)。

```
JOB CATEGORY: Facility manager / administrator candidate (施設長・管理者候補) — overseeing daily facility operations, leading and supporting staff, coordinating with families and external partners at an eldercare facility.

ACCESSORY RULE (CRITICAL — a previous generation attempt violated this): NO earring is strongly preferred for this role. If an earring appears at all, it MUST be an extremely small flat stud sitting flush against the earlobe with ZERO visible drop, chain, or dangling element of any length (even a few millimeters of hanging chain/thread is a violation). NO hoop, NO drop, NO dangle, NO chain/threader earring under any circumstance. Simple watch OK.

OUTFIT VARIATION: a tailored jacket (charcoal, navy, or beige) worn open over the black polo shirt (2026-07-02 決裁者指示: 経営/管理シーンはテーラードジャケット重ね着可). Blue lanyard + ID badge kept visible.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A scene that reads as management/leadership rather than one-on-one consultation or desk work — e.g. leading a short staff huddle/briefing, reviewing an operations report or shift schedule at a standing table, walking through the facility checking on operations. Should look visibly distinct from [illust-job-consultant.png] (one-on-one family consultation) and [illust-job-office.png] (desk work).

Please generate one illustration.
```

### 21. `illust-job-consultation.png` — 求人カード 相談員 (2026-08-12 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、求人数3位 (36件) の相談員を次の対象に選定。既存 `illust-job-consultant.png` (SCENE #2) は「相談員 / ケアマネジャー」向けに作られたが、実際は「ケアマネジャー」カード (ケアプラン作成の複数人ミーティング) で使用中のため、本 SCENE は相談員固有の業務 (入所前の窓口相談・施設見学案内など、ケアプラン策定より前段の一次窓口) を明確に描写し視覚的に区別する。

```
JOB CATEGORY: Resident/family intake consultation staff (相談員) — the first point of contact for prospective residents and their families: facility tours, intake counseling, and ongoing life-support consultation at an eldercare facility. Distinct from ケアマネジャー (care-plan formulation with a multi-person team meeting).

ACCESSORY RULE (CRITICAL — a previous generation for a different role violated this and required a redo): NO earring is strongly preferred. If an earring appears at all, it MUST be an extremely small flat stud sitting flush against the earlobe with ZERO visible drop, chain, or dangling element of any length (even a few millimeters of hanging chain/thread is a violation). NO hoop, NO drop, NO dangle, NO chain/threader earring under any circumstance. Simple watch OK.

OUTFIT VARIATION: keep the black polo shirt as base; a subtle charcoal or muted-navy cardigan open over it is optional.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A one-on-one or small-scale intake/reception scene — e.g. greeting a prospective family at a reception desk with a facility brochure, guiding a family on a tour of the facility, a calm explanatory conversation at a low table with tea served. Should look visibly distinct from [illust-job-consultant.png] (multi-person care-plan meeting) and read clearly as a welcoming first-contact/reception moment, not a planning meeting.

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で3枚生成。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施。3枚とも顔/髪/眼鏡/年齢感/衣装/画風/手指/クロップは Pass、耳元も3枚とも ACCESSORY RULE 範囲内(1枚は耳が髪で非描画、1枚は極小フラットスタッドで垂れなし、1枚は耳が見えるが完全非描画)。

1枚(高齢の利用者様・そのご家族と3人でテーブルを囲みタブレットを提示するシーン)は構図比較の結果、**既に採用済みの `illust-job-consultant.png`/`illust-job-consultant-2.png` (ケアマネジャー、複数人でのケアプラン相談シーン) とほぼ同一の構図**(スタッフ+高齢者+家族の3人・テーブル囲み・タブレット提示のポーズ・青幾何学背景+都市スカイライン)と判明し不採用。COMPOSITION で明示した「既存 `illust-job-consultant.png` と視覚的に区別できること」という要件を満たせなかったため(PR #183 の教訓の再発パターン)。

残り2枚のうち、施設内を案内しながら高齢の利用者様と会話する歩行シーンを `illust-job-consultation.png` としてトップページ「相談員」カードに採用(SCENE 意図の「施設見学案内」に最も直接的に合致し、既存カード群 [全て着席・タブレット提示型] の中で唯一の歩行構図)。窓口で高齢の利用者様と一対一で会話するシーンは `illust-job-consultation-2.png` としてバリエーション採用、`/jobs/` 求人一覧の `selectors.yaml` `thumbnail_categories.consultation` バケット(旧 `consultant` から「相談員」synonym を分離・移動)の2枚プールとして採用。テキストタグから格上げ(7→6)。

### 22. `illust-job-general.png` — 求人カード 総合職（営業・管理職） (2026-08-12 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、訪問看護・夜勤専従・施設長・管理者候補・相談員に続く5番目の対象として、テキストタグのみだった残り7職種の中で本番実測 (2026-08-12) 最多 (21件) の総合職（営業・管理職）を選定。既存 `illust-job-office.png` (事務スタッフ、社内デスクワーク) や `illust-job-facility-manager.png` (施設長、自施設内のマネジメント/リーダーシップ) とは異なり、本 SCENE は「営業」側の外向き業務 (提携施設・取引先との商談、資料プレゼン) を明確に描写し視覚的に区別する。

```
JOB CATEGORY: General-track sales and management staff (総合職・営業/管理職) — business development and external partnership work for an eldercare company: visiting partner facilities and organizations, presenting proposals, negotiating contracts. Distinct from 事務スタッフ (in-house desk work) and 施設長・管理者候補 (leading staff within one's own facility).

ACCESSORY RULE: Small hoop, small drop, or stud earring OK (subtle only, nothing dangling large). Watch OK. Small subtle rings OK.

OUTFIT VARIATION: suit style — black or charcoal tailored jacket over a white collared shirt (external-facing business role). Blue lanyard kept. A laptop bag or slim briefcase as an optional prop signals "out visiting a partner", not desk-bound.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. An external business-development scene — e.g. presenting a proposal/laptop across a table to a partner-organization representative in a glass meeting room, a business greeting/handshake at a partner facility's reception, or reviewing a contract document together at a conference table. Should look visibly distinct from [illust-job-office.png] (solo desk work) and [illust-job-facility-manager.png] (leading one's own staff) — this is externally-facing, two-organization business dealing, not internal operations.

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で3枚生成。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施、3枚とも小さめのスタッド/ドロップ程度でACCESSORY RULE(このSCENEはoffice系と同じ「小さめの装飾はOK」)の範囲内、手指も破綻なし。

1枚(デスクでタブレット+クリップボードにチャート記入するシーン)は採点の過程で **既に採用済みの `illust-job-facility-manager.png` と構図がほぼ同一**(座り姿勢・タブレットを片手・クリップボードにペン記入・青いバインダースタック・観葉植物・ガラス張り廊下背景)と判明し不採用。COMPOSITION で明示した「施設長カードと視覚的に区別できること」という要件を満たせなかったため。

残り2枚のうち、ホワイトボードの資料を指し示しながら同僚にプレゼンテーションするシーンを `illust-job-general.png` としてトップページ「総合職（営業・管理職）」カードに採用(既存カードと最も差別化でき、SCENE 意図の「外向き商談・提案」に最も合致)。施設内廊下を歩きながらクリップボードを確認するシーンは `illust-job-general-2.png` としてバリエーション保存、`/jobs/` 求人一覧の `selectors.yaml` `thumbnail_categories.general` バケット(旧 `office` から「総合職（営業・管理職）」synonym を分離・移動)の2枚プールとして採用。テキストタグから格上げ(7→6)。

### 23. `illust-job-support.png` — 求人カード サポート職（清掃・洗濯・調理・送迎） (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、訪問看護・夜勤専従・施設長・管理者候補・相談員・総合職(営業・管理職)に続く6番目の対象として、テキストタグのみだった残り6職種の中で本番実測 (2026-08-12) 最多 (7件) のサポート職(清掃・洗濯・調理・送迎)を選定。現在 `selectors.yaml` では `care` バケット(介護職・世話人と共有)に折り込まれ専用イラストが無い。既存 `illust-job-care.png`/`-2.png`/`-3.png` (介護スタッフ、入浴・排泄・移動介助など身体に直接触れる介護動作) や `illust-job-visit.png` (訪問介護員、利用者宅での洗濯物たたみ) とは異なり、本 SCENE は「身体介護を伴わない裏方支援」(清掃・調理・送迎)を明確に描写し視覚的に区別する。洗濯物たたみの構図は `illust-job-visit.png` で既出のため避ける。

```
JOB CATEGORY: Facility hospitality/support staff (サポート職 — 清掃・調理・送迎) — behind-the-scenes support work at an eldercare facility: cleaning common areas and resident rooms, preparing and serving meals in the facility kitchen, and driving residents to and from appointments or day-service pickup. This role does NOT provide direct hands-on physical care to residents (no bathing, no toileting, no mobility assistance).

ACCESSORY RULE: Kitchen/food-safety and driving-safety appropriate — NO earring, NO rings, NO dangling jewelry of any kind. Short natural nails. Simple watch OK only in a non-cooking scene.

OUTFIT VARIATION: keep the black polo shirt as base; if the scene is a kitchen/cooking scene, add a simple white or pale apron over it (no apron if driving or cleaning).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Pick ONE clear, specific facility-support action — e.g. plating/preparing a meal tray in a bright facility kitchen, wiping down and tidying a resident's room or common lounge area, or loading a resident into a facility van for a day-service pickup. Must look visibly distinct from [illust-job-care.png]/[illust-job-care-2.png]/[illust-job-care-3.png] (no direct physical contact with a resident's body) and must NOT be a laundry-folding scene (that motif already exists in [illust-job-visit.png]).

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で3枚生成(清掃・洗濯・送迎の3シーン)。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施した結果、3枚中2枚を不採用とした。

- 清掃シーン(テーブル拭き)・洗濯シーン(タオルたたみ)の2枚は、いずれも耳元拡大確認で**小さなスタッドピアスが視認され不採用**。本 SCENE の ACCESSORY RULE は施設長候補 SCENE #20 の教訓を踏まえ「NO earring, NO rings, NO dangling jewelry of any kind」と無条件で指定していたが、それでも ChatGPT UI が小さなピアスを描画するケースがあると判明(consultant 系 SCENE の「小stud許容」ルールとの取り違えではなく、無条件禁止でも起こりうる)。
- 洗濯シーンはさらに、COMPOSITION で明示的に回避を指定していたにもかかわらず **既存 `illust-job-visit.png`(訪問介護員、洗濯物たたみ)と主要モチーフ(タオルをたたむ動作)が重複**しており、二重の不採用理由。
- 残り1枚(送迎車へご利用者様をご案内するシーン)は耳元クリーン(ピアスなし)、手指も破綻なく、既存カード群の中で唯一の車両シーンのため視覚的に完全に区別できる。`illust-job-support.png` として単独採用(1枚プール、`facility-manager` と同じ先行反映パターン)。**教訓: 「NO earring」等の無条件禁止ルールを明記していても、ChatGPT UI 側が小さなアクセサリーを描画することがある。耳元拡大確認は職種のACCESSORY RULEの強さによらず毎回実施すべき**(次回以降のSCENE採点でも継続)。

**【フォローアップ】`support` バリエーション追加**: 現在1枚プールのため、本番7件(サポート職)のカードは全て同一画像になる。清掃・調理のいずれかのシーンをACCESSORY RULEをさらに強い表現(例: 「earring-shaped mark of any size is a violation」等)で再生成依頼し、2枚目以降を追加する。

### 24. `illust-job-visiting-rehab.png` — 求人カード 訪問リハビリ (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、訪問看護・夜勤専従・施設長・管理者候補・相談員・総合職(営業・管理職)・サポート職に続く7番目の対象として、残り5職種の中で件数同率1位(6件、サービス管理責任者・世話人と同率)の訪問リハビリを選定。現在 `selectors.yaml` では `nurse` バケット(看護職と共有)に折り込まれ専用イラストが無い。既存 `illust-job-nurse.png`(訪問看護師、血圧測定などの医療行為)や `illust-job-visit-3.png`(訪問介護員、手を引いての歩行介助)とは異なり、本 SCENE は「機能訓練・運動療法」という構造化されたリハビリ動作(ゴムバンドを使った筋力訓練、関節可動域訓練、歩行訓練の計測等)を明確に描写し視覚的に区別する。

```
JOB CATEGORY: Visiting physical/occupational rehabilitation therapist (訪問リハビリ) — in-home structured therapeutic exercise for elderly residents: guided resistance-band strength training, joint range-of-motion stretching, or gait/balance training measured with a stopwatch or notepad. This is structured rehabilitation therapy, NOT a medical examination and NOT casual daily-living assistance.

ACCESSORY RULE: NO earring ideally; tiny dot stud maximum. NO hoop, NO drop, NO dangle. Simple medical-appropriate watch OK.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A specific rehab-therapy action with a visible rehab-specific prop — e.g. guiding a seated resident through a resistance-band arm/leg exercise, supporting a leg stretch on a mat, or timing a structured gait-training walk with a stopwatch/notepad in hand. Must look visibly distinct from [illust-job-nurse.png] (no blood-pressure cuff, no medical vitals device) and from [illust-job-visit-3.png] (no simple hand-holding walking assistance, no cane) — must clearly read as structured exercise therapy, not a medical check or casual walking support.

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で1枚生成(リハビリバーを使った上肢運動療法シーン)。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施、全項目Pass。耳元はクリーン(ピアスなし)、手指(スタッフ・利用者様ともリハビリバーを握る手)も破綻なし。テーブル上にストレスボール・カラー積み木(指先訓練用)・タオルが配置され、構造化された機能訓練であることが明確。既存 `illust-job-nurse.png`(血圧測定などの医療行為)・`illust-job-visit-3.png`(手を引く歩行介助)とも視覚的に完全に区別できるため、`illust-job-visiting-rehab.png` として単独採用(1枚プール、`facility-manager`/`support` と同じ先行反映パターン)。`selectors.yaml` に `visiting-rehab` バケット新設(`nurse` から「訪問リハビリ」synonym を分離・移動、看護職・看護師の既存割り当ては無変更)。テキストタグから格上げ(5→4)。

### 25. `illust-job-service-manager.png` — 求人カード サービス管理責任者 (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、訪問看護・夜勤専従・施設長・管理者候補・相談員・総合職(営業・管理職)・サポート職・訪問リハビリに続く8番目の対象として、残り4職種のうち件数同率1位(6件、世話人と同率)のサービス管理責任者を決裁者選定(タイブレーク理由: 世話人は既存 `illust-job-care.png` 系[入浴・移動介助などの身体介護動作]と構図が近く drift リスクが高い一方、サービス管理責任者は「個別支援計画の確認・スタッフ監督」という書類仕事寄りの動作を描けるため、既存 `illust-job-consultant.png`/`-2.png`(ケアマネジャー、多人数でのケアプラン相談)・`illust-job-consultation.png`/`-2.png`(相談員、ご本人・ご家族との窓口相談)との視覚的区別が付けやすい)。現在 `selectors.yaml` では `consultant` バケット(ケアマネジャー・計画作成担当者と共有)に折り込まれ専用イラストが無い。

```
JOB CATEGORY: Service manager / individual-support-plan supervisor (サービス管理責任者、通称「サビ管」) at a disability welfare facility — responsible for drafting and reviewing individual support plans (個別支援計画) and supervising the facility's care staff to ensure plan quality and compliance. This is internal staff-supervision work, NOT a face-to-face consultation with a resident or family member.

ACCESSORY RULE: Small hoop, small drop, or stud earring OK (subtle only, nothing dangling large). Watch OK. Small subtle rings OK.

OUTFIT VARIATION: base black polo shirt + blue lanyard, unchanged.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. The scene MUST be ONE of these two specific staff-supervision actions only:
  (a) standing at a whiteboard that shows a staff shift schedule / duty roster, gesturing toward it while briefing ONE seated colleague (a second staff member in a colored polo, NOT a resident/elderly person) — a team-huddle / staff-meeting moment, or
  (b) standing behind a seated colleague's shoulder, pointing at something on the colleague's paper care-record or laptop screen with an approving nod (two staff members, not seated at a shared negotiation-style table).
Do NOT use a solo-seated-at-desk-with-tablet-and-pen pose (too close to [illust-job-facility-manager.png]'s composition: seated, one hand tablet, one hand pen on a clipboard, blue binders on desk). Do NOT use a solo-walking-down-a-corridor-holding-documents pose (too close to [illust-job-general-2.png]'s composition: walking through a glass-walled corridor with a reception desk and potted plants in the background). Do NOT use a multi-person table meeting with a resident/family member or a tablet held out to a client (too close to [illust-job-consultant.png]/[illust-job-consultant-2.png]/[illust-job-consultation.png]/[illust-job-consultation-2.png]). This should clearly read as one staff member supervising/briefing another staff member, indoors, standing.

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で2枚生成(デスクでタブレット+ペンを持つシーン/廊下を書類持って歩くシーン、いずれも改訂前の初期COMPOSITION指定時の生成)。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施、2枚とも全項目Pass。

既存カードとの構図比較(PR #183/#186の教訓に基づく確認)では、廊下を歩くシーンが `illust-job-general-2.png`(総合職バリエーション、同じ窓+観葉植物+受付背景の廊下歩行構図)と酷似していると判明し不採用。デスクシーンは `illust-job-facility-manager.png`(座り姿勢+片手タブレット+片手ペンの共通アーキタイプ)と要素は近いが、背景(本SCENEはオフィスデスク+都市スカイラインの窓、facility-managerはロビー受付+階段)とトーンが明確に異なり視覚的に区別可能と decision-maker が判断、`illust-job-service-manager.png` として単独採用(1枚プール、`facility-manager`/`support`/`visiting-rehab` と同じ先行反映パターン)。`selectors.yaml` に `service-manager` バケット新設(`consultant` から「サービス管理責任者」synonym を分離・移動、ケアマネジャー・計画作成担当者の既存割り当ては無変更)。テキストタグから格上げ(4→3)。

**教訓**: 既存カードとの構図比較チェックは「SCENE本文で明示的に除外指定した対象」だけでなく全既存カードに対して行うべき(本件では consultant/consultation 系との区別は SCENE で明示していたが、facility-manager/general-2 系との重複は事後確認で発覚)。ただし共通アーキタイプ(座り+タブレット+ペン等)の再使用そのものは即不採用理由にはならず、背景・トーンといった副次要素での区別可否も含めて総合判断する。

### 26. `illust-job-caretaker.png` — 求人カード 世話人 (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、サービス管理責任者に続く9番目の対象として、残り3職種のうち件数最多(6件)の世話人を選定。現在 `selectors.yaml` では `care` バケット(介護職と共有)に折り込まれ専用イラストが無い。世話人はグループホーム(共同生活援助)で高齢者・障害者の日常生活を支える役割で、既存 `illust-job-care.png`/`-2.png`/`-3.png`(介護職、入浴・移動介助などの身体に直接触れる介護動作)とは異なり「服薬確認・食事時の会話・生活相談」という伴走型の生活支援を描く。清掃・洗濯・調理・送迎など裏方作業を描く `illust-job-support.png`(サポート職)とも区別する。

```
JOB CATEGORY: Caretaker / daily-life support staff (世話人) at a group home (共同生活援助・グループホーム) for elderly or disabled residents — providing companionship-based daily-living support: checking a weekly medication organizer together with a resident, having a warm conversation during a shared meal, or helping a resident go over a shopping list for the week. This is companionship and life-coaching work, NOT hands-on physical care (no bathing, no toileting, no mobility/transfer assistance) and NOT solo behind-the-scenes housekeeping (no cleaning, no laundry, no cooking alone, no driving).

ACCESSORY RULE: same as care-level — nothing ideally, tiny dot stud (close to earlobe) maximum. NO hoop, NO drop, NO dangle.

OUTFIT VARIATION: base black polo shirt + blue lanyard, unchanged.

COMPOSITION: horizontal 3:2 or 16:9 wide. Two people: the staff member and ONE elderly or adult resident, seated together at a small table in a warm group-home living/dining area (NOT a clinical or generic care facility corridor). Pick ONE specific companionship action — e.g. the staff member and resident together checking a weekly pill organizer / medication chart on the table, going over a handwritten shopping list together, or sharing a cup of tea while chatting at mealtime. Must look visibly distinct from [illust-job-care.png]/[illust-job-care-2.png]/[illust-job-care-3.png] (no bathing, no toileting, no physical transfer/lifting, no direct hands-on body contact) and from [illust-job-support.png] (no facility van, no solo cleaning/cooking/laundry). Must NOT be a standing multi-person meeting with a tablet held out (too close to [illust-job-consultant.png]/[illust-job-consultation.png] family) — this is a seated, homey, one-on-one companionship moment.

Please generate one illustration.
```

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で2枚生成(グループホームでの食事配膳シーン/脱衣所でのタオル手渡しシーン)。10項目採点+耳元拡大確認(sips でのピンポイントクロップ)を実施。

脱衣所シーンは背景に浴槽・シャワー・介護用いすが明確に描かれ、SCENE本文で明示的に禁止した「no bathing, no direct hands-on body contact」に直接抵触(既存カードとの構図比較以前に SCENE 指示そのものへの違反)と判明し不採用。食事配膳シーンは COMPOSITION で例示した3パターン(服薬確認/買い物リスト/お茶)のいずれでもなく「二人とも着席」の指定からも外れる(スタッフは立位)が、companionship の精神には合致し既存カードとの構図重複もないため decision-maker 判断で採用、`illust-job-caretaker.png` として単独採用(1枚プール、`facility-manager`/`support`/`visiting-rehab`/`service-manager` と同じ先行反映パターン)。`selectors.yaml` に `caretaker` バケット新設(`care` から「世話人」synonym を分離・移動、介護職の既存割り当ては無変更)。テキストタグから格上げ(3→2)。

**教訓**: ChatGPT UI は COMPOSITION で明示的に列挙した具体例から外れた新しい動作を提案することがある(今回は「配膳」)。明示的除外構図(入浴・身体接触)への抵触は既存カード比較を待たずその場でFail判定できる一方、明示例からの逸脱(新しい動作の提案)自体は自動的に不採用理由にはならず、JOB CATEGORY の精神との整合性で個別判断する。

### 27. `illust-job-service-lead.png` — 求人カード サービス提供責任者 (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、世話人に続く10番目(最後から2番目)の対象として、残り2職種のうち件数最多(4件、新卒・既卒総合職は2件)のサービス提供責任者を選定。現在 `selectors.yaml` では `visit` バケット(ホームヘルパー/訪問介護員と共有)に折り込まれ専用イラストが無い。サービス提供責任者(通称「サ責」)は訪問介護事業所において複数のホームヘルパーの訪問スケジュール・ルートを組み、訪問介護計画書を作成し、ケアマネジャーと連携する調整役であり、既存 `illust-job-visit.png`/`-2.png`/`-3.png`(ホームヘルパー、利用者宅での洗濯物たたみ・食事介助・歩行介助といった訪問先での身体介護動作そのもの)とは明確に異なる「事業所内でのスケジュール調整」を描く。同じ「スタッフ監督」系の `illust-job-service-manager.png`(SCENE #25、障害福祉施設内の当番表ブリーフィング)とも、対象が施設内スタッフの当番表ではなく複数ヘルパーの訪問先ルート/地図である点で区別する。

```
JOB CATEGORY: Home-visit care service coordinator (サービス提供責任者、通称「サ責」) at a home-visit care agency (訪問介護事業所) — drafts home-visit care plans (訪問介護計画書), assigns and schedules a team of home-visit helpers (ホームヘルパー) to client visit routes, and liaises with each client's care manager (ケアマネジャー). This is an office-based scheduling/coordination role, distinct from ホームヘルパー themselves (hands-on in-home care at a client's residence) and from サービス管理責任者 (a disability-facility staff duty-roster supervisor).

ACCESSORY RULE: NO earring ideally; tiny flat dot stud sitting flush against the earlobe maximum. NO hoop, NO drop, NO dangle, NO chain/threader earring under any circumstance. Simple watch OK.

OUTFIT VARIATION: base black polo shirt + blue lanyard, unchanged.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered, indoors at the home-visit care agency's office (NOT a client's home, NOT a facility corridor). The scene MUST be ONE of these two specific actions only, and MUST feature a wall-mounted area map or large paper schedule board showing multiple helpers' names alongside pinned home-visit routes/time slots as the central visual signature:
  (a) standing at the map/board, updating one helper's route or time slot with a marker or pin, alone in the office, or
  (b) seated at a desk with the map/board clearly visible on the wall behind them, on a phone call (headset or handset) coordinating with a helper in the field, a paper route sheet in the other hand.
There must be NO second person seated across the table, and NO elderly resident or family member anywhere in the frame — this is solely the coordinator alone in the office, not a meeting. Do NOT use a multi-person table scene with a tablet held out to a client/resident/family member (too close to [illust-job-consultant.png]/[illust-job-consultant-2.png]/[illust-job-consultation.png]/[illust-job-consultation-2.png] — those are resident/family consultation scenes, this role does not face clients directly). Do NOT use a staff duty-roster whiteboard briefing a seated colleague (too close to [illust-job-service-manager.png]). Do NOT use generic desk paperwork without the map/route-board (too close to [illust-job-office.png]/[illust-job-office-2.png]).

Please generate one illustration.
```

**却下履歴 (2026-08-13、1回目生成)**: 初回生成1枚(高齢の利用者様・スタッフ・書類記入中の女性の3人がテーブルを囲みタブレットの小さなグリッドを提示するシーン)は10項目チェックのうち項目9(職務内容整合)がFail。COMPOSITIONで必須指定した「壁掛け地図/スケジュールボードを中心視覚要素とする事業所内の調整シーン」が一切描かれておらず、代わりに既採用済み `illust-job-consultant.png`/`-2.png`(ケアマネジャー)・`illust-job-consultation.png`/`-2.png`(相談員)とほぼ同一の「利用者・家族との相談ミーティング」構図(PR #183/#186/#195と同種の construction drift 再発パターン)。上記 COMPOSITION を「地図/ボード必須 + 利用者・家族を含む多人数ミーティング構図を明示的に禁止」する形に絞り込んだうえで再生成を依頼する。

**採用結果 (2026-08-13)**: 上記の絞り込み後、本田様が改めて1回目生成の画像(高齢の利用者様・ご家族・スタッフの3人がテーブルを囲みタブレットを提示するシーン)をそのまま採用する判断を下した。理由: 「現代のオフィスでは壁に地図やスケジュールボードを掲示する運用は実態にそぐわない」との decision-maker 判断で、COMPOSITION が要求した地図/ボード必須要件そのものを不採用(絞り込み版 SCENE への再生成は行わず、絞り込み前に生成済みだった画像を採用)。

10項目チェックのうち項目9(職務内容整合)以外は元評価通り全て Pass(顔・髪・眼鏡・年齢感・画風・手指・文字混入・クロップ)。項目5(衣装+アクセサリー)は耳元が髪でほぼ隠れており明確なピアス描画は確認できず。項目9は decision-maker の明示判断により Pass 扱いへ変更。既存カード `illust-job-consultant.png`/`-2.png`(ケアマネジャー)・`illust-job-consultation.png`/`-2.png`(相談員)との構図近似(3人・テーブル囲み・タブレット提示という共通アーキタイプ)は残存するが、これも decision-maker が許容範囲と判断。`illust-job-service-lead.png` として単独採用(1枚プール、`facility-manager`/`support`/`visiting-rehab`/`service-manager`/`caretaker` と同じ先行反映パターン)。`selectors.yaml` に `service-lead` バケット新設(`visit` から「サービス提供責任者」synonym を分離・移動、ホームヘルパーの既存割り当ては無変更)。テキストタグから格上げ(2→1、残るは新卒・既卒総合職のみ)。

**教訓**: SCENE の COMPOSITION が前提とする業務環境の実在性(本件は「壁掛け地図/スケジュールボード」という物理的小道具の現代における実態)は、decision-maker の現場知識でしか検証できない場合がある。AI(Claude)側の想定が実態と乖離しているケースでは、10項目チェックの機械的な Fail 判定より decision-maker の最終判断を優先する。

### 28. `illust-job-new-grad.png` — 求人カード 新卒・既卒総合職 (2026-08-13 新規追加)

**経緯**: 決裁者指摘 (2026-08-11) で入口のなかった11職種のうち、サービス提供責任者に続く最後(11番目)の対象として、新卒・既卒総合職を選定(残り2職種のうち件数最少2件だが、これで11職種全ての専用イラストカード化が完了する)。現在 `selectors.yaml` では `office` バケット(事務職と共有)に折り込まれ専用イラストが無い。本 SCENE は事前の SCENE ブロック作成を経ず、本田様が直接 ChatGPT UI で生成した画像を採点する形で進行した(通常のワークフローと異なる進行順)。

**採用結果 (2026-08-13)**: 本田様が ChatGPT UI で1枚生成(黒/charcoal テーラードジャケット+白襟シャツのスーツ姿で、ガラス張りのオフィスロビーを書類フォルダを片手に歩くシーン)。10項目採点を実施、項目9(職務内容整合)以外は全て Pass。衣装は CLAUDE.md 2026-07-02 決裁者指示の「office はスーツ系(黒/charcoal テーラードジャケット+白襟シャツ)」派生ルールに合致。

既存カードとの構図比較で、`illust-job-general-2.png`(総合職バリエーション、ガラス張り廊下を歩きながらクリップボードを確認するシーン)と「ガラス張りロビー/廊下を歩く単独人物+都市スカイライン窓+観葉植物+青幾何学壁」というアーキタイプが共通していると判明。ただし衣装(本SCENEはスーツ+白襟シャツ、`illust-job-general-2.png`は黒ポロシャツ)という明確な差別化要素があり、「フォーマルなオフィスワーカー」対「現場を回るスタッフ」という職務の質的差を視覚的に表現できていると decision-maker が判断し採用。`illust-job-new-grad.png` として単独採用(1枚プール、`facility-manager`/`support`/`visiting-rehab`/`service-manager`/`caretaker`/`service-lead` と同じ先行反映パターン)。`selectors.yaml` に `new-grad` バケット新設(`office` から「新卒・既卒総合職」synonym を分離・移動、事務職の既存割り当ては無変更)。これで決裁者指摘の11職種すべてが専用イラストカード化完了、トップページの「その他の募集職種」テキストタグセクションは対象消滅により削除。

**教訓**: 構図の共通アーキタイプ(本件は「ガラス張り廊下を歩く単独人物」)が既存カードと重複していても、衣装や小道具といった別の視覚要素で職務の質的差異を明確に表現できていれば decision-maker 判断で許容されうる(PR #197 サービス管理責任者の「背景・トーンで区別可能」判断と同種の許容パターン)。

## 生成後の運用

各生成完了後:

1. 本田様が Claude セッション (私) に画像を送信
2. Claude が **10 項目 Pass/Fail 判定** (verification-checklist.md 準拠) を実施
3. Pass → `mockup/assets/img/<filename>` に配置 + necessary alt テキスト調整
4. 全 16 枚集まったら **Phase 4 feature branch → PR → code-review → 認可 → squash merge**
5. Fail → SCENE 微調整案を提示、本田様が UI 再生成

## Fallback

ChatGPT UI で identity drift が起きた場合の対処:
- 会話冒頭で PREAMBLE を再貼付
- Image #2 (証明済み好例) を UI 会話に添付して "match this character's identity" 指示
- それでも drift する場合 → 現状 API 経路より確実な代替なし。次の一手は本田様判断
