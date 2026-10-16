"""把口播稿变成配音文件，以及视频工程要用的时间轴和字幕。

输出格式对齐 ai-media 工作区里现有项目的 assets 写法：
  voice_<key>.mp3        分段配音
  voice_timeline.json    分段文本 + 起止时间
  cues.json              字幕短句 + 起止时间
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path

from common import resolve_local_path, spacing

logger = logging.getLogger("brief")

# 现有三个项目的成片都比配音总长多 3.5 秒，留给片尾
VIDEO_TAIL = 3.5
# 英文句点不能当分隔符——它是小数点（Opus 5.5）和缩写的组成部分
# 顿号也不能断——「开发者、企业、消费者」是一组并列，断开就散了
SPLIT_RE = re.compile(r"[，。！？；,!?;：:]+")

# 这些词落在行尾读起来会断气
CONNECTORS = {"和", "与", "及", "或", "跟", "并", "而", "但", "在", "把", "被", "的", "了"}

# 整行超宽时的优先断点
SOFT_BREAKS = "，、；："

# 本机路径一律放 .env（见 config.yaml 里 weekly 那节的说明），代码里不写死
DEFAULT_FFPROBE = ""
DEFAULT_FFMPEG = ""


def ffprobe_path(cfg: dict) -> str:
    weekly = (cfg or {}).get("weekly") or {}
    return resolve_local_path(weekly.get("ffprobe"), "FFPROBE_PATH", DEFAULT_FFPROBE, "ffprobe")


def ffmpeg_path(cfg: dict) -> str:
    weekly = (cfg or {}).get("weekly") or {}
    return resolve_local_path(weekly.get("ffmpeg"), "FFMPEG_PATH", DEFAULT_FFMPEG, "ffmpeg")


def bgm_path(cfg: dict) -> str:
    weekly = (cfg or {}).get("weekly") or {}
    return resolve_local_path(weekly.get("bgm"), "BGM_PATH")


class TTSError(RuntimeError):
    pass


def probe_duration(path: Path, ffprobe: str | None = None) -> float:
    """用 ffprobe 读音频真实时长（秒）。"""
    exe = ffprobe or DEFAULT_FFPROBE
    if not Path(exe).exists():
        raise TTSError(
            f"找不到 ffprobe（{exe or '未配置'}）。请在 .env 里设 FFPROBE_PATH，"
            f"或把 ffmpeg 所在目录加进 PATH。"
        )
    result = subprocess.run(
        [
            exe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise TTSError(f"ffprobe 读取失败：{result.stderr.strip()[:200]}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise TTSError(f"ffprobe 返回的不是数字：{result.stdout!r}") from exc


async def _synth_all(jobs: list[tuple[str, str, str, Path]]) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise TTSError("没装 edge-tts，先跑 pip install edge-tts") from exc

    for text, voice, rate, out_path in jobs:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(out_path))


def synthesize(texts: list[str], out_paths: list[Path], voice: str, rate: str) -> None:
    """一次性合成所有分段（一个事件循环里跑完，避免反复起停）。"""
    if len(texts) != len(out_paths):
        raise TTSError("文本数和输出路径数不一致")
    jobs = [(t, voice, rate, p) for t, p in zip(texts, out_paths)]
    try:
        asyncio.run(_synth_all(jobs))
    except TTSError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TTSError(f"配音失败：{type(exc).__name__}: {exc}") from exc


def build_timeline(voice: str, rate: str, gap: float, segments: list[dict]) -> dict:
    """segments 里每项需含 key / text / file / duration。"""
    cursor = 0.0
    out: list[dict] = []
    for seg in segments:
        start = round(cursor, 3)
        end = round(start + float(seg["duration"]), 3)
        out.append(
            {
                "key": seg["key"],
                "text": seg["text"],
                "file": seg["file"],
                "duration": round(float(seg["duration"]), 3),
                "start": start,
                "end": end,
            }
        )
        cursor = end + gap
    total = round(max(cursor - gap, 0.0), 3)
    return {
        "voice": voice,
        "rate": rate,
        "gap": gap,
        "total": total,
        "video_duration": round(total + VIDEO_TAIL, 3),
        "segments": out,
    }


def display_width(text: str) -> int:
    """屏幕上占多宽：中日韩字符按 2 算，英文数字标点按 1 算。"""
    return sum(2 if ord(char) > 0x2E80 else 1 for char in text)


def _greedy_lines(words: list[str], limit: int) -> list[str]:
    """按宽度装行。连接词（和、的、与……）不许落在行尾。"""
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}" if line else word
        if not line or display_width(candidate) <= limit:
            line = candidate
            continue
        parts = line.split(" ")
        if len(parts) > 1 and parts[-1] in CONNECTORS:
            lines.append(" ".join(parts[:-1]))
            line = f"{parts[-1]} {word}"
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _rebalance(lines: list[str], limit: int) -> list[str]:
    """最后一行太短时，从上一行末尾挪一个词过来。"""
    if len(lines) < 2 or display_width(lines[-1]) >= 10:
        return lines
    prev_words = lines[-2].split(" ")
    if len(prev_words) < 2:
        return lines
    moved = prev_words[-1]
    new_prev = " ".join(prev_words[:-1])
    new_last = f"{moved} {lines[-1]}"
    if display_width(new_last) <= limit:
        return lines[:-2] + [new_prev, new_last]
    return lines


def _hard_split(line: str, limit: int) -> list[str]:
    """整行放不下时切开。中文优先断在标点上，实在没有标点才按宽度硬切。"""
    if display_width(line) <= limit:
        return [line]

    pieces: list[str] = []
    rest = line
    while display_width(rest) > limit:
        cut = ""
        best = -1
        for char in rest:
            if display_width(cut + char) > limit:
                break
            cut += char
            if char in SOFT_BREAKS:
                best = len(cut)
        if best > len(cut) * 0.5:  # 断点太靠前还不如硬切
            pieces.append(rest[:best].strip())
            rest = rest[best:].lstrip()
        else:
            pieces.append(cut)
            rest = rest[len(cut):]
    if rest:
        pieces.append(rest)
    return pieces


def split_cue_text(text: str, max_width: int = 26) -> list[str]:
    """切成能一行放下的字幕。

    英文按词边界断，不许把单词劈成两半；行数定了之后再均衡一次，
    免得出现「Gemini 4」/「Argon」这种最后一行只剩一个词的切法。
    """
    chunks: list[str] = []
    for part in SPLIT_RE.split(text):
        part = part.strip()
        if not part:
            continue
        words = [word for word in part.split(" ") if word]
        if not words:
            continue

        lines = _rebalance(_greedy_lines(words, max_width), max_width)
        for line in lines:
            chunks.extend(_hard_split(line, max_width))
    return chunks


def build_cues(segments: list[dict], size: tuple[int, int] = (1920, 1080), max_width: int = 26) -> dict:
    """把每段口播词切成字幕短句，按显示宽度比例分配到该段的时间窗里。"""
    cues: list[dict] = []
    for seg in segments:
        chunks = split_cue_text(spacing(seg["text"]), max_width)
        if not chunks:
            continue
        weights = [display_width(chunk) for chunk in chunks]
        total_weight = sum(weights) or 1
        start = float(seg["start"])
        span = float(seg["end"]) - start
        cursor = start
        for chunk, weight in zip(chunks, weights):
            length = span * weight / total_weight
            cues.append(
                {"text": chunk, "start": round(cursor, 3), "end": round(cursor + length, 3)}
            )
            cursor += length
    return {"size": list(size), "cues": cues}


def write_assets_dir(
    assets_dir: Path,
    script: dict,
    voice: str,
    rate: str,
    gap: float,
    ffprobe: str | None,
) -> dict:
    """把一份口播稿落成 assets 目录，返回 timeline。"""
    segs = script.get("segments") or []
    if not segs:
        raise TTSError("口播稿里没有分段")

    assets_dir.mkdir(parents=True, exist_ok=True)
    # 同一期反复重跑时，段数会变，上一轮的分段音频必须清掉，否则新旧混在一起
    for stale in assets_dir.glob("voice_*.mp3"):
        stale.unlink()
    texts: list[str] = []
    paths: list[Path] = []
    for index, seg in enumerate(segs, start=1):
        seg.setdefault("key", f"s{index}")
        key = seg["key"]
        seg["file"] = f"voice_{key}.mp3"
        texts.append(seg["text"])
        paths.append(assets_dir / seg["file"])

    logger.info("开始配音，共 %d 段…", len(texts))
    synthesize(texts, paths, voice, rate)

    with_duration: list[dict] = []
    for seg, path in zip(segs, paths):
        duration = probe_duration(path, ffprobe)
        with_duration.append({**seg, "duration": duration})

    timeline = build_timeline(voice, rate, gap, with_duration)
    (assets_dir / "voice_timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    cues = build_cues(timeline["segments"])
    (assets_dir / "cues.json").write_text(
        json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "配音完成：%.1f 秒 / %d 段 / 字幕 %d 条",
        timeline["total"],
        len(timeline["segments"]),
        len(cues["cues"]),
    )
    return timeline


def _run_ffmpeg(ffmpeg: str, args: list[str], log: logging.Logger) -> None:
    if not Path(ffmpeg).exists():
        raise TTSError(
            f"找不到 ffmpeg（{ffmpeg or '未配置'}）。请在 .env 里设 FFMPEG_PATH，"
            f"或把 ffmpeg 所在目录加进 PATH。"
        )
    result = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise TTSError(f"ffmpeg 失败：{(result.stderr or '').strip()[:300]}")


def build_full_tracks(
    assets_dir: Path,
    timeline: dict,
    ffmpeg: str | None = None,
    bgm: str | None = None,
    bgm_volume: float = 0.12,
    log: logging.Logger | None = None,
) -> dict:
    """把分段音频拼成整轨，再叠上背景音乐——渲染工程读的是这两条轨。

    分段之间有空隙，所以按 timeline 里的 start 逐个 adelay 对齐再混，不去猜间隔。
    """
    log = log or logger
    exe = ffmpeg or DEFAULT_FFMPEG
    segs = timeline.get("segments") or []
    if not segs:
        raise TTSError("时间轴里没有分段")

    voice_out = assets_dir / "voice_full.wav"
    args: list[str] = []
    for seg in segs:
        args += ["-i", str(assets_dir / seg["file"])]
    filters = [
        f"[{index}:a]adelay={int(round(float(seg['start']) * 1000))}|"
        f"{int(round(float(seg['start']) * 1000))}[a{index}]"
        for index, seg in enumerate(segs)
    ]
    joined = "".join(f"[a{index}]" for index in range(len(segs)))
    filters.append(f"{joined}amix=inputs={len(segs)}:normalize=0:duration=longest[out]")
    args += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le",
        str(voice_out),
    ]
    _run_ffmpeg(exe, args, log)
    log.info("整轨配音已生成：%s", voice_out.name)

    result = {"voice_full": voice_out.name}
    if not bgm or not Path(bgm).exists():
        if bgm:
            log.warning("找不到 BGM（%s），只出配音整轨", bgm)
        return result

    mix_out = assets_dir / "mix_full.wav"
    total = float(timeline.get("video_duration") or timeline.get("total") or 0)
    _run_ffmpeg(
        exe,
        [
            "-i", str(voice_out),
            "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[bg];[0:a][bg]amix=inputs=2:duration=first:normalize=0[out]",
            "-map", "[out]",
            "-t", f"{total:.3f}",
            "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le",
            str(mix_out),
        ],
        log,
    )
    log.info("混音整轨已生成：%s（%.1f 秒）", mix_out.name, total)
    result["mix_full"] = mix_out.name
    return result
