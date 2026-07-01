# Handoff — 2026-07-01 (Phase A aozora-illust Codex 統合 + /gpt-image edits API 実証セッション)

## TL;DR

本セッションで **aozora-illust スキルに Codex (GPT-5.5) prompt rewrite を恒久統合** (PR #43)。同実証中に派生して **`/gpt-image` グローバルスキルに `v1/images/edits` API 対応** を実装 (global config PR #334)。reference 画像を text 化せず pixel のまま API に渡せるようになり、Claude 経由でも ChatGPT UI 同等の identity 保持生成 (78-82% 一致率) が達成可能であることを実証。

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/
🚀 Cloud Run (Phase 2B-exec): https://aozora-sync-flry56mxwa-an.a.run.app (稼働中、本セッション変更なし)

## 今セッションで完了したこと

### マージ済 PR (1 件、本リポ)

| PR | タイトル | 内容 |
|---|---|---|
| #43 | `aozora-illust: Codex prompt rewriting を恒久統合 + care-2 高品質版差替` | `gen.sh` に `--codex-rewrite=on\|off` フラグ追加 (default on)。新規 `scripts/codex-rewrite.sh` + `prompts/codex-rewrite-template.txt` で SCENE を ChatGPT UI 風に rewrite してから生成。sheet モード自動 OFF / Codex 障害時 fallback / marker LAST occurrence 抽出。`illust-job-care-2.png` を Codex 最適化版に差替 |

### 派生で global config に反映した PR (1 件、別リポ `yasushi-honda/claude-code-config`)

| PR | タイトル | 内容 |
|---|---|---|
| #334 | `gpt-image: v1/images/edits API 対応で reference 画像から identity 保持生成` | `~/.claude/skills/gpt-image/SKILL.md` 全面改訂: endpoint 選択ガイド追加、Phase 0 mode 判定 (`--reference=<path>`)、Phase 3-3 を generations / edits 経路に branch 化、制約セクション更新。さらに本田様側で追加反映 (aspect ratio / evaluation 指標 / preset) |

### 確立した実証知見

#### Codex prompt rewrite の効果 (PR #43, #334 で恒久統合)

`gpt-image-2` の品質差は **model 違いではなく endpoint と prompt 質** に起因。Codex (GPT-5.5) で prompt を rewrite すると ChatGPT UI 並のクオリティが得られる。aozora-illust の care-2 (5 人 recreation シーン) で実証済。

#### endpoint 選択が identity 再現の決定要因 (PR #334 で documenting)

| 経路 | 受け取れる入力 | identity 保持 |
|---|---|---|
| `v1/images/generations` (text-only) | text のみ | **不可能** (text 化で顔情報が失われる) |
| `v1/images/edits` + reference 画像 | text + image[] (1-16 枚) | **可能** (pixel のまま届く) |

本セッション中の検証で reference を含む生成タスクで [Image #9] (ChatGPT UI 由来 target) との一致率 **78-82%** を達成。

#### Sonnet 5 default 化 (v2.1.197)

handoff 作成中に system-reminder で workflow.md / MEMORY.md 経由で確認。Sonnet 5 が Claude Code default、native 1M-token context、promotional pricing $2/$10 per Mtok (〜2026-08-31)。当環境は `settings.json` で Opus 4.7 固定継続。

## 重要な設計判断 (本セッション)

### Codex rewrite は default ON で恒久化、OFF は限定ケースのみ

PR #43 で `gen.sh` に `--codex-rewrite=on|off` フラグを追加したが、default ON で運用。OFF は (1) sheet モード (6 パネル構図厳密指定)、(2) SCENE 既に最適化済、(3) Codex 障害時の fallback、の 3 ケースのみ。

### Claude が間に入ると識別が劣化する問題の真因究明

本田様 feedback「Claude が間に入ると上手くいかない」の原因究明で **text 化で reference 識別情報が失われる構造的問題** を実証。`/gpt-image` を generations only から edits 対応に拡張することで Claude 経由でも ChatGPT UI 同等品質を達成可能にした (PR #334)。

### `chatgpt-image-latest` model は org KYC 必須

検証中に発覚: `chatgpt-image-latest` は OpenAI organization verification (KYC) 必須で 403 を返す。`gpt-image-2` は verification 不要で使用可、品質も最新。verification 後でも model 違いより endpoint 違いの方が品質に直結するため `gpt-image-2` + edits 経路で十分。

## 次のアクション (3 分割構造)

### 即着手タスク

**即着手タスクなし**。本セッションは「Codex 統合」「edits API 実証」をユーザー指示で完遂。次の着手は本田様の優先指示が trigger。

### 条件待ち (明示 trigger 付き、4 件 — 前 handoff から継承、本セッション変更なし)

| # | 項目 | カテゴリ | trigger | 充足時のタスク |
|---|------|---------|---------|--------------|
| 1 | **Phase A 決裁者承認の取得** | 新規価値創出 | 本田様 → 関係者へ公開モック URL + Loom ウォークスルー (5 分) を共有、承認/リビジョン回答到来 | リビジョン依頼内容に応じて機械生成スクリプト再実行で再整形 |
| 2 | **`/healthz` rename + redeploy** | 守り (修正) | 本田様 → 「/healthz 直して」明示指示 | `sync/src/sync/app.py` の `@app.get("/healthz")` を `/health` に変更 → pytest → buildx push → gcloud run deploy → curl 確認 (15-20 分) |
| 3 | **WP 統合 (Cloud Run server-to-server fetch 組込)** | 新規価値創出 | 本田様 → 「WP に Cloud Run の URL 組込開始」明示指示 + WP 環境のアクセス情報 | WP 側で `https://aozora-sync-flry56mxwa-an.a.run.app/jobs/{id}` を fetch する PHP/プラグインを実装、採用ページに埋込 |
| 4 | **Billing budget alert $5 設定** | 整理・点検 | 本田様 → 「設定したい」明示指示 (Console UI 操作なので本田様直接実施推奨) | GCP Console で budgets `$5` alert 作成 (5 分) |

### 却下候補 (記録のみ)

| # | 項目 | 着手しない理由 |
|---|------|--------------|
| 1 | mockup の追加 UI 機能 (検索フィルター高度化、お気に入り保存等) | Phase A 範囲外、Phase B 以降の WP プラグインで実装する想定。AI 起点の新規価値創出案発想は 4 原則 §1 違反 |
| 2 | `scripts/mockup-rebuild/` の Phase B template 移植 | Phase B 着手時の作業、現時点 trigger なし |
| 3 | 詳細ページの aside (関連求人) 表示ロジック改修 | 現状で機能、Phase B 着手時の作業 |
| 4 | 追加カテゴリのイラスト生成 (看護職 / 訪問介護 / リハビリ等) | 現時点で該当カテゴリの求人なし、ジョブカン側に該当カテゴリが追加されたら trigger 化 |
| 5 | care-3 / consultant / consultant-2 / office-2 を Codex rewrite で再生成して品質底上げ | Codex 統合 (PR #43) で基盤は整ったが、再生成は明示指示なき限り着手しない (整理・点検カテゴリ、4 原則 §1 違反防止) |

## Issue Net 変化

- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件

(本セッションは本田様の指示に従って PR #43 + global PR #334 を実施、Issue 化対象なし)

## 環境状態

| 項目 | 状態 |
|---|---|
| Git | clean、main 同期 (PR #43 merge 済、本 handoff PR 作成前) |
| 最新 commit | `083a001` (#43 aozora-illust Codex 統合 + care-2 差替) |
| Cloud Run service | `aozora-sync` 稼働中 (revision `00002-724` traffic 100%、本セッション変更なし) |
| GitHub Pages | `pages-build-deployment` success (commit `083a001`、2026-06-30T12:26:47Z 完了) |
| 残留プロセス | なし |
| OPEN PR | 0 件 |
| OPEN Issue | 0 件 |
| 関連 global PR | yasushi-honda/claude-code-config #334 merge 済 (本田様側で追加反映実施) |

## 構造的整合性チェック

| チェック対象 | 結果 |
|---|---|
| `/impact-analysis` (型・共有ロジック・設定) | ⏭️スキップ (PR #43 は skill 内 script 拡張 + PNG 差替のみ、型・共有ロジック変更なし) |
| `/new-resource` (新規テーブル/API) | ⏭️スキップ (該当なし) |
| `/trace-dataflow` (データフロー実装) | ⏭️スキップ (mockup 静的ファイル / skill 拡張、データフローなし) |
| グローバル memory scope チェック (§4.5) | ⏭️スキップ (本リポの `memory/` 配下変更なし、global config 側変更は別リポで完結) |
| 同根再発スキャン (§4.6) | ✅ 該当なし (本セッション feat PR のみ、修正 PR ナシ) |
| 対症療法判定 (§4.7) | ⏭️スキップ (修正 PR ナシ) |
| 残留プロセス | ✅ なし |

## 最終結論

🛑 **executor 領分の作業ゼロ、即時終了推奨**

- OPEN PR / Issue 0 件、Git clean、Pages build success (`083a001`)
- 即着手タスク = 0 件、条件待ち = 4 件 (全て本田様明示指示が trigger、現時点未充足)
- 残留プロセスなし
- 同根再発・対症療法判定: 該当なし (本セッション feat PR のみ)
- 関連 global PR #334 は本田様側で merge 済、本リポ側に作業 spillover なし
- 次セッションは本田様の優先指示 (Phase A 決裁者承認進行 / /healthz / WP 統合 / budget alert / 追加イラスト生成依頼の何れか) が trigger
