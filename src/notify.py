"""推送钉钉。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
import urllib.request

logger = logging.getLogger("brief")


def signed_url(webhook: str, secret: str) -> str:
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    payload = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    signature = urllib.parse.quote_plus(base64.b64encode(digest))
    joiner = "&" if "?" in webhook else "?"
    return f"{webhook}{joiner}timestamp={timestamp}&sign={signature}"


def build_markdown(date_str: str, cards: list[dict], url: str, degraded_note: str) -> str:
    lines = [f"### 早报 · {date_str}", f"> {len(cards)} 条"]
    if degraded_note:
        lines.append(f"> {degraded_note}")
    lines.append("")
    for index, card in enumerate(cards, start=1):
        lead = (card.get("what") or "").strip()
        lead = lead.split("。")[0]
        if len(lead) > 46:
            lead = lead[:46] + "…"
        lines.append(f"**{index}. {card['title']}**")
        lines.append(f"{lead}。")
        lines.append("")
    if url:
        lines.append(f"[查看完整早报]({url})")
    return "\n".join(lines)


def send(cfg: dict, date_str: str, cards: list[dict], url: str, degraded_note: str = "") -> bool:
    webhook = (os.environ.get("DINGTALK_WEBHOOK") or "").strip()
    secret = (os.environ.get("DINGTALK_SECRET") or "").strip()
    if not webhook:
        logger.warning("缺少 DINGTALK_WEBHOOK，跳过推送")
        return False

    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"早报 · {date_str}",
            "text": build_markdown(date_str, cards, url, degraded_note),
        },
    }
    request = urllib.request.Request(
        signed_url(webhook, secret),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("errcode") == 0:
            logger.info("钉钉推送成功")
            return True
        logger.warning("钉钉返回错误：%s", data)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("钉钉推送异常：%s", exc)
        return False


def send_alert(text: str) -> bool:
    """发一条纯文本告警。

    失败时用它，让"今天没生成"这件事不会静默。
    （2026-10-15 加：10-12 与 10-13 两次"所有源都抓不到"只写了日志，没人知道。）
    """
    webhook = (os.environ.get("DINGTALK_WEBHOOK") or "").strip()
    secret = (os.environ.get("DINGTALK_SECRET") or "").strip()
    if not webhook:
        logger.warning("缺少 DINGTALK_WEBHOOK，告警也发不出去")
        return False

    body = {"msgtype": "text", "text": {"content": text}}
    request = urllib.request.Request(
        signed_url(webhook, secret),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("errcode") == 0:
            logger.info("失败告警已推送")
            return True
        logger.warning("告警推送返回错误：%s", data)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("告警推送异常：%s", exc)
        return False


def build_weekly_markdown(
    digest: dict, start, end, url: str, scripts: dict, timelines: dict
) -> str:
    groups = digest.get("groups") or []
    total = sum(len(group.get("items") or []) for group in groups)
    lines = [f"### 周报 · {start} ~ {end}"]
    if digest.get("headline"):
        lines.append(f"> {digest['headline']}")
    lines.append(f"> {len(groups)} 组 / {total} 条")
    lines.append("")
    for group in groups:
        lines.append(f"**{group.get('name', '')}**")
        if group.get("summary"):
            lines.append(group["summary"])
        for item in group.get("items") or []:
            lines.append(f"- {item.get('title', '')}")
        lines.append("")
    if timelines:
        parts = " · ".join(f"{name} {value['total']:.0f} 秒" for name, value in timelines.items())
        lines.append(f"配音：{parts}")
    if scripts:
        words = " · ".join(f"{name} {chars} 字" for name, chars in scripts.items())
        lines.append(f"口播稿：{words}")
    if url:
        lines.append("")
        lines.append(f"[查看完整周报]({url})")
    return "\n".join(lines)


def send_weekly(
    digest: dict, start, end, url: str, scripts: dict, timelines: dict
) -> bool:
    """推送周报。格式和日报那条保持一致，只是内容换成一周的汇总。"""
    webhook = (os.environ.get("DINGTALK_WEBHOOK") or "").strip()
    secret = (os.environ.get("DINGTALK_SECRET") or "").strip()
    if not webhook:
        logger.warning("缺少 DINGTALK_WEBHOOK，跳过周报推送")
        return False

    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"周报 · {start} ~ {end}",
            "text": build_weekly_markdown(digest, start, end, url, scripts, timelines),
        },
    }
    request = urllib.request.Request(
        signed_url(webhook, secret),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("errcode") == 0:
            logger.info("周报钉钉推送成功")
            return True
        logger.warning("周报推送返回错误：%s", data)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("周报推送异常：%s", exc)
        return False
