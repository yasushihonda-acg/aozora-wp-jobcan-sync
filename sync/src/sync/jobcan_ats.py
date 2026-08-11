"""Playwright automation for `ats.jobcan.jp` — the CSV-migration follow-up's
browser-driven half (2026-08-11).

Deliberately has no knowledge of `JobOffer`/`CrawlResult`/Firestore: this
module's only job is to log into the ATS admin screen and download the
公開状況=公開 (published-only) `job_offers` list as one CSV file per page,
returning `list[Path]`. `csv_ingest.py` (no Playwright dependency at all)
turns those files into `CrawlResult`.

This is the **only** module in the package that imports `playwright` — the
`ats` extra (`pyproject.toml`) is not a base dependency and not in the dev
group, so every other module/test/environment (including the request-serving
FastAPI image) never needs it installed. `cli.py` mirrors this by importing
`JobcanAtsClient` inside the `ats-download` command body, not at module level.

## Safety model (read before touching `assert_safe_bulk_action`)

The ATS list screen's bulk-action dropdown mixes CSV export with genuinely
destructive actions (`求人を削除する`, `求人ページを非公開にする`,
`求人を非アクティブにする`, ...) in one `<select>`. This module NEVER
performs any of those — `download_published_csvs` is the only public entry
point and it only ever selects a CSV-download action. `assert_safe_bulk_action`
is called three times per page (after selecting, before clicking 実行, before
clicking 確定) as defence in depth against a Jobcan UI change silently
reassigning a value or relabelling an option.

This session's investigation (2026-08-10/11) established the two facts this
module's design depends on, both verified against the live UI, not assumed:

1. The `jobcan-sync@aozora-cg.com` account needs 「求人の登録・編集：全て登録・
   編集可」(not merely view access) for the row-selection checkboxes to even
   render — a view-only role gets an empty `<td></td>` per row and a
   permanently-disabled 実行 button. `_download_one_page` treats that exact
   symptom (checked-row count staying 0 after clicking select-all) as a hard
   error rather than hanging.
2. The 公開状況=公開 filter is what makes the CSV export match the 382
   postings Phase B actually serves (471 unfiltered). `_apply_published_filter`
   aborts if filtering doesn't reduce the count — the single highest-value
   guard in this module, since a silently-broken filter would otherwise
   publish 89 unpublished postings straight to the live site.
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .models import JobcanAtsError, JobcanAtsSafetyError, JobcanStructureChangeError
from .secrets import get_secret

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

_logger = logging.getLogger(__name__)

# The only two bulk-action values this module will ever select. Any other
# value found in the dropdown — including the visually-similar "Indeed PLUS
# CSVファイルをダウンロード" export — is out of scope and must never be chosen.
CSV_DOWNLOAD_ACTIONS: Final[frozenset[str]] = frozenset({"output_file", "output_file_utf8"})
CSV_DOWNLOAD_LABEL_PREFIX: Final[str] = "CSVファイルをダウンロード"

# Every substring observed across the ATS bulk-action dropdown's real options
# (captured 2026-08-10) that indicates a state-mutating action, not a
# read-only export. Deliberately broad substrings (not full label matches) so
# a Jobcan wording tweak to any of these still trips the guard.
FORBIDDEN_LABEL_SUBSTRINGS: Final[tuple[str, ...]] = (
    "削除",
    "非公開",
    "公開する",
    "停止",
    "受付",
    "アクティブ",
    "有効",
    "無効",
)


def assert_safe_bulk_action(value: str, label: str) -> None:
    """Raises `JobcanAtsSafetyError` unless `(value, label)` is unambiguously
    one of the two CSV-download bulk actions.

    Three independent layers, ANY of which alone would be insufficient:

    1. `value` must be in the whitelist (`output_file`/`output_file_utf8`).
    2. The label actually shown for that value must start with the CSV
       download prefix — guards against Jobcan silently reassigning
       `output_file` to a different action.
    3. The label must contain none of `FORBIDDEN_LABEL_SUBSTRINGS` — a second,
       independent check that does not rely on the prefix check alone.
    """
    if value not in CSV_DOWNLOAD_ACTIONS:
        raise JobcanAtsSafetyError(f"bulk action value {value!r} is not a whitelisted CSV export")
    if not label.startswith(CSV_DOWNLOAD_LABEL_PREFIX):
        raise JobcanAtsSafetyError(
            f"bulk action value {value!r} is now labelled {label!r}, "
            f"expected a label starting with {CSV_DOWNLOAD_LABEL_PREFIX!r}"
        )
    for bad in FORBIDDEN_LABEL_SUBSTRINGS:
        if bad in label:
            raise JobcanAtsSafetyError(
                f"bulk action label {label!r} contains forbidden substring {bad!r}"
            )


_TOTAL_COUNT_RE = re.compile(r"(\d+)件中")


def parse_total_count(text: str) -> int:
    """Pulls the leading count out of the ATS list screen's 「NNN件中
    N-N件を表示」text. Raises `JobcanStructureChangeError` (not a bare
    `ValueError`) so callers can route it through the same exit-code-2 path
    as an HTML selector going missing."""
    match = _TOTAL_COUNT_RE.search(text)
    if match is None:
        raise JobcanStructureChangeError(missing=[f"件数表示 (got {text!r})"])
    return int(match.group(1))


def pick_select_index(option_labels: list[list[str]], placeholder: str) -> int:
    """PURE. Given every `<select>` on the page (as its option label lists),
    returns the index of the one `<select>` whose first option's text equals
    `placeholder` exactly.

    Raises `JobcanStructureChangeError` — with the full observed placeholder
    list — when the match count is not exactly 1. An operator reading the
    resulting alert sees precisely what Jobcan renamed, rather than a bare
    "selector not found."
    """
    hits = [
        i for i, opts in enumerate(option_labels) if opts and opts[0].strip() == placeholder
    ]
    if len(hits) != 1:
        raise JobcanStructureChangeError(
            missing=[
                f"select[options[0]=={placeholder!r}] (found {len(hits)}; "
                f"observed first options: {[opts[0] if opts else None for opts in option_labels]})"
            ]
        )
    return hits[0]


_PAGE_SIZE_OPTION_RE = re.compile(r"^\d+件を表示$")


def pick_page_size_select_index(option_labels: list[list[str]]) -> int:
    """PURE. The 表示件数 `<select>` has no blank placeholder option — its
    default-selected first option is itself a real value (`"20件を表示"`) —
    so it needs its own predicate distinct from `pick_select_index`: the
    unique `<select>` whose every option matches `NN件を表示`."""
    hits = [
        i
        for i, opts in enumerate(option_labels)
        if opts and all(_PAGE_SIZE_OPTION_RE.match(o.strip()) for o in opts)
    ]
    if len(hits) != 1:
        raise JobcanStructureChangeError(
            missing=[
                f"select[options match /{_PAGE_SIZE_OPTION_RE.pattern}/] "
                f"(found {len(hits)}; observed: {option_labels})"
            ]
        )
    return hits[0]


@dataclass(frozen=True)
class JobcanAtsConfig:
    login_url: str = "https://id.jobcan.jp/users/sign_in"
    ats_oauth_url: str = "https://ats.jobcan.jp/jbc-oauth/login"
    job_offers_url: str = "https://ats.jobcan.jp/job_offers"
    email: str = "jobcan-sync@aozora-cg.com"
    password_secret_name: str = "jobcan-sync-password"
    page_size: int = 100
    headless: bool = True
    action_timeout_ms: int = 15_000
    download_timeout_ms: int = 120_000
    max_page_retries: int = 2
    retry_base_delay: float = 2.0
    inter_page_delay: float = 1.0


@dataclass(frozen=True)
class AtsDownloadResult:
    paths: list[Path] = field(default_factory=list)
    expected_total: int = 0
    """The 公開状況=公開-filtered count read from the ATS list screen itself
    (382 as of 2026-08-11) — feeds `CrawlResult.expected_total` via
    `csv_ingest.crawl_from_csv`'s `expected_total` argument."""
    unfiltered_total: int = 0
    """The count before the 公開状況 filter was applied (471 as of
    2026-08-11) — logged for the sanity assertion, not consumed downstream."""
    fully_downloaded: bool = True
    """False if ANY page failed after retries. Must be threaded honestly into
    `CrawlResult.fully_listed` by the caller — a partial download that claims
    completeness would let genuinely-still-open postings from an undownloaded
    page look `removed` and eventually close (see module docstring)."""
    errors: list[dict[str, str]] = field(default_factory=list)


