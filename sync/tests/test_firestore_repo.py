"""`JobCacheRepository` tests against a fake Firestore client.

No real Firestore / emulator connection here — `FakeFirestoreClient`
(conftest.py, shared with test_orchestrator.py and test_cli.py) models just
enough of the `google-cloud-firestore` surface (`collection().document(id).set()`,
`collection().stream()`, `client.batch()`) to exercise `JobCacheRepository`'s
own translation logic (dict <-> JobSnapshot, date safety, batching). True
wire-level behaviour against a live Firestore emulator is the plan's separate
manual verification step, not this file's job.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from sync.firestore_repo import JobCacheRepository, _convert_dates_to_datetimes
from sync.models import JobOffer
from sync.snapshot import JobSnapshot
from tests.conftest import FakeFirestoreClient as _FakeFirestoreClient


def _offer(job_id: str) -> JobOffer:
    return JobOffer(
        job_id=job_id,
        title=f"求人 {job_id}",
        body_html="<p>本文</p>",
        address="福岡事業所",
        label="介護職 正社員",
        location="福岡県福岡市",
        salary="¥250,000",
        apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        page_title=None,
    )


def _snapshot(job_id: str, *, last_seen_at: datetime | None = None) -> JobSnapshot:
    # absence_count passed explicitly (even though JobSnapshot defaults it to
    # 0) — a pyright/pydantic interaction quirk already present in this
    # codebase's baseline (see test_app.py's identical "page_title missing"
    # false positive on JobOffer) flags Field()-defaulted params as required
    # when omitted from a call site.
    offer = _offer(job_id)
    return JobSnapshot(
        job_id=job_id,
        content_hash="x" * 64,
        offer=offer,
        list_item=None,
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


def test_set_encodes_extra_lines_as_maps_not_nested_arrays() -> None:
    """Firestore rejects an array nested directly inside another array.
    `JobOffer.extra_lines` is `list[tuple[str, str]]`, so the stored dict
    must NOT contain a bare tuple/list inside `offer.extra_lines` — each
    pair must be wrapped in a map (dict) instead (2026-08-07 production
    incident: first real `sync-run` failed with `InvalidArgument: 400
    Property offer contains an invalid nested entity`)."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    extra_lines = [("福利厚生", "社会保険完備"), ("休日", "週休2日")]
    offer = _offer("1").model_copy(update={"extra_lines": extra_lines})
    snapshot = _snapshot("1").model_copy(update={"offer": offer})

    repo.set(snapshot)

    stored_extra_lines = client.store["1"]["offer"]["extra_lines"]
    assert stored_extra_lines == [
        {"header": "福利厚生", "value": "社会保険完備"},
        {"header": "休日", "value": "週休2日"},
    ]
    assert all(isinstance(item, dict) for item in stored_extra_lines)


def test_set_then_get_all_round_trips_extra_lines_back_to_tuples() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    offer = _offer("1").model_copy(update={"extra_lines": [("福利厚生", "社会保険完備")]})
    snapshot = _snapshot("1").model_copy(update={"offer": offer})

    repo.set(snapshot)
    result = repo.get_all()

    assert result["1"].offer.extra_lines == [("福利厚生", "社会保険完備")]


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


