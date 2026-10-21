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


def video_motion_rules(video_mode: str = "i2v") -> str:
    rules = """VIDEO PROMPT RULES:
Write video_prompt in English using one main action and one camera behavior per shot.
A locked-off camera counts as a camera behavior. Choose framing and movement to support
this shot; do not default every shot to a slow push-in or cinematic camera movement.
Use concrete verbs, direction and speed. Refer to subjects simply (the person, the cup).
For image-to-video, the input image already defines appearance, lighting and composition:
do not copy the image_prompt or repeat visual style, clothing and scenery descriptions.
Keep the action feasible within the shot duration. Use a single continuous shot.
Do not force camera or motion continuity with the preceding scene.
"""
    if video_mode == "keyframes":
        rules += """Both frames belong to this same shot. Describe the ordered phases of ONE action:
initiation, progression, then arrival at the pose/object positions in end_image_prompt.
Use 'then' and 'finally' when useful, not a list of unrelated actions. Keep one camera behavior.
Provide end_image_prompt describing the concrete final state in the same setting.
"""
    elif video_mode == "t2v":
        rules += "For text-to-video only, include the essential subject, setting and visual style as well as motion."
    else:
        rules += "Use only the starting frame as a constraint. Do not refer to a final frame or prescribe an end-image match."
    return rules


def topic_script_prompt(topic: str, n_scenes: int, language: str, style_prompt: str, video_mode: str = "i2v") -> str:
    return f"""You are a professional short-video scriptwriter and visual director. Write a narrated short video about the topic below with strict visual and motion continuity across scenes.

TOPIC:
{topic}

REQUIREMENTS
1. Produce exactly {n_scenes} scenes. Together they form one coherent, engaging story with a hook at the start and a strong closing line.
2. Narration language: {_lang(language)}. Every narration MUST be written in that language, in a natural spoken tone (it will be read aloud by text-to-speech). Do not use markdown, emoji, or stage directions. {_narration_length_rule(language)}.
3. VISUAL CONTINUITY & IMAGE PROMPTS (FIRST & LAST FRAMES):
   - Each scene needs an "image_prompt": English description (30 to 60 words) for the STARTING FRAME (首幀) of the scene. Concrete and visual (clear single subject or defined group, anatomically correct, detailed character traits, setting, lighting, camera angle). Never include text, letters, captions, or logos. Global style: "{style_prompt}".
   - Each scene needs an "end_image_prompt": English description (30 to 60 words) for the ENDING FRAME (尾幀) of the scene. MUST depict the SAME SINGLE subject/character in their final pose or position, maintaining identical clothing, face, environment and lighting. CRITICAL ANATOMY & SINGLE ENTITY RULE: Explicitly depict clear, natural anatomy with exactly one head, standard limbs (two arms and two legs for humanoids, four legs for quadrupeds), and IF AN ANIMAL HAS A TAIL, DEPICT EXACTLY ONE SINGLE TAIL. NEVER describe swinging or wagging tails in a way that suggests motion blur, and NEVER allow multiple tails, extra tails, split tails, extra limbs, or fused multiple heads.
   - SCENE-TO-SCENE CONTINUITY: Maintain story and character consistency across scenes; each scene is an independent shot and may use a different camera setup.
   - CHARACTER CONSISTENCY: If characters appear across multiple scenes, their visual appearance MUST remain 100% consistent across all scenes (specify identical facial features, age, hairstyle, hair color, exact clothing colors, accessories, and signature costume). Scene 1 defines the master keyframe (原首幀); subsequent scenes MUST match this exact character so they never look like a different person.
   - ENVIRONMENT CONSISTENCY: If scenes take place in the same location, maintain identical architecture, atmosphere, color palette, and lighting conditions. Transitions between locations must be spatially coherent.
4. MOTION CONTINUITY & VIDEO PROMPTS (FIRST-TO-LAST FRAME TRANSITION):
   - Each scene needs a "video_prompt": concise English motion description (normally 20-50 words).
{video_motion_rules(video_mode)}
5. Give the video a short catchy title (max 12 characters for CJK languages, max 8 words otherwise) in the narration language.

OUTPUT
Return ONLY a JSON object, no explanation, no code fence:
{{"title": "...", "scenes": [{{"narration": "...", "image_prompt": "...", "end_image_prompt": "...", "video_prompt": "..."}}, ...]}}
"""


