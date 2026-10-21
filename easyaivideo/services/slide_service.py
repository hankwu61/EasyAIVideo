"""Presentation / Slide-to-Video service.

Handles:
- PPTX slide export to 1080p PNG images (PowerPoint COM on Windows with fallbacks)
- PPTX speaker notes extraction (python-pptx)
- Companion Markdown Speaker Guide parsing
- Natural spoken dialogue cleaning
- Sentence-level proportional subtitle calculation
- Synchronized master SRT generation
- Scene initialization for presentation projects
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pptx import Presentation

from ..models import Project, Scene
from . import storage

log = logging.getLogger("easyaivideo.slide")

PRE_PAD_SECONDS = 0.4
POST_PAD_SECONDS = 0.5


# ---------------------------------------------------------
# TEXT CLEANING & NORMALIZATION
# ---------------------------------------------------------
def clean_speech_text(raw_text: str) -> str:
    """Clean markdown formatting, code blocks, and symbols for natural spoken TTS."""
    if not raw_text:
        return ""

    text = raw_text

    # Remove code blocks and inline code
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove markdown bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)

    # Remove markdown blockquotes and headers
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)

    # Remove markdown list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Convert directional arrows to natural oral connectors
    text = text.replace("->", "，接著")
    text = text.replace("→", "，接著")
    text = text.replace("=>", "，也就是")
    text = text.replace("⇒", "，也就是")

    # Remove non-BMP emojis and common UI icons
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    for sym in ["🎯", "💡", "📌", "⚠️", "✅", "🔥", "🚀", "📊", "🛠️", "⚙️", "✨", "🎬", "🎙️", "📝", "👏"]:
        text = text.replace(sym, "")

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------
# SPEAKER GUIDE & NOTES PARSING
# ---------------------------------------------------------
def parse_duration_seconds(val_str: Optional[str]) -> Optional[float]:
    """Parse time string like '01:30', '90s', '1分30秒', '2min' into seconds."""
    if not val_str:
        return None
    val = val_str.strip()
    m = re.search(r"(\d+)\s*[:：]\s*(\d+)", val)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m_min = re.search(r"(\d+(?:\.\d+)?)\s*(?:分|分鐘|min)", val)
    m_sec = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|sec|s\b)", val)
    if m_min or m_sec:
        mins = float(m_min.group(1)) if m_min else 0.0
        secs = float(m_sec.group(1)) if m_sec else 0.0
        return mins * 60 + secs
    return None


def strip_guide_metadata(raw_text: str) -> str:
    """Strip out metadata headers and non-speech sections (title, action, goal, transition)."""
    lines = []
    skip_block = False
    for line in raw_text.splitlines():
        stripped = line.strip()
        # Strip metadata lines: - **標題**：, - **預估時長**：, etc.
        if re.match(
            r"^[-*]?\s*\**\s*(?:標題|預估時長|時長|核心目標|目標|重點|畫面動作|操作提示|演練操作指引|轉場|轉場語|視覺指引|視覺引導與操作提示|口播逐字講稿|章節/頁面轉場語|投影片資訊)\s*\**[：:]",
            stripped,
        ):
            continue
        # Strip block headers like #### 【畫面動作】, #### 【轉場】, etc.
        if re.match(
            r"^#{1,6}\s*【?(?:畫面動作|演練操作指引|操作指引|視覺指引|視覺引導與操作提示|轉場|轉場語|章節/頁面轉場語|Action|Transition)】?",
            stripped,
        ):
            skip_block = True
            continue
        # Re-enter speech block when reaching script headers
        if re.match(
            r"^#{1,6}\s*【?(?:逐字稿|逐字講稿|口播逐字講稿|講稿內容|講稿|Script|Narration)】?",
            stripped,
        ):
            skip_block = False
            continue
        if skip_block:
            continue
        lines.append(line)
    return "\n".join(lines)


def parse_speaker_guide(content: str) -> list[dict]:
    """Parse a Markdown speaker guide into a list of slide dicts with:
    - slide_num: int
    - title: str
    - clean_text: str (STRICTLY pure spoken script from 逐字稿)
    - target_duration: Optional[float]
    - goal: str (核心目標)
    - action: str (畫面動作)
    - transition: str (轉場說明)
    - calibrated_speed: Optional[float]
    """
    if not content or not content.strip():
        return []

    # Match sections like "### Slide 1: Title", "## Slide 1", "**Slide 1**"
    pattern = r"(?:###\s+Slide\s+(\d+):?|##\s+Slide\s+(\d+):?|\*\*Slide\s+(\d+)\*\*:?)\s*(.*?)\n(.*?)(?=(?:###\s+Slide\s+\d+|##\s+Slide\s+\d+|\*\*Slide\s+\d+\*\*|\Z))"
    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

    slides = []
    for m in matches:
        num_str = m[0] or m[1] or m[2]
        title = m[3].strip()
        body = m[4].strip()

        try:
            slide_num = int(num_str)
        except ValueError:
            continue

        # 1. Parse target duration (e.g. 01:30 -> 90s)
        dur_match = re.search(
            r"\*?\*?(?:預估時長|時長|預計時間|Duration)\*?\*?[：:]\s*([^\n]+)",
            body,
            re.IGNORECASE,
        )
        target_dur = parse_duration_seconds(dur_match.group(1)) if dur_match else None

        # 2. Parse core goal / focus (核心目標)
        goal_match = re.search(
            r"\*?\*?(?:核心目標|目標|重點|Goal)\*?\*?[：:]\s*([^\n]+)",
            body,
            re.IGNORECASE,
        )
        goal = goal_match.group(1).strip() if goal_match else ""

        # 3. Parse visual action guide (畫面動作)
        action_match = re.search(
            r"####\s*【?(?:畫面動作|演練操作指引|操作指引|視覺指引|視覺引導與操作提示|Action)】?\s*\n(.*?)(?=####|---|###|\Z)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        action = action_match.group(1).strip() if action_match else ""
        action_clean = clean_speech_text(action)

        # 4. Parse transition instructions (轉場語)
        trans_match = re.search(
            r"####\s*【?(?:轉場語|轉場|章節/頁面轉場語|Transition)】?\s*\n(.*?)(?=---|###|####|\Z)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        transition = trans_match.group(1).strip() if trans_match else ""

        # 5. Extract PURE spoken script (逐字稿) ONLY
        script_match = re.search(
            r"####\s*【?(?:逐字稿|逐字講稿|口播逐字講稿|講稿內容|講稿|Script|Narration)】?\s*\n(.*?)(?=####|---|###|\Z)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        if script_match:
            raw_script = script_match.group(1).strip()
        else:
            raw_script = strip_guide_metadata(body).strip()

        clean_text = clean_speech_text(raw_script)

        # 6. Calculate calibrated speech speed based on target duration
        speakable_chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", clean_text))
        calibrated_speed = None
        if target_dur and target_dur > 0 and speakable_chars > 0:
            est_normal_dur = speakable_chars / 3.8
            ratio = est_normal_dur / target_dur
            # Clamp between 0.85 and 1.25 for clear, intelligible audio
            calibrated_speed = round(max(0.85, min(1.25, ratio)), 2)

        slides.append({
            "slide_num": slide_num,
            "title": title,
            "raw_script": raw_script,
            "clean_text": clean_text,
            "target_duration": target_dur,
            "goal": goal,
            "action": action_clean,
            "transition": transition,
            "calibrated_speed": calibrated_speed,
        })

    return slides


def extract_pptx_slides_data(pptx_path: Path) -> list[dict]:
    """Extract slide titles, body text, and embedded speaker notes from a PPTX file."""
    prs = Presentation(str(pptx_path))
    slides_data = []

    for i, slide in enumerate(prs.slides, 1):
        # Extract title
        title = ""
        if slide.shapes.title and slide.shapes.title.text:
            title = slide.shapes.title.text.strip()

        # Extract body text from all shapes
        body_parts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                text = shape.text_frame.text.strip()
                if text:
                    body_parts.append(text)
        body_text = "\n".join(body_parts)

        # Extract embedded speaker notes
        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        # If title is empty, deduce from first line of body or notes
        if not title:
            if body_parts:
                title = body_parts[0].splitlines()[0][:40]
            elif notes_text:
                title = notes_text.splitlines()[0][:40]
            else:
                title = f"Slide {i}"

        clean_notes = clean_speech_text(notes_text)

        slides_data.append({
            "slide_num": i,
            "title": title,
            "body_text": body_text,
            "raw_notes": notes_text,
            "clean_text": clean_notes,
        })

    return slides_data


# ---------------------------------------------------------
# PPTX SLIDE EXPORT (POWERPOINT COM / FALLBACK)
# ---------------------------------------------------------
def export_pptx_slides(pptx_path: Path, output_dir: Path, width: int = 1920, height: int = 1080) -> list[Path]:
    """Export each slide from PPTX to a PNG image.

    Uses PowerPoint COM API on Windows for highest fidelity 1080p rendering.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    abs_pptx = pptx_path.resolve()

    # Try PowerPoint COM API on Windows
    exported = _export_via_powerpoint_com(abs_pptx, output_dir, width, height)
    if exported:
        return exported

    # Fallback to LibreOffice if installed
    exported = _export_via_libreoffice(abs_pptx, output_dir, width, height)
    if exported:
        return exported

    raise RuntimeError(
        "無法匯出 PPTX 投影片圖片。請確認本機已安裝 Microsoft PowerPoint，或安裝 LibreOffice。"
    )


