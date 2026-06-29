"""Fetch and parse all job offers listed in jobs.html via sync's parser.

Usage:
    python scripts/mockup-rebuild/fetch_all.py [job_ids.txt] [out.json]

Defaults:
    job_ids: scripts/mockup-rebuild/job_ids.txt
    out:     scripts/mockup-rebuild/jobs_data.json

The script reads job IDs (one per line) and writes a JSON file containing
each JobOffer's normalised fields plus the full extra_lines table. Rate-limited
by a 0.5s sleep between requests.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "sync" / "src"))

from sync.jobcan_client import JobcanClient
from sync.models import JobcanClientError, JobcanStructureChangeError, JobcanValidationError
from sync.parser import parse_job_detail


def main(argv: list[str]) -> int:
    ids_file = Path(argv[1]) if len(argv) > 1 else HERE / "job_ids.txt"
    out_file = Path(argv[2]) if len(argv) > 2 else HERE / "jobs_data.json"

    if not ids_file.exists():
        print(f"ERROR: ids file not found: {ids_file}", file=sys.stderr)
        return 1

    ids = [ln.strip() for ln in ids_file.read_text().splitlines() if ln.strip()]
    print(f"Fetching {len(ids)} jobs", flush=True)

    results: list[dict] = []
    errors: list[dict] = []
    with JobcanClient() as client:
        for i, jid in enumerate(ids, 1):
            try:
                source_url, html = client.fetch_job_detail(jid)
                offer = parse_job_detail(html, source_url, job_id=jid)
                results.append(
                    {
                        "job_id": offer.job_id,
                        "title": offer.title,
                        "address": offer.address,
                        "label": offer.label,
                        "location": offer.location,
                        "salary": offer.salary,
                        "body_html": offer.body_html,
                        "extra_lines": list(offer.extra_lines),
                        "source_url": offer.source_url,
                    }
                )
                print(f"[{i:2}/{len(ids)}] OK  {jid}  {offer.title[:40]}", flush=True)
            except (JobcanClientError, JobcanStructureChangeError, JobcanValidationError) as e:
                errors.append({"job_id": jid, "error": f"{type(e).__name__}: {e}"})
                print(f"[{i:2}/{len(ids)}] ERR {jid}  {type(e).__name__}: {e}", flush=True)
            time.sleep(0.5)

    out_file.write_text(
        json.dumps({"jobs": results, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {out_file} ({len(results)} ok, {len(errors)} errors)", flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
