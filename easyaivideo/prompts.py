"""LLM prompt templates."""

from __future__ import annotations

from typing import Iterable

from .models import Character, Location, Overview
from .presets import LANGUAGE_NAMES


def _lang(language: str) -> str:
    return LANGUAGE_NAMES.get(language, language)


def is_cjk(language: str) -> bool:
    return language.startswith("zh") or language in ("ja", "ko")


def _narration_length_rule(language: str) -> str:
    if is_cjk(language):
        return "each narration is 20 to 45 characters"
    return "each narration is 15 to 35 words"


def topic_script_prompt(topic: str, n_scenes: int, language: str, style_prompt: str) -> str:
    return f"""You are a professional short-video scriptwriter. Write a narrated short video about the topic below.

TOPIC:
{topic}

REQUIREMENTS
1. Produce exactly {n_scenes} scenes. Together they form one coherent, engaging story with a hook at the start and a strong closing line.
2. Narration language: {_lang(language)}. Every narration MUST be written in that language, in a natural spoken tone (it will be read aloud by text-to-speech). Do not use markdown, emoji, or stage directions. {_narration_length_rule(language)}.
3. Each scene also needs an "image_prompt": an English description for an AI image generator that visually represents that narration. 25 to 50 words, concrete and visual (subject, setting, lighting, camera angle). Never include any text, letters, captions, or logos in the image. Keep the same visual style across scenes; the global style is: "{style_prompt}".
4. Each scene also needs a "video_prompt": an English description of the MOTION for an AI video generator that animates that scene's image (what moves, camera movement such as slow push-in / pan / handheld, atmosphere). 15 to 35 words. No text or logos.
5. Give the video a short catchy title (max 12 characters for CJK languages, max 8 words otherwise) in the narration language.

OUTPUT
Return ONLY a JSON object, no explanation, no code fence:
{{"title": "...", "scenes": [{{"narration": "...", "image_prompt": "...", "video_prompt": "..."}}, ...]}}
"""


def image_prompts_prompt(segments: list[str], language: str, style_prompt: str) -> str:
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(segments))
    return f"""You are helping to create a narrated short video. Below are the narration segments (language: {_lang(language)}) in order.

SEGMENTS:
{numbered}

TASKS
1. Write a short catchy title for the whole video in the same language as the segments (max 12 characters for CJK, max 8 words otherwise).
2. For EACH segment write one English "image_prompt" for an AI image generator: 25 to 50 words, concrete and visual (subject, setting, lighting, camera angle), representing that segment. Never include text, letters, captions or logos in the image. Keep a consistent visual style: "{style_prompt}".
3. For EACH segment also write one English "video_prompt" describing the motion for an AI video generator (what moves, camera movement, atmosphere), 15 to 35 words.

OUTPUT
Return ONLY a JSON object with exactly {len(segments)} image prompts and {len(segments)} video prompts in order, no explanation, no code fence:
{{"title": "...", "image_prompts": ["...", "..."], "video_prompts": ["...", "..."]}}
"""


# ---- AI review ----------------------------------------------------------------


def review_scene_prompt(
    *,
    index: int,
    total: int,
    narration: str,
    image_prompt: str,
    language: str,
    n_frames: int,
    characters: list[Character],
    title: str,
) -> str:
    chars = _character_block(characters) if characters else "(none)"
    return f"""You are reviewing a finished narrated short video, scene by scene. The {n_frames} attached image(s) are keyframes taken from the rendered video for ONE scene (they may include burned-in subtitles and a title overlay; ignore those overlays themselves).

VIDEO TITLE: {title}
SCENE INDEX: {index}
SCENE {index} of {total}
NARRATION spoken during this scene ({_lang(language)}):
"{narration}"
INTENDED IMAGE PROMPT (what the image generator was asked for):
"{image_prompt}"
CHARACTERS (if the narration mentions one, the visuals must match this appearance):
{chars}

CHECK
1. Does the picture show what the narration talks about (subject, place, action, time of day, mood)? Anything mentioned in the narration but clearly missing or contradicted?
2. Are there visible defects: garbled or unwanted text/logos in the image itself (NOT the subtitle overlay), extra limbs/fingers, distorted faces, wrong number of people, inconsistent character appearance?
3. Is the scene visually readable at a glance (main subject clear, not too cluttered)?

OUTPUT — JSON only, no code fence:
{{"score": 1-5 (5 = perfect match, 3 = acceptable, 1 = unrelated or broken),
 "match": true|false,
 "issues": ["short concrete sentence per problem, in {_lang(language)}; empty list if none"],
 "suggested_image_prompt": "if score <= 3: an improved ENGLISH image prompt (30-60 words) that would fix the issues while keeping the same style; otherwise empty string",
 "note": "one sentence overall comment in {_lang(language)}"}}
"""


def review_summary_prompt(title: str, language: str, scene_lines: list[str]) -> str:
    joined = "\n".join(scene_lines)
    return f"""TASK: REVIEW_SUMMARY
You reviewed every scene of the short video "{title}". SCENE REVIEWS (one per line: index | score | issues):
{joined}

Write a 2-4 sentence summary for the creator in {_lang(language)}: overall quality, which scenes need fixing first and why. Be concrete and brief.
Return ONLY JSON, no code fence: {{"summary": "..."}}
"""


# ---- long-form documents ---------------------------------------------------


