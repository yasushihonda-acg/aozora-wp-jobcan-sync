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


def compute_diff(
    current_offers: list[JobOffer],
    previous_snapshots: dict[str, JobSnapshot],
) -> DiffResult:
    """Classify every current offer against the previous snapshot set.

    `changed` is decided by `content_hash` equality, not field-by-field
    comparison — the hash already covers every normalised field, so a single
    comparison catches any change without this module having to know which
    fields matter.
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

    removed = [
        snapshot
        for job_id, snapshot in previous_snapshots.items()
        if job_id not in current_ids
    ]

    return DiffResult(added=added, changed=changed, unchanged=unchanged, removed=removed)
