"""Stamp every GitHub-Pages-only Phase A mockup file with a redirect to its
Phase B (Cloud Run) equivalent.

Context: `mockup/` is dual-purpose — `.dockerignore` bakes only
`mockup/assets/**` and `mockup/index.html` into the Cloud Run image
(`sync/Dockerfile`); every other file here (`mockup/jobs/*.html`,
`mockup/jobs.html`, `mockup/jobs-{care,nurse,office,it}.html`,
`mockup/job-preview.html`) is served *exclusively* by GitHub Pages and has
zero effect on what Cloud Run answers. Once Phase B carries the real 382-job
dataset, a 決裁者 who still opens (or has bookmarked) one of these legacy
pages should land on the equivalent Cloud Run page instead of the stale
~37-job Phase A sample — this script inserts that redirect.

`<meta http-equiv="refresh" content="0;url=...">` is the mechanism for every
file except `jobs.html` (see below): GitHub Pages serves static files with
no header/redirect config, and Google Search Central's "Redirects and
Google Search" doc states an *instant* (0-second) meta refresh is treated
as a *permanent* redirect (a delayed one is treated as temporary) — so this
is SEO-safe, not a hack.

`jobs.html` is special (2026-08-09 codex review finding): Phase A's own top
page links to it with `?job_type=visit`/`?job_type=care-manager`
(`mockup/index.html`), and Cloud Run's `redirect_legacy_jobs_list` route
(`sync/src/sync/app.py`) maps those two query values to filtered category
listings server-side. A static meta refresh can't read the query string —
it would always send every visitor to the unfiltered `/jobs/`, discarding
which category they actually asked for. `jobs.html` instead gets a tiny
inline script that does the equivalent client-side lookup, with a
`<noscript>` meta-refresh fallback to the unfiltered listing for the (rare,
JS-disabled) degraded case.

`mockup/index.html` gets the plain meta-refresh tag too (it's the page a
bookmark most likely opens), but it is *also* the file Cloud Run's own `/`
route reads and serves (`sync/src/sync/app.py`'s
`_load_top_page`/`_render_top_page`) — that function strips this exact
block (`_TOP_PAGE_PHASE_A_REDIRECT_RE`) before responding, so Cloud Run's
own top page never redirects to itself.

Idempotent: re-running (e.g. after Stage 5's domain switch, with a new
`--base-url`) replaces the previously-inserted block rather than
duplicating it, via the `<!-- phase-a-redirect -->` sentinel comments.

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
# dependency chain.
#
# `_CATEGORY_IDS`: the 4 keys with a standalone `mockup/jobs-*.html` file.
_CATEGORY_IDS = {
    "care": "18773",
    "nurse": "18983",
    "office": "58859",
    "it": "69384",
}
# `_JOB_TYPE_CATEGORY_IDS`: the other 13 entries, query-string-only on Phase A
# (`mockup/index.html`'s ホームヘルパー/ケアマネジャー cards, and the 11
# 「その他の募集職種」tags added 2026-08-11, link to `jobs.html?job_type=...`,
# never their own static page) — consumed by `jobs.html`'s inline script,
# not the plain per-file meta refresh below.
_JOB_TYPE_CATEGORY_IDS = {
    "visit": "18986",  # ホームヘルパー
    "care-manager": "18985",  # ケアマネジャー
    "consultant": "18984",  # 相談員
    "visiting-nurse": "18987",  # 訪問看護
    "night-shift": "18988",  # 夜勤専従（介護・看護）
    "facility-manager": "18989",  # 施設長・管理者候補
    "service-lead": "18990",  # サービス提供責任者
    "service-manager": "22014",  # サービス管理責任者
    "caretaker": "39695",  # 世話人
    "visiting-rehab": "41046",  # 訪問リハビリ
    "support": "43764",  # サポート職（清掃・洗濯・調理・送迎）
    "general": "71511",  # 総合職（営業・管理職）
    "new-grad": "73697",  # 新卒・既卒総合職
}

_PHASE_A_REDIRECT_BLOCK_RE = re.compile(
    r"<!--\s*phase-a-redirect\s*-->.*?<!--\s*/phase-a-redirect\s*-->\n?",
    re.IGNORECASE | re.DOTALL,
)
_CHARSET_RE = re.compile(r'<meta\s+charset=["\'][^"\']*["\']\s*/?>', re.IGNORECASE)


def _redirect_block(path: Path, target_url: str, base_url: str) -> str:
    """Build the sentinel-wrapped redirect block for `path`."""
    if path.name == "jobs.html":
        category_map_js = ",".join(f'"{k}":"{v}"' for k, v in _JOB_TYPE_CATEGORY_IDS.items())
        return (
            "<!-- phase-a-redirect -->"
            "<script>(function(){"
            f"var m={{{category_map_js}}};"
            'var c=m[new URLSearchParams(location.search).get("job_type")];'
            f'location.replace(c?"{base_url}/jobs/?category_id="+c:"{target_url}");'
            "})();</script>"
            f'<noscript><meta http-equiv="refresh" content="0;url={target_url}"></noscript>'
            "<!-- /phase-a-redirect -->\n"
        )
    return (
        "<!-- phase-a-redirect -->"
        f'<meta http-equiv="refresh" content="0;url={target_url}">'
        "<!-- /phase-a-redirect -->\n"
    )


def apply_redirect(path: Path, target_url: str, base_url: str) -> str:
    """Insert/replace the redirect block in `path`'s content.

    Returns "inserted", "updated", or "unchanged" (already has this exact
    block — re-running with the same `--base-url` is a no-op).
    """
    raw = path.read_text(encoding="utf-8")
    existing = _PHASE_A_REDIRECT_BLOCK_RE.search(raw)
    block = _redirect_block(path, target_url, base_url)

    if existing and existing.group(0) == block:
        return "unchanged"

    if existing:
        new_raw = _PHASE_A_REDIRECT_BLOCK_RE.sub(block, raw, count=1)
        status = "updated"
    else:
        charset_match = _CHARSET_RE.search(raw)
        if not charset_match:
            raise ValueError(f"{path}: no <meta charset> anchor found, cannot insert redirect")
        insert_at = charset_match.end()
        new_raw = raw[:insert_at] + "\n" + block + raw[insert_at:]
        status = "inserted"

    path.write_text(new_raw, encoding="utf-8")
    return status


def _targets(base_url: str) -> dict[Path, str]:
    """Map each GitHub-Pages-only file to its (fallback/default) Cloud Run
    target URL. `jobs.html`'s value here is the unfiltered `/jobs/`
    fallback — the actual per-visitor target may differ client-side, see
    `_redirect_block`."""
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
    parser.add_argument(
        "--base-url", required=True, help="Cloud Run origin, e.g. https://aozora-sync-flry56mxwa-an.a.run.app"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    targets = _targets(base_url)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}

    for path, target_url in targets.items():
        rel = path.relative_to(REPO)
        block = _redirect_block(path, target_url, base_url)
        if args.dry_run:
            existing = _PHASE_A_REDIRECT_BLOCK_RE.search(path.read_text(encoding="utf-8"))
            action = (
                "unchanged" if existing and existing.group(0) == block else ("updated" if existing else "inserted")
            )
            print(f"[dry-run] {action:9} {rel} -> {target_url}")
            counts[action] += 1
            continue
        status = apply_redirect(path, target_url, base_url)
        print(f"{status:9} {rel} -> {target_url}")
        counts[status] += 1

    print(
        f"\n{len(targets)} files processed: "
        f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['unchanged']} unchanged"
        + (" (dry-run, nothing written)" if args.dry_run else "")
    )


if __name__ == "__main__":
    main()
