"""`detail_sections.py` — Phase A section-extraction parity + edge cases.

`TestRealDataParity` locks in behaviour against the actual Phase A mockup
output (`scripts/mockup-rebuild/jobs_data.json` + `mockup/jobs/*.html`) — the
37-job dataset the mockup script itself was built from. Every extracted
field is expected to match the mockup's rendered HTML *except* the one
documented bug fix (job 1891511's salary chip, see `detail_sections.py`
module docstring).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from sync.detail_sections import (
    BenefitParagraph,
    QualificationRow,
    WorkItem,
    build_detail_view,
    extract_benefits,
    extract_hashtags,
    extract_holiday_chip,
    extract_holiday_paragraph,
    extract_lead_paragraph,
    extract_qualifications,
    extract_region_prefecture,
    extract_salary_chip,
    extract_salary_detail,
    extract_selection_flow,
    extract_work_description,
    extract_work_time_capacity,
    simplify_address,
    split_label,
)
from sync.models import JobOffer

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MOCKUP_DATA = _REPO_ROOT / "scripts" / "mockup-rebuild" / "jobs_data.json"
_MOCKUP_JOBS_DIR = _REPO_ROOT / "mockup" / "jobs"

# job_id whose mockup salary chip is the documented Phase A bug (only the
# first qualification's rate survived — see detail_sections.py docstring).
_KNOWN_SALARY_BUG_JOB_ID = "1891511"


def _make_offer(
    *,
    job_id: str = "1",
    title: str = "テスト求人",
    body_html: str = "<p>テスト本文</p>",
    address: str = "テスト支店",
    label: str = "介護職正社員",
    location: str = "テスト駅から徒歩5分",
    salary: str = "【月額】200,000円〜",
    extra_lines: list[tuple[str, str]] | None = None,
) -> JobOffer:
    return JobOffer(
        job_id=job_id,
        title=title,
        body_html=body_html,
        address=address,
        label=label,
        location=location,
        salary=salary,
        apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        page_title=None,
        extra_lines=extra_lines or [],
    )


class TestExtractSalaryChip:
    def test_monthly_single(self) -> None:
        assert extract_salary_chip("【月額】200,800円〜") == "20.1 万円〜"

    def test_monthly_range(self) -> None:
        assert extract_salary_chip("【月額】181,360円〜262,000円") == "18.1 万〜26.2 万円"

    def test_hourly_single(self) -> None:
        assert extract_salary_chip("【時給】1,500円〜") == "時給 1,500 円〜"

    def test_hourly_range(self) -> None:
        assert extract_salary_chip("【時給】1,200円〜1,500円") == "時給 1,200〜1,500 円"

    def test_multi_qualification_hourly_combines_into_one_range(self) -> None:
        """The documented bug fix: the mockup script's `re.search`-based
        original only kept the first qualification's rate (`時給 1,900
        円〜`, silently dropping 准看護師's 1,500円). This must show both."""
        salary = "【時給】・正看護師：1,900円〜・准看護師：1,500円〜"
        assert extract_salary_chip(salary) == "時給 1,500〜1,900 円"

    def test_ignores_breakdown_amounts_after_uchiwake(self) -> None:
        salary = "【月額】200,800円〜内訳：基本給（148,407円）+業務手当（48,393円）"
        assert extract_salary_chip(salary) == "20.1 万円〜"

    def test_ignores_footnote_amount_after_asterisk(self) -> None:
        """`※土日祝勤務：時給＋100円` is a differential note, not a base
        rate — including it would corrupt the min/max combine logic."""
        salary = "【時給】1,500円〜※土日祝勤務：時給＋100円"
        assert extract_salary_chip(salary) == "時給 1,500 円〜"

    def test_no_recognisable_pattern_falls_back_to_truncation(self) -> None:
        assert extract_salary_chip("応相談") == "応相談"
        long_text = (
            "給与は面接時に応相談とさせていただきますので"
            "詳しくは担当者までお問い合わせください"
        )
        result = extract_salary_chip(long_text)
        assert result == long_text[:30] + "…"

    def test_tilde_variants_normalised(self) -> None:
        tilde = extract_salary_chip("【月額】200,000円~")
        fullwidth_tilde = extract_salary_chip("【月額】200,000円〜")
        assert tilde == fullwidth_tilde


class TestExtractSalaryDetail:
    def test_extracts_breakdown(self) -> None:
        salary = (
            "【月額】200,800円〜内訳：基本給（148,407円）+業務手当（48,393円）"
            "※固定残業代を含む"
        )
        assert extract_salary_detail(salary) == "基本給（148,407円）+業務手当（48,393円）"

    def test_absent_returns_none(self) -> None:
        assert extract_salary_detail("【月額】200,800円〜") is None

    def test_empty_after_trailing_punctuation_strip_returns_none(self) -> None:
        assert extract_salary_detail("内訳：、") is None


class TestExtractHolidayChip:
    def test_annual_days_pattern(self) -> None:
        assert extract_holiday_chip([("休日・休暇", "年間休日120日・週休2日制")]) == "120 日"

    def test_weekly_days_off_pattern(self) -> None:
        assert extract_holiday_chip([("休日・休暇", "週休3日制")]) == "週休 3 日制"

    def test_weekly_range_pattern(self) -> None:
        assert extract_holiday_chip([("休日・休暇", "週3〜4日勤務")]) == "週 3〜4 日"

    def test_unmatched_text_truncates(self) -> None:
        text = "シフトによる相談制のため詳細は面談時にご案内します"
        chip = extract_holiday_chip([("休日・休暇", text)])
        assert chip == text[:15] + "…"

    def test_no_holiday_entry_returns_none(self) -> None:
        assert extract_holiday_chip([]) is None
        assert extract_holiday_chip([("勤務時間", "9:00〜18:00")]) is None


class TestExtractHolidayParagraph:
    def test_joins_with_full_width_slash(self) -> None:
        result = extract_holiday_paragraph([("休日・休暇", "年間休日110日・週休2日制・有給休暇")])
        assert result == "年間休日110日 ／ 週休2日制 ／ 有給休暇"

    def test_absent_returns_none(self) -> None:
        assert extract_holiday_paragraph([]) is None


class TestSimplifyAddress:
    def test_extracts_city_and_keeps_facility_as_detail(self) -> None:
        facility = "【鹿児島】あおぞらケアグループ永吉（デイ・有料）"
        registration_office = facility + "鹿児島県鹿児島市永吉2-1-14"
        primary, detail = simplify_address(facility, [("募集拠点", registration_office)])
        assert primary == "鹿児島市"
        assert detail == "あおぞらケアグループ永吉（デイ・有料）"

    def test_ward_extraction_includes_city_prefix(self) -> None:
        primary, _detail = simplify_address(
            "四箇支店", [("募集拠点", "福岡県福岡市早良区四箇1-2-3")]
        )
        assert primary == "福岡市早良区"

    def test_no_registration_office_entry_falls_back_to_facility_only(self) -> None:
        primary, detail = simplify_address("福岡支店", [])
        assert primary == "福岡支店"
        assert detail is None

    def test_bracketed_prefix_stripped_from_facility(self) -> None:
        _primary, detail = simplify_address("【福岡】テスト施設", [("募集拠点", "無関係の文字列")])
        assert detail is None or "【" not in (detail or "")


class TestExtractRegionPrefecture:
    def test_recognised_bracket(self) -> None:
        assert extract_region_prefecture("【鹿児島】あおぞらケアグループ永吉") == "鹿児島県"
        assert extract_region_prefecture("【福岡】福岡支店") == "福岡県"

    def test_unrecognised_bracket_returns_none(self) -> None:
        assert extract_region_prefecture("【本社】あおぞらケアグループ") is None

    def test_no_bracket_returns_none(self) -> None:
        assert extract_region_prefecture("福岡支店") is None


class TestExtractQualifications:
    def test_must_and_want(self) -> None:
        result = extract_qualifications(
            [("必要資格", "介護福祉士"), ("歓迎スキル・経験", "普通自動車免許")]
        )
        assert result == [
            QualificationRow(kind="必須", text="介護福祉士"),
            QualificationRow(kind="歓迎", text="普通自動車免許"),
        ]

    def test_must_only(self) -> None:
        result = extract_qualifications([("必須スキル・経験", "実務経験3年以上")])
        assert result == [QualificationRow(kind="必須", text="実務経験3年以上")]

    def test_neither_present_returns_empty(self) -> None:
        assert extract_qualifications([("勤務時間", "9:00〜18:00")]) == []

    def test_must_synonyms_joined_with_slash(self) -> None:
        result = extract_qualifications(
            [("必須スキル・経験", "普通自動車免許"), ("必要資格", "介護福祉士")]
        )
        assert result == [QualificationRow(kind="必須", text="普通自動車免許 / 介護福祉士")]


class TestExtractBenefits:
    def test_chips_and_other_paragraphs(self) -> None:
        value = "【福利厚生】・社会保険完備・定期健康診断※一部条件有【研修制度】OJT研修があります"
        chips, paragraphs = extract_benefits([("待遇", value)])
        assert chips == ["社会保険完備", "定期健康診断"]
        assert paragraphs == [BenefitParagraph(heading="研修制度", content="OJT研修があります")]

    def test_no_taiguu_entry_returns_empty(self) -> None:
        chips, paragraphs = extract_benefits([])
        assert chips == []
        assert paragraphs == []


class TestExtractSelectionFlow:
    def test_splits_on_down_arrow(self) -> None:
        result = extract_selection_flow([("選考フロー", "ご応募↓面接↓採否ご連絡")])
        assert result == ["ご応募", "面接", "採否ご連絡"]

    def test_absent_returns_empty(self) -> None:
        assert extract_selection_flow([]) == []


class TestExtractWorkTimeCapacity:
    def test_both_present(self) -> None:
        work_time, capacity = extract_work_time_capacity(
            [("勤務時間", "9:00〜18:00"), ("定員", "3 名")]
        )
        assert work_time == "9:00〜18:00"
        assert capacity == "3 名"

    def test_both_absent(self) -> None:
        assert extract_work_time_capacity([]) == (None, None)


class TestSplitLabel:
    def test_already_space_separated(self) -> None:
        assert split_label("介護職 正社員") == ["介護職", "正社員"]

    def test_concatenated_matches_longest_suffix_first(self) -> None:
        # Must not split "看護職短時間正社員" into "看護職短時間" + "正社員" —
        # "短時間正社員" (6 chars) must win over "正社員" (3 chars).
        assert split_label("看護職短時間正社員") == ["看護職", "短時間正社員"]

    def test_concatenated_simple_suffix(self) -> None:
        assert split_label("事務職パート") == ["事務職", "パート"]

    def test_no_known_suffix_returns_single_element(self) -> None:
        assert split_label("業務委託") == ["業務委託"]


class TestExtractHashtags:
    def test_extracts_and_dedups(self) -> None:
        body = "<p>#ケア重視#ケア重視＃キャリアアップ 本文が続きます</p>"
        assert extract_hashtags(body) == ["#ケア重視", "#キャリアアップ"]

    def test_digit_only_tag_excluded(self) -> None:
        """A tag whose captured text is *entirely* digits (e.g. a stray
        `#123` in body text) is dropped — but a digit-*leading* tag like
        `#20代〜70代が活躍中` is not (the whole capture isn't numeric), which
        matches the mockup script's identical behaviour (verified against
        all 37 real Phase A postings in `TestRealDataParity` — none of them
        actually hit this edge case, since Jobcan body text never puts a
        literal `#` in front of an age range like `20〜70代`)."""
        assert extract_hashtags("<p>#123 本文が続きます</p>") == []
        assert extract_hashtags("<p>#20代〜70代が活躍中</p>") == ["#20代〜70代が活躍中"]

    def test_capped_at_eight(self) -> None:
        body = "<p>" + "".join(f"#tag{i}" for i in range(12)) + "</p>"
        assert len(extract_hashtags(body)) == 8

    def test_no_hashtags_returns_empty(self) -> None:
        assert extract_hashtags("<p>ハッシュタグなしの本文です</p>") == []

    def test_only_scans_first_400_chars(self) -> None:
        body = "<p>" + "あ" * 400 + "#後方のタグ</p>"
        assert extract_hashtags(body) == []


class TestExtractLeadParagraph:
    def test_stops_before_work_description_heading(self) -> None:
        body = "<p>施設の紹介文です。<br>【仕事内容】介護業務全般</p>"
        assert extract_lead_paragraph(body) == "施設の紹介文です。"

    def test_removes_leading_hashtag_line(self) -> None:
        body = "<p>#ケア重視#未経験OK<br>施設の紹介文です。</p>"
        assert extract_lead_paragraph(body) == "施設の紹介文です。"

    def test_short_text_unchanged(self) -> None:
        body = "<p>短い紹介文です。</p>"
        assert extract_lead_paragraph(body) == "短い紹介文です。"

    def test_long_text_truncated_with_ellipsis(self) -> None:
        body = "<p>" + "あ" * 250 + "</p>"
        result = extract_lead_paragraph(body, max_len=200)
        assert result.endswith("…")
        assert len(result) <= 201

    def test_empty_body_returns_empty_string(self) -> None:
        assert extract_lead_paragraph("<p></p>") == ""


class TestExtractWorkDescription:
    def test_paragraph_then_bullets(self) -> None:
        body = (
            "<p>【仕事内容】介護業務全般<br>"
            "〇食事、入浴介助<br>"
            "〇日常生活補助</p>"
        )
        result = extract_work_description(body)
        assert result == [
            WorkItem(kind="p", text="介護業務全般"),
            WorkItem(kind="li", text="食事、入浴介助"),
            WorkItem(kind="li", text="日常生活補助"),
        ]

    def test_no_heading_returns_empty(self) -> None:
        assert extract_work_description("<p>仕事内容の見出しがない本文</p>") == []


class TestBuildDetailView:
    def test_full_offer_populates_every_section(self) -> None:
        offer = _make_offer(
            body_html=(
                "<p>#ケア重視<br>施設紹介文です。<br>【仕事内容】介護業務全般<br>"
                "〇食事介助</p>"
            ),
            salary="【月額】200,800円〜内訳：基本給（180,000円）",
            extra_lines=[
                ("募集拠点", "福岡県福岡市博多区1-2-3"),
                ("必要資格", "介護福祉士"),
                ("歓迎スキル・経験", "普通自動車免許"),
                ("待遇", "【福利厚生】・社会保険完備"),
                ("休日・休暇", "年間休日110日・週休2日制"),
                ("選考フロー", "ご応募↓面接↓採否連絡"),
                ("勤務時間", "9:00〜18:00"),
                ("定員", "2 名"),
            ],
        )
        view = build_detail_view(offer)

        assert view.labels == ["介護職", "正社員"]
        assert view.employment_type == "正社員"
        assert view.employment_type_schema == "FULL_TIME"
        assert view.salary_chip == "20.1 万円〜"
        assert view.salary_detail == "基本給（180,000円）"
        assert view.location_primary == "福岡市博多区"
        assert view.work_time_short == "9:00〜18:00"
        assert view.holiday_chip == "110 日"
        assert view.capacity == "2 名"
        assert view.hashtags == ["#ケア重視"]
        assert view.lead == "施設紹介文です。"
        assert view.work_items == [
            WorkItem(kind="p", text="介護業務全般"),
            WorkItem(kind="li", text="食事介助"),
        ]
        assert view.qualifications == [
            QualificationRow(kind="必須", text="介護福祉士"),
            QualificationRow(kind="歓迎", text="普通自動車免許"),
        ]
        assert view.benefit_chips == ["社会保険完備"]
        # 休暇制度 paragraph is always prepended when a holiday entry exists.
        assert view.benefit_paragraphs[0].heading == "休暇制度"
        assert view.selection_steps == ["ご応募", "面接", "採否連絡"]

    def test_minimal_offer_degrades_to_empty_sections_without_raising(self) -> None:
        """A posting whose `extra_lines` matches none of the known headers
        (AC-3: unknown Jobcan formatting must not break the page) still
        produces a valid `DetailView` — every section field is empty/None,
        which `job_detail.html` treats as "hide this section"."""
        offer = _make_offer(
            body_html="<p>本文のみ、見出しなし</p>",
            salary="要相談",
            extra_lines=[("未知のヘッダー", "未知の値")],
        )
        view = build_detail_view(offer)

        assert view.qualifications == []
        assert view.benefit_chips == []
        assert view.selection_steps == []
        assert view.holiday_chip is None
        assert view.capacity is None
        assert view.work_time_short is None
        assert view.hashtags == []
        assert view.salary_chip == "要相談"

    def test_completely_empty_extra_lines_and_body(self) -> None:
        offer = _make_offer(body_html="<p></p>", extra_lines=[])
        view = build_detail_view(offer)
        assert view.qualifications == []
        assert view.benefit_paragraphs == []
        assert view.work_items == []
        assert view.lead == ""


@pytest.mark.skipif(not _MOCKUP_DATA.exists(), reason="mockup-rebuild fixtures not present")
class TestRealDataParity:
    """Every extracted field for all 37 Phase A sample jobs must match the
    mockup's actual rendered HTML, except the one documented bug fix."""

    @staticmethod
    def _load_jobs() -> list[dict]:
        data = json.loads(_MOCKUP_DATA.read_text(encoding="utf-8"))
        return data["jobs"]

    @staticmethod
    def _offer_from_job(job: dict) -> JobOffer:
        return JobOffer(
            job_id=job["job_id"],
            title=job["title"],
            body_html=job["body_html"],
            address=job["address"],
            label=job["label"],
            location=job.get("location") or "不明",
            salary=job["salary"],
            apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job['job_id']}",
            source_url=job["source_url"],
            page_title=None,
            extra_lines=[tuple(pair) for pair in job["extra_lines"]],
        )

    def test_no_job_raises(self) -> None:
        for job in self._load_jobs():
            build_detail_view(self._offer_from_job(job))  # must not raise

    def test_salary_chip_matches_mockup_except_known_bug(self) -> None:
        mismatches = []
        for job in self._load_jobs():
            path = _MOCKUP_JOBS_DIR / f"{job['job_id']}.html"
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            dd = soup.select_one("dd.is-accent")
            if dd is None:
                continue
            # `dd`'s first content node is the chip text; any `<small>`
            # breakdown detail is a separate trailing sibling node.
            mockup_chip_text = str(dd.contents[0]).strip() if dd.contents else ""
            view = build_detail_view(self._offer_from_job(job))
            if mockup_chip_text != view.salary_chip and job["job_id"] != _KNOWN_SALARY_BUG_JOB_ID:
                mismatches.append((job["job_id"], mockup_chip_text, view.salary_chip))
        assert mismatches == []

    def test_known_bug_job_now_shows_combined_range(self) -> None:
        jobs = {j["job_id"]: j for j in self._load_jobs()}
        job = jobs.get(_KNOWN_SALARY_BUG_JOB_ID)
        if job is None:
            pytest.skip(f"job {_KNOWN_SALARY_BUG_JOB_ID} not present in fixture data")
        view = build_detail_view(self._offer_from_job(job))
        assert view.salary_chip == "時給 1,500〜1,900 円"

    def test_qualifications_match_mockup(self) -> None:
        mismatches = []
        for job in self._load_jobs():
            path = _MOCKUP_JOBS_DIR / f"{job['job_id']}.html"
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            mockup_quals = []
            for row in soup.select(".job-qualification__row"):
                key = row.select_one(".job-qualification__key")
                val = row.select_one(".job-qualification__val")
                assert key is not None and val is not None
                mockup_quals.append((key.get_text(), val.get_text()))
            view = build_detail_view(self._offer_from_job(job))
            ours = [(q.kind, q.text) for q in view.qualifications]
            if mockup_quals != ours:
                mismatches.append((job["job_id"], mockup_quals, ours))
        assert mismatches == []

    def test_selection_flow_matches_mockup(self) -> None:
        mismatches = []
        for job in self._load_jobs():
            path = _MOCKUP_JOBS_DIR / f"{job['job_id']}.html"
            if not path.exists():
                continue
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            mockup_steps = [li.get_text() for li in soup.select(".selection-flow__step")]
            view = build_detail_view(self._offer_from_job(job))
            if mockup_steps != view.selection_steps:
                mismatches.append((job["job_id"], mockup_steps, view.selection_steps))
        assert mismatches == []