def image_prompts_prompt(segments: list[str], language: str, style_prompt: str, video_mode: str = "i2v") -> str:
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(segments))
    return f"""You are helping to create a narrated short video with high visual and motion continuity. Below are the narration segments (language: {_lang(language)}) in order.

SEGMENTS:
{numbered}

TASKS
1. Write a short catchy title for the whole video in the same language as the segments (max 12 characters for CJK, max 8 words otherwise).
2. VISUAL CONTINUITY: For EACH segment from segment 2 onward, build upon the previous segment's characters, setting, and ending visual state.
3. For EACH segment write one English "image_prompt" for the starting frame (首幀): 30 to 60 words, concrete and visual (clear single subject, anatomically correct, setting, lighting, camera angle). Keep consistent visual style: "{style_prompt}".
4. For EACH segment write one English "end_image_prompt" for the ending frame (尾幀): 30 to 60 words, strictly matching the same single character/animal, clothing, and environment. MUST depict one single subject with proper natural anatomy (one head, standard limbs, exactly one single tail if an animal) in their final pose, strictly avoiding any ghosting, duplicated limbs, multiple tails, or multiple heads.
5. For EACH segment write one concise English "video_prompt" (normally 20-50 words).
{video_motion_rules(video_mode)}

OUTPUT
Return ONLY a JSON object with exactly {len(segments)} items for each list in order, no explanation, no code fence:
{{"title": "...", "image_prompts": ["...", "..."], "end_image_prompts": ["...", "..."], "video_prompts": ["...", "..."]}}
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
    video_mode: str = "i2v",
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
3. VISUAL CONTINUITY & IMAGE PROMPTS (CRITICAL): Each scene needs "image_prompt": ENGLISH, 30-60 words, one clear shot: who is in frame with their exact appearance text from the character list, the location, action, lighting, camera angle. Every scene from Scene 2 onward MUST reference the preceding scene's image prompt. Keep identical character appearance (facial features, hairstyle, clothing) across consecutive scenes to prevent character drifting. Never include text, letters or logos. Also give "location": the location name or null.
4. MOTION CONTINUITY & VIDEO PROMPTS (CRITICAL): Each scene needs "video_prompt": concise ENGLISH motion instructions.
{video_motion_rules(video_mode)}
5. Give the episode a short "title" in {_lang(language)} (may reuse the episode title).

OUTPUT (JSON only, no code fence):
{{"title": "...", "scenes": [{{"lines": [{{"speaker": "...", "text": "..."}}], "image_prompt": "...", "video_prompt": "...", "end_image_prompt": "...", "location": "..."}}, ...]}}
"""
    else:
        rules = f"""REQUIREMENTS (narration mode: a narrator retells the story)
1. Retell the excerpt as an engaging voice-over of about {n_scenes} scenes in story order, total about {budget} {unit} so it lasts about {target_seconds} seconds. Keep key dialogue as reported speech or short quotes. Do not summarise so much that it becomes dull; keep concrete moments.
2. Every "narration" in {_lang(language)}, natural spoken tone, {_narration_length_rule(language)}, no markdown, no stage directions.
3. VISUAL CONTINUITY & IMAGE PROMPTS (CRITICAL): Each scene needs "image_prompt": ENGLISH, 30-60 words, one clear shot: who is in frame with their exact appearance text from the character list, the location, action, lighting, camera angle. Every scene from Scene 2 onward MUST reference the preceding scene's image prompt. Keep identical character appearance (facial features, hairstyle, clothing) across consecutive scenes to prevent character drifting. Never include text, letters or logos. Also give "location": the location name or null.
4. MOTION CONTINUITY & VIDEO PROMPTS (CRITICAL): Each scene needs "video_prompt": concise ENGLISH motion instructions.
{video_motion_rules(video_mode)}
5. Give the episode a short "title" in {_lang(language)} (may reuse the episode title).

OUTPUT (JSON only, no code fence):
{{"title": "...", "scenes": [{{"narration": "...", "image_prompt": "...", "video_prompt": "...", "end_image_prompt": "...", "location": "..."}}, ...]}}
"""
    return common + "\n" + rules


