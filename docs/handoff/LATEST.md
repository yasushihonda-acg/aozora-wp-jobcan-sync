# Handoff — 2026-07-02 (制服 spec pivot + 生成経路 pivot セッション)

## TL;DR

**決裁者判断による方針転換 2 件を実施**:
1. 制服 spec pivot: 黒 V-neck scrub → **黒ポロシャツ** (襟 + 2-3 button placket)
2. 生成経路 pivot: API `v1/images/edits` → **ChatGPT UI** (character-critical illustration 用)

理由: API 経路で care の identity + 介護 action + 服装 3 拍子を揃えるのに 8 回試行 + Codex 診断 2 回で $0.68 消費して届かず、決裁者が UI で数回で到達品質を出した (Image #4/#5)。**Image #5** (歩行介助シーン、黒ポロ + 青ランヤード + 青アクセント背景) を新 baseline PNG に採用 + `illust-job-care.png` として mockup 配置 → Round α care 完了。真理ソース 7 ファイル + PNG 差替 + ChatGPT UI プロンプト集 (`docs/specs/chatgpt-ui-prompts.md`) を **PR #49** で一括更新・マージ。

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run (Phase 2B-exec): https://aozora-sync-flry56mxwa-an.a.run.app (稼働中、本セッション変更なし)

## 今セッションで完了したこと

### マージ済 PR (1 件)

| PR | タイトル | 内容 |
|---|---|---|
| #49 | `feat(aozora-illust): 制服 spec pivot (V-neck scrub → 黒ポロシャツ) + 生成経路 pivot (API → ChatGPT UI) + Round α care 完了` | 決裁者判断 (2026-07-02) による全面刷新。真理ソース 7 ファイル (CLAUDE.md / reference_illustration_baseline.md / outfit-spec.txt / verification-checklist.md / SKILL.md / codex-rewrite-template.txt / illust-refresh-ledger.md) を "V-neck scrub" → "黒ポロシャツ" に置換、コーポレートカラー #00C4CC / #575656 / #f8f5ee を明示、画風スペックから江口寿史等の作家名を除外。baseline PNG を Image #5 に差替、旧 Phase 1.5 版を archive/2026-07-01/ に保管。`illust-job-care.png` = Image #5 (歩行介助シーン) 採用。`docs/specs/chatgpt-ui-prompts.md` 新設 (PREAMBLE + 12 SCENE ブロック、決裁者原稿ベースの最小条件版)。gen.sh に `--composition-ref` / `--composition-mask` / `--quality` / `--skip-baseline` flags 追加 (本セッションの実験用)。13 files, +516 / -146 |

### 確立した実証知見

#### 1. API `v1/images/edits` の identity 保持限界

**8 連続失敗を経て確定した事実**:
- baseline PNG が portrait crop なら prompt mandate は portrait bias を突破できない (v6-v9 で 5 連続 solo)
- 案 2 (nurse を composition-ref に追加) で multi-person 突破 → clipboard/pen action 継承の別問題発生
- 案 C (2-stage generation, reference-free layout → baseline refine) で介護 action 描画は成功 → **identity が Layout の caregiver との hybrid になり別人化**
- 教訓: identity + 構図 + action の 3 拍子は API `v1/images/edits` では原理的に困難。ChatGPT UI は内部で multi-turn refinement + endpoint 選択 + fidelity tuning を実施していると推定 (Codex 診断)

#### 2. ChatGPT UI 経路が character-critical illustration の decisive answer

- 決裁者が UI で数回試行して Image #4 (第 1 案、identity + 歩行介助 + 黒ポロ) → Image #5 (改善版、施設 context + 青アクセント背景 + brand color natural 配置) に到達
- API 経路で 8 回試行して届かなかった品質を **UI では 2 回目で達成**
- 教訓: character-critical では **UI の業界知識 + 内部最適化に委ねる方が Claude が SCENE を細かく指定するより結果が良い**

#### 3. 最小条件プロンプト方針

- Claude が SCENE を詳細に書くと Claude の想定バイアスが混入 (「care=食事介助」等)
- **職種 + accessory rule + composition の最小条件のみ渡し、SCENE は UI に判断させる**方が variant 多様性と自然さで優れる
- 実装: `docs/specs/chatgpt-ui-prompts.md` の 12 SCENE ブロックは全て最小条件版 (JOB CATEGORY + ACCESSORY RULE + OUTFIT VARIATION + COMPOSITION の 4 項目のみ)

#### 4. gen.sh に追加した実験的 flags (人物なし挿絵 or 将来の実験用)

- `--composition-ref=<path>`: 既存の成功画像を composition-ref として image[0] に挿入、baseline は image[1,2] へシフト。solo portrait bias を打ち消す
- `--composition-mask=<path>`: mask edit (action envelope 置換) 対応。Python PIL で mask PNG 生成推奨
- `--quality=<low|medium|high|auto>`: 品質指定を CLI から可変に (Stage 1 実験で cost 節約)
- `--skip-baseline=on|off`: baseline PNG を送らない (composition-only edit) — Stage 1 で用途特化

これらは **character-critical では非使用**、人物なし挿絵 (`illust-numbers.jpg` の pallet 追従等) or 将来の実験用途に保持。

## 進行中 (次セッション着手対象)

### Phase 3 Round β/γ (11 枚、ChatGPT UI で本田様生成待ち)

| 順 | ファイル | ラウンド | 依頼済 SCENE ブロック |
|----|-----|-----|-----|
| 1 | `illust-job-consultant.png` | β | #2 |
| 2 | `illust-job-nurse.png` | β | #3 |
| 3 | `illust-job-office.png` | β | #4 |
| 4 | `illust-job-it.png` | β | #5 |
| 5 | `illust-job-care-2.png` | β | #6 |
| 6 | `illust-job-care-3.png` | γ | #7 |
| 7 | `illust-job-default.png` | γ | #8 |
| 8 | `illust-job-consultant-2.png` | γ | #9 |
| 9 | `illust-job-office-2.png` | γ | #10 |
| 10 | `illust-philosophy.jpg` | γ | #11 |
| 11 | `illust-flow.jpg` | γ | #12 |

**各生成の手順** (`docs/specs/chatgpt-ui-prompts.md`):
1. ChatGPT UI で新規会話を開く
2. PREAMBLE をコピペ
3. `.claude/memory/illustration-baseline.png` (Image #5) を UI 会話にアタッチ → "match this character's identity exactly" と明示
4. 該当 SCENE ブロックをコピペ
5. 生成完了 → Claude に送信 → 10 項目採点 → OK なら mockup 配置 → NG なら SCENE 微調整 or 再生成指示
6. **1 会話 = 1 illustration** で運用 (drift 防止)

### Phase 4 (mockup 反映 + PR)

Round β + γ の 11 枚が集まり次第:
1. `mockup/assets/img/illust-*.png` に一括配置
2. feature branch → PR → `/code-review low` → 認可 → squash merge
3. 公開モック URL で確認

## 予算現況

- **OpenAI API**: 累計 $4.12 / $10 (残 $5.88)。**以降 character-critical 用途では非使用**、人物なし挿絵 (illust-numbers.jpg) or 実験用途で保持
- **ChatGPT UI**: 本田様の ChatGPT Plus/Pro subscription 内で完結 (別勘定)

## 次のアクション (3 分割)

### 即着手タスク

**即着手タスクなし** — 次セッション冒頭で本田様が ChatGPT UI で Round β 1 枚目 (consultant) を生成して送信していただき次第、10 項目採点 + mockup 配置から着手。

### 条件待ち (明示 trigger 付き)

| # | 項目 | 分類 | trigger | 充足時のタスク |
|---|------|-----|--------|-------------|
| 1 | Round β consultant 生成物 | 新規価値創出 (起点指示待ち) | 本田様「consultant 生成した、これで良い?」 | 10 項目採点 → OK なら `mockup/assets/img/illust-job-consultant.png` 配置 → 次 (nurse) 促す |
| 2 | Round β nurse 生成物 | 同上 | 本田様 nurse 提示 | 同 |
| 3 | Round β office 生成物 | 同上 | 本田様 office 提示 | 同 |
| 4 | Round β it 生成物 | 同上 | 本田様 it 提示 | 同 |
| 5 | Round β care-2 生成物 | 同上 | 本田様 care-2 提示 | 同 |
| 6 | Round γ 5 枚 (care-3 / default / consultant-2 / office-2 / philosophy / flow) 生成物 | 同上 | 本田様 提示 | 同 |
| 7 | Phase 4 mockup 反映認可 | 同上 | 11 枚集まり本田様「Phase 4 進んでよい」 | feature branch → 11 枚一括配置 → PR → 認可 → squash merge |
| 8 | 前々 handoff 継続項目 | 同上 | 本田様指示 | `/healthz` rename / WP 統合 / Billing budget alert $5 |

### 却下候補 (記録のみ)

| # | 項目 | 分類 | 着手しない理由 |
|---|-----|-----|--------------|
| 1 | Round α consultant/nurse (旧 V-neck scrub 版 mockup 残存) を prompted に再生成 | 新規価値創出 (起点 unclear) | Round β で本田様が UI 再生成するときに置換される、Claude 側で先取りする理由なし |
| 2 | gen.sh 拡張 flags (`--composition-ref` 等) を character-critical に活用 | 新規価値創出 (起点 unclear) | 決裁者判断で UI 経路に統一済、API 経路は人物なし挿絵に限定 |
| 3 | baseline PNG に close-up を追加生成 | 新規価値創出 (起点 unclear) | Image #5 単独で drift 起きたら次セッション協議、先取りせず |

### 終了判定

🛑 **即着手 = 0 件、条件待ち 8 件全て trigger 未充足** → **executor 領分の作業ゼロ、セッション終了推奨**

本田様の ChatGPT UI 生成を待つフェーズ。AI 側から着手候補を昇格させない (4 原則 §1: decision-maker 領分)。

## セッション終了可否

✅ **終了可**。本セッションの目的 (制服 spec pivot、生成経路 pivot、Round α care 完了) は全て達成。PR #49 merged、main sync 済、git clean。次セッションは本田様の UI 生成物を受け取ってから着手。
