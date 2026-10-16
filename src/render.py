"""渲染手机优先的静态网页。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, select_autoescape
from markupsafe import Markup, escape

from common import out_dir

logger = logging.getLogger("brief")

env = Environment(autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)

LATIN_RE = re.compile(r"^[\x20-\x7e]+$")


def term_key(term: str) -> str:
    return term.strip().lower()


def find_term(text: str, term: str):
    flags = re.IGNORECASE if LATIN_RE.match(term) else 0
    return re.search(re.escape(term), text, flags)


def mark_terms(text: str, terms: list[dict], used: set[str], gloss_map: dict[str, str]):
    """把本卡片里首次出现、且全局还没标过的术语包成可点击的 span。"""
    if not text:
        return Markup("")

    matches: list[tuple[int, int, str, str]] = []
    for item in terms:
        term = (item.get("term") or "").strip()
        key = term_key(term)
        if not term or key in used:
            continue
        found = find_term(text, term)
        if not found:
            continue
        start, end = found.span()
        if any(not (end <= s or start >= e) for s, e, _, _ in matches):
            continue  # 与前一个术语的区间重叠，跳过
        matches.append((start, end, term, gloss_map.get(key, item.get("gloss", ""))))
        used.add(key)

    if not matches:
        return Markup(escape(text))

    matches.sort(key=lambda item: item[0])
    parts: list[Markup] = []
    cursor = 0
    for start, end, term, gloss in matches:
        parts.append(Markup(escape(text[cursor:start])))
        parts.append(
            Markup('<span class="term" role="button" tabindex="0" data-term="')
            + escape(term)
            + Markup('" data-gloss="')
            + escape(gloss)
            + Markup('">')
            + escape(text[start:end])
            + Markup("</span>")
        )
        cursor = end
    parts.append(Markup(escape(text[cursor:])))
    return Markup("").join(parts)


def prepare_cards(cards: list[dict]) -> tuple[list[dict], int]:
    """给每张卡片的正文加上术语标注，同一个词只标最早出现的那一次。"""
    gloss_map: dict[str, str] = {}
    for card in cards:
        for item in card.get("terms") or []:
            term = (item.get("term") or "").strip()
            if term:
                gloss_map.setdefault(term_key(term), item.get("gloss", ""))

    used: set[str] = set()
    prepared: list[dict] = []
    for card in cards:
        terms = card.get("terms") or []
        item = dict(card)
        for field in ("what", "background", "why", "next"):
            item[f"{field}_html"] = mark_terms(card.get(field) or "", terms, used, gloss_map)
        item["term_count"] = len(terms)
        prepared.append(item)

    return prepared, len(used)

TEMPLATE = env.from_string(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow">
<meta name="description" content="{{ meta_desc }}">
<meta property="og:type" content="website">
<meta property="og:title" content="{{ page_title }}">
<meta property="og:description" content="{{ meta_desc }}">
<meta property="og:site_name" content="{{ heading }}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="{{ heading }} RSS" href="feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%232f6feb'/%3E%3Ctext x='50%25' y='50%25' dy='.35em' text-anchor='middle' font-family='system-ui' font-size='34' font-weight='700' fill='white'%3EAI%3C/text%3E%3C/svg%3E">
<title>{{ page_title }}</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f4f5f7;
    --card: #ffffff;
    --ink: #16181d;
    --dim: #6b7280;
    --line: #e5e7eb;
    --accent: #2f6feb;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #101216; --card: #1a1d23; --ink: #e8eaed; --dim: #9aa0a6; --line: #2a2f38; --accent: #7aa5ff; }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 18px 14px 56px;
    background: var(--bg); color: var(--ink);
    font: 16px/1.72 -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    max-width: 680px; margin-inline: auto;
    -webkit-text-size-adjust: 100%;
  }
  header { margin-bottom: 18px; }
  h1 { font-size: 21px; line-height: 1.4; margin: 0 0 6px; letter-spacing: .3px; }
  .sub { color: var(--dim); font-size: 13px; }
  .warn {
    border: 1px solid #f0c36d; background: #fff8e6; color: #7a5b12;
    border-radius: 8px; padding: 10px 12px; font-size: 13px; margin: 14px 0; line-height: 1.6;
  }
  @media (prefers-color-scheme: dark) { .warn { background: #2a2413; color: #e8cf95; border-color: #4a3d1a; } }
  article {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 15px 16px 13px; margin-bottom: 14px;
  }
  h2 { font-size: 17px; line-height: 1.5; margin: 0 0 8px; }
  .num { color: var(--accent); font-weight: 600; margin-right: 6px; font-variant-numeric: tabular-nums; }
  .meta { color: var(--dim); font-size: 12px; margin: 0 0 10px; }
  .what { margin: 0 0 10px; }
  .what strong { background: linear-gradient(transparent 62%, rgba(47,111,235,.18) 62%); }
  details { border-top: 1px dashed var(--line); padding-top: 9px; }
  summary { cursor: pointer; color: var(--accent); font-size: 14px; outline: none; }
  details section { margin-top: 11px; }
  details h3 { font-size: 13px; margin: 0 0 4px; color: var(--dim); font-weight: 600; }
  details p { margin: 0; font-size: 15px; }
  .src { margin: 11px 0 0; font-size: 12px; color: var(--dim); }
  .src a { color: var(--dim); text-decoration: none; border-bottom: 1px solid var(--line); }
  .term-hint { color: var(--dim); font-size: 12px; margin-top: 4px; }
  .term {
    border-bottom: 1px dashed var(--accent);
    cursor: pointer;
    padding: 1px 0;
    -webkit-tap-highlight-color: transparent;
  }
  .term:active { background: rgba(47,111,235,.16); }
  .mask {
    position: fixed; inset: 0; background: rgba(0,0,0,.38);
    opacity: 0; pointer-events: none; transition: opacity .18s ease; z-index: 49;
  }
  .mask.open { opacity: 1; pointer-events: auto; }
  .sheet {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 50;
    background: var(--card); border-top: 1px solid var(--line);
    border-top-left-radius: 16px; border-top-right-radius: 16px;
    padding: 16px 18px calc(20px + env(safe-area-inset-bottom));
    transform: translateY(110%); transition: transform .22s ease;
    max-height: 62vh; overflow-y: auto;
    box-shadow: 0 -8px 30px rgba(0,0,0,.18);
  }
  .sheet.open { transform: translateY(0); }
  .sheet-head {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 12px; margin-bottom: 8px;
  }
  .sheet-term { font-weight: 700; font-size: 17px; line-height: 1.4; }
  .sheet-close {
    border: 0; background: transparent; color: var(--dim);
    font-size: 24px; line-height: 1; padding: 0 4px; cursor: pointer;
  }
  .sheet-gloss { margin: 0; font-size: 15px; line-height: 1.78; }
  .about {
    margin: 14px 0 4px; border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 14px; background: var(--card); font-size: 14px; line-height: 1.72;
  }
  .about summary { cursor: pointer; color: var(--accent); font-weight: 600; outline: none; }
  .about p { margin: 10px 0 0; color: var(--ink); }
  .about a { color: var(--accent); }
  footer { color: var(--dim); font-size: 12px; text-align: center; margin-top: 26px; line-height: 2; }
  footer a { color: var(--dim); }
  .archive li { margin-bottom: 8px; }
  .archive a { color: var(--accent); text-decoration: none; }
</style>
</head>
<body>
{% if is_archive %}
  <header>
    <h1>往期早报</h1>
    <div class="sub">共 {{ archive|length }} 期</div>
  </header>
  <ul class="archive">
  {% for item in archive %}
    <li><a href="{{ item.file }}">{{ item.date }}</a> {% if item.count %}<span class="sub">· {{ item.count }} 条</span>{% endif %}</li>
  {% endfor %}
  </ul>
{% else %}
  <header>
    <h1>{{ heading }}</h1>
    <div class="sub">{{ date_str }} · 共 {{ cards|length }} 条 · 生成于 {{ generated_at }}</div>
    <details class="about">
      <summary>这是什么？</summary>
      <p>每天自动从 50 多个国内外信息源（Hacker News、TechCrunch、量子位、IT之家、少数派、arXiv 等）
      抓取 AI 与科技动态，由 AI 去重、打分、筛选后写成卡片。每条讲清「是什么 · 背景 · 为什么重要 · 接下来」，
      正文里带虚线的术语点一下就有解释。</p>
      <p>每天中午更新。想看往期点底部「往期早报」；想每天自动收到，把 <a href="feed.xml">RSS</a> 加进阅读器即可。</p>
    </details>
    {% if term_count %}<div class="term-hint">正文里带虚线的术语，点一下看解释</div>{% endif %}
  </header>

  {% if degraded %}
  <div class="warn">{{ degraded_reason }}</div>
  {% endif %}

  {% for card in cards %}
  <article>
    <h2><span class="num">{{ "%02d"|format(loop.index) }}</span>{{ card.title }}</h2>
    <p class="meta">{{ card.sources[0].name if card.sources }} · 置信度 {{ card.confidence }}</p>
    <p class="what">{{ card.what_html }}</p>
    <details>
      <summary>背景 · 为什么重要 · 接下来</summary>
      <section><h3>背景</h3><p>{{ card.background_html }}</p></section>
      <section><h3>为什么重要</h3><p>{{ card.why_html }}</p></section>
      <section><h3>接下来</h3><p>{{ card.next_html }}</p></section>
    </details>
    <p class="src">来源：{% for s in card.sources %}<a href="{{ s.url }}">{{ s.name }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p>
  </article>
  {% endfor %}
{% endif %}

<footer>
  <a href="archive.html">往期早报</a> · <a href="feed.xml">RSS 订阅</a>
  {% if source_note %}<br>{{ source_note }}{% endif %}
  {% if generated_at %}<br>{{ generated_at }} 生成{% endif %}
</footer>

<div class="mask" id="term-mask"></div>
<div class="sheet" id="term-sheet" role="dialog" aria-modal="true" aria-label="术语解释">
  <div class="sheet-head">
    <span class="sheet-term" id="term-title"></span>
    <button class="sheet-close" id="term-close" type="button" aria-label="关闭">×</button>
  </div>
  <p class="sheet-gloss" id="term-gloss"></p>
</div>

<script>
(function () {
  var sheet = document.getElementById('term-sheet');
  var mask = document.getElementById('term-mask');
  var titleEl = document.getElementById('term-title');
  var glossEl = document.getElementById('term-gloss');
  if (!sheet || !mask) { return; }

  function open(term, gloss) {
    titleEl.textContent = term || '';
    glossEl.textContent = gloss || '';
    sheet.classList.add('open');
    mask.classList.add('open');
  }
  function close() {
    sheet.classList.remove('open');
    mask.classList.remove('open');
  }
  function payload(el) {
    return [el.getAttribute('data-term'), el.getAttribute('data-gloss')];
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    var el = target.closest ? target.closest('.term') : null;
    if (el) {
      var data = payload(el);
      open(data[0], data[1]);
      return;
    }
    if (target === mask || (target.id === 'term-close')) { close(); }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { close(); return; }
    var active = document.activeElement;
    if ((event.key === 'Enter' || event.key === ' ')
        && active && active.classList && active.classList.contains('term')) {
      var data = payload(active);
      open(data[0], data[1]);
      event.preventDefault();
    }
  });
})();
</script>
</body>
</html>
"""
)


