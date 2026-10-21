"""Forensic video and audio analysis service for video-to-H3 reverse engineering.

Faithfully implements the forensic inspection pipeline from D:\\video-to-h3-prompt:
- Probe metadata (duration, width, height, fps, codec, audio stream)
- Sparse frame extraction & 4x4 contact sheet generation
- Audio WAV extraction (22050 Hz mono)
- Spectrogram generation
- 0.5s RMS energy envelope and band energy distribution
- Spectral flux note onset and card-point detection (graded S / H / .)
- Tempo and rhythm credibility assessment (fixed tempo vs free-tempo rubato)
"""

from __future__ import annotations

import asyncio
import csv
import logging
import math
from pathlib import Path
from typing import Any, Optional
import wave

import numpy as np

try:
    from scipy.io import wavfile
    from scipy.signal import find_peaks, stft

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from . import ffmpeg

log = logging.getLogger("easyaivideo.forensic")


class ForensicAnalysisResult:
    def __init__(
        self,
        duration: float,
        width: int,
        height: int,
        fps: float,
        has_audio: bool,
        frame_paths: list[Path],
        grid_paths: list[Path],
        audio_path: Optional[Path],
        spectrum_path: Optional[Path],
        rms_envelope: list[tuple[float, float]],
        band_energies: dict[str, float],
        onsets: list[dict[str, Any]],
        estimated_tempo: Optional[float],
        tempo_stable: bool,
        summary_text: str,
        transitions: Optional[list["Transition"]] = None,
        breath_gaps: Optional[list[tuple[float, float]]] = None,
        pitch_hz: Optional[float] = None,
        onset_cv: Optional[float] = None,
        has_bgm: bool = False,
        source_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.duration = duration
        self.width = width
        self.height = height
        self.fps = fps
        self.has_audio = has_audio
        self.frame_paths = frame_paths
        self.grid_paths = grid_paths
        self.audio_path = audio_path
        self.spectrum_path = spectrum_path
        self.rms_envelope = rms_envelope
        self.band_energies = band_energies
        self.onsets = onsets
        self.estimated_tempo = estimated_tempo
        self.tempo_stable = tempo_stable
        self.summary_text = summary_text
        self.transitions = transitions or []
        self.breath_gaps = breath_gaps or []
        self.pitch_hz = pitch_hz
        self.onset_cv = onset_cv
        self.has_bgm = has_bgm
        self.source_path = source_path
        self.output_dir = output_dir


def load_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file into a normalized 1D float array and sample rate."""
    w = wave.open(str(path), "rb")
    sr = w.getframerate()
    n = w.getnframes()
    width = w.getsampwidth()
    ch = w.getnchannels()
    raw = w.readframes(n)
    w.close()

    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(width, np.int16)
    x = np.frombuffer(raw, dtype=dtype).astype(float) / float(np.iinfo(dtype).max or 1)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def compute_rms_envelope(x: np.ndarray, sr: int, hop_sec: float = 0.5) -> list[tuple[float, float]]:
    """Compute RMS energy envelope over 0.5s windows."""
    hop = int(sr * hop_sec)
    res: list[tuple[float, float]] = []
    for i in range(0, len(x), hop):
        chunk = x[i : i + hop]
        if len(chunk) > 0:
            rms_val = float(np.sqrt((chunk**2).mean()))
            res.append((round(i / sr, 2), round(rms_val, 4)))
    return res


def compute_band_energy(x: np.ndarray, sr: int) -> dict[str, float]:
    """Compute average spectral energy across low, mid, and high frequency bands."""
    if len(x) == 0:
        return {"low": 0.0, "mid": 0.0, "hi": 0.0}
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    out: dict[str, float] = {}
    for lo, hi, name in [(0, 250, "low"), (250, 2000, "mid"), (2000, sr // 2, "hi")]:
        m = (freqs >= lo) & (freqs < hi)
        out[name] = round(float(spec[m].mean()), 3) if m.any() else 0.0
    return out


def detect_onsets(
    y: np.ndarray,
    sr: int,
    min_spacing: float = 0.055,
    strong_q: float = 0.85,
    hard_q: float = 0.70,
    prom: float = 0.02,
) -> tuple[list[dict[str, Any]], Optional[float], bool]:
    """Detect attack onsets and estimate tempo from high-frequency weighted spectral flux."""
    if not HAS_SCIPY or len(y) < 1024:
        return [], None, False

    nper = 1024
    hop = 256
    f, _t, Z = stft(y, fs=sr, nperseg=nper, noverlap=nper - hop)
    mag = np.abs(Z)
    weight = 1.0 + 0.6 * (f / (sr / 2.0))
    flux = np.zeros(mag.shape[1])
    for k in range(1, mag.shape[1]):
        d = mag[:, k] - mag[:, k - 1]
        d[d < 0] = 0
        flux[k] = (d * weight).sum()

    if flux.max() > 0:
        flux /= flux.max()
    flux = np.convolve(flux, np.ones(3) / 3.0, mode="same")
    fps = sr / hop

    dist = max(1, int(min_spacing * fps))
    med = float(np.median(flux))
    sd = float(np.std(flux))
    pk, props = find_peaks(flux, height=med + 0.55 * sd, distance=dist, prominence=prom)

    if len(pk) == 0:
        return [], None, False

    times = pk / fps
    strength = props["peak_heights"]
    strong_cut = float(np.quantile(strength, strong_q))
    hard_cut = float(np.quantile(strength, hard_q))

    onsets_list: list[dict[str, Any]] = []
    for t_val, s_val in zip(times, strength):
        g = "S" if s_val >= strong_cut else ("H" if s_val >= hard_cut else ".")
        onsets_list.append({
            "time": round(float(t_val), 3),
            "strength": round(float(s_val), 4),
            "grade": g,
        })

    # Estimate tempo via autocorrelation
    tempo: Optional[float] = None
    tempo_stable = False
    try:
        x_centered = flux - flux.mean()
        ac = np.correlate(x_centered, x_centered, "full")[len(x_centered) - 1 :]
        a, b = int(0.28 * fps), int(1.1 * fps)
        if b < len(ac):
            lag = a + int(np.argmax(ac[a:b]))
            if lag > 0:
                tempo = round(60.0 / (lag / fps), 1)
                # Check variance of inter-onset intervals for strong/hard onsets
                sh_times = [o["time"] for o in onsets_list if o["grade"] in ("S", "H")]
                if len(sh_times) >= 4:
                    diffs = np.diff(sh_times)
                    mean_d = float(np.mean(diffs))
                    std_d = float(np.std(diffs))
                    if mean_d > 0 and (std_d / mean_d) < 0.65:
                        tempo_stable = True
    except Exception as exc:
        log.warning("Tempo estimation error: %s", exc)

    return onsets_list, tempo, tempo_stable



# ---------------------------------------------------------------------------
# Shot transitions, breath gaps, pitch, BGM verdict and long-clip segmentation
# (the evidence channels of the video-to-h3-prompt skill, steps 2-4 and 9)
# ---------------------------------------------------------------------------


class Transition:
    """A detected shot change. kind = "cut" (hard cut) or "soft" (dissolve / morph candidate)."""

    def __init__(self, time: float, kind: str, score: float, start: Optional[float] = None, end: Optional[float] = None) -> None:
        self.time = round(float(time), 3)
        self.kind = kind
        self.score = round(float(score), 3)
        self.start = round(float(start if start is not None else time), 3)
        self.end = round(float(end if end is not None else time), 3)

    def to_dict(self) -> dict[str, Any]:
        return {"time": self.time, "kind": self.kind, "score": self.score, "start": self.start, "end": self.end}

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Transition({self.kind}@{self.time}, {self.score})"


class SegmentPlan:
    """One <=15 s generation unit cut from the source (global source seconds)."""

    def __init__(self, index: int, start: float, end: float, reason: str = "") -> None:
        self.index = index
        self.start = round(float(start), 3)
        self.end = round(float(end), 3)
        self.reason = reason

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "start": self.start, "end": self.end, "duration": self.duration, "reason": self.reason}


def parse_scene_scores(text: str) -> tuple[list[float], list[float]]:
    """Parse ffmpeg ``metadata=print`` output into (pts_time list, scene_score list)."""
    times: list[float] = []
    scores: list[float] = []
    pending: Optional[float] = None
    for line in text.splitlines():
        if "pts_time:" in line:
            try:
                pending = float(line.split("pts_time:", 1)[1].split()[0])
            except (ValueError, IndexError):
                pending = None
        elif "scene_score=" in line and pending is not None:
            try:
                scores.append(float(line.split("scene_score=", 1)[1].strip()))
                times.append(pending)
            except ValueError:
                pass
            pending = None
    return times, scores


def detect_transitions(
    times: list[float],
    scores: list[float],
    *,
    cut_threshold: float = 0.25,
    soft_window: float = 0.5,
    soft_threshold: float = 0.035,
    soft_peak: float = 0.06,
    min_gap: float = 0.4,
) -> list[Transition]:
    """Hard cuts = single-frame scene-score spikes; soft = sustained elevated windows (dissolves/morphs).

    Soft transitions are *candidates*: in AI-generated footage fast in-shot motion can look similar,
    so they must be confirmed on the dense timecoded sheets.
    """
    if not times or len(times) != len(scores):
        return []
    t = np.asarray(times, dtype=float)
    s = np.asarray(scores, dtype=float)
    out: list[Transition] = []

    for i in np.where(s >= cut_threshold)[0]:
        if t[i] < 0.15:  # first frame always scores high
            continue
        if out and t[i] - out[-1].time < min_gap:
            if s[i] > out[-1].score:
                out[-1] = Transition(t[i], "cut", s[i])
            continue
        out.append(Transition(t[i], "cut", s[i]))

    if len(t) > 3:
        dt = float(np.median(np.diff(t))) or 1 / 24
        win = max(3, int(round(soft_window / dt)))
        smooth = np.convolve(s, np.ones(win) / win, mode="same")
        inside = False
        st = 0
        for i, v in enumerate(smooth):
            if v > soft_threshold and not inside:
                inside, st = True, i
            elif (v <= soft_threshold or i == len(smooth) - 1) and inside:
                inside = False
                seg = s[st : i + 1]
                pk = int(np.argmax(seg)) + st
                if s[pk] < soft_peak or t[pk] < 0.3:
                    continue
                if any(abs(c.time - t[pk]) < 0.6 for c in out):
                    continue
                out.append(Transition(t[pk], "soft", s[pk], t[st], t[i]))
    out.sort(key=lambda x: x.time)
    return out



def color_histograms(frames: np.ndarray) -> np.ndarray:
    """(n, h, w, 3) uint8 RGB frames -> (n, 512) normalised 8x8x8 colour histograms."""
    if frames.size == 0:
        return np.zeros((0, 512))
    q = (frames.astype(np.int32) // 32).reshape(len(frames), -1, 3)
    idx = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    out = np.zeros((len(frames), 512))
    for i in range(len(frames)):
        h = np.bincount(idx[i], minlength=512).astype(float)
        out[i] = h / max(1.0, h.sum())
    return out


def detect_soft_transitions(
    hists: np.ndarray,
    fps: float,
    cuts: list[float],
    *,
    span: float = 0.5,
    height: float = 0.25,
    prominence: float = 0.12,
    cut_guard: float = 0.6,
) -> list[Transition]:
    """Dissolve / morph candidates: the colour content 0.5 s before vs 0.5 s after differs strongly.

    Colour histograms ignore motion inside a shot but react to a change of scene, so this catches
    cross-dissolves that per-frame scene scores miss. Peaks near hard cuts are dropped.
    """
    n = len(hists)
    k = max(1, int(round(span * fps)))
    if n < 2 * k + 3:
        return []
    d = np.zeros(n)
    for i in range(k, n - k):
        d[i] = 1.0 - float(np.minimum(hists[i - k], hists[i + k]).sum())
    if not HAS_SCIPY:
        return []
    pk, _ = find_peaks(d, height=height, distance=max(1, int(0.75 * fps)), prominence=prominence)
    out: list[Transition] = []
    for p in pk:
        lo, hi = max(1, p - k - 1), min(n - 1, p + k + 1)
        fine = [1.0 - float(np.minimum(hists[i - 1], hists[i + 1]).sum()) if 0 < i < n - 1 else 0.0 for i in range(lo, hi)]
        centre = lo + int(np.argmax(fine)) if fine else p
        t = centre / fps
        if any(abs(t - c) <= cut_guard for c in cuts):
            continue
        out.append(Transition(t, "soft", d[p], max(0.0, t - span / 2), t + span / 2))
    return out


def detect_breath_gaps(
    x: np.ndarray, sr: int, *, hop_sec: float = 0.02, min_len: float = 0.2, rel: float = 0.18, floor: float = 0.006
) -> list[tuple[float, float]]:
    """Low-energy runs (>= min_len) in the audio: narration breaths / phrase gaps / silence."""
    if len(x) == 0 or sr <= 0:
        return []
    hop = max(1, int(sr * hop_sec))
    n = len(x) // hop
    if n == 0:
        return []
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames**2).mean(axis=1))
    active = rms[rms > 1e-4]
    if active.size == 0:
        return [(0.0, round(len(x) / sr, 2))]
    thr = max(floor, rel * float(np.median(active)))
    gaps: list[tuple[float, float]] = []
    start: Optional[int] = None
    for i, v in enumerate(rms):
        if v < thr and start is None:
            start = i
        elif v >= thr and start is not None:
            if (i - start) * hop_sec >= min_len:
                gaps.append((round(start * hop_sec, 2), round(i * hop_sec, 2)))
            start = None
    if start is not None and (n - start) * hop_sec >= min_len:
        gaps.append((round(start * hop_sec, 2), round(n * hop_sec, 2)))
    return gaps


def estimate_pitch(x: np.ndarray, sr: int) -> Optional[float]:
    """Median voiced F0 (autocorrelation, 70-400 Hz). ~85-180 Hz male, ~165-300 Hz female speech."""
    if len(x) < sr // 2:
        return None
    fr = int(0.04 * sr)
    hop = int(0.02 * sr)
    gate = 0.5 * float(np.sqrt((x**2).mean()))
    lo, hi = int(sr / 400), int(sr / 70)
    vals: list[float] = []
    step = max(1, (len(x) // hop) // 1500)  # cap work on long files
    for i in range(0, len(x) - fr, hop * step):
        c = x[i : i + fr]
        if float(np.sqrt((c**2).mean())) < gate:
            continue
        c = c - c.mean()
        ac = np.correlate(c, c, "full")[fr - 1 :]
        if ac[0] <= 0 or hi >= len(ac):
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.5 * ac[0]:
            vals.append(sr / lag)
    return round(float(np.median(vals)), 1) if len(vals) >= 20 else None


def onset_regularity(onsets: list[dict[str, Any]]) -> Optional[float]:
    """Coefficient of variation of strong/hard onset intervals (>= 0.8 => irregular, no beat grid)."""
    ts = [o["time"] for o in onsets if o.get("grade") in ("S", "H")]
    if len(ts) < 4:
        return None
    d = np.diff(ts)
    m = float(np.mean(d))
    return round(float(np.std(d)) / m, 2) if m > 0 else None


def plan_segments(
    duration: float,
    breath_gaps: list[tuple[float, float]],
    transitions: list[Transition],
    *,
    max_len: float = 15.0,
    min_len: float = 4.0,
    min_tail: float = 4.0,
    length_weight: float = 2.0,
    coincide: float = 0.35,
) -> list[SegmentPlan]:
    """Split a long clip into <= max_len generation segments at "breathing points".

    Candidate cut points: breath-gap midpoints (weight 2), hard cuts (2) / soft transitions (1);
    a breath gap that coincides with a shot transition scores 3. Within each window the score is
    weight + length_weight * (segment length / max_len), so longer segments win ties and we never
    cut in the middle of a phrase when a gap is available.
    """
    duration = float(duration)
    if duration <= max_len + 1e-6:
        return [SegmentPlan(0, 0.0, duration, "whole clip")]

    cands: list[tuple[float, float, str]] = []
    for a, b in breath_gaps:
        mid = (a + b) / 2.0
        w, why = 2.0, "breath"
        for tr in transitions:
            if a - coincide <= tr.time <= b + coincide:
                w, why = 3.0, f"breath+{tr.kind}"
                break
        cands.append((mid, w, why))
    for tr in transitions:
        if not any(abs(tr.time - c[0]) <= coincide for c in cands):
            cands.append((tr.time, 2.0 if tr.kind == "cut" else 1.0, tr.kind))
    cands.sort()

    plans: list[SegmentPlan] = []
    start = 0.0
    while duration - start > max_len + 1e-6:
        lo, hi = start + min_len, min(start + max_len, duration - min_tail)
        best: Optional[tuple[float, float, str]] = None
        best_score = -1.0
        for t, w, why in cands:
            if lo <= t <= hi:
                sc = w + length_weight * (t - start) / max_len
                if sc > best_score:
                    best, best_score = (t, w, why), sc
        if best is None:
            cut = min(start + max_len, duration - min_tail) if duration - start > max_len + min_tail else (start + duration) / 2
            plans.append(SegmentPlan(len(plans), start, cut, "fallback"))
            start = cut
        else:
            plans.append(SegmentPlan(len(plans), start, best[0], best[2]))
            start = best[0]
    plans.append(SegmentPlan(len(plans), start, duration, "end"))
    return plans


def localize(values: list[float], start: float, end: float) -> list[float]:
    """Global source seconds -> segment-local seconds (only values inside [start, end])."""
    return [round(v - start, 2) for v in values if start <= v <= end]


def build_timecoded_sheet(frames: list[tuple[Path, float, float]], out: Path, *, cols: int = 4, thumb_w: int = 270) -> Optional[Path]:
    """Tile frames into a contact sheet, each labelled with its segment-local and source time.

    ``frames`` is a list of (image path, local seconds, global seconds).
    """
    from PIL import Image, ImageDraw

    from .fonts import load_font

    items = [(p, lt, gt) for p, lt, gt in frames if p.is_file()]
    if not items:
        return None
    with Image.open(items[0][0]) as im0:
        w0, h0 = im0.size
    th = max(1, int(thumb_w * h0 / max(1, w0)))
    rows = (len(items) + cols - 1) // cols
    pad = 4
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (th + pad) + pad), (255, 214, 0))
    font = load_font(22)
    small = load_font(14)
    for k, (p, lt, gt) in enumerate(items):
        with Image.open(p) as im:
            tile = im.convert("RGB").resize((thumb_w, th))
        d = ImageDraw.Draw(tile)
        d.rectangle([0, 0, 118, 46], fill=(0, 0, 0))
        d.text((5, 2), f"{lt:05.2f}", fill=(255, 235, 0), font=font)
        d.text((5, 27), f"src {gt:.2f}", fill=(220, 220, 220), font=small)
        x = pad + (k % cols) * (thumb_w + pad)
        y = pad + (k // cols) * (th + pad)
        sheet.paste(tile, (x, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


class ForensicService:
    """Forensic extractor that mirrors the D:\\video-to-h3-prompt forensic methodology."""

    async def run_probe(self, video_path: Path, output_dir: Path) -> ForensicAnalysisResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        # 1. ffprobe basic info
        duration = await ffmpeg.probe_duration(video_path)
        width, height = await ffmpeg.probe_dimensions(video_path)

        # Probe fps and audio stream existence via ffprobe command
        ffprobe_bin = ffmpeg.ffprobe_bin()
        ffmpeg_bin = ffmpeg.ffmpeg_bin()

        fps = 30.0
        has_audio = False

        probe_cmd = [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(video_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            txt = stdout.decode("utf-8", errors="replace")
            (output_dir / "probe.txt").write_text(txt, encoding="utf-8")
            if "codec_type=audio" in txt:
                has_audio = True
            for line in txt.splitlines():
                if line.startswith("r_frame_rate="):
                    val = line.split("=", 1)[1].strip()
                    if "/" in val:
                        num, den = val.split("/", 1)
                        if float(den) > 0:
                            fps = round(float(num) / float(den), 2)
                    elif val:
                        fps = round(float(val), 2)
                    break
        except Exception as exc:
            log.warning("Failed to run deep ffprobe: %s", exc)

        # 2. Extract sparse frames at 2fps
        frame_pattern = frames_dir / "f_%03d.jpg"
        extract_frames_cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            "fps=2,scale=480:-1",
            str(frame_pattern),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *extract_frames_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except Exception as exc:
            log.warning("Sparse frame extraction failed: %s", exc)

        extracted_frames = sorted(frames_dir.glob("f_*.jpg"))

        # 3. Build 4x4 contact sheets with yellow padding (mirroring forensic_probe.ps1)
        grid_paths: list[Path] = []
        if extracted_frames:
            grid_pattern = output_dir / "grid_%03d.jpg"
            contact_cmd = [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-framerate",
                "1",
                "-i",
                str(frame_pattern),
                "-vf",
                "scale=240:-2,tile=4x4:padding=4:color=yellow",
                str(grid_pattern),
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *contact_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                grid_paths = sorted(output_dir.glob("grid_*.jpg"))
            except Exception as exc:
                log.warning("Contact sheet creation failed: %s", exc)

        # 4. Audio extraction, Spectrogram, RMS envelope & Onset Detection
        audio_path: Optional[Path] = None
        spectrum_path: Optional[Path] = None
        rms_env: list[tuple[float, float]] = []
        band_e: dict[str, float] = {}
        onsets: list[dict[str, Any]] = []
        tempo: Optional[float] = None
        tempo_stable = False
        breath_gaps: list[tuple[float, float]] = []
        pitch_hz: Optional[float] = None

        if has_audio:
            wav_file = output_dir / "audio.wav"
            extract_audio_cmd = [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "22050",
                str(wav_file),
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *extract_audio_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if wav_file.is_file():
                    audio_path = wav_file

                    # Generate spectrogram
                    spec_file = output_dir / "spectrum.jpg"
                    spec_cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-v",
                        "error",
                        "-i",
                        str(wav_file),
                        "-lavfi",
                        "showspectrumpic=s=1000x400:legend=1",
                        str(spec_file),
                    ]
                    proc_spec = await asyncio.create_subprocess_exec(
                        *spec_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc_spec.communicate()
                    if spec_file.is_file():
                        spectrum_path = spec_file

                    # Compute RMS & Band Energy
                    audio_arr, sr = load_wav_mono(wav_file)
                    rms_env = compute_rms_envelope(audio_arr, sr, hop_sec=0.5)
                    band_e = compute_band_energy(audio_arr, sr)

                    # Onset detection
                    onsets, tempo, tempo_stable = detect_onsets(audio_arr, sr)
                    breath_gaps = detect_breath_gaps(audio_arr, sr)
                    pitch_hz = estimate_pitch(audio_arr, sr)

                    # Save audio stats and onsets to disk
                    stats_text = [
                        f"Sample Rate: {sr} Hz, Duration: {len(audio_arr) / sr:.2f}s",
                        f"Band Energy: Low={band_e.get('low', 0)}, Mid={band_e.get('mid', 0)}, High={band_e.get('hi', 0)}",
                        f"Estimated Tempo: {tempo or 'N/A'} BPM (Stable: {tempo_stable})",
                        "\n-- 0.5s RMS Envelope --",
                    ]
                    for t, v in rms_env:
                        bar = "#" * int(min(v * 80, 50))
                        stats_text.append(f"{t:5.1f}s: {v:.4f} {bar}")
                    (output_dir / "audio_stats.txt").write_text("\n".join(stats_text), encoding="utf-8")

                    onsets_txt_lines = [
                        f"Total Onsets: {len(onsets)}, Estimated BPM: {tempo or 'N/A'} (Stable: {tempo_stable})",
                        "Time (s)\tStrength\tGrade (S=Strong, H=Hard)",
                    ]
                    for o in onsets:
                        if o["grade"] in ("S", "H"):
                            onsets_txt_lines.append(f"{o['time']:7.3f}\t{o['strength']:.4f}\t{o['grade']}")
                    (output_dir / "onsets.txt").write_text("\n".join(onsets_txt_lines), encoding="utf-8")

                    # Write CSV
                    with (output_dir / "onsets.csv").open("w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=["time", "strength", "grade"])
                        writer.writeheader()
                        writer.writerows(onsets)

            except Exception as exc:
                log.warning("Audio forensic processing failed: %s", exc)

        # 5. Shot transitions (hard cuts / dissolve candidates) from per-frame scene scores
        transitions: list[Transition] = []
        try:
            times, scores = await self.scene_scores(video_path)
            cuts_only = [t for t in detect_transitions(times, scores) if t.kind == "cut"]
            try:
                hists = color_histograms(await self.small_frames(video_path, fps=8.0))
                softs = detect_soft_transitions(hists, 8.0, [c.time for c in cuts_only])
            except Exception as exc:
                log.warning("Histogram dissolve detection failed, using scene-score windows: %s", exc)
                softs = [t for t in detect_transitions(times, scores) if t.kind == "soft"]
            transitions = sorted(cuts_only + softs, key=lambda x: x.time)
            (output_dir / "transitions.txt").write_text(
                "\n".join(f"{t.time:7.3f}\t{t.kind}\t{t.score:.3f}\t{t.start:.2f}-{t.end:.2f}" for t in transitions),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Scene transition detection failed: %s", exc)

        # 6. Cross-validated sound verdict: a fixed BPM needs a stable tempo AND regular onsets
        onset_cv = onset_regularity(onsets)
        has_bgm = bool(has_audio and tempo_stable and onset_cv is not None and onset_cv < 0.8)
        if breath_gaps:
            (output_dir / "breath_gaps.txt").write_text("\n".join(f"{a:.2f}-{b:.2f}" for a, b in breath_gaps), encoding="utf-8")

        summary_text = self.compose_summary(
            duration=duration, width=width, height=height, fps=fps, n_frames=len(extracted_frames), has_audio=has_audio,
            tempo=tempo, has_bgm=has_bgm, onset_cv=onset_cv, band_e=band_e, rms_env=rms_env, onsets=onsets,
            transitions=transitions, breath_gaps=breath_gaps, pitch_hz=pitch_hz,
        )
        (output_dir / "dossier.txt").write_text(summary_text, encoding="utf-8")

        return ForensicAnalysisResult(
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            has_audio=has_audio,
            frame_paths=extracted_frames,
            grid_paths=grid_paths,
            audio_path=audio_path,
            spectrum_path=spectrum_path,
            rms_envelope=rms_env,
            band_energies=band_e,
            onsets=onsets,
            estimated_tempo=tempo,
            tempo_stable=tempo_stable,
            summary_text=summary_text,
            transitions=transitions,
            breath_gaps=breath_gaps,
            pitch_hz=pitch_hz,
            onset_cv=onset_cv,
            has_bgm=has_bgm,
            source_path=video_path,
            output_dir=output_dir,
        )

    # ------------------------------------------------------------ helpers
    @staticmethod
    def compose_summary(
        *,
        duration: float,
        width: int,
        height: int,
        fps: float,
        n_frames: int,
        has_audio: bool,
        tempo: Optional[float],
        has_bgm: bool,
        onset_cv: Optional[float],
        band_e: dict[str, float],
        rms_env: list[tuple[float, float]],
        onsets: list[dict[str, Any]],
        transitions: list[Transition],
        breath_gaps: list[tuple[float, float]],
        pitch_hz: Optional[float],
        offset: float = 0.0,
        end: Optional[float] = None,
    ) -> str:
        """Human/LLM readable dossier. With offset/end every time is converted to segment-local seconds."""
        end = duration if end is None else end

        def inside(t: float) -> bool:
            return offset - 1e-6 <= t <= end + 1e-6

        def loc(t: float) -> float:
            return round(t - offset, 2)

        local = offset > 0 or end < duration - 1e-6
        lines = [
            "=== FORENSIC DOSSIER ===",
            f"- Source: {duration:.2f}s, {width}x{height}, {fps} fps, {n_frames} sparse frames (2 fps)",
        ]
        if local:
            lines.append(
                f"- THIS SEGMENT covers source {offset:.2f}-{end:.2f}s ({end - offset:.2f}s). "
                f"ALL times below are SEGMENT-LOCAL (00:00 = source {offset:.2f}s)."
            )
        cuts = [t for t in transitions if t.kind == "cut" and inside(t.time)]
        softs = [t for t in transitions if t.kind == "soft" and inside(t.time)]
        lines.append("- Hard cuts: " + (", ".join(f"{loc(t.time):.2f}s" for t in cuts) or "none"))
        lines.append(
            "- Soft transition candidates (dissolve / morph, VERIFY on the timecoded sheets): "
            + (", ".join(f"{loc(t.time):.2f}s ({loc(t.start):.2f}-{loc(t.end):.2f})" for t in softs) or "none")
        )
        if not has_audio:
            lines.append("- Audio: NO audio track -> overall_soundscape silent, non_diegetic_music: N/A (explicit silence).")
            return "\n".join(lines)

        voice = ""
        if pitch_hz:
            voice = " (likely female voice)" if pitch_hz >= 165 else " (likely male voice)"
        gaps = [(a, b) for a, b in breath_gaps if inside((a + b) / 2)]
        sh = [o for o in onsets if o.get("grade") in ("S", "H") and inside(o["time"])]
        peaks = sorted([p for p in rms_env if inside(p[0])], key=lambda x: x[1], reverse=True)[:6]
        if has_bgm:
            rhythm = f"- Rhythm verdict: FIXED TEMPO ~{tempo} BPM (onset CV {onset_cv})"
        else:
            rhythm = (
                f"- Rhythm verdict: NO stable beat grid (onset CV {onset_cv}; autocorrelation BPM {tempo} is a FALSE DETECTION). "
                "Treat as narration / diegetic sound; NEVER write a BPM; non_diegetic_music: N/A unless music is clearly audible."
            )
        lines += [
            f"- Band energy: low={band_e.get('low', 0)}, mid={band_e.get('mid', 0)}, hi={band_e.get('hi', 0)}",
            f"- Median voiced pitch: {pitch_hz or 'n/a'} Hz{voice}",
            rhythm,
            "- Breath gaps / phrase pauses: " + (", ".join(f"{loc(a):.2f}-{loc(b):.2f}" for a, b in gaps) or "none"),
            "- Strong(S)/Hard(H) onsets (card-point candidates): "
            + (", ".join(f"{loc(o['time']):.2f}{o['grade']}" for o in sh[:40]) or "none"),
            "- 0.5s RMS peaks: " + (", ".join(f"{loc(t):.1f}s({v:.2f})" for t, v in sorted(peaks)) or "none"),
            "- Reconciliation rule: every cut / impact / state change should land on an S/H onset or a breath gap; "
            "cuts that land in breath gaps mean the edit follows the narration, not music.",
        ]
        return "\n".join(lines)

    async def scene_scores(self, video_path: Path) -> tuple[list[float], list[float]]:
        txt = await ffmpeg._exec(
            ffmpeg.ffmpeg_bin(),
            [
                "-hide_banner", "-nostats", "-i", str(video_path), "-an",
                "-vf", "scale=160:-2,select='gte(scene,0)',metadata=print:file=-",
                "-f", "null", "-",
            ],
        )
        return parse_scene_scores(txt)

    async def small_frames(self, video_path: Path, *, fps: float = 8.0, w: int = 36, h: int = 64) -> np.ndarray:
        """Tiny RGB frames (n, h, w, 3) streamed from ffmpeg for histogram analysis."""
        proc = await asyncio.create_subprocess_exec(
            ffmpeg.ffmpeg_bin(), "-v", "error", "-i", str(video_path), "-an",
            "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        raw, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(err.decode(errors="replace")[-300:])
        frame = w * h * 3
        n = len(raw) // frame
        return np.frombuffer(raw[: n * frame], dtype=np.uint8).reshape(n, h, w, 3)

    async def extract_window_frames(
        self, video_path: Path, start: float, end: float, fps: float, out_dir: Path, *, width: int = 360, prefix: str = "w"
    ) -> list[tuple[Path, float, float]]:
        """Frames between start..end at ``fps``; returns (path, seconds from start, source seconds)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob(f"{prefix}_*.jpg"):
            old.unlink(missing_ok=True)
        dur = max(0.05, end - start)
        await ffmpeg.run([
            "-ss", f"{max(0.0, start):.3f}", "-t", f"{dur:.3f}", "-i", str(video_path),
            "-vf", f"fps={fps},scale={width}:-2", "-q:v", "4", str(out_dir / f"{prefix}_%04d.jpg"),
        ])
        files = sorted(out_dir.glob(f"{prefix}_*.jpg"))
        return [(f, round(i / fps, 2), round(start + i / fps, 2)) for i, f in enumerate(files)]

    async def cut_reference_media(
        self, video_path: Path, start: float, end: float, out_video: Path, out_audio: Optional[Path], *, short_edge: int = 720
    ) -> tuple[Path, Optional[Path]]:
        """H3 R2V reference clip (H.264/AAC, 2-15 s, <=50 MB, 24 fps) plus a mono 44.1 kHz WAV of the same range."""
        out_video.parent.mkdir(parents=True, exist_ok=True)
        dur = max(2.0, end - start)
        scale = f"scale='if(gt(iw,ih),-2,{short_edge})':'if(gt(iw,ih),{short_edge},-2)'"
        await ffmpeg.run([
            "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video_path),
            "-vf", scale, "-r", "24",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_video),
        ])
        audio_out: Optional[Path] = None
        if out_audio is not None:
            try:
                await ffmpeg.run([
                    "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(out_audio),
                ])
                audio_out = out_audio if out_audio.is_file() else None
            except Exception as exc:  # source without an audio stream
                log.info("No reference audio for %.2f-%.2f: %s", start, end, exc)
        return out_video, audio_out
