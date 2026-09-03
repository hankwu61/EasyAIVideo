"""Split a user-provided script into narration segments."""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+|(?<=\n)")


def split_script(text: str, language: str, max_len: int | None = None) -> list[str]:
    cjk = language.startswith("zh") or language in ("ja", "ko")
    limit = max_len or (42 if cjk else 170)
    text = text.replace("\r", "")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    segments: list[str] = []
    for para in paragraphs:
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(para) if s and s.strip()]
        current = ""
        for sentence in sentences:
            if not current:
                current = sentence
            elif len(current) + len(sentence) + (0 if cjk else 1) <= limit:
                current = current + ("" if cjk else " ") + sentence
            else:
                segments.append(current)
                current = sentence
        if current:
            segments.append(current)
    # very long single sentences: hard-split so TTS/subtitles stay readable
    out: list[str] = []
    for seg in segments:
        while len(seg) > limit * 2:
            cut = seg.rfind("，" if cjk else ",", 0, limit * 2)
            if cut <= 0:
                cut = limit * 2
            out.append(seg[: cut + 1].strip())
            seg = seg[cut + 1 :].strip()
        if seg:
            out.append(seg)
    return out