def source_note(stats: list[dict]) -> str:
    if not stats:
        return ""
    failed = [item for item in stats if not item["count"]]
    ok = len(stats) - len(failed)
    note = f"本次 {ok}/{len(stats)} 个源可用"
    if failed:
        names = "、".join(item["name"] for item in failed[:6])
        note += f"；未取到：{names}"
        if len(failed) > 6:
            note += f" 等 {len(failed)} 个"
    return note


def render_brief(cfg: dict, cards: list[dict], date_str: str, generated_at: str,
                 stats: list[dict], degraded: bool, degraded_reason: str) -> Path:
    directory = out_dir(cfg)
    prepared, term_count = prepare_cards(cards)
    html = TEMPLATE.render(
        page_title=f"{cfg['site'].get('title', '早报')} · {date_str}",
        meta_desc=f"{date_str} AI 早报，共 {len(cards)} 条：" + "、".join(c["title"] for c in cards[:3]),
        heading=cfg["site"].get("title", "早报"),
        date_str=date_str,
        generated_at=generated_at,
        cards=prepared,
        term_count=term_count,
        is_archive=False,
        degraded=degraded,
        degraded_reason=degraded_reason,
        source_note=source_note(stats),
        archive=[],
    )

    dated = directory / f"{date_str}.html"
    dated.write_text(html, encoding="utf-8")
    (directory / "index.html").write_text(html, encoding="utf-8")

    render_archive(cfg, directory)
    render_feed(cfg, directory)
    logger.info("网页已生成：%s", dated)
    return dated


