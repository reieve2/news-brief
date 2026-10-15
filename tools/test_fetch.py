"""只测抓取，不调用模型、不部署、不推送。

用法：
  python tools/test_fetch.py                      # 全部源
  python tools/test_fetch.py --only 机器之心,36氪   # 只测名字匹配的源
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fetch  # noqa: E402
from common import load_config, load_env, setup_logging  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    load_env()
    cfg = load_config()
    log = setup_logging(cfg)

    if args.only:
        keywords = [part.strip() for part in args.only.split(",") if part.strip()]
        cfg["sources"] = [
            source for source in cfg["sources"]
            if any(keyword.lower() in source["name"].lower() for keyword in keywords)
        ]

    entries, stats = fetch.fetch_all(cfg, log)
    entries = fetch.filter_recent(cfg, entries, log)

    log.info("---------- 统计 ----------")
    for item in stats:
        flag = "ok  " if item["count"] else "fail"
        log.info("%s %-26s %3d 条  %s", flag, item["name"], item["count"], item["error"])
    ok = sum(1 for item in stats if item["count"])
    log.info("可用源 %d/%d，时间窗内合计 %d 条", ok, len(stats), len(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
