"""Aspect-ratio exact size computation (mirrors ArcReel's aspect_size idea)."""

from __future__ import annotations

import math
from typing import Optional


def reduce_ratio(width: int, height: int) -> tuple[int, int]:
    g = math.gcd(width, height) or 1
    return width // g, height // g


def aspect_size(
    width: int,
    height: int,
    short_edge: int,
    *,
    round_to: int = 8,
    max_long_edge: Optional[int] = None,
) -> tuple[int, int]:
    """Return (w, h) with exactly the aspect of width:height, both divisible by round_to,
    short edge as close as possible to short_edge, long edge capped at max_long_edge."""
    aw, ah = reduce_ratio(width, height)
    unit_w, unit_h = aw * round_to, ah * round_to
    short_unit = min(unit_w, unit_h)
    t = max(1, round(short_edge / short_unit))
    w, h = unit_w * t, unit_h * t
    if max_long_edge and max(w, h) > max_long_edge:
        t = max(1, max_long_edge // max(unit_w, unit_h))
        w, h = unit_w * t, unit_h * t
    return w, h


VIDEO_TIER_SHORT_EDGE = {"480p": 480, "720p": 720, "1080p": 1080}
