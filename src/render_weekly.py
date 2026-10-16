"""渲染周报网页。风格沿用日报，结构改成按主题分组。"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, select_autoescape

from common import out_dir

logger = logging.getLogger("brief")

env = Environment(autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)

TEMPLATE = env.from_string(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
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
  header { margin-bottom: 20px; }
  h1 { font-size: 21px; line-height: 1.4; margin: 0 0 6px; }
  .sub { color: var(--dim); font-size: 13px; }
  .headline {
    margin: 12px 0 0; padding: 12px 14px; border-left: 3px solid var(--accent);
    background: var(--card); border-radius: 0 10px 10px 0; font-size: 17px; font-weight: 600;
    line-height: 1.6;
  }
  .warn {
    border: 1px solid #f0c36d; background: #fff8e6; color: #7a5b12;
    border-radius: 8px; padding: 10px 12px; font-size: 13px; margin: 14px 0; line-height: 1.6;
  }
  @media (prefers-color-scheme: dark) { .warn { background: #2a2413; color: #e8cf95; border-color: #4a3d1a; } }
  .group { margin-bottom: 26px; }
  .group > h2 {
    font-size: 15px; letter-spacing: .5px; color: var(--accent);
    margin: 0 0 6px; padding-bottom: 6px; border-bottom: 1px solid var(--line);
  }
  .group-summary { margin: 0 0 12px; font-size: 15px; color: var(--ink); opacity: .88; }
  article {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 14px 16px 12px; margin-bottom: 12px;
  }
  h3 { font-size: 17px; line-height: 1.5; margin: 0 0 7px; }
  .meta { color: var(--dim); font-size: 12px; margin: 0 0 9px; }
  .tag {
    display: inline-block; border: 1px solid var(--line); border-radius: 5px;
    padding: 0 5px; margin-left: 4px; font-size: 11px; color: var(--dim);
  }
  .what { margin: 0 0 9px; }
  details { border-top: 1px dashed var(--line); padding-top: 8px; }
  summary { cursor: pointer; color: var(--accent); font-size: 14px; outline: none; }
  details p { margin: 10px 0 0; font-size: 15px; }
  .src { margin: 10px 0 0; font-size: 12px; color: var(--dim); }
  .src a { color: var(--dim); text-decoration: none; border-bottom: 1px solid var(--line); }
  footer { color: var(--dim); font-size: 12px; text-align: center; margin-top: 28px; line-height: 2; }
  footer a { color: var(--dim); }
</style>
</head>
<body>
  <header>
    <h1>本周 AI 科技周报</h1>
    <div class="sub">{{ week_start }} ~ {{ week_end }} · {{ item_count }} 条 · 生成于 {{ generated_at }}</div>
    {% if headline %}<p class="headline">{{ headline }}</p>{% endif %}
  </header>

  {% if skipped_note %}<div class="warn">{{ skipped_note }}</div>{% endif %}

  {% for group in groups %}
  <section class="group">
    <h2>{{ group.name }}</h2>
    <p class="group-summary">{{ group.summary }}</p>
    {% for item in group.get('items') or [] %}
    <article>
      <h3>{{ item.title }}</h3>
      <p class="meta">{{ item.date }} · {{ item.source_count }} 个来源 · 可信度 {{ item.confidence }}{% if item.ongoing %}<span class="tag">本周持续</span>{% endif %}</p>
      <p class="what">{{ item.what }}</p>
      {% if item.why %}
      <details>
        <summary>为什么重要</summary>
        <p>{{ item.why }}</p>
      </details>
      {% endif %}
      {% if item.sources %}
      <p class="src">来源：{% for s in item.sources %}<a href="{{ s.url }}">{{ s.name }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p>
      {% endif %}
    </article>
    {% endfor %}
  </section>
  {% endfor %}

  <footer>
    <a href="archive.html">往期日报</a>
    <br>{{ generated_at }} 生成
  </footer>
</body>
</html>
"""
)


def render_weekly(cfg: dict, digest: dict, start: date, end: date, generated_at: str) -> Path:
    directory = out_dir(cfg)
    groups = digest.get("groups") or []
    item_count = sum(len(group.get("items") or []) for group in groups)

    html = TEMPLATE.render(
        page_title=f"本周 AI 科技周报 · {start} ~ {end}",
        week_start=start.isoformat(),
        week_end=end.isoformat(),
        item_count=item_count,
        generated_at=generated_at,
        headline=digest.get("headline", ""),
        groups=groups,
        skipped_note=digest.get("skipped_note", ""),
    )

    path = directory / f"weekly-{end.isoformat()}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("周报网页已生成：%s", path)
    return path
