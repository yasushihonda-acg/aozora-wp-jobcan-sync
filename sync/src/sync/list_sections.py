"""Derives the Phase A job-list card decorations (category colour, salary/
holiday meta-grid) from Firestore data — the list-page counterpart to
`detail_sections.py`.

Phase A's `scripts/mockup-rebuild/rewrite_jobs_html.py` (a one-time script
over a 37-job static sample) computed three things per card: a category key
(`job-list-card--{care,nurse,office,it}` CSS modifier, from the card's first
label), a salary chip, and a holiday chip. This module ports the
category-key half as a pure function; the salary/holiday chips are *not*
duplicated here — `detail_sections.extract_salary_chip`/
`extract_holiday_chip` already do the same extraction from `JobOffer.salary`/
`extra_lines` (Stage 2), and both fields are already present on every
`JobSnapshot.offer`, list route included.

Deliberately not `labels[0]`-only: `_resolve_display_thumbnail` in
`parser.py` was corrected (Codex review finding) to walk every label instead
of trusting Jobcan's label order as a contract. `category_key_from_labels`
follows the same defensive shape.
"""

from __future__ import annotations

from pydantic import BaseModel

from .detail_sections import extract_holiday_chip, extract_salary_chip
from .facility_geo import facility_key
from .job_types import JOB_TYPE_NAMES
from .models import JobListItem
from .snapshot import JobSnapshot

# 求人ラベル → カテゴリ key。scripts/mockup-rebuild/rewrite_jobs_html.py の
# LABEL_TO_CATEGORY(5種のみ、37件サンプルに出現した型)を土台に、Firestore
# 全382件の実データ監査(2026-08-09)で判明した残り12種の職種ラベルを追加した
# もの。PR #72 で確定した「4系統(介護/看護/事務/IT、相談員は care へ統合)」
# という色分け設計自体は変えず、その4系統への割り当てを17種類の
# KNOWN_CATEGORY_IDS(`crawler.py`)全域に拡張している:
# - care: 現場介護職 + 相談支援・計画作成・管理系(ケアマネジャー/サービス提供
#   責任者/サービス管理責任者/世話人/施設長/夜勤専従/サポート職)
# - nurse: 看護職 + 訪問看護・リハビリ系
# - office: 事務職 + 総合職(営業・管理・新卒)
#
# 2026-08-11: `selectors.yaml`の`thumbnail_categories`(求人カードの挿絵選択)
# は本マッピングとは別物として6系統(care/visit/consultant/nurse/office/it)
# へ分離した — ホームヘルパー等の訪問系・相談員等の相談支援系に専用イラスト
# (illust-job-visit.png/illust-job-consultant.png)が既にあり、挿絵選択では
# それらを使うのが自然だが、CSSカラー修飾子は4系統のまま(専用色が無いため)。
# 挿絵側の変更にあわせて本マッピングを4→6系統へ追従させる必要はない。
LABEL_TO_CATEGORY: dict[str, str] = {
    "介護職": "care",
    "相談員": "care",
    "ホームヘルパー": "care",
    "ケアマネジャー・計画作成担当者": "care",
    "サービス提供責任者": "care",
    "サービス管理責任者": "care",
    "世話人": "care",
    "夜勤専従（介護・看護）": "care",
    "サポート職（清掃・洗濯・調理・送迎）": "care",
    "施設長・管理者候補": "care",
    "看護職": "nurse",
    "訪問看護": "nurse",
    "訪問リハビリ": "nurse",
    "事務職": "office",
    "総合職（営業・管理職）": "office",
    "新卒・既卒総合職": "office",
    "ITエンジニア職": "it",
}


def category_key_from_labels(labels: list[str]) -> str | None:
    """`job-list-card--{key}` modifier for a card, or `None` when no label
    matches a known category (e.g. a job type outside the four colour
    buckets — the card still renders, just without a colour accent)."""
    for label in labels:
        key = LABEL_TO_CATEGORY.get(label)
        if key is not None:
            return key
    return None


class JobListCardView(BaseModel):
    """One `job-list-card` — `JobListItem` plus the render-time decorations
    Phase A's card markup needs (colour modifier, salary/holiday chips,
    facility key for the map/GPS layer). Kept separate from the persisted
    `JobListItem` for the same reason Stage 2's `RelatedJob`/`DetailView` are
    separate from `JobOffer` — these fields are derived at render time, not
    stored."""

    item: JobListItem
    category_key: str | None
    salary_chip: str
    holiday_chip: str | None
    facility_key: str

    model_config = {"frozen": True}


def build_card_view(snapshot: JobSnapshot) -> JobListCardView | None:
    """`None` when `snapshot.list_item` is absent (never produced by a real
    `crawl_all()` run, but not schema-impossible — same defensive shape as
    `_primary_category_id` in `app.py`)."""
    if snapshot.list_item is None:
        return None
    return JobListCardView(
        item=snapshot.list_item,
        category_key=category_key_from_labels(snapshot.list_item.labels),
        salary_chip=extract_salary_chip(snapshot.offer.salary),
        holiday_chip=extract_holiday_chip(snapshot.offer.extra_lines),
        facility_key=facility_key(snapshot.offer.address),
    )


class JobTypeChip(BaseModel):
    """One `/jobs/` search-panel 職種 chip — the Jobcan-original 17-category
    granularity (as opposed to `category_key_from_labels`'s 4-bucket colour
    system above, which the chip panel used to reuse before decision-maker
    feedback 2026-08-09 that it didn't match `recruit.jobcan.jp/aozora`'s own
    17-category top-page nav). `category_id` is what the client sends back
    on selection and what `search_index.py`'s `jobTypes` field holds."""

    category_id: str
    name: str
    count: int

    model_config = {"frozen": True}


def build_job_type_chips(snapshots: dict[str, JobSnapshot]) -> list[JobTypeChip]:
    """Chips for every job type with at least one live posting, sorted by
    count descending (busiest job type first — e.g. 看護職 before 新卒・
    既卒総合職). A category with 0 active postings is omitted entirely: a
    chip a visitor can press only to see "0 件を表示中" is noise, not a
    filter.

    Eligibility mirrors `build_search_index`'s (`active` + `list_item`
    present) so the chip count never disagrees with what's actually
    filterable — a job legitimately listed under more than one category
    (`crawler.crawl_all`'s docstring) counts toward each of its chips."""
    counts: dict[str, int] = {}
    for snapshot in snapshots.values():
        if snapshot.sync_status != "active" or snapshot.list_item is None:
            continue
        for category_id in snapshot.category_ids:
            counts[category_id] = counts.get(category_id, 0) + 1

    chips = [
        JobTypeChip(category_id=category_id, name=name, count=counts[category_id])
        for category_id, name in JOB_TYPE_NAMES.items()
        if counts.get(category_id, 0) > 0
    ]
    chips.sort(key=lambda chip: chip.count, reverse=True)
    return chips
