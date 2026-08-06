"""HTTP client for fetching Jobcan public pages.

Codex review reflected:
- Explicit timeout (no infinite hang)
- Explicit User-Agent (identifies traffic, avoids generic-python-client blocks)
- Retry on transient errors (429 / 5xx) with bounded backoff
- 4xx (except 429) surfaces immediately — no retry on permanent client errors
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .models import JobcanClientError

DEFAULT_USER_AGENT = (
    "AozoraJobcanSync/0.2 (+contact@aozora-cg.com; "
    "Phase B periodic sync - 1x/day, gentle crawl)"
)
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds (multiplied by 2^attempt)
# Crawl-delay between *separate* requests (not retry backoff). 3-5s is the
# range agreed for Phase B (社長 report: 1x/day cadence + gentle per-request
# spacing so a single sync run never resembles a burst). Applied before every
# request, keyed off the client instance's own clock — a single JobcanClient
# is expected to live for the duration of one crawl run.
DEFAULT_CRAWL_DELAY = 3.0  # seconds

JOBCAN_BASE_URL = "https://recruit.jobcan.jp/aozora"


@dataclass(frozen=True)
class JobcanClientConfig:
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    crawl_delay: float = DEFAULT_CRAWL_DELAY
    base_url: str = JOBCAN_BASE_URL


class JobcanClient:
    """Synchronous httpx client wrapping Jobcan public pages."""

    def __init__(
        self,
        config: JobcanClientConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or JobcanClientConfig()
        # Allow caller (tests) to inject a pre-configured client (e.g. respx mock)
        self._client = client or httpx.Client(
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.timeout,
            follow_redirects=True,
        )
        self._owns_client = client is None
        # Crawl-delay bookkeeping: `None` until the first request, so the very
        # first request of a run never waits.
        self._last_request_at: float | None = None

    def fetch_job_detail(self, job_id: str | int) -> tuple[str, str]:
        """Fetch a single job detail page.

        Returns:
            (source_url, html) — both used by the parser to build a JobOffer.
            `source_url` is the URL actually requested (before any redirect
            following).

        Raises:
            JobcanClientError: on permanent failures (4xx other than 429,
                exhausted retries on 429/5xx, or network errors).
        """
        url = f"{self.config.base_url}/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
        return url, self._get_with_retry(url)

    def fetch_job_list(self, category_id: str | int, page: int = 1) -> tuple[str, str]:
        """Fetch a Jobcan category listing page.

        Args:
            category_id: Jobcan category to list.
            page: 1-based page number. Page 1 uses the original
                `/list?category_id=` path (unchanged, so existing callers that
                never pass `page` see identical behaviour). Page 2+ uses the
                path-segment form Jobcan actually serves
                (`/list/all/all/{page}?category_id=`) — confirmed against real
                fixtures (`jobcan-html-structure.md` §8/§9 only speculated
                `?page=N`; the real pagination links use a path segment).

        Returns:
            (source_url, html) — `source_url` includes the `category_id`
            query parameter and Jobcan's frame-hiding flags so the parser
            can extract `category_id` from it.

        Raises:
            JobcanClientError: same conditions as `fetch_job_detail`.
        """
        if page <= 1:
            url = (
                f"{self.config.base_url}/list"
                f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
            )
        else:
            url = (
                f"{self.config.base_url}/list/all/all/{page}"
                f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
            )
        return url, self._get_with_retry(url)

    def _wait_for_crawl_delay(self) -> None:
        """Sleep just enough to keep requests at least `crawl_delay` apart.

        Applied once per top-level call (not per retry — retries already have
        their own exponential backoff). The first request of a client's
        lifetime never waits (`_last_request_at` starts as `None`).
        """
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.config.crawl_delay - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _get_with_retry(self, url: str) -> str:
        self._wait_for_crawl_delay()
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    continue
                # status_code=None means "network failure, the canonical URL
                # is just as unreachable for the user as for us" — the proxy
                # treats it like a 5xx (HTML maintenance page, not redirect).
                raise JobcanClientError(
                    f"Network error after {attempt + 1} attempts: {exc}",
                    status_code=None,
                ) from exc

            if resp.status_code == 200:
                return resp.text

            # Retry on 429 (rate limit) and 5xx (transient server errors)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    continue
                raise JobcanClientError(
                    f"Transient HTTP {resp.status_code} from {url}",
                    status_code=resp.status_code,
                )

            # 4xx (other than 429): permanent — do not retry
            raise JobcanClientError(
                f"HTTP {resp.status_code} from {url}",
                status_code=resp.status_code,
            )

        # Every loop body path returns or raises; this satisfies the type checker.
        raise AssertionError("unreachable: retry loop completed")  # pragma: no cover

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JobcanClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