def _export_via_powerpoint_com(pptx_path: Path, output_dir: Path, width: int, height: int) -> list[Path]:
    """Export slides using PowerPoint application in an isolated subprocess."""
    if os.name != "nt":
        return []

    log.info("Exporting PPTX slides via isolated PowerPoint COM process: %s", pptx_path)
    code = (
        "import sys, os\n"
        "import win32com.client\n"
        f"pptx = {repr(str(pptx_path))}\n"
        f"out_dir = {repr(str(output_dir))}\n"
        "ppt = win32com.client.Dispatch('PowerPoint.Application')\n"
        "try:\n"
        "    pres = ppt.Presentations.Open(pptx, WithWindow=False)\n"
        "    count = pres.Slides.Count\n"
        "    for i in range(1, count + 1):\n"
        "        target = os.path.join(out_dir, f'slide_{i:02d}.png')\n"
        f"        pres.Slides(i).Export(target, 'PNG', {width}, {height})\n"
        "    pres.Close()\n"
        "finally:\n"
        "    ppt.Quit()\n"
    )

    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    except Exception as exc:
        log.error("PowerPoint COM subprocess export failed: %s", exc)
        return []

    return sorted(output_dir.glob("slide_*.png"))


def _export_via_libreoffice(pptx_path: Path, output_dir: Path, width: int, height: int) -> list[Path]:
    """Fallback export converting PPTX to PDF using LibreOffice then rendering images."""
    import shutil
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return []

    try:
        # Convert to pdf
        cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        pdf_path = output_dir / f"{pptx_path.stem}.pdf"
        if not pdf_path.exists():
            return []

        # Convert pdf pages to images with pdftoppm if available
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            out_prefix = output_dir / "slide"
            cmd = [pdftoppm, "-png", "-r", "150", str(pdf_path), str(out_prefix)]
            subprocess.run(cmd, check=True, capture_output=True)
            images = sorted(output_dir.glob("slide-*.png"))
            pdf_path.unlink(missing_ok=True)
            return images

    except Exception as exc:
        log.warning("LibreOffice export failed: %s", exc)

    return []