def test_set_many_exactly_at_batch_limit_is_a_single_batch(monkeypatch) -> None:
    """Exactly 500 snapshots must stay a single `client.batch()` call."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    batch_calls = []
    original_batch = client.batch

    def _counting_batch():
        batch_calls.append(1)
        return original_batch()

    monkeypatch.setattr(client, "batch", _counting_batch)

    snapshots = [_snapshot(str(i)) for i in range(500)]
    repo.set_many(snapshots)

    assert len(batch_calls) == 1
    assert len(repo.get_all()) == 500


def test_delete_many_removes_specified_snapshots() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1"), _snapshot("2"), _snapshot("3")])

    repo.delete_many(["1", "3"])

    assert set(repo.get_all()) == {"2"}


def test_delete_many_on_empty_list_is_a_no_op() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1")])

    repo.delete_many([])

    assert set(repo.get_all()) == {"1"}


def test_delete_many_ignores_nonexistent_job_ids() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1")])

    repo.delete_many(["does-not-exist"])

    assert set(repo.get_all()) == {"1"}


def test_delete_many_chunks_at_batch_limit(monkeypatch) -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot(str(i)) for i in range(501)])
    batch_calls = []
    original_batch = client.batch

    def _counting_batch():
        batch_calls.append(1)
        return original_batch()

    monkeypatch.setattr(client, "batch", _counting_batch)

    repo.delete_many([str(i) for i in range(501)])

    assert len(batch_calls) == 2
    assert repo.get_all() == {}


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


def test_get_returns_the_matching_snapshot() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1"), _snapshot("2")])

    result = repo.get("1")

    assert result is not None
    assert result.job_id == "1"


def test_get_returns_none_for_missing_job_id() -> None:
    repo = JobCacheRepository(_FakeFirestoreClient())
    assert repo.get("nonexistent") is None


def test_get_all_raises_on_a_single_malformed_doc() -> None:
    """The sync path (`orchestrator.run_sync`) must fail loudly rather than
    silently narrow its `previous_snapshots` baseline (see get_all()'s
    docstring for why a dropped doc would corrupt closed-rate accounting)."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set(_snapshot("1"))
    client.store["bad"] = {"job_id": "bad"}  # missing every other required field

    with pytest.raises(ValidationError):
        repo.get_all()


def test_get_all_valid_skips_a_malformed_doc_and_reports_it() -> None:
    """The serving path (`app.py`'s category listing) must not let one bad
    document take down every category's listing page."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1"), _snapshot("2")])
    client.store["bad"] = {"job_id": "bad"}

    snapshots, skipped = repo.get_all_valid()

    assert set(snapshots) == {"1", "2"}
    assert skipped == ["bad"]


def test_get_all_valid_on_a_fully_valid_collection_skips_nothing() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many([_snapshot("1"), _snapshot("2")])

    snapshots, skipped = repo.get_all_valid()

    assert set(snapshots) == {"1", "2"}
    assert skipped == []


# ─────────────────────────── get_by_category ──────────────────────────────
# Stage 2 (job-detail design parity, 2026-08-08) — the "related jobs" sidebar.


def test_get_by_category_returns_only_matching_active_snapshots() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many(
        [
            _snapshot("1").model_copy(update={"category_ids": ["18773"]}),
            _snapshot("2").model_copy(update={"category_ids": ["58859"]}),  # different category
            _snapshot("3").model_copy(
                update={"category_ids": ["18773", "58859"]}
            ),  # multi-category, still matches
        ]
    )

    result = repo.get_by_category("18773")

    assert {s.job_id for s in result} == {"1", "3"}


def test_get_by_category_excludes_non_active_snapshots() -> None:
    """The sidebar must not link to a closed/pending posting — filtered in
    Python after the query (Firestore's `array_contains` query can't also
    filter on `sync_status` without a composite index, see the method's
    docstring)."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set_many(
        [
            _snapshot("1").model_copy(
                update={"category_ids": ["18773"], "sync_status": "active"}
            ),
            _snapshot("2").model_copy(
                update={"category_ids": ["18773"], "sync_status": "closed"}
            ),
            _snapshot("3").model_copy(
                update={"category_ids": ["18773"], "sync_status": "pending_review"}
            ),
        ]
    )

    result = repo.get_by_category("18773")

    assert {s.job_id for s in result} == {"1"}


def test_get_by_category_no_match_returns_empty_list() -> None:
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set(_snapshot("1").model_copy(update={"category_ids": ["58859"]}))

    assert repo.get_by_category("18773") == []


def test_get_by_category_skips_a_malformed_doc_and_keeps_the_rest() -> None:
    """Same lenient-skip posture as `get_all_valid()` — one bad document
    must not take down the sidebar for every other posting in the category."""
    client = _FakeFirestoreClient()
    repo = JobCacheRepository(client)
    repo.set(_snapshot("1").model_copy(update={"category_ids": ["18773"]}))
    client.store["bad"] = {"job_id": "bad", "category_ids": ["18773"]}

    result = repo.get_by_category("18773")

    assert {s.job_id for s in result} == {"1"}
