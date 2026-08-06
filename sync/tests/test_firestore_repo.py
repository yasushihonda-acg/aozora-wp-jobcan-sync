"""`JobCacheRepository` tests against a fake Firestore client.

No real Firestore / emulator connection here — the fake below models just
enough of the `google-cloud-firestore` surface (`collection().document(id).set()`,
`collection().stream()`, `client.batch()`) to exercise `JobCacheRepository`'s
own translation logic (dict <-> JobSnapshot, date safety, batching). True
wire-level behaviour against a live Firestore emulator is the plan's separate
manual verification step, not this file's job.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sync.firestore_repo import JobCacheRepository, _convert_dates_to_datetimes
from sync.snapshot import JobSnapshot


class _FakeDocSnapshot:
    def __init__(self, doc_id: str, data: dict) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class _FakeDocRef:
    def __init__(self, store: dict, doc_id: str) -> None:
        self._store = store
        self.id = doc_id

    def set(self, data: dict) -> None:
        self._store[self.id] = data


class _FakeCollection:
    def __init__(self, store: dict) -> None:
        self._store = store

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, doc_id)

    def stream(self) -> list[_FakeDocSnapshot]:
        return [_FakeDocSnapshot(doc_id, data) for doc_id, data in self._store.items()]


class _FakeBatch:
    def __init__(self, store: dict) -> None:
        self._store = store
        self._pending: list[tuple[str, dict]] = []

    def set(self, doc_ref: _FakeDocRef, data: dict) -> None:
        self._pending.append((doc_ref.id, data))

    def commit(self) -> None:
        for doc_id, data in self._pending:
            self._store[doc_id] = data


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    def collection(self, *collection_path: str) -> _FakeCollection:
        assert collection_path == ("job_cache",)
        return _FakeCollection(self.store)

    def batch(self) -> _FakeBatch:
        return _FakeBatch(self.store)


def _snapshot(job_id: str, *, last_seen_at: datetime | None = None) -> JobSnapshot:
    # absence_count passed explicitly (even though JobSnapshot defaults it to
    # 0) — a pyright/pydantic interaction quirk already present in this
    # codebase's baseline (see test_app.py's identical "page_title missing"
    # false positive on JobOffer) flags Field()-defaulted params as required
    # when omitted from a call site.
    return JobSnapshot(
        job_id=job_id,
        content_hash="x" * 64,
        normalized={"title": f"求人 {job_id}"},
        source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        last_seen_at=last_seen_at or datetime(2026, 8, 7, tzinfo=UTC),
        absence_count=0,
        closed_at=None,
    )


def test_set_then_get_all_round_trips_a_single_snapshot() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)

    repo.set(_snapshot("1"))
    result = repo.get_all()

    assert set(result) == {"1"}
    assert result["1"].job_id == "1"
    assert result["1"].sync_status == "active"


def test_get_all_on_empty_collection_returns_empty_dict() -> None:
    repo = JobCacheRepository(_FakeFirestoreClient())
    assert repo.get_all() == {}


def test_set_many_writes_every_snapshot() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)

    repo.set_many([_snapshot("1"), _snapshot("2"), _snapshot("3")])

    assert set(repo.get_all()) == {"1", "2", "3"}


def test_set_many_chunks_at_batch_limit(monkeypatch) -> None:
    """501 snapshots must trigger 2 separate `client.batch()` calls, not 1."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    batch_calls = []
    original_batch = client.batch

    def _counting_batch():
        batch_calls.append(1)
        return original_batch()

    monkeypatch.setattr(client, "batch", _counting_batch)

    snapshots = [_snapshot(str(i)) for i in range(501)]
    repo.set_many(snapshots)

    assert len(batch_calls) == 2
    assert len(repo.get_all()) == 501


def test_set_overwrites_existing_snapshot_for_same_job_id() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)

    repo.set(_snapshot("1", last_seen_at=datetime(2026, 8, 6, tzinfo=UTC)))
    repo.set(_snapshot("1", last_seen_at=datetime(2026, 8, 7, tzinfo=UTC)))

    result = repo.get_all()
    assert len(result) == 1
    assert result["1"].last_seen_at == datetime(2026, 8, 7, tzinfo=UTC)


def test_convert_dates_to_datetimes_converts_bare_date_to_midnight_utc() -> None:
    """The ported aozora-sns-auto pitfall guard: a bare `date` must become a
    `datetime` at UTC midnight, not raise or pass through unchanged."""
    converted = _convert_dates_to_datetimes({"closed_at": date(2026, 8, 7)})
    assert converted == {"closed_at": datetime(2026, 8, 7, tzinfo=UTC)}


def test_convert_dates_to_datetimes_leaves_real_datetimes_untouched() -> None:
    """`datetime` is a subclass of `date` — must not be double-converted or dropped."""
    original = datetime(2026, 8, 7, 3, 30, tzinfo=UTC)
    converted = _convert_dates_to_datetimes({"last_seen_at": original})
    assert converted == {"last_seen_at": original}


def test_convert_dates_to_datetimes_recurses_into_nested_lists_and_dicts() -> None:
    payload = {"outer": [{"inner_date": date(2026, 1, 1)}, "unrelated"]}
    converted = _convert_dates_to_datetimes(payload)
    assert converted == {"outer": [{"inner_date": datetime(2026, 1, 1, tzinfo=UTC)}, "unrelated"]}
