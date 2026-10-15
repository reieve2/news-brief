"""在命令行里查看某天的早报内容。

用法：
  python tools/show_brief.py            # 最新一期
  python tools/show_brief.py 2026-10-07 # 指定日期
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    briefs = sorted((ROOT / "data" / "briefs").glob("*.json"))
    if not briefs:
        print("还没有生成过早报。")
        return 1

    target = briefs[-1]
    if len(sys.argv) > 1:
        candidate = ROOT / "data" / "briefs" / f"{sys.argv[1]}.json"
        if not candidate.exists():
            print(f"找不到 {sys.argv[1]} 的早报。")
            return 1
        target = candidate

    data = json.loads(target.read_text(encoding="utf-8"))
    cards = data.get("cards", [])

    print(f"== {data.get('date')} 早报 · {len(cards)} 条 · 生成于 {data.get('generated_at')} ==")
    if data.get("degraded"):
        print(f"（降级版本：{data.get('degraded_reason')}）")
    print()

    for index, card in enumerate(cards, start=1):
        sources = "、".join(item["name"] for item in card.get("sources", []))
        print(f"{index}. {card['title']}    [{card['confidence']}] {sources}")
        print(f"   发生：{card['what']}")
        print(f"   背景：{card['background']}")
        print(f"   重要：{card['why']}")
        print(f"   预测：{card['next']}")
        terms = card.get("terms") or []
        if terms:
            print("   术语：" + "；".join(f"{item['term']}={item['gloss']}" for item in terms))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
