"""Crawl orchestrator tests (Phase B: `crawl_all`).

Uses small hand-built HTML fixtures (not the real 4-category fixtures used by
`test_parser.py`) because these tests exercise *orchestration* — de-dup,
partial-failure continuation, pagination walking, total-count reconciliation
— not selector correctness. Real-fixture parsing correctness is already
covered by `test_parser.py`.
"""

from __future__ import annotations

import httpx
import respx

from sync.crawler import CrawlResult, crawl_all
from sync.jobcan_client import JOBCAN_BASE_URL, JobcanClient, JobcanClientConfig


def _client() -> JobcanClient:
    return JobcanClient(
        JobcanClientConfig(max_retries=0, retry_base_delay=0.0, crawl_delay=0.0)
    )


def _list_html(*, job_ids: list[str], total_count: int | None, last_page: int) -> str:
    """Minimal valid `.job-offer-box` list page with optional pagination block."""
    cards = "".join(
        f"""
        <div class="job-offer-box">
          <h2 class="job-offer-title">求人 {jid}</h2>
          <a class="job-offer-title" href="/aozora/job_offers/{jid}?hide_breadcrumb=false">
            求人 {jid}
          </a>
        </div>
        """
        for jid in job_ids
    )
    pagination = ""
    if total_count is not None:
        count_text = (
            f"{total_count}&nbsp;件中&nbsp;1-10&nbsp;件を表示"
            if last_page > 1
            else f"{total_count}&nbsp;件"
        )
        last_link = (
            f'<a rel="last" href="/aozora/list/all/all/{last_page}?category_id=X">last</a>'
            if last_page > 1
            else ""
        )
        pagination = f"""
        <div class="pagination-area">
          <div class="pagination-number">{count_text}</div>
          {last_link}
        </div>
        """
    return f"<html><body>{pagination}{cards}</body></html>"


def _detail_html(job_id: str) -> str:
    """Minimal valid detail page — every field required by `parse_job_detail`."""
    return f"""
    <html><body>
      <div class="job-offer-detail-title">求人 {job_id}</div>
      <div class="job-offer-description-full">本文 {job_id}</div>
      <div class="job-offer-address">拠点 {job_id}</div>
      <div class="job-offer-label">介護職 正社員</div>
      <a href="/aozora/entry/new/{job_id}">apply</a>
      <div class="job-offer-table">
        <div class="content-table-line">
          <div class="content-table-head">勤務地</div>
          <div class="td-contentTable__breakWordWrap">福岡</div>
        </div>
        <div class="content-table-line">
          <div class="content-table-head">給与</div>
          <div class="td-contentTable__breakWordWrap">¥250,000</div>
        </div>
      </div>
    </body></html>
    """


def _mock_list_page(category_id: str, page: int, html: str) -> None:
    if page <= 1:
        url = (
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        )
    else:
        url = (
            f"{JOBCAN_BASE_URL}/list/all/all/{page}"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        )
    respx.get(url).mock(return_value=httpx.Response(200, text=html))


def _mock_detail(job_id: str, *, status_code: int = 200) -> None:
    url = f"{JOBCAN_BASE_URL}/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
    if status_code == 200:
        respx.get(url).mock(return_value=httpx.Response(200, text=_detail_html(job_id)))
    else:
        respx.get(url).mock(return_value=httpx.Response(status_code))


@respx.mock
def test_crawl_all_collects_every_job_across_categories() -> None:
    _mock_list_page("A", 1, _list_html(job_ids=["1"], total_count=1, last_page=1))
    _mock_list_page("B", 1, _list_html(job_ids=["2"], total_count=1, last_page=1))
    _mock_detail("1")
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A", "B"))

    assert {o.job_id for o in result.offers} == {"1", "2"}
    assert result.errors == []


