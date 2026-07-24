"""Application configuration resolved at app construction.

Pulled into a frozen dataclass so the route layer relies on stable settings
for the process lifetime — mirrors `sync/src/sync/app.py`'s `AppConfig`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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
            max_output_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS", "512")),
            rate_limit_window_seconds=int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60")),
            rate_limit_max_requests=int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20")),
        )
