"""Derives the Phase A job-detail page sections from a `JobOffer`.

Phase A (`mockup/jobs/*.html`) was hand-generated once by
`scripts/mockup-rebuild/rewrite_job_details.py`, which extracts hero copy,
summary fields, and four content sections (仕事内容/応募資格/待遇・福利厚生/
選考の流れ) from a Jobcan posting's `extra_lines` (header/value table rows)
and `body_html`. That script operated on a 37-job static snapshot
(`scripts/mockup-rebuild/jobs_data.json`) and wrote its output straight into
mockup HTML files via string concatenation.

This module ports the *data-extraction* half of that script (not the HTML
generation, which `job_detail.html` now owns as a Jinja2 template) so the
same section structure can be derived at request time from any of the 382
live Firestore postings — `JobSnapshot.offer.extra_lines` round-trips through
`firestore_repo._decode_extra_lines` into the same `list[tuple[str, str]]`
shape the mockup script consumed, so the extraction rules translate exactly.

Two behaviours were deliberately changed relative to the mockup script (both
occur unavoidably now that this runs across 382 real postings instead of a
hand-curated sample of 37):

- `_extract_salary_chip` collects *every* amount match instead of only the
  first, so a multi-qualification breakdown (e.g. `【時給】・正看護師：
  1,900円〜・准看護師：1,500円〜`) renders the full range instead of silently
  dropping every qualification after the first.
- Every field degrades to "absent" (`None` / empty list) rather than a
  truncated guess when nothing matches — `build_detail_view` never raises,
  and `job_detail.html` hides a section entirely when its data is empty
  (matching this module's "extraction only, no HTML" scope).
"""

from __future__ import annotations

import re
from typing import Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel

from .models import JobOffer

_WORK_DESCRIPTION_HEAD = "【仕事内容】"

# Longest-first so "看護職短時間正社員" splits into ("看護職", "短時間正社員"),
# not ("看護職短時間", "正社員") — mirrors
# `scripts/mockup-rebuild/rewrite_job_details.py::build_new_main_html` and
# `add_new_cards.py::split_label`, which this list must stay in sync with.
_EMPLOYMENT_SUFFIXES = sorted(
    ["正社員", "パート", "アルバイト", "契約社員", "短時間正社員", "パートアルバイト"],
    key=len,
    reverse=True,
)

# schema.org JobPosting `employmentType` has no exact match for 短時間正社員
# (reduced-hours but still permanent) — mapping it to FULL_TIME would overstate
# the hours commitment, so it's intentionally left unmapped (JSON-LD omits the
# field rather than guess).
_EMPLOYMENT_TYPE_SCHEMA: dict[str, str] = {
    "正社員": "FULL_TIME",
    "パート": "PART_TIME",
    "アルバイト": "PART_TIME",
    "パートアルバイト": "PART_TIME",
    "契約社員": "CONTRACTOR",
}

# This project operates in exactly these two prefectures (site footer copy,
# `mockup/jobs/*.html`) — `address`'s leading `【...】` bracket (when present)
# names one of them. Unlike the Phase A mockup script (which hardcoded
# `addressRegion: "福岡県"` for every posting, a known bug — see
# `docs/handoff/GOAL.md` PR #87 note), an unrecognised or absent bracket
# omits `addressRegion` from the JSON-LD rather than guessing wrong.
_REGION_TO_PREFECTURE: dict[str, str] = {
    "福岡": "福岡県",
    "鹿児島": "鹿児島県",
}


class QualificationRow(BaseModel):
    kind: Literal["必須", "歓迎"]
    text: str


class BenefitParagraph(BaseModel):
    heading: str
    content: str


class WorkItem(BaseModel):
    kind: Literal["p", "li"]
    text: str


class WorkBlock(BaseModel):
    """A run of consecutive `WorkItem`s collapsed into one renderable block —
    `kind="p"` carries `text`, `kind="ul"` carries `items`. Doing this
    grouping in Python (`group_work_items`) rather than in the Jinja template
    keeps `job_detail.html` from needing lookahead/lookbehind loop logic to
    decide where a `<ul>` opens and closes."""

    kind: Literal["p", "ul"]
    text: str = ""
    items: list[str] = []

    model_config = {"frozen": True}


