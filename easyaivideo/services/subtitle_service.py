"""Subtitle service for parsing, updating, splitting, and managing project SRT cues."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..models import Project
from ..services.slide_service import format_srt_timestamp


@dataclass
class SubtitleCue:
    id: int
    start: float  # seconds
    end: float  # seconds
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_srt_time(time_str: str) -> float:
    """Parse '00:01:23,456' or '00:01:23.456' into seconds."""
    time_str = time_str.strip().replace(".", ",")
    m = re.match(r"(\d+):(\d+):(\d+)(?:,(\d+))?", time_str)
    if not m:
        return 0.0
    hrs = int(m.group(1))
    mins = int(m.group(2))
    secs = int(m.group(3))
    ms_str = (m.group(4) or "0").ljust(3, "0")[:3]
    ms = int(ms_str)
    return hrs * 3600 + mins * 60 + secs + ms / 1000.0


def parse_srt_content(content: str) -> list[SubtitleCue]:
    """Parse raw SRT content into a list of SubtitleCue."""
    if not content or not content.strip():
        return []

    cues: list[SubtitleCue] = []
    # Normalize newlines
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    # Blocks separated by double newline
    blocks = re.split(r"\n\s*\n", normalized.strip())

    for idx, block in enumerate(blocks, 1):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        time_line_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                time_line_idx = i
                break

        if time_line_idx == -1:
            continue

        time_line = lines[time_line_idx]
        parts = time_line.split("-->")
        if len(parts) != 2:
            continue

        start = parse_srt_time(parts[0])
        end = parse_srt_time(parts[1])
        text_lines = lines[time_line_idx + 1 :]
        text = " ".join(text_lines).strip()

        # Try to parse index from preceding line
        cue_id = idx
        if time_line_idx > 0:
            try:
                cue_id = int(lines[time_line_idx - 1])
            except ValueError:
                cue_id = idx

        if text:
            cues.append(SubtitleCue(id=cue_id, start=round(start, 3), end=round(end, 3), text=text))

    return cues


def serialize_cues_to_srt(cues: list[SubtitleCue]) -> str:
    """Format a list of SubtitleCue into standard SRT file content."""
    # Ensure ordered by start time
    sorted_cues = sorted(cues, key=lambda c: (c.start, c.end))
    blocks = []
    for i, cue in enumerate(sorted_cues, 1):
        start_ts = format_srt_timestamp(max(0.0, cue.start))
        end_ts = format_srt_timestamp(max(cue.start + 0.1, cue.end))
        blocks.append(f"{i}\n{start_ts} --> {end_ts}\n{cue.text.strip()}")

    return "\n\n".join(blocks) + "\n"


def split_cue(cues: list[SubtitleCue], cue_id: int, split_time: float) -> list[SubtitleCue]:
    """Split a single cue into two at split_time."""
    result: list[SubtitleCue] = []
    for cue in cues:
        if cue.id == cue_id and cue.start < split_time < cue.end:
            # Proportionally estimate text split
            ratio = (split_time - cue.start) / max(cue.end - cue.start, 0.001)
            chars = list(cue.text.strip())
            cut_idx = max(1, min(len(chars) - 1, int(len(chars) * ratio)))

            part1_text = "".join(chars[:cut_idx]).strip()
            part2_text = "".join(chars[cut_idx:]).strip()

            result.append(SubtitleCue(id=cue.id, start=cue.start, end=split_time, text=part1_text))
            result.append(SubtitleCue(id=cue.id + 1000, start=split_time, end=cue.end, text=part2_text))
        else:
            result.append(cue)

    # Re-index
    for i, c in enumerate(result, 1):
        c.id = i
    return result


def merge_cues(cues: list[SubtitleCue], cue_id1: int, cue_id2: int) -> list[SubtitleCue]:
    """Merge two adjacent cues into one."""
    sorted_cues = sorted(cues, key=lambda c: c.start)
    c1 = next((c for c in sorted_cues if c.id == cue_id1), None)
    c2 = next((c for c in sorted_cues if c.id == cue_id2), None)
    if not c1 or not c2:
        return cues

    new_cues: list[SubtitleCue] = []
    merged = False
    for c in sorted_cues:
        if c.id == c1.id and not merged:
            new_cues.append(
                SubtitleCue(
                    id=c1.id,
                    start=min(c1.start, c2.start),
                    end=max(c1.end, c2.end),
                    text=f"{c1.text.strip()} {c2.text.strip()}",
                )
            )
            merged = True
        elif c.id in (c1.id, c2.id):
            continue
        else:
            new_cues.append(c)

    for i, c in enumerate(new_cues, 1):
        c.id = i
    return new_cues


def generate_cues_from_project_scenes(project: Project) -> list[SubtitleCue]:
    """Generate initial subtitle cues from project scenes if no SRT exists yet."""
    cues: list[SubtitleCue] = []
    cumulative_time = 0.0
    cue_counter = 1

    for scene in project.scenes:
        dur = scene.duration or 3.0
        # If drama mode has lines
        if scene.lines:
            line_offset = cumulative_time
            for ln in scene.lines:
                ln_dur = ln.duration or (dur / max(len(scene.lines), 1))
                if ln.text.strip():
                    cues.append(
                        SubtitleCue(
                            id=cue_counter,
                            start=round(line_offset, 3),
                            end=round(line_offset + ln_dur, 3),
                            text=ln.text.strip(),
                        )
                    )
                    cue_counter += 1
                line_offset += ln_dur
        elif scene.narration.strip():
            # Split narration into sentences
            sentences = [s.strip() for s in re.split(r"([。！？\n])", scene.narration) if s.strip()]
            rebuilt = []
            curr = ""
            for s in sentences:
                if s in ("。", "！", "？", "\n"):
                    curr += s
                    rebuilt.append(curr.strip())
                    curr = ""
                else:
                    if curr:
                        rebuilt.append(curr.strip())
                    curr = s
            if curr.strip():
                rebuilt.append(curr.strip())

            if not rebuilt:
                rebuilt = [scene.narration.strip()]

            total_chars = sum(len(s) for s in rebuilt)
            seg_start = cumulative_time
            for s in rebuilt:
                weight = len(s) / max(total_chars, 1)
                seg_dur = max(0.8, dur * weight)
                cues.append(
                    SubtitleCue(
                        id=cue_counter,
                        start=round(seg_start, 3),
                        end=round(seg_start + seg_dur, 3),
                        text=s,
                    )
                )
                cue_counter += 1
                seg_start += seg_dur

        cumulative_time += dur

    return cues
