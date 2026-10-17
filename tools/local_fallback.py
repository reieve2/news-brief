"""本地兜底：检查线上今天是否已有早报，没有才本地补跑一次。

设计意图：云端（GitHub Actions）是主力。这个脚本只在云端没跑成时补位，
所以它先查线上页面，确认缺失才生成——避免两边重复抓取、重复花钱。

用法:
    python tools/local_fallback.py           # 正常检查
    python tools/local_fallback.py --check   # 只检查不补跑
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "fallback.log"


def log(message: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        # 写日志失败不能把兜底本身带崩（2026-10-17 就是栽在这：权限被拒直接 exit 1）
        print(f"[WARN] 写日志失败：{exc}")


def online_has(date_str: str, base_url: str, attempts: int = 3) -> bool | None:
    """线上是否已有该日期的早报。网络不通时返回 None（不补跑，等下次）。"""
    url = f"{base_url}/?v={int(time.time())}"
    for i in range(attempts):
        try:
            resp = requests.get(
                url, timeout=20, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
            )
            return date_str in resp.text
        except Exception as exc:  # noqa: BLE001
            log(f"检查线上失败（{i + 1}/{attempts}）：{type(exc).__name__}")
            time.sleep(5)
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    check_only = "--check" in sys.argv

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    base_url = (cfg.get("site", {}).get("base_url") or "").strip().rstrip("/")
    if not base_url:
        log("config.yaml 里没有 site.base_url，无法检查，跳过")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    state = online_has(today, base_url)

    if state is True:
        log(f"线上已有 {today} 的早报，无需补跑")
        return
    if state is None:
        log("网络不通，无法判断线上状态，本次不补跑")
        return
    if check_only:
        log(f"线上缺少 {today} 的早报（仅检查模式，未补跑）")
        return

    log(f"线上缺少 {today} 的早报，本地补跑一次")
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "main.py"), "--force"],
        cwd=str(ROOT),
    )
    log(f"补跑结束，返回码 {result.returncode}")


if __name__ == "__main__":
    main()
