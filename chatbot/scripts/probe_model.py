"""Ground-truth probe for MODEL_ID / VERTEX_LOCATION before deploying.

Rationale: Gemini model GA status and per-region availability change
frequently and must not be assumed from training data or secondary sources
(see ~/.claude/rules/tech-selection.md §1.1). This script re-runs the same
check performed by hand on 2026-07-24 (curl against the REST API) using the
`google-genai` SDK instead, so it can be re-run on demand — e.g. after a
model deprecation announcement, or before a redeploy in a new GCP project.

Usage:
    cd chatbot
    gcloud auth application-default login   # if not already logged in
    GCP_PROJECT=aozora-wp-jobcan-sync uv run python scripts/probe_model.py
"""

from __future__ import annotations

import os
import sys

from google import genai

CANDIDATES = [
    ("asia-northeast1", "gemini-3.5-flash-lite"),
    ("global", "gemini-3.5-flash-lite"),
    ("asia-northeast1", "gemini-3.5-flash"),  # last-resort fallback, higher cost
]


def probe(project: str, location: str, model_id: str) -> bool:
    client = genai.Client(vertexai=True, project=project, location=location)
    try:
        response = client.models.generate_content(model=model_id, contents="ping")
    except Exception as exc:  # broad on purpose: print+continue is the point of this probe
        print(f"  FAIL  location={location!r} model={model_id!r}: {exc}")
        return False
    print(f"  OK    location={location!r} model={model_id!r} -> {response.text!r}")
    return True


def main() -> int:
    project = os.environ.get("GCP_PROJECT")
    if not project:
        print("GCP_PROJECT env var is required", file=sys.stderr)
        return 1

    print(f"Probing Vertex AI Gemini candidates for project={project!r}...")
    for location, model_id in CANDIDATES:
        if probe(project, location, model_id):
            print(f"\n=> Use VERTEX_LOCATION={location} MODEL_ID={model_id}")
            return 0

    print("\nAll candidates failed — check API enablement / ADC / IAM.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
