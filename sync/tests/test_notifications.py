"""`notify_slack` tests — webhook URL and HTTP calls are mocked; nothing here
ever raises out of `notify_slack` regardless of failure mode."""

from __future__ import annotations

import httpx
import pytest
import respx

import sync.notifications as notifications

_WEBHOOK_URL = "https://hooks.slack.com/services/T00/B00/xxxx"


@respx.mock
def test_notify_slack_posts_text_to_webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    route = respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200, text="ok"))

    notifications.notify_slack("closed率が30%を超えました")

    assert route.call_count == 1
    sent_body = route.calls[0].request.content
    assert b"closed" in sent_body


def test_notify_slack_swallows_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(name: str) -> str:
        raise LookupError("secret not found")

    monkeypatch.setattr(notifications, "get_secret", _raise)

    notifications.notify_slack("test")  # must not raise


@respx.mock
def test_notify_slack_swallows_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    respx.post(_WEBHOOK_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    notifications.notify_slack("test")  # must not raise


@respx.mock
def test_notify_slack_logs_but_does_not_raise_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notifications, "get_secret", lambda name: _WEBHOOK_URL)
    respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(404, text="invalid_webhook"))

    notifications.notify_slack("test")  # must not raise


@respx.mock
def test_notify_slack_uses_custom_secret_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def _get_secret(name: str) -> str:
        captured.append(name)
        return _WEBHOOK_URL

    monkeypatch.setattr(notifications, "get_secret", _get_secret)
    respx.post(_WEBHOOK_URL).mock(return_value=httpx.Response(200))

    notifications.notify_slack("test", secret_name="custom-webhook-secret")

    assert captured == ["custom-webhook-secret"]
