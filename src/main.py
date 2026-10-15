"""每日早报主流程。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import compose
import dedupe
import fetch
import notify
import pick as select_mod
from common import ROOT, data_dir, load_config, load_env, now_local, setup_logging
from deploy import deploy
from render import render_brief

logger = logging.getLogger("brief")


def warn_proxy(cfg: dict, log) -> None:
    """开工前提醒一句：配置里的代理端口连不上，国外源会全挂。（2026-10-15 加）"""
    import socket

    proxy = ((cfg.get("network") or {}).get("proxy") or "").strip()
    if not proxy:
        return
    host, _, port = proxy.replace("http://", "").replace("https://", "").partition(":")
    if not port:
        return
    try:
        with socket.create_connection((host, int(port)), timeout=2):
            pass
    except OSError as exc:
        log.warning("代理 %s 连不上（%s）——国外源会全挂，先确认 Clash 是否在运行", proxy, exc)


def alert_unless_silent(args, text: str) -> None:
    """失败告警；dry-run 与 --no-notify 时不发。"""
    if getattr(args, "dry_run", False) or getattr(args, "no_notify", False):
        logger.warning("（已跳过失败告警推送：dry-run 或 --no-notify）")
        return
    notify.send_alert(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成每日 AI 科技早报")
    parser.add_argument("--dry-run", action="store_true", help="只在本地生成网页，不部署不推送")
    parser.add_argument("--force", action="store_true", help="忽略当天已生成的判断")
    parser.add_argument("--limit", type=int, default=0, help="限制卡片条数（调试用）")
    parser.add_argument("--no-deploy", action="store_true", help="不部署")
    parser.add_argument("--no-notify", action="store_true", help="不推送")
    parser.add_argument("--only-sources", default="", help="只用名字匹配这些关键词的源（逗号分隔，调试用）")
    return parser.parse_args()


def state_path() -> Path:
    return data_dir() / "state.json"


def read_state() -> dict:
    path = state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def write_state(data: dict) -> None:
    state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)

    if args.limit:
        cfg["brief"]["card_count"] = args.limit
        cfg["brief"]["card_count_min"] = min(int(cfg["brief"].get("card_count_min", 5)), args.limit)

    now = now_local(cfg)
    date_str = now.strftime("%Y-%m-%d")
    generated_at = now.strftime("%H:%M")

    state = read_state()
    if state.get("last_date") == date_str and not args.force:
        log.info("今天（%s）已经生成过早报，跳过。需要重跑请加 --force。", date_str)
        return 0

    if args.only_sources:
        keywords = [part.strip() for part in args.only_sources.split(",") if part.strip()]
        cfg["sources"] = [
            source for source in cfg["sources"]
            if any(keyword.lower() in source["name"].lower() for keyword in keywords)
        ]
        log.info("调试模式：只使用 %d 个源", len(cfg["sources"]))

    log.info("=== 开始生成 %s 的早报 ===", date_str)
    warn_proxy(cfg, log)

    entries, stats = fetch.fetch_all(cfg, log)
    total_sources = len(cfg["sources"])
    ok_sources = sum(1 for item in stats if item["count"])
    if not entries:
        log.error("所有源都抓不到内容，放弃本次生成。")
        alert_unless_silent(args, f"【早报失败】{date_str} 所有源都抓不到内容，本次没有生成。"
                                  "常见原因：代理/Clash 没起来，或整机断网。")
        return 1

    entries = fetch.filter_recent(cfg, entries, log)
    clusters = dedupe.cluster(entries)

    picked = select_mod.select(cfg, clusters, log)
    if not picked:
        log.error("选材为空，放弃本次生成。")
        alert_unless_silent(args, f"【早报失败】{date_str} 抓到内容但选材为空，本次没有生成。")
        return 1

    cards = compose.compose_all(cfg, picked, log)
    if not cards:
        log.error("成卡失败，放弃本次生成。")
        return 1

    cards = drop_duplicate_cards(cards, log)
    cards = select_mod.review_duplicates(cfg, cards, log)
    cards = cards[: int(cfg["brief"].get("card_count", 7))]

    min_count = int(cfg["brief"].get("card_count_min", 5))
    reasons: list[str] = []
    if len(cards) < min_count:
        reasons.append(f"本次只有 {len(cards)} 条")
    if total_sources and ok_sources / total_sources < 0.6:
        reasons.append(f"源可用率偏低（{ok_sources}/{total_sources}）")
    degraded = bool(reasons)
    degraded_reason = "；".join(reasons)

    render_brief(cfg, cards, date_str, generated_at, stats, degraded, degraded_reason)

    brief_path = data_dir() / "briefs" / f"{date_str}.json"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(
        json.dumps(
            {
                "date": date_str,
                "generated_at": generated_at,
                "cards": cards,
                "sources": stats,
                "degraded": degraded,
                "degraded_reason": degraded_reason,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    url = cfg["site"].get("base_url", "").strip()
    if not args.dry_run and not args.no_deploy and cfg["deploy"].get("enabled", True):
        deployed = deploy(cfg)
        if deployed:
            url = deployed
            cfg["site"]["base_url"] = deployed
            try:
                from common import set_base_url

                set_base_url(deployed)
            except Exception as exc:  # noqa: BLE001
                log.warning("写入 base_url 失败：%s", exc)

    if not args.dry_run and not args.no_notify and cfg["notify"].get("dingtalk", True):
        note = f"降级版本：{degraded_reason}" if degraded else ""
        notify.send(cfg, date_str, cards, url, note)

    write_state(
        {
            "last_date": date_str,
            "last_url": url,
            "last_card_count": len(cards),
            "last_degraded": degraded,
        }
    )
    log.info("=== 完成：%d 条卡片，降级=%s ===", len(cards), degraded)
    return 0


def drop_duplicate_cards(cards: list[dict], log: logging.Logger) -> list[dict]:
    """模型偶尔会把同一件事写成两张卡，这里按标题相似度再兜一层。"""
    kept: list[dict] = []
    for card in cards:
        duplicate_of = None
        for existing in kept:
            if dedupe.similar(card["title"], existing["title"]):
                duplicate_of = existing
                break
        if duplicate_of is None:
            kept.append(card)
            continue
        log.info(
            "卡片去重：%s（与「%s」重复，按重要性保留）",
            card["title"],
            duplicate_of["title"],
        )
        if card.get("importance", 3) > duplicate_of.get("importance", 3):
            kept[kept.index(duplicate_of)] = card
    return kept


if __name__ == "__main__":
    sys.exit(main())
