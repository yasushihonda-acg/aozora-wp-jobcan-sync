"""JobcanClient tests — Codex Q6 reflected (timeout / UA / retry / 4xx-5xx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from sync.jobcan_client import JOBCAN_BASE_URL, JobcanClient, JobcanClientConfig
from sync.models import JobcanClientError


def _client_no_sleep() -> JobcanClient:
    return JobcanClient(
        JobcanClientConfig(max_retries=2, retry_base_delay=0.0, crawl_delay=0.0)
    )


@respx.mock
def test_success_returns_html_and_url() -> None:
    job_id = "1777023"
    expected_url = f"{JOBCAN_BASE_URL}/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
    respx.get(expected_url).mock(return_value=httpx.Response(200, text="<html>ok</html>"))

    with _client_no_sleep() as client:
        url, html = client.fetch_job_detail(job_id)
    assert url == expected_url
    assert html == "<html>ok</html>"


@respx.mock
def test_user_agent_sent() -> None:
    job_id = "1777023"
    route = respx.get(f"{JOBCAN_BASE_URL}/job_offers/{job_id}").mock(
        return_value=httpx.Response(200, text="ok")
    )
    with _client_no_sleep() as client:
        client.fetch_job_detail(job_id)
    sent_ua = route.calls[0].request.headers["user-agent"]
    assert "AozoraJobcanSync" in sent_ua


@respx.mock
def test_404_raises_immediately_no_retry() -> None:
    job_id = "999999"
    route = respx.get(f"{JOBCAN_BASE_URL}/job_offers/{job_id}").mock(
        return_value=httpx.Response(404)
    )
    with _client_no_sleep() as client:
        with pytest.raises(JobcanClientError, match="HTTP 404"):
            client.fetch_job_detail(job_id)
    assert route.call_count == 1  # no retry on 4xx (other than 429)


@respx.mock
def test_429_retries_then_succeeds() -> None:
    job_id = "1777023"
    route = respx.get(f"{JOBCAN_BASE_URL}/job_offers/{job_id}").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, text="<html>ok</html>"),
        ]
    )
    with _client_no_sleep() as client:
        _, html = client.fetch_job_detail(job_id)
    assert html == "<html>ok</html>"
    assert route.call_count == 2


@respx.mock
def test_5xx_retries_then_gives_up() -> None:
    job_id = "1777023"
    respx.get(f"{JOBCAN_BASE_URL}/job_offers/{job_id}").mock(
        return_value=httpx.Response(503)
    )
    with _client_no_sleep() as client:
        with pytest.raises(JobcanClientError, match="HTTP 503"):
            client.fetch_job_detail(job_id)


# ============================================================
# Phase B — fetch_job_list(page=N)
# ============================================================


@respx.mock
def test_fetch_job_list_page_1_uses_unchanged_url() -> None:
    """page=1 (the default) must produce byte-identical URLs to the pre-Phase-B
    behaviour — existing callers (`app.py`, `cli.py`) never pass `page`."""
    expected_url = f"{JOBCAN_BASE_URL}/list?category_id=18773&hide_breadcrumb=true&hide_search=true"
    respx.get(expected_url).mock(return_value=httpx.Response(200, text="ok"))
    with _client_no_sleep() as client:
        url, _ = client.fetch_job_list("18773")
    assert url == expected_url


@respx.mock
def test_fetch_job_list_page_2_uses_path_segment_form() -> None:
    """Page 2+ uses `/list/all/all/{page}?category_id=`, not `?page=N` —
    confirmed against the real `rel="last"` links in the fixtures."""
    expected_url = (
        f"{JOBCAN_BASE_URL}/list/all/all/2"
        "?category_id=18773&hide_breadcrumb=true&hide_search=true"
    )
    respx.get(expected_url).mock(return_value=httpx.Response(200, text="ok"))
    with _client_no_sleep() as client:
        url, _ = client.fetch_job_list("18773", page=2)
    assert url == expected_url


@respx.mock
def test_crawl_delay_waits_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two requests on the same client must be spaced >= crawl_delay apart."""
    respx.get(f"{JOBCAN_BASE_URL}/job_offers/1").mock(return_value=httpx.Response(200, text="ok"))
    respx.get(f"{JOBCAN_BASE_URL}/job_offers/2").mock(return_value=httpx.Response(200, text="ok"))

    sleeps: list[float] = []
    monkeypatch.setattr(
        "sync.jobcan_client.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    client = JobcanClient(
        JobcanClientConfig(max_retries=0, retry_base_delay=0.0, crawl_delay=3.0)
    )
    with client:
        client.fetch_job_detail("1")
        client.fetch_job_detail("2")

    # First request never waits (no prior request this run); the second must.
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(3.0, abs=0.1)


@respx.mock
def test_crawl_delay_zero_never_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    respx.get(f"{JOBCAN_BASE_URL}/job_offers/1").mock(return_value=httpx.Response(200, text="ok"))
    respx.get(f"{JOBCAN_BASE_URL}/job_offers/2").mock(return_value=httpx.Response(200, text="ok"))

    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "sync.jobcan_client.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )

    with _client_no_sleep() as client:
        client.fetch_job_detail("1")
        client.fetch_job_detail("2")

    assert sleep_calls == []
