"""配置、环境变量、日志、路径。"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path | None = None) -> None:
    """读取 .env，不覆盖已有的系统环境变量。"""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def set_base_url(url: str, path: Path | None = None) -> bool:
    """只改 config.yaml 里的 base_url 一行，保住文件里的注释和排版。

    之前用 yaml.safe_dump 整体重写，会把注释全抹掉。
    """
    import re

    path = path or ROOT / "config.yaml"
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"(?m)^(\s*base_url:\s*).*$",
        lambda match: f"{match.group(1)}{url}",
        text,
        count=1,
    )
    if count:
        path.write_text(new_text, encoding="utf-8")
    return bool(count)


def local_tz(cfg: dict):
    name = cfg["brief"].get("timezone", "Asia/Shanghai")
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        # Windows 上可能没装 tzdata，退回固定东八区，不让程序因为时区挂掉
        return timezone(timedelta(hours=8), name)


def now_local(cfg: dict) -> datetime:
    return datetime.now(local_tz(cfg))


def data_dir() -> Path:
    path = ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def out_dir(cfg: dict) -> Path:
    path = ROOT / cfg["site"].get("out_dir", "out")
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(cfg: dict) -> logging.Logger:
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass

    logger = logging.getLogger("brief")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(
        log_dir / f"{now_local(cfg):%Y-%m-%d}.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def load_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8").strip()


def resolve_local_path(
    cfg_value: str | None, env_name: str, default: str = "", exe_name: str = ""
) -> str:
    """本机相关路径的解析顺序：config → .env → PATH → 兜底默认值。

    config.yaml 是公开的，所以这类路径优先放 .env（不进 git），
    再退到 PATH 里找，最后才用代码里的兜底值。
    """
    import shutil

    if cfg_value and str(cfg_value).strip():
        return str(cfg_value).strip()
    value = (os.environ.get(env_name) or "").strip()
    if value:
        return value
    if exe_name:
        found = shutil.which(exe_name)
        if found:
            return found
    return default


CJK_RE = r"[\u4e00-\u9fff]"


def spacing(text: str) -> str:
    """中英文之间补一个空格——模型常写成「Muse Wonder定价对标」，挤在一起不好读。"""
    import re

    text = re.sub(rf"({CJK_RE})([A-Za-z0-9])", r"\1 \2", text or "")
    text = re.sub(rf"([A-Za-z0-9])({CJK_RE})", r"\1 \2", text)
    return re.sub(r"\s{2,}", " ", text).strip()
