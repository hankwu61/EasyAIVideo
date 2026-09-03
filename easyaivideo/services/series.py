"""Series (long-form document) helpers: source text storage, episode splitting, child episode projects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..config import config_manager
from ..db import Database
from ..models import Character, Episode, Project, SourceFile, new_id
from ..presets import EDGE_VOICES
from . import storage


class SeriesError(ValueError):
    pass


# ---- source text ----------------------------------------------------------


def source_path(project_id: str) -> Path:
    return storage.project_dir(project_id) / "source" / "source.txt"


def read_source(project_id: str) -> str:
    path = source_path(project_id)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def append_source(project: Project, name: str, text: str) -> None:
    path = source_path(project.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_source(project.id)
    combined = (existing.rstrip("\n") + "\n\n" + text) if existing.strip() else text
    path.write_text(combined, encoding="utf-8")
    project.source_files.append(SourceFile(name=name, chars=len(text)))
    project.source_chars = len(combined)


def clear_source(project: Project) -> None:
    path = source_path(project.id)
    path.unlink(missing_ok=True)
    project.source_files = []
    project.source_chars = 0
    project.episodes = []


def excerpt_for_analysis(text: str, limit: int = 24000) -> str:
    if len(text) <= limit:
        return text
    head = int(limit * 0.5)
    mid = int(limit * 0.25)
    tail = limit - head - mid
    middle_start = len(text) // 2 - mid // 2
    return text[:head] + "\n\n[...]\n\n" + text[middle_start : middle_start + mid] + "\n\n[...]\n\n" + text[-tail:]


# ---- episode planning ------------------------------------------------------


def chars_per_episode(project: Project) -> int:
    cjk = project.language.startswith("zh") or project.language in ("ja", "ko")
    spoken_rate = 4.0 if cjk else 14.0  # source characters spoken per second
    condense = 2.4 if project.content_mode == "narration" else 1.3
    return max(400, int(project.episode_target_seconds * spoken_rate * condense))


def split_into_episodes(text: str, target_chars: int) -> list[tuple[int, int]]:
    """Return (start, end) char ranges aligned to paragraph boundaries."""
    if not text.strip():
        return []
    boundaries = [m.end() for m in re.finditer(r"\n\s*\n|\n", text)]
    boundaries.append(len(text))
    ranges: list[tuple[int, int]] = []
    start = 0
    last_cut = 0
    for b in boundaries:
        if b - start >= target_chars:
            cut = last_cut if last_cut > start and (b - start) > target_chars * 1.35 else b
            ranges.append((start, cut))
            start = cut
        last_cut = b
    if start < len(text) and text[start:].strip():
        # merge a tiny trailing remainder into the previous episode
        if ranges and len(text) - start < target_chars * 0.3:
            s, _ = ranges.pop()
            ranges.append((s, len(text)))
        else:
            ranges.append((start, len(text)))
    return ranges


def pick_voice(language: str, gender: str, fallback: str) -> str:
    if config_manager.get().tts.provider != "edge":
        return fallback
    locale_prefix = {"zh-TW": "zh-TW", "zh-CN": "zh-CN", "en": "en-", "ja": "ja-", "ko": "ko-"}.get(language, language)
    want = "Female" if gender == "female" else "Male" if gender == "male" else None
    for vid, _, locale, g in EDGE_VOICES:
        if locale.startswith(locale_prefix) and (want is None or g == want):
            return vid
    return fallback


def assign_character_ids(project: Project) -> None:
    used = {c.id for c in project.characters if c.id}
    n = 0
    for c in project.characters:
        if not c.id:
            n += 1
            cid = f"c{n:02d}"
            while cid in used:
                n += 1
                cid = f"c{n:02d}"
            c.id = cid
            used.add(cid)
        if not c.voice:
            c.voice = pick_voice(project.language, c.gender, project.voice)


# ---- episode projects ------------------------------------------------------


def episode_by_index(series: Project, index: int) -> Episode:
    ep = next((e for e in series.episodes if e.index == index), None)
    if ep is None:
        raise SeriesError(f"Episode {index} not found")
    return ep


def episode_title(series: Project, ep: Episode) -> str:
    cjk = series.language.startswith("zh") or series.language in ("ja", "ko")
    label = f"第 {ep.index} 集" if cjk else f"Ep {ep.index}"
    name = re.sub(r"^\s*(第\s*\d+\s*[集話话]|episode\s*\d+|ep\.?\s*\d+)\s*[:：\-–]?\s*", "", ep.title, flags=re.IGNORECASE).strip()
    parts = [series.title.strip(), label + (f"：{name}" if name and cjk else f": {name}" if name else "")]
    return " · ".join(p for p in parts if p)[:60]


def episode_excerpt(series: Project, ep: Episode) -> str:
    return read_source(series.id)[ep.source_start : ep.source_end]


async def create_episode(db: Database, series: Project, index: int) -> Project:
    ep = episode_by_index(series, index)
    if ep.project_id:
        existing = await db.get_project(ep.project_id)
        if existing is not None:
            return existing
    child = Project(
        id=new_id("proj"),
        kind="episode",
        parent_id=series.id,
        episode_index=index,
        title=episode_title(series, ep),
        topic=episode_excerpt(series, ep),
        input_mode="novel",
        language=series.language,
        aspect_ratio=series.aspect_ratio,
        style_id=series.style_id,
        style_prompt=series.style_prompt,
        voice=series.voice,
        tts_speed=series.tts_speed,
        bgm=series.bgm,
        bgm_volume=series.bgm_volume,
        subtitle_enabled=series.subtitle_enabled,
        show_title=series.show_title,
        motion=series.motion,
        video_mode=series.video_mode,
        content_mode=series.content_mode,
        episode_target_seconds=series.episode_target_seconds,
    )
    storage.project_dir(child.id).mkdir(parents=True, exist_ok=True)
    await db.save_project(child)
    ep.project_id = child.id
    await db.save_project(series)
    return child


async def enrich_episodes(db: Database, series: Project) -> None:
    """Fill runtime status fields of each episode from its child project."""
    active = {t.project_id: t for t in await db.list_tasks(active=True, limit=500)}
    for ep in series.episodes:
        ep.status, ep.progress, ep.task_message, ep.task_status = "planned", None, None, None
        ep.final_video_url, ep.thumbnail_url, ep.scene_count = None, None, 0
        if not ep.project_id:
            continue
        child = await db.get_project(ep.project_id)
        if child is None:
            ep.project_id = None
            continue
        ep.status = child.status
        ep.final_video_url = child.final_video_url
        ep.thumbnail_url = child.thumbnail_url
        ep.scene_count = len(child.scenes)
        task = active.get(child.id)
        if task:
            ep.task_status, ep.progress, ep.task_message = task.status, task.progress, task.message
        else:
            last = await db.list_tasks(project_id=child.id, limit=1)
            if last and last[0].status == "failed":
                ep.status = "failed"
                ep.task_message = last[0].error


def series_context(project: Project, series: Optional[Project]) -> Project:
    """The project that carries characters/overview/locations for prompts and voices."""
    return series if (project.kind == "episode" and series is not None) else project


def character_voice(ctx: Project, speaker: Optional[str], fallback: str) -> str:
    ch: Optional[Character] = ctx.character_by_name(speaker)
    return ch.voice if ch and ch.voice else fallback