def analyze_video_remake_prompt(language: str, n_frames: int, duration_seconds: float) -> str:
    return f"""TASK: ANALYZE_VIDEO_FOR_REMAKE
You are a master film director and AI video producer. You are provided with {n_frames} sequential keyframes extracted chronologically from an original short video of approximately {duration_seconds:.1f} seconds.

Your mission:
Analyze the video's theme, storyline, visual aesthetics, and breakdown into sequential scenes so we can reproduce/remake a new high-quality AI video with the EXACT SAME THEME, STRUCTURE, PACING, AND VISUAL VIBE.

REQUIREMENTS:
1. "title": Catchy short title in {_lang(language)} (max 15 characters for CJK, max 8 words otherwise).
2. "theme": A clear summary (2-4 sentences) in {_lang(language)} explaining what happens, the core message, and emotional tone.
3. "style_id": Choose the closest match from: ["cinematic", "anime", "comic", "claymation", "cyberpunk", "pixel", "watercolor", "3d_render"].
4. "style_prompt": High-level visual style description in English (lighting, color palette, camera lens, atmosphere, e.g. "cinematic 35mm film look, natural golden hour lighting, 8k resolution, photorealistic").
5. "scenes": An array of sequential scenes (typically {max(2, min(n_frames, 10))} scenes) capturing the story flow:
   For each scene:
   - "index": 0-indexed integer (0, 1, 2...).
   - "keyframe_index": 0-indexed integer (0 to {n_frames - 1}) pointing to which provided keyframe image best corresponds to this scene.
   - "duration": Estimated duration in seconds (typically 3.0 to 7.0 seconds).
   - "narration": Voiceover/narration or spoken dialogue in {_lang(language)} fitting this scene, natural spoken tone, no markdown.
   - "image_prompt": Detailed English text-to-image prompt (30-60 words) describing the scene's starting frame subject, action, framing, environment, lighting. Clean single subject, natural anatomy, no text/watermarks.
   - "end_image_prompt": Detailed English text-to-image prompt (30-60 words) describing the scene's ending frame, matching the character/animal and setting with image_prompt. MUST depict one single subject with proper natural anatomy (one head, standard limbs, exactly one single tail if an animal) in their final pose, avoiding any ghosting, duplicated limbs, multiple tails, or fused multiple heads.
   - "video_prompt": Concise English motion instructions.
{video_motion_rules("keyframes")}

OUTPUT FORMAT:
Return ONLY a valid JSON object, no explanation, no markdown code fences:
{{
  "title": "...",
  "theme": "...",
  "style_id": "...",
  "style_prompt": "...",
  "scenes": [
    {{
      "index": 0,
      "keyframe_index": 0,
      "duration": 4.0,
      "narration": "...",
      "image_prompt": "...",
      "end_image_prompt": "...",
      "video_prompt": "..."
    }}
  ]
}}
"""


def end_image_prompt_for(scene: Any, end_prompt: str, style_prompt: str, prefix: str = "") -> str:
    """Build the prompt for the ending frame, incorporating style, prefix, and single-subject anatomy reinforcement."""
    parts = []
    if prefix.strip():
        parts.append(prefix.strip().rstrip(","))
    p = end_prompt.strip() or getattr(scene, "image_prompt", "").strip()
    if p:
        parts.append(p)
    # Positive prompt reinforcement to prevent limb/head duplication, multiple tails, or fusion across all image models
    parts.append("single subject, clean natural anatomy, perfectly formed limbs, exactly one head, exactly one single tail, photorealistic coherence")
    if style_prompt.strip():
        parts.append(style_prompt.strip())
    return ", ".join(parts)


