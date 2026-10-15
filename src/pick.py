"""让模型从候选条目里挑出当天的早报内容（模块名避开标准库 select）。"""

from __future__ import annotations

import logging

from common import load_text
from model import ModelError, chat_json

logger = logging.getLogger("brief")

REVIEW_PROMPT = """下面是一份早报的卡片标题。请判断哪些标题讲的是同一件事。

规则：
- 只有确实是同一事件、同一产品或同一场发布的不同报道才算重复，不确定就不要判为重复。
- 同一件事的不同侧面（例如「发布」和「开放权重时间表」）算重复。
- 每组重复只保留信息最完整的一条。

输出严格 JSON：{"drop": [要删掉的编号], "reason": "一句话说明"}。没有重复就返回 {"drop": []}。
只输出 JSON。"""


def review_duplicates(cfg: dict, cards: list[dict], logger_) -> list[dict]:
    """让模型复核卡片之间是否还有重复（字面比对抓不住换词改写的情况）。"""
    if len(cards) < 2:
        return cards

    listing = "\n".join(f"{index}. {card['title']}" for index, card in enumerate(cards, start=1))
    try:
        data = chat_json(
            cfg,
            [
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": listing},
            ],
            model=cfg["model"].get("select_model"),
            max_tokens=512,
        )
    except ModelError as exc:
        logger_.warning("去重复核跳过：%s", exc)
        return cards

    raw_drop = data.get("drop", []) if isinstance(data, dict) else []
    drop: set[int] = set()
    for value in raw_drop:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= index <= len(cards):
            drop.add(index)
    if len(drop) > 3:  # 防呆：一次删太多说明判错了
        logger_.warning("去重复核要求删除 %d 条，数量异常，忽略", len(drop))
        return cards

    if drop:
        logger_.info(
            "去重复核删掉 %d 条：%s",
            len(drop),
            "、".join(cards[index - 1]["title"] for index in sorted(drop)),
        )
    return [card for index, card in enumerate(cards, start=1) if index not in drop]


def build_candidates(cfg: dict, clusters: list[dict]) -> list[dict]:
    limit = int(cfg["model"].get("max_candidates", 120))
    summary_chars = int(cfg["model"].get("summary_chars", 500))

    chosen = clusters[:limit]
    return [
        {
            "id": group["id"],
            "title": group["lead"]["title"],
            "source": group["lead"]["source"],
            "published": group["lead"].get("published", ""),
            "summary": (group["lead"].get("summary") or "")[:summary_chars],
            "url": group["lead"]["link"],
            "other_sources": [m["source"] for m in group["members"][1:4]],
        }
        for group in chosen
    ]


def build_user_message(cfg: dict, candidates: list[dict]) -> str:
    min_count = int(cfg["brief"].get("card_count_min", 5))
    # 多要几条：来源上限和卡片去重都会消耗候选，留出余量才能凑够目标条数
    max_count = int(cfg["brief"].get("card_count", 7)) + 4

    lines = [
        f"MIN_COUNT={min_count}",
        f"MAX_COUNT={max_count}",
        f"MAX_PER_SOURCE={int(cfg['brief'].get('max_per_source', 2))}",
        "",
        "候选项：",
        "",
    ]
    for item in candidates:
        others = f"（另有来源：{'、'.join(item['other_sources'])}）" if item["other_sources"] else ""
        lines.append(f"[{item['id']}] {item['title']}")
        lines.append(f"    来源：{item['source']}{others}  时间：{item['published']}")
        if item["summary"]:
            lines.append(f"    摘要：{item['summary']}")
        lines.append(f"    链接：{item['url']}")
        lines.append("")
    return "\n".join(lines)


def select(cfg: dict, clusters: list[dict], logger_: logging.Logger) -> list[dict]:
    candidates = build_candidates(cfg, clusters)
    if not candidates:
        return []

    system_prompt = load_text("prompts/select.md")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_message(cfg, candidates)},
    ]

    data = chat_json(cfg, messages, model=cfg["model"].get("select_model"), max_tokens=4096)
    items = data.get("items", []) if isinstance(data, dict) else []
    if not items:
        logger_.warning("选材返回为空")
        return []

    by_id = {group["id"]: group for group in clusters}
    picked: list[dict] = []
    overflow: list[dict] = []
    per_source: dict[str, int] = {}
    seen: set[str] = set()
    cap = int(cfg["brief"].get("max_per_source", 2))

    for item in items:
        candidate_id = str(item.get("id", "")).strip().strip("[]")
        if candidate_id in seen or candidate_id not in by_id:
            continue
        seen.add(candidate_id)
        entry = {
            "cluster": by_id[candidate_id],
            "importance": item.get("importance", 3),
            "reason": item.get("reason", ""),
        }
        source = by_id[candidate_id]["lead"]["source"]
        if per_source.get(source, 0) >= cap:
            overflow.append(entry)
            continue
        per_source[source] = per_source.get(source, 0) + 1
        picked.append(entry)

    max_count = int(cfg["brief"].get("card_count", 7)) + 4
    min_count = int(cfg["brief"].get("card_count_min", 5))
    # 只有压到不够下限时才回填，否则宁可条数少一点也要保住来源分散
    for entry in overflow:
        if len(picked) >= min_count:
            break
        picked.append(entry)

    picked = picked[:max_count]
    logger_.info(
        "选材完成，挑中 %d 条（同一来源上限 %d 条）",
        len(picked),
        cap,
    )
    return picked
