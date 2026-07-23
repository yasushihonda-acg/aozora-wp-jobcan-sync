# Handoff — 2026-07-23 (採用コンサルフィードバック5項目トリアージ、①職種色分け実装)

## TL;DR

**決裁者が共有した採用担当コンサルの意見5項目をPhase Aモック範囲・アーキテクチャ規模で分類し、①(職種ごとの色分け)のみ先行着手すると決裁者判断。plan mode でフル計画→実装→Evaluator独立検証→`/code-review medium`の2段階レビューを経てPR #72をマージ。②(地図検索+GPS)は実装前に規模感調査(拠点マスタ・地図ライブラリ選定を一次ソースで確認)を実施しGOAL.mdに記録。③④⑤はdecision-maker判断待ちのまま。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/

## 今セッションで完了したこと

### マージ済 PR (3件)

| PR | タイトル | 内容 |
|---|---|---|
| #72 | `feat(mockup): 職種ごとの色分けアクセントをカードに追加` | 募集職種カード(index.html 6件)・求人一覧カード(jobs.html+jobs-care/nurse/office/it.html 計62件)の左帯+職種ラベルチップを4系統(介護=コバルト青/看護=ティール/事務=オーカー/IT=インディゴ)でアクセント色分け。`tokens.css`に12トークン追加、modifier class方式(`.job-list-card--care`等)でCI(`test_design_tokens.py`)の`var()`直接参照制約に適合させた設計に調整 |
| #73 | `chore(handoff): GOAL.md に採用コンサルフィードバック5項目の状況を反映` | PR #72完了・②③④⑤未着手の状況をGOAL.mdに記録 |
| #74 | `chore(handoff): GOAL.md に地図検索(②)の規模感調査結果を反映` | ②の技術調査結果(拠点マスタ・地図ライブラリ・GPS・条件検索UIの現状)を記録 |

### 決裁者判断の記録

| 項目 | 決定 | 反映先 |
|------|------|-------|
| コンサル5項目の対応方針 | ①(職種色分け)のみPhase Aモック範囲で先行着手。②③④はPhase B以降の機能要件、⑤は2026-07-14廃止決定の再考が必要なためdecision-maker指示待ち | GOAL.md |
| ①の色の粒度 | 4系統グループ分け(介護/看護/事務/IT、中彩度に抑制) | plan、`tokens.css` |
| jobs-nurse.htmlの看護色不在問題 | 現状のままマージ(実データに看護師ラベルが1件も存在しないための既知制約、PR説明に明記して決裁者確認済み) | PR #72説明 |
| PR #72 code-review effort | medium | 実施済み |
| ②の次のアクション | 見積もりを決裁者に共有して判断を仰ぐ(この場でfull planは作成しない) | GOAL.md |
| ⑤の着手順 | 「最後にする」(②③④より後回し) | 本セッションの会話文脈(GOAL.mdには反映済みの記載なし、次セッションが参照する場合は本行を参照) |

### 技術的知見 (新規)

- **`sync/tests/test_design_tokens.py`はsync-*.css内の`var(--*)`参照がすべてtokens.css定義済みであることを検査するが、ローカルCSSカスタムプロパティ(`.modifier { --x: var(--y); }`)による間接参照パターンは想定していない**。modifier class経由で複数系統色を切り替える設計をする際は、ローカル変数の間接参照ではなく、各modifier class内で対象プロパティ(border-left-color等)を直接指定する方式にする必要がある(本セッションでこのCI失敗を実際に踏んで書き直した)
- **地図ライブラリ選定の一次ソース確認結果**(②の規模感調査、次にこの種の判断をする際の参考): 国土地理院タイル(地理院タイル)はPDL1.0で商用利用可・APIキー不要・無料(出典表示必須)、Leaflet.jsとの組み合わせが日本向けサービスの標準的選択。OpenStreetMap生タイルは法的には商用利用可だが公式ポリシーで「商用サービスの継続利用は非推奨、予告なくアクセス遮断され得る」と明記されており本番運用に不向き。Google Maps JavaScript APIは月10,000回表示まで無料だが2025-03に定額$200クレジット制度が廃止され従量課金化済み
- **`python3 -m http.server`のcharset mojibake既知問題(2026-07-15記録済み)の実運用ワークアラウンド**: `SimpleHTTPRequestHandler.guess_type()`をオーバーライドし`text/*`系MIMEに`; charset=utf-8`を付加するカスタムサーバースクリプトで回避可能(`end_headers()`のオーバーライドでは効かない、`guess_type()`側で上書きする必要がある)

## Evaluator・code-review 指摘の記録 (PR #72)

Evaluator(全AC PASS)と`/code-review medium`の両方が同一論点を独立に指摘: `jobs-nurse.html`は実データが全て「相談員」ラベルのため`--job-nurse`(ティール)トークンがサイト内のどのHTMLからも使われない状態になっている。これはlabel基準の分類方式(plan承認済み)の直接的な帰結であり「誤タグ付けバグ」ではないが、看護カテゴリだけ色分け機能が視覚的に機能しないという実害は残る。decision-maker確認の上、現状のままマージ・PR説明に明記する対応で合意。実データ反映(Phase B)時に解消見込み。

## 採用コンサルフィードバック5項目の状況 (詳細は`docs/handoff/GOAL.md`)

- [x] ① 職種ごとの色分け — 完了(PR #72)
- [ ] ② 条件+地図検索(GPS) — 規模感調査完了、decision-maker判断待ち
- [ ] ③ 外国人採用特設ページ — 未着手、decision-maker判断待ち
- [ ] ④ 採用チャットボット — 未着手、decision-maker判断待ち
- [ ] ⑤ スタッフインタビュー再考 — 未着手、decision-maker判断待ち(本人希望で優先順位を最後に設定)

## 次のアクション

### 即着手タスク
なし(②③④⑤いずれもdecision-maker側の判断・指示が必要)

### 条件待ち
| # | 項目 | trigger | 充足時のタスク |
|---|------|---------|--------------|
| 1 | ② 地図検索の実装着手 | decision-makerが規模感調査結果(GOAL.md記載)を確認し実装可否を判断 | plan modeでフルplan作成→実装 |
| 2 | ③ 外国人採用特設ページ | decision-makerが法務/人事部門確認の上で着手指示 | 内容仕様のヒアリング→plan mode |
| 3 | ④ 採用チャットボット | decision-makerがベンダー/予算方針を決定 | 方針に応じてplan mode |
| 4 | ⑤ スタッフインタビュー再考 | decision-makerが2026-07-14廃止決定の再考について指示(本人希望で②③④より後回し) | 復活する場合、イニシャル+AI生成画像の仕様を軽量プランで提示 |

### 却下候補
なし

## 最終結論

✅ **セッション終了可** — OPEN PR 0件、Git clean(main、origin/mainと同期済み)、即着手タスク0件・条件待ち4件、残留プロセスは他プロジェクト(sanwa-houkai-app)由来のNext.js devサーバーのみで本プロジェクトと無関係、既知blockerなし。
