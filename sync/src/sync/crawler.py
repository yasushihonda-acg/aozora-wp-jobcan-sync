"""Full-catalogue crawl orchestrator (Phase B periodic sync).

Deliberately separate from `parser.py` / `jobcan_client.py`: this module owns
*cross-request* concerns (the category list, de-dup across categories,
partial-failure handling, total-count reconciliation) that a single
list-page or detail-page fetch has no business knowing about.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .jobcan_client import JobcanClient
from .models import JobcanClientError, JobcanStructureChangeError, JobcanValidationError, JobOffer
from .parser import parse_job_detail, parse_job_list

_logger = logging.getLogger(__name__)

# Every category_id confirmed to exist on https://recruit.jobcan.jp/aozora as
# of 2026-08-06. The 11 marked (docs) were already confirmed in
# `docs/specs/jobcan-html-structure.md` §4; the remaining 6 were confirmed via
# the top-page category link list in this session (18984 corrects that
# document's own recorded mistake — it was fetched as "看護師" but the page
# title says 相談員; 18983 is the real 看護職).
#
# This is a manually-curated constant, not an auto-discovered list. Jobcan
# can add a category without notice; `crawl_all()` has no way to detect that
# on its own. Auto-discovering categories from the top page is a real gap but
# deliberately out of scope for Phase B's first cut (see
# `.claude/memory/feedback_overengineering_recovery_2026-06-18.md` — building
# a "just in case" discovery mechanism before it's needed is exactly the
# pattern that was walked back once already). Revisit if the 30%-closed
# circuit breaker (crawler.py callers, Firestore layer) starts firing for a
# category that legitimately just moved to a new category_id.
KNOWN_CATEGORY_IDS: tuple[str, ...] = (
    "18773",  # 介護職 (docs)
    "18983",  # 看護職
    "18984",  # 相談員 (docs recorded this as a "看護師" mis-fetch; corrected here)
    "18985",  # ケアマネジャー・計画作成担当者 (docs)
    "18986",  # ホームヘルパー (docs)
    "18987",  # 訪問看護
    "18988",  # 夜勤専従（介護・看護） (docs)
    "18989",  # 施設長・管理者候補
    "18990",  # サービス提供責任者 (docs)
    "22014",  # サービス管理責任者 (docs)
    "39695",  # 世話人 (docs)
    "41046",  # 訪問リハビリ
    "43764",  # サポート職（清掃・洗濯・調理・送迎） (docs)
    "58859",  # 事務職 (docs)
    "69384",  # IT エンジニア職 (docs)
    "71511",  # 総合職（営業・管理職）
    "73697",  # 新卒・既卒総合職 (docs)
)


@dataclass
class CrawlResult:
    """Outcome of one full-catalogue crawl run.

    `expected_total` / `collected_total` are the reconciliation check: sum
    each category's own reported `total_count` (from its page-1 listing) vs.
    every job_id actually attempted (fetched OK or errored — either way, we
    "saw" it). A silent partial crawl (a 200 with a half-rendered page, or a
    category missing from `KNOWN_CATEGORY_IDS`) shows up as a mismatch here
    instead of shipping short with no signal.
    """

    offers: list[JobOffer] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    expected_total: int = 0
    collected_total: int = 0
    listed_job_ids: set[str] = field(default_factory=set)
    """Every job_id actually observed in a successfully-fetched listing page
    this run, regardless of whether its detail fetch later succeeded. This is
    the ground truth `diff.compute_diff` needs to avoid conflating "detail
    fetch failed" with "gone from the listing" (see `fully_listed` below for
    the category-level equivalent) — `closed_detection.py`'s absence counter
    must never advance just because *we* failed to fetch something."""
    fully_listed: bool = True
    """False if any category failed to list completely this run (page 1
    itself failed, or a later page failed mid-pagination). `listed_job_ids`
    alone can't distinguish "this job_id is genuinely gone" from "its whole
    category failed to list, so we never got the chance to see it" — the
    caller (`orchestrator.py`) uses this flag to suppress absence-counting
    entirely for a run where any category's picture is incomplete, rather
    than risk closing jobs based on a gap that means nothing."""


def crawl_all(
    client: JobcanClient,
    category_ids: tuple[str, ...] = KNOWN_CATEGORY_IDS,
) -> CrawlResult:
    """Crawl every known category end to end and fetch every job's detail page.

    De-duplicates job_ids across categories — a posting can legitimately
    appear under more than one category (e.g. a 夜勤専従 posting also listed
    under 介護職). Each duplicate is fetched once.

    Partial-failure handling mirrors `scripts/mockup-rebuild/fetch_all.py`
    (Phase A's existing batch-fetch precedent): a single job_id or a single
    list page failing is recorded in `errors` and the crawl continues — a
    Jobcan-side blip on one posting must not block updating every other
    posting that fetched fine. Category-level failure (page 1 itself
    unreachable or structurally broken) skips that category and continues to
    the next one.
    """
    result = CrawlResult()
    seen_job_ids: set[str] = set()

    for category_id in category_ids:
        try:
            job_ids_for_category, category_fully_listed = _collect_category_job_ids(
                client, category_id, result
            )
        except (JobcanClientError, JobcanStructureChangeError) as exc:
            result.errors.append(
                {"category_id": category_id, "error": f"{type(exc).__name__}: {exc}"}
            )
            result.fully_listed = False
            _logger.error(
                "crawl: category listing failed, skipping category",
                extra={"category_id": category_id, "error": str(exc)},
            )
            continue

        if not category_fully_listed:
            result.fully_listed = False
        result.listed_job_ids.update(job_ids_for_category)

        for job_id in job_ids_for_category:
            if job_id in seen_job_ids:
                continue
            seen_job_ids.add(job_id)
            _fetch_one_detail(client, job_id, result)

    result.collected_total = len(result.offers) + len([e for e in result.errors if "job_id" in e])
    return result


def _collect_category_job_ids(
    client: JobcanClient,
    category_id: str,
    result: CrawlResult,
) -> tuple[list[str], bool]:
    """Walk every page of one category, returning (job_ids, fully_listed).

    Page 1's failure propagates to the caller (category-level skip). A later
    page's failure is recorded and the walk stops for *this category only* —
    `last_page` came from page 1, so a mid-crawl failure means the remaining
    pages of this one category are missing this run, not silently dropped
    without a trace. `fully_listed=False` in that case tells the caller this
    category's job_ids are an undercount, not a true "these are all the jobs".
    """
    source_url, html = client.fetch_job_list(category_id, page=1)
    page = parse_job_list(html, source_url)
    if page.total_count is not None:
        result.expected_total += page.total_count

    job_ids = [item.job_id for item in page.items]
    fully_listed = True

    for page_number in range(2, page.last_page + 1):
        try:
            source_url, html = client.fetch_job_list(category_id, page=page_number)
            next_page = parse_job_list(html, source_url)
        except (JobcanClientError, JobcanStructureChangeError) as exc:
            result.errors.append(
                {
                    "category_id": category_id,
                    "page": str(page_number),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            _logger.error(
                "crawl: category page failed, stopping this category's pagination",
                extra={"category_id": category_id, "page": page_number, "error": str(exc)},
            )
            fully_listed = False
            break
        job_ids.extend(item.job_id for item in next_page.items)

    return job_ids, fully_listed


def _fetch_one_detail(client: JobcanClient, job_id: str, result: CrawlResult) -> None:
    try:
        source_url, html = client.fetch_job_detail(job_id)
        offer = parse_job_detail(html, source_url, job_id=job_id)
        result.offers.append(offer)
    except (JobcanClientError, JobcanStructureChangeError, JobcanValidationError) as exc:
        result.errors.append({"job_id": job_id, "error": f"{type(exc).__name__}: {exc}"})
        _logger.error(
            "crawl: job detail fetch failed",
            extra={"job_id": job_id, "error": str(exc)},
        )