def analyze_video_h3_prompt(
    language: str,
    n_frames: int,
    duration_seconds: float,
    aspect_ratio: str,
    forensic_summary: str,
    h3_mode: str = "ref2va",
    character_replacement: Optional[str] = None,
) -> str:
    """Prompt for forensic reverse-engineering of reference video into MiniMax Hailuo H3 prompts.

    Based on the forensic methodology in D:\\video-to-h3-prompt:
    1. Film-Type Triage into Camera State Machine:
       - Type A: continuous take (one unbroken take)
       - Type B: editorial snap-lock (HARD LOCK <-> INSTANT BURST two-state machine)
       - Type C: multi-shot montage (named setups + cut discipline)
    2. Audio Onset & Card-Point Reconciliation
    3. Causal Event-Chain Reconstruction (trigger -> action -> reaction)
    4. 4-Layer Separation (Live action, Camera, Editing/Effects, Sound)
    5. Pure English H3 Assembly (Ref2VA 6-section or 14-field format)
    6. Segmentation for clips > 15s (clocks reset to 00:00, hand-off state)
    7. Character/Coser Replacement (skin-only swap without plot change)
    """
    mode_instructions = ""
    if h3_mode.lower() == "ref2va":
        mode_instructions = """### MODE: Ref2VA (Six-Section Format)
The 'h3_prompt' field MUST follow the exact 6-section Ref2VA template:
1. `subject_definitions:`
   <Subject 1> is the identity in <Picture 1>, with appearance list...
   <Video 1> is the source video that defines the target video's shot structure, motion path, and pacing: [summary of source]. <Video 1> is used only for temporal structure; [what is discarded].
2. `summary:`
   [task-tag + asset-tag] One-paragraph task summary using <Subject 1>, <Picture 1>, <Video 1>.
3. `retention_analysis:`
   <Subject 1> (appears in [Shot 1], [Shot 2]...): fully_preserved - [what is kept].
   <Video 1> (governs the whole video): reference - [what is kept]; [what is discarded].
4. `detailed_description:`
   The target video uses [style description].
   [Shot 1] [Opening composition, NO timestamp, must include all 6 elements: Composition, Subject appearance+position, Environment+lighting, Action+state change, Camera movement, Current sound].
   [Shot 2] At 00:XX.XXX, [transition verb] [rest of shot with all 6 elements]...
   (Strictly increasing timestamps, two decimals '00:03.20').
5. `overall_soundscape:`
   [Ambience + physical SFX + non-verbal human sounds + freeze-frame post-SFX].
6. `non_diegetic_music:`
   [Audience-only score or N/A or explicit silence].
"""
    else:
        mode_instructions = f"""### MODE: {h3_mode.upper()} (14-Field Format)
The 'h3_prompt' field MUST follow the exact 14-field template in this order:
1. `subject_definitions:` (Actors, age, clothing, hand props, off-camera actors, aspect ratio {aspect_ratio})
2. `environment_definition:` (Space, architecture, ground, background, exclusions; omit if I2VA first-frame lock)
3. `lighting_definition:` (Key direction, color temp, fill, shadows, specular)
4. `visual_anchor:` (If I2VA: 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.')
5. `audio:` (If reusing audio: 'supplied audio fully_copy')
6. `integrated_multimodal_description:` (One structural premise sentence + [Shot 1] opening state without timestamp + strictly increasing timestamps [00:XX.X] trigger->action->expansion->accent->recovery with embedded diegetic sound)
7. `camera_direction:` (POV/framing/angle, movement type + amplitude + speed + motivation, explicit no-orbit/no-zoom list, or HARD LOCK <-> INSTANT BURST state machine)
8. `editing:` (Cut policy, freeze-frame gags with in-point, duration, overlay recipe, snap-back, N-beat rhythm)
9. `performance:` (Emotional arc, contrast, where exaggeration is allowed/forbidden)
10. `body_mechanics:` (Wind-up before release, force transmission, grounded feet)
11. `costume_hair_physics:` (Hair lag, fabric weight, wet evolution, glasses/mask resistance)
12. `negative_constraints:` (Exclusions: no extra people, no added props, no style drift, no subtitles/watermarks)
13. `overall_soundscape:` (Ambient bed, ordered diegetic cues, freeze post-SFX)
14. `non_diegetic_music:` (Target music spec or explicit silence)
"""

    char_replace_prompt = ""
    if character_replacement and character_replacement.strip():
        char_replace_prompt = f"""### CHARACTER / COSER REPLACEMENT TASK:
The user has requested replacing the character/actor with:
"{character_replacement.strip()}"
RULES FOR REPLACEMENT:
- Skin-only swap: change appearance, costume, face, hair ONLY.
- Keep the physical actions, movement trajectory, and camera state machine 100% IDENTICAL to the source.
- Populate 'character_replacement_table' with: original_element -> replaced_element, and action compatibility notes.
"""

    segmentation_rule = ""
    if duration_seconds > 15.0:
        segmentation_rule = f"""### LONG VIDEO SEGMENTATION RULE (Duration {duration_seconds:.1f}s > 15s):
MiniMax H3 clips are optimal at <= 15 seconds.
You MUST provide multiple sequential segment prompts in 'h3_segments' array.
Each segment:
- Clock resets and starts from 00:00.00
- Music does NOT restart from beginning (carries over)
- Explicit hand-off state connecting the end of Segment N with start of Segment N+1
"""

    return f"""TASK: FORENSIC_REVERSE_ENGINEER_VIDEO_TO_MINIMAX_H3_PROMPT
You are a senior forensic film director and MiniMax Hailuo H3 master prompt engineer.
You are provided with {n_frames} keyframe images extracted chronologically from a video of {duration_seconds:.2f} seconds ({aspect_ratio}), together with the following forensic audio and media dossier:

{forensic_summary}

{mode_instructions}

{char_replace_prompt}

{segmentation_rule}

### CORE FORENSIC RULES (From D:\\video-to-h3-prompt):
1. TRIAGE FILM TYPE FIRST:
   - Type A (Continuous Take): One unbroken take, baseline handheld/locked camera, continuous motion.
   - Type B (Editorial Snap-Lock): Mutually exclusive HARD LOCK <-> INSTANT BURST states. Camera holds dead still, burst only on transitions.
   - Type C (Multi-shot Montage): Named setups (e.g. HERO_MS, REACTION_CU), cuts aligned with musical accents.
2. AUDIO ONSET ALIGNMENT:
   Every cut, freeze-frame, impact, punch, or state change must align with a Strong (S) or Hard (H) audio onset listed in the forensic summary. If audio has no stable BGM, DO NOT invent a BPM.
3. CAUSAL EVENT CHAIN:
   Do not just list poses. State trigger -> action -> reaction for every change.
4. FOUR-LAYER SEPARATION:
   Separate live physical action, camera motion, editing/post effects (freeze gags, manga speedlines, RGB glitches belong in editing/SFX, not physical action), and sound layers.
5. NO APPEARANCE PROSE IF REFERENCE IMAGE USED:
   When <Picture 1> is referenced, prose carries only camera, timing, state machine, and props. Appearance is locked by the picture.
6. IMPACT COUNTABILITY:
   Countable discrete impacts, not continuous mushy vibration. Move camera, do not deform character.

OUTPUT FORMAT:
Return ONLY a valid JSON object (no markdown code blocks, no leading/trailing explanation):
{{
  "title": "Short title in {_lang(language)}",
  "film_type": "A_continuous" | "B_snap_lock" | "C_montage",
  "h3_mode": "{h3_mode.lower()}",
  "forensic_report": "Detailed markdown report in {_lang(language)} covering: 1. 片型與相機狀態機判定, 2. 音樂節奏與卡點對帳分析 (列出每個強音頭與畫面對應), 3. 因果動作鏈重建, 4. 鏡頭與機位命名分鏡, 5. 剪輯與後期特效層分離, 6. 聲音與同期聲總覽",
  "h3_prompt": "Complete, ready-to-paste, fully compiled English MiniMax H3 prompt block",
  "h3_segments": [
    {{
      "segment_index": 0,
      "time_range": "00:00 - 00:12",
      "prompt": "Segment prompt with clock from 00:00.00"
    }}
  ],
  "character_replacement_table": "Markdown table if replacement was requested, else empty string",
  "scenes": [
    {{
      "index": 0,
      "keyframe_index": 0,
      "duration": 4.0,
      "narration": "Narration / dialogue in {_lang(language)} for this scene",
      "image_prompt": "Detailed English starting frame prompt (30-60 words)",
      "video_prompt": "Precise English motion and camera instruction according to H3 state machine",
      "cut_time": "00:00.00"
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Video clone -> MiniMax H3 (segment-aware forensic reverse engineering)
# Rules follow the video-to-h3-prompt skill; its key references are bundled in easyaivideo/h3_refs.
# ---------------------------------------------------------------------------

_H3_REF_FILES = ("shot-syntax.md", "06-film-type-and-state-machine.md", "08-multi-image-and-segmentation.md", "05-pitfalls-checklist.md")


def h3_reference_docs(names: Iterable[str] = _H3_REF_FILES) -> str:
    """Bundled skill references, concatenated (empty string if the folder is missing)."""
    from pathlib import Path

    base = Path(__file__).resolve().parent / "h3_refs"
    parts: list[str] = []
    for name in names:
        p = base / name
        if p.is_file():
            parts.append(f"----- {name} -----\n{p.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def _h3_inputs_block(use_video: bool, use_audio: bool, n_pictures: int, h3_mode: str) -> str:
    mode = h3_mode.lower()
    if mode == "t2va":
        return "INPUTS SENT TO H3 WITH THIS PROMPT: text only (no reference media). Describe appearance, environment and lighting fully in text."
    if mode in ("i2va", "fl2va"):
        frames = "<Picture 1> = the segment's first frame" + (" and <Picture 2> = its last frame" if mode == "fl2va" else "")
        return f"INPUTS SENT TO H3 WITH THIS PROMPT: {frames}. Use the visual_anchor field; do not re-describe what the anchor frame already shows."
    lines = ["INPUTS SENT TO H3 WITH THIS PROMPT (label meaning must stay identical in every section):"]
    for i in range(n_pictures):
        lines.append(f"- <Picture {i + 1}>: user-supplied identity reference image #{i + 1} (locks ONE character's identity + costume only).")
    if use_video:
        lines.append("- <Video 1>: the source video cut to exactly this segment (structure, timing, composition, camera paths). Its burned-in text/graphics must be declared discarded.")
    if use_audio:
        lines.append("- <Audio 1>: the source audio cut to exactly this segment. It is fully_copy-ed and is the ONLY temporal source; the voice is off-screen narration unless the frames show lip-sync.")
    if n_pictures:
        lines.append("PICTURE RULE: appearance lives in the pictures -> ZERO appearance prose for picture-locked subjects (face, hair, outfit). Props, environment, lighting and camera stay in text.")
    if not use_video and not n_pictures:
        lines.append("WARNING: R2V needs at least one image or video reference; the app will add <Video 1>.")
    return "\n".join(lines)


def analyze_video_h3_overview_prompt(
    language: str,
    duration_seconds: float,
    aspect_ratio: str,
    dossier: str,
    segments: list[dict],
    n_images: int,
    n_pictures: int = 0,
    character_replacement: str | None = None,
) -> str:
    """Pass 1: whole-video triage -> film type, shared subject definitions, style line, Chinese report."""
    seg_lines = "\n".join(
        f"  Part {s['index'] + 1}: source {s['start']:.2f}-{s['end']:.2f}s ({s['duration']:.2f}s, cut at: {s.get('reason', '')})" for s in segments
    )
    replace = ""
    if character_replacement and character_replacement.strip():
        replace = (
            f"\nCHARACTER REPLACEMENT REQUESTED: \"{character_replacement.strip()}\". Skin-only swap: change appearance only, keep every action, "
            "camera move and timing. Put the NEW appearance in subjects_block and fill character_replacement_table (markdown, "
            f"{_lang(language)}) with original -> replacement and action-compatibility notes.\n"
        )
    pictures = ""
    if n_pictures:
        pictures = (
            f"\nThe user supplied {n_pictures} identity reference picture(s) (<Picture 1>..<Picture {n_pictures}>). In subjects_block bind each "
            "main character to one picture with the all-purpose identity-lock wording and write NO appearance prose for them.\n"
        )
    return f"""TASK: VIDEO_TO_H3_OVERVIEW
