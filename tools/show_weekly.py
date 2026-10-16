"""查看某期周报的底稿和口播稿。

用法：
  python tools/show_weekly.py              # 最新一期
  python tools/show_weekly.py 2026-10-16   # 指定覆盖到哪天
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    base = ROOT / "data" / "weekly"
    dirs = sorted(path for path in base.glob("*") if path.is_dir())
    if not dirs:
        print("还没有生成过周报。")
        return 1

    target = dirs[-1]
    if len(sys.argv) > 1:
        candidate = base / sys.argv[1]
        if not candidate.exists():
            print(f"找不到 {sys.argv[1]} 的周报。")
            return 1
        target = candidate

    digest = json.loads((target / "digest.json").read_text(encoding="utf-8"))
    groups = digest.get("groups") or []
    total = sum(len(group.get("items") or []) for group in groups)

    print(f"== 周报 {target.name} · {len(groups)} 组 / {total} 条 ==")
    print(f"头条：{digest.get('headline', '')}")
    if digest.get("skipped_note"):
        print(f"备注：{digest['skipped_note']}")
    print()

    for group in groups:
        print(f"【{group.get('name', '')}】{group.get('summary', '')}")
        for index, item in enumerate(group.get("items") or [], start=1):
            flag = "（本周持续）" if item.get("ongoing") else ""
            print(f"  {index}. [{item.get('date')}·{item.get('source_count')}源·{item.get('confidence')}]{flag} {item.get('title')}")
            print(f"     {item.get('what')}")
        print()

    for version in ("douyin", "bili"):
        path = target / f"script-{version}.json"
        if not path.exists():
            continue
        script = json.loads(path.read_text(encoding="utf-8"))
        chars = sum(len(seg.get("text", "")) for seg in script.get("segments") or [])
        timeline_path = target / f"assets-{version}" / "voice_timeline.json"
        duration = ""
        if timeline_path.exists():
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
            duration = f"，配音 {timeline['total']:.1f} 秒"
        print(f"===== {version} 口播稿（{chars} 字{duration}）=====")
        for seg in script.get("segments") or []:
            print(f"[{seg.get('key')}] {seg.get('text')}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