class RelatedJob(BaseModel):
    """One `.aside-card__list` entry — same-category postings shown next to
    the current one (see `firestore_repo.get_by_category` / `app.py`)."""

    job_id: str
    title: str
    detail_url: str
    region_tag: str | None

    model_config = {"frozen": True}


class DetailView(BaseModel):
    """Everything `job_detail.html` needs beyond the raw `JobOffer` fields.

    Every field that drives a section is `None` / `[]` when nothing in
    `extra_lines`/`body_html` matched — the template hides that section
    entirely rather than rendering an empty heading.
    """

    labels: list[str]
    employment_type: str
    employment_type_schema: str | None

    salary_chip: str
    salary_detail: str | None

    location_primary: str
    location_detail: str | None

    work_time_short: str | None
    work_time_detail: str | None

    holiday_chip: str | None
    holiday_paragraph: str | None

    capacity: str | None

    hashtags: list[str]
    lead: str

    work_blocks: list[WorkBlock]
    qualifications: list[QualificationRow]
    benefit_chips: list[str]
    benefit_paragraphs: list[BenefitParagraph]
    selection_steps: list[str]

    region_prefecture: str | None

    model_config = {"frozen": True}


def _yen_to_man(yen: int) -> str:
    man = yen / 10000
    if man == int(man):
        return f"{int(man)}.0 万"
    return f"{man:.1f}".rstrip("0").rstrip(".") + " 万"


def _normalize_tilde(s: str) -> str:
    return s.replace("～", "〜").replace("~", "〜")


_AMOUNT_PAIR_RE = re.compile(r"([\d,]+)\s*円(?:\s*〜\s*([\d,]+)\s*円)?")


def _format_comma(n: int) -> str:
    return f"{n:,}"


def _format_amount_group(headline: str, *, to_man: bool) -> tuple[str, str, bool] | None:
    """Collects every `NNN円`/`NNN円〜MMM円` occurrence in `headline`.

    `_AMOUNT_PAIR_RE`'s trailing group is greedy about extending a bare
    amount into a range when a `〜MMM円` immediately follows, so a genuine
    `X円〜Y円` range is captured as a *single* match (lo=X, hi=Y) — it is
    never double-counted as two separate bare amounts.

    A posting with several qualifications each stating their own rate in the
    same field (e.g. `【時給】・正看護師：1,900円〜・准看護師：1,500円〜` — the
    label word appears once, not once per qualification, so it cannot be
    used to delimit each amount) yields several matches here; those collapse
    into one combined min–max chip instead of the mockup script's original
    behaviour of keeping only the first amount and silently dropping the
    rest (see module docstring).

    Returns `(formatted_lo, formatted_hi, is_combined)` — `is_combined` is
    True when either more than one occurrence was found, or a single
    occurrence was itself an explicit range; both render as `lo〜hi`. False
    means one bare amount, rendered as `lo〜` by the caller.
    """
    pairs = _AMOUNT_PAIR_RE.findall(headline)
    if not pairs:
        return None

    los: list[int] = []
    his: list[int] = []
    for lo, hi in pairs:
        lo_val = int(lo.replace(",", ""))
        los.append(lo_val)
        his.append(int(hi.replace(",", "")) if hi else lo_val)

    fmt = _yen_to_man if to_man else _format_comma
    is_range_or_multi = len(pairs) > 1 or bool(pairs[0][1])
    return fmt(min(los)), fmt(max(his)), is_range_or_multi


