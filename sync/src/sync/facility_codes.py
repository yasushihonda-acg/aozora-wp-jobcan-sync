"""Single source of truth for Jobcan's 拠点 (facility/branch) code → name/address
table (ats.jobcan.jp/configs/branches).

Same design as `job_types.py` (category_id → name): a manually-curated
constant, not auto-fetched, because facility openings are rare deliberate
business events, unlike job-posting churn. Captured 2026-08-10 from the live
"拠点一覧" admin screen.

Feeds the CSV-ingestion pipeline's facility_key derivation: the job CSV's
"募集拠点" column holds only the code (e.g. "b030"), not a name — this table
resolves that code to `name`, which is in the SAME bracketed-name format
(`【福岡】あおぞらケアグループ野芥（デイ・有料・GH・訪問介護）`)
`facility_geo.py` already parses from the HTML-scraping path today, so no
new parsing logic is needed on the consumer side, only this lookup.

Non-care-facility codes (b001 本社, b002/b012/b015 various offices, b022
ネスレ薬局, b023 東京オフィス) are kept in the table as-is — callers that
only care about care facilities should filter by whatever signal already
distinguishes them (e.g. presence of `【福岡】`/`【鹿児島】` bracket prefix
in `name`, matching how `facility_geo.py` already treats untagged addresses).

TODO once the jobcan-sync@aozora-cg.com limited-role account is active:
confirm it can view /configs/branches (this is under 設定, outside the
5-item 求人/候補者/レポート permission matrix that role was scoped to) — if
so, this table can be auto-refreshed each sync run instead of manually
re-captured; if not, keep this manual-refresh pattern (same trade-off
`job_types.py` already accepted for LABEL_TO_CATEGORY drift risk).
"""

from __future__ import annotations

# 拠点コード -> (名前, 郵便番号, 住所)
FACILITY_CODES: dict[str, tuple[str, str, str]] = {
    "b001": ("本社", "890-0056", "鹿児島県鹿児島市下荒田3丁目17-1 レジデンス久野3F"),
    "b002": ("福岡支店", "812-0016", "福岡県福岡市博多区博多駅南6丁目13-21 駅南ジェイティビル2F"),
    "b003": (
        "【鹿児島】あおぞらケアグループ武（デイ・有料・GH）",
        "890-0045",
        "鹿児島県鹿児島市武3-13-4",
    ),
    "b004": (
        "【鹿児島】あおぞらケアグループ荒田（訪問看護・居宅）",
        "890-0054",
        "鹿児島県鹿児島市荒田1丁目56-14",
    ),
    "b005": (
        "【鹿児島】あおぞらケアグループ鹿児島中央（訪問介護）",
        "890-0063",
        "鹿児島県鹿児島市鴨池2丁目3-16 えりかビル3F",
    ),
    "b006": (
        "【鹿児島】あおぞらケアグループ下荒田（デイ・有料・GH）",
        "890-0056",
        "鹿児島県鹿児島市下荒田2丁目39-21",
    ),
    "b007": (
        "【鹿児島】あおぞらケアグループ東千石（デイ・サ高住・GH）",
        "892-0842",
        "鹿児島県鹿児島市東千石町3-19",
    ),
    "b008": (
        "【鹿児島】あおぞらケアグループ小松原（相談支援・就労・GH）",
        "891-0114",
        "鹿児島県鹿児島市小松原2-35-5 清見橋ビル",
    ),
    "b009": (
        "【鹿児島】あおぞらケアグループ笹貫（有料・GH）",
        "891-0114",
        "鹿児島県鹿児島市小松原1丁目12-23",
    ),
    "b010": (
        "【鹿児島】あおぞらケアグループ永吉（デイ・有料）",
        "890-0023",
        "鹿児島県鹿児島市永吉2-1-14",
    ),
    "b011": (
        "【鹿児島】あおぞらケアグループ谷山（訪問看護）",
        "891-0114",
        "鹿児島県鹿児島市小松原2-1-8 エンプレスマンション202",
    ),
    "b012": (
        "【福岡】あおぞらケアグループ博多（訪問介護/訪問看護・居宅）",
        "812-0016",
        "福岡県福岡市博多区博多駅南6丁目13-21 駅南ジェイティビル2F",
    ),
    "b013": ("【鹿児島】あおぞらケアグループ共同生活援助", "", "鹿児島県鹿児島市内の各事業所"),
    "b014": (
        "【鹿児島】あおぞらケアグループ 田上（デイ・有料）",
        "890-0034",
        "鹿児島県鹿児島市田上5-3-2",
    ),
    "b015": (
        "【福岡】あおぞらケアグループ博多（デイ・有料）",
        "812-0042",
        "福岡県福岡市博多区豊2丁目1-7",
    ),
    "b016": (
        "【鹿児島】あおぞらケアグループ鹿児島北（訪問介護）",
        "890-0021",
        "鹿児島県鹿児島市小野3丁目14-7 第2寿ハイツ101",
    ),
    "b017": (
        "【鹿児島】あおぞらケアグループ姶良（訪問看護）",
        "899-5432",
        "鹿児島県姶良市宮島町10-7 C",
    ),
    "b020": (
        "【鹿児島】あおぞらケアグループ四元（介護付有料）",
        "899-2708",
        "鹿児島県鹿児島市四元町1097-1",
    ),
    "b021": (
        "【鹿児島】あおぞらケアグループ南栄（デイ・有料・GH）",
        "891-0122",
        "鹿児島県鹿児島市南栄5丁目10-25",
    ),
    "b022": ("ネスレ薬局", "892-0847", "鹿児島県鹿児島市西千石町3-26 201号"),
    "b023": ("東京オフィス", "108-0075", "東京都港区港南2丁目17-1 京王品川ビル2階"),
    "b028": (
        "【福岡】あおぞらケアグループ梅ヶ丘（特養）",
        "818-0123",
        "福岡県太宰府市梅ケ丘2丁目15番30号",
    ),
    "b030": (
        "【福岡】あおぞらケアグループ野芥（デイ・有料・GH・訪問介護）",
        "814-0171",
        "福岡県福岡市早良区野芥7-26-18",
    ),
    "b031": (
        "【鹿児島】あおぞらケアグループ七福の里（デイ・有料）",
        "890-0082",
        "鹿児島県鹿児島市紫原5-44-20",
    ),
    "b032": (
        "【鹿児島】あおぞらケアグループうらら（デイ・介護付有料・GH）",
        "899-4463",
        "鹿児島県霧島市国分下井2988",
    ),
    "b033": (
        "【福岡】あおぞらケアグループ宇美（デイ・有料）",
        "811-2128",
        "福岡県糟屋郡宇美町宇美中央2丁目24-33",
    ),
    "b034": (
        "【福岡】あおぞらケアグループ油山（デイ・有料）",
        "811-1246",
        "福岡県那珂川市西畑423-3",
    ),
    "b035": (
        "【福岡】あおぞらケアグループ田村（デイ・有料）",
        "814-0175",
        "福岡県福岡市早良区田村7丁目22-10",
    ),
    "b036": (
        "【鹿児島】あおぞらケアグループ鹿児島南（訪問介護）",
        "891-0104",
        "鹿児島県鹿児島市山田町364 サンステージB棟202",
    ),
    "b037": (
        "【福岡】あおぞらケアグループ四箇（デイ・有料）",
        "811-1103",
        "福岡県福岡市早良区四箇6丁目23-11",
    ),
}
