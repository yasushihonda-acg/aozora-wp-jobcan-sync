"""`notify_ops` tests — webhook URL and HTTP calls are mocked; nothing here
ever raises out of `notify_ops` regardless of failure mode.

The webhook fixture is a Google Chat incoming-webhook URL (query string with
`key`/`token` included) because that is the real transport as of 2026-08-09 —
the org runs its ops channel on Google Chat, not Slack."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

import sync.notifications as notifications

_WEBHOOK_URL = (
    "https://chat.googleapis.com/v1/spaces/AAAAmockspace/messages"
    "?key=mock-key-123&token=mock-token-456"
)


@respx.mock
def test_notify_ops_posts_text_to_webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    route = respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200, text="ok"))

    notifications.notify_ops("closed率が30%を超えました")

    assert route.call_count == 1
    sent_body = route.calls[0].request.content
    assert b"closed" in sent_body


@respx.mock
def test_notify_ops_sends_exactly_text_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Google Chat accepts the same `{"text": ...}` body Slack did — assert the
    body is exactly that and nothing else, so a future transport tweak can't
    silently drop or wrap the message."""
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    route = respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200, text="ok"))

    notifications.notify_ops("🚨 ジョブカン同期: closed率が閾値を超えました")

    payload = json.loads(route.calls[0].request.content)
    assert payload == {"text": "🚨 ジョブカン同期: closed率が閾値を超えました"}


@respx.mock
def test_notify_ops_preserves_webhook_query_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Google Chat authenticates via the `key`/`token` query params — dropping
    them yields a 401 and a silently lost alert, so pin them here."""
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    route = respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200, text="ok"))

    notifications.notify_ops("test")

    request_url = route.calls[0].request.url
    assert request_url.params["key"] == "mock-key-123"
    assert request_url.params["token"] == "mock-token-456"
    assert request_url.path == "/v1/spaces/AAAAmockspace/messages"


def test_notify_ops_swallows_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(name: str) -> str:
        raise LookupError("secret not found")

    monkeypatch.setattr(notifications, "get_secret", _raise)

    notifications.notify_ops("test")  # must not raise


@respx.mock
def test_notify_ops_swallows_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    respx.post(_WEBHOOK_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    notifications.notify_ops("test")  # must not raise


@respx.mock
def test_notify_ops_logs_but_does_not_raise_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(404, text="invalid_webhook"))

    notifications.notify_ops("test")  # must not raise


@respx.mock
def test_notify_ops_uses_custom_secret_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def _get_secret(name: str) -> str:
        captured.append(name)
        return _WEBHOOK_URL

    monkeypatch.setattr(notifications, "get_secret", _get_secret)
    respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200))

    notifications.notify_ops("test", secret_name="custom-webhook-secret")

    assert captured == ["custom-webhook-secret"]


def test_notify_ops_default_secret_name_is_transport_neutral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default secret is `ops-webhook-url` (not `slack-webhook-url`) —
    `infra/README.md` §1.5 provisions exactly this name."""
    captured: list[str] = []

    def _get_secret(name: str) -> str:
        captured.append(name)
        raise LookupError("not provisioned in tests")

    monkeypatch.setattr(notifications, "get_secret", _get_secret)

    notifications.notify_ops("test")

    assert captured == ["ops-webhook-url"]
