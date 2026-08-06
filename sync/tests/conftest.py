"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobcan_responses"
SAMPLE_JOB_ID = "1777023"
SAMPLE_SOURCE_URL = (
    f"https://recruit.jobcan.jp/aozora/job_offers/{SAMPLE_JOB_ID}"
    "?hide_breadcrumb=true&hide_search=true"
)


@pytest.fixture
def sample_html() -> str:
    return (FIXTURES_DIR / f"job_{SAMPLE_JOB_ID}.html").read_text(encoding="utf-8")


@pytest.fixture
def broken_html() -> str:
    return (FIXTURES_DIR / "job_broken.html").read_text(encoding="utf-8")


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
        self._pending: list[tuple[str, dict | None]] = []

    def set(self, doc_ref: _FakeDocRef, data: dict) -> None:
        self._pending.append((doc_ref.id, data))

    def delete(self, doc_ref: _FakeDocRef) -> None:
        self._pending.append((doc_ref.id, None))

    def commit(self) -> None:
        for doc_id, data in self._pending:
            if data is None:
                self._store.pop(doc_id, None)
            else:
                self._store[doc_id] = data


class FakeFirestoreClient:
    """Minimal in-memory double for `firestore.Client` — models just enough
    of the SDK surface (`collection().document(id).set()/.stream()`,
    `client.batch()`) for `JobCacheRepository` and its callers to run against
    without a live Firestore / emulator connection. Shared by
    `test_firestore_repo.py`, `test_orchestrator.py`, and `test_cli.py`."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    def collection(self, *collection_path: str) -> _FakeCollection:
        # Variadic to structurally match `firestore.Client.collection`
        # (`*collection_path: str`) — `JobCacheRepository` is typed against
        # that shape via `_FirestoreClientLike`, so a fixed single-arg
        # signature here would make pyright reject this fake.
        assert collection_path == ("job_cache",)
        return _FakeCollection(self.store)

    def batch(self) -> _FakeBatch:
        return _FakeBatch(self.store)
