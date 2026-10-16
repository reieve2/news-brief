"""把口播稿变成屏幕上的大字和副标题，供视频工程使用。"""

from __future__ import annotations

import json
import logging

from common import load_text
from model import ModelError, chat_json

logger = logging.getLogger("brief")

SCREEN_MAX = 14


def build_storyboard(cfg: dict, script: dict, log) -> dict:
    segments = script.get("segments") or []
    if not segments:
        raise ModelError("口播稿没有分段")

    listing = "\n".join(
        f"[{seg.get('key', index)}] {seg.get('text', '')}"
        for index, seg in enumerate(segments, start=1)
    )
    messages = [
        {"role": "system", "content": load_text("prompts/storyboard.md")},
        {"role": "user", "content": listing},
    ]
    data = chat_json(cfg, messages, model=cfg["model"].get("compose_model"), max_tokens=3072)

    by_key = {}
    for scene in data.get("scenes") or []:
        key = str(scene.get("key", "")).strip().strip("[]")
        if key:
            by_key[key] = scene

    scenes: list[dict] = []
    for index, seg in enumerate(segments, start=1):
        key = str(seg.get("key") or f"s{index}")
        scene = by_key.get(key, {})
        screen = str(scene.get("screen") or "").strip()
        sub = str(scene.get("sub") or "").strip()
        emphasis = str(scene.get("emphasis") or "").strip()

        if not screen:
            screen = (seg.get("text") or "")[:SCREEN_MAX]
        if len(screen) > SCREEN_MAX:
            log.debug("屏幕字过长，截断：%s", screen)
            screen = screen[:SCREEN_MAX]
        if emphasis and emphasis not in screen:
            emphasis = ""

        scenes.append(
            {
                "key": key,
                "text": seg.get("text", ""),
                "screen": screen,
                "sub": sub,
                "emphasis": emphasis,
            }
        )

    log.info("分镜完成：%d 个场景", len(scenes))
    return {"scenes": scenes}


def load_or_build(cfg: dict, script: dict, cache_path, log) -> dict:
    """已经有分镜就直接读，省一次模型调用。"""
    try:
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("scenes"):
                log.info("分镜已有缓存，直接用：%s", cache_path.name)
                return cached
    except Exception:  # noqa: BLE001
        pass

    board = build_storyboard(cfg, script, log)
    cache_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    return board
