"""Builds the single grounding context string injected into the system prompt.

Phase A design: FAQ + job knowledge is bundled into the container image
(`knowledge/faq.yaml`, `knowledge/jobs_summary.json`, `knowledge/jobs_detail.json`)
and assembled once, cached for the process lifetime — no RAG, no external
fetch. This means the chatbot's answers (and job recommendations) go stale if
`mockup/index.html` `#faq` or `mockup/assets/data/jobs.json` change without a
matching update+redeploy here (documented tradeoff, see chatbot/README.md).
`jobs_detail.json` is regenerated via `scripts/build_jobs_detail.py`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

from .models import JobCard

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

_MAX_RESOLVED_JOBS = 3


def _load_faq() -> list[dict[str, str]]:
    data = yaml.safe_load((_KNOWLEDGE_DIR / "faq.yaml").read_text(encoding="utf-8"))
    return data["faq"]


def _load_jobs_summary() -> dict:
    return json.loads((_KNOWLEDGE_DIR / "jobs_summary.json").read_text(encoding="utf-8"))


def _load_jobs_detail() -> list[dict]:
    return json.loads((_KNOWLEDGE_DIR / "jobs_detail.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _jobs_by_id() -> dict[str, JobCard]:
    """id → JobCard lookup built once from `jobs_detail.json`.

    This is the whitelist `resolve_jobs` checks candidate ids against — a
    ChatGPT-style structured-output call can name an id that doesn't exist
    (stale training data, mis-copied digit), so the client must never render
    a job the server hasn't independently confirmed.
    """
    return {
        job["id"]: JobCard(
            id=job["id"],
            title=job["title"],
            url=job["url"],
            category=job["category"],
            employment=job["employment"],
            facility=job["facility"],
            city=job["city"],
        )
        for job in _load_jobs_detail()
    }


def resolve_jobs(job_ids: list[str]) -> list[JobCard]:
    """Resolve model-suggested ids to `JobCard`s, dropping anything unknown.

    Preserves the model's relevance ordering, de-duplicates, and caps at
    `_MAX_RESOLVED_JOBS` — the prompt already asks for at most 3, but the
    server must not trust that (same rationale as `app._trim_history`).
    """
    known = _jobs_by_id()
    resolved: list[JobCard] = []
    seen: set[str] = set()
    for job_id in job_ids:
        if job_id in seen:
            continue
        job = known.get(job_id)
        if job is None:
            continue
        seen.add(job_id)
        resolved.append(job)
        if len(resolved) >= _MAX_RESOLVED_JOBS:
            break
    return resolved


@lru_cache(maxsize=1)
def build_context() -> str:
    """Assemble FAQ + job summary into one grounding document (cached).

    `lru_cache` gives us "read once per process" for free — Cloud Run
    reuses the same instance across many requests, and re-parsing the same
    two small files on every request would be pure overhead.
    """
    faq = _load_faq()
    jobs = _load_jobs_summary()
    jobs_detail = _load_jobs_detail()

    lines = ["## よくある質問"]
    for item in faq:
        lines.append(f"Q: {item['question']}\nA: {item['answer']}")

    lines.append("\n## 求人情報サマリー（Phase Aのダミーデータ）")
    lines.append(f"対応エリア: {', '.join(jobs['areas'])}")
    lines.append(f"職種カテゴリ: {', '.join(jobs['categories'])}")
    lines.append(f"雇用形態: {', '.join(jobs['employment_types'])}")
    lines.append(f"拠点数: {jobs['facility_count']} 拠点 / 求人数: {jobs['job_count']} 件")
    for facility in jobs["facilities"]:
        lines.append(
            f"- {facility['name']}（{facility['city']}）: "
            f"求人{facility['job_count']}件、職種: {', '.join(facility['categories'])}"
        )

    # job_ids の選択根拠。id はここに載っているものだけが実在する — 応答の
    # job_ids はこの一覧の id からのみ選ぶよう system prompt 側で指示する。
    lines.append("\n## 応募可能な求人一覧（id | タイトル | エリア/職種/雇用形態）")
    for job in jobs_detail:
        lines.append(
            f"- {job['id']} | {job['title']} | {job['area']}/{job['category']}/"
            f"{', '.join(job['employment'])}"
        )
    return "\n".join(lines)
