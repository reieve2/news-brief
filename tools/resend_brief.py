"""按日期补推一次早报——只推送，不重新生成、不花钱。

用法：
  python tools/resend_brief.py              # 最新一期
  python tools/resend_brief.py 2026-10-17   # 指定日期
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import notify  # noqa: E402
from common import load_config, load_env, setup_logging  # noqa: E402


def main() -> int:
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)

    briefs = sorted((ROOT / "data" / "briefs").glob("*.json"))
    if not briefs:
        print("还没有存档。")
        return 1

    target = briefs[-1]
    if len(sys.argv) > 1:
        target = ROOT / "data" / "briefs" / f"{sys.argv[1]}.json"
        if not target.exists():
            print(f"找不到 {sys.argv[1]} 的存档。")
            return 1

    data = json.loads(target.read_text(encoding="utf-8"))
    url = (cfg["site"].get("base_url") or "").rstrip("/")
    note = f"降级版本：{data['degraded_reason']}" if data.get("degraded") else ""
    ok = notify.send(cfg, data["date"], data["cards"], url, note)
    print(f"补推 {data['date']}：{'成功' if ok else '失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
