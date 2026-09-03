"""ffmpeg / ffprobe wrappers used by the renderer."""

from __future__ import annotations

import asyncio
import math
import shutil
from pathlib import Path
from typing import Optional

from ..config import config_manager


class FFmpegError(RuntimeError):
    pass


TimedOverlay = tuple[Path, float, float]  # (png path, start seconds, end seconds)


def ffmpeg_bin() -> str:
    custom = config_manager.get().render.ffmpeg_path
    if custom:
        return custom
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    custom = config_manager.get().render.ffmpeg_path
    if custom:
        probe = Path(custom).with_name("ffprobe" + Path(custom).suffix)
        if probe.exists():
            return str(probe)
    return shutil.which("ffprobe") or "ffprobe"


def available() -> bool:
    return shutil.which(ffmpeg_bin()) is not None or Path(ffmpeg_bin()).exists()


async def _exec(binary: str, args: list[str]) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError as exc:
        raise FFmpegError(f"{binary} not found. Install ffmpeg and make sure it is on PATH.") from exc
    try:
        out, err = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        raise
    if proc.returncode != 0:
        raise FFmpegError(f"{Path(binary).name} failed (exit {proc.returncode}):\n{err.decode(errors='replace')[-1500:]}")
    return out.decode(errors="replace")


async def run(args: list[str]) -> None:
    await _exec(ffmpeg_bin(), ["-hide_banner", "-loglevel", "error", "-y", *args])


async def probe_duration(path: Path) -> float:
    out = await _exec(
        ffprobe_bin(),
        ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
    )
    try:
        return float(out.strip().splitlines()[0])
    except (ValueError, IndexError) as exc:
        raise FFmpegError(f"Could not read duration of {path}") from exc


async def make_silence(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    await run(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-q:a", "9", str(path)])
    return path


async def concat_audio(files: list[Path], gap: float, output: Path) -> Path:
    """Join several audio files into one mp3, inserting `gap` seconds of silence after each."""
    if not files:
        raise FFmpegError("concat_audio needs at least one file")
    args: list[str] = []
    graph = ""
    for i, f in enumerate(files):
        args += ["-i", str(f)]
        graph += f"[{i}:a]aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur={gap:.3f}[a{i}];"
    graph += "".join(f"[a{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[a]"
    output.parent.mkdir(parents=True, exist_ok=True)
    await run([*args, "-filter_complex", graph, "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "4", str(output)])
    return output


def _kenburns_filter(index: int, width: int, height: int, fps: int, frames: int) -> str:
    n = max(frames, 2)
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    variants = [
        (f"1+0.15*on/{n}", center_x, center_y),  # zoom in
        (f"1.15-0.15*on/{n}", center_x, center_y),  # zoom out
        ("1.12", f"(iw-iw/zoom)*on/{n}", center_y),  # pan right
        ("1.12", center_x, f"(ih-ih/zoom)*on/{n}"),  # pan down
    ]
    z, x, y = variants[index % len(variants)]
    big_w, big_h = width * 2, height * 2
    return (
        f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={width}x{height}:fps={fps}"
    )


def _cover_filter(width: int, height: int, fps: int) -> str:
    return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}"


async def render_segment(
    *,
    output: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
    audio: Path,
    image: Optional[Path] = None,
    clip: Optional[Path] = None,
    overlay: Optional[Path] = None,
    timed_overlays: Optional[list[TimedOverlay]] = None,
    motion: str = "kenburns",
    scene_index: int = 0,
    crf: int = 23,
) -> Path:
    """Compose one scene: visual (image or clip) + static overlay + timed overlays + narration audio."""
    if clip is None and image is None:
        raise FFmpegError("render_segment needs an image or a clip")
    frames = int(math.ceil(duration * fps))
    args: list[str] = []
    if clip is not None:
        args += ["-stream_loop", "-1", "-i", str(clip)]
        visual = _cover_filter(width, height, fps)
    elif motion == "kenburns":
        args += ["-i", str(image)]
        visual = _kenburns_filter(scene_index, width, height, fps, frames)
    else:
        args += ["-loop", "1", "-framerate", str(fps), "-i", str(image)]
        visual = _cover_filter(width, height, fps)

    next_idx = 1
    graph = f"[0:v]{visual},format=yuv420p[v0];"
    current = "v0"
    step = 0
    if overlay is not None:
        args += ["-i", str(overlay)]
        step += 1
        graph += f"[{current}][{next_idx}:v]overlay=0:0:format=auto[v{step}];"
        current = f"v{step}"
        next_idx += 1
    for path, start, end in timed_overlays or []:
        args += ["-i", str(path)]
        step += 1
        graph += f"[{current}][{next_idx}:v]overlay=0:0:format=auto:enable='between(t,{start:.3f},{end:.3f})'[v{step}];"
        current = f"v{step}"
        next_idx += 1
    graph += f"[{current}]format=yuv420p[v];"
    args += ["-i", str(audio)]
    graph += f"[{next_idx}:a]apad,aresample=44100[a]"

    output.parent.mkdir(parents=True, exist_ok=True)
    await run(
        [
            *args,
            "-filter_complex", graph,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-r", str(fps), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-t", f"{duration:.3f}", "-movflags", "+faststart",
            str(output),
        ]
    )
    return output


async def concat(segments: list[Path], output: Path) -> Path:
    list_file = output.with_suffix(".txt")
    lines = []
    for seg in segments:
        escaped = seg.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    await run(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(output)])
    list_file.unlink(missing_ok=True)
    return output


async def mix_bgm(video: Path, bgm: Path, volume: float, duration: float, output: Path) -> Path:
    fade_out_start = max(duration - 2.5, 0.0)
    graph = (
        f"[1:a]volume={volume:.3f},afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out_start:.3f}:d=2.5[bg];"
        "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    )
    await run(
        [
            "-i", str(video), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}", "-movflags", "+faststart",
            str(output),
        ]
    )
    return output
