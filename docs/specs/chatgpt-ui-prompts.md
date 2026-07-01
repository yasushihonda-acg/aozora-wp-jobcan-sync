# ChatGPT UI 生成用 プロンプト集 (2026-07-02)

mockup 内キャラ含みイラスト 12 枚を ChatGPT UI (gpt-image) で生成する際のコピペ用テンプレート。API `v1/images/edits` の identity 保持限界により UI 経路に統一 (empirical、本セッションで確定)。

## 使い方

1. ChatGPT UI で **新規会話** を開始
2. 下記「共通 PREAMBLE」を貼る
3. 続けて生成したい illustration の「SCENE」ブロックを貼る
4. 生成された画像を本田様が確認 → 私 (Claude) に送信 → 私が 10 項目採点 + ファイル配置 + mockup 反映 + commit

各 illustration は **独立した会話** で生成する。同一会話で複数生成すると context が汚れて identity drift する可能性あり。

## 共通 PREAMBLE (毎回冒頭に貼付)

**併せて添付**: `.claude/memory/illustration-baseline.png` (Image #5 = 歩行介助シーン baseline) を UI 会話にアタッチして "match this character's identity exactly" と明示すると drift 最小化。

```
あおぞらケアグループの求人サイト・採用サイトで使うイラストを生成してください。以下の条件を最優先で守ってください。

【目的】
あおぞらケアグループの求人サイトで使える、統一感のあるイメージキャラクターのイラスト。介護スタッフ、相談員、看護、事務、IT、採用面談、施設紹介、理念ページなど、いろいろな場面に差し込めるキャラクター。

【全体の世界観】
・現代的でおしゃれ
・介護求人サイトに合う清潔感
・やさしく、親しみやすい
・でも幼すぎず、少し大人っぽい
・働く人の誇りや専門性が伝わる
・「やりがい搾取」ではなく、「ケアスタッフにやりがいと経済的豊かさを」という思想に合う
・温かいが、古臭くない
・かわいいだけではなく、採用ブランディングとして使える洗練感がある

【イラストの方向性】
著名な作家や特定の漫画家の画風を直接指定しないでください。方向性としては、
「現代的でおしゃれな日本のエディトリアル系イラスト」
「細い線、清潔感、少しレトロポップ、都会的、介護求人に合う温かさ」
「雑誌の挿絵や採用サイトのキービジュアルに使える洗練された雰囲気」
を目指してください。

【イメージキャラクター】
・日本人女性
・20代後半〜30代前半くらい
・親しみやすく、知的で、あたたかい雰囲気
・若すぎず、子どもっぽくしない
・流行りのメガネをかけている (べっ甲丸縁、tortoiseshell)
・黒髪を低い位置でゆるくまとめたシニヨン + ウィスピーバング
・清潔感があり、仕事ができそう
・介護現場にも、相談員にも、事務にも、採用広報にも使える汎用性のある女性キャラクター
・表情はやさしい笑顔。大げさな笑顔ではなく、安心感のある自然な笑顔

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

【あおぞらケアグループのコーポレートカラー】
以下の色を意識してください。ただし、機械的なベタ塗りではなく、自然に馴染ませてください。
・ブルー: #00C4CC
・グレー: #575656
・ベージュ: #f8f5ee

使い方の優先イメージ:
・黒ポロシャツが主役
・ブルー #00C4CC は差し色 (ランヤード、名札、背景アクセント、小物、施設内装の一部)
・グレー #575656 は文字や小物、落ち着いた影色
・ベージュ #f8f5ee は背景や空間のやさしいベース

【避けたいもの】
・アニメっぽすぎる大きな目
・子どもっぽいキャラクター
・派手すぎる装飾
・医療ドラマ風の過剰演出
・古い介護施設の暗い雰囲気
・青い制服
・白衣っぽすぎる表現
・読めない文字や不自然な日本語テキスト
・ロゴや文字の無理な生成
・実在作家の画風をそのまま模倣する表現
・V ネックスクラブ (旧 Phase 1.5 版、廃止)
・ターコイズ / cyan / teal 系の制服 (最旧版、廃止)
・commercial anime のグロス感、透明水彩フラット、フラットベクター

【アスペクト比】
横長 (3:2 or 16:9)、求人カードやウェブサイトの crop に耐える中央配置。テキストやロゴは入れない。

続けて specific SCENE を提示するので、上記条件でイラストを生成してください。
```

## 12 枚の SCENE ブロック (最小条件版)

**方針変更 (2026-07-02)**: 詳細な SCENE 指定は AI (Claude) の想定バイアスを注入するリスクあり。ChatGPT UI 側の業界知識に委ねる方が variant 多様性と自然さで優れる (実証: 本セッション 8 回試行で raw API では届かなかった品質を UI は少数回で達成)。よって **職種 + accessory rule + composition の最小条件のみ渡し**、SCENE は UI の判断に任せる。

各ブロックは PREAMBLE の直後に貼る。**1 会話 = 1 illustration** で運用。

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

OUTFIT VARIATION: keep the black polo shirt as base, but she MAY wear a subtle beige or muted cardigan open over it (optional).

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. Bright office environment.

Please generate one illustration.
```

### 5. `illust-job-it.png` — 求人カード IT / システム

```
JOB CATEGORY: IT / systems staff (IT / システム) — supports the company's internal systems, scheduling software, care-record digitization, etc.

ACCESSORY RULE: Small hoop, small drop, or stud earring OK. Watch OK. Simple rings OK.

OUTFIT VARIATION: keep the black polo shirt as base, but she MAY wear a tailored dark-navy or charcoal blazer open over it in this professional-tech context (optional).

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

OUTFIT VARIATION: cardigan-over-polo OK.

COMPOSITION: horizontal 3:2 or 16:9 wide. Main subject centered. A distinctly different office-work scene.

Please generate one illustration.
```

### 11. `illust-philosophy.jpg` — 理念セクション用ヒーロー

```
JOB CATEGORY: N/A — this is the corporate philosophy / mission-statement hero illustration for the recruitment website. Should evoke the company's warm eldercare mission across generations.

ACCESSORY RULE: NO earring on the recurring character (care hygiene).

COMPOSITION: WIDE horizontal 16:9 environmental scene. MULTI-PERSON MANDATORY — depict at least 3 people at similar visual weight: the recurring character, an elderly resident, and one more person (another elderly resident OR a family member OR a colleague). Emphasize warm intergenerational connection.

Please generate one illustration.
```

### 12. `illust-flow.jpg` — 応募フロー用

```
JOB CATEGORY: HR / recruitment interview — the recurring character meeting with a job applicant. This illustration appears on the application-flow section of the recruitment website.

ACCESSORY RULE: Small subtle stud OK (consultant tier).

OUTFIT VARIATION: cardigan-over-polo OK.

COMPOSITION: WIDE horizontal 16:9. Two-person environmental scene — the recurring character on one side, a Japanese job applicant (casual-professional attire) on the other side, engaged in warm application interview conversation.

Please generate one illustration.
```

## 生成後の運用

各生成完了後:

1. 本田様が Claude セッション (私) に画像を送信
2. Claude が **10 項目 Pass/Fail 判定** (verification-checklist.md 準拠) を実施
3. Pass → `mockup/assets/img/<filename>` に配置 + necessary alt テキスト調整
4. 全 12 枚集まったら **Phase 4 feature branch → PR → code-review → 認可 → squash merge**
5. Fail → SCENE 微調整案を提示、本田様が UI 再生成

## Fallback

ChatGPT UI で identity drift が起きた場合の対処:
- 会話冒頭で PREAMBLE を再貼付
- Image #2 (証明済み好例) を UI 会話に添付して "match this character's identity" 指示
- それでも drift する場合 → 現状 API 経路より確実な代替なし。次の一手は本田様判断
