"""Tests for the facility-name → coordinates lookup (Stage 3, `facility_geo.py`)."""

from __future__ import annotations

from sync.facility_geo import (
    FACILITY_COORDS,
    LAT_RANGE,
    LNG_RANGE,
    area_from_address,
    facility_coords,
    facility_key,
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
    assert facility_key("【福岡】あおぞらケアグループ四箇（デイ・有料）") == "facility-四箇"


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
