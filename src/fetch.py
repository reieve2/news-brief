"""抓取 RSS 源，必要时抓取正文。"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone

import feedparser
import requests

logger = logging.getLogger("brief")

_thread_local = threading.local()

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
BLOCK_RE = re.compile(r"</(p|div|li|h[1-6]|br|section|article)>", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def clean_text(raw: str, limit: int = 800) -> str:
    if not raw:
        return ""
    text = TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text).strip()
    return text[:limit]


def entry_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8", "ignore")).hexdigest()[:12]


def make_session(cfg: dict, direct: bool = False) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": cfg.get("network", {}).get("user_agent", "Mozilla/5.0")}
    )
    if direct:
        # 访问国内接口时不跟随系统代理
        session.trust_env = False
    return session


def proxies_for(cfg: dict, use_proxy: bool):
    if not use_proxy:
        return None
    network = cfg.get("network", {})
    proxy = (network.get("proxy") or "").strip()
    if not proxy:
        proxy = (os_environ_proxy() or "").strip()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def os_environ_proxy() -> str:
    import os

    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(key)
        if value:
            return value
    return ""


def get(session: requests.Session, cfg: dict, url: str, use_proxy: bool = True, timeout: int | None = None):
    """带重试的 GET，返回 Response 或 None。"""
    network = cfg.get("network", {})
    timeout = timeout or int(network.get("timeout", 15))
    retries = int(network.get("retries", 2))
    proxies = proxies_for(cfg, use_proxy)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, proxies=proxies, timeout=timeout)
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code}")
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    logger.debug("请求失败 %s: %s", url, last_error)
    return None


def fetch_source(session: requests.Session, cfg: dict, source: dict) -> tuple[list[dict], str]:
    """抓单个源，返回 (条目列表, 错误信息)。"""
    response = get(session, cfg, source["url"], use_proxy=bool(source.get("proxy", True)))
    if response is None:
        return [], "请求失败"

    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", 0) and not feed.entries:
        return [], f"解析失败: {getattr(feed, 'bozo_exception', 'unknown')}"

    entries: list[dict] = []
    for raw in feed.entries[:60]:
        link = (raw.get("link") or "").strip()
        title = clean_text(raw.get("title", ""), 200)
        if not link or not title:
            continue

        published = None
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            parsed = raw.get(key)
            if parsed:
                published = datetime(*parsed[:6], tzinfo=timezone.utc)
                break

        summary = clean_text(
            raw.get("summary") or raw.get("description") or raw.get("content", [{}])[0].get("value", ""),
            1500,
        )
        entries.append(
            {
                "id": entry_id(link),
                "source": source["name"],
                "group": source.get("group", ""),
                "weight": int(source.get("weight", 1)),
                "aggregator": bool(source.get("aggregator", False)),
                "needs_proxy": bool(source.get("proxy", True)),
                "title": title,
                "link": link,
                "published": published.isoformat() if published else "",
                "published_dt": published,
                "summary": summary,
            }
        )
    return entries, ""


def fetch_all(cfg: dict, logger_: logging.Logger) -> tuple[list[dict], list[dict]]:
    """并发抓取所有源。

    串行抓 56 个源，平时一分半；但代理一不稳，每个失败的源都要重试三次，
    整轮会拖到十几分钟。并发之后正常情况二三十秒，代理坏掉时也有时间预算兜底。
    """
    sources = cfg.get("sources", [])
    network = cfg.get("network", {})
    workers = max(1, int(network.get("workers", 8)))
    budget = float(network.get("fetch_budget_seconds", 360))

    results: dict[str, tuple[list[dict], str]] = {}
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {pool.submit(_fetch_one, cfg, source): source for source in sources}
        try:
            for future in as_completed(futures, timeout=budget):
                source = futures[future]
                try:
                    results[source["name"]] = future.result()
                except Exception as exc:  # noqa: BLE001
                    results[source["name"]] = ([], f"异常: {exc}")
        except FuturesTimeout:
            logger_.warning("抓取超过 %.0f 秒预算，剩下的源本轮跳过", budget)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    entries: list[dict] = []
    stats: list[dict] = []
    for source in sources:
        items, error = results.get(source["name"], ([], "跳过"))
        stats.append({"name": source["name"], "count": len(items), "error": error})
        entries.extend(items)
        status = "ok" if items else f"fail ({error or '空'})"
        logger_.info("抓取 %-24s %s", source["name"], status)

    return entries, stats


def _fetch_one(cfg: dict, source: dict) -> tuple[list[dict], str]:
    """每个线程、每种模式各一个 session——requests.Session 不是线程安全的。

    2026-10-15 修：以前无论源标不标 proxy，都复用 make_session(cfg)（跟随系统代理），
    于是"直连"的国内源其实也走代理——Clash 一挂就全灭（10-12 10:24 / 10-13 09:32 两次）。
    现在按源自己的标记选 session：proxy=false 的用 trust_env=False，真正直连，
    不受系统代理 / 环境变量影响。
    """
    direct = not bool(source.get("proxy", True))
    sessions = getattr(_thread_local, "sessions", None)
    if sessions is None:
        sessions = {}
        _thread_local.sessions = sessions
    session = sessions.get(direct)
    if session is None:
        session = make_session(cfg, direct=direct)
        sessions[direct] = session
    return fetch_source(session, cfg, source)


def filter_recent(cfg: dict, entries: list[dict], logger_: logging.Logger) -> list[dict]:
    hours = int(cfg["brief"].get("lookback_hours", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    fresh: list[dict] = []
    unknown = 0
    for entry in entries:
        published = entry.get("published_dt")
        if published is None:
            unknown += 1
            fresh.append(entry)
        elif published >= cutoff:
            fresh.append(entry)

    logger_.info("时间窗内 %d 条（其中 %d 条无发布时间），共抓到 %d 条", len(fresh), unknown, len(entries))
    return fresh


def fetch_article_text(session: requests.Session, cfg: dict, url: str, use_proxy: bool) -> str:
    """抓单篇正文，只保留文字。失败返回空串。"""
    limit = int(cfg["brief"].get("fulltext_max_chars", 6000))
    response = get(session, cfg, url, use_proxy=use_proxy, timeout=20)
    if response is None:
        return ""
    if "text/html" not in response.headers.get("Content-Type", ""):
        return ""
    raw = response.text
    raw = SCRIPT_RE.sub(" ", raw)
    body = raw
    match = re.search(r"<article[^>]*>(.*?)</article>", raw, re.I | re.S)
    if match:
        body = match.group(1)
    else:
        match = re.search(r"<main[^>]*>(.*?)</main>", raw, re.I | re.S)
        if match:
            body = match.group(1)
    body = BLOCK_RE.sub("\n", body)
    text = clean_text(body, limit * 2)
    return text[:limit]