def extract_salary_chip(salary: str) -> str:
    """Format `salary` into a short summary chip.

    Only the text before `内訳` (the itemised allowance breakdown, handled
    separately by `extract_salary_detail`) or `※` (a footnote — commonly a
    weekend/holiday differential like `※土日祝勤務：時給＋100円`, whose amount
    is not a base rate and would otherwise get folded into the min/max) is
    scanned. This keeps allowance sub-amounts (基本給/業務手当/...), any
    `想定年収` figure, and footnote amounts out of the headline chip.
    Whichever label literal (`月額` or `時給`) appears first in that headline
    decides the unit; falls back to a 30-char truncation when neither is
    present or nothing matches.
    """
    s = _normalize_tilde(salary)
    headline = re.split(r"内訳|※", s, maxsplit=1)[0]

    if "月額" in headline:
        group = _format_amount_group(headline, to_man=True)
        if group:
            lo, hi, is_range = group
            return f"{lo}〜{hi}円" if is_range else f"{lo}円〜"
    elif "時給" in headline:
        group = _format_amount_group(headline, to_man=False)
        if group:
            lo, hi, is_range = group
            return f"時給 {lo}〜{hi} 円" if is_range else f"時給 {lo} 円〜"

    return s[:30] + ("…" if len(s) > 30 else "")


def extract_salary_detail(salary: str) -> str | None:
    """Pull the「内訳：...」breakdown out of `salary`, or `None` if absent."""
    s = _normalize_tilde(salary)
    m = re.search(r"内訳[：:]\s*(.+?)(?:※|$)", s, re.DOTALL)
    if not m:
        return None
    detail = m.group(1).strip().rstrip("、,。 ")
    return detail or None


_HOLIDAY_COUNT_RE = re.compile(r"年間休日\s*(\d+)\s*日")


def extract_holiday_chip(extra_lines: list[tuple[str, str]]) -> str | None:
    for k, v in extra_lines:
        if k != "休日・休暇":
            continue
        m = _HOLIDAY_COUNT_RE.search(v)
        if m:
            return f"{m.group(1)} 日"
        m = re.search(r"週休\s*(\d)\s*日制", v)
        if m:
            return f"週休 {m.group(1)} 日制"
        m = re.search(r"週\s*(\d+)\s*[〜~～]\s*(\d+)\s*日勤務", v)
        if m:
            return f"週 {m.group(1)}〜{m.group(2)} 日"
        m = re.search(r"週\s*(\d+)\s*日勤務", v)
        if m:
            return f"週 {m.group(1)} 日"
        return v[:15] + ("…" if len(v) > 15 else "")
    return None


def extract_holiday_paragraph(extra_lines: list[tuple[str, str]]) -> str | None:
    """休日・休暇 の全文を「・」区切りで読みやすく整形したもの、無ければ `None`。"""
    for k, v in extra_lines:
        if k != "休日・休暇":
            continue
        items = [
            s.strip().lstrip("・").strip()
            for s in v.split("・")
            if s.strip().lstrip("・").strip()
        ]
        return " ／ ".join(items) or None
    return None


_REGION_ADDRESS_RE = re.compile(
    r"(?:北海道|東京都|京都府|大阪府|[^県]+?県)((?:[^市区]+?市)(?:[^区]+?区)?|[^町村]+?[町村])"
)


def simplify_address(address: str, extra_lines: list[tuple[str, str]]) -> tuple[str, str | None]:
    """Returns (primary: city or facility name, detail: facility name if it
    differs from primary, else `None`)."""
    facility = re.sub(r"^【[^】]+】", "", address)
    raw_addr = ""
    for k, v in extra_lines:
        if k == "募集拠点":
            raw_addr = v
            break
    m = _REGION_ADDRESS_RE.search(raw_addr)
    city = m.group(1) if m else ""
    primary = city or facility
    detail = facility if (facility and primary != facility) else None
    return primary, detail


_REGION_BRACKET_RE = re.compile(r"^【([^】]+)】")


def extract_region_tag(address: str) -> str | None:
    """Returns `address`'s leading `【...】` bracket content verbatim (e.g.
    `"鹿児島"`), or `None` when absent. This is the short label
    `mockup/jobs/*.html`'s `.aside-card__meta` shows next to each related
    job (`福岡`, not `福岡県`) — `extract_region_prefecture` below builds on
    this for the JSON-LD's full prefecture name."""
    m = _REGION_BRACKET_RE.match(address)
    return m.group(1) if m else None


