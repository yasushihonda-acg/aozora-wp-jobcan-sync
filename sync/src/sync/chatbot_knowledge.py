"""Builds the `GET /jobs/chatbot-knowledge.json` payload — the source
`chatbot/`'s knowledge base fetches at startup (and on its periodic
refresh) as the grounding data Gemini uses to recommend jobs.

Phase A's equivalent (`chatbot/src/chatbot/knowledge/jobs_detail.json`) was
a one-time build artefact over a 37-job static sample
(`chatbot/scripts/build_jobs_detail.py`, sourced from `mockup/jobs.html`),
requiring a human to re-run the script and `git push` for every catalogue
change. It last ran 2026-08-08 and was never re-run after — by the time this
module was written, the site itself served 390 real postings while the
chatbot still only knew about those original 37. This module produces the
same 9-field shape at request time from live Firestore snapshots instead
(mirroring `search_index.py`'s own "stop hand-rebuilding, derive at request
time" fix for the same underlying staleness pattern), so the chatbot's
knowledge tracks the 6-hourly sync without a rebuild step.

Deliberately a *separate* endpoint from `/jobs/search-index.json`, not a
reuse of it: that payload's `jobs[]` entries carry no `title` (needed for
`map-search.js`'s freeword/chip filtering, not for job identification —
`facilityKey` is enough there) and have no `service_types` concept at all.
Retrofitting those onto `search_index.py` would bloat a payload
`map-search.js` fetches on every listing-page load with fields only the
chatbot needs.
"""

from __future__ import annotations

import re

from .facility_geo import area_from_address, facility_coords, facility_core_name
from .facility_geo import service_types_from_address as _service_types_from_address
from .list_sections import LABEL_TO_CATEGORY, category_key_from_labels
from .snapshot import JobSnapshot

# A job titled "相談支援専門員" is specifically a 相談支援 role even when its
# facility carries other service tags too (e.g. 小松原「相談支援・就労・GH」)
# — tagging it with the full facility service-type list would let Gemini
# recommend it for a GH/就労支援 query it doesn't actually belong to. Ported
# from `chatbot/scripts/build_jobs_detail.py::_TITLE_SERVICE_TYPE_OVERRIDE`
# (originally a Codex review-diff finding on job 90447 under the Phase A
# pipeline; the same facility-ambiguity risk applies unchanged here).
_TITLE_SERVICE_TYPE_OVERRIDE: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"相談支援専門員"), ["相談支援"]),
]


def _service_types_for(address: str, title: str) -> list[str]:
    for pattern, override in _TITLE_SERVICE_TYPE_OVERRIDE:
        if pattern.search(title):
            return override
    return _service_types_from_address(address)


def build_chatbot_knowledge(snapshots: dict[str, JobSnapshot]) -> tuple[list[dict], list[str]]:
    """Pure function: no Firestore access, no I/O (same split `app.py`
    already uses for `search_index.py` — the caller decides where warnings
    go).

    Only `active` postings with a `list_item` are included — the same
    eligibility rule `build_search_index` uses, so the chatbot never
    recommends a job_id the plain card list itself would exclude.

    Unlike `build_search_index` (which simply omits a `facility_coords()`
    miss from its `facilities` map, leaving the job with "no map pin"), a
    miss here still produces a full record with `city=""` and
    `service_types=[]` — dropping the job entirely would remove a real,
    applyable posting from what the chatbot can recommend, which is exactly
    the staleness bug this module exists to fix. The miss is still surfaced
    via `warnings` (one job_id list, not a per-job log line) so a whole-
    catalogue drift is observable.
    """
    records: list[dict] = []
    missing_city_job_ids: list[str] = []
    uncategorized_job_ids: list[str] = []
    unmatched_area_job_ids: list[str] = []

    for snapshot in snapshots.values():
        if snapshot.sync_status != "active" or snapshot.list_item is None:
            continue

        offer = snapshot.offer
        list_item = snapshot.list_item
        address = offer.address
        labels = list_item.labels

        coords = facility_coords(address)
        if coords is None:
            missing_city_job_ids.append(snapshot.job_id)

        # `category`/`area` MUST be strings, unlike `search_index.py`'s
        # `jobs[]` (whose consumer, `map-search.js`, tolerates `null`):
        # chatbot's `parse_jobs_detail()` validates this entire payload as
        # one `list[_StrictJobDetail]` call, so a single `None` here would
        # fail the WHOLE knowledge refresh — every other active posting
        # would lose its recommendability too, not just this one job
        # (codex review finding, 2026-08-09).
        category = category_key_from_labels(labels)
        if category is None:
            uncategorized_job_ids.append(snapshot.job_id)
            category = "unknown"
        area = area_from_address(address)
        if area is None:
            unmatched_area_job_ids.append(snapshot.job_id)
            area = "unknown"

        # `labels[1:]` would assume the category label is always first —
        # Jobcan's label order is observation, not contract (same lesson
        # `search_index.py::build_search_index` already encodes).
        employment = [label for label in labels if label not in LABEL_TO_CATEGORY]

        records.append(
            {
                "id": snapshot.job_id,
                "title": list_item.title,
                "category": category,
                "employment": employment,
                "area": area,
                "facility": facility_core_name(address),
                "city": coords["city"] if coords else "",
                "service_types": _service_types_for(address, list_item.title),
                "url": f"jobs/{snapshot.job_id}",
            }
        )

    warnings: list[str] = []
    if missing_city_job_ids:
        warnings.append(f"no facility_coords match (no city) for job_ids: {missing_city_job_ids}")
    if uncategorized_job_ids:
        warnings.append(f"no category_key match for job_ids: {uncategorized_job_ids}")
    if unmatched_area_job_ids:
        warnings.append(f"no area match for job_ids: {unmatched_area_job_ids}")
    return records, warnings
