"""Secret Manager accessor (Phase B B-5): read-only, single secret at a time.

Slimmed down from `aozora-sns-auto`'s `SecretClient` — that one also supports
`set()` (secret creation/rotation from app code) and byte payloads, neither
of which `sync` needs: its only secret is `slack-webhook-url`, provisioned
once via `gcloud secrets create` (`infra/README.md`, B-6), never written from
inside the running service.
"""

from __future__ import annotations

import os
from functools import lru_cache

from google.cloud import secretmanager


@lru_cache(maxsize=1)
def _client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


@lru_cache(maxsize=8)
def get_secret(name: str, *, version: str = "latest") -> str:
    """Fetch a secret's payload as text, cached per (name, version) for this process."""
    project = os.environ.get("GCP_PROJECT_ID", "aozora-wp-jobcan-sync")
    path = f"projects/{project}/secrets/{name}/versions/{version}"
    response = _client().access_secret_version(name=path)
    return response.payload.data.decode("utf-8")
