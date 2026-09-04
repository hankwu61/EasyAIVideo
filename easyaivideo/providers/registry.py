"""Build provider instances from the current config (re-read on every call for hot reload)."""

from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from .base import ImageProvider, LLMProvider, ProviderError, TTSProvider, VideoProvider


def get_llm(cfg: AppConfig) -> LLMProvider:
    if cfg.llm.provider == "openai_compat":
        from .llm.openai_compat import OpenAICompatLLM

        return OpenAICompatLLM(cfg.llm)
    from .llm.mock import MockLLM

    return MockLLM()


def get_tts(cfg: AppConfig) -> TTSProvider:
    if cfg.tts.provider == "edge":
        from .tts.edge import EdgeTTS

        return EdgeTTS()
    if cfg.tts.provider == "openai_compat":
        from .tts.openai_compat import OpenAICompatTTS

        return OpenAICompatTTS(cfg.tts)
    from .tts.silent import SilentTTS

    return SilentTTS()


def get_image(cfg: AppConfig) -> ImageProvider:
    if cfg.image.provider == "openai_compat":
        from .image.openai_compat import OpenAICompatImage

        return OpenAICompatImage(cfg.image)
    if cfg.image.provider == "comfyui":
        from .image.comfyui import ComfyUIImage

        return ComfyUIImage(cfg.image)
    from .image.placeholder import PlaceholderImage

    return PlaceholderImage()


def get_video(cfg: AppConfig) -> Optional[VideoProvider]:
    """Returns an AI video provider, or None when clips are animated locally (kenburns)."""
    if cfg.video.provider == "comfyui":
        from .video.comfyui import ComfyUIVideo

        return ComfyUIVideo(cfg.video)
    if cfg.video.provider == "agnes":
        from .video.agnes import AgnesVideo

        return AgnesVideo(cfg.video)
    return None


def get_vision(cfg: AppConfig):
    if cfg.llm.provider == "mock" and not cfg.review.model:
        from .llm.vision import MockVision

        return MockVision()
    from .llm.vision import OpenAICompatVision

    return OpenAICompatVision(cfg)


async def test_provider(cfg: AppConfig, kind: str) -> str:
    if kind == "llm":
        return await get_llm(cfg).test()
    if kind == "review":
        return await get_vision(cfg).test()
    if kind == "tts":
        return await get_tts(cfg).test()
    if kind == "image":
        return await get_image(cfg).test()
    if kind == "video":
        provider = get_video(cfg)
        if provider is None:
            return "Video provider 'kenburns' uses ffmpeg only; nothing to test."
        return await provider.test()
    if kind == "comfyui":
        from .comfyui import ComfyUIClient

        url = cfg.image.comfyui_url if cfg.image.provider == "comfyui" else cfg.video.comfyui_url
        try:
            stats = await ComfyUIClient(url).stats()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Cannot reach ComfyUI at {url}: {exc}") from exc
        version = stats.get("system", {}).get("comfyui_version", "?")
        return f"ComfyUI online at {url} (version {version})"
    raise ProviderError(f"Unknown provider kind: {kind}")
