"""Stamp every GitHub-Pages-only Phase A mockup file with a meta refresh to
its Phase B (Cloud Run) equivalent.

Context: `mockup/` is dual-purpose — `.dockerignore` bakes only
`mockup/assets/**` and `mockup/index.html` into the Cloud Run image
(`sync/Dockerfile`); every other file here (`mockup/jobs/*.html`,
`mockup/jobs.html`, `mockup/jobs-{care,nurse,office,it}.html`,
`mockup/job-preview.html`) is served *exclusively* by GitHub Pages and has
zero effect on what Cloud Run answers. Once Phase B carries the real 382-job
dataset, a 決裁者 who still opens (or has bookmarked) one of these legacy
pages should land on the equivalent Cloud Run page instead of the stale
~37-job Phase A sample — this script inserts that redirect.

`<meta http-equiv="refresh" content="0;url=...">` is the only realistic
mechanism here: GitHub Pages serves static files with no header/redirect
config, and Google Search Central's "Redirects and Google Search" doc states
an *instant* (0-second) meta refresh is treated as a *permanent* redirect
(a delayed one is treated as temporary) — so this is SEO-safe, not a hack.

`mockup/index.html` gets the tag too (it's the page a bookmark most likely
opens), but it is *also* the file Cloud Run's own `/` route reads and serves
(`sync/src/sync/app.py`'s `_load_top_page`/`_render_top_page`) — that
function strips this exact tag (`_TOP_PAGE_META_REFRESH_RE`) before
responding, so Cloud Run's own top page never redirects to itself.

Idempotent: re-running (e.g. after Stage 5's domain switch, with a new
`--base-url`) replaces the previously-inserted tag rather than duplicating
it, via the `<!-- phase-a-redirect -->` sentinel comments.

Usage:
    ./sync/.venv/bin/python scripts/mockup-rebuild/add_pages_redirects.py \
        --base-url https://aozora-sync-flry56mxwa-an.a.run.app [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MOCKUP = REPO / "mockup"

# Mirrors `sync/src/sync/app.py`'s `_LEGACY_CATEGORY_IDS` — that dict is the
# actual source of truth (it drives Cloud Run's own redirect routes and
# in-page link rewriting). Duplicated here, not imported, so this script
# stays a plain-stdlib script runnable without pulling in `sync`'s FastAPI
# dependency chain. Only the 4 keys that have a `mockup/jobs-*.html` file —
# `visit`/`care-manager` are query-string-only on Phase A and have no
# standalone static page to redirect.
_CATEGORY_IDS = {
    "care": "18773",
    "nurse": "18983",
    "office": "58859",
    "it": "69384",
}

_META_REFRESH_BLOCK_RE = re.compile(
    r"(?:<!--\s*phase-a-redirect\s*-->\s*)?"
    r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*>'
    r"(?:\s*<!--\s*/phase-a-redirect\s*-->)?\n?",
    re.IGNORECASE,
)
_CHARSET_RE = re.compile(r'<meta\s+charset=["\'][^"\']*["\']\s*/?>', re.IGNORECASE)


def _redirect_tag(target_url: str) -> str:
    return (
        "<!-- phase-a-redirect -->"
        f'<meta http-equiv="refresh" content="0;url={target_url}">'
        "<!-- /phase-a-redirect -->\n"
    )


def apply_redirect(path: Path, target_url: str) -> str:
    """Insert/replace the redirect tag in `path`'s content.

    Returns "inserted", "updated", or "unchanged" (already has this exact
    target — re-running with the same `--base-url` is a no-op).
    """
    raw = path.read_text(encoding="utf-8")
    existing = _META_REFRESH_BLOCK_RE.search(raw)
    tag = _redirect_tag(target_url)

    if existing and existing.group(0).strip() == tag.strip():
        return "unchanged"

    if existing:
        new_raw = _META_REFRESH_BLOCK_RE.sub(tag, raw, count=1)
        status = "updated"
    else:
        charset_match = _CHARSET_RE.search(raw)
        if not charset_match:
            raise ValueError(f"{path}: no <meta charset> anchor found, cannot insert redirect")
        insert_at = charset_match.end()
        new_raw = raw[:insert_at] + "\n" + tag + raw[insert_at:]
        status = "inserted"

    path.write_text(new_raw, encoding="utf-8")
    return status


def _targets(base_url: str) -> dict[Path, str]:
    base_url = base_url.rstrip("/")
    targets: dict[Path, str] = {
        MOCKUP / "index.html": f"{base_url}/",
        MOCKUP / "jobs.html": f"{base_url}/jobs/",
        MOCKUP / "job-preview.html": f"{base_url}/jobs/",
    }
    for key, category_id in _CATEGORY_IDS.items():
        targets[MOCKUP / f"jobs-{key}.html"] = f"{base_url}/jobs/?category_id={category_id}"
    for detail_path in sorted((MOCKUP / "jobs").glob("*.html")):
        job_id = detail_path.stem
        targets[detail_path] = f"{base_url}/jobs/{job_id}"
    return {path: url for path, url in targets.items() if path.exists()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Cloud Run origin, e.g. https://aozora-sync-flry56mxwa-an.a.run.app")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    args = parser.parse_args()

    targets = _targets(args.base_url)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}

    for path, target_url in targets.items():
        rel = path.relative_to(REPO)
        if args.dry_run:
            existing = _META_REFRESH_BLOCK_RE.search(path.read_text(encoding="utf-8"))
            action = "unchanged" if existing and target_url in existing.group(0) else (
                "updated" if existing else "inserted"
            )
            print(f"[dry-run] {action:9} {rel} -> {target_url}")
            counts[action] += 1
            continue
        status = apply_redirect(path, target_url)
        print(f"{status:9} {rel} -> {target_url}")
        counts[status] += 1

    print(
        f"\n{len(targets)} files processed: "
        f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['unchanged']} unchanged"
        + (" (dry-run, nothing written)" if args.dry_run else "")
    )


if __name__ == "__main__":
    main()
