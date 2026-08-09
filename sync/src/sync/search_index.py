"""Builds the client-side job-search index (`GET /jobs/search-index.json`)
that `map-search.js` fetches to power the chip filters, freeword search, map
pins, and GPS distance sort on the all-jobs listing page (Stage 3).

Phase A's equivalent (`mockup/assets/data/jobs.json`) was a one-time build
artefact over a 37-job static sample
(`scripts/mockup-rebuild/build_geo_data.py`). This module produces the same
`{"facilities": {...}, "jobs": [...]}` shape at request time from live
Firestore snapshots instead, so it stays in sync with the full 382-posting
catalogue without a rebuild step.

Deliberately served from `/jobs/search-index.json`, not `/assets/data/
jobs.json` — that `/assets/` path is a `StaticFiles` mount over `mockup/
assets` (`app.py`), which still contains Phase A's *stale* 37-job static
file. A route under `/assets/` would either collide with that mount or be
shadowed by it; Cloud Run currently serves the old file transparently at
that exact path (verified in production, 2026-08-09) — this module's caller
(`app.py`) must not reuse it.
"""

from __future__ import annotations

from .facility_geo import area_from_address, facility_coords, facility_key
from .list_sections import category_key_from_labels
from .snapshot import JobSnapshot


def build_search_index(snapshots: dict[str, JobSnapshot]) -> dict:
    """Pure function: no Firestore access, no I/O. Only `active` postings
    with a `list_item` are included — same eligibility rule `_render_list`
    (`app.py`) uses for the plain card grid, so the search index never
    references a job_id the card list itself would exclude."""
    facilities: dict[str, dict] = {}
    jobs: list[dict] = []

    for snapshot in snapshots.values():
        if snapshot.sync_status != "active" or snapshot.list_item is None:
            continue

        address = snapshot.offer.address
        labels = snapshot.list_item.labels
        category = category_key_from_labels(labels)
        area = area_from_address(address)
        key = facility_key(address)
        coords = facility_coords(address)

        if coords is not None and key not in facilities:
            facilities[key] = {
                "name": coords.get("source_address", address),
                "city": coords["city"],
                "area": coords["area"],
                "lat": coords["lat"],
                "lng": coords["lng"],
                "jobCount": 0,
                "categories": [],
            }
        if key in facilities:
            facilities[key]["jobCount"] += 1
            if category is not None and category not in facilities[key]["categories"]:
                facilities[key]["categories"].append(category)

        jobs.append(
            {
                "id": snapshot.job_id,
                "facilityKey": key,
                "category": category,
                "employment": list(labels[1:]),
                "area": area,
            }
        )

    return {"facilities": facilities, "jobs": jobs}
