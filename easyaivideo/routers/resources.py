from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..config import BGM_DIR, WORKFLOWS_DIR, config_manager
from ..presets import (
    ASPECT_RATIOS,
    CONTENT_MODES,
    FONTS,
    INPUT_MODES,
    KINDS,
    LANGUAGES,
    LLM_PRESETS,
    MOTIONS,
    STYLES,
    SUBTITLE_POSITIONS,
    TRANSITIONS,
    VIDEO_MODES,
)
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
        "transitions": TRANSITIONS,
        "subtitle_positions": SUBTITLE_POSITIONS,
        "fonts": FONTS,
    }


@router.get("/transitions")
async def transitions() -> list[dict[str, str]]:
    return TRANSITIONS


@router.get("/subtitle-positions")
async def subtitle_positions() -> list[dict[str, str]]:
    return SUBTITLE_POSITIONS


@router.get("/fonts")
async def fonts() -> list[dict[str, str]]:
    return FONTS


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


@router.post("/bgm/upload")
async def upload_bgm(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "檔案名稱不可為空")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if f".{ext}" not in AUDIO_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支援的音訊格式，僅支援 {', '.join(sorted(AUDIO_EXT))}")
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)
    dest = BGM_DIR / safe_name
    content = await file.read()
    dest.write_bytes(content)
    return {"name": safe_name, "url": f"/api/files/_bgm/{safe_name}"}


@router.get("/workflows")
async def workflows() -> dict[str, list[str]]:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in WORKFLOWS_DIR.glob("*.json"))
    return {
        "image": [n for n in names if n.startswith("image_")],
        "video": [n for n in names if n.startswith("video_")],
    }
