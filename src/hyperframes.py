"""把分镜 + 时间轴 + 字幕组装成一个 HyperFrames 视频工程。

生成的目录结构和 ai-media 工作区里的现成项目一致：index.html + assets/，
复制过去（或直接在本地）跑 npx hyperframes render 就能出片。
"""

from __future__ import annotations

import html
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("brief")

LAYOUTS = {
    "douyin": {
        "resolution": "portrait",
        "width": 1080,
        "height": 1920,
        "body_size": 38,
        "cue_font": 58,
        "cue_bottom": 480,
        "cue_width": 26,
        "pad": "0 110px 380px",
        "h1_sizes": [(6, 124), (8, 104), (10, 88), (12, 78), (99, 70)],
    },
    "bili": {
        "resolution": "landscape",
        "width": 1920,
        "height": 1080,
        "body_size": 36,
        "cue_font": 50,
        "cue_bottom": 132,
        "cue_width": 44,
        "pad": "0 160px 120px",
        "h1_sizes": [(8, 112), (11, 96), (14, 82), (99, 72)],
    },
}

PACKAGE_JSON = {
    "name": "aibrief-weekly",
    "private": True,
    "type": "module",
    "scripts": {
        "dev": "npx --yes hyperframes@0.8.163 preview",
        "check": "npx --yes hyperframes@0.8.163 check",
        "render": "npx --yes hyperframes@0.8.163 render",
        "publish": "npx --yes hyperframes@0.8.163 publish",
    },
}

HYPERFRAMES_JSON = {
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {
        "blocks": "compositions",
        "components": "compositions/components",
        "assets": "assets",
    },
    "media": {"autoProxy": True},
}


def pick_size(sizes: list[tuple[int, int]], text: str) -> int:
    length = len(text)
    for limit, size in sizes:
        if length <= limit:
            return size
    return sizes[-1][1]


def scene_title(screen: str, emphasis: str) -> str:
    """把强调词包上标色 span，其余部分转义。"""
    safe_screen = html.escape(screen)
    if not emphasis:
        return safe_screen
    safe_em = html.escape(emphasis)
    return safe_screen.replace(safe_em, f'<span class="hl">{safe_em}</span>', 1)


def scene_times(timeline: dict) -> list[tuple[float, float]]:
    """每个场景占一段：从该段的 start 到下一段的 start，最后一段到片尾。"""
    segments = timeline.get("segments") or []
    total = float(timeline.get("video_duration") or timeline.get("total") or 0)
    spans: list[tuple[float, float]] = []
    for index, seg in enumerate(segments):
        start = float(seg["start"])
        end = float(segments[index + 1]["start"]) if index + 1 < len(segments) else total
        spans.append((round(start, 3), round(max(end - start, 0.5), 3)))
    return spans


