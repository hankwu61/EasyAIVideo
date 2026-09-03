"""Draw the transparent title/subtitle overlay for one scene (or one spoken line)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .fonts import load_font, wrap_text

ACCENT = (196, 181, 253, 255)


def render_overlay(
    output: Path,
    width: int,
    height: int,
    *,
    title: Optional[str],
    subtitle: Optional[str],
    speaker: Optional[str] = None,
    font_path: str = "",
    subtitle_size: int = 56,
) -> Path:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    portrait = height > width
    max_w = int(width * 0.86)

    if title:
        size = int(subtitle_size * (1.35 if portrait else 1.2))
        font = load_font(size, font_path)
        lines = wrap_text(title, font, max_w)[:2]
        line_h = int(size * 1.3)
        y = int(height * (0.07 if portrait else 0.06))
        for line in lines:
            w = font.getlength(line)
            x = (width - w) / 2
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 140))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=max(2, size // 14), stroke_fill=(0, 0, 0, 255))
            y += line_h

    if subtitle:
        size = subtitle_size
        font = load_font(size, font_path)
        lines = wrap_text(subtitle, font, max_w)[:4]
        line_h = int(size * 1.35)
        block_h = line_h * len(lines)
        block_w = int(max(font.getlength(line) for line in lines))
        speaker_font = load_font(int(size * 0.72), font_path) if speaker else None
        speaker_h = int(size * 0.72 * 1.4) if speaker else 0
        if speaker and speaker_font is not None:
            block_w = max(block_w, int(speaker_font.getlength(speaker)))
        bottom = int(height * (0.82 if portrait else 0.90))
        top = bottom - block_h - speaker_h
        pad_x, pad_y = int(size * 0.6), int(size * 0.35)
        box = [
            (width - block_w) // 2 - pad_x,
            top - pad_y,
            (width + block_w) // 2 + pad_x,
            bottom + pad_y,
        ]
        draw.rounded_rectangle(box, radius=int(size * 0.35), fill=(0, 0, 0, 115))
        y = top
        if speaker and speaker_font is not None:
            w = speaker_font.getlength(speaker)
            draw.text(((width - w) / 2, y), speaker, font=speaker_font, fill=ACCENT, stroke_width=2, stroke_fill=(0, 0, 0, 220))
            y += speaker_h
        for line in lines:
            w = font.getlength(line)
            draw.text(((width - w) / 2, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=max(2, size // 18), stroke_fill=(0, 0, 0, 230))
            y += line_h

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, "PNG")
    return output