def analyze_document_prompt(excerpt: str, language: str) -> str:
    return f"""TASK: ANALYZE_DOCUMENT
You are a story analyst preparing a novel or long article for adaptation into short videos.

DOCUMENT (may be excerpted from a longer text):
<<<
{excerpt}
>>>

Produce, in {_lang(language)} unless stated otherwise:
1. "overview": {{"synopsis": 3-5 sentences, "genre": short label, "theme": one sentence, "world_setting": 1-3 sentences about time, place and rules of the world}}.
2. "characters": the 3 to 8 most important characters. For each: {{"name": exact name as written in the text, "description": role and personality in 1-2 sentences, "gender": "female" | "male" | "other", "appearance": ENGLISH visual description for an AI image generator (age, ethnicity if implied, hair, face, build, signature clothing and colors; 20-40 words; no names)}}.
3. "locations": up to 6 recurring places: {{"name": "...", "description": 1 sentence}}.

Return ONLY a JSON object, no explanation, no code fence:
{{"overview": {{...}}, "characters": [...], "locations": [...]}}
"""


def episode_titles_prompt(excerpts: Iterable[tuple[int, str]], language: str) -> str:
    blocks = "\n\n".join(f"[EPISODE {i}]\n{text}" for i, text in excerpts)
    return f"""TASK: EPISODE_TITLES
A long text was split into consecutive episodes for a video series. Below is the beginning of each episode.

{blocks}

For every episode write, in {_lang(language)}:
- "title": a short catchy episode title (max 12 characters for CJK, max 8 words otherwise). Do NOT include the episode number.
- "summary": 1-2 sentences describing what happens in that episode.

Return ONLY a JSON object, no explanation, no code fence:
{{"episodes": [{{"index": 1, "title": "...", "summary": "..."}}, ...]}}
"""


def _character_block(characters: list[Character]) -> str:
    if not characters:
        return "(none defined)"
    return "\n".join(f"- {c.name} ({c.gender}): {c.description} | appearance: {c.appearance}" for c in characters if c.name)


def _location_block(locations: list[Location]) -> str:
    if not locations:
        return "(none defined)"
    return "\n".join(f"- {loc.name}: {loc.description}" for loc in locations if loc.name)


def episode_script_prompt(
    *,
    mode: str,
    excerpt: str,
    language: str,
    target_seconds: int,
    style_prompt: str,
    overview: Overview | None,
    characters: list[Character],
    locations: list[Location],
    episode_title: str,
) -> str:
    rate = 4.0 if is_cjk(language) else 2.6
    unit = "characters" if is_cjk(language) else "words"
    budget = int(target_seconds * rate)
    n_scenes = max(3, min(40, round(target_seconds / 7)))
    synopsis = overview.synopsis if overview else ""
    common = f"""TASK: EPISODE_SCRIPT ({mode})
You are adapting one episode of a long story into a short video with AI-generated images and text-to-speech.

STORY SYNOPSIS: {synopsis}
EPISODE TITLE: {episode_title}
CHARACTERS (use these exact names; put the appearance text into image prompts whenever the character is visible):
{_character_block(characters)}
LOCATIONS:
{_location_block(locations)}

EXCERPT:
<<<
{excerpt}
>>>

GLOBAL IMAGE STYLE: "{style_prompt}"
"""
    if mode == "drama":
        rules = f"""REQUIREMENTS (drama mode: characters speak their own lines)
1. Split the excerpt into about {n_scenes} scenes in story order. Each scene has 2 to 6 "lines". A line is {{"speaker": character name or null for the narrator, "text": spoken text}}. Dialogue must come from or be faithfully adapted from the excerpt; use narrator lines (speaker null) for necessary description and transitions. Keep the total spoken text around {budget} {unit} so the episode lasts about {target_seconds} seconds.
2. All spoken text in {_lang(language)}, natural spoken tone, no stage directions, no markdown.
3. Each scene needs "image_prompt": ENGLISH, 30-60 words, one clear shot: who is in frame with their exact appearance text from the character list, the location, action, lighting, camera angle. Never include text, letters or logos. Also give "location": the location name or null.
4. Each scene needs "video_prompt": ENGLISH, 15-35 words describing the motion for an AI video generator (character action, camera movement, atmosphere), consistent with the image prompt.
5. Give the episode a short "title" in {_lang(language)} (may reuse the episode title).

OUTPUT (JSON only, no code fence):
{{"title": "...", "scenes": [{{"lines": [{{"speaker": "...", "text": "..."}}], "image_prompt": "...", "video_prompt": "...", "location": "..."}}, ...]}}
"""
    else:
        rules = f"""REQUIREMENTS (narration mode: a narrator retells the story)
1. Retell the excerpt as an engaging voice-over of about {n_scenes} scenes in story order, total about {budget} {unit} so it lasts about {target_seconds} seconds. Keep key dialogue as reported speech or short quotes. Do not summarise so much that it becomes dull; keep concrete moments.
2. Every "narration" in {_lang(language)}, natural spoken tone, {_narration_length_rule(language)}, no markdown, no stage directions.
3. Each scene needs "image_prompt": ENGLISH, 30-60 words, one clear shot: who is in frame with their exact appearance text from the character list, the location, action, lighting, camera angle. Never include text, letters or logos. Also give "location": the location name or null.
4. Each scene needs "video_prompt": ENGLISH, 15-35 words describing the motion for an AI video generator (character action, camera movement, atmosphere), consistent with the image prompt.
5. Give the episode a short "title" in {_lang(language)} (may reuse the episode title).

OUTPUT (JSON only, no code fence):
{{"title": "...", "scenes": [{{"narration": "...", "image_prompt": "...", "video_prompt": "...", "location": "..."}}, ...]}}
"""
    return common + "\n" + rules
