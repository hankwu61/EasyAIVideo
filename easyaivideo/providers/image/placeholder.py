"""Placeholder image provider: draws a gradient card locally (no AI, fully offline)."""

from __future__ import annotations

import asyncio
import colorsys
import hashlib
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter

from ...services.fonts import load_font, wrap_text


def _palette(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    hue = (h % 360) / 360.0
    c1 = colorsys.hsv_to_rgb(hue, 0.55, 0.55)
    c2 = colorsys.hsv_to_rgb((hue + 0.12) % 1.0, 0.65, 0.25)
    return tuple(int(c * 255) for c in c1), tuple(int(c * 255) for c in c2)  # type: ignore[return-value]


def draw_placeholder(prompt: str, width: int, height: int, output_path: Path, seed: Optional[int] = None) -> Path:
    c1, c2 = _palette(prompt)
    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    rng = random.Random(seed if seed is not None else prompt)
    glow = Image.new("RGB", (width, height), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for _ in range(6):
        r = rng.randint(width // 6, width // 2)
        x, y = rng.randint(-r // 2, width), rng.randint(-r // 2, height)
        gdraw.ellipse([x, y, x + r, y + r], fill=tuple(rng.randint(40, 120) for _ in range(3)))
    glow = glow.filter(ImageFilter.GaussianBlur(width // 10))
    img = Image.blend(img, Image.composite(glow, img, Image.new("L", (width, height), 110)), 0.6)

    draw = ImageDraw.Draw(img)
    font = load_font(int(min(width, height) * 0.045))
    lines = wrap_text(prompt, font, int(width * 0.78))[:6]
    line_h = int(font.size * 1.4)
    total_h = line_h * len(lines)
    y = (height - total_h) // 2
    for line in lines:
        w = font.getlength(line)
        draw.text(((width - w) / 2, y), line, font=font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        y += line_h
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


class PlaceholderImage:
    name = "placeholder"

    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        output_path: Path,
        seed: Optional[int] = None,
        reference_images: Optional[list[Path]] = None,
    ) -> Path:
        return await asyncio.to_thread(draw_placeholder, prompt, width, height, output_path, seed)

    async def test(self) -> str:
        return "Placeholder image provider active (no AI images)."
