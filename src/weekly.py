"""一周汇总：读最近七天的早报存档，产出周报底稿、两份口播稿和配音。

与日报的关系：日报负责"今天发生了什么"，这里负责"这一周发生了什么"。
数据全部来自 data/briefs/*.json，不重新抓取。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import dedupe
import notify
import tts
from common import ROOT, data_dir, load_text, now_local
from model import ModelError, chat_json
from render_weekly import render_weekly

logger = logging.getLogger("brief")

DEFAULT_VERSIONS = {
    "douyin": {
        "seconds": 60, "max_items": 3, "word_budget": 300,
        "voice": "zh-CN-YunjianNeural", "rate": "+15%", "gap": 0.15,
    },
    "bili": {
        "seconds": 180, "max_items": 9, "word_budget": 900,
        "voice": "zh-CN-YunjianNeural", "rate": "+12%", "gap": 0.4,
    },
}


def weekly_dir() -> Path:
    path = data_dir() / "weekly"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_state() -> dict:
    path = weekly_dir() / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def write_state(data: dict) -> None:
    (weekly_dir() / "state.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def last_full_week(today: date) -> tuple[date, date]:
    """最近一个完整的自然周（周一到周日）。

    周一跑时 end = 昨天（周日）；周二到周日跑时回到更早的那个周日。
    """
    offset = (today.weekday() + 1) % 7 or 7
    end = today - timedelta(days=offset)
    return end - timedelta(days=6), end


def load_cards(start: date, end: date) -> list[dict]:
    """读区间内的所有卡片，顺手排掉可信度为「低」的。"""
    briefs = data_dir() / "briefs"
    cards: list[dict] = []
    for path in sorted(briefs.glob("*.json")):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if not (start <= day <= end):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for card in data.get("cards", []):
            if card.get("confidence") == "低":
                continue
            cards.append({**card, "date": path.stem})
    return cards


def merge_across_days(cards: list[dict]) -> list[dict]:
    """把同一件事在不同天的报道合并成一条，取最新的说法，并统计独立来源数。"""
    groups: list[dict] = []
    for card in sorted(cards, key=lambda item: item["date"]):
        for group in groups:
            if any(dedupe.similar(card["title"], member["title"]) for member in group["members"]):
                group["members"].append(card)
                break
        else:
            groups.append({"members": [card]})

    items: list[dict] = []
    for group in groups:
        members = sorted(group["members"], key=lambda item: item["date"])
        latest = members[-1]

        sources: list[dict] = []
        seen: set[str] = set()
        for member in members:
            for source in member.get("sources") or []:
                name = source.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    sources.append(source)

        items.append(
            {
                "title": latest["title"],
                "date": members[0]["date"],
                "last_date": latest["date"],
                "days": sorted({member["date"] for member in members}),
                "days_count": len({member["date"] for member in members}),
                "ongoing": len({member["date"] for member in members}) > 1,
                "what": latest.get("what", ""),
                "why": latest.get("why", ""),
                "confidence": latest.get("confidence", "中"),
                "importance": max(int(member.get("importance", 3)) for member in members),
                "source_count": len(sources),
                "sources": sources[:4],
            }
        )

    items.sort(key=lambda item: (-item["source_count"], -item["importance"], item["date"]))
    logger.info("跨天合并：%d 条卡片 → %d 件事", len(cards), len(items))
    return items


def build_digest_input(items: list[dict], limit: int) -> str:
    lines: list[str] = []
    for index, item in enumerate(items[:limit], start=1):
        names = "、".join(source.get("name", "") for source in item["sources"])
        link = item["sources"][0].get("url", "") if item["sources"] else ""
        lines.append(f"[{index}] {item['title']}")
        lines.append(
            f"    首次出现：{item['date']}　最后跟进：{item['last_date']}"
            f"　一周内跟进：{item.get('days_count', 1)} 天"
        )
        lines.append(f"    独立来源数：{item['source_count']}（{names}）")
        lines.append(f"    可信度：{item['confidence']}　影响力：{item['importance']}")
        lines.append(f"    发生了什么：{item['what']}")
        lines.append(f"    为什么重要：{item['why']}")
        lines.append(f"    链接：{link}")
        lines.append("")
    return "\n".join(lines)


def generate_digest(cfg: dict, items: list[dict], log) -> dict:
    limit = int(cfg["weekly"].get("max_items_to_model", 30))
    messages = [
        {"role": "system", "content": load_text("prompts/weekly_digest.md")},
        {"role": "user", "content": build_digest_input(items, limit)},
    ]
    data = chat_json(cfg, messages, model=cfg["model"].get("compose_model"), max_tokens=8192)
    data = trim_digest(data, int(cfg["weekly"].get("digest_limit", 12)), log)
    groups = data.get("groups") or []
    total = sum(len(group.get("items") or []) for group in groups)
    log.info("底稿完成：%d 组 / %d 条", len(groups), total)
    return data


def trim_digest(digest: dict, limit: int, log=None) -> dict:
    """模型经常超量，这里按"每组保底一条、其余轮流分配"硬截一道。"""
    groups = []
    for group in digest.get("groups") or []:
        item = dict(group)
        item["items"] = list(group.get("items") or [])
        groups.append(item)

    total = sum(len(group["items"]) for group in groups)
    if total <= limit or not groups:
        return digest

    kept: list[list[dict]] = [[group["items"][0]] if group["items"] else [] for group in groups]
    used = sum(len(items) for items in kept)
    cursor = 1
    while used < limit:
        progressed = False
        for index, group in enumerate(groups):
            if used >= limit:
                break
            if cursor < len(group["items"]):
                kept[index].append(group["items"][cursor])
                used += 1
                progressed = True
        if not progressed:
            break
        cursor += 1

    if log:
        log.info("底稿超量：%d 条裁到 %d 条", total, used)
    out = dict(digest)
    out["groups"] = [{**group, "items": kept[index]} for index, group in enumerate(groups)]
    out["groups"] = [group for group in out["groups"] if group["items"]]
    return out


def script_chars(script: dict) -> int:
    return sum(len(segment.get("text", "")) for segment in script.get("segments") or [])


def shorten(text: str, limit: int) -> str:
    """按句读截断，尽量不截在半句上，更不许截在数字中间。"""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # 切点落在 ASCII 字母数字（数字、单位、英文词）中间时往前退，否则 272k 会被截成 2
    while cut and cut[-1].isascii() and (cut[-1].isalnum() or cut[-1] in ".%+-"):
        cut = cut[:-1]
    for mark in ("。", "；", "，"):
        position = cut.rfind(mark)
        if position > limit * 0.6:
            return cut[: position + 1]
    return cut + "…"


def script_digest_view(digest: dict, max_items: int) -> dict:
    """给口播稿的素材：只留要讲的那几条，而且只给要点。

    素材太密的话，模型会照着底稿的长度写，压不下来——口播稿要的是要点，不是全文。
    """
    flat: list[tuple[str, dict]] = []
    for group in digest.get("groups") or []:
        for item in group.get("items") or []:
            flat.append((group.get("name", ""), item))

    return {
        "headline": digest.get("headline", ""),
        "items": [
            {
                "theme": name,
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "point": shorten(item.get("what", ""), 70),
                "why": shorten(item.get("why", ""), 45),
                "source_count": item.get("source_count", 1),
            }
            for name, item in flat[:max_items]
        ],
    }


def build_segment_plan(version: str, max_items: int, budget: int) -> str:
    """把段数和每段字数算好直接告诉模型——让它自己做除法它做不好。"""
    opening = 30 if version == "douyin" else 50
    closing = 45 if version == "douyin" else 60
    body_total = max(budget - opening - closing, max_items * 20)
    per_body = body_total // max(max_items, 1)
    return (
        f"段落计划（照这个写，不要自己改）：\n"
        f"- 共 {max_items + 2} 段。\n"
        f"- 第 1 段开场，约 {opening} 字。\n"
        f"- 第 2 到第 {max_items + 1} 段是正文，每段约 {per_body} 字，一段只讲一件事，一共讲 {max_items} 条。\n"
        f"- 最后 1 段结尾，约 {closing} 字。\n"
        f"- 全文总字数必须落在 {int(budget * 0.9)} 到 {int(budget * 1.1)} 字之间。\n"
    )


def generate_script(
    cfg: dict, digest: dict, version: str, log, previous: dict | None = None, feedback: str = ""
) -> dict:
    params = cfg["weekly"]["versions"][version]
    max_items = int(params["max_items"])
    budget = int(params["word_budget"])
    view = script_digest_view(digest, max_items)
    base_user = (
        f"VERSION={version}\n"
        f"TARGET_SECONDS={params['seconds']}\n"
        f"MAX_ITEMS={max_items}\n"
        f"WORD_BUDGET={budget}\n\n"
        f"{build_segment_plan(version, max_items, budget)}\n"
        f"本周要点（只有这几条，不要提材料外的内容）：\n"
        f"{json.dumps(view, ensure_ascii=False, indent=2)}"
    )
    messages = [
        {"role": "system", "content": load_text("prompts/weekly_script.md")},
        {"role": "user", "content": base_user},
    ]
    if feedback:
        content = feedback
        if previous:
            content = (
                "上一版口播稿（JSON）：\n"
                + json.dumps({"segments": previous.get("segments") or []}, ensure_ascii=False, indent=2)
                + "\n\n"
                + feedback
                + "\n在这一版的基础上改，不要另起一版。"
            )
        messages.append({"role": "user", "content": content})

    script = chat_json(cfg, messages, model=cfg["model"].get("compose_model"), max_tokens=4096)
    segments = script.get("segments") or []
    for index, segment in enumerate(segments, start=1):
        segment.setdefault("key", f"s{index}")
    script["segments"] = segments
    log.info(
        "%s 口播稿：%d 段 / %d 字",
        version,
        len(segments),
        script_chars(script),
    )
    return script


def build_length_note(
    script_actual: int, budget: int, timeline_total: float, target: float, too_short: bool
) -> str:
    prefix = f"上面这版口播稿实际 {script_actual} 字，预算是 {budget} 字，配音实测 {timeline_total:.1f} 秒，目标是 {target:.0f} 秒。"
    if too_short:
        return (
            prefix
            + f"太短了。请保持同样的条目，重新输出一版 JSON：每条多说一句，补上具体数字、"
            f"具体动作或一句为什么重要，把总字数提到 {budget} 字左右。不要靠加形容词凑字数。"
        )
    return (
        prefix
        + f"太长了。请精简后重新输出一版 JSON：删掉次要条目和修饰性的句子，保留事实和数字，"
        f"总字数压到 {budget} 字以内。"
    )


def run(cfg: dict, args, log) -> bool:
    """跑一次周报。返回是否真的产出了东西。"""
    weekly_cfg = cfg.get("weekly") or {}

    # 云端（GitHub Actions）不做周报：配音要 ffprobe、产物要落到本地素材目录，
    # 在云端跑还要多花一次模型钱。想在云端跑就把 weekly.run_in_cloud 改成 true。
    if os.environ.get("GITHUB_ACTIONS") == "true" and not weekly_cfg.get("run_in_cloud", False):
        log.info("跑在 GitHub Actions 上，周报跳过（周报统一在本地做）")
        return False

    today = now_local(cfg).date()

    # 登录后的自动检查每天都跑，但只在周一到周三动手，避免周中冒出一份过期的周报
    forced = bool(getattr(args, "force", False) or getattr(args, "weekly", False))
    if not forced and today.weekday() not in (0, 1, 2):
        log.info("今天不是周一到周三，不自动补周报（要强制跑加 --force）")
        return False

    if getattr(args, "week_end", ""):
        end = date.fromisoformat(args.week_end)
        start = end - timedelta(days=6)
    else:
        start, end = last_full_week(today)

    state = read_state()
    if state.get("last_week_end") == end.isoformat() and not getattr(args, "force", False):
        log.info("周报 %s ~ %s 已经生成过，跳过", start, end)
        return False

    log.info("=== 生成周报：%s ~ %s ===", start, end)
    cards = load_cards(start, end)
    if not cards:
        log.warning("这段时间没有存档，跳过周报")
        return False

    items = merge_across_days(cards)
    digest = generate_digest(cfg, items, log)
    if not (digest.get("groups") or []):
        log.error("底稿为空，放弃本次周报")
        return False

    out_dir = weekly_dir() / end.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "digest.json").write_text(
        json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    degraded_reasons: list[str] = []
    if digest.get("skipped_note"):
        degraded_reasons.append(str(digest["skipped_note"]))

    page = render_weekly(cfg, digest, start, end, f"{now_local(cfg):%H:%M}")

    scripts: dict[str, dict] = {}
    timelines: dict[str, dict] = {}
    want_audio = not getattr(args, "no_audio", False)
    ffprobe = tts.ffprobe_path(cfg)
    if want_audio and not Path(ffprobe).exists():
        log.warning("找不到 ffprobe（%s），本次只出文本不配音", ffprobe)
        want_audio = False

    for version in weekly_cfg.get("versions", {}):
        params = cfg["weekly"]["versions"][version]
        try:
            script = generate_script(cfg, digest, version, log)
        except ModelError as exc:
            log.warning("%s 口播稿生成失败：%s", version, exc)
            degraded_reasons.append(f"{version} 口播稿失败")
            continue

        budget = int(params["word_budget"])
        target_seconds = float(params["seconds"])
        # 先把字数压到位再配音，省得反复生成音频
        for attempt in range(2):
            actual = script_chars(script)
            if budget * 0.85 <= actual <= budget * 1.1:
                break
            too_short = actual < budget * 0.85
            log.info(
                "%s 字数 %d 偏离预算 %d，第 %d 次重写（%s）",
                version,
                actual,
                budget,
                attempt + 1,
                "加长" if too_short else "精简",
            )
            try:
                script = generate_script(
                    cfg, digest, version, log,
                    previous=script,
                    feedback=build_length_note(actual, budget, 0.0, target_seconds, too_short),
                )
            except ModelError as exc:
                log.warning("%s 重写失败，沿用上一版：%s", version, exc)
                break

        scripts[version] = script
        (out_dir / f"script-{version}.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not want_audio:
            continue

        assets = out_dir / f"assets-{version}"
        try:
            timeline = tts.write_assets_dir(
                assets, script, params["voice"], params["rate"], float(params["gap"]), ffprobe
            )
        except tts.TTSError as exc:
            log.warning("%s 配音失败（口播稿已经保留）：%s", version, exc)
            degraded_reasons.append(f"{version} 配音失败")
            continue

        too_long = timeline["total"] > target_seconds * 1.2
        too_short = timeline["total"] < target_seconds * 0.7
        if (too_long or too_short) and len(script["segments"]) > 1:
            log.info(
                "%s 配音 %.1f 秒偏离目标 %.0f 秒，%s后重配",
                version,
                timeline["total"],
                target_seconds,
                "精简" if too_long else "加长",
            )
            new_budget = int(budget * 0.85) if too_long else int(budget * 1.05)
            try:
                revised = generate_script(
                    cfg, digest, version, log,
                    previous=script,
                    feedback=build_length_note(
                        script_chars(script), new_budget,
                        timeline["total"], target_seconds, too_short,
                    ),
                )
                timeline = tts.write_assets_dir(
                    assets, revised, params["voice"], params["rate"], float(params["gap"]), ffprobe
                )
                scripts[version] = revised
                (out_dir / f"script-{version}.json").write_text(
                    json.dumps(revised, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except (ModelError, tts.TTSError) as exc:
                log.warning("%s 重配失败，保留原版：%s", version, exc)

        try:
            tts.build_full_tracks(
                assets,
                timeline,
                ffmpeg=tts.ffmpeg_path(cfg),
                bgm=tts.bgm_path(cfg),
                bgm_volume=float(weekly_cfg.get("bgm_volume", 0.12)),
                log=log,
            )
        except tts.TTSError as exc:
            log.warning("%s 整轨合成失败（分段音频仍在）：%s", version, exc)
            degraded_reasons.append(f"{version} 整轨合成失败")

        timelines[version] = timeline

    base_url = (cfg["site"].get("base_url") or "").rstrip("/")
    if (
        not getattr(args, "dry_run", False)
        and not getattr(args, "no_deploy", False)
        and cfg.get("deploy", {}).get("enabled", True)
    ):
        try:
            from deploy import deploy

            deployed = deploy(cfg)
            if deployed:
                cfg["site"]["base_url"] = deployed
                base_url = deployed.rstrip("/")
        except Exception as exc:  # noqa: BLE001
            log.warning("周报部署失败：%s", exc)

    page_url = f"{base_url}/{page.name}" if base_url else ""

    summary = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "cards": len(cards),
        "items": len(items),
        "groups": len(digest.get("groups") or []),
        "digest_items": sum(len(group.get("items") or []) for group in digest.get("groups") or []),
        "page": page.name,
        "page_url": page_url,
        "scripts": {k: script_chars(v) for k, v in scripts.items()},
        "durations": {k: v["total"] for k, v in timelines.items()},
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not getattr(args, "dry_run", False) and not getattr(args, "no_notify", False):
        notify.send_weekly(digest, start, end, page_url, scripts, timelines)

    write_state(
        {
            "last_week_end": end.isoformat(),
            "last_run": f"{now_local(cfg):%Y-%m-%d %H:%M}",
            "last_page": page.name,
        }
    )
    log.info(
        "=== 周报完成：%d 组 / %d 条，配音 %s ===",
        summary["groups"],
        summary["digest_items"],
        summary["durations"],
    )
    return True
