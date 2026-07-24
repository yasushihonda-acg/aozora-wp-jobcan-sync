"""Regenerate `src/chatbot/knowledge/jobs_detail.json` from the mockup source data.

Run by hand after `mockup/jobs.html` / `mockup/assets/data/jobs.json` change
materially (same manual-sync tradeoff as `jobs_summary.json`, see
chatbot/README.md "知識ベースの鮮度"). No BeautifulSoup dependency — `jobs.html`
is machine-generated static markup with one `<h2 class="job-list-card__title">`
per `<a class="job-list-card__link" href="jobs/{id}.html">` in matching
document order, so a plain regex pairing is reliable and avoids adding a
parser dependency to this service for a one-off script.

Usage:
    cd chatbot && uv run python scripts/build_jobs_detail.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JOBS_HTML = _REPO_ROOT / "mockup" / "jobs.html"
_JOBS_JSON = _REPO_ROOT / "mockup" / "assets" / "data" / "jobs.json"
_OUTPUT = Path(__file__).resolve().parents[1] / "src" / "chatbot" / "knowledge" / "jobs_detail.json"

_LINK_RE = re.compile(r'href="jobs/(?P<id>\d+)\.html"')
_TITLE_RE = re.compile(r'<h2 class="job-list-card__title">(?P<title>.*?)</h2>')


def _extract_titles_by_id(html: str) -> dict[str, str]:
    ids = _LINK_RE.findall(html)
    titles = _TITLE_RE.findall(html)
    if len(ids) != len(titles):
        raise ValueError(
            f"jobs.html structure mismatch: {len(ids)} job links vs {len(titles)} titles"
        )
    return dict(zip(ids, titles, strict=True))


def main() -> None:
    html = _JOBS_HTML.read_text(encoding="utf-8")
    titles_by_id = _extract_titles_by_id(html)

    jobs_data = json.loads(_JOBS_JSON.read_text(encoding="utf-8"))
    facilities = jobs_data["facilities"]

    detail = []
    for job in jobs_data["jobs"]:
        job_id = job["id"]
        if job_id not in titles_by_id:
            raise ValueError(f"job id {job_id} in jobs.json has no matching title in jobs.html")
        facility = facilities[job["facilityKey"]]
        detail.append(
            {
                "id": job_id,
                "title": titles_by_id[job_id],
                "category": job["category"],
                "employment": job["employment"],
                "area": job["area"],
                "facility": facility["name"],
                "city": facility["city"],
                "url": f"jobs/{job_id}.html",
            }
        )

    _OUTPUT.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(detail)} jobs to {_OUTPUT}")


if __name__ == "__main__":
    main()
