# Aozora ACG Phase B - Jobcan Proxy Sync

ジョブカン公開ページを取得し、自社 BEM デザインで再表示する Cloud Run プロキシ。
応募ボタンはジョブカン側 URL に直リンクし、応募導線はジョブカン側で完結します。

## Phase 0 (本セッション)

ローカル動作する最小実装:
- `python -m sync render 1777023 > out.html` で 1 求人を取得 → 自社テンプレで HTML 出力
- pytest で parser / renderer / client mock の単体テスト

## セットアップ

```bash
cd sync
uv sync
uv run python -m sync render 1777023 --out out.html
```

## アーキテクチャ

```
sync/
  src/sync/
    models.py          # Pydantic JobOffer
    jobcan_client.py   # httpx クライアント (timeout/UA/retry)
    parser.py          # BeautifulSoup パーサー (sanitize + 必須項目バリデーション)
    renderer.py        # Jinja2 テンプレレンダリング
    cli.py             # Typer CLI
    templates/         # 自社 BEM テンプレ
    static/            # コンポーネント CSS (mockup/assets/css/ とは分離)
  tests/
    fixtures/jobcan_responses/  # 検証済み実 HTML + 壊れ HTML
    test_parser.py
    test_renderer.py
    test_client.py
```

## Phase 0 の制約 (Codex 指摘反映)

- **本番デプロイ禁止**: ジョブカン公式照会回答前は本番運用不可
- **sanitize 必須**: 外部 HTML を自社ドメインで配信する責任を負うため、bleach で許可タグ方式
- **必須項目バリデーション**: 給与/勤務地/雇用形態の欠落で例外、部分表示禁止
- **CSS は tokens.css のみ共有**: コンポーネント CSS は本プロジェクト内で完結

詳細: `../docs/specs/jobcan-html-structure.md` / `../docs/specs/sync-strategy.md`
