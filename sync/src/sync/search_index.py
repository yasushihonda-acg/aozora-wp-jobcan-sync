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

from .facility_geo import area_from_address, facility_coords, facility_core_name, facility_key
from .list_sections import LABEL_TO_CATEGORY, category_key_from_labels
from .snapshot import JobSnapshot


def build_search_index(snapshots: dict[str, JobSnapshot]) -> tuple[dict, list[str]]:
    """Pure function: no Firestore access, no I/O (logging included — the
    caller decides where warnings go, same split `_render_list`/`app.py`
    already use for `skipped` malformed docs).

    Only `active` postings with a `list_item` are included — same
    eligibility rule `_render_list` (`app.py`) uses for the plain card grid,
    so the search index never references a job_id the card list itself
    would exclude.

    Returns `(index, warnings)`. A `facility_coords()` miss and a
    `category_key_from_labels()` miss both degrade silently in the returned
    index (no pin / no colour accent, not an error) — but a miss for either
    is also *indistinguishable at the call site* from data drift (a newly
    added Jobcan facility/job-type this table has never seen) unless it's
    surfaced somewhere. `warnings` is that surface (silent-failure-hunter
    review finding, 2026-08-09) — one job_id list per miss kind, not a
    per-job log line, so a whole-catalogue drift doesn't flood the log.
    """
    facilities: dict[str, dict] = {}
    jobs: list[dict] = []
    unmatched_facility_job_ids: list[str] = []
    uncategorized_job_ids: list[str] = []

    for snapshot in snapshots.values():
        if snapshot.sync_status != "active" or snapshot.list_item is None:
            continue

        address = snapshot.offer.address
        labels = snapshot.list_item.labels
        category = category_key_from_labels(labels)
        area = area_from_address(address)
        key = facility_key(address)
        coords = facility_coords(address)

        if coords is None:
            unmatched_facility_job_ids.append(snapshot.job_id)
        if category is None:
            uncategorized_job_ids.append(snapshot.job_id)

        if coords is not None and key not in facilities:
            facilities[key] = {
                "name": facility_core_name(address),
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

        # `labels[1:]` would assume the category label is always first —
        # Jobcan's label order is observation, not contract (same lesson
        # `parser.py::_resolve_display_thumbnail` already encodes, and
        # `category_key_from_labels` itself doesn't rely on position
        # either). Excluding whatever *is* a recognised category label
        # keeps this correct regardless of order (codex review finding).
        employment = [label for label in labels if label not in LABEL_TO_CATEGORY]

        jobs.append(
            {
                "id": snapshot.job_id,
                "facilityKey": key,
                "category": category,
                "employment": employment,
                "area": area,
            }
        )

    warnings: list[str] = []
    if unmatched_facility_job_ids:
        warnings.append(
            "no facility_coords match (no map pin) for job_ids: "
            f"{unmatched_facility_job_ids}"
        )
    if uncategorized_job_ids:
        warnings.append(
            "no category_key match (no colour accent) for job_ids: "
            f"{uncategorized_job_ids}"
        )
    return {"facilities": facilities, "jobs": jobs}, warnings
