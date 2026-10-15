"""为每条入选新闻生成深度卡片。"""

from __future__ import annotations

import logging

from common import load_text
from fetch import fetch_article_text, make_session
from model import chat_json

logger = logging.getLogger("brief")

FIELDS = ("title", "what", "background", "why", "next", "confidence")
TERM_LIMIT = 2
TERM_MAX_CHARS = 40


def clean_terms(raw, card: dict) -> list[dict]:
    """校验模型给的术语：必须是卡片正文里真实出现过的词，单卡内去重。"""
    if not isinstance(raw, list):
        return []

    haystack = " ".join(
        (card.get(field) or "") for field in ("title", "what", "background", "why", "next")
    ).lower()

    terms: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        gloss = str(item.get("gloss") or "").strip()
        if not term or not gloss or len(term) > TERM_MAX_CHARS:
            continue
        key = term.lower()
        if key in seen:
            continue
        if key not in haystack:
            logger.debug("术语 %s 没在正文里出现，丢弃", term)
            continue
        seen.add(key)
        terms.append({"term": term, "gloss": gloss})
        if len(terms) >= TERM_LIMIT:
            break
    return terms


def build_material(cfg: dict, session, direct_session, picked: dict) -> str:
    cluster = picked["cluster"]
    lines: list[str] = []
    fetch_fulltext = bool(cfg["brief"].get("fetch_fulltext", True))
    fulltext_used = False

    for index, member in enumerate(cluster["members"][:3], start=1):
        lines.append(f"--- 来源 {index}：{member['source']} ---")
        lines.append(f"标题：{member['title']}")
        lines.append(f"时间：{member.get('published', '')}")
        lines.append(f"链接：{member['link']}")
        if member.get("summary"):
            lines.append(f"摘要：{member['summary'][:800]}")

        if fetch_fulltext and index == 1 and not fulltext_used:
            use_proxy = bool(member.get("needs_proxy", True))
            text = fetch_article_text(
                session if use_proxy else direct_session, cfg, member["link"], use_proxy=use_proxy
            )
            if text:
                fulltext_used = True
                lines.append(f"正文节选：{text}")
        lines.append("")

    return "\n".join(lines)


def compose_card(cfg: dict, session, direct_session, picked: dict) -> dict:
    system_prompt = load_text("prompts/compose.md")
    material = build_material(cfg, session, direct_session, picked)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": material},
    ]
    data = chat_json(cfg, messages, model=cfg["model"].get("compose_model"), max_tokens=2560)

    card = {field: (data.get(field) or "").strip() for field in FIELDS}
    if not card["title"]:
        card["title"] = picked["cluster"]["lead"]["title"][:40]
    if card["confidence"] not in {"高", "中", "低"}:
        card["confidence"] = "中"
    card["importance"] = picked.get("importance", 3)
    card["terms"] = clean_terms(data.get("terms"), card)
    card["sources"] = [
        {"name": member["source"], "url": member["link"]}
        for member in picked["cluster"]["members"][:3]
    ]
    return card


def compose_all(cfg: dict, picked_list: list[dict], logger_: logging.Logger) -> list[dict]:
    # 两个 session：走代理的与真直连的；正文按每个成员的 needs_proxy 各取所需
    session = make_session(cfg)
    direct_session = make_session(cfg, direct=True)
    cards: list[dict] = []
    for index, picked in enumerate(picked_list, start=1):
        try:
            card = compose_card(cfg, session, direct_session, picked)
            cards.append(card)
            logger_.info("成卡 %d/%d：%s", index, len(picked_list), card["title"])
        except Exception as exc:  # noqa: BLE001
            logger_.warning("成卡失败（%s）：%s", picked["cluster"]["lead"]["title"][:40], exc)
    return cards
