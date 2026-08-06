"""`job_cache/{job_id}` snapshot model (Phase B Firestore schema).

Schema per `docs/specs/sync-strategy.md` §6, plus one field that document
doesn't have yet: `absence_count` (連続不在カウンタ). closed 判定は「2回連続で
一覧に不在」で決まる(B-3)ため、1回の不在では消えない状態を Firestore 側に
保持する必要がある — この場は snapshot の schema であり実装は B-3 の担当。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .models import JobOffer

SyncStatus = Literal["active", "closed", "pending_review"]

# `normalized` は一覧・詳細ページの再描画に必要な最小限のフィールドのみを持つ。
# `body_html` を含めない理由: 差分検出は content_hash で足り、Firestore ドキュメント
# サイズを不必要に膨らませたくない(sync-strategy.md の設計意図を踏襲)。
_NORMALIZED_FIELDS = ("title", "address", "label", "location", "salary")


class JobSnapshot(BaseModel):
    """One `job_cache/{job_id}` document.

    `source` is always `"html_parse"` for Phase B (the only implemented
    ingestion path); the literal keeps the door open for the `"csv"` / `"api"`
    variants `sync-strategy.md` already documents as fallbacks, without this
    module having to know how to produce them.
    """

    job_id: str = Field(..., description="Jobcan job_offer ID (numeric string)")
    content_hash: str = Field(..., description="JobOffer.content_hash at last_seen_at")
    source_url: str
    apply_url: str
    last_seen_at: datetime = Field(..., description="When this snapshot was last confirmed present")
    source: Literal["html_parse", "csv", "api"] = "html_parse"
    normalized: dict[str, str] = Field(
        default_factory=dict, description="Subset of JobOffer fields needed to re-render a card"
    )
    sync_status: SyncStatus = "active"
    absence_count: int = Field(
        0, ge=0, description="Consecutive crawls where this job_id was absent from its listing"
    )
    closed_at: datetime | None = Field(
        None, description="When sync_status first flipped to closed (B-3); None while active"
    )

    model_config = {"frozen": True}


def snapshot_from_offer(
    offer: JobOffer,
    *,
    now: datetime,
    sync_status: SyncStatus = "active",
    absence_count: int = 0,
) -> JobSnapshot:
    """Build the Firestore-bound snapshot for a freshly-fetched `JobOffer`.

    A freshly-seen job resets `absence_count` to 0 and `closed_at` to `None`
    by default — a job_id that comes back after being closed (e.g. Jobcan
    re-publishes it) is treated as a fresh posting, not a resurrection of the
    old record. Callers doing the closed-job bookkeeping (B-3) pass an
    explicit `absence_count` only when constructing a snapshot for a job that
    was *not* re-fetched this run.
    """
    normalized = {field: getattr(offer, field) for field in _NORMALIZED_FIELDS}
    return JobSnapshot(
        job_id=offer.job_id,
        content_hash=offer.content_hash,
        normalized=normalized,
        source_url=offer.source_url,
        apply_url=offer.apply_url,
        last_seen_at=now,
        sync_status=sync_status,
        absence_count=absence_count,
        closed_at=None,
    )