You are a senior forensic film editor and MiniMax H3 prompt engineer. You receive {n_images} timecoded contact sheets
(yellow = segment-local seconds, white "src" = source seconds) covering a {duration_seconds:.2f}s {aspect_ratio} video,
and this measured forensic dossier (treat measured numbers as evidence; the sheets are the visual channel):

{dossier}

The app already split the video into H3 generation parts (each <= 15 s):
{seg_lines}
{replace}{pictures}
DO, following the skill workflow (sparse skeleton -> cross-validate audio -> causal chain -> film-type triage):
1. Triage the film type: A_continuous (one take), B_snap_lock (HARD LOCK <-> INSTANT BURST), or C_montage (named setups + cut discipline).
   A clip of slow AI camera moves joined by dissolves/cuts is C_montage; never use LOCK/BURST for it.
2. Separate layers: burned-in titles, captions, speech bubbles, badges, stickers and text inside dissolves are POST-PRODUCTION graphics.
   They are never generated by H3: list their exact text in post_text_overlays (verbatim, original language) so the user can add them later.
3. Define the recurring subjects ONCE so every part stays consistent: subjects_block = English lines
   "<Subject 1> is ...", "<Subject 2> is ..." (identity, age feel, hair, outfit; animals: coat/build/eyes). If the source shows identity
   drift between shots, unify to one consistent look and say so in the report. Do NOT define <Video>/<Audio> here.
