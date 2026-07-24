---
updated: 2026-07-15
---

## 現在のミッション
リクルートページの基礎トンマナ全面刷新 (第2フェーズ)。コーポレートカラー(#00c4cc)をあえて外し、確立済みの江口寿史風イラスト世界観から抽出した配色に統一する。加えてスクロール演出(視差効果)の強化、AI臭さの払拭による洗練度向上を段階的に進める。

## 背景・why
決裁者から「ページ全体をみて今の色合いに変えましょう。コーポレートカラーをあえて外してリクルートページを際立たせます。もっと視差効果というか参考で渡したwebページ(tcy.co.jp/recruit, g-s.dev)のようにスクロール時にアクションやアニメーションが動くような感じにしたほうが良い。全体をもうちょっとAI臭い感じを払拭してより洗練された今のイメージによく合うものにアップデートすべき」との方針転換指示(2026-07-15)。`/impl-plan` フルモードで Stage 1(完了・PR #64)に続き、Stage 2(スクロール演出・視差効果の強化)を計画・承認・実装・本番確認まで完了(2026-07-15、決裁者「すすめて」で明示承認、PR #65)。演出パターンは「ヒーローパララックス＋stagger強化の組合せ」・強度は「控えめ・上品」を決裁者選択。Stage 3 は Stage 1・2 の結果を decision-maker が確認し、具体的な指摘を得てから個別 `/impl-plan` で着手する(現時点で未承認)。

## 完了の定義 (Stage 2: スクロール演出・視差効果の強化) — 2026-07-15 実装完了・PR #65・本番確認済み
- [x] スクロール時、ヒーロー背景がコンテンツより低速で移動する(視差比率 0.2、最大55px)（証明: Playwright `scrollTo(0,300)`/`scrollTo(0,2000)` で背景transform値の変化・上限クランプを確認）
- [x] career-ladder等の複数要素セクションで、各ステップが70ms刻みの遅延差で順次フェードインする（証明: Playwrightで各要素の `transition-delay` 実測。項目数が増えた場合のcatch-all delayも検証）
- [x] `prefers-reduced-motion: reduce` 環境でパララックス・staggerが無効化され、即時全表示される（証明: Playwright `page.emulateMedia({reducedMotion:'reduce'})`）
- [x] site.js読み込み失敗を模したケースで、全 `[data-reveal]` 要素が `is-visible` となり非表示のまま残らない(既存フォールバックの回帰なし、確認済み)
- [x] モバイル幅(375px)でレイアウト崩れ・横スクロールが発生しない（証明: Playwright 375pxフルページスクリーンショット、横スクロール0を確認）
- [x] 本番相当の環境でconsoleエラー0件、体感スクロールジャンクなし(目視確認済み)

## 進行中のtasks (Stage 2) — 全完了
- [x] タスクA: ヒーロー背景パララックス実装 (site.js + components.css)
- [x] タスクB: career-ladder / job categories にstagger遅延強化 (70ms刻み、catch-all含む)
- [x] タスクC: prefers-reduced-motion / JS失敗フォールバックの回帰確認・修正
- [x] タスクD: Playwright実機検証(通常/reduced-motion/JS失敗/複数viewport幅) + `/code-review medium`(2エージェント×2ラウンド)

### 実装メモ (3段階の検証で発見・修正した実害バグ、いずれも実機スクリーンショット/測定で確認)
- **1段目 (実装中の内部code-review)**: 初回実装は `.hero__bg` に `inset:-18%` の固定%拡張で視差余白を確保していたが、`background-size:cover` の基準軸(幅基準/高さ基準)がボックスの縦横比に依存するため、拡張により基準軸が反転し画像が意図せずズームされる実害バグを発見(スカイラインがほぼ見切れる状態)
- **2段目 (同、修正後の再レビュー)**: 固定pxオフセット + `@media (min-width:1200px)` に変更するも、1200-1390px帯(1280px/1366pxなど主要ノートPC解像度を含む)で同じ不具合が再発すると判明。`assets/js/site.js` が実行時に `sky-hero.jpg` の自然サイズと hero の実測寸法を読み込み、余白(60px)を加えても `cover` が幅基準のままであることを確認できた場合のみ視差を有効化する方式に変更(固定ブレークポイント非依存)。sky-hero.jpg は過去に複数回差し替えられており画像アスペクト比依存の実測方式が必須と判断。同時に `will-change` の常時付与→IntersectionObserverでのbind/unbind連動化、`category-card` の項目数超過時catch-all遅延値の不一致(280ms→350ms)、負の`scrollY`(iOS rubber-band)未クランプも修正
- **3段目 (PR #65作成後、4エージェント独立レビュー×3が一致指摘)**: 2段目の実測方式は画像読み込み時に安全性判定を一度だけ実行しており、有効化後にウィンドウをリサイズして危険な比率へ転じても再判定されず、まさに1段目のズームバグが再発する経路が残っていた。`resize`イベント(200msデバウンス)で安全性判定を再実行するよう修正し、実機で1440px(有効)→1280px(危険帯、自動無効化)→1440px(再有効化)の往復動作を確認。あわせて非同期コールバック(probe.onload/resize後の再判定)がtry/catchで保護されていなかった構造的ギャップも解消

## Stage 2 追加改善 (2026-07-15 決裁者フィードバック対応、PR #67〜#70・全完了・本番確認済み)
Stage 2 (PR #65) 本番反映後、決裁者から追加フィードバック4件を受け、同日中に段階的に実装・検証・マージ:
1. 「ヒーローセクションにもっとダイナミックな動画的な動きが欲しい」→ Remotion(企業向け有償ライセンス要)・AI動画生成(未導入ツール要)は不採用と判断、追加コストゼロの CSS Ken Burns ズーム(26秒ループ、scale 1→1.06)を追加 (PR #67)
2. 「トップページ全体でスクロールしたら各セクションもそれぞれ動くように」→ career-ladder/category-card のみだった70ms刻みstaggerを mission-card(Philosophy)/stat(数字)/flow__step(選考フロー)/faq__item(FAQ) にも拡張 (PR #68)
3. 「全然動きません、固定のまま。わからないならWebでベストプラクティスを調べて」→ WebSearchで2026年時点のベストプラクティスを調査、`animation-timeline: view()` (CSS Scroll-driven Animations、Chrome/Edge/Safari対応・Firefox安定版は2026-07時点で未対応のため `@supports` でIntersectionObserver版をfallback維持) に刷新。スクロール位置そのものに要素のopacity/scale/位置がリアルタイム連動するよう変更 (PR #69)
4. 「動くタイミングが速すぎる」→ `animation-range` を `entry`(要素自身の高さ基準、薄い要素で一瞬終わる欠陥)から `cover`(ビューポート高さ基準、要素の高さに関わらず安定して長め)に変更、進行速度を緩和 (PR #70)

- [x] タスクE: ヒーロー背景 Ken Burns ズームループ追加、既存パララックスと別要素に分離し競合回避 (PR #67)
- [x] タスクF: 全セクション要素(mission-card/stat/flow__step/faq__item)へのstagger演出拡張 (PR #68)
- [x] タスクG: `animation-timeline: view()` によるスクロール連動アニメーション化、非対応ブラウザへの `@supports` fallback (PR #69)
- [x] タスクH: `animation-range` を entry→cover に変更しスクロール連動の進行速度を緩和 (PR #70、実測: career-ladder__step 780px / faq__item 660px でゆっくり完了)

いずれも Playwright 実機検証(通常スクロール・`prefers-reduced-motion: reduce`・本番 GitHub Pages)を実施し、決裁者のフィードバックを受けて次PRへ反映するサイクルで進めた。次に決裁者が実機で確認し、体感速度・強度が適切か追加フィードバックを待つ状態(2026-07-15時点で最新フィードバック未着)。

## Stage 1 (完了・2026-07-15 PR #64) 履歴
配色システムの再定義(tokens.css/components.css新パレット、career-ladderコントラスト調整、CLAUDE.md更新)完了・本番確認済み。詳細diffは PR #64 参照。

### フォローアップ (Stage 1 スコープ外、decision-maker 確認後に着手)
- `mockup/jobs/*.html`(33ファイル)+カテゴリページの `<meta name="theme-color">` が旧 `#00c4cc` のまま。Stage 1 は「トップページのみ」の承認スコープのため意図的に対象外。横展開時に一括更新
- `CLAUDE.md` line 44「コーポレートカラー: ブルー #00C4CC」(メインキャラクター画像生成セクション)と `docs/specs/chatgpt-ui-prompts.md` のイラスト生成プリアンブルが、実際に採用済みのイラスト実測配色(コバルトブルー系, sky-hero.jpg 等)と乖離。イラスト生成は decision-maker 領分のクリエイティブ仕様のため、更新要否は decision-maker 判断待ち
- career-ladder level-4/5 の背景色コントラストが低い(実測 1.3:1、ほぼ同系統の濃紺)。高さの階段状レイアウトで序列は視覚的に伝わっているため非ブロッキングだが、Stage 3(コンポーネントリデザイン)で改善余地あり

## ロードマップ (Stage 3、Stage 2決裁者確認後に個別 impl-plan で仕切り直し)
- **Stage 3: コンポーネント単位のリデザイン(AI臭さの払拭)** — 最も主観的な要素のため、Stage 1・2の結果を決裁者に見せ、具体的な指摘(角丸・ソフトシャドウ・pill型ボタン等のSaaS的表現をポスター的・シャープな表現へ、等)を得てから着手。スコープ未確定

## 採用担当コンサルフィードバック (2026-07-23、5項目)
決裁者が共有した採用コンサル意見5項目のうち、Phase Aモック範囲に収まる①のみ先行着手すると決裁者判断。②③④はPhase B以降の機能要件(地図検索+GPS、外国人採用特設ページ、チャットボット)、⑤(スタッフインタビュー)は2026-07-14決裁者指示による廃止の再考が必要なため、いずれも未着手・decision-maker判断待ち。

- [x] **① 職種ごとの色分け**(PR #72、2026-07-23完了・マージ済み): 募集職種カード・求人一覧カードの左帯+職種ラベルチップを4系統(介護=コバルト青/看護=ティール/事務=オーカー/IT=インディゴ)でアクセント色分け。Evaluator全AC PASS・`/code-review medium`実施・WCAG AA(6.5:1〜11.8:1)クリア
  - **既知制約**: ダミー求人データに「看護師」ラベルの求人が1件も存在せず、`jobs-nurse.html`の全カードはラベル基準でcare(青)色になる。看護系統色(ティール)は`index.html`のカテゴリカード1箇所にのみ出現。実データ反映(Phase B)まで解消しない、decision-maker確認済みの既知制約
  - **フォローアップ**: `sync/src/sync/templates/job_list.html`(Phase B動的レンダリング側)への同一ロジック追従は未着手
- [x] **② 条件+地図検索(GPS、市区町村レベル、13拠点)**(PR #76→#78→#80→#83→#84(クローズ)→#85→#86→#87、2026-07-24 Google Maps版で最終確定・マージ済み): 求人一覧ページ(`jobs.html`)に職種/雇用形態/エリア/フリーワードのANDフィルタ + 地図(13拠点) + GPS現在地からのHaversine距離順並べ替えをプログレッシブエンハンスメントで追加。既存34求人カードのマークアップは無改変
  - **地図表現の刷新(PR #78→#80→#83→#87、4段階)**: PR #76当初はLeaflet.js+国土地理院タイルを採用したが、決裁者フィードバック「実地図画像である限りトンマナと合わない」を受けPR #78で完全廃止、自作の抽象ブロブ図に置き換え。決裁者が参考画像(九州県境シルエット)を共有しPR #80で九州7県シルエットSVG(`assets/img/kyushu-map.svg`、県重心1点にピン集約)へ再刷新。「ピンが県1点に団子状で雑」というフィードバックを受けPR #83で拠点別の実位置表示に変更、続けて「拡大化するとレイアウト的に良い」との評価を得て福岡/鹿児島の拡大2パネル化(PR #84として作成)。さらに「理想はGoogleマップで対応できないか」という明示指示を受け、過去の「実地図はトンマナと合わない」判断を明示的に上書きしGoogle Maps JavaScript API埋め込みへ最終刷新(PR #87)。PR #84はmainとコンフリクトしフォールバックとしての実益もないためクローズ判断
  - **Google Maps採用の前提整備(PR #85→#86)**: APIキー発行のためGCPプロジェクト専用のWIF(Workload Identity Federation)+GitHub Actionsワークフローを新規ブートストラップ(`aozora-sns-auto`と同じ1リポジトリ=1poolパターン、`docs/runbooks/wif-setup.md`)。APIキーはHTTPリファラー制限付きクライアントキー(`https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/*`, `http://localhost:8989/*`)としてMaps JavaScript API限定で発行、`gcloud services api-keys describe`で実測確認済み
  - **コンプライアンス判断(2026-07-24、decision-maker確認済み)**: CLAUDE.mdの「外部SaaS不採用」「ismap準拠GCP内完結」原則との関係を確認し、「表示するのは拠点所在地(公開情報)のみで応募者個人情報を伴わない」ことを理由にこのケースは適用対象外と判断して進める合意を得た
  - Google Maps実装は福岡/鹿児島2エリアをそれぞれ独立した`google.maps.Map`インスタンスとして拡大表示(旧2パネルSVGのレイアウト評価を引き継ぐ)、`fitBounds`で拠点へ自動フィット。ピンは職種カテゴリ配色のカスタムSVGアイコン、`styles`配列でPOI/交通機関/道路ラベルを非表示にしブランドカラーへ簡略化。`/code-review high`+Evaluator(全7 AC PASS)で検証、InfoWindow外側クリック未対応・キーボードアクセシビリティ(`optimized:false`)・空エリアパネル非表示・fitBoundsタイミングの4件を修正
  - 拠点座標: 正本データ(`scripts/mockup-rebuild/jobs_data.json`の番地レベル住所)を国土地理院AddressSearch APIで一度きりジオコーディングし`scripts/mockup-rebuild/build_geo_data.py`にハードコード(可視化刷新後も座標データ自体は流用)。求人34件はカテゴリ内訳 介護20/事務10/IT4(看護0、①と同じ既知制約)
  - JS無効時は既存34カード全表示にフォールバック(Playwright実機検証済み)
  - **技術的負債(記録のみ)**: `google.maps.Marker`(レガシーAPI、非推奨だが廃止予定日なし)を使用。`AdvancedMarkerElement`への移行はMap ID+Cloud Console側スタイル設定が別途必要なため今回は見送り
  - **フォローアップ**: `jobs-care/nurse/office/it.html`(職種別一覧)・Phase B動的レンダリング側(`sync/src/sync/templates/job_list.html`)への横展開は未着手
- [ ] ③ 外国人採用特設ページ(特定技能・介護ビザ) — 内容の事実正確性に法務/人事確認が前提。decision-maker指示待ち
- [x] **④ 採用チャットボット**(PR #89→#90、2026-07-24完了・本番稼働確認済み): 決裁者が方式(GCP自前構築=Vertex AI Gemini + Cloud Run、求人FAQのみスコープ、APIキー発行なしのキーレス認証)を確定し着手。`chatbot/`に独立FastAPIバックエンド新設、`index.html`/`jobs.html`にチャットウィジェット埋め込み
  - **モデル/リージョン確定(ground truth実測)**: `gemini-3.5-flash-lite`はasia-northeast1で404、globalで200 → `VERTEX_LOCATION=global`採用。実測結果は`~/.claude/memory/reference_vertex_ai_to_gemini_enterprise_2026.md`にも記録
  - **知識ベース**: FAQ5件+求人34件サマリーをイメージに同梱(RAGなし、Phase Aの小規模データに対する意図的なシンプル設計)。`jobs.json`/`#faq`更新時は手動同期+再デプロイが必要(結合トレードオフ、README明記)
  - **レビュー2ラウンド**: 1回目`/code-review high`で認証迂回(X-Forwarded-For先頭→末尾)・データ流出(ローカル用query paramを本番で無制限許可)・到達不能コード(`str(Enum)`比較)等10件検出・修正。2回目で残存3件(MAX_TOKENS切れ未処理・CSS一律オフセット・定数重複)を検出・修正、以降重大指摘0件に収束
  - **デプロイ(2026-07-24)**: `aozora-chatbot`をasia-northeast1へ`gcloud run deploy --source`でデプロイ(`https://aozora-chatbot-1084369586348.asia-northeast1.run.app`)。ランタイムSA`chatbot-run`は`roles/aiplatform.user`のみ最小権限。デプロイ中に`Dockerfile`の`--mount=type=cache`(BuildKit機能)がCloud Buildの既定dockerビルダー非対応と判明、除去して解消(PR #90)
  - **本番実機確認**: GitHub Pages実URL上でPlaywrightにより送受信を確認(index.html/jobs.html両方)
  - **フォローアップ(未着手、記録のみ)**: 応答ストリーミング・RAG/ベクタDB・全ページ展開・GHA WIF自動デプロイ・知識ベース自動追従はいずれもPhase Aスコープ外として見送り、`chatbot/README.md`に明記
- [ ] ⑤ スタッフインタビュー再考 — 2026-07-14廃止指示の理由(実写とイラストの不整合)をコンサル提案(イニシャル+AI生成画像)が解消しうるため再検討の価値ありとdecision-makerに提示済み、再判断待ち

## 🔄 中断点（in-flight）
なし
