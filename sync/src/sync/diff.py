"""Diff detection: this crawl's `JobOffer`s vs. the previous `job_cache` snapshot.

Deliberately pure / I/O-free (no Firestore import here) so the classification
logic is unit-testable without an emulator — `firestore_repo.py` supplies the
`previous_snapshots` dict, this module only compares.

Closed-job bookkeeping (2 回連続不在で closed 化、closed率サーキットブレーカー)
is *not* this module's job — that's B-3. This module only answers "what
changed since last time," which B-3 then interprets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import JobOffer
from .snapshot import JobSnapshot


@dataclass(frozen=True)
class DiffResult:
    added: list[JobOffer] = field(default_factory=list)
    changed: list[JobOffer] = field(default_factory=list)
    unchanged: list[JobOffer] = field(default_factory=list)
    # `removed` holds the *previous* snapshot (not a JobOffer — we have no
    # fresh data for a job that vanished from its listing this run).
    removed: list[JobSnapshot] = field(default_factory=list)
    # A job_id that WAS seen in a listing this run (so it's still posted) but
    # whose detail fetch failed — distinct from `removed` on purpose. Codex
    # review flagged the original version of this module for conflating the
    # two: a detail-fetch failure is not evidence a posting disappeared, and
    # letting it fall into `removed` would let two unlucky fetch failures in
    # a row incorrectly close a still-live posting.
    unfetched: list[JobSnapshot] = field(default_factory=list)


def compute_diff(
    current_offers: list[JobOffer],
    previous_snapshots: dict[str, JobSnapshot],
    *,
    listed_job_ids: frozenset[str] = frozenset(),
) -> DiffResult:
    """Classify every current offer against the previous snapshot set.

    `changed` is decided by `content_hash` equality, not field-by-field
    comparison — the hash already covers every normalised field, so a single
    comparison catches any change without this module having to know which
    fields matter.

    `listed_job_ids` (from `crawler.CrawlResult.listed_job_ids`) is every
    job_id actually seen in a listing this run, independent of whether its
    detail fetch succeeded. A previously-known job_id missing from
    `current_offers` is `unfetched` (still listed, just not re-fetched) when
    it's in `listed_job_ids`, and only `removed` when it isn't — i.e. its
    listing genuinely no longer mentions it. Omitting `listed_job_ids`
    (the default) preserves the old behaviour of treating every absence as
    `removed`, for callers that don't have crawl-level listing data (e.g.
    unit tests exercising pure diff classification).
    """
    current_ids = {offer.job_id for offer in current_offers}
    added: list[JobOffer] = []
    changed: list[JobOffer] = []
    unchanged: list[JobOffer] = []

    for offer in current_offers:
        previous = previous_snapshots.get(offer.job_id)
        if previous is None:
            added.append(offer)
        elif previous.content_hash != offer.content_hash:
            changed.append(offer)
        else:
            unchanged.append(offer)

    removed: list[JobSnapshot] = []
    unfetched: list[JobSnapshot] = []
    for job_id, snapshot in previous_snapshots.items():
        if job_id in current_ids:
            continue
        if job_id in listed_job_ids:
            unfetched.append(snapshot)
        else:
            removed.append(snapshot)

    return DiffResult(
        added=added, changed=changed, unchanged=unchanged, removed=removed, unfetched=unfetched
    )