# ---------------------------------------------------------
# SUBTITLE TIMING & SRT GENERATION
# ---------------------------------------------------------
def calculate_proportional_subtitles(text: str, total_duration: float) -> list[dict]:
    """Split narration text into natural spoken sentences and assign proportional timestamps."""
    if not text or not text.strip():
        return []

    # Split by sentence terminators, line breaks, semicolons, and commas (for long sentences)
    # First split by major terminators: 。！？!?\n；;
    raw_units = re.split(r"([。！？!?\n；;]+)", text)
    major_sentences = []
    for i in range(0, len(raw_units), 2):
        s = raw_units[i].strip()
        punct = raw_units[i + 1].strip() if i + 1 < len(raw_units) else ""
        full_s = (s + punct).strip()
        if full_s:
            major_sentences.append(full_s)

    # If any sentence is still longer than 32 characters, further split by commas
    sentences = []
    for s in major_sentences:
        if len(s) > 32 and any(p in s for p in ["，", ",", "、"]):
            parts = re.split(r"([，,、]+)", s)
            curr = ""
            for j in range(0, len(parts), 2):
                seg = parts[j].strip()
                p_mark = parts[j + 1].strip() if j + 1 < len(parts) else ""
                combined = (seg + p_mark).strip()
                if not curr:
                    curr = combined
                elif len(curr) + len(combined) <= 30:
                    curr += combined
                else:
                    sentences.append(curr)
                    curr = combined
            if curr:
                sentences.append(curr)
        else:
            sentences.append(s)

    if not sentences:
        return [{"start": 0.0, "end": total_duration, "text": text.strip()}]

    # Weight by character count plus small punctuation pauses
    weights = []
    for s in sentences:
        w = len(s) + s.count("，") * 1.5 + s.count("。") * 2.5 + s.count(",") * 1.5
        weights.append(max(w, 1.0))

    total_w = sum(weights)
    result = []
    curr_time = 0.0
    for s, w in zip(sentences, weights):
        dur = total_duration * (w / total_w)
        result.append({
            "start": round(curr_time, 3),
            "end": round(curr_time + dur, 3),
            "text": s,
        })
        curr_time += dur

    return result


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm SRT time format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_presentation_srt(slides_subtitles: list[dict], out_srt_path: Path, pre_pad: float = PRE_PAD_SECONDS) -> Path:
    """Generate master SRT subtitle file with cumulative timestamps across all presentation slides.

    Each item in slides_subtitles:
      {
        "slide_start": float,  # cumulative offset in video
        "sentences": [{"start": float, "end": float, "text": str}]
      }
    """
    srt_index = 1
    srt_lines = []

    for slide in slides_subtitles:
        slide_offset = slide.get("slide_start", 0.0) + pre_pad
        sentences = slide.get("sentences", [])

        for sent in sentences:
            text = sent.get("text", "").strip()
            if not text:
                continue
            start_t = slide_offset + sent["start"]
            end_t = slide_offset + sent["end"]

            srt_lines.append(str(srt_index))
            srt_lines.append(f"{format_srt_timestamp(start_t)} --> {format_srt_timestamp(end_t)}")
            srt_lines.append(text)
            srt_lines.append("")
            srt_index += 1

    out_srt_path.parent.mkdir(parents=True, exist_ok=True)
    out_srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return out_srt_path


