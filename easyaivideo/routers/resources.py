from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..config import BGM_DIR, WORKFLOWS_DIR, config_manager
from ..presets import ASPECT_RATIOS, CONTENT_MODES, INPUT_MODES, KINDS, LANGUAGES, LLM_PRESETS, MOTIONS, STYLES, VIDEO_MODES
from ..providers.registry import get_tts

router = APIRouter(prefix="/api/resources", tags=["resources"])
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


@router.get("/presets")
async def presets() -> dict[str, Any]:
    return {
        "aspect_ratios": ASPECT_RATIOS,
        "languages": LANGUAGES,
        "motions": MOTIONS,
        "input_modes": INPUT_MODES,
        "llm_presets": LLM_PRESETS,
        "content_modes": CONTENT_MODES,
        "kinds": KINDS,
        "video_modes": VIDEO_MODES,
    }


@router.get("/styles")
async def styles() -> list[dict[str, str]]:
    return STYLES


@router.get("/voices")
async def voices() -> list[dict[str, str]]:
    try:
        provider = get_tts(config_manager.get())
        return [v.to_dict() for v in await provider.list_voices()]
    except Exception:  # noqa: BLE001
        return []


@router.get("/bgm")
async def bgm() -> list[dict[str, str]]:
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in BGM_DIR.iterdir() if p.suffix.lower() in AUDIO_EXT)
    return [{"name": p.name, "url": f"/api/files/_bgm/{p.name}"} for p in files]


@router.get("/workflows")
async def workflows() -> dict[str, list[str]]:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in WORKFLOWS_DIR.glob("*.json"))
    return {
        "image": [n for n in names if n.startswith("image_")],
        "video": [n for n in names if n.startswith("video_")],
    }