4. style_line = one English sentence: "The target video uses ..." (look, light, palette, depth of field, camera feel, aspect).
5. forensic_report (markdown, {_lang(language)}) with the fixed structure: 片型與分流結論 / 場景 / 人物(含畫外行動者) / 因果動作鏈 /
   機位分鏡表 / 剪輯特效層 / 節奏分析與卡點對帳 / 聲音結論 / 推測與待確認. Mark single-channel claims as 推測.

Return ONLY valid JSON:
{{
  "title": "short title in {_lang(language)}",
  "theme": "one line in {_lang(language)}",
  "film_type": "A_continuous" | "B_snap_lock" | "C_montage",
  "style_line": "The target video uses ...",
  "subjects_block": "<Subject 1> is ...\\n<Subject 2> is ...",
  "post_text_overlays": ["verbatim on-screen text 1", "..."],
  "character_replacement_table": "",
  "forensic_report": "markdown"
}}
"""


def analyze_h3_segment_prompt(
    *,
    language: str,
    part_index: int,
    part_count: int,
    seg_start: float,
    seg_end: float,
    request_duration: int,
    aspect_ratio: str,
    local_dossier: str,
    film_type: str,
    style_line: str,
    subjects_block: str,
    prev_hand_off: str,
    h3_mode: str = "ref2va",
    use_video: bool = True,
    use_audio: bool = True,
    has_audio: bool = True,
    n_pictures: int = 0,
    n_images: int = 0,
    include_refs: bool = True,
) -> str:
    """Pass 2: one H3 prompt per part, on a segment-local clock."""
    dur = seg_end - seg_start
    mode = h3_mode.lower()
    last = part_index == part_count - 1
    if mode == "ref2va":
        template = """Write the prompt in the Ref2VA SIX-SECTION format, in this order, each header on its own line:
