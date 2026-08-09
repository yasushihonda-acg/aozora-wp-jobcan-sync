"""Jinja2 renderer for the in-house job-detail and job-list templates."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .detail_sections import RelatedJob, build_detail_view, build_job_posting_json_ld
from .list_sections import JobListCardView, JobTypeChip
from .models import JobListPage, JobOffer

TEMPLATES_DIR = Path(__file__).parent / "templates"
_logger = logging.getLogger(__name__)

# Stage 4-E (launch readiness, 2026-08-09): OGP / Twitter Card defaults,
# rendered by `base.html`'s `social_meta` block. Kept here rather than in the
# template so every page shares one string and the tests can assert against
# the same constant the templates use.
SITE_NAME = "あおぞらケアグループ 採用情報"
SITE_DESCRIPTION = (
    "あおぞらケアグループ採用情報。介護職・看護職・IT エンジニア・事務職など、"
    "福岡県・鹿児島県で地域に根ざす介護のしごとを募集しています。"
)
# Site-root-absolute: served by this app's own `/assets` StaticFiles mount
# over `mockup/assets` (app.py), and prefixed with `base_url` in the template
# so the og:image is the fully-qualified URL crawlers require.
OG_IMAGE_PATH = "/assets/img/sky-hero.jpg"


def _site_relative(url: str | None) -> str:
    """Prefix a page-relative stored asset URL with `/` so it resolves the
    same from any route depth.

    `JobListItem.thumbnail_url` (`selectors.yaml`'s category-image
    overrides) is persisted in Firestore as a page-relative string
    (`assets/img/illust-job-care.png`) — this was already a known,
    commented gap (`selectors.yaml` L71-78) that only surfaced once
    `/jobs/?category_id=` became a real, publicly-reachable route depth
    other than site root (Stage 1 of the Cloud Run consolidation,
    2026-08-08 — a `/jobs/...` page resolving `assets/img/...` 404s exactly
    like the CSS links did before `base.html`/`job_list.html` were fixed to
    use `/assets/...`). Absolute URLs are left untouched: `thumb_cfg.enabled
    = False` falls back to Jobcan's own CDN thumbnail (parser.py
    `_resolve_display_thumbnail`), which must not be rewritten.
    """
    if not url or url.startswith(("http://", "https://", "/")):
        return url or ""
    return f"/{url}"


def make_environment(templates_dir: Path | None = None) -> Environment:
    """Build a Jinja2 environment with autoescape enabled for HTML output."""
    loader = FileSystemLoader(str(templates_dir or TEMPLATES_DIR))
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        keep_trailing_newline=True,
    )
    env.filters["site_relative"] = _site_relative
    return env


def render_job_detail(
    job: JobOffer,
    *,
    closed: bool = False,
    base_url: str = "",
    category_id: str | None = None,
    thumbnail_url: str | None = None,
    related: list[RelatedJob] | None = None,
    env: Environment | None = None,
) -> str:
    """Render a single job offer into HTML using `job_detail.html`.

    `closed=True` (B-8: `app.py` serving a `sync_status="closed"` snapshot)
    swaps the apply CTA for a "募集終了しました" banner — the page itself
    still renders (SEO / 被リンク維持, CLAUDE.md 方針), only the CTA changes.

    `base_url` (Stage 1 of the Cloud Run consolidation, 2026-08-08) is this
    service's own public origin (e.g. `https://recruit.aozora-cg.com`, no
    trailing slash) used to build `canonical_url` pointing at *our* page
    instead of the upstream Jobcan URL — `job.source_url` remains available
    on the model for the 503/500 fallback links, but is no longer what
    `rel="canonical"` points to (that was a standing bug: it undermined the
    "keep closed listings up for SEO" design intent). Empty string (the
    default, used by local dev / tests that don't care about SEO) renders a
    site-root-relative canonical instead of a fully qualified one.

    Stage 2 (job-detail design parity, 2026-08-08) additions:

    - `category_id` builds every "back to listing" link (`category_url`
      below). `None` (a posting with no `category_ids`, or the caller opted
      not to look one up) falls back to the top page `/` rather than
      emitting a query string with a literal `None` in it — `/jobs/` alone
      404s (`category_id` is a required query param on that route).
    - `thumbnail_url` is the hero illustration — `None` hides that block
      entirely (`job_detail.html`), matching `render_job_list`'s existing
      "no thumbnail, no `<img>`" behaviour for `JobListItem`.
    - `related` is the same-category sidebar (`app.py` looks these up via
      `firestore_repo.get_by_category`); an empty/`None` list hides the
      `<aside>` entirely rather than rendering an empty card.
    """
    env = env or make_environment()
    template = env.get_template("job_detail.html")
    view = build_detail_view(job)
    if not view.work_blocks:
        # Unlike 応募資格/待遇/選考フロー (genuinely absent on some real
        # postings — confirmed against all 37 Phase A sample jobs), every
        # real Jobcan posting's body_html contains "【仕事内容】"
        # (`detail_sections.extract_work_description`'s anchor). An empty
        # result here is the strongest available signal that Jobcan's body
        # format drifted in a way the extractor doesn't recognise — the
        # section still degrades to "hidden" rather than failing the page
        # (`detail_sections.py`'s documented contract), but that degrade
        # must not be silent in production (second-opinion review finding).
        _logger.warning(
            "job detail missing 仕事内容 section — possible body_html format drift",
            extra={"job_id": job.job_id},
        )
    json_ld = json.dumps(
        build_job_posting_json_ld(job, view), ensure_ascii=False, indent=2
    ).replace("</", "<\\/")
    category_url = f"/jobs/?category_id={category_id}" if category_id else "/"
    return template.render(
        job=job,
        view=view,
        json_ld=json_ld,
        page_title=job.page_title,
        closed=closed,
        base_url=base_url,
        category_id=category_id,
        category_url=category_url,
        thumbnail_url=thumbnail_url,
        related=related or [],
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        og_image_path=OG_IMAGE_PATH,
    )


def render_job_list(
    page: JobListPage,
    *,
    base_url: str = "",
    cards: list[JobListCardView] | None = None,
    search_mode: bool = False,
    search_index_url: str | None = None,
    job_type_chips: list[JobTypeChip] | None = None,
    env: Environment | None = None,
) -> str:
    """Render a parsed Jobcan listing page into HTML using `job_list.html`.

    See `render_job_detail` for `base_url`.

    Stage 3 (求人一覧デザインパリティ) additions:
    - `cards`: per-item colour/chip/facility decorations (`list_sections.
      build_card_view`), matched to `page.items` by `job_id`. The template
      renders from `page.items` first and looks up a card's decoration by
      id — an item with no match (or `cards=None`, the CLI `list`
      subcommand's path, which has no `JobSnapshot`/`JobOffer` to derive
      chips from) falls back to the plain pre-Stage-3 card markup instead
      of a missing/empty card, so every existing `render_job_list(page)`
      call site keeps working unchanged.
    - `search_mode`: `True` for the all-jobs page (`category_id=None`) —
      the template renders the chip/freeword/map search panel only then.
    - `search_index_url`: where `map-search.js` fetches the filter/map
      dataset from (`/jobs/search-index.json`, never the `/assets/`-mounted
      Phase A static file — see `search_index.py`'s module docstring).
    - `job_type_chips`: the 17-category 職種 chip list
      (`list_sections.build_job_type_chips`), rendered only in
      `search_mode` (job-type-filter-granularity follow-up, 2026-08-09).
      `None`/empty falls back to an empty chip row rather than erroring —
      same "no data → nothing renders, not a crash" shape as `cards`.
    """
    env = env or make_environment()
    template = env.get_template("job_list.html")
    cards_by_job_id = {c.item.job_id: c for c in (cards or [])}
    return template.render(
        page=page,
        base_url=base_url,
        cards_by_job_id=cards_by_job_id,
        search_mode=search_mode,
        search_index_url=search_index_url,
        job_type_chips=job_type_chips or [],
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        og_image_path=OG_IMAGE_PATH,
    )


def render_error(
    *,
    title: str,
    message: str,
    fallback_url: str,
    env: Environment | None = None,
) -> str:
    """Render the FastAPI proxy's error fallback page using `error.html`.

    Phase 2A.3 cleanup (code-review #5): the proxy used to build this HTML
    by `str.format` on a module-level template. Jinja2 autoescape closes a
    subtle XSS path where a structured-change error's selector list lands
    in `message`, and keeps the error page in the same template family as
    `job_detail.html` / `job_list.html`.
    """
    env = env or make_environment()
    template = env.get_template("error.html")
    return template.render(title=title, message=message, fallback_url=fallback_url)


def render_not_found(*, env: Environment | None = None) -> str:
    """Render the FastAPI proxy's public-facing 404 page using
    `not_found.html` (Stage 4 P0-2, 2026-08-09).

    Static content — no per-request data to interpolate, so this takes no
    arguments beyond the environment override every other `render_*`
    function accepts (matches `render_error`'s pattern for consistency).
    """
    env = env or make_environment()
    template = env.get_template("not_found.html")
    return template.render()


def render_sitemap(urls: list[str], *, env: Environment | None = None) -> str:
    """Render `sitemap.xml` from a pre-built list of absolute URLs (Stage 4
    P1-1, 2026-08-09).

    Deliberately takes the final URL list rather than `JobSnapshot`s — the
    active/closed filtering and category-URL construction is `app.py`'s
    concern (`_build_sitemap_urls`), kept separate so that function stays
    unit-testable without a Jinja2 environment, matching `_render_list`'s
    existing split between "decide what to show" and "render it."
    """
    env = env or make_environment()
    template = env.get_template("sitemap.xml")
    return template.render(urls=urls)
