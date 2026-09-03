"""Font discovery (CJK capable) and text wrapping for PIL."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import ImageFont

from ..config import RESOURCES_DIR

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc",  # Microsoft JhengHei (Traditional Chinese)
    "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei (Simplified Chinese)
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


@lru_cache(maxsize=8)
def find_font(preferred: str = "") -> Optional[str]:
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    fonts_dir = RESOURCES_DIR / "fonts"
    if fonts_dir.exists():
        candidates += [str(p) for p in sorted(fonts_dir.iterdir()) if p.suffix.lower() in (".ttf", ".ttc", ".otf")]
    candidates += FONT_CANDIDATES
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def load_font(size: int, preferred: str = "") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = find_font(preferred)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def _tokens(text: str) -> list[str]:
    """Split into wrap units: words for space-delimited text, characters for CJK."""
    if re.search(r"[぀-ヿ㐀-鿿가-힯]", text):
        out: list[str] = []
        for chunk in re.split(r"(\s+)", text):
            if not chunk:
                continue
            if chunk.isspace():
                out.append(" ")
            elif re.search(r"[぀-ヿ㐀-鿿가-힯]", chunk):
                out.extend(list(chunk))
            else:
                out.append(chunk)
        return out
    return re.split(r"(\s+)", text)


def wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        current = ""
        for tok in _tokens(paragraph):
            if not tok:
                continue
            candidate = current + tok
            if font.getlength(candidate.strip()) <= max_width or not current.strip():
                current = candidate
            else:
                lines.append(current.strip())
                current = tok.lstrip()
        if current.strip():
            lines.append(current.strip())
    return lines or [""]
