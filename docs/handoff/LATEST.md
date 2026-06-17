# Handoff — 2026-06-18 (Phase B 着手 + Phase 2A.1a 完了セッション)

## TL;DR
フロント (Phase A) 決裁者反応待ちと並行してバック (Phase B) に着手。**Phase 0 (ローカル PoC) → 案 B 採用 (公式照会保留で進める) → ACG GCP プロジェクト確定 → `.envrc` セットアップ → Phase 2A.1a (parser 強化 + selectors.yaml + フィクスチャ拡充) まで 3 PR で完了**。次セッションは **Phase 2A.1b** (一覧ページ + CLI list) に直行可能。

## 今セッションで完了した変更

| PR | 内容 | コミット |
|---|---|---|
| #10 | Phase B Phase 0 — ジョブカン公開ページ動的プロキシ PoC (Python + httpx + BS4 + Pydantic + Jinja2 + Typer、17 pytest) | `3b5e83b` |
| #11 | ACG プロジェクト恒久設定 (`.envrc` + 新規 gcloud config `aozora-wp-jobcan-sync`) | `4b48644` |
| #12 | Phase 2A.1a — parser 強化 + selectors.yaml + フィクスチャ拡充 (32 pytest、code-review 5 件全対応) | `fb09651` |

5 PR の累積コミット (新しい順):
```
fb09651 feat(sync): Phase 2A.1a - parser 強化 + selectors.yaml + フィクスチャ拡充 (#12)
4b48644 chore(envrc): ACG プロジェクト恒久設定 (.envrc 追加) (#11)
3b5e83b feat(sync): Phase B Phase 0 - ジョブカン公開ページ動的プロキシ PoC (#10)
ef5ed07 chore(handoff): 2026-06-17 イラスト本家トンマナ整合セッションの handoff 更新 (#9)
221a7ac feat(mockup): イラスト 2 枚 (philosophy/flow) の肌色多様性を本家に合わせる (#8)
```

🔗 公開モック (Phase A): https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/

## 重要な設計判断 (確定済)

| 項目 | 確定値 | 根拠 / 経緯 |
|---|---|---|
| **採用アーキテクチャ** | 案 D = 動的プロキシ + 自社テンプレ再表示 | ジョブカン公開ページを Cloud Run で取得 → BS4 パース → 自社 BEM で再表示。応募はジョブカン直リンク (`/aozora/entry/new/{id}`) |
| **進め方** | 案 B = 公式照会送付保留、Phase 2A → 2B を進める | 「ドラフトのエリア = 本番ドメイン未切替」の位置づけで、規約リスク低 |
| **段階分割** | 2A.1a / 2A.1b / 2A.2 の 3 PR | Codex 計画レビュー (3 回目) 推奨、品質ゲート回しやすい |
| **GCP プロジェクト** | `aozora-wp-jobcan-sync` (project number 1084369586348) | yasushi.honda@aozora-cg.com 所有、ACG 専用、命名規則 = リポ名 |
| **GitHub アカウント** | yasushihonda-acg | ACG アカウント、`.envrc` で自動切替 |
| **本番化判断** | 別 Phase (Phase 2B 完了後) | DNS 切替 (`recruit.aozora-cg.com`) は決裁者承認 + 公式照会要否含めて再検討 |

## Phase 2A.1a 実装サマリ

| ファイル | 内容 |
|---|---|
| `sync/src/sync/selectors.yaml` | CSS セレクタ / synonym map / sanitize allowlist の宣言的設定 |
| `sync/src/sync/config.py` | Pydantic `SelectorConfig` + `load_selector_config()` + `ConfigError` (StructureChange と分離) |
| `sync/src/sync/parser.py` | ハードコード排除、`_normalise_jobcan_url` (protocol-relative 防御)、`_attr` (list 返却防御)、synonym map (fuzzy 禁止)、DOM order 堅牢化 |
| `sync/tests/test_design_tokens.py` | grep ベースで sync 参照 var(--foo) が tokens.css に存在するか自動検証 (AC-5) |
| `sync/tests/fixtures/jobcan_responses/job_{1668696,1690435,2199420,2215694}.html` | 相談員 / IT / 事務 / 介護 の 4 件追加 (計 5 fixtures) |
| `sync/tests/fixtures/jobcan_responses/list_{care,nurse,it,office}.html` | 一覧ページ 4 件 (Phase 2A.1b で parse_job_list 用) |

