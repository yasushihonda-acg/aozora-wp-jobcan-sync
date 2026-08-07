"""Scaffold brand-new job-list cards + detail-page skeletons for job IDs
that have never appeared in a mockup listing page before.

`rewrite_jobs_html.py` / `rewrite_job_details.py` are deliberately update-only
(see their docstrings): they refresh content for cards/files that already
exist, keyed by job_id, but have no code path to insert a job_id that has
never been seen. This script fills exactly that one gap — it creates the
skeleton `<li class="job-list-card">` element and (if missing) the skeleton
detail-page file, using real data already fetched into `jobs_data.json`
(run `fetch_all.py` first). The existing pipeline (`rewrite_jobs_html.py`,
`rewrite_job_details.py`, `build_geo_data.py`) then fills in every other
field (address/description/meta-grid/sections) exactly as it does for the
34 pre-existing jobs — nothing here duplicates that formatting logic.

Usage:
    python scripts/mockup-rebuild/add_new_cards.py <job_id> [<job_id> ...] \
        --target mockup/jobs.html [--replace]

--replace: remove every existing job-list-card from --target before
           inserting the new ones (used for mockup/jobs-nurse.html, whose
           10 existing cards show the wrong category's jobs entirely).
Category (job-list-card--<category>) and chip label are derived from each
job's `label` field via LABEL_TO_CATEGORY (imported from rewrite_jobs_html.py
— single source of truth, no separate hardcoded category list here).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = HERE / "jobs_data.json"
DETAIL_TEMPLATE = REPO / "mockup" / "jobs" / "1777023.html"

sys.path.insert(0, str(HERE))
from rewrite_jobs_html import CATEGORY_VARIANTS, LABEL_TO_CATEGORY  # noqa: E402

# チップUIの表示ラベル (ジョブカン正本の職種名を短縮した表示コピー、既存の
# 「介護・相談」「事務」「IT」と同じ短縮方針)。category は実データ由来だが、
# チップの見せ方(コピー)は人が決めるUI事項のため、ここだけ明示的に管理する。
CHIP_LABELS: dict[str, str] = {"nurse": "看護"}

# 長い(複合)キーワードを先に判定しないと「看護職パートアルバイト」が
# 「看護職パート」+「アルバイト」に割れて職種側に雇用形態の残骸が残る。
EMPLOYMENT_KEYWORDS = sorted(
    ["短時間正社員", "契約社員", "パートアルバイト", "正社員", "パート", "アルバイト"],
    key=len,
    reverse=True,
)


def split_label(label: str) -> list[str]:
    """'看護職正社員' -> ['看護職', '正社員'] (rewrite_job_details.py と同一ロジック、
    複合雇用形態 'パートアルバイト' にも対応する拡張版)。

    'パートアルバイト' は「パート」「アルバイト」いずれでも応募可という意味の
    複合値であり、jobs.json の employment はフィルターチップの値と個別一致
    (map-search.js `job.employment.some(e => state.employment.has(e))`) する
    必要があるため、1個の結合文字列ではなく2要素に分割して返す。
    """
    for emp in EMPLOYMENT_KEYWORDS:
        if not label.endswith(emp):
            continue
        head = label[: -len(emp)].strip()
        tail = ["パート", "アルバイト"] if emp == "パートアルバイト" else [emp]
        return ([head] if head else []) + tail
    return [label]


# CLAUDE.md記載の通り本事業は福岡県・鹿児島県(九州)限定のため、汎用的な
# 「任意の文字列+県」パターンだと施設名(括弧書き等)を巻き込んでしまう
# (実際に「あおぞらケアグループ博多（デイ・有料）福岡県」まで誤って一致した)。
# 対象2県のみを明示的に列挙して誤爆を防ぐ。
PREFECTURE_CITY_RE = re.compile(
    r"(福岡県|鹿児島県)((?:[^市区]+?市)(?:[^区]+?区)?|[^町村]+?[町村])"
)


def extract_prefecture_city(extras: list[list[str]]) -> tuple[str, str]:
    """extras['募集拠点'] の住所末尾 (例: 「...福岡県福岡市博多区豊2丁目1-7」) から
    (都道府県, 市区町村) を抽出する (rewrite_jobs_html.py の simplify_address と
    同じ正規表現方針、都道府県も別途取り出す点のみ拡張)."""
    for k, v in extras:
        if k != "募集拠点":
            continue
        m = PREFECTURE_CITY_RE.search(v)
        if m:
            return m.group(1), m.group(2)
    return "", ""


def clean_meta_description(body_html: str, max_len: int = 120) -> str:
    soup = BeautifulSoup(body_html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with(" ")
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    text = re.sub(r"^(?:[#＃]\s*[^\s#＃]+\s*)+", "", text).strip()
    return text[:max_len] + ("…" if len(text) > max_len else "")


def build_skeleton_card(job: dict, category: str) -> str:
    labels = split_label(job["label"])
    thumb = CATEGORY_VARIANTS.get(category, ["illust-job-care.png"])[0]
    li = (
        f'<li class="job-list-card job-list-card--{category}">\n'
        f'<a class="job-list-card__link" href="jobs/{job["job_id"]}.html" rel="noopener">\n'
        f'<div class="job-list-card__thumb">\n'
        f'<img alt="" class="job-list-card__thumb-img" loading="lazy" src="assets/img/{thumb}"/>\n'
        f"</div>\n"
        f'<div class="job-list-card__body">\n'
        f'<ul class="job-list-card__labels" role="list">\n'
        + "".join(f'<li class="job-list-card__label">{lbl}</li>\n' for lbl in labels)
        + "</ul>\n"
        f'<h2 class="job-list-card__title">{job["title"]}</h2>\n'
        f'<p class="job-list-card__address"></p>\n'
        f'<p class="job-list-card__description"></p>\n'
        f'<span class="job-list-card__cta">詳細を見る</span>\n'
        f"</div>\n"
        f"</a>\n"
        f"</li>\n"
    )
    return li


def insert_cards(target: Path, job_ids: list[str], jobs: dict[str, dict], *, replace: bool) -> None:
    html = target.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    card_list = soup.find("ul", class_="job-list__cards")
    if card_list is None:
        raise SystemExit(f"{target}: <ul class=\"job-list__cards\"> not found")

    existing_ids = set()
    for card in card_list.find_all("li", class_="job-list-card"):
        link = card.find("a", class_="job-list-card__link")
        m = re.search(r"jobs/(\d+)\.html", link.get("href", "")) if link else None
        if m:
            existing_ids.add(m.group(1))

    if replace:
        for card in card_list.find_all("li", class_="job-list-card"):
            card.decompose()
        existing_ids = set()

    added = 0
    for jid in job_ids:
        if jid in existing_ids:
            print(f"  SKIP {jid}: card already present in {target.name}")
            continue
        job = jobs[jid]
        category = LABEL_TO_CATEGORY.get(split_label(job["label"])[0], "care")
        fragment = BeautifulSoup(build_skeleton_card(job, category), "html.parser")
        card_list.append(fragment)
        added += 1
        print(f"  ADDED {jid} ({category}): {job['title'][:40]}")

    # ヘッダーの「N 件の募集中ポジション」を実カード数へ同期
    total_cards = len(card_list.find_all("li", class_="job-list-card"))
    lede = soup.find("p", class_=re.compile(r"__(lede|lead)$"))
    if lede and "件" in lede.get_text():
        lede.string = re.sub(r"\d+\s*件", f"{total_cards} 件", lede.get_text())

    # フィルターチップ (jobs.html のみ対象、既に存在すれば追加しない)
    chip_group = soup.find(attrs={"data-filter-group": "category"})
    if chip_group is not None:
        seen_values = {b.get("data-value") for b in chip_group.find_all("button")}
        added_categories = {
            LABEL_TO_CATEGORY.get(split_label(jobs[jid]["label"])[0]) for jid in job_ids
        }
        new_categories = added_categories - seen_values
        for cat in sorted(c for c in new_categories if c and c in CHIP_LABELS):
            btn = soup.new_tag(
                "button",
                attrs={
                    "aria-pressed": "false",
                    "class": "job-search-panel__chip",
                    "data-value": cat,
                    "type": "button",
                },
            )
            btn.string = CHIP_LABELS[cat]
            chip_group.append(btn)
            print(f"  ADDED filter chip: {cat} ({CHIP_LABELS[cat]})")

    target.write_text(str(soup), encoding="utf-8")
    print(f"{target.name}: {added} card(s) added, {total_cards} total\n")


# 「あおぞらケアグループ<拠点名>」からエリア(福岡/鹿児島)を判定する簡易表。
# ここで作る詳細ページは常にこの3拠点のいずれかなので、汎用的な地理データを
# 別途持たず、既知拠点だけの最小マップで足りる。
FACILITY_AREA = {
    "博多": "福岡",
    "永吉": "鹿児島",
    "梅ヶ丘": "福岡",
}


def facility_area(address: str) -> str:
    for name, area in FACILITY_AREA.items():
        if name in address:
            return area
    return ""


def update_related_jobs(soup: BeautifulSoup, job_id: str, batch: dict[str, dict]) -> None:
    """関連する求人サイドバーを、クローン元テンプレートの無関係な求人リンクから
    同一バッチ内の他求人へ差し替える (クローン直後は 1777023.html の介護職リンクが
    そのまま残ってしまうため)。"""
    aside_list = soup.find("ul", class_="aside-card__list")
    if aside_list is None:
        return
    others = [(jid, j) for jid, j in batch.items() if jid != job_id]
    if not others:
        return
    for li in aside_list.find_all("li"):
        li.decompose()
    for jid, other in others:
        li = soup.new_tag("li")
        a = soup.new_tag("a", href=f"{jid}.html")
        title_span = soup.new_tag("span")
        title_span.string = other["title"]
        meta_span = soup.new_tag("span", attrs={"class": "aside-card__meta"})
        meta_span.string = facility_area(other["address"])
        a.append(title_span)
        a.append(meta_span)
        li.append(a)
        aside_list.append(li)


def create_detail_skeleton(job_id: str, job: dict, batch: dict[str, dict]) -> None:
    out_path = REPO / "mockup" / "jobs" / f"{job_id}.html"
    if out_path.exists():
        print(f"  SKIP {job_id}.html: already exists")
        return

    html = DETAIL_TEMPLATE.read_text(encoding="utf-8").replace("1777023", job_id)
    soup = BeautifulSoup(html, "html.parser")

    meta_desc = clean_meta_description(job["body_html"])
    employment_type = (
        "PART_TIME" if any(k in job["label"] for k in ("パート", "アルバイト")) else "FULL_TIME"
    )

    title_el = soup.find("title")
    if title_el:
        title_el.string = f"{job['title']} | あおぞらケアグループ採用"

    meta_el = soup.find("meta", attrs={"name": "description"})
    if meta_el:
        meta_el["content"] = meta_desc

    script_el = soup.find("script", attrs={"type": "application/ld+json"})
    if script_el and script_el.string:
        posting = json.loads(script_el.string)
        posting["title"] = job["title"]
        posting["description"] = meta_desc
        posting["employmentType"] = employment_type
        prefecture, city = extract_prefecture_city(job["extra_lines"])
        if prefecture and city:
            posting["jobLocation"]["address"]["addressRegion"] = prefecture
            posting["jobLocation"]["address"]["addressLocality"] = city
        script_el.string = json.dumps(posting, ensure_ascii=False, indent=4)

    breadcrumb = soup.find("p", class_="breadcrumb")
    if breadcrumb:
        spans = breadcrumb.find_all("span", recursive=False)
        if spans:
            spans[-1].string = job["title"]

    update_related_jobs(soup, job_id, batch)

    out_path.write_text(str(soup), encoding="utf-8")
    print(f"  CREATED {job_id}.html")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_ids", nargs="+")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    jobs = {j["job_id"]: j for j in data["jobs"]}
    for jid in args.job_ids:
        if jid not in jobs:
            raise SystemExit(f"{jid} not found in {DATA} — run fetch_all.py first")

    insert_cards(args.target, args.job_ids, jobs, replace=args.replace)

    batch = {jid: jobs[jid] for jid in args.job_ids}
    for jid in args.job_ids:
        create_detail_skeleton(jid, jobs[jid], batch)


if __name__ == "__main__":
    main()