def build_index_html(version: str, storyboard: dict, timeline: dict, cues: dict) -> str:
    layout = LAYOUTS.get(version, LAYOUTS["douyin"])
    scenes = storyboard.get("scenes") or []
    spans = scene_times(timeline)
    total = float(timeline.get("video_duration") or timeline.get("total") or 0)

    scene_html: list[str] = []
    cue_html: list[str] = []
    anim: list[str] = []

    for index, (scene, (start, duration)) in enumerate(zip(scenes, spans), start=1):
        size = pick_size(layout["h1_sizes"], scene.get("screen", ""))
        title = scene_title(scene.get("screen", ""), scene.get("emphasis", ""))
        sub = scene.get("sub", "")
        scene_html.append(
            f'      <div class="clip scene" id="scene{index}" '
            f'data-start="{start}" data-duration="{duration}" data-track-index="0">'
        )
        scene_html.append(
            f'        <h1 id="t{index}" style="font-size:{size}px">{title}</h1>'
        )
        if sub:
            scene_html.append(f'        <div class="sub" id="s{index}">{html.escape(sub)}</div>')
        scene_html.append("      </div>")

        anim.append(
            f'      tl.fromTo("#t{index}", {{ opacity: 0, y: 48 }}, '
            f'{{ opacity: 1, y: 0, duration: 0.5 }}, {round(start + 0.12, 3)});'
        )
        if sub:
            anim.append(
                f'      tl.fromTo("#s{index}", {{ opacity: 0, y: 20 }}, '
                f'{{ opacity: 1, y: 0, duration: 0.42 }}, {round(start + 0.42, 3)});'
            )

    for index, cue in enumerate(cues.get("cues") or [], start=1):
        start = float(cue["start"])
        duration = round(float(cue["end"]) - start, 3)
        cue_html.append(
            f'      <div class="cue" id="cue{index}" data-start="{start}" '
            f'data-duration="{duration}">{html.escape(cue["text"])}</div>'
        )

    return f"""<!doctype html>
<html lang="zh-CN" data-resolution="{layout['resolution']}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={layout['width']}, height={layout['height']}" />
    <script src="assets/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      @font-face {{ font-family: "Microsoft YaHei"; src: local("Microsoft YaHei"); }}
      html, body {{
        margin: 0; width: {layout['width']}px; height: {layout['height']}px; overflow: hidden;
        background: #05080f; font-family: "Microsoft YaHei"; color: #f8fafc;
      }}
      .grid-bg {{
        position: absolute; inset: 0;
        background-image:
          linear-gradient(rgba(120, 160, 200, 0.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(120, 160, 200, 0.06) 1px, transparent 1px);
        background-size: 150px 150px;
      }}
      .scene {{
        position: absolute; left: 0; top: 0;
        width: {layout['width']}px; height: {layout['height']}px;
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; text-align: center;
        padding: {layout['pad']};
      }}
      h1 {{ font-weight: 800; line-height: 1.22; }}
      .hl {{ color: #fbbf24; }}
      .sub {{
        margin-top: 38px; font-size: {layout['body_size']}px;
        color: #94a3b8; line-height: 1.5; max-width: 84%;
      }}
      .cue {{
        /* left:50% 会让可用宽度只剩半个屏幕，max-width 形同虚设、字幕被迫折行；
           改成左右贴边 + margin auto 居中，宽度才真正由内容决定 */
        position: absolute; left: 0; right: 0; bottom: {layout['cue_bottom']}px;
        margin-left: auto; margin-right: auto;
        width: fit-content; max-width: 88%;
        padding: 14px 34px;
        background: rgba(5, 8, 15, 0.8);
        border-radius: 10px;
        font-size: {layout['cue_font']}px; font-weight: 700; color: #ffffff;
        line-height: 1.35; text-align: center; white-space: nowrap;
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{total:.3f}"
      data-width="{layout['width']}"
      data-height="{layout['height']}"
    >
      <div class="grid-bg"></div>
      <audio id="vo" src="assets/mix_full.wav" data-start="0" data-duration="{total:.3f}"></audio>

{chr(10).join(scene_html)}

{chr(10).join(cue_html)}
    </div>

    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});

{chr(10).join(anim)}

      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def write_project(
    version: str,
    project_dir: Path,
    storyboard: dict,
    timeline: dict,
    cues: dict,
    assets_src: Path,
    gsap_src: Path | None = None,
) -> Path:
    """写出一个完整可渲染的 HyperFrames 项目目录。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    (project_dir / "index.html").write_text(
        build_index_html(version, storyboard, timeline, cues), encoding="utf-8"
    )
    (project_dir / "package.json").write_text(
        json.dumps(PACKAGE_JSON, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (project_dir / "hyperframes.json").write_text(
        json.dumps(HYPERFRAMES_JSON, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (project_dir / "meta.json").write_text(
        json.dumps(
            {"id": f"aibrief-weekly-{version}", "name": f"aibrief-weekly-{version}"},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for name in ("mix_full.wav", "voice_full.wav", "voice_timeline.json", "cues.json"):
        source = assets_src / name
        if source.exists():
            shutil.copy2(source, assets_dir / name)
    for stale in assets_dir.glob("voice_*.mp3"):
        stale.unlink()
    # Path("") 会变成当前目录，所以必须先判空再判是不是文件
    if gsap_src and Path(gsap_src).is_file():
        shutil.copy2(gsap_src, assets_dir / "gsap.min.js")

    logger.info("视频工程已生成：%s", project_dir)
    return project_dir
