"""Facility name → coordinates lookup for the job-search map (Stage 3).

Phase A's `scripts/mockup-rebuild/build_geo_data.py` hand-geocoded 13
facilities (国土地理院 AddressSearch API, one-time lookup) that covered its
34-job static sample. Firestore's full 382-posting catalogue references 28
distinct facility names, 15 of which were absent from that 13-facility set
(2026-08-09 audit against `job_cache`). This module carries the original 13
forward unchanged and adds the 14 that could be geocoded to a single street
address (国土地理院 AddressSearch API, same one-time-lookup approach; source
addresses obtained from the company's internal 事業所マスタ spreadsheet, not
from Jobcan — Jobcan postings never carry banchi-level addresses, only a
facility label and a "nearest station" blurb).

The 15th ("共同生活援助", `【鹿児島】あおぞらケアグループ共同生活援助`) is a
single Jobcan posting that rotates across 12 group-home sites ("鹿児島市各12
事業所（宇宿、紫原、真砂本町、上荒田、上塩屋、小松原、天文館、南栄、田上、
笹貫、東千石、下荒田）のいずれか" per its own listing text) — it has no
single address to geocode and is deliberately left out of `FACILITY_COORDS`.
`facility_key()` still returns a stable key for it; callers look it up with
`.get()` and treat a miss as "no map pin for this card" rather than an error
(the posting still needs to render in the plain list/filter, just without a
pin — Stage 3 doesn't invent a location for it).

Re-geocoding, if a source address ever needs revisiting:
https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所>
"""

from __future__ import annotations

import re
import unicodedata

# 座標の妥当性チェック用レンジ (九州: 鹿児島市〜太宰府市、build_geo_data.py と同じ)
LAT_RANGE = (31.0, 34.0)
LNG_RANGE = (129.0, 131.0)