_SEARCH_TOGGLE_SELECTOR = 'img[alt="toggle"]'
_SEARCH_BUTTON_TEXT = "検索"
_EXECUTE_BUTTON_TEXT = "実行"
_CONFIRM_BUTTON_TEXT = "確定"
_COUNT_TEXT_SELECTOR = "text=/\\d+件中/"


def _all_select_option_labels(page: Page) -> list[list[str]]:
    return page.eval_on_selector_all(
        "select", "els => els.map(e => [...e.options].map(o => o.textContent))"
    )


def _read_selected_label(select: Locator) -> str:
    return select.evaluate("e => e.options[e.selectedIndex].textContent.trim()")


class JobcanAtsClient:
    """Context manager owning the Playwright/browser/context lifecycle.

    ```python
    with JobcanAtsClient() as client:
        result = client.download_published_csvs(Path("/tmp/ats"))
    ```

    No tracing, HAR recording, or video capture is ever enabled on the
    browser context — any of those would capture the login POST body
    containing the password. No screenshots are taken anywhere in this class
    for the same reason (see `_login`).
    """

    def __init__(self, config: JobcanAtsConfig | None = None) -> None:
        self.config = config or JobcanAtsConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self._known_unfiltered_total: int | None = None

    def __enter__(self) -> JobcanAtsClient:
        # Imported here (not at module level) so nothing outside this class
        # ever needs `playwright` importable — see module docstring.
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            # Cloud Run's /dev/shm is small; Chromium reliably crashes there
            # without this flag.
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )
        self._context = self._browser.new_context(accept_downloads=True)
        self._context.set_default_timeout(self.config.action_timeout_ms)
        self._page = self._context.new_page()
        self._login(self._page)
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _login(self, page: Page) -> None:
        """Logs into the ジョブカン共通ID SSO gateway, which then carries the
        session to `ats.jobcan.jp`.

        `password` is a local variable ONLY — never stored on `self`, never
        logged, never passed to anything that could persist it (no tracing/
        HAR/video is enabled on this context; see class docstring). Attempted
        exactly once: retrying a failed login risks account lockout, so a
        login failure surfaces as a plain exception rather than a retry loop.
        """
        password = get_secret(self.config.password_secret_name)
        page.goto(self.config.login_url)
        page.fill('input[type="email"], input[name*="email"]', self.config.email)
        page.fill('input[type="password"]', password)
        del password
        page.click('button[type="submit"], input[type="submit"]')
        # The sign-in URL itself is under id.jobcan.jp, so a bare "still on
        # id.jobcan.jp" check would resolve instantly without ever waiting
        # for the redirect. `/account/profile` is where a successful login
        # actually lands (verified against the live UI, 2026-08-10).
        page.wait_for_url(re.compile(r"^https://id\.jobcan\.jp/account/profile"), timeout=30_000)

        # A successful ジョブカン共通ID login alone does NOT establish a
        # session on ats.jobcan.jp — going straight to /job_offers from here
        # times out waiting for content that never renders (confirmed against
        # the live UI: this exact omission caused the first real
        # `ats-download` run to fail, 2026-08-11). The OAuth handshake below
        # is what the 採用 nav link in the id.jobcan.jp header actually
        # points at; visiting it directly establishes the ATS-side session.
        page.goto(self.config.ats_oauth_url)
        page.wait_for_url(re.compile(r"^https://ats\.jobcan\.jp/"), timeout=30_000)

    def download_published_csvs(self, dest_dir: Path) -> AtsDownloadResult:
        """Downloads one CSV per page of the 公開状況=公開-filtered
        `job_offers` list, at `config.page_size` rows per page, into
        `dest_dir`. Returns as soon as every page has been attempted
        (including retries) — a failed page is recorded in `.errors` and
        `.fully_downloaded=False`, it never raises past this method for a
        single-page failure (only for the pre-pagination setup: login
        already happened in `__enter__`, and a broken 公開状況 filter is
        exactly the kind of thing that must abort the whole run).
        """
        assert self._page is not None, "call within a `with JobcanAtsClient() as client:` block"
        page = self._page
        dest_dir.mkdir(parents=True, exist_ok=True)

        page.goto(self.config.job_offers_url)
        filtered_total, unfiltered_total = self._apply_published_filter(page)
        self._known_unfiltered_total = unfiltered_total
        self._set_page_size(page, self.config.page_size)

        after_page_size = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))
        if after_page_size != filtered_total:
            raise JobcanAtsSafetyError(
                f"page-size change altered the filtered count "
                f"({filtered_total} -> {after_page_size}); the 公開状況 filter "
                "may have been reset"
            )

        total_pages = math.ceil(filtered_total / self.config.page_size) if filtered_total else 0
        paths: list[Path] = []
        errors: list[dict[str, str]] = []
        all_ok = True

        for page_number in range(1, total_pages + 1):
            try:
                paths.append(
                    self._download_one_page(page, page_number, filtered_total, dest_dir)
                )
            except JobcanAtsSafetyError:
                raise  # never swallowed — always aborts the whole run
            except JobcanAtsError as exc:
                errors.append({"page": str(page_number), "error": f"{type(exc).__name__}: {exc}"})
                _logger.error(
                    "jobcan_ats: page download failed, continuing to next page",
                    extra={"page": page_number, "error": str(exc)},
                )
                all_ok = False
            time.sleep(self.config.inter_page_delay)

        return AtsDownloadResult(
            paths=paths,
            expected_total=filtered_total,
            unfiltered_total=unfiltered_total,
            fully_downloaded=all_ok,
            errors=errors,
        )

    def _apply_published_filter(self, page: Page) -> tuple[int, int]:
        """Applies 公開状況=公開 and returns `(filtered_total, unfiltered_total)`.

        `filtered_total >= unfiltered_total` aborts — see module docstring.
        This is the single highest-value guard in this module.
        """
        unfiltered_total = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))

        page.click(_SEARCH_TOGGLE_SELECTOR)
        index = pick_select_index(_all_select_option_labels(page), "公開状況")
        select = page.locator("select").nth(index)
        select.select_option(value="1")
        label = _read_selected_label(select)
        if label != "公開":
            raise JobcanAtsSafetyError(f"公開状況 filter read back {label!r}, expected '公開'")

        page.click(f"button:has-text('{_SEARCH_BUTTON_TEXT}')")
        page.wait_for_load_state("networkidle")
        filtered_total = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))

        if filtered_total >= unfiltered_total:
            raise JobcanAtsSafetyError(
                f"公開状況 filter had no effect ({filtered_total} of {unfiltered_total}); "
                "aborting rather than risk exporting unpublished postings"
            )
        return filtered_total, unfiltered_total

    def _set_page_size(self, page: Page, page_size: int) -> None:
        index = pick_page_size_select_index(_all_select_option_labels(page))
        select = page.locator("select").nth(index)
        select.select_option(label=f"{page_size}件を表示")
        page.wait_for_load_state("networkidle")

    def _download_one_page(
        self, page: Page, page_number: int, expected_filtered_total: int, dest_dir: Path
    ) -> Path:
        last_error: Exception | None = None
        for attempt in range(self.config.max_page_retries + 1):
            try:
                return self._download_one_page_attempt(
                    page, page_number, expected_filtered_total, dest_dir
                )
            except JobcanAtsSafetyError:
                raise  # safety errors are never retried
            except JobcanAtsError as exc:
                last_error = exc
                if attempt < self.config.max_page_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    page.goto(self.config.job_offers_url)
                    self._ensure_published_filter(page)
                    self._set_page_size(page, self.config.page_size)
        assert last_error is not None
        raise last_error

    def _ensure_published_filter(self, page: Page) -> None:
        """Re-establishes 公開状況=公開 after a mid-run `page.goto` (retry
        path only).

        NOT the same as calling `_apply_published_filter` again: that method
        reads whatever count is currently on screen and treats it as the
        *unfiltered* baseline — but Jobcan persists the previous search
        filter across a same-session reload (confirmed against the live UI:
        the naive "just call `_apply_published_filter` again" version read
        the already-filtered 382 as if it were the 471 baseline and tripped
        the `filtered >= unfiltered` safety abort on a perfectly healthy
        retry, 2026-08-11). This method instead compares against the ONE
        `unfiltered_total` captured at the very start of the run
        (`self._known_unfiltered_total`) — if the reload already shows the
        expected filtered count, the filter survived and nothing more is
        needed; only re-apply it when the reload reverted all the way back
        to the true unfiltered count.
        """
        assert self._known_unfiltered_total is not None, "call after the initial filter succeeds"
        current = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))
        if current != self._known_unfiltered_total:
            return  # filter survived the reload — nothing to redo

        page.click(_SEARCH_TOGGLE_SELECTOR)
        index = pick_select_index(_all_select_option_labels(page), "公開状況")
        select = page.locator("select").nth(index)
        select.select_option(value="1")
        label = _read_selected_label(select)
        if label != "公開":
            raise JobcanAtsSafetyError(f"公開状況 filter read back {label!r}, expected '公開'")

        page.click(f"button:has-text('{_SEARCH_BUTTON_TEXT}')")
        page.wait_for_load_state("networkidle")
        reapplied = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))
        if reapplied >= self._known_unfiltered_total:
            raise JobcanAtsSafetyError(
                f"公開状況 filter did not reduce the count on retry "
                f"({reapplied} of {self._known_unfiltered_total})"
            )

    def _download_one_page_attempt(
        self, page: Page, page_number: int, expected_filtered_total: int, dest_dir: Path
    ) -> Path:
        if page_number > 1:
            # `nav.c-pagination > ul.c-pagination__list > li > a.c-pagination__item`,
            # current page marked by `li.is-active` (confirmed against the
            # live UI, 2026-08-11). `get_by_text(exact=True)` scoped to this
            # class avoids matching an unrelated "2" elsewhere on the page.
            # The list is rendered twice (top + bottom pagination bars), so
            # every locator here must be scoped with `.first`.
            page.locator(f"a.c-pagination__item:text-is('{page_number}')").first.click()
            page.wait_for_load_state("networkidle")
            active_page_text = page.locator(
                "li.is-active a.c-pagination__item"
            ).first.inner_text()
            if active_page_text.strip() != str(page_number):
                raise JobcanAtsError(
                    f"page {page_number}: pagination click landed on "
                    f"{active_page_text.strip()!r} instead"
                )

        current_total = parse_total_count(page.inner_text(_COUNT_TEXT_SELECTOR))
        if current_total != expected_filtered_total:
            raise JobcanAtsError(
                f"page {page_number}: filtered count changed mid-download "
                f"({expected_filtered_total} -> {current_total})"
            )

        # Checked-state read before clicking (not a blind click) — clicking
        # an already-checked header checkbox toggles every row OFF instead
        # of on. `<thead><tr><th><label class="c-checkbox"><input
        # type="checkbox">...` confirmed against the live UI, 2026-08-11.
        header_checkbox = page.locator("thead input[type='checkbox']").first
        if not header_checkbox.is_checked():
            page.locator("thead label").first.click()

        visible_rows = page.locator("table tbody tr").count()
        # Polled rather than read once immediately after the click: the SPA
        # takes a moment to flip every row's checkbox state after select-all
        # (confirmed against the live UI, 2026-08-11 — an instant read
        # produced a false-positive "0 checked" on a healthy page). Scoped to
        # `tbody` specifically (codex review finding, 2026-08-11): counting
        # ALL checked checkboxes — including the header's own — let the poll
        # exit the instant the header toggled, before the SPA had propagated
        # that state to any row, so a bulk action could fire against an
        # empty or partially-selected page. The exit condition is now "every
        # visible row is checked", not merely "at least one is". A genuine
        # permission problem (view-only role, empty `<td></td>` row cells —
        # the exact symptom this session's manual investigation hit) never
        # reaches that count no matter how long this polls, so it still
        # fails loudly rather than hanging on a button that will never
        # enable.
        checked_count = 0
        deadline = time.monotonic() + (self.config.action_timeout_ms / 1000)
        while time.monotonic() < deadline:
            checked_count = page.eval_on_selector_all(
                'table tbody input[type="checkbox"]:checked', "els => els.length"
            )
            if checked_count >= visible_rows > 0:
                break
            time.sleep(0.2)
        if checked_count < visible_rows or visible_rows < 1:
            raise JobcanAtsError(
                f"page {page_number}: select-all produced {checked_count} checked "
                f"rows out of {visible_rows} visible — the account's role likely "
                "lacks 求人の登録・編集 permission (row checkboxes do not render)"
            )

        bulk_action_index = pick_select_index(
            _all_select_option_labels(page), "一括アクションを選択"
        )
        bulk_select = page.locator("select").nth(bulk_action_index)
        bulk_select.select_option(value="output_file_utf8")
        assert_safe_bulk_action("output_file_utf8", _read_selected_label(bulk_select))

        assert_safe_bulk_action("output_file_utf8", _read_selected_label(bulk_select))
        page.click(f"button:has-text('{_EXECUTE_BUTTON_TEXT}')")

        assert_safe_bulk_action("output_file_utf8", _read_selected_label(bulk_select))
        with page.expect_download(timeout=self.config.download_timeout_ms) as download_info:
            page.click(f"button:has-text('{_CONFIRM_BUTTON_TEXT}')")
        download = download_info.value

        dest_path = dest_dir / f"page_{page_number}.csv"
        download.save_as(dest_path)

        if dest_path.stat().st_size == 0:
            raise JobcanAtsError(f"page {page_number}: downloaded CSV is empty ({dest_path})")

        return dest_path
