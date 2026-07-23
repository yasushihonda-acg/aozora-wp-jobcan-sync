"""jobs.html の 34 件カードから拠点+座標つきの検索用データ (jobs.json) を生成する.

地図検索機能(採用コンサルフィードバック②)のための一度きりのビルドスクリプト。
jobs.html の各カード(職種色分けクラス・雇用形態ラベル・拠点住所)をソースとして読み取り、
FACILITY_COORDS(国土地理院 AddressSearch API で番地レベル住所から一度だけ取得した座標。
再取得が必要な場合は https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所> を叩く)
と結合して mockup/assets/data/jobs.json を書き出す。

jobs.html 自体は改変しない(読み取り専用)。
"""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
JOBS_HTML = REPO / "mockup" / "jobs.html"
OUT_JSON = REPO / "mockup" / "assets" / "data" / "jobs.json"

# 拠点マスタ: jobs.html のカード住所 (「市区町村 ／ 拠点名」の拠点名部分) をキーとする。
# 座標は国土地理院 AddressSearch API (2026-07-23 一度きり取得、[lng, lat] → lat/lng に変換) 由来。
FACILITY_COORDS: dict[str, dict] = {
    "本社": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.572187, "lng": 130.552887,
        "source_address": "鹿児島県鹿児島市下荒田3丁目17-1",
    },
    "あおぞらケアグループ永吉（デイ・有料）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.602989, "lng": 130.532990,
        "source_address": "鹿児島県鹿児島市永吉2-1-14",
    },
    "あおぞらケアグループ鹿児島北（訪問介護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.611486, "lng": 130.520584,
        "source_address": "鹿児島県鹿児島市小野3丁目14-7",
    },
    "あおぞらケアグループ鹿児島南（訪問介護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.564461, "lng": 130.501053,
        "source_address": "鹿児島県鹿児島市山田町364",
    },
    "あおぞらケアグループ南栄（デイ・有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.506332, "lng": 130.516617,
        "source_address": "鹿児島県鹿児島市南栄5丁目10-25",
    },
    "あおぞらケアグループ下荒田（デイ・有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.573156, "lng": 130.558838,
        "source_address": "鹿児島県鹿児島市下荒田2丁目39-21",
    },
    "あおぞらケアグループ小松原（相談支援・就労・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.528824, "lng": 130.522690,
        "source_address": "鹿児島県鹿児島市小松原2-35-5",
    },
    "福岡支店": {
        "city": "福岡市博多区", "area": "fukuoka",
        "lat": 33.575733, "lng": 130.429916,
        "source_address": "福岡県福岡市博多区博多駅南6丁目13-21",
    },
    "あおぞらケアグループ田村（デイ・有料）": {
        "city": "福岡市早良区", "area": "fukuoka",
        "lat": 33.534451, "lng": 130.322891,
        "source_address": "福岡県福岡市早良区田村7丁目22-10",
    },
    "あおぞらケアグループ四箇（デイ・有料）": {
        "city": "福岡市早良区", "area": "fukuoka",
        "lat": 33.531143, "lng": 130.327820,
        "source_address": "福岡県福岡市早良区四箇6丁目23-11",
    },
    "あおぞらケアグループ博多（デイ・有料）": {
        "city": "福岡市博多区", "area": "fukuoka",
        "lat": 33.598984, "lng": 130.432480,
        "source_address": "福岡県福岡市博多区豊2丁目1-7",
    },
    "あおぞらケアグループ油山（デイ・有料）": {
        "city": "那珂川市", "area": "fukuoka",
        "lat": 33.488441, "lng": 130.390900,
        "source_address": "福岡県那珂川市西畑423-3",
    },
    "あおぞらケアグループ梅ヶ丘（特養）": {
        "city": "太宰府市", "area": "fukuoka",
        "lat": 33.495445, "lng": 130.545227,
        "source_address": "福岡県太宰府市梅ケ丘2丁目15番30号",
    },
}

# 座標の妥当性チェック用レンジ (九州: 鹿児島市〜太宰府市)
LAT_RANGE = (31.0, 34.0)
LNG_RANGE = (129.0, 131.0)


def facility_key(name: str) -> str:
    """表示名から安定した slug key を生成 (JSON キー・data 属性値用)。"""
    import re
    import unicodedata

    ascii_map = {
        "本社": "kagoshima-hq",
        "福岡支店": "fukuoka-branch",
    }
    if name in ascii_map:
        return ascii_map[name]
    # 「あおぞらケアグループ<地名>（...）」→ <地名>のローマ字は用意していないため、
    # 全角括弧の前までを正規化してキーにする (人手管理下の固定13件なので衝突しない)。
    core = re.sub(r"（.*", "", name).replace("あおぞらケアグループ", "").strip()
    normalized = unicodedata.normalize("NFKC", core)
    return "facility-" + normalized


def main() -> None:
    html = JOBS_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("li", class_="job-list-card")
    print(f"jobs.html から {len(cards)} 件のカードを検出")

    facilities: dict[str, dict] = {}
    jobs: list[dict] = []
    unmatched: list[str] = []

    for card in cards:
        classes = card.get("class", [])
        category = next(
            (c.replace("job-list-card--", "") for c in classes if c.startswith("job-list-card--")),
            None,
        )
        link = card.find("a", class_="job-list-card__link")
        href = link.get("href") if link else None
        job_id = href.split("/")[-1].replace(".html", "") if href else None

        labels = [li.get_text(strip=True) for li in card.find_all("li", class_="job-list-card__label")]
        employment = labels[1:] if len(labels) > 1 else []

        addr_el = card.find("p", class_="job-list-card__address")
        addr_text = addr_el.get_text(strip=True) if addr_el else ""
        facility_name = addr_text.split("／")[-1].strip() if "／" in addr_text else addr_text

        if facility_name not in FACILITY_COORDS:
            unmatched.append(f"{job_id}: {facility_name!r}")
            continue

        key = facility_key(facility_name)
        if key not in facilities:
            coords = FACILITY_COORDS[facility_name]
            facilities[key] = {
                "name": facility_name,
                "city": coords["city"],
                "area": coords["area"],
                "lat": coords["lat"],
                "lng": coords["lng"],
                "jobCount": 0,
                "categories": [],
            }
        facilities[key]["jobCount"] += 1
        if category and category not in facilities[key]["categories"]:
            facilities[key]["categories"].append(category)

        jobs.append({
            "id": job_id,
            "facilityKey": key,
            "category": category,
            "employment": employment,
            "area": facilities[key]["area"],
        })

    if unmatched:
        raise SystemExit(
            "FACILITY_COORDS に未登録の拠点がカードに存在します:\n  " + "\n  ".join(unmatched)
        )

    # 検証: 34求人・13拠点・座標が九州レンジ内
    assert len(jobs) == 34, f"求人件数が想定外: {len(jobs)}"
    assert len(facilities) == 13, f"拠点件数が想定外: {len(facilities)}"
    for key, f in facilities.items():
        assert LAT_RANGE[0] <= f["lat"] <= LAT_RANGE[1], f"{key} の緯度が範囲外: {f['lat']}"
        assert LNG_RANGE[0] <= f["lng"] <= LNG_RANGE[1], f"{key} の経度が範囲外: {f['lng']}"

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps({"facilities": facilities, "jobs": jobs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK: 求人{len(jobs)}件 / 拠点{len(facilities)}件 → {OUT_JSON.relative_to(REPO)} に出力")


if __name__ == "__main__":
    main()
