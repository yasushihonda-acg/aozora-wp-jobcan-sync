"""`job_cache/{job_id}` snapshot model (Phase B Firestore schema).

Schema per `docs/specs/sync-strategy.md` §6, plus fields that document
doesn't have yet: `absence_count`/`first_absent_at` (不在ブックキーピング, B-3)
and `offer`/`list_item`/`category_ids` (B-8, 配信層統合). closed 判定は「一覧
から最初に不在を観測してから 48 時間経過」で決まる(B-3、2026-08-08 のクロール
6 時間ごと化に合わせて実行回数ベースから時間ベースへ変更)ため、1回の不在では
消えない状態を Firestore 側に保持する必要がある。B-8 で `normalized:
dict[str,str]` を `offer: JobOffer` に置き換えたのは、配信層 (`app.py`) が
詳細ページを再描画するのに `body_html`/`extra_lines`/`page_title` が必要だが、
旧 `normalized` はこれらを意図的に持たなかったため(コメント参照、差分検出は
content_hash で足りるので Firestore ドキュメントを膨らませたくない、という
判断)。B-8 実装時点で `job_cache` は本番に一件も書かれていなかったが、
2026-08-07 のローカル初回同期で投入済み(全件 `first_absent_at` 未設定 =
`None`、pydantic のデフォルト値埋めにより既存ドキュメントも問題なく読める)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .models import JobListItem, JobOffer

SyncStatus = Literal["active", "closed", "pending_review"]


class JobSnapshot(BaseModel):
    """One `job_cache/{job_id}` document.

    `source` is always `"html_parse"` for Phase B (the only implemented
    ingestion path); the literal keeps the door open for the `"csv"` / `"api"`
    variants `sync-strategy.md` already documents as fallbacks, without this
    module having to know how to produce them.

    `offer` carries everything `render_job_detail` needs to re-render the
    detail page without ever touching Jobcan again (B-8). `list_item` is the
    listing-card view of the same posting (`description`/`labels`/
    `thumbnail_url` — fields `JobOffer` doesn't have) and is `None` only for
    snapshots built outside a full catalogue crawl (defensive; every real
    `crawl_all()` job_id has one). `category_ids` is every category this
    job_id was seen under this run — a posting can legitimately appear in
    more than one category (crawler.py dedups job_ids across categories but
    keeps every category association), which is what `GET /jobs/?category_id=`
    filters on.
    """

    job_id: str = Field(..., description="Jobcan job_offer ID (numeric string)")
    content_hash: str = Field(..., description="JobOffer.content_hash at last_seen_at")
    source_url: str
    apply_url: str
    last_seen_at: datetime = Field(..., description="When this snapshot was last confirmed present")
    source: Literal["html_parse", "csv", "api"] = "html_parse"
    offer: JobOffer = Field(..., description="Full posting content, for detail-page re-rendering")
    list_item: JobListItem | None = Field(
        None, description="Listing-card view of this posting (description/labels/thumbnail)"
    )
    category_ids: list[str] = Field(
        default_factory=list, description="Every category_id this job_id was listed under"
    )
    sync_status: SyncStatus = "active"
    absence_count: int = Field(
        0, ge=0, description="Consecutive crawls where this job_id was absent from its listing"
    )
    first_absent_at: datetime | None = Field(
        default=None,
        description=(
            "When this job_id was FIRST observed absent from its listing "
            "(a genuine removal, not an unfetched detail page); None while present. "
            "Closed detection requires 48h elapsed since this timestamp (B-3)."
        ),
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
    list_item: JobListItem | None = None,
    category_ids: list[str] | None = None,
) -> JobSnapshot:
    """Build the Firestore-bound snapshot for a freshly-fetched `JobOffer`.

    A freshly-seen job resets `absence_count` to 0 and `closed_at` to `None`
    by default — a job_id that comes back after being closed (e.g. Jobcan
    re-publishes it) is treated as a fresh posting, not a resurrection of the
    old record. Callers doing the closed-job bookkeeping (B-3) pass an
    explicit `absence_count` only when constructing a snapshot for a job that
    was *not* re-fetched this run.
    """
    return JobSnapshot(
        job_id=offer.job_id,
        content_hash=offer.content_hash,
        offer=offer,
        list_item=list_item,
        category_ids=list(category_ids) if category_ids else [],
        source_url=offer.source_url,
        apply_url=offer.apply_url,
        last_seen_at=now,
        sync_status=sync_status,
        absence_count=absence_count,
        closed_at=None,
    )