# 拠点マスタ: 13件は scripts/mockup-rebuild/build_geo_data.py の
# FACILITY_COORDS をそのまま踏襲(座標の再取得はしない)。14件は今回
# 追加ジオコーディング(2026-08-09)。キーは「地名（業態）」— Firestore の
# `offer.address`(例 "【福岡】あおぞらケアグループ四箇（デイ・有料）")から
# `facility_key()` が region/法人名プレフィックスを除去した後の残り文字列と
# 一致する。
FACILITY_COORDS: dict[str, dict] = {
    # --- 既存13件 (Phase A、build_geo_data.py と同一座標) ---
    "本社": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.572187, "lng": 130.552887,
        "source_address": "鹿児島県鹿児島市下荒田3丁目17-1",
    },
    "永吉（デイ・有料）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.602989, "lng": 130.532990,
        "source_address": "鹿児島県鹿児島市永吉2-1-14",
    },
    "鹿児島北（訪問介護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.611486, "lng": 130.520584,
        "source_address": "鹿児島県鹿児島市小野3丁目14-7",
    },
    "鹿児島南（訪問介護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.564461, "lng": 130.501053,
        "source_address": "鹿児島県鹿児島市山田町364",
    },
    "南栄（デイ・有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.506332, "lng": 130.516617,
        "source_address": "鹿児島県鹿児島市南栄5丁目10-25",
    },
    "下荒田（デイ・有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.573156, "lng": 130.558838,
        "source_address": "鹿児島県鹿児島市下荒田2丁目39-21",
    },
    "小松原（相談支援・就労・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.528824, "lng": 130.522690,
        "source_address": "鹿児島県鹿児島市小松原2-35-5",
    },
    "福岡支店": {
        "city": "福岡市博多区", "area": "fukuoka",
        "lat": 33.575733, "lng": 130.429916,
        "source_address": "福岡県福岡市博多区博多駅南6丁目13-21",
    },
    "田村（デイ・有料）": {
        "city": "福岡市早良区", "area": "fukuoka",
        "lat": 33.534451, "lng": 130.322891,
        "source_address": "福岡県福岡市早良区田村7丁目22-10",
    },
    "四箇（デイ・有料）": {
        "city": "福岡市早良区", "area": "fukuoka",
        "lat": 33.531143, "lng": 130.327820,
        "source_address": "福岡県福岡市早良区四箇6丁目23-11",
    },
    "博多（デイ・有料）": {
        "city": "福岡市博多区", "area": "fukuoka",
        "lat": 33.598984, "lng": 130.432480,
        "source_address": "福岡県福岡市博多区豊2丁目1-7",
    },
    "油山（デイ・有料）": {
        "city": "那珂川市", "area": "fukuoka",
        "lat": 33.488441, "lng": 130.390900,
        "source_address": "福岡県那珂川市西畑423-3",
    },
    "梅ヶ丘（特養）": {
        "city": "太宰府市", "area": "fukuoka",
        "lat": 33.495445, "lng": 130.545227,
        "source_address": "福岡県太宰府市梅ケ丘2丁目15番30号",
    },
    # --- 新規14件 (Stage 3、2026-08-09 追加ジオコーディング) ---
    "荒田（訪問看護・居宅）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.573261, "lng": 130.549911,
        "source_address": "鹿児島県鹿児島市荒田1-56-14",
    },
    "博多（訪問介護/訪問看護・居宅）": {
        "city": "福岡市博多区", "area": "fukuoka",
        "lat": 33.575733, "lng": 130.429916,
        "source_address": "福岡県福岡市博多区博多駅南6丁目13-21",
    },
    "宇美（デイ・有料）": {
        "city": "糟屋郡宇美町", "area": "fukuoka",
        "lat": 33.568745, "lng": 130.525574,
        "source_address": "福岡県糟屋郡宇美町宇美中央2-24-33",
    },
    "野芥（デイ・有料・GH・訪問介護）": {
        "city": "福岡市早良区", "area": "fukuoka",
        "lat": 33.538105, "lng": 130.339157,
        "source_address": "福岡県福岡市早良区野芥7-26-18",
    },
    "田上（デイ・有料）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.576668, "lng": 130.526016,
        "source_address": "鹿児島県鹿児島市田上5-3-2",
    },
    "うらら（デイ・介護付有料・GH）": {
        "city": "霧島市", "area": "kagoshima",
        "lat": 31.702023, "lng": 130.848587,
        "source_address": "鹿児島県霧島市国分下井2988",
    },
    "七福の里（デイ・有料）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.560431, "lng": 130.527039,
        "source_address": "鹿児島県鹿児島市紫原5-44-20",
    },
    "四元（介護付有料）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.571548, "lng": 130.443787,
        "source_address": "鹿児島県鹿児島市四元町1097-1",
    },
    "姶良（訪問看護）": {
        "city": "姶良市", "area": "kagoshima",
        "lat": 31.729158, "lng": 130.630478,
        "source_address": "鹿児島県姶良市宮島町10-7",
    },
    "谷山（訪問看護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.531902, "lng": 130.526642,
        "source_address": "鹿児島県鹿児島市小松原2-1-8",
    },
    "鹿児島中央（訪問介護）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.567783, "lng": 130.552246,
        "source_address": "鹿児島県鹿児島市鴨池2-3-16",
    },
    "東千石（デイ・サ高住・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.591408, "lng": 130.552505,
        "source_address": "鹿児島県鹿児島市東千石町3-19",
    },
    "武（デイ・有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.577364, "lng": 130.536575,
        "source_address": "鹿児島県鹿児島市武3-13-4",
    },
    "笹貫（有料・GH）": {
        "city": "鹿児島市", "area": "kagoshima",
        "lat": 31.539268, "lng": 130.533966,
        "source_address": "鹿児島県鹿児島市小松原1-12-23",
    },
}

_ASCII_KEY_MAP = {
    "本社": "kagoshima-hq",
    "福岡支店": "fukuoka-branch",
}

_REGION_PREFIX_RE = re.compile(r"^【[^】]*】")
_CORP_NAME_RE = re.compile(r"^あおぞらケアグループ")
_FACILITY_PAREN_RE = re.compile(r"（(?P<inner>[^）]+)）")


def facility_core_name(address: str) -> str:
    """Strip the `【福岡】`/`【鹿児島】` region marker (Firestore-crawled
    postings) and the `あおぞらケアグループ` corporate-name prefix (both
    Firestore and the Phase A mockup use it), leaving the bare
    `地名（業態）` string that keys `FACILITY_COORDS`. A posting with no
    parenthetical (e.g. `共同生活援助`, the roaming multi-site GH posting)
    is returned as-is — it deliberately has no `FACILITY_COORDS` entry."""
    core = _REGION_PREFIX_RE.sub("", address)
    core = _CORP_NAME_RE.sub("", core).strip()
    return core


