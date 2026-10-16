"""把一期周报的配音工程组装成可渲染的 HyperFrames 项目。

用法：
  python tools/make_video.py                       # 最新一期，生成工程
  python tools/make_video.py 2026-10-16            # 指定期
  python tools/make_video.py --copy                # 顺便复制到 ai-media 工作区
  python tools/make_video.py --copy --render       # 复制并渲染出片
  python tools/make_video.py --only douyin         # 只做抖音版
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import hyperframes  # noqa: E402
import ogimage  # noqa: E402
import storyboard as storyboard_mod  # noqa: E402
import tts  # noqa: E402
from common import load_config, load_env, resolve_local_path, setup_logging  # noqa: E402
from fetch import make_session  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

IMAGE_EXTENSIONS = (".png", ".webp", ".gif", ".jpeg", ".jpg")


def guess_extension(url: str) -> str:
    lower = url.lower()
    for candidate in IMAGE_EXTENSIONS:
        if candidate in lower:
            return candidate
    return ".jpg"


def collect_screenshots(cfg, digest: dict, board: dict, log):
    """给每一幕找一张素材图。返回 [(scene, image_url, use_proxy)]。"""
    items: dict[int, dict] = {}
    index = 0
    for group in digest.get("groups") or []:
        for item in group.get("items") or []:
            index += 1
            items[index] = item

    proxies = ogimage.proxy_map(cfg)
    session = make_session(cfg)
    pending: list[tuple[dict, str, bool]] = []

    for order, scene in enumerate(board.get("scenes") or [], start=1):
        if scene.get("image"):
            continue  # 上一次已经配好图，别重复抓
        try:
            item_index = int(scene.get("item") or 0)
        except (TypeError, ValueError):
            item_index = 0
        item = items.get(item_index)
        if not item:
            continue
        image_url, source_url, use_proxy = ogimage.find_for_sources(
            cfg, session, item.get("sources") or [], proxies
        )
        if not image_url:
            log.info("第 %d 幕没找到素材图：%s", order, item.get("title", "")[:24])
            continue
        name = f"scene-{order}{guess_extension(image_url)}"
        scene["image"] = name
        pending.append((scene, image_url, use_proxy))
        log.info("第 %d 幕配图来自 %s", order, source_url[:70])

    return pending


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成周报视频工程")
    parser.add_argument("period", nargs="?", default="", help="周报日期，默认最新一期")
    parser.add_argument("--copy", action="store_true", help="复制到 ai-media 工作区")
    parser.add_argument("--render", action="store_true", help="渲染出片（隐含 --copy）")
    parser.add_argument("--only", default="", help="只做某个版本，例如 douyin")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()
    cfg = load_config()
    log = setup_logging(cfg)
    weekly_cfg = cfg.get("weekly") or {}

    base = ROOT / "data" / "weekly"
    dirs = sorted(path for path in base.glob("*") if path.is_dir())
    if not dirs:
        print("还没有生成过周报。")
        return 1
    target = base / args.period if args.period else dirs[-1]
    if not target.exists():
        print(f"找不到 {args.period}")
        return 1

    brand = str(weekly_cfg.get("brand") or "一周 AI 大事件")
    try:
        issue = sorted(path.name for path in dirs).index(target.name) + 1
    except ValueError:
        issue = 0
    brand_sub = f"第 {issue} 期" if issue else ""

    versions = list((weekly_cfg.get("versions") or {}).keys())
    if args.only:
        versions = [args.only]

    gsap_value = resolve_local_path(weekly_cfg.get("gsap"), "GSAP_PATH")
    gsap_src = Path(gsap_value) if gsap_value else None
    ai_media_value = resolve_local_path(weekly_cfg.get("ai_media_dir"), "AI_MEDIA_DIR")
    ai_media = Path(ai_media_value) if ai_media_value else None

    # hyperframes 从 PATH 里找 ffmpeg/ffprobe，把配置里的那个目录塞进去
    render_env = os.environ.copy()
    ffmpeg_dir = str(Path(tts.ffmpeg_path(cfg)).parent)
    for key in list(render_env.keys()):
        if key.upper() == "PATH":
            render_env[key] = ffmpeg_dir + os.pathsep + render_env[key]
            break
    else:
        render_env["PATH"] = ffmpeg_dir

    for version in versions:
        script_path = target / f"script-{version}.json"
        assets = target / f"assets-{version}"
        timeline_path = assets / "voice_timeline.json"
        if not (script_path.exists() and timeline_path.exists()):
            log.warning("跳过 %s：素材不齐（缺口播稿或音频）", version)
            continue
        if not (assets / "mix_full.wav").exists():
            log.warning("跳过 %s：还没有混音整轨，先跑 tools/rebuild_audio.py", version)
            continue

        script = json.loads(script_path.read_text(encoding="utf-8"))
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        # 字幕从时间轴现算，避免用到旧版切法留下的文件
        cue_width = hyperframes.LAYOUTS.get(version, {}).get("cue_width", 26)
        cues = tts.build_cues(timeline["segments"], max_width=cue_width)
        (assets / "cues.json").write_text(
            json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        digest = json.loads((target / "digest.json").read_text(encoding="utf-8"))
        board = storyboard_mod.load_or_build(
            cfg, script, digest, target / f"storyboard-{version}.json", log
        )

        pending: list[tuple[dict, str, bool]] = []
        if weekly_cfg.get("images", True):
            pending = collect_screenshots(cfg, digest, board, log)
        if pending:
            (target / f"storyboard-{version}.json").write_text(
                json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        project_dir = target / f"video-{version}"
        hyperframes.write_project(
            version,
            project_dir,
            board,
            timeline,
            cues,
            assets,
            gsap_src,
            brand=brand,
            brand_sub=brand_sub,
        )

        if pending:
            session = make_session(cfg)
            assets_dir = project_dir / "assets"
            for scene, image_url, use_proxy in pending:
                target_file = assets_dir / scene["image"]
                if target_file.exists() and target_file.stat().st_size > 0:
                    continue
                if ogimage.download_image(cfg, session, image_url, target_file, use_proxy=use_proxy):
                    log.info("  下载配图 %s（%.0f KB）", target_file.name,
                             target_file.stat().st_size / 1024)
                else:
                    log.warning("  配图下载失败：%s", image_url[:70])

        if not (args.copy or args.render):
            continue
        if ai_media is None:
            log.warning("没有配置 AI_MEDIA_DIR（.env 里加一行），跳过复制")
            continue

        dest = ai_media / f"aibrief-weekly-{version}"
        dest.mkdir(parents=True, exist_ok=True)
        for item in project_dir.iterdir():
            target_item = dest / item.name
            if item.is_dir():
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(item, target_item)
            else:
                shutil.copy2(item, target_item)
        # renders 是产物，重跑时不覆盖
        (dest / "renders").mkdir(exist_ok=True)
        log.info("已复制到：%s", dest)

        if args.render:
            log.info("%s 渲染前先跑一次工程检查…", version)
            check = subprocess.run(
                "npm run check",
                cwd=str(dest),
                shell=True,
                env=render_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
            check_out = ((check.stdout or "") + (check.stderr or "")).strip()
            if check.returncode == 0:
                log.info("%s 检查通过", version)
            else:
                log.warning(
                    "%s 检查报错（返回码 %s）：\n%s", version, check.returncode, check_out[-1500:]
                )
            log.info("开始渲染 %s…", version)
            result = subprocess.run(
                "npm run render",
                cwd=str(dest),
                shell=True,
                env=render_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3600,
            )
            output = (result.stdout or "") + (result.stderr or "")
            renders = sorted((dest / "renders").glob("*.mp4")) if (dest / "renders").exists() else []
            if renders:
                log.info("渲染完成：%s", renders[-1])
            else:
                log.warning("没找到产物（返回码 %s）：\n%s", result.returncode, output[-1200:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
