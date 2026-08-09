"""Builds the grounding context injected into the system prompt, and the
job-id whitelist `resolve_jobs` checks against.

FAQ is bundled into the container image (`knowledge/faq.yaml`) and never
changes at runtime — see faq.yaml's own header comment for why. Job data has
NO bundled counterpart (Stage: AIチャットPhase B連携, 2026-08-09) — it comes
exclusively from `sync`'s `GET /jobs/chatbot-knowledge.json`, fetched at
process startup and re-fetched on a periodic timer (`app.py`'s
`_refresh_knowledge`/`_periodic_refresh`), so the chatbot tracks the
6-hourly Firestore sync without a human ever re-running a build script.

The bundled `jobs_detail.json` + `scripts/build_jobs_detail.py` this module
used to fall back to were deleted, not just deprioritized: keeping them
around would have preserved a path where a `sync` outage makes this service
silently answer with stale Phase A sample data instead of admitting it can't
recommend jobs right now — precisely the staleness bug this migration exists
to close. `bundled_knowledge()` is now FAQ-only; see its docstring.

`KnowledgeBase` bundles the prompt context and the job whitelist into one
immutable snapshot so the two can never describe different job sets (see its
docstring). `bundled_knowledge()` builds the FAQ-only fallback snapshot once
per process; `fetch_knowledge()` builds a fresh one from a remote payload, or
raises — callers own the fallback policy (see `app.py`).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import Field, TypeAdapter, field_validator

from .models import JobCard, JobDetail

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

_MAX_RESOLVED_JOBS = 3

# `sync`'s Cloud Run service — the *only* source of job data (Stage: AIチャット
# Phase B連携, 2026-08-09). `/jobs/chatbot-knowledge.json` is built at request
# time from live Firestore snapshots (`sync/src/sync/chatbot_knowledge.py`),
# so this always reflects the 6-hourly sync, not a one-time build artefact.
# A fetch failure is deliberately silent (falls back to the current
# in-memory knowledge base, FAQ-only on a cold start — see
# `app._refresh_knowledge`), so a URL/path drift here could go unnoticed in
# production; `tests/test_knowledge.py::
# test_default_jobs_detail_url_matches_sync_route_path` pins this string
# against `sync`'s own route path mechanically.
DEFAULT_JOBS_DETAIL_URL = (
    "https://aozora-sync-flry56mxwa-an.a.run.app/jobs/chatbot-knowledge.json"
)

# Disallows control/formatting characters and both pipe variants. `context`
# formats each job as a `|`-delimited row and each FAQ/job field is embedded
# directly into the system prompt (the model's highest-trust input) — a
# fetched title containing e.g. a newline could forge a new prompt line, and
# a literal `|` could forge an extra column.
_FORBIDDEN_CHARS_RE = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069|\uff5c]"
)


def _reject_forbidden_chars(value: str) -> str:
    if _FORBIDDEN_CHARS_RE.search(value):
        raise ValueError("contains a forbidden control/formatting character or pipe")
    return value


class _StrictJobDetail(JobDetail):
    """`JobDetail` plus the character-safety checks fetched payloads need.

    Kept separate from `JobDetail` (used elsewhere for the resolved-job
    shape) so the forbidden-character rule is scoped to knowledge ingestion,
    not every consumer of the model.
    """

    # `id` is interpolated into the same pipe-delimited context row as
    # `title` (unescaped) and is used verbatim to rebuild `url`
    # (`jobs/{id}`) — the whole reason `url` itself is discarded and
    # recomputed. A forbidden character in `id` would forge a fake context
    # row exactly like an unvalidated `title` would, and would also corrupt
    # the very `url` recomputation meant to be the safe alternative. All
    # current ids are purely numeric, so pinning the shape is free today.
    id: str = Field(pattern=r"^[0-9]+$")

    @field_validator("title", "category", "area", "facility", "city", mode="after")
    @classmethod
    def _no_forbidden_chars(cls, v: str) -> str:
        return _reject_forbidden_chars(v)

    @field_validator("employment", "service_types", mode="after")
    @classmethod
    def _no_forbidden_chars_in_items(cls, v: list[str]) -> list[str]:
        for item in v:
            _reject_forbidden_chars(item)
        return v


_JOBS_DETAIL_ADAPTER = TypeAdapter(list[_StrictJobDetail])


def _load_faq() -> list[dict[str, str]]:
    data = yaml.safe_load((_KNOWLEDGE_DIR / "faq.yaml").read_text(encoding="utf-8"))
    return data["faq"]


def _summarize_jobs(jobs_detail: list[dict]) -> dict:
    """Derive facility/job aggregate stats from a `jobs_detail` list.

    Every field here (areas, categories, employment types, per-facility job
    counts) is a straightforward aggregation over job records — deriving it
    at load time removes the manual-sync step a separate summary file would
    require.
    """
    facilities: dict[str, dict] = {}
    employment_types: set[str] = set()
    for job in jobs_detail:
        employment_types.update(job["employment"])
        facility = facilities.setdefault(
            job["facility"],
            {
                "name": job["facility"],
                "city": job["city"],
                "area": job["area"],
                "job_count": 0,
                "categories": [],
            },
        )
        facility["job_count"] += 1
        if job["category"] not in facility["categories"]:
            facility["categories"].append(job["category"])

    return {
        "areas": sorted({job["area"] for job in jobs_detail}),
        "categories": sorted({job["category"] for job in jobs_detail}),
        "employment_types": sorted(employment_types),
        "facility_count": len(facilities),
        "job_count": len(jobs_detail),
        "facilities": list(facilities.values()),
    }


def _render_context(faq: list[dict[str, str]], jobs_detail: list[dict]) -> str:
    """Assemble FAQ + job summary into one grounding document.

    `jobs_detail == []` (a FAQ-only `bundled_knowledge()` cold start, or a
    fetch that hasn't succeeded yet) skips the job sections entirely and
    tells the model outright not to recommend jobs — the alternative
    (silently omitting the section) leaves the model free to hallucinate
    job details from FAQ text alone, and an explicit instruction here is
    the only lever this module has over that (`resolve_jobs` server-side
    filtering only catches a fabricated *id*, not a fabricated job
    description with no id at all).
    """
    lines = ["## よくある質問"]
    for item in faq:
        lines.append(f"Q: {item['question']}\nA: {item['answer']}")

    if not jobs_detail:
        lines.append(
            "\n## 求人情報\n"
            "現在、求人情報を取得できていません。求人の詳細案内やおすすめの提示は行わず、"
            "「現在求人情報を確認できないため、後ほど改めてお尋ねいただくか採用ページを"
            "直接ご確認ください」という趣旨をユーザーに伝えてください。"
        )
        return "\n".join(lines)

    jobs = _summarize_jobs(jobs_detail)
    lines.append("\n## 求人情報サマリー")
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
    # サービス種別（デイサービス/訪問介護等）を明示列にしているのは、施設名の
    # 生テキストだけだとユーザーの指定サービス種別との照合精度が model 任せ
    # になり、異なるサービス種別の求人が紛れ込む事象が実際に報告されたため。
    lines.append(
        "\n## 応募可能な求人一覧（id | タイトル | エリア/職種/雇用形態 | サービス種別）"
    )
    for job in jobs_detail:
        service_types = ", ".join(job["service_types"]) or "該当なし"
        lines.append(
            f"- {job['id']} | {job['title']} | {job['area']}/{job['category']}/"
            f"{', '.join(job['employment'])} | {service_types}"
        )
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    """One immutable grounding snapshot: prompt context + job whitelist.

    Built in a single shot and never mutated so a startup refresh can swap
    the whole thing atomically. The two fields MUST describe the same job
    set — a context listing an id `jobs_by_id` doesn't know (or vice versa)
    would make the model recommend jobs the server then silently drops (or
    the reverse: a known job the model can never be told to mention).
    Bundling them into one object makes that skew unrepresentable rather
    than merely unlikely.

    `source` is carried explicitly (rather than having `/health` compare
    `is bundled_knowledge()`) so the reported source stays correct even if
    something ever clears `bundled_knowledge`'s `lru_cache` — an identity
    check would silently start reporting "fetched" for a freshly-recomputed
    bundled snapshot in that case.
    """

    context: str
    jobs_by_id: dict[str, JobCard]
    source: Literal["bundled", "fetched"]

    def resolve_jobs(self, job_ids: list[str]) -> list[JobCard]:
        """Resolve model-suggested ids to `JobCard`s, dropping anything unknown.

        Preserves the model's relevance ordering, de-duplicates, and caps at
        `_MAX_RESOLVED_JOBS` — the prompt already asks for at most 3, but the
        server must not trust that (same rationale as `app._trim_history`).
        """
        resolved: list[JobCard] = []
        seen: set[str] = set()
        for job_id in job_ids:
            if job_id in seen:
                continue
            job = self.jobs_by_id.get(job_id)
            if job is None:
                continue
            seen.add(job_id)
            resolved.append(job)
            if len(resolved) >= _MAX_RESOLVED_JOBS:
                break
        return resolved


def parse_jobs_detail(raw: object) -> list[dict]:
    """Validate an untrusted jobs_detail payload (bundled or fetched).

    Raises `pydantic.ValidationError` / `ValueError` on anything unusable —
    the caller decides what to do about that (bundled: let it crash at
    import, a broken bundled file is a build bug; fetched: fall back, see
    `app._refresh_knowledge`).

    `url` is deliberately NOT taken from the payload: it's fully derived
    from `id` (`jobs/{id}` — `sync`'s canonical detail route, see
    `sync/src/sync/chatbot_knowledge.py`), so trusting a remote-supplied
    `url` would let a compromised/misconfigured upstream put an arbitrary
    URL into `<a href>` on the recruitment site (`chat-widget.js`'s job
    cards). Recomputing it here removes that field from the trust boundary
    entirely rather than trying to validate it.
    """
    jobs = _JOBS_DETAIL_ADAPTER.validate_python(raw)
    if not jobs:
        # An empty list is a perfectly valid `list[_StrictJobDetail]` but
        # swapping it in would silently strip every job from both the prompt
        # and the whitelist — the chatbot keeps answering, just never
        # recommends a job again. That's exactly the failure the bundled
        # fallback exists to prevent, so treat it as an error, not a refresh.
        raise ValueError("jobs_detail payload contains no records")
    ids = [job.id for job in jobs]
    if len(ids) != len(set(ids)):
        # `build_knowledge`'s `{job["id"]: JobCard(**job) ...}` dict
        # comprehension would otherwise let two records sharing an id
        # collide silently: the context still lists both rows, but
        # `resolve_jobs` can only ever return whichever one wins the
        # dict-key collision — exactly the context/whitelist skew
        # `KnowledgeBase` exists to make impossible.
        raise ValueError("jobs_detail payload contains duplicate ids")
    return [{**job.model_dump(), "url": f"jobs/{job.id}"} for job in jobs]


def build_knowledge(
    jobs_detail: list[dict], *, source: Literal["bundled", "fetched"]
) -> KnowledgeBase:
    faq = _load_faq()
    return KnowledgeBase(
        context=_render_context(faq, jobs_detail),
        jobs_by_id={job["id"]: JobCard(**job) for job in jobs_detail},
        source=source,
    )


@lru_cache(maxsize=1)
def bundled_knowledge() -> KnowledgeBase:
    """The FAQ-only fallback used before the first successful
    `fetch_knowledge()` call (or after every retry has failed).

    There is deliberately no bundled job data (Stage: AIチャットPhase B連携,
    2026-08-09 removed the old `knowledge/jobs_detail.json` — see module
    docstring): this process boundary legitimately has zero jobs until
    `sync`'s `/jobs/chatbot-knowledge.json` has been fetched at least once.
    `build_knowledge([], source="bundled")` renders a context that tells the
    model to decline job recommendations rather than resorting to stale
    Phase A sample data (`_render_context`'s empty-jobs branch). `/health`
    reporting `{"source": "bundled", "job_count": 0}` is the observable
    signal that an instance hasn't fetched real data yet.

    `lru_cache` keeps "build once per process": `create_app()` runs at every
    test module's import time (module-level ASGI entrypoint in `app.py`) and
    would otherwise re-parse `faq.yaml` on every import.
    """
    return build_knowledge([], source="bundled")


async def fetch_knowledge(
    url: str,
    *,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> KnowledgeBase:
    """Fetch + validate a fresh knowledge base from `url`. Raises on ANY
    failure (network error, timeout, non-200, non-JSON, schema violation,
    empty payload) — this function has no opinion on availability, the
    caller owns that policy (see `app._refresh_knowledge`).

    `asyncio.timeout` wraps the httpx timeout because `httpx.Timeout(n)`
    applies `n` to connect/read/write/pool *individually*, not as a wall-clock
    total — and this call runs during lifespan startup, before uvicorn binds
    its listen socket, so its duration directly delays the app becoming
    ready.
    """
    async with asyncio.timeout(timeout_seconds):
        async with httpx.AsyncClient(timeout=timeout_seconds, transport=transport) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    return build_knowledge(parse_jobs_detail(payload), source="fetched")