検証: pytest **32 件全 PASS**、ruff/pyright clean、3 段品質ゲート (safe-refactor → code-review medium → evaluator) 全通過。

## 構造的整合性チェック

| 項目 | 状態 | 備考 |
|---|---|---|
| /impact-analysis | ⏭ スキップ | パッケージ内部の改修、API/型/共有ロジック影響なし |
| /new-resource | ⏭ スキップ | 新規 API/テーブルなし |
| /trace-dataflow | ⏭ スキップ | データフロー実装は Phase 2A.1b 以降 |
| ADR 要否 | 不要 | 案 D 採用は sync-strategy.md に既反映、技術選定は impl-plan で網羅 |
| ドキュメント整合 | ✅ | docs/specs/sync-strategy.md (案 D) / jobcan-html-structure.md (selectors 全反映) と一致 |

## Issue Net 変化
- Close 数: 0 件
- 起票数: 0 件
- Net: 0 件
- 補足: 案 B + 段階分割で順次進行、triage 基準 #5 (ユーザー明示指示) で個別タスク化済み (全完了)

## 次のアクション (3 分割)

### 即着手タスク (次セッション、番号単位認可で順次実行可能)

| # | タスク | A/B/C | ROI | 工数 | DoD | 関連 |
|---|---|---|---|---|---|---|
| **1** | **Phase 2A.1b: JobListItem + parse_job_list + job_list.html + CLI list** | C (起点指示済) | バック実装の next step、Phase 2A.2 (FastAPI) の前提 | 1 セッション (T5/T6/T7) | T5: `JobListItem` Pydantic モデル + `parse_job_list()` (parser.py 拡張、selectors.yaml の `list` セクション使用) / T6: `templates/job_list.html` + `sync/src/sync/static/sync-job-list.css` (mockup 触らない、Codex Q1 反映) / T7: `python -m sync list --category-id 18773 --out ...` CLI / pytest +N 件で PASS | sync/tests/fixtures/jobcan_responses/list_{care,nurse,it,office}.html (4 件取得済)、docs/specs/jobcan-html-structure.md §8 (selectors 確定済) |
| 2 | Phase 2A.2: FastAPI 4 分割 + cache + Dockerfile + 動作確認 | C (起点指示済) | Cloud Run デプロイの直前段階 | 1 セッション (T8a-d + T9 + T10 + T11) | T8a (client 例外構造化) → T8b (cachetools.TTLCache + 注入) → T8c (FastAPI endpoint + status mapping) → T8d (structured logging + fallback 302/500 一本化、Codex Q5 反映) → T9 (pytest +20 件) → T10 (Dockerfile slim + non-root + PORT env) → T11 (uvicorn + Docker + Playwright 視認) | 依存: タスク #1 完了 |

CRITICAL プロセス併記 (次セッション AI への申し送り):
- 3 ファイル+ → `/safe-refactor` + `/code-review medium`
- 5 ファイル+ → evaluator 分離プロトコル
- 大規模 PR (3+ ファイル / 200+ 行) → `/codex review` でセカンドオピニオン
- 案 B (Phase 2A.1a) で確立した品質ゲート 3 段パターンを継承

### 条件待ち (明示 trigger 付き)

| # | 項目 | A/B/C | trigger | 充足時のタスク |
|---|---|---|---|---|
| 1 | フロント (Phase A) 決裁者反応収集 | C | 本田様 → 決裁者へモック URL 共有後、決裁者から「OK」「変更要望」「Phase B へ」等の明示反応 | 反応内容に応じて個別対応 (イラスト微調整 / Phase A ゲート通過判定 / その他) |
| 2 | ジョブカン公式照会送付 (`docs/specs/sync-strategy.md` §2 文面) | C | 本田様 → 「照会送る」明示指示 | ドラフト文面の契約プラン名等の最終確認 + 送付サポート (送付自体は本田様) |
| 3 | env-isolation.md 補強 (`.gitconfig.local` + `~/.claude/projects/aozora-wp-jobcan-sync.env`) | B 修正 (write) | 本田様 → 「env-isolation 補強やって」or `/project-setup` 再起動指示 | `.gitconfig.local` 作成 + プロジェクト定義ファイル設置、別 PR で対応 |
| 4 | 本番 DNS 切替 (`recruit.aozora-cg.com`) | C | 決裁者の Phase A 承認 + Phase 2B 完了 + 公式照会回答 (or 「照会なしで本番化」明示判断) | DNS 切替 + 本番運用準備 |

