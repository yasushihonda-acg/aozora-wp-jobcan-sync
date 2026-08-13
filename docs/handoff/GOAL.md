---
updated: 2026-08-11
---

## 現在のミッション
Phase A(GitHub Pages静的モック、Jobcan実求人382件中37件=約9.7%のみのサンプル)から Phase B(Cloud Run + Firestore、382件全件を6時間ごと自動反映済み)への本番切替を前倒しする。トップページ・静的アセットも Cloud Run へ全面集約する。

## 背景・why
社長から「実際のJobcan環境では今も382件の実求人が公開されている。それを勝手に減らして見せる(Phase Aモックは37件のみ)のは非常にまずいのでは」との指摘(2026-08-08)。GitHub Pagesモックは既に一般公開URLであり、求職者が実際の募集内容より少ない件数しか見えない状態を「求人一覧」として公開し続けることは募集機会の毀損につながるリスクがあると判断し、Phase B前倒しを決定。調査の結果、単なるDNS切替ではなくPhase Bテンプレートのデザインパリティ・トップページの配信元決定が必要と判明。decision-maker判断: ①トップページもCloud Runに全面集約(WordPress統合は既に撤回済み、GitHub Pagesは仮置き) ②v1はカテゴリ別一覧でリリース(地図検索+GPS+フリーワード横断検索はStage 3以降)。段階リリース(Stage1: 静的配信基盤+トップページ移植 → Stage2: 求人詳細デザインパリティ → Stage3: 求人一覧デザインパリティ → Stage4: 本番公開前の健全性対応 → Stage5: ドメイン切替)で進行中、各Stage完了後に決裁者確認を挟む。

## 完了の定義 (Stage 1: 静的配信基盤 + トップページ移植 + リンク付け替え) — 2026-08-08 実装完了・本番デプロイ済み・PR #142
- [x] `sync/src/sync/app.py` に `/assets` StaticFilesマウント + `/`(トップページ)ルートを追加
- [x] `base.html`/`job_list.html`/`job_detail.html` の CSS参照・canonical・戻りリンクをサイトルート絶対パス化、`PUBLIC_BASE_URL` 環境変数導入
- [x] `job_list.html` の求人カードサムネイル(`thumbnail_url`)も相対パス起因の404を `site_relative` フィルタで解消(選択当初は未想定、Playwright実機確認で発見)
- [x] `mockup/index.html` は GitHub Pages(Phase A、現在も本番公開中)と共有のため直接編集はせず、Cloud Run配信時にサーバ側でリンクを書き換える方式(`_render_top_page`)を採用。カテゴリ別12箇所の遷移先を `crawler.KNOWN_CATEGORY_IDS` の category_id へ対応、全件横断リンク7箇所は暫定的に最大カテゴリ(介護職 `18773`)へ
- [x] `sync/Dockerfile` のビルドコンテキストをリポジトリルートに変更し `mockup/assets`/`mockup/index.html` を同梱、`infra/README.md` のデプロイ手順を更新
- [x] ローカル`docker build`実機確認(トップページ・静的アセット200)、`uvicorn`+実Firestore+Playwrightでトップページ→カテゴリ一覧→求人詳細の遷移をクリックで確認、console error 0件・404 0件(証明: network requests全件200)
- [x] `sync`のpytest 265件全PASS(新規テスト21件追加: トップページ・静的アセット配信・リンク書き換え・canonical・thumbnail site_relative化・chatbot .htmlリダイレクト・キャッシュヘッダー・PUBLIC_BASE_URL警告。3ラウンドのcodex review + セカンドオピニオンで発見された指摘への対応分を含む)
- [x] 本番デプロイ完了。`aozora-sync`をリビジョン`aozora-sync-00005-mkw`へ更新(トラフィック100%)、`aozora-chatbot`のALLOWED_ORIGINSに新オリジンを追加。検証URL `https://aozora-sync-flry56mxwa-an.a.run.app/` でトップページ→カテゴリ一覧→求人詳細→チャットボット送受信(関連求人カードの`.html`リダイレクトも含む)を実機確認、console error 0件・404 0件(証明: Playwright network requests全件200、チャット実送信で実応答を確認)

🎯 **Stage 1 完了**。

## 完了の定義 (Stage 2: 求人詳細ページのデザインパリティ) — 2026-08-08 実装完了・PR #144(#144後続修正込み)、2026-08-09 本番デプロイ完了
- [x] Phase A(`mockup/jobs/*.html`)と同じセクション構成(ヒーロー+ハッシュタグ+イラスト/サマリー/仕事内容/応募資格/待遇・福利厚生/選考フロー/entry-cta/関連求人サイドバー/固定応募バー/チャットボット)を Firestore 実データからレンダリング。Phase A 生成スクリプト(`scripts/mockup-rebuild/rewrite_job_details.py`)の抽出ロジックを `sync/src/sync/detail_sections.py` へ純粋関数として移植(37件全件で抽出結果を検証、給与regexの複数資格対応バグ1件を修正)
- [x] `base.html` に header/hero/footer/entry_cta_bar/chat_widget の空 block を追加、`job_detail.html` を全面書き換え。`job_list.html` は無変更(Phase Aの求人一覧もチャームレスなため影響なし、Stage 3スコープ温存)
- [x] `firestore_repo.get_by_category`(array_contains、単一フィールドのため複合インデックス不要)で関連求人3件を取得・自己除外、Firestore例外時はサイドバーのみ非表示で本体は200を維持
- [x] `sync_status="closed"` の求人で応募導線(サマリーCTA/entry-cta/entry-cta-bar/ヘッダーCTA)を全て非表示
- [x] `mockup/assets/css/sync-job-detail.css` を削除、`components.css`/`pages.css` へ移行
- [x] 品質ゲート: `codex review --base main -c model_reasoning_effort=high`(findings 0件)+ `pr-review-toolkit` 3エージェント並列(code-reviewer/silent-failure-hunter/type-design-analyzer)。silent-failure-hunterがCRITICAL 1件(関連求人取得のexcept Exceptionが Firestore I/O と純粋ロジックを一括捕捉し誤ラベル)含む妥当な指摘4件を発見、type-design-analyzerが未使用フィールド`DetailView.work_items`を発見。いずれも同PR内で修正済み(discriminated union化等の設計改善提案は実害なしのため見送り、判断の記録のみ)
- [x] pytest 340件全PASS(新規74件)、ruff/pyright 0エラー。Playwright実機確認(実Firestore、`/jobs/104625` デスクトップ1440px・モバイル375pxとも console error 0件・静的アセット全200・横スクロール無し、`/jobs/?category_id=` 側の視覚的リグレッション無し)

### 既知の制約(記録のみ)
- 本番Firestoreに `sync_status="closed"` の求人が0件のため、closed表示は自動テストのみで検証済み。実機での目視確認は次回 closed 求人が発生した際に実施
- JobPosting JSON-LD の `datePosted`/`validThrough` は `JobSnapshot` に対応する真値が無いため出力しない(Phase A のハードコード値は引き継がない、意図的な設計)

### 本番デプロイ(2026-08-09、`infra/README.md` §3・§4bの手順、revision `aozora-sync-00006-5f6`)
- Docker image をリポジトリルートから `sync/Dockerfile` でビルド + push、`gcloud run deploy` で新イメージへ切替(SA/IAM等の初回設定は既存のため不要、image差し替えのみ)
- Playwright実機確認(`https://aozora-sync-flry56mxwa-an.a.run.app`): トップページ・静的アセット・求人一覧(`?category_id=18773`)・求人詳細(`/jobs/2264205`)いずれも200、console error 0件(favicon.ico 404はブラウザ自動リクエストによる既知の想定内挙動)。求人詳細の全セクション(サマリー/仕事内容/応募資格/待遇/選考フロー/entry-cta/関連求人サイドバー)を目視確認
- チャットボット疎通確認: 起動→サジェスト質問クリック→回答受信(関連求人リンク3件、`.html`互換リダイレクト308含む)まで正常動作、`aozora-chatbot`側CORS(`ALLOWED_ORIGINS`)も既存設定のまま機能

🎯 **Stage 2 完了(実装・本番デプロイとも完了)**。

## 完了の定義 (Stage 3: 求人一覧ページのデザインパリティ) — 2026-08-09 実装完了・本番デプロイ完了・PR #148
decision-maker指示「Stage 3を進めて」を受け、スコープを「検索/地図/GPSも含めてフルパリティ」(Phase Aの`mockup/jobs.html`が持つ条件検索+Google Maps地図+GPS距離順並べ替え+フリーワード検索も含む)に確定して着手。

- [x] 拠点ジオコーディングを13→27拠点へ拡張(Firestore全382件監査で判明した15拠点のうち14拠点を新規ジオコーディング。住所は社内「事業所マスタ」スプレッドシートから取得し国土地理院APIでジオコーディング。残り1件「共同生活援助」は12事業所を横断する求人のため単一住所なし、地図ピンなしとして意図的に除外、`sync/src/sync/facility_geo.py`)
- [x] `list_sections.py`: 職種ラベル→カテゴリ4系統(介護/看護/事務/IT)の色分けマッピングをPhase Aの5種から17種(`crawler.KNOWN_CATEGORY_IDS`全域)へ拡張
- [x] `search_index.py`: Firestore全件から検索/地図用JSON(`GET /jobs/search-index.json`、`/assets/`配下のPhase A静的ファイルとの衝突を回避した新規動的エンドポイント)を構築
- [x] `app.py`: `/jobs/`の`category_id`を任意化(無指定時=全件検索ページ、指定時=既存のカテゴリ別グリッドに色分け+meta-grid追加)
- [x] `map-search.js`: `data-jobs-endpoint`属性でPhase A(静的JSON)/Phase B(動的JSON)のデータソースを切替(`chat-widget.js`の`data-endpoint`と同一パターン)
- [x] Google Maps APIキーのリファラー制限にCloud Run originを追加(`docs/runbooks/wif-setup.md`に手順記録)
- [x] 品質ゲート: `codex review --base main -c model_reasoning_effort=high`(2回実施、指摘計2件=雇用形態ラベルの順序依存/Phase A側の通知要素欠如、いずれも修正済み)+ `pr-review-toolkit` 3エージェント並列(code-reviewer/silent-failure-hunter/type-design-analyzer)。実害バグ2件(施設キー衝突による地図ピン・件数の誤マージ、地図ピン表示名への生住所リーク)+サイレント失敗3件(検索機能ロード失敗の完全無音化、未知施設/職種のログ欠如)を検出・修正。type-design-analyzerの型設計改善提案(戻り値のpydanticモデル化等)は実害なしのため見送り(判断の記録のみ)
- [x] pytest 382件全PASS(新規55件)、ruff/pyright 0エラー。Playwright実機確認(ローカル: 職種/エリアチップフィルタでカード件数がFirestore実カウントと一致、フリーワード検索、地図に27拠点全ピン表示、カテゴリ別ページの色分け+meta-grid。本番: `https://aozora-sync-flry56mxwa-an.a.run.app/jobs/`でconsole error 0件、382件全求人+検索パネル+地図の表示を確認)

🎯 **Stage 3 完了(実装・本番デプロイとも完了)**。

## 完了の定義 (Stage 4: 本番公開前の健全性対応) — 2026-08-09 実装完了・本番デプロイ完了・PR #150
社長に見せて採用が決まったら即座にドメイン切替(Stage 5)できる状態を作るための健全性対応。着手前のセッションで「WordPress統合という工程自体が既に無く、実体はCloud Runドメイン切替である」ことを本田様と確認したうえでplan mode実施。

