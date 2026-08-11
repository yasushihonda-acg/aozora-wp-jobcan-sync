"""Tests for `jobcan_ats.py`'s safety guards (CSV-migration follow-up,
2026-08-11) — the destructive-operation-prevention layer for the ATS bulk-
action dropdown.

None of these tests launch a browser: `assert_safe_bulk_action`,
`pick_select_index`, `pick_page_size_select_index`, and `parse_total_count`
are all pure functions operating on plain Python values, by design (see
`jobcan_ats.py`'s module docstring) — every branch is reachable without
Playwright installed.

`_REAL_BULK_ACTION_OPTIONS` is the actual 16-entry `<option>` list captured
from the live `ats.jobcan.jp/job_offers` bulk-action dropdown during this
session's investigation (2026-08-10). The `output_file`/`output_file_utf8`
values are the exact real values observed; the remaining destructive
options' real `value` attributes were not fully captured mid-session, so
placeholder values are used for those — irrelevant to what this test proves,
since `assert_safe_bulk_action` rejects any value outside the two-entry
whitelist regardless of what that value's string actually is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.jobcan_ats import (
    CSV_DOWNLOAD_ACTIONS,
    assert_safe_bulk_action,
    parse_total_count,
    pick_page_size_select_index,
    pick_select_index,
)
from sync.models import JobcanAtsSafetyError, JobcanStructureChangeError

# (value, label) — placeholder excluded. First 4 are CSV exports (2 safe +
# 2 Indeed-PLUS variants that must still be rejected, being neither
# whitelisted nor actually needed); remaining 11 are destructive mutations.
_REAL_BULK_ACTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("output_file", "CSVファイルをダウンロード"),
    ("output_file_utf8", "CSVファイルをダウンロード (UTF-8)"),
    ("output_indeed_job_file", "Indeed PLUS CSVファイルをダウンロード"),
    ("output_indeed_job_file_utf8", "Indeed PLUS CSVファイルをダウンロード (UTF-8)"),
    ("agent_open", "エージェントに公開する"),
    ("agent_close", "エージェントに非公開にする"),
    ("publish", "求人ページを公開する"),
    ("unpublish", "求人ページを非公開にする"),
    ("limited_open", "限定公開求人を有効にする"),
    ("limited_close", "限定公開求人を無効にする"),
    ("entry_open", "求人ページエントリーを受付中にする"),
    ("entry_close", "求人ページエントリーを停止する"),
    ("job_active", "求人をアクティブにする"),
    ("job_inactive", "求人を非アクティブにする"),
    ("job_delete", "求人を削除する"),
)


def test_exactly_two_of_the_fifteen_real_options_pass() -> None:
    passed = []
    for value, label in _REAL_BULK_ACTION_OPTIONS:
        try:
            assert_safe_bulk_action(value, label)
        except JobcanAtsSafetyError:
            continue
        passed.append(value)
    assert passed == ["output_file", "output_file_utf8"]


@pytest.mark.parametrize("value,label", _REAL_BULK_ACTION_OPTIONS)
def test_every_real_option_is_classified_correctly(value: str, label: str) -> None:
    is_csv_download = value in CSV_DOWNLOAD_ACTIONS
    if is_csv_download:
        assert_safe_bulk_action(value, label)  # must NOT raise
    else:
        with pytest.raises(JobcanAtsSafetyError):
            assert_safe_bulk_action(value, label)


def test_relabelled_whitelisted_value_is_rejected() -> None:
    """Guards against Jobcan silently reassigning `output_file` to a
    different action — the whitelist alone would miss this."""
    with pytest.raises(JobcanAtsSafetyError, match="labelled"):
        assert_safe_bulk_action("output_file", "求人を削除する")


def test_forbidden_substring_check_is_independent_of_prefix_check() -> None:
    """A hypothetical label that both starts with the CSV prefix AND
    contains a forbidden word must still be rejected — the two checks are
    ANDed, not a simple prefix-then-stop."""
    with pytest.raises(JobcanAtsSafetyError, match="削除"):
        assert_safe_bulk_action("output_file", "CSVファイルをダウンロードして削除する")


def test_never_selects_bulk_action_by_index_or_label() -> None:
    """Source-level guard: `select_option` for the bulk-action dropdown must
    always use `value=`, never `index=`/`label=` — a future refactor that
    reintroduces positional or label-based selection loses the whitelist
    entirely. Scoped to `_download_one_page_attempt`'s body (not the whole
    file) since `_set_page_size` legitimately uses `label=` for the
    表示件数 (page-size) dropdown, which carries no safety risk."""
    source = (Path(__file__).parents[1] / "src" / "sync" / "jobcan_ats.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _download_one_page_attempt")
    end = source.index("\ndef ", start + 1) if "\ndef " in source[start + 1 :] else len(source)
    body = source[start:end]
    assert "select_option(index=" not in body
    assert "select_option(label=" not in body
    assert 'select_option(value="output_file_utf8")' in body


def test_assertion_runs_at_least_three_times_per_page_download() -> None:
    """Pins the "three assertion points before each irreversible click"
    design (after select, before 実行, before 確定) as a source-level count,
    not just a functional test — losing one of the three call sites would
    still pass every other test in this file but weaken the defence."""
    source = (Path(__file__).parents[1] / "src" / "sync" / "jobcan_ats.py").read_text(
        encoding="utf-8"
    )
    start = source.index("def _download_one_page_attempt")
    end = source.index("\ndef ", start + 1) if "\ndef " in source[start + 1 :] else len(source)
    body = source[start:end]
    assert body.count("assert_safe_bulk_action(") >= 3


class TestParseTotalCount:
    def test_typical_unfiltered_text(self) -> None:
        assert parse_total_count("471件中 1-20件を表示") == 471

    def test_typical_filtered_text(self) -> None:
        assert parse_total_count("382件中 1-100件を表示") == 382

    def test_no_digits_raises_structure_change_error(self) -> None:
        with pytest.raises(JobcanStructureChangeError):
            parse_total_count("該当する求人がありません")


class TestPickSelectIndex:
    def test_finds_the_unique_matching_select(self) -> None:
        options = [
            ["一括アクションを選択", "CSVファイルをダウンロード"],
            ["公開状況", "公開", "非公開"],
        ]
        assert pick_select_index(options, "公開状況") == 1

    def test_zero_matches_raises_with_observed_placeholders(self) -> None:
        options = [["一括アクションを選択"], ["公開状況"]]
        with pytest.raises(JobcanStructureChangeError, match="found 0"):
            pick_select_index(options, "エントリー受付")

    def test_multiple_matches_raises(self) -> None:
        options = [["公開状況"], ["公開状況"]]
        with pytest.raises(JobcanStructureChangeError, match="found 2"):
            pick_select_index(options, "公開状況")

    def test_renamed_placeholder_raises_with_full_observed_list(self) -> None:
        options = [["公開ステータス", "公開", "非公開"]]
        with pytest.raises(JobcanStructureChangeError, match="公開ステータス"):
            pick_select_index(options, "公開状況")


class TestPickPageSizeSelectIndex:
    def test_finds_the_unique_page_size_select(self) -> None:
        options = [
            ["一括アクションを選択", "CSVファイルをダウンロード"],
            ["20件を表示", "50件を表示", "100件を表示"],
        ]
        assert pick_page_size_select_index(options) == 1

    def test_no_matching_select_raises(self) -> None:
        options = [["一括アクションを選択"], ["公開状況"]]
        with pytest.raises(JobcanStructureChangeError):
            pick_page_size_select_index(options)
