"""Tests for the facility-name → coordinates lookup (Stage 3, `facility_geo.py`)."""

from __future__ import annotations

from sync.facility_geo import (
    FACILITY_COORDS,
    LAT_RANGE,
    LNG_RANGE,
    area_from_address,
    facility_coords,
    facility_key,
    service_types_from_address,
)


def test_facility_coords_matches_region_prefixed_firestore_address() -> None:
    coords = facility_coords("【福岡】あおぞらケアグループ四箇（デイ・有料）")
    assert coords is not None
    assert coords["source_address"] == "福岡県福岡市早良区四箇6丁目23-11"


def test_facility_coords_matches_prefix_less_phase_a_address() -> None:
    """Phase A's `mockup/jobs.html` cards never carried the `【福岡】`/
    `【鹿児島】` marker — the lookup must work either way."""
    assert facility_coords("あおぞらケアグループ四箇（デイ・有料）") == facility_coords(
        "【福岡】あおぞらケアグループ四箇（デイ・有料）"
    )


def test_facility_coords_none_for_roaming_gh_posting() -> None:
    """`共同生活援助` has no single address (rotates across 12 sites) — this
    is a deliberate design choice, not a lookup gap."""
    assert facility_coords("【鹿児島】あおぞらケアグループ共同生活援助") is None


def test_facility_coords_none_for_unknown_address() -> None:
    assert facility_coords("【福岡】あおぞらケアグループ架空拠点（テスト）") is None


def test_facility_key_stable_for_ascii_map_entries() -> None:
    assert facility_key("本社") == "kagoshima-hq"
    assert facility_key("福岡支店") == "fukuoka-branch"


def test_facility_key_strips_region_and_corp_prefix() -> None:
    key = facility_key("【福岡】あおぞらケアグループ四箇（デイ・有料）")
    assert key == "facility-四箇(デイ・有料)"


def test_facility_key_keeps_parenthetical_to_disambiguate_same_place_name() -> None:
    """`博多（デイ・有料）` and `博多（訪問介護/訪問看護・居宅）` are two
    different physical addresses — a key derived from the pre-`（` place
    name alone would collapse them (code-reviewer finding, 2026-08-09;
    Phase A's original `build_geo_data.py::facility_key` dropped the
    parenthetical, safe only under its fixed, hand-verified 13-entry
    table)."""
    key_a = facility_key("【福岡】あおぞらケアグループ博多（デイ・有料）")
    key_b = facility_key("【福岡】あおぞらケアグループ博多（訪問介護/訪問看護・居宅）")
    assert key_a != key_b


def test_facility_key_unique_across_every_facility_coords_entry() -> None:
    keys = [facility_key(name) for name in FACILITY_COORDS]
    assert len(keys) == len(set(keys))


def test_area_from_address_reads_region_marker_even_without_coords() -> None:
    """The roaming GH posting has no coords but is still tagged `【鹿児島】`
    — area-chip filtering must work for it regardless."""
    assert area_from_address("【鹿児島】あおぞらケアグループ共同生活援助") == "kagoshima"
    assert area_from_address("【福岡】あおぞらケアグループ四箇（デイ・有料）") == "fukuoka"


def test_area_from_address_falls_back_to_coords_for_prefix_less_names() -> None:
    assert area_from_address("本社") == "kagoshima"
    assert area_from_address("福岡支店") == "fukuoka"


def test_area_from_address_none_for_unknown_prefix_less_name() -> None:
    assert area_from_address("架空拠点") is None


def test_all_28_facility_coords_are_within_kyushu_lat_lng_range() -> None:
    for name, coords in FACILITY_COORDS.items():
        assert LAT_RANGE[0] <= coords["lat"] <= LAT_RANGE[1], name
        assert LNG_RANGE[0] <= coords["lng"] <= LNG_RANGE[1], name


def test_facility_coords_table_has_27_entries_13_original_plus_14_new() -> None:
    assert len(FACILITY_COORDS) == 27


def test_service_types_from_address_known_examples() -> None:
    assert service_types_from_address(
        "【福岡】あおぞらケアグループ四箇（デイ・有料）"
    ) == ["デイサービス", "有料老人ホーム"]
    assert service_types_from_address(
        "【鹿児島】あおぞらケアグループ梅ヶ丘（特養）"
    ) == ["特別養護老人ホーム"]


def test_service_types_from_address_splits_on_both_slash_and_dot_delimiters() -> None:
    """`博多（訪問介護/訪問看護・居宅）` mixes `/` and `・` as delimiters within
    a single parenthetical — both must be treated as token separators."""
    assert service_types_from_address(
        "【福岡】あおぞらケアグループ博多（訪問介護/訪問看護・居宅）"
    ) == ["訪問介護", "訪問看護", "居宅介護支援"]


def test_service_types_from_address_empty_for_untagged_facility() -> None:
    """`本社`/`福岡支店` carry no parenthetical service-type tag."""
    assert service_types_from_address("本社") == []
    assert service_types_from_address("福岡支店") == []


def test_service_types_from_address_empty_for_roaming_gh_posting() -> None:
    """`共同生活援助` has no parenthetical at all (see facility_geo module
    docstring) — must degrade to an empty list, not raise."""
    assert service_types_from_address("【鹿児島】あおぞらケアグループ共同生活援助") == []


def test_service_types_from_address_covers_every_facility_coords_tag() -> None:
    """Every parenthetical token across all 27 `FACILITY_COORDS` entries must
    resolve to a normalized service-type name, never pass through as a raw
    abbreviation (`GH`, `デイ`, `サ高住`, ...). A future Jobcan facility
    naming addition that introduces a new abbreviation must fail this test
    until the normalization map is extended."""
    raw_abbreviations = {
        "デイ",
        "有料",
        "介護付有料",
        "GH",
        "特養",
        "サ高住",
        "訪問介護",  # note: also a valid normalized name itself (see below)
        "居宅",
        "相談支援",  # note: also a valid normalized name itself (see below)
        "就労",
    }
    # `訪問介護`/`訪問看護`/`相談支援` are simultaneously the raw tag AND the
    # normalized display name (no abbreviation to expand) — only the
    # genuinely-abbreviated forms must never survive untranslated.
    must_not_pass_through = raw_abbreviations - {"訪問介護", "相談支援"}

    for address in FACILITY_COORDS:
        for service_type in service_types_from_address(address):
            assert service_type not in must_not_pass_through, (
                f"{address!r} produced untranslated abbreviation {service_type!r}"
            )