FEED_ITEM = """  <item>
    <title>{title}</title>
    <link>{url}</link>
    <guid isPermaLink="false">{guid}</guid>
    <pubDate>{pub}</pubDate>
    <description>{desc}</description>
  </item>"""


def render_feed(cfg: dict, directory: Path, limit: int = 30) -> None:
    """生成 RSS：让读者用阅读器订阅，不依赖任何第三方服务。"""
    briefs_dir = directory.parent / "data" / "briefs"
    if not briefs_dir.exists():
        return
    site = cfg.get("site", {})
    base = (site.get("base_url") or "").rstrip("/")
    title = site.get("title", "早报")
    from email.utils import format_datetime
    from datetime import datetime, timezone

    items: list[str] = []
    for path in sorted(briefs_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        date = path.stem
        cards = data.get("cards", [])
        if not cards:
            continue
        desc = "；".join(c.get("title", "") for c in cards[:6])
        try:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            pub = format_datetime(dt)
        except ValueError:
            pub = ""
        items.append(FEED_ITEM.format(
            title=f"{title} · {date}",
            url=f"{base}/{date}.html",
            guid=f"{base}/{date}.html",
            pub=pub,
            desc=desc,
        ))

    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n<channel>\n'
        f"<title>{title}</title>\n"
        f"<link>{base}/</link>\n"
        "<description>每天从 50 多个信息源自动抓取、筛选、成卡的 AI 科技早报。</description>\n"
        "<language>zh-cn</language>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )
    (directory / "feed.xml").write_text(feed, encoding="utf-8")
    logger.info("RSS 已生成：%s", directory / "feed.xml")

def render_archive(cfg: dict, directory: Path) -> None:
    briefs_dir = directory.parent / "data" / "briefs"
    items: list[dict] = []
    if briefs_dir.exists():
        for path in sorted(briefs_dir.glob("*.json"), reverse=True):
            date = path.stem
            count = 0
            try:
                count = len(json.loads(path.read_text(encoding="utf-8")).get("cards", []))
            except Exception:  # noqa: BLE001
                pass
            items.append({"date": date, "file": f"{date}.html", "count": count})

    html = TEMPLATE.render(
        page_title="往期早报",
        meta_desc="每日 AI 科技早报的往期列表。",
        is_archive=True,
        archive=items,
        heading="往期早报",
        date_str="",
        generated_at="",
        cards=[],
        degraded=False,
        degraded_reason="",
        source_note="",
    )
    (directory / "archive.html").write_text(html, encoding="utf-8")
