# Handoff — 2026-07-01 (Phase A キャラ真理ソース刷新 + イラスト再生成セッション)

## TL;DR

決裁者から新キャラクター (Image #5/#6 = 黒 V-neck scrub + 青ランヤード、以降 Image #7/#8 = 江口寿史 esque editorial illustration) の直接指示を受け、**キャラ真理ソース + spec + baseline PNG を全面刷新**。合計 3 PR マージ (#45 フッターロゴ / #46 Phase 1 真理ソース刷新 / #47 Phase 1.5 style + 職種別ピアスルール + baseline earring 除去)。Round A (画風検証)、Round B (6 panel model sheet)、Round α (求人カード 3 枚 care/consultant/nurse、うち **consultant/nurse は multi-person + eye contact + 職種ルール準拠で完了**、care は 4 回試行するも Phase 1.5 spec 下で solo portrait 化する bias を克服できず判定保留) まで完了。予算消費 $3.36 / $10。

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run (Phase 2B-exec): https://aozora-sync-flry56mxwa-an.a.run.app (稼働中、本セッション変更なし)

## 今セッションで完了したこと

### マージ済 PR (3 件)

| PR | タイトル | 内容 |
|---|---|---|
| #45 | `fix(mockup): フッターロゴの背景色をフッター #323232 に完全一致させる` | `logo-acg-light.png` を `filter: invert(1) brightness(1.6)` していた結果、白背景が純黒に反転して footer #323232 より暗い黒ボックスが浮いていた問題を修正。新規 `logo-acg-footer.png` を Canvas API で生成 (背景 #323232 リペイント)、CSS filter 削除、HTML 35 ファイルの footer src を切替。ヘッダは維持 |
| #46 | `feat(aozora-illust): 決裁者指示によるキャラ真理ソース全面刷新 (2026-07-01)` | baseline PNG 2 枚差替 (Image #5 = full, Image #6 = close-up)、reference_illustration_baseline.md 全面書換、prompts/{face,outfit,style,codex-rewrite-template}-spec.txt 更新、SKILL.md 更新、CLAUDE.md 更新、10 項目 Pass/Fail 検証チェックリスト新規、docs/specs/illust-refresh-ledger.md 新規 (全 23 画像の対応台帳)、旧 baseline を archive に保管 |
| #47 | `refactor(aozora-illust): Phase 1.5 — 江口寿史 esque style + 職種別アクセサリールール + baseline earring 除去` | style-spec を "editorial genre" → "thin-line technique (江口寿史 esque)" に転換 (portrait bias 回避)、COMPOSITION MANDATE 追加、outfit-spec に 職種別 ACCESSORIES RULES 追加 (care/nurse ピアス NG、consultant/office/it 小スタッド OK、hoop/dangle 全職種 NG)、baseline PNG の耳付近を Canvas patch で bare 化 (earring reference bias を根絶) |

### 確立した実証知見

#### 1. style-spec の genre 表現 vs technique 表現の composition bias

- 「editorial magazine illustration (genre)」表現は **portrait bias を強く誘発**。Phase 1.5 test v1-v5 で 5 連続 solo portrait 化
- 「thin-line technique in the vein of Eguchi Hisashi (technique)」+ 明示 COMPOSITION MANDATE で **multi-person 復活**
- 教訓: `v1/images/edits` の prompt engineering では **技法軸 vs ジャンル軸** の使い分けが composition 制御の鍵

#### 2. reference PNG の element bias は text prompt では抑えられない

- Round α v2 (care/consultant/nurse) 生成物にピアスが描画され続けた
- outfit-spec で「care/nurse は earring NG」と明示、face-spec からも identity lock 外しても、**baseline PNG に earring が baked-in なら model が inherit**
- 解決: **baseline PNG 側を Canvas patch で bare 化** (`illustration-baseline.png` 3,144 px 置換 + `-closeup.png` 2,855 px 置換) → 完全解消
- 教訓: reference-based generation で除去したい element は **PNG 側で消す**、prompt override では不十分

#### 3. Codex rewrite が SCENE を genre-drift させることがある

- Round α final の care で「TWO PEOPLE + tea offering with elderly」指定が Codex rewrite で「solo care worker at documentation task」に変質
- SCENE の verb と object (お茶 offering、tea cup) が Codex には「care worker task = documentation」の genre-drift を起こす
- 対策: SCENE を "MANDATORY" prefix + "NOT ..." exclusions で強化 (今セッション末尾で care v8 で試行中)

#### 4. 介護業界のドレスコード実務ルール

- hoop / drop / dangle 系ピアスは care/nurse/consultant/office/it 全職種 で NG (認知症利用者の risk、医療安全、unprofessionalism)
- care/nurse は極小 stud まで許容 (現実の facilities での慣行に沿う)、hoop/dangle 絶対 NG
- consultant/office/it は 小 hoop/drop OK
- 出典: `.claude/skills/aozora-illust/prompts/outfit-spec.txt` ACCESSORIES RULES セクション

## 進行中 (次セッション着手対象)

### Phase 3 Round α (care 1 枚残り、v8 も失敗、別 approach 要)

- **care v8 = 失敗** (2026-07-01 20:50 生成): "MANDATORY tea scene, NOT documentation" 明示にもかかわらず、solo portrait (オフィスデスクの記録作業シーン) に化けた
- v1/v2 (旧 polished anime spec) では multi-person 成立していたが、Phase 1.5 (thin-line technique) 移行後 v7/v8 で連続 solo 化
- **care カテゴリ特有の bias** (訓練データで "care worker" = "at desk documenting" の連想が強い + reference PNG が単独立ち姿) が Codex rewrite + edits API の compositional 制約を超える
- 次セッションで検討するアプローチ:
  - (a) `--ref-mode=face-only` で参照 PNG の単独構図 bias を切る (Phase 1.5 test v3 でも試したが outfit reference も落ちて白衣化した)
  - (b) `--category=job-care-elderly` にリネームして解釈 hint を強化 (Codex rewrite が anchor しやすいカテゴリ名に)
  - (c) SCENE 冒頭を「Eldercare scene: A caregiver AND an elderly resident having tea together」で multi-person を entity-first に (verb-first ではなく noun-first)
  - (d) archive baseline (2026-06-29 版、multi-person nurse/elderly/tablet シーン) を一時的に reference PNG として使用 (identity slight drift の risk あり)
  - (e) polished anime spec に戻して care だけ v2 手法で生成 (spec 分岐の risk あり)
- 判定: v7 (ノート PC scene) を採用可能とするかは本田様の decision-maker 領分

### Phase 3 Round β/γ (残り 9 枚)

- Round β (5 枚): office, it, care-2, care-3, consultant-2 — 予算 $0.80
- Round γ (4 枚): default, office-2, illust-philosophy, illust-flow — 予算 $0.64
- 手法: Phase 1.5 spec + patched baseline + v6 手法 (technique-based + multi-person mandate + explicit LEFT/RIGHT layout + interaction with eye contact) を継続適用
- 予算残: $10 - $3.36 = $6.64 で余裕あり

### Phase 4 (mockup 反映 + PR)

- 承認済み 12 画像を `mockup/assets/img/illust-*.png` にコピー (旧を archive/ へ)
- Playwright で index.html + jobs.html + jobs-{care,nurse,office,it}.html + jobs/*.html 3 件で新画像表示確認
- feature branch → PR → `/code-review low` → 認可 → squash merge → main 同期 → GitHub Pages 反映確認

## 重要な設計判断 (本セッション)

### イラスト刷新スコープの絞り込み (docs/specs/illust-refresh-ledger.md 記録)

- **IN スコープ** (12 枚、イラスト系): `illust-job-*.png` × 10 + `illust-philosophy.jpg` + `illust-flow.jpg`
- **OUT スコープ** (11 枚、実写別レイヤー / 人物なし): `staff-*.jpg` × 3 + `blog-*.jpg` × 3 + `hero-main.jpg` + `category-*.jpg` × 6 + `illust-numbers.jpg` (人物なし、Phase A 承認後別作業)
- **写真 / イラスト 2 レイヤー分離** が本プロジェクトの設計 — キャラ刷新はイラストレイヤーのみ

### 予算 hard cap (Codex plan review 反映)

- $10 上限 (超過時停止して報告)
- 40 回相当の生成余地
- 本セッション消費 $3.36 (34%)、残 $6.64 で Round β/γ 完遂可能

### verification-checklist.md の 10 項目 Pass/Fail

- 主観 78-82% 再現率評価から、10 項目 Pass/Fail 客観判定に転換
- 顔・髪・眼鏡・年齢・衣装・画風・手指・文字・職務・クロップ
- Round B 6 panel model sheet + Round α で 適用済

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし** — 次セッション冒頭で care v8 結果確認後に判断:
- OK なら Round β 5 枚生成 (nurse は既に完了なので実質 office+it+care-2+care-3+consultant-2)
- NG なら care 再々生成

### 条件待ち (明示 trigger 付き)

| # | 項目 | 分類 | trigger | 充足時のタスク |
|---|------|------|--------|--------------|
| 1 | care 判定 (v7 accept / 別 approach 再生成) | 執行 | 本田様「care v7 採用」or「(a)-(e) いずれかの approach で再生成」 | 採用→β へ / 再生成→指定 approach 適用 |
| 2 | Round β 生成認可 | 執行 | 本田様「β へ進んでよい」 | 5 枚生成 → 並置レビュー |
| 3 | Round γ 生成認可 | 執行 | 本田様「γ へ進んでよい」 | 4 枚生成 → 並置レビュー |
| 4 | Phase 4 mockup 反映 | 執行 | 本田様「12 枚 accept、mockup 反映してよい」 | mockup 差替 + PR |
| 5 | 前 handoff からの継続項目 | 執行 | 本田様指示 | `/healthz` rename、WP 統合、Billing budget alert (前 handoff 参照) |

### 却下候補

| # | 項目 | 却下理由 |
|---|------|--------|
| 1 | AI 側から「もっと良くなりそう」で prompts/*.txt を自己判断改変 | 真理ソース由来、decision-maker 領分 |
| 2 | AI 側から baseline PNG を追加編集 | 番号単位認可なし禁止 |
| 3 | Round β/γ を並列 (5+4 枚) 一括生成 | Codex plan review H7 (バッチゲート推奨) 準拠、逐次で認可挟む |

## Issue Net 変化

- 前セッション終了時: OPEN 0
- 本セッション: 新規起票 0、close 0
- 現時点: OPEN 0
- **Net 変化: 0 (KPI 維持)** ✅

## 環境状態

- Git branch: `main`
- 状態: clean (本セッションで別ブランチ 2 本 merge & delete 済)
- 最新コミット: `db7faa4 refactor(aozora-illust): Phase 1.5 …` (PR #47)
- リモート同期: ✅ origin/main と同期済
- CI: `pages-build-deployment` (PR #45/#46/#47 マージ後の実行、次回 catchup で success 確認)
- Cloud Run: 稼働中、本セッション変更なし
- 予算消費: **$3.36 / $10** (33.6%、Round β/γ 予定 $1.44 分の余裕あり)

## 構造的整合性チェック

- CLAUDE.md ↔ prompts/*.txt: Phase 1.5 の style + accessories rules で同期済 ✅
- reference_illustration_baseline.md ↔ baseline PNG: 2026-07-01 (Phase 1.5) 版で整合、archive に 2026-06-29 版保管 ✅
- verification-checklist.md ↔ outfit-spec.txt (ACCESSORIES RULES): 同期済 ✅
- SKILL.md ↔ prompts/verification-checklist.md: 相互リンクで同期 ✅
- docs/specs/illust-refresh-ledger.md: 全 23 画像の IN/OUT 判定を記録済 ✅

## 参考: 本セッション生成物一覧

### 判定用途 (git 管理外、`generated-images/`)

- `gpt-image-round-a-{1,2,3}-*.png` (Round A 画風検証、A1 採用)
- `gpt-image-character-sheet-*.png` (Round B 6 panel model sheet)
- `gpt-image-phase15-test-care-{,v3,v4,v5,v6}-*.png` (Phase 1.5 スタイル + composition 実験、v6 で成立)
- `gpt-image-job-care-2026070*.png`, `-consultant-*.png`, `-nurse-*.png` (Round α v1/v2/final)
- `target-references/target-{7,8}-eguchi-vibe.png` (Image #7/#8 決裁者提示、preview 用に copy)
- 各 `*-preview.html` (比較レビュー用)

### 真理ソース (git 管理下)

- `.claude/memory/illustration-baseline.png` (Phase 1.5 版、earring patched)
- `.claude/memory/illustration-baseline-character-closeup.png` (同上)
- `.claude/memory/archive/*-2026-06-29.png` (旧版保管)
- `.claude/skills/aozora-illust/prompts/*.txt` (Phase 1.5 版)
- `.claude/skills/aozora-illust/prompts/verification-checklist.md` (10 項目)
- `docs/specs/illust-refresh-ledger.md` (23 画像台帳)

## 最終結論

🛑 **executor 領分の作業は care v8 判定待ちのみ、セッション終了推奨** (次セッション冒頭で判定 → Round β 着手)

前 handoff (2026-07-01 codex 統合セッション) からの継続 4 項目 (`/healthz` rename / WP 統合 / Billing budget alert / 追加カテゴリイラスト生成) はすべて未着手継続、本田様の明示指示 trigger 待ち。

本セッションの成果 (真理ソース刷新 + spec Phase 1.5 化 + Round A/B/α 実証) は次セッション以降の Round β/γ + Phase 4 の基盤として恒久化 (PR #46/#47 マージ済)。
