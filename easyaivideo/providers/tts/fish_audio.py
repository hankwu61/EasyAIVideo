"""Fish Audio REST TTS with configurable Traditional Chinese voice presets."""

from pathlib import Path
import tempfile

import httpx

from ...config import TTSConfig
from ...presets import EDGE_VOICES
from ..base import ProviderError, VoiceInfo

FEMALE = "fish-zh-TW-female"
MALE = "fish-zh-TW-male"


class FishAudioTTS:
    name = "fish_audio"

    def __init__(self, cfg: TTSConfig) -> None:
        self.cfg = cfg

    def reference_id(self, voice: str) -> str:
        voice = voice or self.cfg.voice
        # Existing projects/characters may still hold an Edge voice after switching.
        edge_gender = next((g for vid, _, _, g in EDGE_VOICES if vid == voice), None)
        if edge_gender:
            voice = MALE if edge_gender == "Male" else FEMALE
        if voice not in (FEMALE, MALE):
            voice = self.cfg.voice if self.cfg.voice in (FEMALE, MALE) else FEMALE
        gender = "male" if voice == MALE else "female"
        reference = getattr(self.cfg.fish_audio, f"{gender}_reference_id").strip()
        if not reference:
            label = "男聲" if voice == MALE else "女聲"
            raise ProviderError(f"請在設定填入 Fish Audio 繁體中文{label} Voice ID。")
        return reference

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> Path:
        cfg = self.cfg.fish_audio
        if not cfg.api_key.strip():
            raise ProviderError("請在設定填入 Fish Audio API Key。")
        if not cfg.base_url.strip() or not cfg.model.strip():
            raise ProviderError("Fish Audio Base URL / model 不可空白。")
        body = {"text": text, "reference_id": self.reference_id(voice),
                "format": "mp3", "prosody": {"speed": speed}}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    cfg.base_url.rstrip("/") + "/tts",
                    headers={"Authorization": f"Bearer {cfg.api_key}", "model": cfg.model},
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("Fish Audio 連線失敗，請檢查網路與 API 網址。") from exc
        if response.status_code == 402:
            raise ProviderError(
                "Fish Audio HTTP 402：API 額度不足或需要付款。"
                "API 額度與網站平台額度分開計算，請至 "
                "https://fish.audio/app/developers 查看 API 餘額或儲值後重試。"
            )
        if response.status_code == 401:
            raise ProviderError("Fish Audio HTTP 401：API Key 無效或已失效，請檢查金鑰。")
        if response.status_code >= 400:
            raise ProviderError(f"Fish Audio HTTP {response.status_code}：請檢查 API Key、額度與 Voice ID。")
        if not response.content or "json" in response.headers.get("content-type", ""):
            raise ProviderError("Fish Audio 未回傳有效音訊。")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    async def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(FEMALE, "繁體中文 女聲 (Fish Audio)", "zh-TW", "Female"),
                VoiceInfo(MALE, "繁體中文 男聲 (Fish Audio)", "zh-TW", "Male")]

    async def test(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mp3"
            await self.synthesize("你好，這是繁體中文配音測試。", self.cfg.voice, self.cfg.speed, path)
            return f"Fish Audio OK ({path.stat().st_size} bytes)"
