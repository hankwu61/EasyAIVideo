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


async def probe_dimensions(path: Path) -> tuple[int, int]:
    out = await _exec(
        ffprobe_bin(),
        ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)],
    )
    try:
        parts = out.strip().splitlines()[0].split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError) as exc:
        raise FFmpegError(f"Could not read dimensions of {path}") from exc


async def make_silence(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    await run(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-q:a", "9", str(path)])
    return path


async def extract_frame(video: Path, seconds: float, output: Path, width: int = 768) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    await run(["-ss", f"{max(seconds, 0):.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(output)])
    return output


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
    audio: Optional[Path] = None,
    image: Optional[Path] = None,
    end_image: Optional[Path] = None,
    clip: Optional[Path] = None,
    overlay: Optional[Path] = None,
    timed_overlays: Optional[list[TimedOverlay]] = None,
    motion: str = "kenburns",
    scene_index: int = 0,
    crf: int = 23,
    pre_pad: float = 0.0,
    post_pad: float = 0.0,
) -> Path:
    """Compose one scene: visual (image, end_image, or clip) + static overlay + timed overlays + narration audio."""
    if clip is None and image is None:
        raise FFmpegError("render_segment needs an image or a clip")
    frames = int(math.ceil(duration * fps))
    args: list[str] = []
    if clip is not None:
        args += ["-stream_loop", "-1", "-i", str(clip)]
        visual = _cover_filter(width, height, fps)
        graph = f"[0:v]{visual},format=yuv420p[v0];"
        next_idx = 1
    elif end_image is not None and end_image.is_file():
        trans_dur = min(1.5, max(0.5, duration * 0.4))
        offset = max(0.1, duration - trans_dur)
        args += [
            "-loop", "1", "-t", f"{duration:.3f}", "-framerate", str(fps), "-i", str(image),
            "-loop", "1", "-t", f"{duration:.3f}", "-framerate", str(fps), "-i", str(end_image),
        ]
        v0_cov = _cover_filter(width, height, fps)
        v1_cov = _cover_filter(width, height, fps)
        graph = (
            f"[0:v]{v0_cov},format=yuv420p[v_in0];"
            f"[1:v]{v1_cov},format=yuv420p[v_in1];"
            f"[v_in0][v_in1]xfade=transition=fade:duration={trans_dur:.2f}:offset={offset:.2f},format=yuv420p[v0];"
        )
        next_idx = 2
    elif motion == "kenburns":
        args += ["-i", str(image)]
        visual = _kenburns_filter(scene_index, width, height, fps, frames)
        graph = f"[0:v]{visual},format=yuv420p[v0];"
        next_idx = 1
    else:
        args += ["-loop", "1", "-framerate", str(fps), "-i", str(image)]
        visual = _cover_filter(width, height, fps)
        graph = f"[0:v]{visual},format=yuv420p[v0];"
        next_idx = 1
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
    if audio is not None and audio.is_file():
        args += ["-i", str(audio)]
        if pre_pad > 0 or post_pad > 0:
            pre_ms = int(pre_pad * 1000)
            graph += f"[{next_idx}:a]adelay={pre_ms}|{pre_ms},apad=pad_dur={post_pad:.3f},aresample=44100[a]"
        else:
            graph += f"[{next_idx}:a]apad,aresample=44100[a]"
    else:
        args += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        graph += f"[{next_idx}:a]aresample=44100[a]"

    v_args = ["-c:v", "libx264", "-preset", "veryfast"]
    if motion == "static":
        v_args += ["-tune", "stillimage"]
    v_args += ["-crf", str(crf), "-r", str(fps), "-pix_fmt", "yuv420p"]

    output.parent.mkdir(parents=True, exist_ok=True)
    await run(
        [
            *args,
            "-filter_complex", graph,
            "-map", "[v]", "-map", "[a]",
            *v_args,
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


async def concat_with_transitions(
    segments: list[Path],
    output: Path,
    transition: str = "none",
    duration: float = 0.5,
    crf: int = 18,
    fps: int = 30,
) -> Path:
    """Concatenate video segments with optional xfade and acrossfade transitions."""
    if not segments:
        raise FFmpegError("No segments to concatenate")
    if len(segments) == 1 or transition == "none":
        return await concat(segments, output)

    # Probe duration of each segment
    durs: list[float] = []
    for s in segments:
        d = await probe_duration(s)
        durs.append(d)

    min_dur = min(durs)
    eff_trans_dur = min(duration, min_dur / 2.0)
    if eff_trans_dur <= 0.05:
        return await concat(segments, output)

    inputs: list[str] = []
    for s in segments:
        inputs.extend(["-i", str(s)])

    v_filter_parts: list[str] = []
    a_filter_parts: list[str] = []

    last_v = "0:v"
    last_a = "0:a"
    cum_dur = durs[0]

    for i in range(1, len(segments)):
        offset = cum_dur - eff_trans_dur
        next_v = f"v{i}"
        next_a = f"a{i}"
        v_filter_parts.append(
            f"[{last_v}][{i}:v]xfade=transition={transition}:duration={eff_trans_dur:.3f}:offset={offset:.3f}[{next_v}]"
        )
        a_filter_parts.append(
            f"[{last_a}][{i}:a]acrossfade=d={eff_trans_dur:.3f}[{next_a}]"
        )
        last_v = next_v
        last_a = next_a
        cum_dur = offset + durs[i]

    filter_complex = ";".join(v_filter_parts + a_filter_parts)
    output.parent.mkdir(parents=True, exist_ok=True)
    await run([
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{last_v}]",
        "-map", f"[{last_a}]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-r", str(fps), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        str(output),
    ])
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


async def burn_subtitles(
    video: Path,
    srt_path: Path,
    output: Path,
    font_name: str | None = None,
    font_size: int = 20,
    primary_color: str = "&H00FFFFFF",  # ASS AABBGGRR format: white
    back_color: str = "&H80000000",
    border_style: int = 1,  # 1 = outline + drop shadow, 3 = opaque box
    outline: int = 2,
    outline_color: str = "&H00000000",
    alignment: int = 2,  # 2 = bottom-center, 8 = middle-center, 5 = top-center
    margin_v: int = 30,
    margin_l: int = 20,
    crf: int = 18,
) -> Path:
    """Burn subtitles into video using ffmpeg subtitles filter."""
    output.parent.mkdir(parents=True, exist_ok=True)
    # Windows path formatting for ffmpeg filter graph: D\:/path/to/file.srt
    escaped_srt = srt_path.resolve().as_posix().replace(":", "\\:").replace("'", "\\'")
    style_parts = [
        f"FontSize={font_size}",
        f"PrimaryColour={primary_color}",
        f"BackColour={back_color}",
        f"BorderStyle={border_style}",
        f"Outline={outline}",
        f"OutlineColour={outline_color}",
        f"Shadow=1",
        f"Alignment={alignment}",
        f"MarginV={margin_v}",
        f"MarginL={margin_l}",
        f"MarginR={margin_l}",
    ]
    if font_name and font_name.strip():
        # sanitize font name
        clean_font = font_name.strip().replace("'", "").replace(",", "")
        style_parts.insert(0, f"FontName='{clean_font}'")

    style = ",".join(style_parts)
    sub_filter = f"subtitles='{escaped_srt}':force_style='{style}'"

    await run([
        "-i", str(video),
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output),
    ])
    return output


async def trim_video(video: Path, start: float, end: float, output: Path) -> Path:
    """Trim video between start and end seconds."""
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end - start)
    await run([
        "-ss", f"{max(0.0, start):.3f}",
        "-i", str(video),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ])
    return output


async def extract_audio_peaks(
    media_path: Path,
    points_per_second: int = 30,
    max_total_points: int = 20000,
) -> dict[str, Any]:
    """Extract normalized audio PCM peaks from audio or video file using ffmpeg."""
    import array
    import json

    if not media_path.exists():
        return {"duration": 0.0, "sampleRate": points_per_second, "peaks": []}

    cache_path = media_path.parent / f".{media_path.stem}_waveform.json"
    try:
        if cache_path.exists() and cache_path.stat().st_mtime >= media_path.stat().st_mtime:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if "peaks" in data and len(data["peaks"]) > 0:
                return data
    except Exception:
        pass

    args = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(media_path),
        "-vn",
        "-ac", "1",
        "-ar", "4000",
        "-f", "f32le",
        "-",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        raw, _ = await proc.communicate()
    except Exception as exc:
        return {"duration": 0.0, "sampleRate": points_per_second, "peaks": [], "error": str(exc)}

    if not raw:
        return {"duration": 0.0, "sampleRate": points_per_second, "peaks": []}

    samples = array.array("f")
    samples.frombytes(raw)
    total_samples = len(samples)
    duration = total_samples / 4000.0
    if duration <= 0:
        return {"duration": 0.0, "sampleRate": points_per_second, "peaks": []}

    target_pts = min(max_total_points, max(50, int(duration * points_per_second)))
    block_sz = max(1, total_samples // target_pts)

    peaks: list[float] = []
    global_max = 0.001
    for i in range(target_pts):
        s = i * block_sz
        e = min(s + block_sz, total_samples)
        sub = samples[s:e]
        if not sub:
            peaks.append(0.0)
            continue
        p = max((abs(x) for x in sub), default=0.0)
        peaks.append(p)
        if p > global_max:
            global_max = p

    # Normalize so loudest peak reaches 0.95
    norm_factor = 0.95 / global_max
    norm_peaks = [round(min(1.0, max(0.01, p * norm_factor)), 3) for p in peaks]

    result = {
        "duration": round(duration, 3),
        "sampleRate": points_per_second,
        "peaks": norm_peaks,
    }

    try:
        cache_path.write_text(json.dumps(result), encoding="utf-8")
    except Exception:
        pass

    return result




async def has_audio_stream(path: Path) -> bool:
    out = await _exec(ffprobe_bin(), ["-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)])
    return bool(out.strip())


async def normalize_clip(video: Path, duration: float, width: int, height: int, fps: int, output: Path, *, crf: int = 18) -> Path:
    """Trim to ``duration`` and conform to WxH / fps / AAC stereo (adds silence when the clip has no audio).

    Used to make H3 outputs concat-safe: every part ends up with identical stream parameters.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
    )
    dur = f"{max(0.1, duration):.3f}"
    common_v = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    common_a = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
    if await has_audio_stream(video):
        await run(["-i", str(video), "-t", dur, "-vf", vf, *common_v, *common_a, "-movflags", "+faststart", str(output)])
    else:
        await run([
            "-i", str(video), "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", dur, "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, *common_v, *common_a, "-shortest",
            "-movflags", "+faststart", str(output),
        ])
    return output