subject_definitions: / summary: / retention_analysis: / detailed_description: / overall_soundscape: / non_diegetic_music:
- subject_definitions: reuse SUBJECTS BLOCK verbatim (only subjects that appear in this part), then define every input label used.
- summary: "[Ref2VA remake + <assets>] ..." one paragraph.
- retention_analysis: one row per subject and per input label (fully_preserved / reference / fully_copy - kept; discarded).
- detailed_description: first the style line, then [Shot N] blocks. [Shot 1] has NO timestamp; later shots "[Shot N] At 00:SS.SS, <transition verb> ...".
  Every shot covers the 6 elements (composition, subject+position, environment+light, action+state change with trigger->action->result,
  camera move with amplitude+speed+motivation, current sound). Inside a shot use "At 00:SS.SS" for each real state change.
  Then the CONTINUATION STATE line (unless last part), then one "Constraints:" line (exact shot/cut count, no on-screen text/captions/
  logos/watermarks, no lip movement for off-screen narration, no extra people, banned camera moves)."""
    else:
        template = """Write the prompt in the 14-FIELD format, in this order: subject_definitions / environment_definition / lighting_definition /
visual_anchor / audio / integrated_multimodal_description / camera_direction / editing / performance / body_mechanics /
costume_hair_physics / negative_constraints / overall_soundscape / non_diegetic_music. [Shot 1] has no timestamp; later timestamps strictly increase."""

    hand = ""
    if part_index > 0 and prev_hand_off:
        hand = f"\nPREVIOUS PART ENDED ON (open [Shot 1] with 'OPEN ON THE HAND-OFF STATE:' and restate it): {prev_hand_off}\n"
    sound = (
        "overall_soundscape: start with 'Fully copy <Audio 1>:' and describe the voice (gender, tone, off-screen or on-camera), list the breath "
        "pauses from the dossier as segment-local times, then ambience. Do NOT invent sound effects or music that the dossier/frames do not support."
        if (use_audio and has_audio and mode == "ref2va")
        else "overall_soundscape: describe only sound supported by the dossier; if the source has no audio write explicit silence."
    )
    refs = ""
    if include_refs:
        docs = h3_reference_docs()
        if docs:
            refs = f"\n\n=== SKILL REFERENCES (authoritative rules) ===\n{docs}\n=== END REFERENCES ===\n"
    return f"""TASK: VIDEO_TO_H3_SEGMENT_PROMPT
