"""Tests for `facility_codes.py` — the 拠点コード (branch code) → name/address
table captured from ats.jobcan.jp/configs/branches (CSV-migration follow-up,
2026-08-10). Pins the cross-table invariant against `facility_geo.py` so a
future Jobcan facility addition that lacks map coordinates fails loudly here
instead of silently losing its map pin at render time.
"""

from __future__ import annotations

import re

from sync.facility_codes import FACILITY_CODES
from sync.facility_geo import FACILITY_COORDS, facility_core_name

# Facilities with no single geocodable address (see facility_geo.py module
# docstring for b013's roaming-12-sites rationale) and two non-care offices
# that were never in scope for the map feature.
_UNGEOCODED_CODES = {"b013", "b022", "b023"}


def test_facility_codes_has_thirty_entries() -> None:
    assert len(FACILITY_CODES) == 30


def test_facility_codes_codes_are_well_formed_and_unique() -> None:
    assert all(re.fullmatch(r"b\d{3}", code) for code in FACILITY_CODES)
    assert len(set(FACILITY_CODES)) == len(FACILITY_CODES)


def test_facility_codes_names_are_unique() -> None:
    names = [name for name, _postal, _addr in FACILITY_CODES.values()]
    assert len(set(names)) == len(names)


def test_every_geocodable_facility_resolves_to_coords() -> None:
    for code, (name, _postal, _addr) in FACILITY_CODES.items():
        if code in _UNGEOCODED_CODES:
            continue
        assert facility_core_name(name) in FACILITY_COORDS, (code, name)


def test_ungeocoded_codes_are_exactly_the_documented_exceptions() -> None:
    misses = {
        code
        for code, (name, _postal, _addr) in FACILITY_CODES.items()
        if facility_core_name(name) not in FACILITY_COORDS
    }
    assert misses == _UNGEOCODED_CODES


def test_no_orphan_coords_entries() -> None:
    """Every `FACILITY_COORDS` key must be reachable from some
    `FACILITY_CODES` entry — an orphan would mean a coords entry for a
    facility Jobcan no longer lists."""
    cores = {facility_core_name(name) for name, _postal, _addr in FACILITY_CODES.values()}
    assert set(FACILITY_COORDS) - cores == set()
