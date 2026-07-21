from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageFilter


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
IMAGE_EXTENSIONS = {".png", ".webp"}


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    width: int = 1080
    height: int = 1920


@dataclass(frozen=True)
class OverlaySpec:
    image: Path
    side: str
    width_ratio: float


@dataclass(frozen=True)
class ExportJob:
    video: Path
    music: Path
    output: Path
    overlays: tuple[OverlaySpec, ...] = ()
    white_outline: bool = False


def executable_path(name: str) -> str:
    """Find bundled FFmpeg binaries first, then fall back to PATH."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled = base / "ffmpeg" / f"{name}.exe"
    if bundled.exists():
        return str(bundled)
    found = shutil.which(name)
    if found:
        return found
    raise MediaError(f"找不到 {name}，请重新安装本程序。")


def probe_media(path: Path, ffprobe: str | None = None) -> MediaInfo:
    command = [
        ffprobe or executable_path("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height:stream_side_data=rotation",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        raise MediaError(detail[-1] if detail else "无法读取媒体文件")
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MediaError("无法获取媒体时长") from exc
    if duration <= 0:
        raise MediaError("媒体时长为 0")
    streams = data.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    width = int(video_stream.get("width") or 1080)
    height = int(video_stream.get("height") or 1920)
    rotation = next(
        (side_data.get("rotation", 0) for side_data in video_stream.get("side_data_list", []) if "rotation" in side_data),
        0,
    )
    if abs(int(rotation)) % 180 == 90:
        width, height = height, width
    return MediaInfo(
        duration=duration,
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
        width=width,
        height=height,
    )


def find_music(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in MUSIC_EXTENSIONS),
        key=lambda path: str(path).lower(),
    )


def find_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: str(path).lower(),
    )


def assign_random(
    items: Iterable[Path],
    choices: list[Path],
    rng: random.Random | None = None,
) -> list[tuple[Path, Path]]:
    items = list(items)
    if not choices:
        raise MediaError("可选文件列表为空")
    rng = rng or random.Random()
    assigned: list[tuple[Path, Path]] = []
    previous: Path | None = None
    pool: list[Path] = []
    for item in items:
        if not pool:
            pool = list(choices)
            rng.shuffle(pool)
            if len(pool) > 1 and pool[-1] == previous:
                pool[0], pool[-1] = pool[-1], pool[0]
        selected = pool.pop()
        assigned.append((item, selected))
        previous = selected
    return assigned


def assign_music(videos: Iterable[Path], music: list[Path], rng: random.Random | None = None) -> list[tuple[Path, Path]]:
    if not music:
        raise MediaError("音乐文件夹中没有支持的音频文件")
    return assign_random(videos, music, rng)


def assign_overlays(
    videos: Iterable[Path],
    images: list[Path],
    rng: random.Random | None = None,
) -> list[tuple[Path, tuple[OverlaySpec, ...]]]:
    if not images:
        raise MediaError("图片文件夹中没有支持的透明图片")
    rng = rng or random.Random()
    pool: list[Path] = []
    previous: Path | None = None

    def draw_image() -> Path:
        nonlocal pool, previous
        if not pool:
            pool = list(images)
            rng.shuffle(pool)
            if len(pool) > 1 and pool[-1] == previous:
                pool[0], pool[-1] = pool[-1], pool[0]
        selected = pool.pop()
        previous = selected
        return selected

    result = []
    for video in videos:
        count = rng.choice((1, 2)) if len(images) > 1 else 1
        if count == 1:
            overlays = (
                OverlaySpec(
                    image=draw_image(),
                    side=rng.choice(("left", "right")),
                    width_ratio=rng.choice((0.42, 0.50, 0.58)),
                ),
            )
        else:
            overlays = (
                OverlaySpec(draw_image(), "left", rng.choice((0.34, 0.38, 0.42))),
                OverlaySpec(draw_image(), "right", rng.choice((0.34, 0.38, 0.42))),
            )
        result.append((video, overlays))
    return result


def output_path_for(video: Path) -> Path:
    output_folder = video.parent / "已配乐"
    candidate = output_folder / f"{video.stem}_配乐.mp4"
    counter = 2
    while candidate.exists():
        candidate = output_folder / f"{video.stem}_配乐_{counter}.mp4"
        counter += 1
    return candidate


def add_white_outline(
    source: Path,
    destination: Path,
    max_width: int,
    max_height: int,
    outline_width: int,
) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    outline_width = max(1, int(outline_width))
    padded = Image.new(
        "RGBA",
        (image.width + outline_width * 2, image.height + outline_width * 2),
        (0, 0, 0, 0),
    )
    padded.alpha_composite(image, (outline_width, outline_width))
    expanded_alpha = padded.getchannel("A").filter(ImageFilter.MaxFilter(outline_width * 2 + 1))
    white = Image.new("RGBA", padded.size, (255, 255, 255, 0))
    white.putalpha(expanded_alpha)
    white.alpha_composite(padded)
    white.save(destination, "PNG")


def build_ffmpeg_command(
    job: ExportJob,
    info: MediaInfo,
    source_volume: float,
    music_volume: float,
    ffmpeg: str | None = None,
) -> list[str]:
    duration = info.duration
    fade_duration = min(1.0, duration)
    fade_start = max(0.0, duration - fade_duration)
    music_filter = (
        f"[1:a:0]volume={music_volume:.4f},"
        f"atrim=duration={duration:.6f},"
        f"afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f}[music]"
    )
    if info.has_audio:
        filter_complex = (
            f"[0:a:0]volume={source_volume:.4f},apad,atrim=duration={duration:.6f}[source];"
            f"{music_filter};"
            "[source][music]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
        )
    else:
        filter_complex = f"{music_filter};[music]anull[aout]"

    command = [
        ffmpeg or executable_path("ffmpeg"),
        "-hide_banner", "-y",
        "-i", str(job.video),
        "-stream_loop", "-1", "-i", str(job.music),
    ]
    if job.overlays:
        for overlay in job.overlays:
            command.extend(["-loop", "1", "-i", str(overlay.image)])
        image_filters = []
        base_label = "0:v:0"
        for index, overlay in enumerate(job.overlays):
            input_index = index + 2
            max_width = max(2, round(info.width * overlay.width_ratio))
            max_height = max(2, round(info.height * 0.48))
            image_filters.append(
                f"[{input_index}:v:0]format=rgba,"
                f"scale=w={max_width}:h={max_height}:force_original_aspect_ratio=decrease[overlay{index}]"
            )
            x_position = "main_w*0.02" if overlay.side == "left" else "main_w-overlay_w-main_w*0.02"
            output_label = f"vstage{index}"
            image_filters.append(
                f"[{base_label}][overlay{index}]overlay="
                f"x={x_position}:y=main_h-overlay_h:shortest=1[{output_label}]"
            )
            base_label = output_label
        filter_complex = f"{filter_complex};" + ";".join(image_filters)
        video_map = f"[{base_label}]"
        video_codec = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        video_map = "0:v:0"
        video_codec = ["-c:v", "copy"]

    command.extend([
        "-filter_complex", filter_complex,
        "-map", video_map, "-map", "[aout]",
        *video_codec,
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.6f}",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(job.output),
    ])
    return command


def export_job(
    job: ExportJob,
    source_volume: float,
    music_volume: float,
    progress: Callable[[float], None] | None = None,
) -> None:
    info = probe_media(job.video)
    music_info = probe_media(job.music)
    if not music_info.has_audio:
        raise MediaError("所选音乐不包含音轨")
    job.output.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        effective_job = job
        if job.white_outline and job.overlays:
            temp_folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="quick_music_outline_")))
            outlined = []
            outline_width = max(3, round(info.width * 0.007))
            for index, overlay in enumerate(job.overlays):
                destination = temp_folder / f"outline_{index}.png"
                add_white_outline(
                    overlay.image,
                    destination,
                    max_width=max(2, round(info.width * overlay.width_ratio)),
                    max_height=max(2, round(info.height * 0.48)),
                    outline_width=outline_width,
                )
                outlined.append(replace(overlay, image=destination))
            effective_job = replace(job, overlays=tuple(outlined))

        command = build_ffmpeg_command(effective_job, info, source_volume, music_volume)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        assert process.stdout is not None
        log_tail: deque[str] = deque(maxlen=30)
        for line in process.stdout:
            log_tail.append(line.strip())
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and progress:
                try:
                    progress(min(1.0, int(value) / 1_000_000 / info.duration))
                except ValueError:
                    pass
        return_code = process.wait()
        if return_code != 0:
            job.output.unlink(missing_ok=True)
            lines = [line for line in log_tail if line]
            raise MediaError(lines[-1] if lines else f"FFmpeg 处理失败（代码 {return_code}）")
    if progress:
        progress(1.0)
