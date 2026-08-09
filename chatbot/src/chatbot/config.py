"""Application configuration resolved at app construction.

Pulled into a frozen dataclass so the route layer relies on stable settings
for the process lifetime — mirrors `sync/src/sync/app.py`'s `AppConfig`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .knowledge import DEFAULT_JOBS_DETAIL_URL


def _parse_csv_env(value: str) -> tuple[str, ...]:
    """Parse a comma-separated env var into a tuple of trimmed entries.

    Empty string yields an empty tuple. Same convention as sync's
    `_parse_csv_env` (frozenset there; tuple here since CORS `allow_origins`
    needs an ordered list, not a set).
    """
    if not value:
        return ()
    return tuple(entry.strip() for entry in value.split(",") if entry.strip())


@dataclass(frozen=True)
class AppConfig:
    gcp_project: str
    vertex_location: str
    model_id: str
    allowed_origins: tuple[str, ...]
    max_input_chars: int
    max_history_turns: int
    max_output_tokens: int
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    # Defaulted fields must come last (dataclass field-ordering rule) so
    # existing keyword-only `AppConfig(...)` call sites (tests) don't break.
    # Empty string disables the startup knowledge refresh entirely (used by
    # every test — see `chatbot/tests/test_app.py`'s `_config()` — and as a
    # production kill switch via `gcloud run services update
    # --update-env-vars JOBS_DETAIL_URL=`).
    jobs_detail_url: str = DEFAULT_JOBS_DETAIL_URL
    knowledge_fetch_timeout_seconds: float = 3.0
    # A Cloud Run instance can stay warm far longer than one 6-hourly `sync`
    # cycle — without this, a long-lived instance would keep answering with
    # whatever it fetched at cold start forever (Stage: AIチャットPhase B連携,
    # 2026-08-09). Enforced by `app._maybe_refresh_knowledge`, checked at the
    # top of every `/chat` request rather than an `asyncio` background timer
    # — Cloud Run's default CPU allocation freezes background tasks whenever
    # an instance has no in-flight request, so a timer-based design silently
    # misses this interval while idle (see that function's docstring). `0`
    # (or negative) disables it, same convention as `jobs_detail_url=""`
    # disabling the fetch entirely.
    knowledge_refresh_interval_seconds: float = 3600.0

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            gcp_project=os.environ.get("GCP_PROJECT", ""),
            # Step 0 ground truth (2026-07-24): asia-northeast1 returns 404 for
            # gemini-3.5-flash-lite (publisher model not registered in that
            # region), global returns 200. Default reflects the confirmed
            # working combination; override via env if model/region changes.
            vertex_location=os.environ.get("VERTEX_LOCATION", "global"),
            model_id=os.environ.get("MODEL_ID", "gemini-3.5-flash-lite"),
            allowed_origins=_parse_csv_env(
                os.environ.get(
                    "ALLOWED_ORIGINS",
                    "https://yasushihonda-acg.github.io,http://localhost:8989,http://localhost:8080",
                )
            ),
            max_input_chars=int(os.environ.get("MAX_INPUT_CHARS", "500")),
            max_history_turns=int(os.environ.get("MAX_HISTORY_TURNS", "6")),
            # JSON構造化出力 (reply/suggestions/job_ids) はプレーンテキストより
            # トークン消費が増えるため、旧デフォルト512から引き上げ。
            max_output_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS", "768")),
            rate_limit_window_seconds=int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60")),
            rate_limit_max_requests=int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20")),
            # `.get(..., DEFAULT)`, not `or DEFAULT`: an explicit empty string
            # must stay empty (the fetch kill switch), not fall back to the
            # default URL.
            jobs_detail_url=os.environ.get("JOBS_DETAIL_URL", DEFAULT_JOBS_DETAIL_URL),
            # Unlike `jobs_detail_url`, an empty string has no meaning here
            # (there's no "disabled timeout") — `or "3.0"` falls back to the
            # default instead of `float("")` raising `ValueError` and
            # crashing the whole container at import time (this runs before
            # uvicorn binds its listen socket). An operator who copies the
            # `JOBS_DETAIL_URL=` empty-string pattern by analogy for this
            # sibling env var must not get a crash loop for it.
            knowledge_fetch_timeout_seconds=float(
                os.environ.get("KNOWLEDGE_FETCH_TIMEOUT_SECONDS") or "3.0"
            ),
            # `or "3600.0"`, not `.get(..., DEFAULT)`: unlike `jobs_detail_url`,
            # an explicit empty string has no distinct meaning here — `"0"` is
            # the documented way to disable the request-triggered refresh, so
            # an empty string falling back to the default (rather than
            # crashing `float("")`) is the safer default for an operator
            # env-var typo.
            knowledge_refresh_interval_seconds=float(
                os.environ.get("KNOWLEDGE_REFRESH_INTERVAL_SECONDS") or "3600.0"
            ),
        )
