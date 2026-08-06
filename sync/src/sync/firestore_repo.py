"""Firestore repository for `job_cache/{job_id}` (Phase B periodic sync).

Deliberately thin: this module only knows how to read/write the collection.
Diff classification (`diff.py`) and closed-job bookkeeping (B-3) stay separate
so they're testable without a Firestore client at all.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time
from functools import lru_cache
from typing import Any, Protocol

from google.cloud import firestore

from .snapshot import JobSnapshot

_COLLECTION = "job_cache"


class _FirestoreClientLike(Protocol):
    """The subset of `firestore.Client` this module actually calls.

    `JobCacheRepository` is typed against this instead of the concrete SDK
    class so tests can pass a lightweight fake (see `test_firestore_repo.py`)
    without pyright flagging it as an incompatible type — the fake only needs
    to structurally match `collection()` / `batch()`, not subclass the SDK.
    """

    # `*collection_path` (not a single `name` param) to match the real SDK's
    # variadic signature (`firestore.Client.collection(*collection_path: str)`)
    # — a fixed single-positional-arg Protocol method isn't structurally
    # assignable from that, and pyright flags real `firestore.Client` as
    # incompatible with this Protocol otherwise.
    def collection(self, *collection_path: str) -> Any: ...
    def batch(self) -> Any: ...

# Firestore batched writes cap at 500 mutations; documented here rather than
# discovered at runtime via a 3xx/4xx from the SDK.
_BATCH_LIMIT = 500


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    """Build (and cache) the Firestore client for this process.

    Project / database come from env vars, matching the `--set-env-vars`
    Cloud Run deployment convention already used by this repo
    (`infra/README.md` §4) — no dedicated settings module for two values.
    """
    project = os.environ.get("GCP_PROJECT_ID", "aozora-wp-jobcan-sync")
    database = os.environ.get("FIRESTORE_DATABASE", "(default)")
    return firestore.Client(project=project, database=database)


def _convert_dates_to_datetimes(obj: Any) -> Any:
    """Recursively convert bare `datetime.date` to `datetime.datetime` (UTC 00:00).

    Ported from `aozora-sns-auto`'s known pitfall
    (`packages/core/src/aozora_core/firestore/repositories.py`): the Firestore
    SDK's `encode_value` accepts `datetime.datetime` as a Timestamp but raises
    `TypeError` on a bare `datetime.date`. No `JobSnapshot` field is a bare
    `date` today, but every field added later inherits this safety net
    automatically instead of relying on the next author to remember the trap.

    `datetime` is a subclass of `date`, so it's excluded explicitly.
    """
    if isinstance(obj, dict):
        return {key: _convert_dates_to_datetimes(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_convert_dates_to_datetimes(value) for value in obj]
    if isinstance(obj, date) and not isinstance(obj, datetime):
        return datetime.combine(obj, time.min, tzinfo=UTC)
    return obj


def _to_dict(snapshot: JobSnapshot) -> dict[str, Any]:
    """`JobSnapshot` -> Firestore-writable dict."""
    return _convert_dates_to_datetimes(snapshot.model_dump(mode="python"))


class JobCacheRepository:
    """Read/write wrapper around the `job_cache` collection.

    Takes an injected `firestore.Client` rather than always calling
    `get_firestore_client()` internally, so tests can pass a fake client
    without a live emulator connection.
    """

    def __init__(self, client: _FirestoreClientLike) -> None:
        self._client = client
        self._collection = client.collection(_COLLECTION)

    def get_all(self) -> dict[str, JobSnapshot]:
        """Read every existing snapshot, keyed by job_id."""
        snapshots: dict[str, JobSnapshot] = {}
        for doc in self._collection.stream():
            data = doc.to_dict() or {}
            snapshots[doc.id] = JobSnapshot.model_validate(data)
        return snapshots

    def set(self, snapshot: JobSnapshot) -> None:
        self._collection.document(snapshot.job_id).set(_to_dict(snapshot))

    def set_many(self, snapshots: list[JobSnapshot]) -> None:
        """Batched write, chunked at Firestore's 500-mutation limit per batch."""
        for start in range(0, len(snapshots), _BATCH_LIMIT):
            chunk = snapshots[start : start + _BATCH_LIMIT]
            batch = self._client.batch()
            for snapshot in chunk:
                batch.set(self._collection.document(snapshot.job_id), _to_dict(snapshot))
            batch.commit()
