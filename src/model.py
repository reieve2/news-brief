"""DeepSeek 接口封装。"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import requests

logger = logging.getLogger("brief")

JSON_RE = re.compile(r"\{.*\}", re.S)


class ModelError(RuntimeError):
    pass


def _api_key() -> str:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise ModelError("缺少 DEEPSEEK_API_KEY，请填进 .env")
    return key


def chat(cfg: dict, messages: list[dict], model: str | None = None, max_tokens: int = 8192) -> str:
    model_cfg = cfg.get("model", {})
    base_url = model_cfg.get("base_url", "https://api.deepseek.com").rstrip("/")
    payload = {
        "model": model or model_cfg.get("select_model", "deepseek-chat"),
        "messages": messages,
        "temperature": float(model_cfg.get("temperature", 0.3)),
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
    }

    session = requests.Session()
    # DeepSeek 国内直连，不走系统代理
    session.trust_env = False

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_api_key()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )
            if response.status_code >= 400:
                raise ModelError(f"HTTP {response.status_code}: {response.text[:300]}")
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))

    raise ModelError(f"调用失败: {last_error}")


def chat_json(cfg: dict, messages: list[dict], model: str | None = None, max_tokens: int = 8192) -> dict:
    """调用并解析 JSON，解析失败时要求模型重发。"""
    content = chat(cfg, messages, model=model, max_tokens=max_tokens)
    for attempt in range(2):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = JSON_RE.search(content)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            if attempt == 0:
                logger.warning("模型返回不是合法 JSON，要求重发")
                messages = messages + [
                    {"role": "assistant", "content": content[:2000]},
                    {"role": "user", "content": "上面的内容不是合法 JSON。请只输出 JSON，不要任何解释或代码块标记。"},
                ]
                content = chat(cfg, messages, model=model, max_tokens=max_tokens)
    raise ModelError("模型连续两次返回非法 JSON")