### 却下候補 (記録のみ・包括指示では参照しない)

| # | 項目 | 検討経緯 | 着手しない理由 |
|---|---|---|---|
| 1 | パート/アルバイト求人の fixture 取得 | Phase 2A.1a で介護職一覧から「【パ】」タグを推測 → 取得した 2199420 は実際は正社員だった | 真のパート/アルバイト求人 ID は category_id 横断検索が必要、Phase 2A.1b の一覧パース実装後に自動取得可能 |
| 2 | category_id ↔ 職種名マッピングの完全表 | 17 件のうち 4 件確認済 (介護/相談員/IT/事務)、残り 13 件は名称不明 | Phase 2A.1b の一覧実装でブラウザベース検証時に判明、housekeeping (A) で起動禁止 |
| 3 | parse_job_detail 関数長 (~95 行) の分割 | safe-refactor LOW、Phase 0 でも同じ指摘で defer 済 | Phase 2A.2 で FastAPI handler 経由参照になる前提で同時対応、現状は早すぎる |
| 4 | RequiredTableField.canonical 削除 (17 行短縮) | code-review LOW、削除可能だが YAML ドキュメント性失う | trade-off ありで現状維持、Phase 2A.2 で再検討 |
| 5 | config.py `@lru_cache` テスト isolation 改善 | code-review LOW | 現状テストでは未顕在化、Phase 2A.2 で FastAPI lifespan 整理時に同時対応 |
| 6 | Phase 2A.1a 申し送り 9 件 (Phase 2A.1b/2A.2 で対応予定) | code-review / evaluator で defer 判断 | 各 Phase の本実装と一緒に対応する方が手戻り少 |

## Phase 2A.1a 学習・知見 (次セッション活用)

| 観点 | 学び |
|---|---|
| Codex 計画レビューの価値 | 計画段階で 3 回目の Codex 相談 (sync-strategy.md ベース) で「T6 mockup 制約違反」「T8 過大、4 分割必要」「fuzzy 禁止」を発見、実装前に修正でき手戻り削減 |
| 3 段品質ゲートの定着 | safe-refactor → code-review medium → evaluator が Phase 0 + Phase 2A.1a で 2 回連続成功、Phase 2A.1b/2A.2 でも継承 |
| selectors.yaml + Pydantic の効用 | 構造変化時のホットフィックスが Python コード変更なしで可能 (YAML 編集のみ)。Phase 2A.2 で Cloud Run デプロイ後の運用工数を大幅削減できる見込み |
| direnv hook の subshell 制約 | Claude Code の Bash tool は subshell 毎に新規起動、direnv hook が効かない場合 `gh auth switch --user yasushihonda-acg` を明示実行 (PR push 直前の保険) |

## 残留プロセスチェック
✅ 残留プロセスなし (Phase 2A.1a 完了時点で dev server / Playwright 全停止確認済)

## 再開可能性判定
✅ **再開可能** — Git clean / OPEN PR ゼロ / 即着手タスク 2 件 (Phase 2A.1b/2A.2) / Pages CI success / 残留プロセスなし

---

## 最終結論

✅ **セッション終了可** — 次セッションは Phase 2A.1b 着手で直行可能

- OPEN PR / OPEN Issue: 共に 0 件
- Git clean / リモートと同期済 / Pages CI success
- 即着手 = 2 件 (Phase 2A.1b → 2A.2 の依存順)、条件待ち = 4 件 (decision-maker 領分中心)、却下候補 = 6 件 (Phase 内対応 or 申し送り)
- 残留プロセスなし
- 既知の blocker: なし (案 B 採用で公式照会回答待ちは Phase 2B 完了まで非ブロッカー化済)
