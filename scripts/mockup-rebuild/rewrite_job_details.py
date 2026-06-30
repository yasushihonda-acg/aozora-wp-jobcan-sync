"""mockup/jobs/{job_id}.html の hero/summary/sections を正本 JSON データで再生成.

PR #35 で確立した CSS コンポーネントを使い、34 件すべてを統一パターンで生成。
- hero: タグ + タイトル + リード文 (body_html 整形) + ハッシュタグ chip 群
- summary: 月給 (is-accent) / 勤務地 / 雇用形態 / 勤務時間 / 年間休日 / 残業 / 募集定員
- 仕事内容: body_html の【仕事内容】以降を箇条書きへ整形
- 応募資格: 必須スキル・経験 / 必要資格 / 歓迎スキル・経験
- 待遇・福利厚生: extras.待遇 を chip + 休暇制度/研修制度の補足
- 選考フロー: extras.選考フロー (↓ 区切り) を numbered ステップ

aside (関連求人) / header / footer / breadcrumb / 末尾 entry-cta は維持。
hero__media の thumbnail img は mockup/jobs.html の同 job_id カードと src を同期 (一覧 → 詳細でクリック時に同じ絵が出るように)。
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = HERE / "jobs_data.json"
JOBS_DIR = REPO / "mockup" / "jobs"
JOBS_HTML = REPO / "mockup" / "jobs.html"


def build_thumbnail_mapping(jobs_html_path: Path) -> dict[str, str]:
    """jobs.html を parse して job_id → thumbnail src の mapping を構築.

    詳細ページ側で <img src="../assets/img/illust-job-XXX.png"> を一覧と同期させるための真理ソース。
    rewrite_jobs_html.py が cycling を適用した後の jobs.html を読む前提。
    戻り値の src は「assets/img/illust-job-XXX.png」(jobs.html 内のまま) — 詳細ページに書く時は ../ prefix を付ける。
    """
    html = jobs_html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    mapping: dict[str, str] = {}
    for card in soup.find_all("li", class_="job-list-card"):
        link = card.find("a", class_="job-list-card__link")
        if not link:
            continue
        href = link.get("href", "")
        m = re.search(r"jobs/(\d+)\.html", href)
        if not m:
            continue
        jid = m.group(1)
        img = link.find("img", class_="job-list-card__thumb-img")
        if not img:
            continue
        src = img.get("src", "")
        if src:
            mapping[jid] = src
    return mapping

HASHTAG_RE = re.compile(r"[#＃]\s*[^\s#＃◆■★●※【\n]+")
HOLIDAY_RE = re.compile(r"年間休日\s*(\d+)\s*日")
WORK_DESCRIPTION_HEAD = "【仕事内容】"


# ── ヘルパー: 既出のロジックを流用 (rewrite_jobs_html.py と同一) ──

def yen_to_man(yen_str: str) -> str:
    yen = int(yen_str.replace(",", ""))
    man = yen / 10000
    if man == int(man):
        return f"{int(man)}.0 万"
    return f"{man:.1f}".rstrip("0").rstrip(".") + " 万"


def extract_salary_chip(salary: str) -> str:
    s = salary.replace("～", "〜").replace("~", "〜")
    m = re.search(r"【?月額】?\s*([\d,]+)\s*円\s*〜\s*([\d,]+)\s*円", s)
    if m:
        return f"{yen_to_man(m.group(1))}〜{yen_to_man(m.group(2))}円"
    m = re.search(r"【?月額】?\s*([\d,]+)\s*円", s)
    if m:
        return f"{yen_to_man(m.group(1))}円〜"
    m = re.search(r"【?時給】?\s*([\d,]+)\s*円\s*〜\s*([\d,]+)\s*円", s)
    if m:
        return f"時給 {m.group(1)}〜{m.group(2)} 円"
    m = re.search(r"【?時給】?\s*([\d,]+)\s*円", s)
    if m:
        return f"時給 {m.group(1)} 円〜"
    return s[:30] + ("…" if len(s) > 30 else "")


def extract_salary_detail(salary: str) -> str:
    """「内訳：基本給（181,360円）+業務手当（64,640円）+...」部分を取り出し簡素化."""
    s = salary.replace("～", "〜").replace("~", "〜")
    m = re.search(r"内訳[：:]\s*(.+?)(?:※|$)", s, re.DOTALL)
    if m:
        return m.group(1).strip().rstrip("、,。 ")
    return ""


def extract_holiday_chip(extras: list[list[str]]) -> str:
    for k, v in extras:
        if k != "休日・休暇":
            continue
        m = HOLIDAY_RE.search(v)
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
    return "—"


def simplify_address(address: str, extras: list[list[str]]) -> tuple[str, str]:
    """returns (一行目: 市区, 二行目small: 施設名 + 住所末尾)."""
    facility = re.sub(r"^【[^】]+】", "", address)
    raw_addr = ""
    for k, v in extras:
        if k == "募集拠点":
            raw_addr = v
            break
    m = re.search(r"(?:北海道|東京都|京都府|大阪府|[^県]+?県)((?:[^市区]+?市)(?:[^区]+?区)?|[^町村]+?[町村])", raw_addr)
    city = m.group(1) if m else ""
    return (city or facility, facility)


# ── ヒーロー用 ──

def extract_hashtags(body_html: str) -> list[str]:
    """body_html 先頭付近にあるハッシュタグを 6 〜 8 個まで抽出 (空白/区切りなし連結にも対応)."""
    soup = BeautifulSoup(body_html, "lxml")
    text = soup.get_text(separator="\n")
    # 先頭 300 字に含まれるハッシュタグだけ拾う (本文中の「※20代〜70代」とかと誤マッチしないため)
    head = text[:400]
    tags: list[str] = []
    seen: set[str] = set()
    # 「#xxx」「＃xxx」両対応、連結 (例: #ケア重視#未経験) も separable
    pattern = re.compile(r"[#＃]\s*([^\s#＃◆■★●※【\n、。]+)")
    for m in pattern.finditer(head):
        tag = m.group(1).strip()
        # 例外: 「20代〜70代」みたいな数字始まりは捨てる
        if not tag or tag.isdigit():
            continue
        key = tag
        if key in seen:
            continue
        seen.add(key)
        tags.append(f"#{tag}")
        if len(tags) >= 8:
            break
    return tags


def extract_lead_paragraph(body_html: str, max_len: int = 180) -> str:
    """body_html → ハッシュタグ羅列除去 → 【仕事内容】より前の本文 を整形."""
    soup = BeautifulSoup(body_html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    # 行ごとに stripped、空行スキップ
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    # 先頭がハッシュタグ羅列の行は除去
    body_lines: list[str] = []
    for ln in lines:
        if re.fullmatch(r"(?:[#＃]\s*[^\s#＃]+\s*)+", ln):
            continue
        body_lines.append(ln)
    # 【仕事内容】以降は除外 (hero リードには出さない)
    cut: list[str] = []
    for ln in body_lines:
        if WORK_DESCRIPTION_HEAD in ln:
            head = ln.split(WORK_DESCRIPTION_HEAD)[0].strip()
            if head:
                cut.append(head)
            break
        cut.append(ln)
    text = " ".join(cut)
    # 先頭のハッシュタグ残骸を除去 (#xxx#yyy#zzz...が同一行にあった場合)
    text = re.sub(r"^(?:[#＃]\s*[^\s#＃]+\s*)+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_len:
        return text
    cut2 = text[: max_len + 40]
    last_period = max(
        cut2.rfind("。", 0, max_len + 1),
        cut2.rfind("！", 0, max_len + 1),
        cut2.rfind("？", 0, max_len + 1),
    )
    if last_period > max_len // 2:
        return cut2[: last_period + 1]
    return text[:max_len].rstrip() + "…"


# ── 仕事内容セクション ──

def extract_work_description(body_html: str) -> list[tuple[str, str]]:
    """【仕事内容】以降を「リード段落」と「箇条書き行」リストに分解.

    戻り値: [("p", "段落テキスト"), ("li", "リスト項目")] のシーケンス
    """
    soup = BeautifulSoup(body_html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    started = False
    items: list[tuple[str, str]] = []
    bullet_re = re.compile(r"^([〇○●□■◇◆▽▼☆★・※])\s*(.*)")
    for ln in lines:
        if not started:
            if WORK_DESCRIPTION_HEAD in ln:
                started = True
                tail = ln.split(WORK_DESCRIPTION_HEAD, 1)[1].strip()
                if tail:
                    # 先頭の小タイトル (例: "事務業務全般") を段落として
                    items.append(("p", tail))
            continue
        m = bullet_re.match(ln)
        if m:
            text_item = m.group(2).strip() or m.group(1)
            items.append(("li", text_item))
        else:
            items.append(("p", ln))
    return items


# ── 応募資格 ──

def extract_qualifications(extras: list[list[str]]) -> list[tuple[str, str]]:
    """戻り値: [("必須", "..."), ("歓迎", "...")] (片方しかなくても可)."""
    must: list[str] = []
    want: list[str] = []
    for k, v in extras:
        if k in ("必須スキル・経験", "必要資格"):
            must.append(v.strip())
        elif k == "歓迎スキル・経験":
            want.append(v.strip())
    out: list[tuple[str, str]] = []
    if must:
        out.append(("必須", " / ".join(must)))
    if want:
        out.append(("歓迎", " / ".join(want)))
    return out


# ── 待遇・福利厚生 ──

def extract_benefits(extras: list[list[str]]) -> tuple[list[str], list[tuple[str, str]]]:
    """待遇 extras を chip リスト + 補足段落リストに分解.

    chip = 【福利厚生】配下の ・ 区切り項目
    paragraphs = 【研修制度】等のその他見出しブロック
    """
    chips: list[str] = []
    paragraphs: list[tuple[str, str]] = []
    for k, v in extras:
        if k != "待遇":
            continue
        # 【タイトル】 で分割
        sections = re.split(r"【([^】]+)】", v)
        # 最初の空要素を skip
        # sections = ["", "福利厚生", "・社保完備...", "研修制度", "OJT..."]
        for i in range(1, len(sections), 2):
            heading = sections[i].strip()
            content = sections[i + 1].strip() if i + 1 < len(sections) else ""
            if heading == "福利厚生":
                # ・ 区切りで chip 化
                for item in re.split(r"[・•]", content):
                    s = item.strip()
                    s = re.sub(r"※[^・•]*$", "", s).strip()  # ※ 注記は捨てる
                    if s:
                        chips.append(s)
            else:
                paragraphs.append((heading, content))
    return chips, paragraphs


def extract_holiday_paragraph(extras: list[list[str]]) -> str:
    """休日・休暇 extras 全文を 「・」区切りで読みやすく."""
    for k, v in extras:
        if k != "休日・休暇":
            continue
        # 全角・ 中点で分けて join
        items = [s.strip().lstrip("・").strip() for s in v.split("・") if s.strip().lstrip("・").strip()]
        return " ／ ".join(items)
    return ""


# ── 選考フロー ──

def extract_selection_flow(extras: list[list[str]]) -> list[str]:
    for k, v in extras:
        if k != "選考フロー":
            continue
        steps = [s.strip() for s in v.split("↓") if s.strip()]
        # ※ 注記を別行で混ぜないために、行内 ※ 以降は補足としてその step に含めたまま
        return steps
    return []


# ── HTML 生成 ──

def build_new_main_html(job: dict, *, indent: str = "        ") -> str:
    title = job["title"]
    labels = job["label"].split()
    # label は parser 出力で「事務職正社員」のような連結文字列 → 分割
    if not labels or len(labels) == 1:
        # 既知パターン: 「介護職正社員」「事務職パート」等を分けるため、雇用形態キーワードで分割
        emp_patterns = ["正社員", "パート", "アルバイト", "契約社員", "短時間正社員"]
        raw = job["label"]
        for emp in emp_patterns:
            if raw.endswith(emp):
                labels = [raw[: -len(emp)].strip(), emp]
                break
        else:
            labels = [raw]

    salary_chip = extract_salary_chip(job["salary"])
    salary_detail = extract_salary_detail(job["salary"])
    city, facility = simplify_address(job["address"], job["extra_lines"])
    holiday_chip = extract_holiday_chip(job["extra_lines"])
    holiday_paragraph = extract_holiday_paragraph(job["extra_lines"])
    work_time = ""
    capacity = ""
    for k, v in job["extra_lines"]:
        if k == "勤務時間":
            work_time = v.strip()
        elif k == "定員":
            capacity = v.strip()
    work_time_short = work_time[:30] + ("…" if len(work_time) > 30 else "")
    work_time_detail = work_time if work_time != work_time_short else ""

    apply_url = f"https://recruit.jobcan.jp/aozora/entry/new/{job['job_id']}"

    # ハッシュタグ
    hashtags = extract_hashtags(job["body_html"])
    lead = extract_lead_paragraph(job["body_html"], max_len=200)

    # 仕事内容
    work_items = extract_work_description(job["body_html"])

    # 応募資格
    quals = extract_qualifications(job["extra_lines"])

    # 待遇
    benefit_chips, benefit_paragraphs = extract_benefits(job["extra_lines"])

    # 選考フロー
    selection_steps = extract_selection_flow(job["extra_lines"])

    # ── HTML 部分組み立て ──
    lines: list[str] = []

    # hero copy
    lines.append('<div class="job-detail-hero__copy">')
    lines.append('  <div class="job-detail-hero__tags">')
    for lbl in labels:
        lines.append(f'    <span class="job-card__tag">{lbl}</span>')
    lines.append("  </div>")
    lines.append(f'  <h1 class="job-detail-hero__title">{title}</h1>')
    lines.append(f'  <p class="job-detail-hero__lead">{lead}</p>')
    if hashtags:
        lines.append('  <ul class="job-hashtags">')
        for t in hashtags:
            lines.append(f'    <li class="job-hashtags__item">{t}</li>')
        lines.append("  </ul>")
    lines.append("</div>")

    hero_copy_html = "\n".join(indent + ln for ln in lines)

    # summary header
    summary_lines: list[str] = []
    summary_lines.append('<header class="job-detail-summary">')
    summary_lines.append('  <dl class="job-detail-summary__meta">')
    # 月給
    summary_lines.append("    <div>")
    summary_lines.append("      <dt>月給</dt>")
    if salary_detail:
        summary_lines.append(f'      <dd class="is-accent">{salary_chip}<small>{salary_detail}</small></dd>')
    else:
        summary_lines.append(f'      <dd class="is-accent">{salary_chip}</dd>')
    summary_lines.append("    </div>")
    # 勤務地
    summary_lines.append("    <div>")
    summary_lines.append("      <dt>勤務地</dt>")
    if facility and city != facility:
        summary_lines.append(f"      <dd>{city}<small>{facility}</small></dd>")
    else:
        summary_lines.append(f"      <dd>{city}</dd>")
    summary_lines.append("    </div>")
    # 雇用形態
    emp = labels[1] if len(labels) >= 2 else labels[0]
    summary_lines.append(f"    <div><dt>雇用形態</dt><dd>{emp}</dd></div>")
    # 勤務時間
    if work_time:
        summary_lines.append("    <div>")
        summary_lines.append("      <dt>勤務時間</dt>")
        if work_time_detail:
            summary_lines.append(f"      <dd>{work_time_short}<small>{work_time_detail}</small></dd>")
        else:
            summary_lines.append(f"      <dd>{work_time_short}</dd>")
        summary_lines.append("    </div>")
    # 年間休日
    if holiday_chip and holiday_chip != "—":
        summary_lines.append("    <div>")
        summary_lines.append("      <dt>年間休日</dt>")
        if holiday_paragraph:
            summary_lines.append(f'      <dd>{holiday_chip}<small>{holiday_paragraph[:60]}</small></dd>')
        else:
            summary_lines.append(f"      <dd>{holiday_chip}</dd>")
        summary_lines.append("    </div>")
    # 募集定員
    if capacity:
        summary_lines.append(f"    <div><dt>募集定員</dt><dd>{capacity}</dd></div>")
    summary_lines.append("  </dl>")
    summary_lines.append('  <div class="job-detail-summary__cta">')
    summary_lines.append(
        f'    <a class="btn btn--primary" href="{apply_url}" target="_blank" rel="noopener">この求人に応募する</a>'
    )
    summary_lines.append('    <a class="btn btn--ghost" href="../jobs.html">他の求人を見る</a>')
    summary_lines.append("  </div>")
    summary_lines.append(
        '  <p class="notice-bar" style="margin-top: var(--space-5);">応募ボタンを押すと、外部サイト (ジョブカン採用管理) の応募フォームに遷移します。</p>'
    )
    summary_lines.append("</header>")

    summary_html = "\n".join(indent + ln for ln in summary_lines)

    # 仕事内容 section
    work_lines: list[str] = []
    work_lines.append('<section class="job-detail-section">')
    work_lines.append('  <div class="job-detail-section__head">')
    work_lines.append('    <span class="job-detail-section__en">Job Description</span>')
    work_lines.append('    <h2 class="job-detail-section__title">仕事内容</h2>')
    work_lines.append("  </div>")
    work_lines.append('  <div class="job-detail-section__body">')
    # 連続する li を <ul> でまとめる
    i = 0
    while i < len(work_items):
        kind, t = work_items[i]
        if kind == "p":
            work_lines.append(f"    <p>{t}</p>")
            i += 1
        else:
            # collect consecutive li
            work_lines.append("    <ul>")
            while i < len(work_items) and work_items[i][0] == "li":
                work_lines.append(f"      <li>{work_items[i][1]}</li>")
                i += 1
            work_lines.append("    </ul>")
    work_lines.append("  </div>")
    work_lines.append("</section>")

    work_html = "\n".join(indent + ln for ln in work_lines)

    # 応募資格
    qual_html_lines: list[str] = []
    if quals:
        qual_html_lines.append('<section class="job-detail-section">')
        qual_html_lines.append('  <div class="job-detail-section__head">')
        qual_html_lines.append('    <span class="job-detail-section__en">Qualifications</span>')
        qual_html_lines.append('    <h2 class="job-detail-section__title">応募資格</h2>')
        qual_html_lines.append("  </div>")
        qual_html_lines.append('  <div class="job-detail-section__body">')
        qual_html_lines.append('    <ul class="job-qualification">')
        for kind, val in quals:
            cls = "job-qualification__key job-qualification__key--accent" if kind == "必須" else "job-qualification__key"
            qual_html_lines.append('      <li class="job-qualification__row">')
            qual_html_lines.append(f'        <span class="{cls}">{kind}</span>')
            qual_html_lines.append(f'        <div class="job-qualification__val">{val}</div>')
            qual_html_lines.append("      </li>")
        qual_html_lines.append("    </ul>")
        qual_html_lines.append("  </div>")
        qual_html_lines.append("</section>")
    qual_html = "\n".join(indent + ln for ln in qual_html_lines)

    # 待遇・福利厚生
    benefits_html_lines: list[str] = []
    if benefit_chips or holiday_paragraph or benefit_paragraphs:
        benefits_html_lines.append('<section class="job-detail-section">')
        benefits_html_lines.append('  <div class="job-detail-section__head">')
        benefits_html_lines.append('    <span class="job-detail-section__en">Benefits</span>')
        benefits_html_lines.append('    <h2 class="job-detail-section__title">待遇・福利厚生</h2>')
        benefits_html_lines.append("  </div>")
        benefits_html_lines.append('  <div class="job-detail-section__body">')
        if benefit_chips:
            benefits_html_lines.append('    <ul class="job-benefits">')
            for c in benefit_chips:
                benefits_html_lines.append(f'      <li class="job-benefits__item">{c}</li>')
            benefits_html_lines.append("    </ul>")
        if holiday_paragraph:
            benefits_html_lines.append(
                f'    <p style="margin-top: var(--space-5);"><strong>休暇制度</strong> ／ {holiday_paragraph}</p>'
            )
        for heading, content in benefit_paragraphs:
            # 改行を整理
            content_one_line = re.sub(r"\s+", " ", content).strip()
            benefits_html_lines.append(f"    <p><strong>{heading}</strong> ／ {content_one_line}</p>")
        benefits_html_lines.append("  </div>")
        benefits_html_lines.append("</section>")
    benefits_html = "\n".join(indent + ln for ln in benefits_html_lines)

    # 選考フロー
    flow_html_lines: list[str] = []
    if selection_steps:
        flow_html_lines.append('<section class="job-detail-section">')
        flow_html_lines.append('  <div class="job-detail-section__head">')
        flow_html_lines.append('    <span class="job-detail-section__en">Selection Flow</span>')
        flow_html_lines.append('    <h2 class="job-detail-section__title">選考の流れ</h2>')
        flow_html_lines.append("  </div>")
        flow_html_lines.append('  <div class="job-detail-section__body">')
        flow_html_lines.append('    <ol class="selection-flow">')
        for step in selection_steps:
            flow_html_lines.append(f'      <li class="selection-flow__step">{step}</li>')
        flow_html_lines.append("    </ol>")
        flow_html_lines.append("  </div>")
        flow_html_lines.append("</section>")
    flow_html = "\n".join(indent + ln for ln in flow_html_lines)

    # 末尾 entry-cta (apply_url のみ差し替え、構造は既存維持)
    entry_cta_html = (
        f'{indent}<section style="padding-top: var(--space-10);">\n'
        f'{indent}  <div class="entry-cta">\n'
        f'{indent}    <div>\n'
        f'{indent}      <span class="eyebrow" style="color: rgba(255,255,255,0.78);">Apply Now</span>\n'
        f'{indent}      <h2 class="entry-cta__title">この求人に応募する</h2>\n'
        f'{indent}      <p class="entry-cta__lead">ジョブカン応募フォームへ進みます。</p>\n'
        f"{indent}    </div>\n"
        f"{indent}    <div>\n"
        f'{indent}      <div class="entry-cta__actions">\n'
        f'{indent}        <a class="btn btn--on-dark" href="{apply_url}" target="_blank" rel="noopener">エントリーフォームへ進む</a>\n'
        f"{indent}      </div>\n"
        f"{indent}    </div>\n"
        f"{indent}  </div>\n"
        f"{indent}</section>"
    )

    return hero_copy_html, summary_html, work_html, qual_html, benefits_html, flow_html, entry_cta_html


# ── ファイル単位の置換ロジック ──

def rewrite_file(path: Path, job: dict, thumb_src: str | None = None) -> bool:
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    hero_copy_html, summary_html, work_html, qual_html, benefits_html, flow_html, entry_cta_html = (
        build_new_main_html(job)
    )

    # hero__media の thumbnail src を一覧と同期 (jobs.html での cycling 結果に揃える)
    if thumb_src:
        media = soup.find("div", class_="job-detail-hero__media")
        if media:
            img = media.find("img")
            if img:
                # jobs.html は "assets/img/..." 形式、詳細ページは "../assets/img/..." 形式
                img["src"] = f"../{thumb_src}" if not thumb_src.startswith("../") else thumb_src

    # 「← 求人一覧へ戻る」 ナビを breadcrumb の上に挿入 (冪等)
    breadcrumb = soup.find("p", class_="breadcrumb")
    if breadcrumb is not None:
        # 既存の back-nav があれば一旦削除して入れ直す (冪等のため)
        existing = soup.find("nav", class_="job-detail__back-nav")
        if existing is not None:
            existing.decompose()
        back_html = (
            '<nav class="job-detail__back-nav" aria-label="ナビゲーション">'
            '<a class="job-detail__back-link" href="../jobs.html">'
            '<span class="job-detail__back-arrow" aria-hidden="true">←</span>'
            "求人一覧へ戻る"
            "</a>"
            "</nav>"
        )
        back_nav = BeautifulSoup(back_html, "html.parser")
        breadcrumb.insert_before(back_nav)

    # hero copy 置換
    hero = soup.find("div", class_="job-detail-hero__copy")
    if not hero:
        print(f"  SKIP {path.name}: no hero copy element")
        return False
    new_hero = BeautifulSoup(hero_copy_html.lstrip(), "html.parser")
    hero.replace_with(new_hero)

    # main 配下を再構築: header.job-detail-summary + 仕事内容セクション以降 (entry-cta まで) を全削除して入れ直す
    article = soup.find("article", class_="page-job-detail__main")
    if not article:
        print(f"  SKIP {path.name}: no article")
        return False

    # 既存の子要素 (job-detail-summary, section.job-detail-section, end CTA section) を全削除
    for child in list(article.find_all(["header", "section"], recursive=False)):
        child.decompose()
    # コメントノードも除去
    from bs4 import Comment
    for cm in article.find_all(string=lambda s: isinstance(s, Comment)):
        cm.extract()

    # 新規 HTML を組み立てて挿入
    combined = "\n\n".join(
        h for h in [summary_html, work_html, qual_html, benefits_html, flow_html, entry_cta_html] if h
    )
    new_article_content = BeautifulSoup(combined.lstrip(), "html.parser")
    article.append(new_article_content)

    path.write_text(str(soup), encoding="utf-8")
    return True


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    jobs = {j["job_id"]: j for j in data["jobs"]}

    # jobs.html の cycling 結果を真理ソースに、詳細ページ thumbnail を同期
    if not JOBS_HTML.exists():
        raise FileNotFoundError(
            f"{JOBS_HTML} が見つかりません。先に rewrite_jobs_html.py を実行してください。"
        )
    thumb_mapping = build_thumbnail_mapping(JOBS_HTML)
    print(f"Loaded {len(thumb_mapping)} thumbnail mappings from {JOBS_HTML.name}")

    ok = 0
    skipped = 0
    missing_thumb: list[str] = []
    for jid, job in jobs.items():
        path = JOBS_DIR / f"{jid}.html"
        if not path.exists():
            print(f"  MISSING {jid}.html")
            skipped += 1
            continue
        thumb_src = thumb_mapping.get(jid)
        if not thumb_src:
            missing_thumb.append(jid)
        try:
            if rewrite_file(path, job, thumb_src=thumb_src):
                print(f"  OK {jid}: thumb={thumb_src or '(unchanged)'} | {job['title'][:50]}")
                ok += 1
        except Exception as e:
            print(f"  ERR {jid}: {type(e).__name__}: {e}")
            skipped += 1

    print(f"\nRewrote {ok}/{len(jobs)} files (skipped/error: {skipped})")
    if missing_thumb:
        print(f"WARN: jobs.html に thumbnail マッピングがない job_id: {missing_thumb}")


if __name__ == "__main__":
    main()
