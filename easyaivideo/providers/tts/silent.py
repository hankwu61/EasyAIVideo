"""Silent TTS: produces silence whose length approximates the spoken duration (offline testing)."""

from __future__ import annotations

import re
from pathlib import Path

from ...services import ffmpeg
from ..base import VoiceInfo


def estimate_duration(text: str, speed: float = 1.0) -> float:
    cjk = len(re.findall(r"[぀-ヿ㐀-鿿가-힯]", text))
    words = len(re.findall(r"[A-Za-z0-9']+", text))
    seconds = cjk / 4.0 + words / 2.6
    return max(1.5, seconds / max(speed, 0.1))


class SilentTTS:
    name = "silent"

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> Path:
        await ffmpeg.make_silence(output_path, estimate_duration(text, speed))
        return output_path

    async def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(id="silent", name="Silent (no voice)", locale="any")]

    async def test(self) -> str:
        return "Silent TTS active (no voice-over will be produced)."