def facility_key(address: str) -> str:
    """Stable slug for JSON keys / `data-*` attribute values.

    Ported from `scripts/mockup-rebuild/build_geo_data.py::facility_key`
    (extended to strip the region-marker prefix Firestore postings carry),
    with one deliberate deviation: that script dropped everything from the
    first `（` onward on the assumption that the pre-`（` place name alone
    was unique across its fixed, hand-managed 13-entry table (its own
    comment says so). Stage 3's 14 additions broke that assumption —
    `博多（デイ・有料）` and `博多（訪問介護/訪問看護・居宅）` are two
    different addresses that both reduce to `博多` — so this keeps the full
    parenthetical in the key instead (codex/second-opinion review finding,
    2026-08-09; `test_facility_geo.py`'s uniqueness test guards regression)."""
    core = facility_core_name(address)
    if core in _ASCII_KEY_MAP:
        return _ASCII_KEY_MAP[core]
    normalized = unicodedata.normalize("NFKC", core)
    return "facility-" + normalized


_SERVICE_TYPE_TOKEN_RE = re.compile(r"[・/]")

# Normalizes the abbreviated service-type tags packed into a facility's
# parenthetical (e.g. `（デイ・有料）`, `（訪問介護/訪問看護・居宅）`) to a
# display-friendly name. Ported and extended from Phase A's
# `chatbot/scripts/build_jobs_detail.py::_SERVICE_TYPE_MAP` (which only had
# 7 entries — `介護付有料`/`サ高住`/`居宅`/`訪問看護` were silently
# pass-through there, undetected because that script's own facility set
# never exercised them). `test_service_types_from_address_covers_every_
# facility_coords_tag` pins every abbreviation actually present across all
# 27 `FACILITY_COORDS` entries, so a future unmapped tag fails loudly
# instead of leaking a raw abbreviation into chatbot-facing text.
_SERVICE_TYPE_MAP = {
    "デイ": "デイサービス",
    "有料": "有料老人ホーム",
    "介護付有料": "介護付有料老人ホーム",
    "特養": "特別養護老人ホーム",
    "GH": "グループホーム",
    "サ高住": "サービス付き高齢者向け住宅",
    "訪問介護": "訪問介護",
    "訪問看護": "訪問看護",
    "居宅": "居宅介護支援",
    "相談支援": "相談支援",
    "就労": "就労支援",
}


def service_types_from_address(address: str) -> list[str]:
    """Normalized service-type tags packed into `address`'s parenthetical
    (e.g. `【福岡】あおぞらケアグループ四箇（デイ・有料）` →
    `["デイサービス", "有料老人ホーム"]`), for chatbot-facing service-type
    disambiguation (see `chatbot_knowledge.py`).

    An unmapped token passes through unchanged rather than raising — the
    same permissive behaviour as Phase A's script, so a brand-new Jobcan
    facility naming convention degrades to "the tag is just shown as-is"
    instead of taking the sync job down. `本社`/`福岡支店` and the roaming
    GH posting (`共同生活援助`) carry no parenthetical at all and resolve
    to `[]`.
    """
    match = _FACILITY_PAREN_RE.search(facility_core_name(address))
    if not match:
        return []
    tokens = _SERVICE_TYPE_TOKEN_RE.split(match.group("inner"))
    return [_SERVICE_TYPE_MAP.get(token, token) for token in tokens]


def facility_coords(address: str) -> dict | None:
    """`FACILITY_COORDS[facility_core_name(address)]`, or `None` for a
    posting with no single-address facility (the roaming GH posting) or an
    address this table has never seen (logged by the caller, not here —
    this module stays a pure lookup)."""
    return FACILITY_COORDS.get(facility_core_name(address))


_REGION_TO_AREA = {"福岡": "fukuoka", "鹿児島": "kagoshima"}


def area_from_address(address: str) -> str | None:
    """`fukuoka`/`kagoshima` from the `【福岡】`/`【鹿児島】` region marker —
    independent of `FACILITY_COORDS`, so area-chip filtering still works for
    a posting whose facility has no geocoded pin (e.g. the roaming GH
    posting, still tagged `【鹿児島】`). `本社`/`福岡支店` carry no region
    marker at all, so those two fall back to their known coords entry."""
    m = _REGION_PREFIX_RE.match(address)
    if m:
        return _REGION_TO_AREA.get(m.group(0).strip("【】"))
    coords = facility_coords(address)
    return coords["area"] if coords else None