# ---------------------------------------------------------
# PRESENTATION PROJECT INITIALIZATION
# ---------------------------------------------------------
def import_presentation(
    project: Project,
    pptx_path: Path,
    guide_content: Optional[str] = None,
) -> Project:
    """Import a PowerPoint presentation into a Project:

    1. Extract slide titles, text, and embedded speaker notes.
    2. Merge companion speaker guide if provided.
    3. Export slides to project scene image folders.
    4. Populate project.scenes with slide images and narration text.
    """
    project.input_mode = "slide"
    project_dir = storage.project_dir(project.id)
    temp_slides_dir = project_dir / "slides_exported"

    # Step 1: Extract slide notes and body text
    pptx_slides = extract_pptx_slides_data(pptx_path)
    if not pptx_slides:
        raise ValueError("簡報檔中沒有任何投影片。")

    # Step 2: Merge speaker guide if provided
    guide_slides = parse_speaker_guide(guide_content or "")
    guide_by_num = {s["slide_num"]: s for s in guide_slides}

    # Step 3: Export 1080p slide images
    exported_images = export_pptx_slides(pptx_path, temp_slides_dir, project.width, project.height)
    if len(exported_images) < len(pptx_slides):
        raise RuntimeError(
            f"匯出的投影片圖片數量 ({len(exported_images)}) 少於投影片總數 ({len(pptx_slides)})。"
        )

    # If title not set, use presentation Slide 1 title or filename
    if not project.title or project.title == "未命名" or project.title == project.id:
        if pptx_slides and pptx_slides[0]["title"]:
            project.title = pptx_slides[0]["title"][:40]
        else:
            project.title = pptx_path.stem[:40]

    # Reset scenes
    for s in project.scenes:
        for rel in (s.audio_path, s.image_path, s.video_path, s.segment_path):
            storage.remove(rel)
    project.scenes = []
    project.scene_counter = 0

    # Step 4: Create Scene for each slide
    import shutil
    for i, slide_info in enumerate(pptx_slides, 1):
        scene_id = project.next_scene_id()
        scene_dir = project_dir / "scenes" / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)

        # Copy exported slide image to scene directory
        src_img = exported_images[i - 1]
        dest_rel = storage.scene_rel(project.id, scene_id, "image", "png")
        dest_abs = storage.abs_path(dest_rel)
        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_img, dest_abs)

        # Determine narration text, calibrated speed, and context prompt:
        # Priority 1: External speaker guide
        # Priority 2: Embedded PPTX speaker notes
        # Priority 3: Empty (will be generated by LLM if needed)
        narration = ""
        tts_speed = None
        video_prompt = ""
        prompt_parts = [f"Slide {i}: {slide_info['title'] or f'Slide {i}'}"]

        if i in guide_by_num:
            g = guide_by_num[i]
            if g.get("clean_text"):
                narration = g["clean_text"]
            if g.get("calibrated_speed"):
                tts_speed = g["calibrated_speed"]
            if g.get("goal"):
                prompt_parts.append(f"重點: {g['goal']}")
            if g.get("action"):
                prompt_parts.append(f"畫面引導: {g['action']}")
                video_prompt = g["action"]
        elif slide_info["clean_text"]:
            narration = slide_info["clean_text"]

        scene = Scene(
            id=scene_id,
            index=i - 1,
            narration=narration,
            image_prompt=" | ".join(prompt_parts),
            video_prompt=video_prompt,
            image_path=dest_rel,
            image_stale=False,
            audio_stale=True,
            tts_speed=tts_speed,
            status="partial" if narration else "pending",
        )
        project.scenes.append(scene)

    # Clean up temp export dir
    try:
        shutil.rmtree(temp_slides_dir, ignore_errors=True)
    except Exception:
        pass

    project.n_scenes = len(project.scenes)
    return project
