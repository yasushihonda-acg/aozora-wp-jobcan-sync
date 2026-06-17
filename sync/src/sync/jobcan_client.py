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
    "AozoraJobcanSync/0.1 (+contact@aozora-cg.com; "
    "Phase B Phase 0 local PoC - not production)"
)
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds (multiplied by 2^attempt)

JOBCAN_BASE_URL = "https://recruit.jobcan.jp/aozora"


@dataclass(frozen=True)
class JobcanClientConfig:
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
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

    def _get_with_retry(self, url: str) -> str:
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    continue
                raise JobcanClientError(
                    f"Network error after {attempt + 1} attempts: {exc}"
                ) from exc

            if resp.status_code == 200:
                return resp.text

            # Retry on 429 (rate limit) and 5xx (transient server errors)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    continue
                raise JobcanClientError(f"Transient HTTP {resp.status_code} from {url}")

            # 4xx (other than 429): permanent — do not retry
            raise JobcanClientError(f"HTTP {resp.status_code} from {url}")

        # Every loop body path returns or raises; this satisfies the type checker.
        raise AssertionError("unreachable: retry loop completed")  # pragma: no cover

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JobcanClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