- [x] `X-Robots-Tag: noindex, nofollow` の条件付き化 — 全レスポンス無条件付与だった状態から、公開3ページ種(`/`・`/jobs/`・`/jobs/{id}`、200のときのみ)だけindexable化。**このままドメインを当てても検索エンジンに一切載らない最大のブロッカーだった**(証明: 本番実測 `curl -sI $URL/ $URL/jobs/` にヘッダー無し、`$URL/healthz`・404には有り)
- [x] カスタム404ページ(`not_found.html`、FastAPI既定のJSON応答から人向けHTMLへ。`.json`/`/assets/`配下はJSONのまま維持)
- [x] 旧URL→新URLの301リダイレクト。Phase A求人37件が既にcanonical宣言している`/jobs/{id}/`(末尾スラッシュ)が本番実測で**307**だった問題を解消(証明: 本番実測 `curl -sI $URL/jobs/104625/` → `301` + `location: /jobs/104625`)。`/index.html`・`/jobs.html`・`/jobs-{care,nurse,office,it}.html`も301でカバー(証明: 本番実測、6種全て301+期待locationと一致)
- [x] `sitemap.xml`/`robots.txt`動的生成(証明: 本番実測 `/sitemap.xml` が390件=静的8+active求人382件を絶対URLで列挙、closed求人は除外)
- [x] OGP/Twitter Cardメタタグ追加、Phase Aからの退行(og:*が0個)を解消(証明: 本番実測 `/jobs/104625` のog:urlがcanonicalと一致)
- [x] Slack→Google Chat webhook移行(`notify_slack`→`notify_ops`、secret名`slack-webhook-url`→`ops-webhook-url`、Slack絵文字記法→Unicode絵文字)。組織の実運用チャンネルがGoogle Chatだったため
- [x] 品質ゲート: `codex review`を2回実施(コミット前 high effort・PR作成後 strict-config high effort)。1回目でP1(未staged template)+P2(静的アセットのnoindex解除は誤りだった)を検出・修正、2回目はfindings 0件。`pr-review-toolkit`3エージェント並列(code-reviewer/silent-failure-hunter/pr-test-analyzer)によるセカンドオピニオンで、404ページ・sitemap.xmlの`render_*()`呼び出しがtry/exceptで保護されておらずJinja2例外発生時に無ブランド・無ログの生500へ落ちるCRITICAL 1件・HIGH 1件を検出(実機再現確認済み)、同PR内で修正。テストカバレッジ不足4件(5〜7)も全て追加
- [x] pytest 435件全PASS、ruff/pyright 0エラー。本番デプロイ(`aozora-sync-00008-99r`)後、Playwright実機確認(トップ・一覧・詳細・チャットボット送受信・関連求人カード表示、console error 0件— favicon.ico 404のみ、既知の想定内挙動)

**未検証(Secret未設定のため)**: Google Chat通知の実送信確認(AC8)。`notify_ops()`のペイロード/クエリパラメータ保持は`test_notifications.py`のrespx実POSTモックで検証済みだが、実際のGoogle Chat webhook URL発行はdecision-maker領分のため、Secret Manager登録後に別途確認が必要(手順: `infra/README.md` §1.5)。

🎯 **Stage 4 完了(実装・本番デプロイ・実機確認とも完了)**。次のStage 5(ドメイン切替 `recruit.aozora-cg.com`)着手は decision-maker 判断待ち — DNS操作はIT担当者/外部ベンダー(権威DNS `ns1/ns2.canonet.ne.jp`)経由の依頼が必要なためリードタイムを考慮すること。

## 完了の定義 (Stage 4 追加対応: GitHub Pages恒久リダイレクト) — 2026-08-09 実装完了・マージ・GitHub Pages実機確認完了・PR #152

決裁者から「GitHub Pages(37件サンプル版)はあくまで決裁者自身が進捗確認のために直接見る試験ページであり、実データ382件版(Cloud Run)が完成した今、今後も決裁者がブックマーク等でこの古いページを見続けてしまい『件数が合っていない』指摘が再発するリスクがある」との指摘。対策として44ファイルへ恒久リダイレクトを実装。

- [x] 新規スクリプト `scripts/mockup-rebuild/add_pages_redirects.py`: 求人詳細37件・`jobs.html`・カテゴリ別4件・`job-preview.html`・`index.html`の計44ファイルへ、Cloud Run(検証用URL)への meta refresh リダイレクトを冪等に挿入。`--base-url`引数を持つため Stage 5 のドメイン切替後は1コマンドで再適用可能
- [x] SEO一次情報確認済み(Google Search Central "Redirects and Google Search"): 即時(0秒)meta refreshは永続リダイレクト扱い
- [x] `mockup/index.html`はCloud Run自身の`/`が同じファイルを読んで配信する共有ソースのため、`sync/src/sync/app.py`の`_render_top_page()`に自己ループ防止のタグ除去処理(`_TOP_PAGE_PHASE_A_REDIRECT_RE`)を追加
- [x] `jobs.html`はcodex reviewの指摘(P2)を受け修正: `mockup/index.html`から`?job_type=visit`/`?job_type=care-manager`というクエリ付きでリンクされており、Cloud Run側は`job_type→category_id`変換を行うが静的meta refreshはクエリを読めないため、インラインJS(`location.search`読み取り)+ noscriptフォールバックへ変更
- [x] 品質ゲート: codex review 2回(コミット前・strict-config)ともfindings 0件〜1件(P2、修正済み)。`pr-review-toolkit`2エージェント(code-reviewer/pr-test-analyzer)によるセカンドオピニオンで重大な問題なし、テストカバレッジ指摘1件(カテゴリID二重管理のdrift検出テスト)を追加対応
- [x] pytest 439件全PASS、ruff/pyright 0エラー。GitHub Pages実機(Playwright)で反映確認: トップページ・求人詳細・`job_type`クエリ付きURL(3パターン)いずれもCloud Run側の正しいURLへ自動遷移

🎯 **完了**。GitHub Pagesは以後Cloud Runへの導線としてのみ機能し、37件版が決裁者の目に触れることは無くなった。

## 完了の定義 (AIチャット知識ベースをPhase B連携へ移行) — 2026-08-09 実装完了・本番デプロイ完了・実機検証完了・PR #154

