"""Regenerate `src/chatbot/knowledge/jobs_detail.json` from the mockup source data.

Run by hand after `mockup/jobs.html` / `mockup/assets/data/jobs.json` change
materially (same manual-sync tradeoff as `jobs_summary.json`, see
chatbot/README.md "知識ベースの鮮度"). No BeautifulSoup dependency — `jobs.html`
is machine-generated static markup with one `<h2 class="job-list-card__title">`
per `<a class="job-list-card__link" href="jobs/{id}.html">` in matching
document order, so a plain regex pairing is reliable and avoids adding a
parser dependency to this service for a one-off script.

Usage:
    cd chatbot && uv run python scripts/build_jobs_detail.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JOBS_HTML = _REPO_ROOT / "mockup" / "jobs.html"
_JOBS_JSON = _REPO_ROOT / "mockup" / "assets" / "data" / "jobs.json"
_OUTPUT = Path(__file__).resolve().parents[1] / "src" / "chatbot" / "knowledge" / "jobs_detail.json"

_FACILITY_PAREN_RE = re.compile(r"（(?P<inner>[^）]+)）")

# 施設名の括弧内トークン（"・"区切り）→ サービス種別の正規化名。
# Gemini への `job_ids` 選定精度向上のため（施設名の生テキストだけでは
# 「デイサービス」等のユーザークエリとの照合精度が model 任せになり、
# 訪問介護・特養等の異なるサービス種別が紛れ込む — 実際の decision-maker
# 報告事象）、施設名から構造化データとして明示的に抽出しておく。
_SERVICE_TYPE_MAP = {
    "デイ": "デイサービス",
    "有料": "有料老人ホーム",
    "特養": "特別養護老人ホーム",
    "GH": "グループホーム",
    "訪問介護": "訪問介護",
    "相談支援": "相談支援",
    "就労": "就労支援",
}


# 施設タグをそのまま求人の service_types にすると、複合サービス施設（例:
# 「小松原（相談支援・就労・GH）」）に属する求人全てが施設内の全サービスに
# 一致してしまう。ほとんどの職種（介護職／生活相談員）は施設内の複数サービス
# 横断で働くため妥当だが、「相談支援専門員」は相談支援業務に特化した職種で
# あり、同じ施設のグループホーム／就労支援検索に混ざるのは誤り（Codex
# review-diff 指摘、job 90447 で実際に発生）。タイトル中の職種名から
# service_types を絞り込む例外ルールとして扱う。
_TITLE_SERVICE_TYPE_OVERRIDE: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"相談支援専門員"), ["相談支援"]),
]


def _extract_service_types(facility_name: str, title: str) -> list[str]:
    for pattern, override in _TITLE_SERVICE_TYPE_OVERRIDE:
        if pattern.search(title):
            return override
    match = _FACILITY_PAREN_RE.search(facility_name)
    if not match:
        return []
    tokens = match.group("inner").split("・")
    return [_SERVICE_TYPE_MAP.get(token, token) for token in tokens]


_LINK_RE = re.compile(r'href="jobs/(?P<id>\d+)\.html"')
# id と title を1つのマッチで一緒に取る — 別々に findall して位置で zip すると、
# 将来 jobs.html のマークアップ順序が変わった際に件数は一致したまま id と
# title が静かに入れ替わりうる (件数一致チェックでは検出できない)。同じ
# job-card 内で href の直後に対応する title が来るという構造上の前提を、
# 1つの正規表現に閉じ込めることでこの取り違えを構造的に防ぐ。
_JOB_CARD_RE = re.compile(
    r'href="jobs/(?P<id>\d+)\.html".*?<h2 class="job-list-card__title">(?P<title>.*?)</h2>',
    re.DOTALL,
)


def _extract_titles_by_id(html: str) -> dict[str, str]:
    link_count = len(_LINK_RE.findall(html))
    matches = list(_JOB_CARD_RE.finditer(html))
    if len(matches) != link_count:
        raise ValueError(
            f"jobs.html structure mismatch: {link_count} job links vs "
            f"{len(matches)} link+title pairs matched"
        )
    return {m.group("id"): m.group("title") for m in matches}


def main() -> None:
    html = _JOBS_HTML.read_text(encoding="utf-8")
    titles_by_id = _extract_titles_by_id(html)

    jobs_data = json.loads(_JOBS_JSON.read_text(encoding="utf-8"))
    facilities = jobs_data["facilities"]

    detail = []
    for job in jobs_data["jobs"]:
        job_id = job["id"]
        if job_id not in titles_by_id:
            raise ValueError(f"job id {job_id} in jobs.json has no matching title in jobs.html")
        facility = facilities[job["facilityKey"]]
        detail.append(
            {
                "id": job_id,
                "title": titles_by_id[job_id],
                "category": job["category"],
                "employment": job["employment"],
                "area": job["area"],
                "facility": facility["name"],
                "city": facility["city"],
                "service_types": _extract_service_types(facility["name"], titles_by_id[job_id]),
                "url": f"jobs/{job_id}.html",
            }
        )

    _OUTPUT.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(detail)} jobs to {_OUTPUT}")


if __name__ == "__main__":
    main()
