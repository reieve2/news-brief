"""按标题相似度把同一件事的不同来源合并成一条。"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger("brief")

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
NORM_RE = re.compile(r"[^\w\u4e00-\u9fff]+")
STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "with", "is", "are",
    "how", "why", "what", "its", "it", "as", "at", "by", "from", "new", "says",
}


def normalize(title: str) -> str:
    return NORM_RE.sub(" ", title.lower()).strip()


def token_set(title: str) -> set[str]:
    text = normalize(title)
    if CJK_RE.search(text):
        compact = text.replace(" ", "")
        grams = {compact[i : i + 2] for i in range(max(len(compact) - 1, 1))}
        return grams | {t for t in text.split() if len(t) > 2}
    return {t for t in text.split() if len(t) > 2 and t not in STOPWORDS}


def similar(a: str, b: str) -> bool:
    ta, tb = token_set(a), token_set(b)
    if ta and tb:
        jaccard = len(ta & tb) / len(ta | tb)
        if jaccard >= 0.55:
            return True
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio() >= 0.78


def cluster(entries: list[dict]) -> list[dict]:
    """返回聚类列表，每个 cluster 含 members，代表条目为 members[0]。"""
    clusters: list[dict] = []
    for entry in entries:
        placed = False
        for group in clusters:
            if any(similar(entry["title"], member["title"]) for member in group["members"]):
                group["members"].append(entry)
                placed = True
                break
        if not placed:
            clusters.append({"members": [entry]})

    for group in clusters:
        # 同一件事优先用原始来源做代表，聚合站排在后面
        group["members"].sort(
            key=lambda m: (m.get("aggregator", False), -m["weight"], -len(m.get("summary", ""))),
        )
        group["lead"] = group["members"][0]
        group["id"] = group["lead"]["id"]

    clusters.sort(
        key=lambda g: (
            g["lead"].get("aggregator", False),
            -g["lead"]["weight"],
            -len(g["lead"].get("summary", "")),
        )
    )
    logger.info("去重后 %d 条（原始 %d 条）", len(clusters), len(entries))
    return clusters