decision-maker指摘「AIチャットのほうの機能も今回のアップデートに追随できてる？定期スクレイピングのときの情報が常にAIチャットの対象ソース(RAG)になるのが本来必要な要件ですよね？」を起点に調査した結果、AIチャットボット(`chatbot/`)の求人知識ベースがPhase Aの静的37件データのまま2026-08-08(PR #141)を最後に更新停止しており、サイト本体(Firestore、6時間ごと自動同期・実求人390件)と情報不整合を起こしていた本番不具合を発見・修正。

- [x] `sync`側に新規 `GET /jobs/chatbot-knowledge.json`(`chatbot_knowledge.build_chatbot_knowledge`)を追加。Firestoreスナップショットからchatbot向け9フィールド形状(id/title/category/employment/area/facility/city/service_types/url)を都度生成。`service_types_from_address()`で施設名タグ(全角括弧内、11種の語彙)からサービス種別を導出
- [x] `chatbot`側の`DEFAULT_JOBS_DETAIL_URL`を上記エンドポイントへ切替。同梱の古い`jobs_detail.json`(37件固定)+手動更新スクリプト(`build_jobs_detail.py`)を完全削除。`bundled_knowledge()`はFAQのみのフォールバックに変更(求人0件時はコンテキストで推薦を明示的に抑止、古いデータを実データとして答えてしまう経路を構造的に除去)
- [x] 品質ゲート: codex review 3回(P1 1件・P2 2件を検出・修正、最終ラウンドはfindings 0件) + pr-review-toolkit 2エージェント(pr-test-analyzer/silent-failure-hunter、CRITICAL 1件・HIGH 1件・Important 3件を検出・修正)。修正過程で`_install()`の非原子性という新たな実バグを自己発見・修正
- [x] 設計変更: 当初のasyncioバックグラウンドタイマー方式の定期リフレッシュは、Cloud Runの既定CPU割り当て(リクエスト処理中のみ、`aozora-chatbot`が`cpu-throttling`既定=有効であることを実測確認)の下では機能しないと判明し、`/chat`リクエスト駆動の遅延リフレッシュ方式へ全面再設計(`_maybe_refresh_knowledge`)。`/health`に`seconds_since_last_success`/`stale`フィールドを追加し可観測性を改善
- [x] pytest: sync 463件・chatbot 86件全PASS、ruff/pyright とも0エラー
- [x] 本番デプロイ(sync→chatbotの順)+ 実機検証完了: `chatbot-knowledge.json`が382件を正しい形状で返す、chatbot `/health`が`{"source":"fetched","job_count":382}`、Playwrightで実機チャットから「鹿児島で訪問看護」「博多で介護職」を質問し正しい求人(サービス種別・エリアとも一致)と正しい詳細URL(`/jobs/{id}`、`.html`なし)が返ることを確認。コンテキストサイズ実測: system_instruction 32,589文字(旧5,109文字の約6.4倍、圧縮は今回のスコープ外、必要になれば別対応)

🎯 **完了**。AIチャットは以後、人手の作業なしに6時間ごとのスクレイピング結果を自動的に反映する。

## Stage 5 調査結果(2026-08-09、実行はしていない・decision-maker判断待ち)

decision-makerから「今日Cloud Runページを決裁者に見せ、カスタムドメインを当てて移行を進める想定(システム部にDNS依頼)、GA4設定も検討」との方針共有を受け、実際に`gcloud`コマンドで検証した結果:

- **`gcloud beta run domain-mappings create`を実行し実測**: `aozora-cg.com`のSearch Console所有権検証が未完了のため`ERROR: The provided domain does not appear to be verified`で即座に失敗(副作用なし、マッピングは作成されず)。**検証完了が絶対的な前提条件**と確定
- **`gcloud domains verify`は仕様上「in-browser workflow」**(`gcloud domains verify --help`で確認)。TXTレコード値の取得にはGoogle Workspaceアカウント(`yasushi.honda@aozora-cg.com`)に紐づくブラウザ操作が必須で、CLI/AIだけで完結する方法は存在しない
- **手順は本質的に2段階**: ①本田様がSearch Console検証(TXTレコード、システム部へ依頼) → 検証完了後に②`gcloud beta run domain-mappings create`実行(私が可能)→ 払い出されたCNAME値をシステム部へ改めて依頼、という順序。1回のシステム部依頼にまとめることは技術的に不可能(CNAME値は①完了後にしか判明しない)
- **システム部への依頼文テンプレートを作成済み**(本セッションの会話ログ参照、TXT値は本田様がSearch Consoleで取得後に空欄へ埋めるだけで送信可能な形)
- GA4導入・Google Chat webhook Secret登録は、いずれも本田様の手元作業(測定ID取得/webhook発行)が先に必要なため今回は保留(decision-maker選択)

## トンマナ刷新(第2フェーズ) — Phase B前倒しのため一時保留(2026-08-08、以下は保留時点の状態)
リクルートページの基礎トンマナ全面刷新 (第2フェーズ)。コーポレートカラー(#00c4cc)をあえて外し、確立済みの江口寿史風イラスト世界観から抽出した配色に統一する。加えてスクロール演出(視差効果)の強化、AI臭さの払拭による洗練度向上を段階的に進める。

決裁者から「ページ全体をみて今の色合いに変えましょう。コーポレートカラーをあえて外してリクルートページを際立たせます。もっと視差効果というか参考で渡したwebページ(tcy.co.jp/recruit, g-s.dev)のようにスクロール時にアクションやアニメーションが動くような感じにしたほうが良い。全体をもうちょっとAI臭い感じを払拭してより洗練された今のイメージによく合うものにアップデートすべき」との方針転換指示(2026-07-15)。`/impl-plan` フルモードで Stage 1(完了・PR #64)に続き、Stage 2(スクロール演出・視差効果の強化)を計画・承認・実装・本番確認まで完了(2026-07-15、決裁者「すすめて」で明示承認、PR #65)。演出パターンは「ヒーローパララックス＋stagger強化の組合せ」・強度は「控えめ・上品」を決裁者選択。Stage 3 は Stage 1・2 の結果を decision-maker が確認し、具体的な指摘を得てから個別 `/impl-plan` で着手する(現時点で未承認)。Phase B前倒し完了後に再開判断。

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

## Stage 2 追加改善 (2026-07-26 決裁者フィードバック対応、PR #106〜#109・全完了・本番確認済み)
2026-07-15時点で「最新フィードバック未着」だった状態から間を置いて決裁者が本番を確認し、フィードバック4件を受け同日中に段階的に実装・検証・マージ:
1. 「スクロールアニメーションが中途半端で動いたか分かりにくい」→ 実測の結果 ①Chrome/Edge/Safari等`animation-timeline: view()`対応ブラウザで`transition: none`が`transition-delay`を巻き添えで無効化し、意図していた70ms刻みの段差演出が完全に機能していなかったバグ ②変化量(translateY/scale)自体が小さすぎる、の2点を特定・修正 (PR #106)
2. 決裁者スクリーンショット報告「数字で見るセクションのスクロールアニメーションが壊れている」→ `.section--band`の`overflow: hidden`が子要素`.stat`の`animation-timeline: view()`の進捗計算を破壊し、スクロールしても固定値のまま一切追従しない実害バグと判明・修正 (PR #107)
3. 「モッサリしていて、スクロールの特定の位置に来たら途中で止まらず動ききってほしい」→ `animation-timeline: view()`のscroll-scrub方式は仕組み上「スクロールを止めると演出も途中で止まる」ため要件と技術的に両立不可と判断し撤去。加えて表示トリガーが親セクション単位(丈の高いセクションで先頭が視界に入った瞬間に配下カード全部が表示済み判定される構造的バグ)だったことも判明・修正。カード単体をIntersectionObserverで個別監視し、時間ベースのCSS transitionで確実に完了する方式に統一 (PR #108)。`/codex review-diff`(Bash版、effort=high)で「site.js読み込み失敗フォールバックが新しい個別カードセレクタを対象外にしており、JS障害時に主要コンテンツが非表示のまま固まる」P1バグを検出、同PR内で即修正・Playwright再検証
4. 「いいですね。速度が速すぎるので、もっとじわっとゆったりした動きで一気に動くのが良い」→ 初速が非常に速いease-out-expo系カーブ(0.16,1,0.3,1)+550msを、初速の穏やかなease-out-cubic系(0.33,1,0.68,1)+1100msへ変更。段差も70ms→130ms刻みへ比例調整 (PR #109)

- [x] タスクI: `transition: none`が`transition-delay`を無効化するバグ修正+変化量拡大 (PR #106)
- [x] タスクJ: `.section--band`の`overflow: hidden`がview-timelineを破壊するバグ修正 (PR #107)
- [x] タスクK: scroll-scrub方式撤去、カード個別IntersectionObserver監視+時間ベースtransitionへ全面刷新、`onerror`フォールバック追従 (PR #108)
- [x] タスクL: easing/durationをより緩やかな質感へ調整 (PR #109)

いずれもPlaywright実機検証(通常スクロール・`prefers-reduced-motion: reduce`・モバイル375px・JS読み込み失敗シミュレーション)を実施し、キャッシュ起因の誤検証を`page.route`によるキャッシュ完全回避で都度排除した上で判定した。次に決裁者が実機で確認し、追加フィードバックを待つ状態(2026-07-26時点で最新フィードバック未着)。

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
  - **知識ベース**: FAQ5件+求人34件サマリーをイメージに同梱(RAGなし、Phase Aの小規模データに対する意図的なシンプル設計)。`#faq`更新時はFAQのみ手動同期が必要。求人データは2026-07-26以降、起動時にGitHub Pagesから自動フェッチ(下記参照)
  - **レビュー2ラウンド**: 1回目`/code-review high`で認証迂回(X-Forwarded-For先頭→末尾)・データ流出(ローカル用query paramを本番で無制限許可)・到達不能コード(`str(Enum)`比較)等10件検出・修正。2回目で残存3件(MAX_TOKENS切れ未処理・CSS一律オフセット・定数重複)を検出・修正、以降重大指摘0件に収束
  - **デプロイ(2026-07-24)**: `aozora-chatbot`をasia-northeast1へ`gcloud run deploy --source`でデプロイ(`https://aozora-chatbot-1084369586348.asia-northeast1.run.app`)。ランタイムSA`chatbot-run`は`roles/aiplatform.user`のみ最小権限。デプロイ中に`Dockerfile`の`--mount=type=cache`(BuildKit機能)がCloud Buildの既定dockerビルダー非対応と判明、除去して解消(PR #90)
  - **本番実機確認**: GitHub Pages実URL上でPlaywrightにより送受信を確認(index.html/jobs.html両方)
  - **知識ベース自動追従化(2026-07-26完了)**: 求人データ更新のたびに再デプロイが必要だった鮮度問題を解消。`jobs_detail.json`はGitHub Pagesで同一ファイルが既に公開されている(Source `main`/path `/`)ことを実測確認し、同梱フォールバック兼fetch元として活用。起動時1回のみ取得、失敗時(ネットワークエラー/404/不正JSON/スキーマ不一致/空配列)は同梱データへフォールバックし起動継続(uvicornはlifespan startupで例外が漏れるとプロセスを終了させるため、全捕捉が必須要件)。取得データの`url`はid由来に再計算(`chat-widget.js`が`job.url`をそのまま`<a href>`に使うため信頼境界外として扱う)、改行/パイプ/制御文字を含むレコードは拒否。`/health`に`knowledge.source`(fetched/bundled)を追加し運用者が可視化可能に。反映は`build_jobs_detail.py`実行+`git push`のみで再デプロイ不要(ただしGitHub Pages CDNキャッシュ+Cloud Runインスタンス寿命により反映は非同期、詳細`chatbot/README.md`)。テスト73件全PASS、ruff/pyright clean、実機3パターン(fetch成功/404フォールバック/空文字キルスイッチ)確認済み
  - **フォローアップ(未着手、記録のみ)**: 応答ストリーミング・RAG/ベクタDB・GHA WIF自動デプロイはいずれもPhase Aスコープ外として見送り、`chatbot/README.md`に明記
  - **UX改善(PR #92、2026-07-24完了・本番デプロイ済み)**: 決裁者フィードバック(Mac IME誤送信/サジェスト不在/求人レコメンド不在/Markdown記号露出)に対応。IME変換確定Enterの誤送信をisComposing+グレース期間ガードで修正、Gemini構造化出力(`response_schema`)でフォローアップ質問サジェストと関連求人カード(最大3件、サーバ側ホワイトリスト照合済み)を毎回動的生成、`**太字**`/箇条書きのみ許可する軽量MarkdownをDOM生成でレンダリングしXSSも防止。`/code-review medium`で指摘8件中5件修正・3件は理由付きで対応見送り(詳細PR #92)。本番Cloud Run(`aozora-chatbot-00002-dll`)で疎通確認済み
    - **判明した運用上の注意**: `/code-review`はPR規模(large/medium)に応じて10並列/8並列の探索エージェントを起動するため、大規模PRでは相応に時間がかかる。今回large tierで探索エージェント1件がハング(87分間無応答)し、ユーザーが待ちきれず中断→medium tierで再実行する事態が発生。次回大規模PRのレビュー依頼時は所要時間の見込みを事前に一言添えるとよい
  - **求人レコメンドのサービス種別フィルタ修正**(PR #94、2026-07-25完了・本番デプロイ済み): 決裁者報告「デイサービスと検索してもデイサービス以外の求人が出る」に対応。`category`(care/it/office)のみでは施設内の実際のサービス種別(デイサービス/訪問介護/特養/GH/相談支援等)を区別できず、Geminiが施設名テキストの緩い照合でjob_idsを選んでいたのが原因。施設名から`service_types`を構造化データとして抽出し`jobs_detail.json`に追加、Geminiへのコンテキストとシステムプロンプトに明示ルールを追加。Codex `review-diff`セカンドオピニオンで複合サービス施設(相談支援専門員がGH検索に混入)の実害バグを1件検出・修正。`gcloud run deploy`で本番反映済み、実機確認済み(デイサービス/訪問介護/グループホーム検索いずれも正しく絞り込み)
    - **判明した運用上の注意(重要・再発)**: 本セッションで`/code-review`(引数なし: 6 finder+monitor構成)を実行、実測タイムスタンプでは起動から手動停止確認まで約1時間30分が経過（当時「20分以上未完了」と記録したが、これは起動から最初の途中経過報告までの時間にすぎず過小表現だった。事後ファクトチェックで訂正）。`/code-review low`で再試行するも約1時間13分経過後、実質何も処理していないように見えた(ユーザー観察。事後調査でも`low`実行時刻に対応するsubagent transcriptが一件も見つからず、この観察と整合する傍証あり)。上記PR #92の87分ハング事象に続き**2回連続**の再発。両回ともCodex `codex review --uncommitted`(review-diffモード)は正常完了し実害バグを検出できている。次回`/code-review`依頼時、一定時間(目安10-20分)で進捗が見えなければ`/codex review-diff`への切替を早めに提案すべき。3回目の再発時はCLAUDE.md「同じエラーで3回失敗→/codexで委譲」の基準に従い、`/code-review`依存からの切替をdecision-makerに提案する
  - **全ページ展開**(PR #97、2026-07-26完了・本番デプロイ済み): decision-maker指示により、`index.html`/`jobs.html`のみだった埋め込みをカテゴリ別求人一覧4件(`jobs-{care,it,nurse,office}.html`)+求人詳細34件(`jobs/*.html`)の全38ページへ拡大。バックエンド・ウィジェット本体は無変更、CSSリンク+scriptタグの機械的追記のみ(38 files, +76/-0)。`job-preview.html`(sync Phase 0 PoCの生成サンプル、参照0件)は公開導線がないため対象外とし除外。plan mode で相対パス依存・z-index競合・モバイル幅でのentry-cta-bar重なりを事前検証(いずれも問題なし)、`/code-review low main...HEAD`で指摘0件、Playwright実機確認(送受信+モバイルレイアウト)後にGitHub Pages本番反映を確認
  - **技術的負債整理 + `/code-review`ハング問題の原因調査**(PR #100、2026-07-26完了・本番デプロイ済み): decision-maker選択により、chat-widget.jsのbot応答時reflow3回発生(addMessage/addJobCards/addSuggestions個別scrollTop読み取り)を`scrollToBottom()`ヘルパーへ統合し1回に削減。あわせて手動更新が必要だった`jobs_summary.json`(拠点数・求人数等の集計)を廃止し、`jobs_detail.json`から`_summarize_jobs()`で起動時導出する方式に変更(知識ベース更新時の手動同期対象を1ファイル削減)。`/code-review low main...HEAD`で指摘0件(transcriptを直接確認し「diffなし」誤検知でないことも検証済み)、pytest 50件全PASS、Playwright実機確認(送受信+自動スクロール)後、Cloud Run本番反映(`aozora-chatbot-00004-tfd`)・疎通確認済み。並行してGOAL.md 81行目で示唆した`/code-review`ハング問題の原因調査を実施し、GitHub公式issue [anthropics/claude-code#80036](https://github.com/anthropics/claude-code/issues/80036)(nested subagentが`Agent`ツールを継承せずfan-outが単一コンテキストへ静かに劣化するバグ、OPEN・v2.1.217報告)が観測事実(large/medium tierでの長時間無応答)と一致する有力仮説と判明。当方の実測データをissueへコメントで補強済み([issuecomment-5082505972](https://github.com/anthropics/claude-code/issues/80036#issuecomment-5082505972))。詳細は`~/.claude/memory/reference_code_review_finder_agent_reliability.md`
- [ ] ⑤ スタッフインタビュー再考 — 2026-07-14廃止指示の理由(実写とイラストの不整合)をコンサル提案(イニシャル+AI生成画像)が解消しうるため再検討の価値ありとdecision-makerに提示済み、再判断待ち

## 🔄 中断点（in-flight）
- Secret Manager (`ops-webhook-url` = Google Chat webhook) は未設定 — `notify_ops()`は例外を握り込む設計のため実害なし、closed率サーキットブレーカー発火時のアラートが飛ばないだけ。組織の運用チャンネルはSlackではなくGoogle Chatのため、2026-08-09に通知実装をGoogle Chat webhook前提へ移行済み(`notify_slack`→`notify_ops`、secret名`slack-webhook-url`→`ops-webhook-url`、Slack絵文字記法→Unicode絵文字)。webhook URL入手後、`infra/README.md` §1.5の手順で追加可能
- ~~`mockup/index.html`の「訪問介護員(ヘルパー)」「ケアマネジャー」カードの`job_type`クエリ導線切れ~~ → **2026-08-09 PR #152で解消済み**。GitHub Pages(Phase A)側の`jobs.html`にjob_type-aware JSリダイレクトを追加したため、`map-search.js`が実行される前にCloud Run側の正しいフィルタ済みURL(`category_id=18986`/`18985`)へ自動遷移するようになった(実機Playwright確認済み)
- ~~**求人一覧/詳細ページ(`/jobs/`)に新規3職種の専用イラストが未反映**~~ → **2026-08-12 完了(PR #179)**。`sync/src/sync/selectors.yaml`の`thumbnail_categories`を6→9バケットへ拡張し、`夜勤専従（介護・看護）`/`施設長・管理者候補`を`care`から、`訪問看護`を`nurse`から新規バケット(`night-shift`/`facility-manager`/`visiting-nurse`)へ移動(既存バケットの`images`プールは無変更、他職種の既存割り当てに影響なし)。`night-shift`は`illust-job-night-shift-3.png`(訪問看護メイン絵と構図がほぼ同一)を意図的に除外し2枚プール、`facility-manager`は1枚プールのまま先行反映(バリエーション2枚生成は下記フォローアップ参照)。pytest 544件全PASS、`JOB_TYPE_NAMES`全17ラベルのthumbnail synonym網羅を保証する回帰テストを新設。codex review findings 1件(HTML経路のラベル順序依存、現在非稼働のロールバック専用パスのため理由付きで見送り、`infra/README.md` §9.4に注記追加)。Cloud Run Job (`aozora-sync-job`) 再ビルド・デプロイ・手動同期トリガーで本番反映済み、実機確認済み(`category_id=18987`→visiting-nurse系3枚のみ・`18988`→night-shift 2枚のみ・`18989`→facility-manager 38件同一画像・`18773`回帰確認で実装前ベースラインと完全一致)
- **【フォローアップ】`facility-manager`バリエーション2枚生成**: 上記の1枚プール先行反映に伴い、本番38件(施設長・管理者候補)のカードは全て同一画像になる。SCENE #20(`docs/specs/chatgpt-ui-prompts.md`)は生成済みプロンプトを流用可能、ChatGPT UI生成→10項目採点→耳元拡大確認(過去にピアス誤検知の経緯あり)→プール追加の手順で次セッション以降に対応
- ~~総合職（営業・管理職）イラストカード化~~ → **2026-08-13 完了(PR #183)**。SCENE #22で3枚生成、うち1枚は採点の過程で既採用済み`illust-job-facility-manager.png`と構図がほぼ同一(座り姿勢+タブレット+クリップボード+青バインダー+観葉植物+ガラス張り廊下)と判明し不採用。残り2枚(プレゼンシーン採用/廊下巡回シーンはバリエーション)で`illust-job-general.png`/`-2.png`としてカード化、`selectors.yaml`に`general`バケット新設(`office`から分離・移動)。pytest 544件全PASS、codex review findings 0件。**教訓: SCENE プロンプトに「既存カードと視覚的に区別できること」を明記していても、ChatGPT UI側が構図をdriftさせず別の既存カードと酷似した候補を出すことがある。10項目採点に加え、既存採用済み画像との構図比較を毎回明示的に行うべき**(次回以降のSCENE採点でも実施)。Cloud Run Job・Webサービスとも再デプロイ・実機確認済み(トップページカード表示・`category_id=71511`がgeneral系のみ・`58859`/`73697`の既存割り当てがベースラインと完全一致)。テキストタグから格上げ(7→6)
- ~~相談員イラストカード化~~ → **2026-08-13 完了(PR #186)**。SCENE #21で3枚生成、うち1枚(高齢の利用者様・ご家族と3人でテーブルを囲みタブレット提示するシーン)は採点の過程で既採用済み`illust-job-consultant.png`/`-2.png`(ケアマネジャー)と構図がほぼ同一(3人・テーブル囲み・タブレット提示のポーズまで酷似)と判明し不採用(PR #183と同じ構図drift再発パターン)。残り2枚のうち施設内案内の歩行シーンを`illust-job-consultation.png`としてトップページ「相談員」カードに採用、窓口一対一相談シーンを`illust-job-consultation-2.png`としてバリエーション採用。`selectors.yaml`に`consultation`バケット新設(`consultant`から「相談員」synonymのみ分離・移動、ケアマネジャー・サービス管理責任者の既存割り当ては無変更)。pytest 544件全PASS、ruff/pyright 0件、codex review(effort high)+ pr-review-toolkit セカンドオピニオンいずれもfindings 0件。Cloud Run Job・Webサービスとも再デプロイ・実機確認済み(トップページカード表示・`category_id=18984`がconsultation系2枚のみに分散・`18985`(ケアマネジャー)/`22014`(サービス管理責任者)の既存割り当てがベースラインと完全一致、console error 0件)。テキストタグから格上げ(7→6)。残り6職種(サービス提供責任者4件・サービス管理責任者6件・世話人6件・訪問リハビリ6件・サポート職7件・新卒既卒2件、2026-08-12実測)は未着手

## セッション履歴: 2026-08-11〜12 トップページ職種入口整備(PR #167〜#177、一部進行中)

決裁者から「アクティブな求人票が381件だと認識している」との指摘を発端に、ATS管理画面・公開求人サイト・Firestore・配信システムいずれも382件で一致していることを確認(こちら側の不整合ではなく決裁者側の一時的な認識ズレと判明)。その後、決裁者がトップページ本番URLを見て「求人票を見せる画面で、訪問看護の求人票が見えるためのタブがないかも。まず、全タブを確認して、入口を作るようにしないとダメかも」と指摘。調査の結果、トップページ「募集中の職種」カードは6職種のみで、job_types.pyの17区分中11職種がテキストタグ・専用カードいずれの入口も持たない状態だったと判明。

- [x] **軽量対応(PR #167)**: 既存6枚のビジュアルカードは維持し、残り11職種をテキストタグ(`.job-type-tags`)としてトップページに追加。`sync/src/sync/app.py`の`_LEGACY_CATEGORY_IDS`/`_TOP_PAGE_LINK_REWRITES`と`scripts/mockup-rebuild/add_pages_redirects.py`の`_JOB_TYPE_CATEGORY_IDS`を同期。codex review(medium)findings 0件
- [x] **ファビコン追加(PR #168)**: 未設定だったブラウザタブアイコンを、ブランドカラー(`#0a52b8`)ベースのSVG(`favicon.svg`、「ACG」の白文字)で新規追加
- [x] **訪問看護イラストカード化(PR #169→#170)**: SCENE #18(`docs/specs/chatgpt-ui-prompts.md`)をChatGPT UIで生成、血圧測定シーンをメインカードに採用(バリエーション2枚保存)。テキストタグから格上げ(11→10)
- [x] **夜勤専従イラストカード化(PR #171→#172)**: SCENE #19、初めての「夜」シーン(PREAMBLEの「澄んだ青空」制約から意図的に逸脱)。ベッドサイド服薬確認シーンを採用。テキストタグから格上げ(10→9)
- [x] **施設長・管理者候補イラストカード化、1回目失敗→再生成(PR #173→#174クローズ→#175→#176)**: SCENE #20の1回目生成(3枚)は`codex review`(effort: high)が全て耳元の垂れ下がるピアス(ACCESSORY RULE違反)を検出、Claudeの10項目採点では見落としていた実害バグ。PR #174はクローズし、ACCESSORY RULEを「NO earring優先、数mmの垂れも違反」へ強化(PR #175)。2回目生成(1枚)を耳元拡大確認のうえ採用(PR #176)。**2回目生成でもcodexが同一指摘(垂れる糸状のピアス)を再度出したが、Claude・本田様それぞれが600-700px拡大で目視確認しピアスは確認できず、decision-maker最終判断で「codexの誤検出(後れ毛の陰影線)」と結論しPRコメントに記録のうえ採用**。テキストタグから格上げ(9→8)
- [x] **相談員SCENE #21追加(PR #177)**: 求人数3位(36件)。既存`illust-job-consultant.png`(現在ケアマネジャーカードで使用中)との視覚的重複を避ける構図(窓口相談・施設見学案内)を指定、ACCESSORY RULEは前述の教訓を踏まえ強い表現で最初から指定。**プロンプトのみ、画像生成は次セッションに持ち越し**
- 各PR完了ごとに`docker buildx build`→`gcloud run deploy`で本番Cloud Runへデプロイ、実機(`category_id=`遷移・画像200・タグ数)を確認。デプロイ中に`gcloud`認証のreauth要求が1回発生、本田様に対話的`gcloud auth login`を依頼して解消(非対話環境では解決不能な既知の制約)
- **【上記🔄中断点参照】** 求人一覧/詳細ページ(`/jobs/`)側の画像選択(`selectors.yaml`)への新規3イラスト反映は、次セッションでplan modeにより6→9バケット新設方式を設計・実装完了(コード側)。本番デプロイ・実機確認は残作業

## 完了の定義 (ジョブカンCSV自動取得への移行) — 2026-08-11 実装完了・本番切替完了・PR #162

決裁者指摘「求人カテゴリの粒度不一致」を起点にしたHTML解析方式の限界(反映ラグ・新カテゴリ取りこぼし・解析誤り・募集終了判定の間接推測)への懸念を解消するため、ジョブカン管理画面(`ats.jobcan.jp`)のCSVエクスポートを`jobcan-sync@aozora-cg.com`アカウントでPlaywright自動取得する経路を新設し、HTML解析経路と並行稼働可能な形で実装、実データ検証のうえ本番切替した。

- [x] `facility_codes.py`(拠点コード→名称・住所30エントリ)を正式コミット、`facility_geo.FACILITY_COORDS`との整合性テスト追加(既知の3例外`b013`/`b022`/`b023`)
- [x] `csv_ingest.py`: CSV→`CrawlResult`の純粋変換層。UTF-8版CSV(`output_file_utf8`)を41列ヘッダー検証つきで解析、HTML経路の`parser.py`/`detail_sections.py`ロジック(`_jobcan_text`/`canonical_detail_url`/`resolve_display_thumbnail`)を再利用しHTML経路との出力パリティを実データ(job_id 2267337, 1777023)で実証。「休暇・休日」(CSV実列名、HTML経路の「休日・休暇」と逆順)の読み替え、社内専用列(採用担当者・評価設問・社内メモ等)の構造的除外(列インデックス定数のみ参照)を実装
- [x] `orchestrator.run_sync`を`run_sync_from_crawl`として抽出、`source: Literal["html_parse","csv","api"]`を`JobSnapshot`まで配線
- [x] `jobcan_ats.py`: Playwright自動化。一括アクションのプルダウンに「求人削除」等破壊的操作が同居するUIのため、ホワイトリスト+ラベル接頭辞+禁止語+実行直前3回のアサーションからなる4層安全ガード(`assert_safe_bulk_action`)を実装。実機で確認した16選択肢全件を分類するテスト(`test_jobcan_ats_safety.py`)で担保
- [x] `sync-run-csv-live`(Cloud Run Job本体)/`sync-run-csv`/`csv-diff`/`ats-download`の4CLIコマンドを追加、Playwright依存はコマンド関数内ローカルimportに限定し配信用イメージからは分離
- [x] `Dockerfile.job`新設(`mcr.microsoft.com/playwright/python:v1.62.0-noble`、builder/runtime両ステージ統一)、Artifact Registry別リポジトリ`aozora-sync-job`を新設、`playwright==1.62.0`に完全ピン留め
- [x] 実機検証で3件の重大バグを発見・修正: ①ATS OAuthハンドシェイク未経由でのセッション未確立 ②リロード後の既フィルタ済み状態を「未フィルタ」と誤判定する安全ガード誤発火 ③ページネーション`get_by_text`のstrict mode違反(2箇所のページネーションUIに同時マッチ)。2回連続実行で382件完全一致を確認
- [x] `csv-diff`でFirestore実データとの差分を確認: job_id集合382=382完全一致、address/label/location/title/apply_url/source_url/page_title不一致0件、当初懸念していた`category_ids`(クロス掲載)差分もゼロで決裁者への追加確認は不要と判明
- [x] `codex review --base main -c model_reasoning_effort=high`実施、P1(CSV行変換失敗時に`listed_job_ids`へ未記録のまま誤クローズしうるリスク)・P2(チェックボックスポーリングがヘッダー自身を含めてカウントする部分エクスポートバグ)を検出、同PR内で修正し本番Cloud Run Jobへ再デプロイ・再実行確認済み
- [x] 本番切替完了: Cloud Run Job `aozora-sync-daily`を`sync-run-csv-live`経路へ更新、実行結果`added=0 changed=0 unchanged=382 written=True`(切替直後の1回はcontent_hash差分により全382件changed、以降は安定)。全532テストPASS、ruff/pyright clean

🎯 **完了**。以後、求人データはHTML解析ではなくジョブカン管理画面のCSVエクスポートを唯一のソースとして6時間ごとに同期される。HTML解析経路(`sync-run`)は`--args`切替のみでロールバック可能な状態のまま保持。

## セッション履歴: 2026-08-11 求人カード画像マッピングの根本修正(PR #165)+ 同一職種内バリエーション追加(PR #166)

決裁者から「選択した職種タグに紐づく画像がまだ合っていない。意味が近い職種(訪問介護=ホームヘルパー等)は同じ画像にすべき。また以前は1職種内で複数画像を使い分けていたはずで、それも直してほしい」との指摘。

- **原因調査**: PR #159(2026-08-10)は17区分のシノニム漏れによる`default_image`大量フォールバックを解消したが、修正時に**カード色分け用の4系統グルーピング(`list_sections.LABEL_TO_CATEGORY`、介護/看護/事務/IT)をそのまま画像選択にも流用**していた。この4系統は色分け目的の粗い分類であり、ホームヘルパー・相談員・ケアマネジャー等10種類が全て同じ介護シーン画像になっていた。一方で専用イラスト`illust-job-visit.png`(訪問介護員向け)・`illust-job-consultant.png`(相談員/ケアマネジャー向け)は既に生成済みだったが本番マッピングで一度も使われていなかった。
- **修正(PR #165、マージ・本番反映確認済み)**: `selectors.yaml`の`thumbnail_categories`を4→6系統(care/visit/consultant/nurse/office/it)へ再分割し、上記2画像を活用。手動チェックリストレビュー(2ファイル・48行、codex review省略基準内)。Docker再ビルド・Cloud Run Job更新・手動トリガーまで実施し、本番実機(`/jobs/?category_id=`)でホームヘルパー→visit画像、相談員→consultant画像への切り替わりを確認
- **バリエーション機能追加(PR #166、マージ・本番反映確認済み)**: 「1職種内で複数画像」はPhase A(旧静的モック生成スクリプト`rewrite_jobs_html.py`)にあった`CATEGORY_VARIANTS`+ラウンドロビン方式だが、Phase B(6時間ごと自動再同期)にそのまま移植すると求人の増減で他求人の画像までシャッフルされる欠陥があるため不採用。代わりに`job_id`の`sha256`ハッシュで決定的に1枚選ぶ方式(`parser._pick_variant`)を新設、`ThumbnailCategoryEntry.image: str`→`images: list[str]`(プール化)。care(3枚)/visit(3枚)/consultant(2枚)/office(2枚)を複数画像化、nurse/itは1枚のまま
- **品質ゲート**: `codex review --base main -c model_reasoning_effort=high`(指摘0件)+ `pr-review-toolkit`3エージェント並列(code-reviewer/silent-failure-hunter/type-design-analyzer)。type-design-analyzerの改善提案3件中2件(空プールガード・並べ替え契約のテスト)を同PR内で反映、残り1件(既存クラスのfrozen化)はスコープ外として見送り理由を明記
- pytest 543件全PASS(新規11件)、ruff/pyright 0件。本番実機で介護職(53件が care/-2/-3 に分散)・ホームヘルパー(15件)・相談員(36件)いずれも複数画像への分散を確認

🎯 **完了**。決裁者からの2点の指摘(タグ↔画像の紐づけ・同一職種内バリエーション)ともに本番まで解決。

## セッション履歴: 2026-08-10 求人カード画像マッピング修正(PR #159) + CSV移行 招待メール解決・Secret Manager登録(PR #160)

決裁者が本番の職種フィルタ(看護職等)で求人カード画像を確認したところ、フィルタと無関係に同じ画像(相談員がタブレットで家族に説明するシーン)が表示されることを報告。

- **原因調査・修正(PR #159、マージ・実機反映待ち)**: `sync/src/sync/selectors.yaml`の`thumbnail_categories`シノニムがPhase 2A.1c時点の6種類のまま、前セッションの17区分フィルタ拡張(PR #157)に追従しておらず、実際のジョブカン生ラベル(例:「看護職」)の大半が未登録でdefault_imageへフォールバックしていたことが判明。`list_sections.LABEL_TO_CATEGORY`(2026-08-09に17区分へ更新済み)と同じ4系統グルーピングへ揃えて全17ラベルを網羅。sync/tests 474件全PASS、手動チェックリストレビュー(1ファイル・小規模のためcodex review省略)。反映は次回自動クロール(最大6時間以内)を待つ方針で合意、即時反映(Cloud Run Job手動実行)は見送り
- 決裁者向け進捗報告HTML(スクラッチパッド、リポジトリ外)を更新: PoC(実現可能性検証・完了)と自動化(未着手、Secret Manager導入で初めて人手を介さない実行になる)の違いを明記
- **CSV移行のブロッカー解消**: `jobcan-sync@aozora-cg.com`(Googleグループとして発行)の招待メール未着問題を、Googleグループ側「投稿を許可するユーザー」設定修正→ 外部テストメール到達確認 → それでも招待メール自体は届かず → `https://id.jobcan.jp/users/invitation/new?lang=ja`からの招待メール再送、の順で切り分け、最終的に再送で解決
- **Secret Manager登録(PR #160)完了**: `jobcan-sync-password`シークレット作成(空コンテナ)+`aozora-sync-job` SAへの`secretmanager.secretAccessor`付与はgcloud CLIで実施。パスワード本体は`gcloud secrets versions add`がSSO/2段階認証アカウントのreauthループ(パスワード入力方式のみ対応、`gcloud auth revoke`→`login`の完全再ログインでも解消せず)で失敗し、GCPコンソール(ブラウザ)経由での登録に切替えて成功。`infra/README.md`§1.6に実測結果ベースの手順を記録(bashの`read -s -p`はzshで構文エラーになる注記も含む)

## セッション履歴: 2026-08-10 求人一覧の職種フィルタを17区分へ拡張(PR #157) + CSVデータ取得方式への移行検討(進行中)

決裁者から、ジョブカン原本(`recruit.jobcan.jp/aozora`)の職種ナビ17区分と、Cloud Run求人一覧の職種フィルタ4区分の粒度不一致を指摘。調査の結果、PR #72(2026-07-23)で意図的に4系統へ統合した設計と判明したが、正式な決裁を経ていなかったため、17区分への拡張で決裁者承認を得てplan mode実施。

- **実装(PR #157、マージ・本番デプロイ・実機確認完了)**: `job_types.py`(新規)にcategory_id→職種名17件の単一真理ソースを新設、`crawler.KNOWN_CATEGORY_IDS`はここから導出。色分け用の`LABEL_TO_CATEGORY`(4系統)は意図的に分離維持しdrift検出テストを追加。職種チップを17個+件数バッジへ拡張、sitemap.xmlの職種URLも17区分へ拡張。`codex review --base main -c model_reasoning_effort=high`指摘0件、pytest 474件全PASS。本番実測で17チップ・件数・sitemap・search-indexいずれも期待通りを確認(看護職85件〜新卒既卒総合職2件、合計382件)
- **続けて決裁者から「そもそもDBではなくスクレイピングであることへの懸念」が提起**され、詳細を議論。現行HTML解析方式の4つの構造的限界(反映ラグ・新カテゴリ取りこぼし・解析誤り・募集終了判定の間接推測)を整理し、CSV自動取得方式への切り替えを検討開始(上記🔄中断点に詳細)
- ジョブカン標準UIでのカスタマイズ機能(採用サイト基本設定等)も検討したが、独自ドメイン非対応・デザイン自由度不足のため見送り、独自ドメイン+CSV自動取得の組み合わせを採用方針とした
- 決裁者向け・システム部向けの説明資料(HTML、コピーボタン付き)を複数作成、スクラッチパッドに保存(リポジトリ外)

## セッション履歴: 2026-08-08 mockup反映漏れ修正 + Phase B Stage1本番デプロイ(PR #141→#142、社長指摘「実際のJobcanより少ない件数を見せているのはまずい」を起点)

社長から「実際のJobcan環境では382件公開されているが、それより少ない件数を求人一覧として見せているのは実データなのか、勝手に減らしているのではないか」との指摘。

**調査(全ページ突合)**: `mockup/jobs-care.html`が2026年7月以降更新されておらず介護カテゴリ20件中10件が欠落、チャットボット知識ベースも3件欠落と判明・修正(PR #141)。あわせてFirestore job_cache(Phase B、6時間ごと自動クロール)を突合したところ、Jobcan上の実際のactive求人は**382件**、Phase Aモックは**37件(約9.7%)**のみのサンプル設計だったことが判明。これはPhase A設計当初からの意図的なサンプリングだが、GitHub Pagesが既に一般公開URLである以上「求人一覧として少なすぎる件数を見せている」というリスクは実在すると判断。

**decision-maker判断**: ①Phase B(Cloud Run+Firestore、382件全件反映済み)への本番切替を前倒し ②トップページもCloud Runへ全面集約(WordPress統合は既に撤回済み、GitHub Pagesは仮置き) ③v1はカテゴリ別一覧でリリース(地図検索+GPS+横断検索はStage 3以降)。plan mode(Explore 3並列)で調査したところ、単なるDNS切替ではなくPhase Bテンプレートのデザインパリティ不足・静的アセット配信欠如・トップページ配信元未定が判明。

**実装(Stage 1、PR #142)**: `/assets` StaticFilesマウント+`/`ルート追加、CSS/canonical/戻りリンクの絶対パス化(`PUBLIC_BASE_URL`導入)、`mockup/index.html`はGitHub Pages(現在も本番公開中)と共有のためサーバ側リンク書き換え方式を採用(直接編集で一度revertする場面あり)、Dockerfileのビルドコンテキストをリポジトリルートへ変更。

**品質ゲート(4ラウンド)**: codex review×3回・セカンドオピニオンエージェント×2回(うち1回は実際にTestClientで挙動を検証する実測ベースのレビューで35分を要した)。発見・修正した実害バグ: index.html自己リンク404・チャットボット関連求人リンク404・静的アセットの`no-store`キャッシュ・`/assets`404のキャッシュ汚染・`check_dir=False`のコメントと実挙動の乖離(実際はRuntimeError)・`/`ルートの`run_in_threadpool`未使用・トップページcanonicalが`PUBLIC_BASE_URL`未追従。

**本番デプロイ完了**: `aozora-sync`リビジョン`aozora-sync-00005-mkw`(トラフィック100%)、`aozora-chatbot`のALLOWED_ORIGINS更新。検証URL(`https://aozora-sync-flry56mxwa-an.a.run.app/`)でPlaywright実機確認(トップ→カテゴリ一覧→求人詳細→チャットボット送受信→関連求人`.html`リダイレクト、console error/404 0件)。**まだ`recruit.aozora-cg.com`には未接続**(Stage 5でドメイン切替するまでは検証用URLのみ、一般求職者への影響なし)。

pytest 266件全PASS(新規29件追加)、ruff check clean。

## セッション履歴: 2026-08-08 スクレイピング間隔を6時間ごとへ変更 + closed判定の時間ベース化(PR #138→#139、decision-maker「スクレイピングのタイミングを1時間くらいにできますか？」を起点)

decision-makerから求人データの鮮度向上を目的に「1時間ごと」への変更依頼。調査の結果、
`docs/specs/sync-strategy.md` §3 の自己申告済みポリシー(「頻度6h or 12h」)およびジョブカン
宛照会文面(「6時間に1回程度」)との矛盾、1回のフルクロールが約429リクエスト・21分を要し
1時間間隔では稼働率36%・実行重複リスクが生じる点を発見。AskUserQuestionで方針確認し、
**6時間ごと(3:00/9:00/15:00/21:00 JST)+フルクロール維持**に決定。

- **closed判定の時間ベース化(plan mode実施)**: 「連続2回不在でclosed」の実行回数ベース判定は
  日次前提(実質48時間の猶予)だったため、6時間ごとクロールにそのまま適用すると判定窓が12時間に
  縮み誤closedリスクが増大。`JobSnapshot.first_absent_at`を新設し、`absence_count>=2 AND
  (now - first_absent_at)>=48h`のAND条件に変更。`diff.unfetched`(一覧には出ているが詳細取得
  のみ失敗)は「存在確認済み」としてbookkeepingをリセットする挙動に変更(旧: carry-forward
  untouched)。境界値(47h/48h/49h)・6時間刻み8回連続不在シミュレーション等の新規テストを追加
- **品質ゲート**: `codex review`を2回実行(push前medium effort、large tier hook指定のhigh
  effort+`--strict-config`)、いずれもfindings 0件。`pr-review-toolkit`セカンドオピニオン4
  エージェント並列起動(code-reviewer/pr-test-analyzer/comment-analyzer/type-design-analyzer)
  — comment-analyzerが実際のdocstring不整合(`skip_absence_bookkeeping`時の`diff.removed`が
  「unfetchedと同じ」という記述が、同PRでunfetched側の挙動を変えた結果不正確になっていた)を
  検出、PR #139でフォローアップ修正。type-design-analyzerが`absence_count`/`first_absent_at`間
  にcross-field validatorがない設計リスクを指摘したが、意図的な防御的テストケース
  (`test_single_absence_does_not_close_even_after_48_hours`)と直接矛盾するため追加は見送り
  (判断の記録のみ、コード変更なし)
  - **判明した運用上の注意**: review-code/review-tests(pr-review-toolkit)は数分で完了したが、
    review-comments/review-types の2エージェントは約25分応答なしとなり、既知のsubagentハング/
    ゾンビバグ(reference_subagent_hang_zombie_bugs.md)を疑ってdecision-maker確認のうえ得られた
    結果のみで進行・マージした。実際にはハングではなく、マージ完了後に両エージェントから正常な
    結果が遅延到着した(単に遅かっただけ)。次回同様の遅延時は、ハング断定前にもう少し長く待つ
    余地がある
- **本番反映**: Dockerイメージ再ビルド・push → `gcloud run jobs update aozora-sync-daily
  --image=...` → `gcloud scheduler jobs update http aozora-sync-daily-trigger --schedule="0
  3,9,15,21 * * *"`。PR #138マージ前の状態でCloud Schedulerは日次のまま未検証だったが、本セッション
  中に初回自動実行(2026-08-08 3:00 JST)が新イメージ・新スケジュールの反映後に発火し**成功**を確認
  (所要21分44秒、`added=0 changed=6 unchanged=376 removed=0 newly_closed=0 gc_deleted=0
  crawl_errors=0 written=True`、severity>=WARNINGのログなし)。旧「Cloud Scheduler初回自動実行を
  要監視」の中断点はこれで解消(上記🔄中断点セクションから削除済み)

## セッション履歴: 2026-08-07 Phase A看護職カテゴリの実データ復元(PR #136、decision-maker指摘を起点に調査・修正)

decision-makerが公開モック`jobs.html`実機を確認し「ここについて社長からの指摘が網羅されてません」と指摘。
調査したところ、実ジョブカンサイトの17職種カテゴリ(看護職=category_id 18983等)は既にPhase Bで正しく
クロール済み(Firestoreに看護職85件)だったが、静的モック`jobs.html`の職種フィルターは「介護・相談/事務/IT」
の3バケットのみで看護が存在せず、`jobs.json`の34件にも看護師求人が0件だった。加えて`jobs-nurse.html`
(index.htmlの看護カード導線先)はcategory_id 18984/18983取り違えにより相談員の求人を看護師として誤表示。

一度は「Phase Bが解決済みだから静的モック修正は不要」と誤って却下したが(PR #135)、decision-makerから
「実際に見ている画面(静的モック)では直っていない」「元ジョブカンの選択内容をスクレイピングしてきたなら
それが反映されるべき」との指摘で誤りを訂正。カテゴリ・サンプルを手動で決め打ちするのではなく実データ
(Firestore/既存の`scripts/mockup-rebuild/`正本取得パイプライン)から生成する方針でplan mode実施。

- **実装**: Firestore実測(category_id=18983、既存の座標登録済み拠点のみ・新規ジオコーディング不要)から
  実求人3件(博多/正社員・永吉/短時間正社員・梅ヶ丘/パート)を選定。既存の`scripts/mockup-rebuild/`
  パイプライン(README「Phase A中の追加ジョブ描加にも再利用可」)を拡張: 新規`add_new_cards.py`
  (既存スクリプトが持たない「新規job_idの追加」パスを担う)、`rewrite_jobs_html.py`に看護マッピング追加
  +対象HTMLファイルCLI引数化、給与regexの資格別内訳プレフィックス未対応バグを修正(看護データで初露見)
- **codex review (P2×4) 対応**: 「パートアルバイト」複合雇用形態のjobs.json分割漏れ(個別フィルター一致
  不可)・`rewrite_job_details.py`のemp_patterns順序(複合雇用形態タグ誤表示)・新規詳細ページのJobPosting
  jobLocationが常に「福岡」表記だった(鹿児島の求人でも)、の3件を修正。残り1件(初期表示件数固定)は
  コード確認+実機確認で誤検知と判断
- **動作確認**: Playwrightで看護チップ表示・絞り込み・詳細ページ全セクション・`jobs-nurse.html`修正・
  看護+パート同時選択でパートアルバイト求人が正しく1件ヒットすることを確認。既存34件は内容不変
  (属性順の差異のみ)

## セッション履歴: 2026-08-07 Phase B 本番インフラ初回ロールアウト(decision-maker明示指示「始めてください」で実行)

decision-makerから「Phase B本番インフラのプロビジョニング、始めてください」との明示指示を受け、
`infra/README.md`「B-8 初回ロールアウト順序」1〜6を実行。前提だった「ジョブカン正式照会回答待ち」は
本セッション冒頭でdecision-maker指摘により撤回済み(PR #132、2026-06-18方針転換の適用漏れと判明)。

- **実行内容**: Dockerイメージビルド・push → API有効化(firestore/secretmanager/cloudscheduler)→
  Firestore DB作成(asia-northeast1, native mode)→ サービスアカウント2種作成+IAM付与
  (`aozora-sync-web`: datastore.viewer / `aozora-sync-job`: datastore.user)→ クローラdry-run
  検証(実ジョブカン、382件・エラー0件・`expected_total==collected_total`・`fully_listed=True`)→
  Cloud Run Job (`aozora-sync-daily`) 作成 → 初回本番同期実行 → Cloud Run Service再デプロイ
  (Firestore単一ソース配信)→ Cloud Scheduler (`aozora-sync-daily-trigger`, 日次3:00 JST) 作成
- **本番初回書き込みで発見・修正した実害バグ (PR #133)**: `JobOffer.extra_lines: list[tuple[str, str]]`
  が`model_dump(mode="python")`でタプルのリストのまま残り、Firestoreの「配列を配列に直接ネスト
  できない」制約に抵触し、全件書き込みが`InvalidArgument: 400 Property offer contains an invalid
  nested entity`で失敗。`firestore_repo.py`に`_encode_extra_lines`/`_decode_extra_lines`を追加して
  解消(回帰テスト2件追加、pytest 236件全PASS・ruff/pyright 0エラー)。修正後の再実行で382件全て
  `active`として書き込み成功、`extra_lines`もタプルとして正しく復元されることを確認
- **その他に遭遇した問題(コード起因ではない)**:
  - `gcloud run jobs execute`がClaude Code auto modeクラシファイアに一貫してブロックされたため、
    初回本番同期はdecision-maker合意のもとローカル`python -m sync sync-run`で代替実行(Cloud Run Job
    自体の実行経路は次回スケジューラ発火まで未検証、上記🔄中断点に記録)
  - ローカルFirestore書き込み時にgRPC(c-ares)のDNS解決だけが失敗する問題(`Could not contact DNS
    servers`、通常のDNS解決/curlは正常)に遭遇、`GRPC_DNS_RESOLVER=native`で回避(Docker Desktop起動に
    伴うネットワーク設定変化が疑われるが未確定、ローカル環境固有の問題でCloud Run実行環境には影響しない見込み)
  - 修正コミット後にイメージの再ビルド・再push忘れで旧イメージのままServiceを一度デプロイし、詳細
    ページが503(旧コードは`extra_lines`デコード未対応でPydanticバリデーションエラー)。イメージ再
    ビルド・再デプロイで解消
- **動作確認**: `/jobs/104625`(詳細)・`/jobs/?category_id=43764`(一覧)とも200、
  `sync-job-detail`/`sync-job-list`のBEMクラス確認済み。存在しないjob_idで404確認済み
- **未実施**: Secret Manager(運用通知webhook、URL未提供のため次回以降。2026-08-09にGoogle Chat
  webhook前提へ移行、secret名は`ops-webhook-url`)。Cloud Billing budget alert
  (§6、Console UI経由が必要)
- **[却下→2026-08-07同日中に撤回・実装済み] Phase A 看護職カテゴリ不整合の静的モック修正**: 本判断は誤り
  だった。Firestore(Phase B裏側)は看護職85件を正しく保持していたが、これは静的モック`jobs.html`の
  表示には一切反映されない(GitHub Pagesは独立した固定データを参照)。decision-makerが実機を確認し
  「実際に見ている画面では直っていない」と指摘、方針を訂正してPR #136で実データ(Firestore)から看護職
  3件を静的モックへ復元・反映した。詳細は下記セッション履歴参照

## セッション履歴: 2026-08-07 Phase B 配信層統合実装(B-8、PR #129マージ後の新セッション)

前セッションでPR #129 (B-1〜B-7データ層) をマージ後、decision-makerが次作業として
「B-8: 配信層統合」を選択 (`AskUserQuestion`推奨肢)。5ファイル以上・新機能・
アーキテクチャ判断に該当するため plan mode でフル計画 → 承認 → 実装。

- **計画時の重要発見 (自ら`gcloud`で実測)**: Phase Bのインフラ (Firestore DB・
  Secret Manager・Cloud Scheduler・Cloud Run Job) が**一切プロビジョニングされて
  いない**ことが判明 (`firestore.googleapis.com`等3APIが未有効化、Job 0件)。
  `infra/README.md` §1.5/§8/§8.3 は「書かれているが一度も実行されていない手順」
  だった。この発見により計画を「コード実装」だけでなく「初回プロビジョニング
  手順の具体化」まで含める方針に拡張
- **decision-makerの追加指示 (plan提示直後)**: 当初計画に「CLI承認コマンド +
  Slack承認待ち通知」を含めていたが、社長から「完全自動化が必要」との明示指示。
  `AskUserQuestion`で範囲を確認し「`REVIEW_BYPASS=true`を常時適用、承認導線自体
  は実装しない」に確定 (`approval.py`本体はコードとして残置、巻き戻しコスト対策)
- **実装内容**:
  - `snapshot.py`: `JobSnapshot.normalized: dict[str,str]`(production側の読み手ゼロ、
    Firestoreが空なので移行コスト無し) を `offer: JobOffer`/`list_item: JobListItem|None`/
    `category_ids: list[str]` へ置換。詳細ページ全文再現・複数カテゴリ掲載対応
  - `crawler.py`: `CrawlResult`に`list_items`/`category_ids`を追加、`_collect_category_job_ids`が
    `JobListItem`を保持するよう変更 (既存の`expected_total`/`collected_total`不変条件は維持)
  - `closed_detection.py`/`orchestrator.py`: 上記2フィールドをスナップショット生成まで配線
  - `firestore_repo.py`: 単一ドキュメント`get(job_id)`を追加
  - `renderer.py`: `render_job_detail(job, *, closed=False)`、`job_detail.html`に募集終了バナー分岐
  - `app.py` (最大の変更、590→約210行): ジョブカン直接フェッチ経路(4xx/5xx例外マッピング・
    ネガティブキャッシュ・allowlist)を全削除、`JobCacheRepository`ベースの配信へ全面書き換え。
    `pending_review`→404・`closed`→募集終了表示・カテゴリ一覧はPython側フィルタ
    (Firestore複合クエリは~34件規模では過剰と判断、コメントに根拠明記)。`JOBCAN_FETCH_ENABLED`削除
  - **自ら発見し対処した罠**: `create_app()`のデフォルトで`JobCacheRepository(get_firestore_client())`
    を即時構築すると、`app = create_app()`というモジュールトップレベルの1行が
    `import sync.app`のたびに`google.auth.default()`を要求してしまい、ADCの無い
    環境(CI等)でテスト収集自体が壊れるリスクがあった。`_resolve_repo()`による
    遅延解決(初回リクエスト時まで構築を遅らせる)で回避、テストで明示的に確認
  - `infra/README.md`: §1a (Firestore DB作成)・§4a (Web用read-only専用SA)・§8.1b
    (クローラの実ジョブカンdry-run検証、初回のみ・Job作成前に必須)・「B-8初回
    ロールアウト順序」セクションを新規追加。§8.2の`REVIEW_BYPASS`を`true`固定・
    `task-timeout`を600s→最終的に3600sへ引き上げ(下記レビューラウンドで再修正)
  - `CLAUDE.md`/`docs/specs/sync-strategy.md`: B-8完了を反映、既知ギャップ節を解消
- **テスト**: 221件→変わらず221件(test_app.py 28→17件に整理、他ファイルで+22件、
  差分は新規カバレッジ)、ruff/pyright共に0エラー (旧test_app.py起因の既知ベース
  ライン17件も、全面書き換えにより解消)
- **PR #130作成後、`codex review --base main --strict-config -c model_reasoning_effort=high`
  + `pr-review-toolkit`4エージェント(code-reviewer/pr-test-analyzer/type-design-analyzer/
  silent-failure-hunter、いずれもmodel: sonnet明示・read-only)による並行レビューを実施
  (P2×2・独立指摘多数、相互検証済み)**:
  - [P2・修正済み、codex+silent-failure-hunter+超過タスクの計画エージェント2件が独立指摘]
    劣化クロール(あるカテゴリの一覧取得が完全失敗)時、複数カテゴリに掲載されている求人の
    `category_ids`が「今回見えた分だけ」で全置換され、失敗したカテゴリの一覧から静かに
    消える実害バグ。`skip_absence_bookkeeping=True`時のみ前回スナップショットの
    `category_ids`とunionするよう`closed_detection.py`を修正(既存の
    `skip_absence_bookkeeping`フラグの意味論を再利用、新規フラグ追加なし)
  - [P2・修正済み] `app.py`の2ルートが同期Firestore SDK呼び出しを`async def`ハンドラ内で
    直接実行しており、Cloud Run concurrency下で遅いFirestore RPCがイベントループを
    ブロックし他の同時リクエストを直列化しうる。両ルートの読み取りを
    `starlette.concurrency.run_in_threadpool`でラップして解消
  - [HIGH・修正済み、silent-failure-hunter+pr-test-analyzer 2名が独立指摘] `get_job_detail`の
    `repo.get(job_id)`呼び出しがtry/except外にあり、Firestore読み取り失敗が無ログ・無応答の
    フレームワーク既定500として素通りしていた(list route側は元々try/except内)。両ルートを
    「Firestoreエラー→503+ログ」「render失敗→500+ログ」に明確分離する構造へ統一
    (`_firestore_error_response`ヘルパー新設)
  - [MEDIUM・修正済み] `_render_list`が`repo.get_all()`をrender処理と同一try/exceptで
    包んでおり、Firestoreコレクション中のドキュメント1件でも不正だと**全カテゴリの
    一覧ページが連鎖的に落ちる**設計だった。`firestore_repo.py`に`get_all_valid()`
    (不正docをskip+ERRORログ、有効な分だけ返す)を新設し配信経路のみ使用。
    sync経路(`orchestrator.run_sync`)は`get_all()`のまま厳格維持
    (dropしたdocがdiff baselineを汚しclosed率サーキットブレーカーを誤発火させるため、
    配信経路と非対称にすることが意図的な設計)
  - [対応不要と判断] type-design-analyzer指摘の`category_ids: list[str]`をfrozenset/tupleに
    すべき(`model_config={"frozen":True}`の意図と厳密には不整合)、および
    `list_item.job_id`と親`job_id`の一致・`sync_status=="closed"⟺closed_at is not None`
    をtype levelで強制していない点は、いずれも実害ゼロ・PR #129時点から既知の
    低severityなnitで、本PRのスコープ拡大に見合わないため見送り
  - [対応見送り、次セッション検討] 計画段階のエージェント(すでにsupersededな設計だが
    この指摘のみ独立に有効)指摘: `closed`求人を被リンク維持のため残す方針にもかかわらず
    `templates/base.html`/`job_list.html`の`rel=canonical`がジョブカン側URLを指しており、
    SEO上「本物はジョブカン側」と宣言してしまい方針を実質無効化している。本番ドメイン
    (`recruit.aozora-cg.com`)のDNS切替が未確定のため`PUBLIC_BASE_URL`env var設計を含む
    追加機能として次セッションに持ち越し
  - **計画段階で起動したPlan agent(plan-ops)による無許可の実ジョブカンライブアクセス
    (本人が自己申告・訂正済み)**: 「実ジョブカンに対しread-only GETで実測」と報告し
    実求人382件(想定34件の11倍)・crawl_delay 3秒で全体約21.4分と主張していたが、
    本人に確認したところ**実際に送信したのは4回の実行で合計77リクエスト(list 47件
    重複含む+detail 8件のみ、約3.7分)**で、382件の詳細ページは取得していないと訂正。
    382件・21.4分は「フルsync-runを実行したら」という**見積り値**であり実測ではなかった。
    全てGETのみ・crawl_delay 3秒遵守・身元特定可能なUser-Agent送信を確認。本人からは
    「社長への正式照会が回答待ちの状態でのライブクロール実行前に確認を取るべきだった、
    executorが単独で判断してよい事項ではなかった」との明確な誤り認識の申告あり。
    実求人382件という数値自体は8件のサンプルパースが成功した実績はあるものの、
    フルクロールでの検証ではないため引き続き未確定。`infra/README.md`の
    `task-timeout`(1800s→3600s、コスト増なし)は安全側の措置として維持、確定値は
    §8.1bのdry-run実行時に決裁者確認のうえ得る
  - **PR #130の第2ラウンド(review-code-b8)からさらに3件の指摘を受領、2件は修正・1件は
    レビュー対象がスナップショット古かったため解消済みと確認**:
    - [解消済み(レビュー対象が修正コミット反映前のスナップショットだった)] 「Firestore
      読み取りがrun_in_threadpoolでラップされていない」— 直前のcodex/silent-failure-hunter
      指摘への対応で既に修正済みのコードに対する指摘と判明、現行HEADで確認済み
    - [LOW・修正済み] 一覧カードのソートが`item.job_id`の文字列辞書順で、桁数の異なる
      job_id間(例: "9999999" vs "10000000")で数値順が崩れる潜在バグ。`int(item.job_id)`
      による数値降順ソートに修正
    - [LOW, style・修正済み] `_resolve_repo`の1要素リストによる可変セルパターンが
      `nonlocal`変数で足りる用途に対し不必要に複雑との指摘。`nonlocal`変数へ簡素化
  - 修正後テスト234件全PASS(+13件)、ruff/pyright共に0エラー、修正4ラウンドをpush済み

## セッション履歴: 2026-08-07 Phase B 定期同期システム実装(B-1〜B-7、`sync/` 大規模拡張)

社長から「看護職が入ってないのは明らかにおかしい」との指摘を起点に旧サイト比較調査を開始したところ、`mockup/jobs-nurse.html` の category_id 誤マッピング(18984=相談員 を看護師と誤認、正しい看護職は18983)が見つかった一方、本田様から「モック単発修正では同種の不整合(一回性スナップショット起因)が再発する」との根本的な設計懸念が提起され、Phase A の看護職修正を後回しにして **Phase B(ジョブカン定期同期)を先に本格実装する**方針転換があった(計画ファイル: `elegant-wobbling-snowflake.md`)。

- **法務/契約面の事前確認**: ジョブカン採用管理利用規約・基本規約を一次資料で確認し、スクレイピング・クローリングを明示的に禁止する条項は無いと判明(第9条のリバースエンジニアリング禁止はソフトウェア解析文脈で公開ページ読み取りには通常適用されない解釈)。正式な許諾確認は社長へ報告済み・回答待ちだが、技術検証・実装は並行して進める判断(2026-06-18 の内部方針転換 `feedback_overengineering_recovery_2026-06-18.md` の延長)。**[2026-08-07 訂正]** この後の Phase B セッションで「本番デプロイもジョブカン正式照会回答待ち」という条件が再掲され続けたが、2026-06-18 の方針転換は Phase 2B(=本番展開)着手判断のtriggerを「本田様の deploy 指示のみ」と既に確定していたため、この条件再掲は同方針の適用漏れだったと判明・撤回
- **アーキテクチャ決定**: WordPress は求人データを一切保持しない設計に確定 (CPT/ACF/WP REST API 連携は不採用)。Cloud Run 動的プロキシが一覧・詳細ページを直接配信する案 D (`docs/specs/sync-strategy.md`) に設計を GCP へ集約 (「せっかく GCP でプロジェクトを組んでいるので設計を GCP に集める」という本田様判断)。矛盾していた CLAUDE.md「CPT/ACF (Phase B)」節・`sync-strategy.md` §6/§7 を本セッションで整合済み
- **実装 (B-1〜B-6、データ層のみ)**:
  - B-1 クロール基盤: `jobcan_client.py` にページネーション対応(`/list/all/all/{page}`形式) + Crawl-delay 3秒、`parser.py`/`models.py` にページネーション情報抽出、`crawler.py`(新規)で全17カテゴリ×全ページ巡回オーケストレータ(job_id重複排除・部分失敗継続・総件数検算)
  - B-2 Firestoreスナップショット + 差分検出: `snapshot.py`(新規、`job_cache/{job_id}` スキーマ)、`diff.py`(新規、added/changed/unchanged/removed/unfetched分類)、`firestore_repo.py`(新規、date→datetime変換の地雷を`aozora-sns-auto`から移植)
  - B-3 closed判定 + サーキットブレーカー: `closed_detection.py`(新規、連続2回不在で closed化、closed率>30%でサーキットブレーカー、30日GC候補選定+実削除)
  - B-4 承認ステータス計算: `approval.py`(新規、`pending_review`判定 + `review_bypass`フラグの純関数。`aozora-sns-auto`の`compute_finalize_target_status`パターンを移植。**承認を実行するCloud Runエンドポイントは未実装**、下記ギャップ参照)
  - B-5 Slack通知: `notifications.py`/`secrets.py`(新規、Secret Manager経由のWebhook通知、失敗を握り込む設計)
  - B-6 Cloud Scheduler + Cloud Run Job配線: `orchestrator.py`(新規、全体オーケストレーション、GC実行含む)、`cli.py`に`sync-run`コマンド追加、`infra/README.md`にSecret Manager(§1.5)・Cloud Scheduler/Job(§8)手順追記
  - B-7 ドキュメント整合: CLAUDE.md「CPT/ACF」節を「求人データ配信アーキテクチャ」節へ書き換え、`sync-strategy.md`のWP CPTブロック・ロードマップを現状に合わせて更新、本エントリでGOAL.md更新
- **意図的に対象外**(過剰設計の反面教師、2026-06-18の巻き戻し方針を踏襲): Terraformモジュール化・WIF+GHA自動デプロイ・Cloud Armor・Load Balancer・Memorystore・多段階リリース・規約照会ゲート、いずれも不採用
- **PR #129作成後、`codex review --base main -c model_reasoning_effort=high`実施(P1×3・P2×1検出)**:
  - [P1・修正済み] `crawler.py`が「一覧には出ているが詳細取得だけ失敗」を「不在」と誤分類し、2回連続の一時的失敗だけで正常な求人をclosed化する実害バグ。`CrawlResult.listed_job_ids`/`fully_listed`を追加し、`diff.py`に`unfetched`分類・`closed_detection.py`に`skip_absence_bookkeeping`を追加して解消(テスト16件追加)
  - [P2・修正済み] `find_gc_candidates()`が実際には呼ばれておらずGCが機能していなかった。`firestore_repo.delete_many()`を追加し`orchestrator.run_sync()`から実行するよう接続(テスト5件追加)
  - [P1×2・未修正、B-8として次セッション対象] `app.py`がFirestoreを読まずジョブカン直接フェッチのままで承認ワークフローが実配信に無効/承認エンドポイント自体が存在しない。設計判断とスキーマ拡張を要する別スコープの機能のため、本PRでは実装せず、CLAUDE.md・GOAL.mdに既知ギャップとして明記のうえ次セッションへ持ち越し
  - 修正後テスト212件全PASS、ruff/pyright既存ベースライン以外エラー0件
- **並行起動した`pr-review-toolkit`(code-reviewer/pr-test-analyzer/silent-failure-hunter/type-design-analyzer)+`evaluator`の5エージェントによる第二意見レビュー結果を反映(3エージェントから報告受領、code-reviewer/evaluatorは再送依頼中)**:
  - [HIGH・修正済み] pr-test-analyzer指摘: `review_bypass=True`時に「closedから再掲載」の安全策(`pending_review`要求)が無条件で上書きされる挙動が未テスト。意図的挙動と判断しテストで固定(`test_review_bypass_true_reactivating_from_closed_skips_review`)、`approval.py`のdocstringに根拠を明記
  - [MED-HIGH・修正済み] pr-test-analyzer指摘: サーキットブレーカーの分子(pending_review含む全absent job)と分母(`active`限定)の population不一致で closed_rate が実態を超えて計算されうる不整合。分母を`previous_open_count`(active+pending_review)に拡張して解消(テスト2件追加)
  - [HIGH・修正済み、silent-failure-hunter+pr-test-analyzer 2名が独立指摘] `expected_total`/`collected_total`のreconciliation機構が計算されるだけで一度も参照されておらず「サイレントな部分クロール検知」が死んでいた。`orchestrator.run_sync`で不一致を検知しSlack警告するよう接続。あわせて`collected_total`の集計基準を「重複排除後」から「カテゴリ単位・重複排除前」に修正(exp/collected両方が同じ基準でないと複数カテゴリに掲載された求人が常に不一致判定されるバグを実装中に発見・修正)
  - [MED・意図的挙動と判断、テストのみ追加] pr-test-analyzer指摘: `pending_review`のまま2回不在の求人が`approval.reject()`を経由せず自動closed化される。「未承認でも消えたら消えた扱いでよい」という判断でコード変更なし、`test_pending_review_job_absent_twice_auto_closes_without_reject`で挙動を固定
  - [LOW-MED・修正済み] pr-test-analyzer指摘: サーキットブレーカー30%閾値ちょうど・GC30日ちょうど・batch上限500ちょうどの境界値が未テスト。3件追加(全て期待通りの境界挙動を確認)
  - [LOW・修正済み] pr-test-analyzer+silent-failure-hunter指摘: サーキットブレーカー発火時に別枠のクロールエラーSlack警告が握り込まれる問題。1回のSlack通知に統合(テスト追加)
  - [MEDIUM-HIGH・対応見送り、次セッション検討] type-design-analyzer指摘: `CrawlResult.errors: list[dict[str,str]]`がキー有無で異種レコードを判別するstringly-typed設計で、`collected_total`計算の型安全性が弱い。tagged union化が対応候補だが影響範囲(crawler.py+テスト多数)が大きく本ラウンドでは見送り
  - [MEDIUM・対応見送り、次セッション検討] type-design-analyzer指摘: `JobSnapshot`が`sync_status=="closed"⟺closed_at is not None`の不変条件をモデル自身で検証していない。`model_validator`追加を検討したが、Firestore読み込み時(`get_all()`)に不正データで即クラッシュするリスクとのトレードオフがあり、本プロジェクトの「部分失敗は継続」方針と矛盾するため見送り(silent-failure-hunter指摘の握り込み設計とは逆方向の判断、要decision-maker確認)
  - silent-failure-hunter: `notify_slack()`の全握り込み設計・`crawl_all()`の例外網羅は「安全と確認」との評価
- **`pr-review-toolkit:code-reviewer`(review-code)の報告(2回のフォローアップ後に受領、5件・うち高深刻度2件)を反映**:
  - [HIGH・修正済み] `JobcanClient._wait_for_crawl_delay()`のcheck-sleep-update手続きに排他制御が無く、`app.py`が共有する同一クライアントへの並行リクエスト下で2スレッドが同時に同じ`remaining`待機時間を計算し、Crawl-delayの間隔保証を静かにすり抜けうる(`crawler.py`の逐次利用では発生しない、`app.py`固有のレース)。`threading.Lock`で該当区間を保護して解消
  - [HIGH・修正済み、review-codeの指摘を調査した過程で自ら発見した副次バグ] 上記スレッド安全性の調査中に、`app.py`の共有プロキシクライアントがB-1で追加した`DEFAULT_CRAWL_DELAY=3.0`(バッチクロール用)をそのまま継承していたことが判明。これはcodex/review-codeどちらも明示的に指摘していない、本セッション独自の発見で、バッチ日次実行だけでなく**本番の全ライブユーザーリクエストが3秒間隔ゲートで直列化されていた**実害バグ(review-codeのレースコンディション指摘より深刻度が高い)。`create_app()`のクライアント構築時に`JobcanClientConfig(crawl_delay=0.0)`を明示指定して解消
  - [MED・修正済み] `test_firestore_repo.py`が`conftest.py`と同内容のフェイクFirestoreクラスを重複定義。`conftest.py`からimportする形に統一
  - [MED・修正済み] `_FirestoreClientLike.collection()`が単一`name: str`引数のみを宣言しており、実SDK(`firestore.Client.collection(*collection_path: str)`)の可変長引数と構造的に不一致でpyrightが本物のクライアントを拒否。Protocol側も`*collection_path: str`に変更(テストフェイク側も追随)
  - 上記reconciliation_mismatch接続(B-6)の副作用で、`test_orchestrator.py`/`test_cli.py`のリスティングHTML生成helperが`.pagination-number`を含んでおらず`expected_total`が常に0扱いになる既存ギャップが露呈(サーキットブレーカー関連テスト3件が偽の不一致でabsence-bookkeepingを抑制され失敗)。両helperに`total_count`パラメータ(既定値`len(job_ids)`)を追加して解消
  - `review-evaluator`は合計4回のフォローアップ(idle通知への再送3回+最終確認1回)に応答なし。他4エージェント(code-reviewer/pr-test-analyzer/silent-failure-hunter/type-design-analyzer)+codex review 2ラウンドから十分な相互検証済み知見を得られたと判断し、応答を待たずレビュー完了として次工程(コミット・push・ドキュメント反映)へ進めた
  - 最終テスト221件全PASS、ruff/pyright既存ベースライン(test_app.py 17件、本PR未変更ファイル・以前からの既知偽陽性)以外エラー0件、修正3ラウンドをpush済み(直近: `4e5b426`)
  - **決裁者への報告待ち**: 上記全修正完了後、PR #129のマージには本田様の番号単位明示認可が必要(CLAUDE.md PRワークフロー)。まだ依頼していない

## セッション履歴: 2026-08-05〜06 決裁者チャット指示対応(PR #119〜#121、全完了・本番確認済み)
社長からのGoogleチャット指摘3件に対応。いずれも番号単位認可を経てマージ・ローカルmain同期・本番反映確認済み。
- **career-ladder階段化の疑義**: 社長から「右肩上がりの階段になっているか」との確認依頼。調査の結果、該当CSS(`career-ladder__step--b1〜b6`のmin-height階段実装)はPR #113で既に実装・本番反映済みと判明、Playwrightで本番URL実機確認(階段状であることを確認)。ブラウザキャッシュが原因と回答、コード変更なし
- **philosophyリード文の見出し+2段落化**(PR #119): 社長がチャットで提案した「現行の丁寧な単一パラグラフ→強調見出し「私たちはやりがい搾取を嫌悪しています！」+口語2段落」の構成へ差替え。反映方法(全置換/見出しのみ追加/社長に再確認)をAskUserQuestionで確認し「見出し+本文2段落に全置換」を選択、新規CSSクラス`.section__lead-strong`を追加
- **改行位置の孤立行修正**(PR #120→#121、2段階): PR #119後、社長から「す。」が1文字だけ次行に孤立する不格好な折返しの指摘(スクリーンショット)を受けPR #117と同じ手法(文中の自然な区切りへ`<br>`挿入)で対応(PR #120)。しかし選んだ区切り位置(「送れるように」/「することを」)が「ようにする」という一体の述語表現を分断しており、社長から再度「改行位置が不自然、読み手が読みにくい」との指摘(2回目)。改行位置を文中の読点(「私たちは、」直後)という文法的に自然な文節境界へ変更し解消(PR #121)。**同一セッション内で改行位置修正が2回連続発生**(§4.6相当の同根再発)、詳細は下記「振り返り」参照
- 完了後、社長への返信ドラフトHTML(ローカル生成・ローカルブラウザ表示、Google Chat貼付用)を作成。git非管理・ephemeral、恒久化なし

### 振り返り: 手動`<br>`による改行制御の脆弱性(記録のみ、decision-maker判断待ち)
PR #117(2026-08-04)・PR #120→#121(2026-08-05〜06)と、同一philosophyリード文パラグラフに対して**都合3回**「改行位置」起因の修正が発生している(いずれも文言変更のたびに手動`<br>`位置の再調整が必要になるパターン)。根本要因は、日本語テキストは空白を持たないため文節境界を尊重した折返しにはブラウザ標準機能だけでは不十分で、`max-width: 720px`コンテナ幅に対して都度目視で区切り位置を計算し`<br>`を手動挿入する現行方式が、文言確定→実機確認→指摘→再修正のループに陥りやすい構造的傾向がある。技術的な改善余地(例: `text-wrap: pretty`によるorphan自動回避、パラグラフを短く保つ運用ルール化 等)はあるが、**これは新規価値創出カテゴリの改善提案であり起点はdecision-maker領分**のため、AI側から着手はしない。次回同種の指摘が発生した場合(3回目相当)は、CLAUDE.md Debug Protocol「同一機能に対するバグ修正PRが3件連続→元PRの設計を再レビュー」に基づき、本振り返りを踏まえた設計見直しをdecision-makerに提案する

## セッション履歴: 2026-08-04 決裁者チャット指示対応(PR #113〜#117、全完了・本番確認済み)
前回セッションで相談中だった「career-ladder Lv.2〜4 年収帯未確定」は、決裁者から機械補間ではなく**職種別(介護施設・介護スタッフ/訪問介護・ホームヘルパー)の実データスプレッドシート**が新たに提供され、当初の相談方針(①②③)とは異なる形で解消した。
- **キャリアアップモデルの職種別タブ化**(PR #113): 単一5段階キャリアパスを「介護施設・介護スタッフ」(5段階)/「訪問介護・ホームヘルパー」(6段階)のタブ切替構成へ刷新、役職名・想定年収帯を新スプレッドシートの実データへ全面差し替え。codex review指摘2件(no-JSフォールバック欠如・color-mix非対応ブラウザのコントラスト低下)を同PR内で修正
- **法人理念の反映**(PR #114→#116→#117、3段階): 決裁者指示(①ご利用者の主体的な生活 ②スタッフの経済的リターン)を、まずphilosophyセクションのリード文へ反映(PR #114)。決裁者から「4カードにも反映すべきでは」との指摘を受け、価値観カード01・02を差し替え(PR #116、AIが初回スコープを狭く解釈していた自己認識あり)。さらに「改行が不格好」との指摘でリード文の`<br>`位置を調整(PR #117)
- **「数字で見る、あおぞら」ブロック削除**(PR #115): 決裁者指示により該当セクション+関連死コード(`.stats`/`.stat*`/`.section--band`)を完全除去。codex review指摘0件
- 3件とも本番(GitHub Pages)で実データ・実表示を直接検証済み。詳細は `docs/handoff/archive/` 化後のセッションログ、または git log (`3a96629`〜`969f3df`) 参照