def extract_region_prefecture(address: str) -> str | None:
    """Maps `address`'s leading `【...】` bracket (e.g. `【鹿児島】...`) to a
    full prefecture name, or `None` when absent/unrecognised. See module
    docstring — this deliberately does NOT default to a single prefecture."""
    tag = extract_region_tag(address)
    if tag is None:
        return None
    return _REGION_TO_PREFECTURE.get(tag)


def extract_qualifications(extra_lines: list[tuple[str, str]]) -> list[QualificationRow]:
    must: list[str] = []
    want: list[str] = []
    for k, v in extra_lines:
        if k in ("必須スキル・経験", "必要資格"):
            must.append(v.strip())
        elif k == "歓迎スキル・経験":
            want.append(v.strip())
    out: list[QualificationRow] = []
    if must:
        out.append(QualificationRow(kind="必須", text=" / ".join(must)))
    if want:
        out.append(QualificationRow(kind="歓迎", text=" / ".join(want)))
    return out


def extract_benefits(
    extra_lines: list[tuple[str, str]],
) -> tuple[list[str], list[BenefitParagraph]]:
    """待遇 extras を chip リスト(【福利厚生】配下の・区切り項目)と
    補足段落リスト(【研修制度】等その他見出しブロック)に分解する。"""
    chips: list[str] = []
    paragraphs: list[BenefitParagraph] = []
    for k, v in extra_lines:
        if k != "待遇":
            continue
        sections = re.split(r"【([^】]+)】", v)
        for i in range(1, len(sections), 2):
            heading = sections[i].strip()
            content = sections[i + 1].strip() if i + 1 < len(sections) else ""
            if heading == "福利厚生":
                for item in re.split(r"[・•]", content):
                    stripped = item.strip()
                    stripped = re.sub(r"※[^・•]*$", "", stripped).strip()
                    if stripped:
                        chips.append(stripped)
            else:
                paragraphs.append(BenefitParagraph(heading=heading, content=content))
    return chips, paragraphs


_LEADING_CIRCLED_NUMBER = re.compile(r"^[①-⑳]\s*")


def extract_selection_flow(extra_lines: list[tuple[str, str]]) -> list[str]:
    """Jobcan の「選考フロー」を `↓` で分割してステップ一覧にする。

    投稿によって担当者が手入力で先頭に丸数字(①②③…)を付けているものと
    付けていないものが混在する(`mockup/jobs/*.html` の実データで確認)。
    `job_detail.html` 側 (`.selection-flow__step::before`) が既に連番の
    バッジを描画するため、丸数字付きの投稿だけ番号が二重表示されていた
    (decision-maker報告、2026-08-14)。先頭の丸数字だけを取り除き、丸数字が
    無い投稿はそのまま(`\\s*` が 0 文字マッチするだけで実質無変化)。"""
    for k, v in extra_lines:
        if k != "選考フロー":
            continue
        return [
            _LEADING_CIRCLED_NUMBER.sub("", s.strip())
            for s in v.split("↓")
            if s.strip()
        ]
    return []


