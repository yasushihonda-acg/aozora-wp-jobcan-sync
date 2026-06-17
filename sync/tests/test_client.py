"""JobcanClient tests — Codex Q6 reflected (timeout / UA / retry / 4xx-5xx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from sync.jobcan_client import JOBCAN_BASE_URL, JobcanClient, JobcanClientConfig
from sync.models import JobcanClientError


def _client_no_sleep() -> JobcanClient:
    return JobcanClient(JobcanClientConfig(max_retries=2, retry_base_delay=0.0))


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