You write PART {part_index + 1} of {part_count} of a MiniMax H3 remake. This part covers source {seg_start:.2f}-{seg_end:.2f}s
= {dur:.2f}s; H3 will be asked for {request_duration}s and trimmed to {dur:.2f}s. Aspect {aspect_ratio}. Film type: {film_type}.
The {n_images} images are timecoded contact sheets of THIS PART ONLY: the big yellow number is the SEGMENT-LOCAL time you must use.

{local_dossier}

{_h3_inputs_block(use_video, use_audio, n_pictures, mode)}

SUBJECTS BLOCK (shared by all parts, reuse verbatim):
{subjects_block or "(none - define subjects yourself)"}

STYLE LINE: {style_line or "(write one)"}
{hand}
{template}
{sound}
non_diegetic_music: "N/A - explicit silence ..." unless the dossier says FIXED TEMPO / music is clearly present.

HARD RULES:
- English only inside h3_prompt (no Chinese characters). Times use two decimals: 00:07.00. Clock starts at 00:00 for this part.
- Use the measured hard cuts / dissolve candidates / onsets / breath gaps (segment-local) as timestamp anchors; confirm on the sheets.
  Hard cuts -> "the camera cuts to"; verified dissolves -> "the shot transitions to (a 0.xx-second soft cross-dissolve)".
- Burned-in text, captions, speech bubbles, badges and stickers are post-production: never ask H3 to render text. For card/graphic shots
  write "Keep the upper third and the lower third calm and uncluttered for graphics added in post."
- Off-screen hands that move purposefully belong to a named subject (e.g. "<Subject 1>'s hands in cream knit sleeves").
- {"This is the LAST part: no CONTINUATION STATE." if last else "End detailed_description with: CONTINUATION STATE at 00:SS.SS: <exact pose/framing> - Part " + str(part_index + 2) + " opens on this state."}
- Total h3_prompt length 2500-6500 characters (hard limit 7000).
{refs}
Return ONLY valid JSON:
{{
  "h3_prompt": "the complete ready-to-paste English prompt",
  "hand_off_state": "{'' if last else 'one sentence: the final pose/framing (English)'}",
  "shots": [{{"start": 0.0, "end": 7.0, "transition_in": "none|cut|dissolve", "summary": "short description in {_lang(language)}"}}],
  "warnings": ["anything uncertain, in {_lang(language)}"]
}}
"""