def extract_work_time_capacity(extra_lines: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """Returns (work_time, capacity) — the raw `勤務時間`/`定員` values, or
    `None` for whichever is absent. Short-form truncation for display is the
    caller's job (`build_detail_view`), matching the summary's
    `<dd>{short}<small>{detail}</small></dd>` split."""
    work_time: str | None = None
    capacity: str | None = None
    for k, v in extra_lines:
        if k == "勤務時間":
            work_time = v.strip() or None
        elif k == "定員":
            capacity = v.strip() or None
    return work_time, capacity


def split_label(label: str) -> list[str]:
    """Splits a Jobcan `label` field into job-type + employment-form tags.

    Real Jobcan labels are a single unbroken string (`"事務職正社員"`), so the
    whitespace-split below almost never fires — but the mockup script tried
    it first, so this keeps the same order for parity. The fallback matches
    the longest known employment-form suffix (`_EMPLOYMENT_SUFFIXES`) to
    avoid splitting `"看護職短時間正社員"` into `"看護職短時間"` + `"正社員"`.
    """
    labels = label.split()
    if labels and len(labels) >= 2:
        return labels
    for suffix in _EMPLOYMENT_SUFFIXES:
        if label.endswith(suffix):
            return [label[: -len(suffix)].strip(), suffix]
    return [label]


def extract_hashtags(body_html: str) -> list[str]:
    """Pulls up to 8 `#tag` hashtags out of `body_html`'s first 400 chars."""
    soup = BeautifulSoup(body_html, "lxml")
    text = soup.get_text(separator="\n")
    head = text[:400]
    tags: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(r"[#＃]\s*([^\s#＃◆■★●※【\n、。]+)")
    for m in pattern.finditer(head):
        tag = m.group(1).strip()
        if not tag or tag.isdigit():
            continue
        if tag in seen:
            continue
        seen.add(tag)
        tags.append(f"#{tag}")
        if len(tags) >= 8:
            break
    return tags


def extract_lead_paragraph(body_html: str, max_len: int = 200) -> str:
    """`body_html` → hashtag-line removal → text before `【仕事内容】`."""
    soup = BeautifulSoup(body_html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    body_lines: list[str] = []
    for ln in lines:
        if re.fullmatch(r"(?:[#＃]\s*[^\s#＃]+\s*)+", ln):
            continue
        body_lines.append(ln)

    cut: list[str] = []
    for ln in body_lines:
        if _WORK_DESCRIPTION_HEAD in ln:
            head = ln.split(_WORK_DESCRIPTION_HEAD)[0].strip()
            if head:
                cut.append(head)
            break
        cut.append(ln)

    text = " ".join(cut)
    text = re.sub(r"^(?:[#＃]\s*[^\s#＃]+\s*)+", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if len(text) <= max_len:
        return text
    window = text[: max_len + 40]
    last_period = max(
        window.rfind("。", 0, max_len + 1),
        window.rfind("！", 0, max_len + 1),
        window.rfind("？", 0, max_len + 1),
    )
    if last_period > max_len // 2:
        return window[: last_period + 1]
    return text[:max_len].rstrip() + "…"


def extract_work_description(body_html: str) -> list[WorkItem]:
    """`【仕事内容】` 以降を段落("p")と箇条書き("li")のシーケンスへ分解する。"""
    soup = BeautifulSoup(body_html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    started = False
    items: list[WorkItem] = []
    bullet_re = re.compile(r"^([〇○●□■◇◆▽▼☆★・※])\s*(.*)")
    for ln in lines:
        if not started:
            if _WORK_DESCRIPTION_HEAD in ln:
                started = True
                tail = ln.split(_WORK_DESCRIPTION_HEAD, 1)[1].strip()
                if tail:
                    items.append(WorkItem(kind="p", text=tail))
            continue
        m = bullet_re.match(ln)
        if m:
            item_text = m.group(2).strip() or m.group(1)
            items.append(WorkItem(kind="li", text=item_text))
        else:
            items.append(WorkItem(kind="p", text=ln))
    return items


def group_work_items(items: list[WorkItem]) -> list[WorkBlock]:
    """Collapses consecutive `li` items into one `WorkBlock(kind="ul")`,
    leaving `p` items as their own `WorkBlock(kind="p")` — mirrors the
    mockup script's `build_new_main_html` grouping loop (`work_lines`'s
    `while i < len(work_items)` block)."""
    blocks: list[WorkBlock] = []
    i = 0
    while i < len(items):
        item = items[i]
        if item.kind == "p":
            blocks.append(WorkBlock(kind="p", text=item.text))
            i += 1
            continue
        bullets: list[str] = []
        while i < len(items) and items[i].kind == "li":
            bullets.append(items[i].text)
            i += 1
        blocks.append(WorkBlock(kind="ul", items=bullets))
    return blocks


_WORK_TIME_SHORT_LEN = 30
_HOLIDAY_PARAGRAPH_SHOW_LEN = 60


def build_detail_view(offer: JobOffer) -> DetailView:
    """Derives every Phase A section from `offer` — the single entry point
    `render_job_detail` (renderer.py) calls. Never raises: absent/unmatched
    data degrades to `None`/`[]`, which `job_detail.html` treats as "hide
    this section" rather than a rendering failure."""
    labels = split_label(offer.label)
    employment_type = labels[1] if len(labels) >= 2 else labels[0]

    location_primary, location_detail = simplify_address(offer.address, offer.extra_lines)

    work_time, capacity = extract_work_time_capacity(offer.extra_lines)
    work_time_short: str | None = None
    work_time_detail: str | None = None
    if work_time:
        work_time_short = work_time[:_WORK_TIME_SHORT_LEN] + (
            "…" if len(work_time) > _WORK_TIME_SHORT_LEN else ""
        )
        work_time_detail = work_time if work_time != work_time_short else None

    holiday_chip = extract_holiday_chip(offer.extra_lines)
    holiday_paragraph_full = extract_holiday_paragraph(offer.extra_lines)
    holiday_paragraph_short = (
        holiday_paragraph_full[:_HOLIDAY_PARAGRAPH_SHOW_LEN] if holiday_paragraph_full else None
    )

    benefit_chips, benefit_paragraphs = extract_benefits(offer.extra_lines)
    # Benefits section body also shows the full holiday paragraph (not the
    # summary's truncated one) as a labelled "休暇制度" line — matches
    # `build_new_main_html`'s `benefits_html_lines` in the mockup script.
    if holiday_paragraph_full:
        benefit_paragraphs = [
            BenefitParagraph(heading="休暇制度", content=holiday_paragraph_full),
            *benefit_paragraphs,
        ]

    work_items = extract_work_description(offer.body_html)

    return DetailView(
        labels=labels,
        employment_type=employment_type,
        employment_type_schema=_EMPLOYMENT_TYPE_SCHEMA.get(employment_type),
        salary_chip=extract_salary_chip(offer.salary),
        salary_detail=extract_salary_detail(offer.salary),
        location_primary=location_primary,
        location_detail=location_detail,
        work_time_short=work_time_short,
        work_time_detail=work_time_detail,
        holiday_chip=holiday_chip,
        holiday_paragraph=holiday_paragraph_short,
        capacity=capacity,
        hashtags=extract_hashtags(offer.body_html),
        lead=extract_lead_paragraph(offer.body_html),
        work_blocks=group_work_items(work_items),
        qualifications=extract_qualifications(offer.extra_lines),
        benefit_chips=benefit_chips,
        benefit_paragraphs=benefit_paragraphs,
        selection_steps=extract_selection_flow(offer.extra_lines),
        region_prefecture=extract_region_prefecture(offer.address),
    )


def build_job_posting_json_ld(offer: JobOffer, view: DetailView) -> dict:
    """Builds the `JobPosting` structured-data dict (schema.org).

    `mockup/jobs/*.html`'s JSON-LD was an explicitly-labelled placeholder
    ("Phase A 雛形 / Phase B で正本化") with two hardcoded values this
    intentionally does NOT carry over:

    - `datePosted`/`validThrough` were the same literal dates
      (`2026-06-01`/`2026-12-31...`) on every one of the 37 mockup postings —
      `JobSnapshot` has no real posting/expiry date to substitute, so both
      keys are omitted entirely rather than shipping another fake constant.
    - `jobLocation.address.addressRegion` was hardcoded `"福岡県"` on every
      posting regardless of the actual facility (a known bug — see
      `docs/handoff/GOAL.md` PR #87 note, and `extract_region_prefecture`'s
      docstring). Here it's derived from the real address, and omitted
      (rather than guessed) when it can't be determined.
    """
    posting: dict = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": offer.title,
    }
    if view.lead:
        posting["description"] = view.lead
    if view.employment_type_schema:
        posting["employmentType"] = view.employment_type_schema

    address: dict = {"@type": "PostalAddress", "addressCountry": "JP"}
    if view.region_prefecture:
        address["addressRegion"] = view.region_prefecture
    posting["jobLocation"] = {"@type": "Place", "address": address}

    posting["hiringOrganization"] = {
        "@type": "Organization",
        "name": "あおぞらケアグループ",
        "sameAs": "https://aozora-cg.com/",
    }
    posting["directApply"] = False
    posting["applicationContact"] = {"@type": "ContactPoint", "url": offer.apply_url}
    return posting
