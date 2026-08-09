"""Ops webhook notifications — Google Chat (Phase B B-5).

The org runs its operations channel on Google Chat, not Slack (2026-08-09),
so this posts to a Google Chat incoming webhook. The payload shape is
unchanged from the original Slack implementation: Google Chat's incoming
webhook accepts the very same `{"text": "..."}` JSON body. The function name
and secret name are deliberately transport-neutral (`notify_ops` /
`ops-webhook-url`) so a future move to yet another channel touches only this
module's URL, not every call site.

Ported from `aozora-sns-auto`'s `notifications/slack.py` (31 lines) with one
deliberate simplification: no `tenacity` retry loop. A single failed POST is
logged and swallowed — the cron already retries the whole sync at the next
6-hourly run (2026-08-08: even sooner than the old once-daily cadence), so
retrying one POST inside a single run adds a dependency for marginal
benefit (this project's anti-overengineering precedent:
`.claude/memory/feedback_overengineering_recovery_2026-06-18.md`).

Failure must never crash the calling sync run: closed-rate circuit-breaker
alerts and summary posts are operational nice-to-haves, not something worth
losing a crawl over.
"""

from __future__ import annotations

import logging

import httpx

from .secrets import get_secret

_logger = logging.getLogger(__name__)

_SECRET_NAME = "ops-webhook-url"


def notify_ops(text: str, *, secret_name: str = _SECRET_NAME) -> None:
    """Post `text` to the configured ops incoming webhook (Google Chat).

    The secret holds the full webhook URL including its `key`/`token` query
    parameters — Google Chat authenticates on those, so the URL is posted to
    verbatim.

    Every failure mode (missing secret, network error, non-2xx response) is
    caught, logged, and swallowed — never raised to the caller.
    """
    try:
        webhook_url = get_secret(secret_name)
    except Exception as exc:
        _logger.warning("ops_webhook_unavailable", extra={"error": str(exc)})
        return

    try:
        response = httpx.post(webhook_url, json={"text": text}, timeout=10.0)
    except httpx.HTTPError as exc:
        _logger.error("ops_notify_failed", extra={"error": str(exc)})
        return

    if response.status_code >= 400:
        _logger.error(
            "ops_notify_failed",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
