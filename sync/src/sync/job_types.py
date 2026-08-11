"""Single source of truth for Jobcan's 17 job-type categories (category_id →
display name).

Deliberately a leaf module with zero project-internal imports: `crawler.py`
(the crawl orchestrator, which pulls in `jobcan_client`/`parser`) and
`list_sections.py`/`search_index.py` (the render-time layer, which must not
import `crawler`'s heavier dependency chain just to know a category's name)
both need this table, so it can't live in either.

This promotes what used to be a comment-only annotation on
`crawler.KNOWN_CATEGORY_IDS` into an actual data structure (Stage 3
follow-up, 2026-08-09 job-type-filter-granularity work) — the values and
order are unchanged, `crawler.KNOWN_CATEGORY_IDS` now derives from this
table instead of duplicating it.
"""

from __future__ import annotations

# Every category_id confirmed to exist on https://recruit.jobcan.jp/aozora as
# of 2026-08-06 (see `crawler.py`'s original docstring for the confirmation
# history). Order matches the top-page category link list.
JOB_TYPE_NAMES: dict[str, str] = {
    "18773": "介護職",
    "18983": "看護職",
    "18984": "相談員",
    "18985": "ケアマネジャー・計画作成担当者",
    "18986": "ホームヘルパー",
    "18987": "訪問看護",
    "18988": "夜勤専従（介護・看護）",
    "18989": "施設長・管理者候補",
    "18990": "サービス提供責任者",
    "22014": "サービス管理責任者",
    "39695": "世話人",
    "41046": "訪問リハビリ",
    "43764": "サポート職（清掃・洗濯・調理・送迎）",
    "58859": "事務職",
    "69384": "ITエンジニア職",
    "71511": "総合職（営業・管理職）",
    "73697": "新卒・既卒総合職",
}

# Reverse lookup for the CSV ingestion path (CSV-migration follow-up,
# 2026-08-11): the CSV's「求人カテゴリ」column holds the display NAME, not the
# category_id. Safe only because `JOB_TYPE_NAMES`'s values are unique — pinned
# by `test_job_types.py::test_job_type_names_values_are_unique`.
JOB_TYPE_IDS_BY_NAME: dict[str, str] = {
    name: category_id for category_id, name in JOB_TYPE_NAMES.items()
}
