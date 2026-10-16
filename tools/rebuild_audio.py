"""从已有的口播稿重建配音和整轨——不调用模型，不花钱。

改了音色、语速、BGM 之后用它重出音频，不用重跑整期周报。

用法：
  python tools/rebuild_audio.py              # 最新的那一期，两个版本都重建
  python tools/rebuild_audio.py 2026-10-16   # 指定期
  python tools/rebuild_audio.py 2026-10-16 douyin
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tts  # noqa: E402
from common import load_config, load_env, setup_logging  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)
    weekly_cfg = cfg.get("weekly") or {}

    base = ROOT / "data" / "weekly"
    dirs = sorted(path for path in base.glob("*") if path.is_dir())
    if not dirs:
        print("还没有生成过周报。")
        return 1

    target = dirs[-1]
    versions = list((weekly_cfg.get("versions") or {}).keys())
    if len(sys.argv) > 1:
        target = base / sys.argv[1]
        if not target.exists():
            print(f"找不到 {sys.argv[1]}")
            return 1
    if len(sys.argv) > 2:
        versions = [sys.argv[2]]

    ffprobe = tts.ffprobe_path(cfg)
    ffmpeg = tts.ffmpeg_path(cfg)

    for version in versions:
        script_path = target / f"script-{version}.json"
        if not script_path.exists():
            print(f"跳过 {version}：没有口播稿")
            continue
        script = json.loads(script_path.read_text(encoding="utf-8"))
        params = cfg["weekly"]["versions"][version]
        assets = target / f"assets-{version}"
        timeline = tts.write_assets_dir(
            assets, script, params["voice"], params["rate"], float(params["gap"]), ffprobe
        )
        tts.build_full_tracks(
            assets,
            timeline,
            ffmpeg=ffmpeg,
            bgm=tts.bgm_path(cfg),
            bgm_volume=float(weekly_cfg.get("bgm_volume", 0.12)),
            log=log,
        )
        log.info("%s 重建完成：%.1f 秒", version, timeline["total"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
