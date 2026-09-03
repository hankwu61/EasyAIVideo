"""Microsoft Edge neural TTS (free, online) via the edge-tts package."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ...presets import EDGE_VOICES
from ..base import ProviderError, VoiceInfo


def speed_to_rate(speed: float) -> str:
    return f"{int(round((speed - 1.0) * 100)):+d}%"


class EdgeTTS:
    name = "edge"

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> Path:
        import edge_tts

        output_path.parent.mkdir(parents=True, exist_ok=True)
        last: Exception | None = None
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice or "zh-TW-HsiaoChenNeural", rate=speed_to_rate(speed))
                await asyncio.wait_for(communicate.save(str(output_path)), timeout=90)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
                raise ProviderError("Edge TTS produced an empty file.")
            except Exception as exc:  # noqa: BLE001 - retry on any transient network error
                last = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise ProviderError(f"Edge TTS failed: {last}")

    async def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(id=v[0], name=v[1], locale=v[2], gender=v[3]) for v in EDGE_VOICES]

    async def test(self) -> str:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mp3"
            await self.synthesize("Hello", "en-US-AriaNeural", 1.0, path)
            return f"Edge TTS OK ({path.stat().st_size} bytes)"
