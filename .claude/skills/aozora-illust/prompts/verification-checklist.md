# 10 項目 Pass/Fail 検証チェックリスト (2026-07-02 baseline pivot)

新規生成イラストの採用可否は、以下 10 項目 **すべて Pass** が条件。1 項目でも Fail の場合は再生成 or シーン記述側で局所調整。

## チェック項目

| # | 項目 | Pass 基準 | Fail の典型 |
|---|------|----------|-----------|
| 1 | **顔** (目・鼻・口・輪郭) | baseline `illustration-baseline.png` と目視同一 (アーモンド細長目、下がり目、微笑、oval face + tapered jaw) | 目が丸すぎ / 大きすぎ、輪郭が丸顔、口が grin、別人化 |
| 2 | **髪** | 黒髪 + 低い位置のシニヨン + 後れ毛 + ウィスピーバング + subtle highlights | 髪型が違う、フラット塗り、明るい茶髪 |
| 3 | **眼鏡** | べっ甲丸縁太フレーム、レンズはラウンドオーバル | 眼鏡なし、四角フレーム、細縁、単色フレーム |
| 4 | **年齢感** | 20 代後半〜30 代前半、大人の落ち着き | 幼く見える、20 代前半に見える、老けて見える |
| 5 | **衣装 + アクセサリー** | **黒ポロシャツ (襟 + ボタン)** + **青ランヤード + ID badge**。**アクセサリーは職種別ルール準拠** (care/nurse は nothing 理想、極小 stud まで許容、hoop/dangle 全職種で絶対 NG — outfit-spec.txt 参照)。派生: consultant/office はニュートラルカーディガン重ね着可、it はテーラードジャケット重ね着可 | ターコイズ / 青の polo、白 lanyard、V-neck scrub (旧 Phase 1.5)、パイピングあり、care/nurse で hoop/dangle ピアス描画 |
| 6 | **画風** | 現代的でおしゃれな日本のエディトリアル系イラスト、細い線、清潔感、少しレトロポップ、都会的、雑誌挿絵レベルの洗練感 | 透明水彩フラット塗り、フラットベクター、油彩厚塗り、3D 風、commercial anime (thick outline + glossy)、キラキラアニメ、青い制服、白衣っぽい表現、実在作家の直接模倣 |
| 7 | **手指** | 破綻なし (5 本指、自然な曲がり) | 6 本指、指の融合、不自然な角度 |
| 8 | **文字混入** | 画像内にテキスト・ロゴ・シンボルなし (シーンの必要小道具のみ) | 意味不明の英数字、ブランドロゴ、無理な日本語テキスト |
| 9 | **職務内容整合** | シーン記述 (nurse=医療、office=デスク、care=介護 action 等) と描画内容が一致 | シーン記述と違う職務 (nurse なのに PC 前 だけ、care なのに相談員絵 等) |
| 10 | **クロップ** | 用途アスペクト比 (16:9 / 4:5 / 16:10) に耐える構図、主要要素が中央付近 | 主要要素が端に寄る、クロップで顔が切れる |

## 適用タイミング

- **Round α/β/γ (量産)**: 全 10 項目を厳密評価
- **mockup 反映前**: 全 10 項目 + alt テキストとの整合を確認

## 記録

各採用画像には `manifest.json` を Git 管理:

```json
{
  "file": "illust-job-care.png",
  "generated_at": "2026-07-02T00:00:00+09:00",
  "source": "chatgpt-ui",
  "approval_number": "N",
  "reference_baseline_md5": "<md5 of illustration-baseline.png at time of generation>",
  "prompt_summary": "<日本語 SCENE 概要 or 主要意図>",
  "verification": {
    "face": "pass", "hair": "pass", "glasses": "pass", "age": "pass",
    "outfit": "pass", "style": "pass", "hands": "pass",
    "text": "pass", "job_match": "pass", "crop": "pass"
  }
}
```

manifest は `generated-images/manifests/<file>.json` に配置し、コミット対象に含める。