@respx.mock
def test_crawl_all_dedupes_job_id_seen_in_two_categories() -> None:
    """job_id 1 appears in both category A and category B's listing — the
    detail page must be fetched exactly once, not twice."""
    _mock_list_page("A", 1, _list_html(job_ids=["1"], total_count=1, last_page=1))
    _mock_list_page("B", 1, _list_html(job_ids=["1"], total_count=1, last_page=1))
    route = respx.get(
        f"{JOBCAN_BASE_URL}/job_offers/1?hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(200, text=_detail_html("1")))

    with _client() as client:
        result = crawl_all(client, category_ids=("A", "B"))

    assert len(result.offers) == 1
    assert route.call_count == 1


@respx.mock
def test_crawl_all_walks_multi_page_category() -> None:
    _mock_list_page("A", 1, _list_html(job_ids=["1"], total_count=2, last_page=2))
    _mock_list_page("A", 2, _list_html(job_ids=["2"], total_count=None, last_page=1))
    _mock_detail("1")
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A",))

    assert {o.job_id for o in result.offers} == {"1", "2"}
    assert result.expected_total == 2


@respx.mock
def test_crawl_all_continues_after_one_category_fails() -> None:
    """Category A's page 1 500s; category B must still be crawled."""
    respx.get(
        f"{JOBCAN_BASE_URL}/list?category_id=A&hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))
    _mock_list_page("B", 1, _list_html(job_ids=["2"], total_count=1, last_page=1))
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A", "B"))

    assert {o.job_id for o in result.offers} == {"2"}
    assert any(e.get("category_id") == "A" for e in result.errors)


@respx.mock
def test_crawl_all_continues_after_one_detail_fetch_fails() -> None:
    """job_id 1's detail 404s; job_id 2 in the same category must still be collected."""
    _mock_list_page("A", 1, _list_html(job_ids=["1", "2"], total_count=2, last_page=1))
    _mock_detail("1", status_code=404)
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A",))

    assert {o.job_id for o in result.offers} == {"2"}
    assert any(e.get("job_id") == "1" for e in result.errors)
    # job_id 1 was still *listed* even though its detail fetch failed — this
    # is what lets diff.py distinguish "fetch failed" from "gone from the
    # listing" (P1 codex finding).
    assert result.listed_job_ids == {"1", "2"}
    assert result.fully_listed is True


@respx.mock
def test_crawl_all_fully_listed_false_when_category_page_1_fails() -> None:
    respx.get(
        f"{JOBCAN_BASE_URL}/list?category_id=A&hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))

    with _client() as client:
        result = crawl_all(client, category_ids=("A",))

    assert result.fully_listed is False
    assert result.listed_job_ids == set()


@respx.mock
def test_crawl_all_fully_listed_false_when_a_later_page_fails() -> None:
    _mock_list_page("A", 1, _list_html(job_ids=["1"], total_count=2, last_page=2))
    respx.get(
        f"{JOBCAN_BASE_URL}/list/all/all/2?category_id=A&hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))
    _mock_detail("1")

    with _client() as client:
        result = crawl_all(client, category_ids=("A",))

    assert result.fully_listed is False
    # Page 1's job_id is still legitimately listed — only the missing page 2
    # is unknown, not page 1's contents.
    assert result.listed_job_ids == {"1"}


@respx.mock
def test_crawl_all_fully_listed_true_when_every_category_succeeds() -> None:
    _mock_list_page("A", 1, _list_html(job_ids=["1"], total_count=1, last_page=1))
    _mock_list_page("B", 1, _list_html(job_ids=["2"], total_count=1, last_page=1))
    _mock_detail("1")
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A", "B"))

    assert result.fully_listed is True
    assert result.listed_job_ids == {"1", "2"}


@respx.mock
def test_crawl_all_reconciliation_counts_match_on_full_success() -> None:
    _mock_list_page("A", 1, _list_html(job_ids=["1", "2"], total_count=2, last_page=1))
    _mock_detail("1")
    _mock_detail("2")

    with _client() as client:
        result = crawl_all(client, category_ids=("A",))

    assert result.expected_total == 2
    assert result.collected_total == 2


def test_crawl_result_defaults_are_empty() -> None:
    result = CrawlResult()
    assert result.offers == []
    assert result.errors == []
    assert result.expected_total == 0
    assert result.collected_total == 0
    assert result.listed_job_ids == set()
    assert result.fully_listed is True
