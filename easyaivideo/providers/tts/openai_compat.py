"""OpenAI-style /audio/speech TTS provider."""

from __future__ import annotations

from pathlib import Path

import httpx

from ...config import TTSConfig
from ...presets import OPENAI_VOICES
from ..base import ProviderError, VoiceInfo


class OpenAICompatTTS:
    name = "openai_compat"

    def __init__(self, cfg: TTSConfig) -> None:
        self.cfg = cfg
        if not cfg.base_url:
            raise ProviderError("TTS base_url is empty.")

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> Path:
        url = self.cfg.base_url.rstrip("/") + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        body = {"model": self.cfg.model or "tts-1", "input": text, "voice": voice or "alloy", "speed": speed, "response_format": "mp3"}
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"TTS request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"TTS HTTP {resp.status_code}: {resp.text[:300]}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        return output_path

    async def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(id=v, name=v.capitalize(), locale="multi") for v in OPENAI_VOICES]

    async def test(self) -> str:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mp3"
            await self.synthesize("Hello", self.cfg.voice or "alloy", 1.0, path)
            return f"TTS OK ({path.stat().st_size} bytes)"
