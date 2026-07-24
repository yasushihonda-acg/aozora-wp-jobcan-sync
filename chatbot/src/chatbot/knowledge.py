"""Builds the single grounding context string injected into the system prompt.

Phase A design: FAQ + job-summary knowledge is bundled into the container
image (`knowledge/faq.yaml`, `knowledge/jobs_summary.json`) and assembled
once, cached for the process lifetime — no RAG, no external fetch. This
means the chatbot's answers go stale if `mockup/index.html` `#faq` or
`mockup/assets/data/jobs.json` change without a matching update+redeploy
here (documented tradeoff, see chatbot/README.md).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _load_faq() -> list[dict[str, str]]:
    data = yaml.safe_load((_KNOWLEDGE_DIR / "faq.yaml").read_text(encoding="utf-8"))
    return data["faq"]


def _load_jobs_summary() -> dict:
    return json.loads((_KNOWLEDGE_DIR / "jobs_summary.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def build_context() -> str:
    """Assemble FAQ + job summary into one grounding document (cached).

    `lru_cache` gives us "read once per process" for free — Cloud Run
    reuses the same instance across many requests, and re-parsing the same
    two small files on every request would be pure overhead.
    """
    faq = _load_faq()
    jobs = _load_jobs_summary()

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
    return "\n".join(lines)
