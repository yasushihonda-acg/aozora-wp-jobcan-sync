"""jobs.html の 34 件カードを正本 JSON データを元に一括書き換え.

- description → 整形リード文 (body_html の先頭、ハッシュタグ羅列除去 + 100-130 字に短縮)
- meta-grid dl 追加 (月給 + 年休、salary/休日・休暇 から自動抽出)
- address → 「市区名 + 補足」形式に整形
- thumbnail → カテゴリ別 variant を cycle (同カテゴリ内で絵を分散)
- labels / title は既存維持

冪等: 既に新デザインの 3 件カード (1777023/2199420/452341) も同じパイプラインで再生成し統一感を出す。
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = HERE / "jobs_data.json"
JOBS_HTML = REPO / "mockup" / "jobs.html"

# 給与: 月額XXX,XXX円〜 → 「26.5 万円〜」「20.0 万円〜」
SALARY_MONTHLY_RE = re.compile(r"月額\s*([\d,]+)\s*円")
SALARY_RANGE_RE = re.compile(r"月額\s*([\d,]+)\s*円(?:\s*[～~〜]\s*([\d,]+)\s*円)?")
HOURLY_RE = re.compile(r"時給\s*([\d,]+)\s*円")
# 休日: 「年間休日XXX日」
HOLIDAY_RE = re.compile(r"年間休日\s*(\d+)\s*日")

# ハッシュタグ連続羅列 (先頭) を除去
HASHTAG_HEAD_RE = re.compile(r"^[#＃][^#＃◆■★●※【\n]+(?:\s*[#＃][^#＃◆■★●※【\n]+)*\s*")

# 求人ラベル → カテゴリ key 対応 (job-list-card__label 1 件目を見て判定)
LABEL_TO_CATEGORY = {
    "介護職": "care",
    "相談員": "consultant",  # 既存 illust-job-nurse.png は使用停止、consultant variant に置換
    "事務職": "office",
    "ITエンジニア職": "it",
}

# カテゴリ別 thumbnail variant 一覧 (cycling 順)
CATEGORY_VARIANTS: dict[str, list[str]] = {
    "care": ["illust-job-care.png", "illust-job-care-2.png", "illust-job-care-3.png"],
    "consultant": ["illust-job-consultant.png", "illust-job-consultant-2.png"],
    "office": ["illust-job-office.png", "illust-job-office-2.png"],
    "it": ["illust-job-it.png"],
}


def detect_category(card) -> str | None:
    """カードの 1 件目 label からカテゴリ key を判定."""
    label = card.find("li", class_="job-list-card__label")
    if not label:
        return None
    text = label.get_text(strip=True)
    return LABEL_TO_CATEGORY.get(text)


def yen_to_man(yen_str: str) -> str:
    """265,000 → '26.5 万'."""
    yen = int(yen_str.replace(",", ""))
    man = yen / 10000
    if man == int(man):
        return f"{int(man)}.0 万"
    return f"{man:.1f}".rstrip("0").rstrip(".") + " 万"


def extract_salary_chip(salary: str) -> str:
    """salary 原文 → '26.5 万円〜' / '20.0〜34.5 万円' / '時給 1,050 円〜' を抽出.

    salary 原文は parser 経由で「【月額】265,000円〜内訳：...」「【時給】1,500円〜※...」形式。
    冒頭の【種別】+ 最初の金額レンジだけ抽出し、「内訳」「※」以降は捨てる。
    """
    s = salary.replace("～", "〜").replace("~", "〜")
    # 月給範囲
    m = re.search(r"【?月額】?\s*([\d,]+)\s*円\s*〜\s*([\d,]+)\s*円", s)
    if m:
        return f"{yen_to_man(m.group(1))}〜{yen_to_man(m.group(2))}円"
    # 月給単独
    m = re.search(r"【?月額】?\s*([\d,]+)\s*円", s)
    if m:
        return f"{yen_to_man(m.group(1))}円〜"
    # 時給範囲
    m = re.search(r"【?時給】?\s*([\d,]+)\s*円\s*〜\s*([\d,]+)\s*円", s)
    if m:
        return f"時給 {m.group(1)}〜{m.group(2)} 円"
    # 時給単独
    m = re.search(r"【?時給】?\s*([\d,]+)\s*円", s)
    if m:
        return f"時給 {m.group(1)} 円〜"
    return s[:30] + ("…" if len(s) > 30 else "")


def extract_holiday_chip(extras: list[list[str]]) -> str:
    """休日・休暇 から '年休 110 日' / '週○〜○日勤務' (時給系) を抽出.

    フルタイム系: 「年間休日110日・週休2日制...」→ "110 日"
    パート系: 「・週1～5日勤務（時間や日数は面接時にご相談ください）...」→ "週 1〜5 日"
    """
    for k, v in extras:
        if k != "休日・休暇":
            continue
        # 1) 年間休日 N 日
        m = HOLIDAY_RE.search(v)
        if m:
            return f"{m.group(1)} 日"
        # 2) 週 N 日制
        m = re.search(r"週休\s*(\d)\s*日制", v)
        if m:
            return f"週休 {m.group(1)} 日制"
        # 3) 週 N〜M 日勤務 (パート)
        m = re.search(r"週\s*(\d+)\s*[〜~～]\s*(\d+)\s*日勤務", v)
        if m:
            return f"週 {m.group(1)}〜{m.group(2)} 日"
        # 4) 週 N 日勤務 (パート)
        m = re.search(r"週\s*(\d+)\s*日勤務", v)
        if m:
            return f"週 {m.group(1)} 日"
        return v[:15] + ("…" if len(v) > 15 else "")
    return "—"


def clean_description(body_html: str, max_len: int = 130) -> str:
    """body_html → プレーンテキスト → ハッシュタグ羅列除去 → max_len 字に短縮."""
    soup = BeautifulSoup(body_html, "lxml")
    # <br> を改行に
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    # 行ごとに整理 (空白行除去)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    text = " ".join(lines)
    # 先頭のハッシュタグ羅列 (#xxx#yyy#zzz...) を除去
    text = HASHTAG_HEAD_RE.sub("", text).strip()
    # 全角空白を半角化
    text = text.replace("　", " ").replace("　", " ")
    # 連続空白を 1 つに
    text = re.sub(r"\s+", " ", text)
    # 装飾記号で区切られた部分を「。」相当として段落化
    # 末尾「。」までで切る (max_len 以内に。の位置があればそこで止め、なければ … で切る)
    if len(text) <= max_len:
        return text
    # max_len 付近で 。 か 、 で区切れる位置を探す
    cut = text[:max_len + 30]  # 少し余裕を持って探す
    last_period = max(cut.rfind("。", 0, max_len + 1), cut.rfind("！", 0, max_len + 1), cut.rfind("？", 0, max_len + 1))
    if last_period > max_len // 2:
        return cut[: last_period + 1]
    # 句点なし: 130 字でぶった切って … 付与
    return text[:max_len].rstrip() + "…"


def simplify_address(address: str, extras: list[list[str]]) -> str:
    """カード address: 「市区名 ／ 施設名」形式に整形.

    address は parser 出力で「【福岡】あおぞらケアグループ博多（デイ・有料）」形式 (施設名)。
    都道府県+市区は extras['募集拠点'] 末尾の住所から抽出: 「...鹿児島県鹿児島市永吉2-1-14」→「鹿児島市」。
    """
    facility = re.sub(r"^【[^】]+】", "", address)
    raw_addr = ""
    for k, v in extras:
        if k == "募集拠点":
            raw_addr = v
            break
    # 都道府県+市区を抽出: 鹿児島県 + 鹿児島市 or 福岡県 + 福岡市博多区
    m = re.search(r"(?:北海道|東京都|京都府|大阪府|[^県]+?県)((?:[^市区]+?市)(?:[^区]+?区)?|[^町村]+?[町村])", raw_addr)
    if m:
        city = m.group(1)
        return f"{city} ／ {facility}" if facility else city
    return facility or address


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    jobs = {j["job_id"]: j for j in data["jobs"]}

    html = JOBS_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.find_all("li", class_="job-list-card")
    print(f"Found {len(cards)} cards in jobs.html")

    # カテゴリ別 thumbnail cycling 用カウンタ
    category_counters: dict[str, int] = {k: 0 for k in CATEGORY_VARIANTS}

    updated = 0
    for card in cards:
        link = card.find("a", class_="job-list-card__link")
        if not link:
            continue
        href = link.get("href", "")
        m = re.search(r"jobs/(\d+)\.html", href)
        if not m:
            continue
        jid = m.group(1)
        if jid not in jobs:
            print(f"  SKIP {jid}: no data")
            continue
        job = jobs[jid]

        body = link.find("div", class_="job-list-card__body")
        if not body:
            continue

        # thumbnail src cycling (カテゴリ判定 → variant を順に割当)
        category = detect_category(card)
        if category and category in CATEGORY_VARIANTS:
            thumb_img = link.find("img", class_="job-list-card__thumb-img")
            if thumb_img:
                variants = CATEGORY_VARIANTS[category]
                idx = category_counters[category] % len(variants)
                thumb_img["src"] = f"assets/img/{variants[idx]}"
                category_counters[category] += 1

        # address 更新
        addr_el = body.find("p", class_="job-list-card__address")
        if addr_el:
            addr_el.string = simplify_address(job["address"], job["extra_lines"])

        # description 更新
        desc_el = body.find("p", class_="job-list-card__description")
        if desc_el:
            desc_el.string = clean_description(job["body_html"], max_len=120)

        # meta-grid を入れる位置: description の直後 / cta の直前
        # 既存の meta-grid を削除して再生成 (冪等)
        existing_meta = body.find("dl", class_="job-card__meta-grid")
        if existing_meta:
            existing_meta.decompose()

        salary_chip = extract_salary_chip(job["salary"])
        holiday_chip = extract_holiday_chip(job["extra_lines"])

        meta_dl = soup.new_tag("dl", attrs={"class": "job-card__meta-grid"})
        dt1 = soup.new_tag("dt"); dt1.string = "月給"
        dd1 = soup.new_tag("dd", attrs={"class": "is-accent"}); dd1.string = salary_chip
        dt2 = soup.new_tag("dt"); dt2.string = "年休"
        dd2 = soup.new_tag("dd"); dd2.string = holiday_chip
        meta_dl.extend([dt1, dd1, dt2, dd2])

        # cta の直前に挿入
        cta = body.find("span", class_="job-list-card__cta")
        if cta:
            cta.insert_before(meta_dl)
            cta.insert_before("\n        ")
        else:
            body.append(meta_dl)

        updated += 1
        print(f"  OK {jid}: 月給={salary_chip}, 年休={holiday_chip}")

    JOBS_HTML.write_text(str(soup), encoding="utf-8")
    print(f"\nUpdated {updated}/{len(cards)} cards in {JOBS_HTML}")
    print("Thumbnail cycling counts:", category_counters)


if __name__ == "__main__":
    main()
