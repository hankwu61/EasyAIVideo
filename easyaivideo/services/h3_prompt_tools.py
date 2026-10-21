"""Self-checks for MiniMax H3 prompts (video-to-h3-prompt skill, step 10 / pitfalls checklist)."""

from __future__ import annotations

import math
import re

H3_PROMPT_LIMIT = 7000

REF2VA_SECTIONS = (
    "subject_definitions:",
    "summary:",
    "retention_analysis:",
    "detailed_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
)
FIELD14_SECTIONS = (
    "subject_definitions:",
    "integrated_multimodal_description:",
    "camera_direction:",
    "negative_constraints:",
    "overall_soundscape:",
    "non_diegetic_music:",
)

_CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
_STAMP = re.compile(r"\b(?:At|at)\s+(\d{1,2}):(\d{2}(?:\.\d{1,3})?)")
_SHOT1 = re.compile(r"\[Shot 1\]\s*(?:At\s+\d)", re.IGNORECASE)


def request_duration(seconds: float, model: str = "MiniMax-H3") -> int:
    """Integer seconds to ask H3 for so the output can be trimmed down to ``seconds``."""
    lo = 5 if model == "MiniMax-H3-Max" else 4
    return int(max(lo, min(15, math.ceil(seconds - 0.05))))


def timestamps(text: str) -> list[float]:
    return [int(m.group(1)) * 60 + float(m.group(2)) for m in _STAMP.finditer(text)]


def validate_h3_prompt(text: str, *, mode: str = "ref2va", duration: float | None = None) -> list[str]:
    """Return human-readable (zh-TW) warnings; an empty list means the prompt passed every check."""
    warnings: list[str] = []
    body = text or ""
    if not body.strip():
        return ["H3 提示詞為空。"]
    if len(body) > H3_PROMPT_LIMIT:
        warnings.append(f"提示詞 {len(body)} 字元，超過 H3 上限 {H3_PROMPT_LIMIT}，送出前需刪減。")
    cjk = _CJK.findall(body)
    if cjk:
        warnings.append(f"提示詞含 {len(cjk)} 個中文字元（H3 可執行內容應為全英文）：{''.join(cjk[:12])}…")
    sections = REF2VA_SECTIONS if mode.lower() == "ref2va" else FIELD14_SECTIONS
    missing = [s for s in sections if s not in body]
    if missing:
        warnings.append("缺少段落：" + ", ".join(missing))
    if _SHOT1.search(body):
        warnings.append("[Shot 1] 不應帶時間戳。")
    stamps = timestamps(body)
    if any(b < a - 1e-6 for a, b in zip(stamps, stamps[1:])):
        warnings.append("時間戳未嚴格遞增。")
    if duration is not None and stamps and max(stamps) > duration + 0.05:
        warnings.append(f"時間戳 {max(stamps):.2f}s 超出段長 {duration:.2f}s（每段應從 00:00 重新計時）。")
    if re.search(r"\b\d{2,3}\s*BPM\b", body, re.IGNORECASE) and "N/A" in body.split("non_diegetic_music:")[-1]:
        warnings.append("無 BGM 卻寫了 BPM。")
    return warnings
