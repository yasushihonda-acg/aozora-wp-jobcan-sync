# Handoff — 2026-07-24 (地図②のさらなる刷新: 拠点別配置→拡大2パネル→Google Maps埋め込みへの3段階転換)

## TL;DR

**前回セッション(PR #76→#78→#80)で完成した九州シルエット地図に対し、決裁者から「ピンが県1点に団子状で雑」との実機フィードバックを受け、拠点別の実位置表示(PR #83)→福岡/鹿児島の拡大2パネル化(PR #84)と改善。決裁者が拡大化のレイアウト改善を評価したうえで「理想はGoogleマップで対応できないか」と明示指示、過去の「実地図はトンマナと合わない」という却下判断(PR #78)を意図的に上書きしてGoogle Maps JavaScript API埋め込みへ最終転換した。API利用のためGCPプロジェクト専用のWIF+GitHub Actions基盤を新規ブートストラップ(PR #85→#86)、Google Maps埋め込み本体を実装(PR #87)。plan mode・Evaluator・`/code-review`(medium×1、high×1)を通じて計11件の実バグ・設計課題を検出しすべて修正。PR #84はGoogle Maps版と競合しフォールバックの実益もないためクローズ。計6PRマージ+1PRクローズ。**

🔗 公開モック: https://yasushihonda-acg.github.io/aozora-wp-jobcan-sync/mockup/

## 今セッションで完了したこと

### マージ済 PR (6件) + クローズ 1件

| PR | タイトル | 内容 |
|---|---|---|
| #83 | `fix(mockup): 地図ピンを県重心1点集約から拠点別の実位置表示へ変更` | 決裁者「ピンが正しいエリアに個別に立たない、雑になった」指摘を受け、既にGPS距離計算で使っている実緯度経度を県ポリゴンの外接矩形へ線形マッピングし拠点ごとの相対位置を反映。徒歩圏内の近接拠点のみクラスタチップにまとめる |
| #84 | `feat(mockup): 地図を福岡・鹿児島の拡大2パネルに刷新` | 「福岡・鹿児島だけ拡大地図として並べては」との提案を受け、九州7県シルエットのうち拠点が実在する2県のみ抜き出し拡大パネル化。実装中にクラスタ統合しきい値不足によるピン完全重なり・介護カテゴリ色と地図塗り色の偶然一致による埋没の2件のバグを発見・修正。**後述の理由でクローズ（マージなし）** |
| #85 | `chore(infra): Google Maps API有効化用のWIF+GHAワークフローを追加` | `aozora-sns-auto`と同じ1リポジトリ=1poolパターンでWIF pool/provider/専用SA(`github-maps-admin`、Maps API管理に権限を絞る)をブートストラップ。`/code-review medium`で2件指摘(apikeys.googleapis.com有効化漏れ・リファラー制限がドメイン全体で範囲過剰)、全修正 |
| #86 | `fix(infra): APIキー作成にapikeys.googleapis.com伝播待ちのリトライを追加` | #85マージ後の実行で「API有効化直後に呼ぶと伝播遅延で失敗する」既知のGCP挙動を実機で確認、30秒間隔・最大8回のリトライを追加 |
| #87 | `feat(mockup): 求人一覧の地図をGoogle Maps埋め込みへ刷新` | 福岡/鹿児島を独立した`google.maps.Map`インスタンスとして拡大表示、`fitBounds`で自動フィット。カスタム配色ピン・`styles`配列によるブランド寄せスタイル・InfoWindow・GPS最寄りハイライトを実装。Evaluator(全7 AC PASS)+`/code-review high`(5件指摘、4件修正・1件は`gcloud`実測で担保)を経てマージ |

### 決裁者フィードバックの記録(②のビジュアル方向性、時系列・前回セッションからの続き)

| 順番 | フィードバック | 対応 |
|------|--------------|------|
| 3 | 「ピンがただしいエリアに個別に立つ事ができないんでしょうか？すごく雑になりました」 | 実緯度経度ベースの拠点別配置へ(PR #83) |
| 4 | 「拡大化するとレイアウト的に良くなったようにおもいます。これを理想はGoogleマップで対応できませんか？」 | 過去の実地図却下判断を明示的に上書きし、Google Maps JavaScript API埋め込みへ(PR #87) |

### コンプライアンス判断(明記事項)

CLAUDE.mdの「外部SaaS不採用」「ismap準拠GCP内完結」原則とGoogle Maps採用の関係を確認。「表示するのは拠点所在地(公開情報)のみで応募者個人情報を伴わない」ことを理由に、このケースは適用対象外と判断して進める明示合意を得た(CLAUDE.md自身も「採用サイト本体は個人情報を保存しない設計のため適用範囲はホスティング選定時に再判定」と留保済み)。

### 技術的知見(新規)

- **Google Maps Platform料金(2026-07-24公式確認)**: 旧$200/月クレジットは2025-02-28で終了済み。Dynamic Maps(JS API地図表示)は月10,000 load無料、超過後$7.00/1000(10万loadまで、以降段階的に下落)。2パネル構成は1ページビューあたり2 load消費
- **`google.maps.Marker`は非推奨だが廃止予定日なし**: 2024-02-21に非推奨化されたが公式に「discontinueの予定はない」と明記。新しい`AdvancedMarkerElement`はMap ID+Cloud Console側スタイル設定が別途必要なため、設定コストを避け今回はレガシーMarkerを採用
- **レガシーMarkerのキーボードアクセシビリティ**: `optimized: false` + クリックリスナーの組み合わせでbutton相当のセマンティクス(Tab/矢印キーでのroving tabindex、Enter/Spaceでのクリック)が有効になる。デフォルト(`optimized`省略)はcanvas最適化描画になりDOM要素として個別フォーカス不可
- **`gcloud services enable`直後のeventual consistency**: API有効化リクエストの受理と実際の利用可能化の間に数分の伝播遅延がある(公式エラーメッセージ「wait a few minutes for the action to propagate」)。CI/CDワークフローで直後に依存APIを呼ぶ場合はリトライ必須
- **WIFは1リポジトリ=1poolが本環境の一貫パターン**: `aozora-sns-auto`/`hr-system`/`tokunaga_chup_pj`/`visitcare-shift-optimizer`等、確認した全プロジェクトで`attribute_condition`がリポジトリ単位に厳密固定されており、複数リポジトリで使い回す共有poolは存在しない(意図的なセキュリティ分離設計)
- **Google Maps InfoWindowは地図外クリック・Escapeで自動的に閉じない**: 旧自作ポップアップの`document.addEventListener('click'/'keydown', ...)`による外側クリック・Escape閉じロジックを、InfoWindow移行時に明示的に再実装する必要がある

## 採用コンサルフィードバック5項目の状況(詳細は`docs/handoff/GOAL.md`)

- [x] ① 職種ごとの色分け — 完了(PR #72)
- [x] ② 条件+地図検索(GPS、13拠点、Google Maps版) — 完了(PR #76→#78→#80→#83→#84クローズ→#85→#86→#87、本セッションで最終確定)
- [ ] ③ 外国人採用特設ページ — 未着手、decision-maker判断待ち
- [ ] ④ 採用チャットボット — 未着手、decision-maker判断待ち
- [ ] ⑤ スタッフインタビュー再考 — 未着手、decision-maker判断待ち(本人希望で優先順位を最後に設定)

## 次のアクション

### 即着手タスク
なし(③④⑤いずれもdecision-maker側の判断・指示が必要)

### 条件待ち
| # | 項目 | trigger | 充足時のタスク |
|---|------|---------|--------------|
| 1 | ③ 外国人採用特設ページ | decision-makerが法務/人事部門確認の上で着手指示 | 内容仕様のヒアリング→plan mode |
| 2 | ④ 採用チャットボット | decision-makerがベンダー/予算方針を決定 | 方針に応じてplan mode |
| 3 | ⑤ スタッフインタビュー再考 | decision-makerが2026-07-14廃止決定の再考について指示 | 復活する場合、イニシャル+AI生成画像の仕様を軽量プランで提示 |
| 4 | Google Maps横展開(職種別一覧ページ・Phase B) | decision-makerから展開指示 | `jobs-care/nurse/office/it.html`・`sync/src/sync/templates/job_list.html`への同一実装の追従 |
| 5 | `google.maps.Marker`→`AdvancedMarkerElement`移行 | decision-makerから移行指示、またはレガシーMarkerの将来的な廃止アナウンス | Map ID発行+Cloud Console側スタイル設定を追加した上で移行 |

### 却下候補
なし

## フォローアップ(②のスコープ外、記録のみ)
- Google Maps API利用コストの監視: 現状Phase Aモック(private review段階)のトラフィックでは月10,000 load無料枠に収まる見込みだが、本番公開後はGCP予算アラート設定を検討余地あり(未設定、実装必須ではない)
- 看護系統色(ティール)は求人ダミーデータに看護師ラベルが1件も存在しないため地図上にも出現しない既知制約(①から継続)

## 最終結論

✅ **セッション終了可** — OPEN PR 0件(#87マージ済み、#84クローズ済み)、Git clean(main、origin/mainと同期済み)、即着手タスク0件・条件待ち5件(いずれもdecision-maker判断待ちで新規追加なし)、残留プロセスなし(本セッション起動のhttp.server含め全て停止確認済み、他ポートのhttp.serverプロセスは別プロジェクトセッション由来と推定され対象外)、Issue Net変化なし(起票0/close 0、本セッションはIssue不使用)、同根再発スキャン候補0件(archive過去7日分・本セッション内で`SERVICE_DISABLED`/`InfoWindow`/`WIF`等のキーワード重複なし、PR #86の伝播遅延バグとPR #87のDOM/アクセシビリティ系バグは異なる層の別根本原因)、対症療法疑いなし(PR #86はGCP公式エラーメッセージによる根本原因特定+実ワークフロー実行での検証、PR #87の4件はPlaywright実機での機能別検証、いずれも表面的な症状抑制ではない)、既知blockerなし。
