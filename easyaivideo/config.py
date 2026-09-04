"""Configuration: YAML file on disk, editable at runtime from the web UI."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("EASYAIVIDEO_DATA_DIR", ROOT_DIR / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
BGM_DIR = DATA_DIR / "bgm"
WORKFLOWS_DIR = DATA_DIR / "workflows" / "comfyui"
RESOURCES_DIR = ROOT_DIR / "resources"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
CONFIG_PATH = Path(os.environ.get("EASYAIVIDEO_CONFIG", ROOT_DIR / "config.yaml"))
DB_PATH = DATA_DIR / "easyaivideo.db"

SECRET_MASK = "***"
SECRET_FIELDS = {"api_key"}


class LLMConfig(BaseModel):
    provider: Literal["openai_compat", "mock"] = "mock"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = Field(0.8, ge=0.0, le=2.0)


class TTSConfig(BaseModel):
    provider: Literal["edge", "openai_compat", "silent"] = "edge"
    voice: str = "zh-TW-HsiaoChenNeural"
    speed: float = Field(1.0, ge=0.5, le=2.0)
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "tts-1"


class ImageConfig(BaseModel):
    provider: Literal["placeholder", "openai_compat", "comfyui"] = "placeholder"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "dall-e-3"
    size_portrait: str = "1024x1792"
    size_landscape: str = "1792x1024"
    size_square: str = "1024x1024"
    # "preset" sends size_portrait/landscape/square (DALL-E style fixed sizes);
    # "exact" sends a WxH computed from the project aspect ratio and short_edge (Agnes, gpt-image proxies ...).
    size_mode: Literal["preset", "exact"] = "preset"
    short_edge: int = Field(1024, ge=512, le=2160)
    # Send character sheets as image-to-image references (Agnes image models support an `image` list).
    use_references: bool = False
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_workflow: str = "image_default.json"
    prompt_prefix: str = ""
    negative_prompt: str = "text, watermark, logo, blurry, low quality, deformed"


class VideoConfig(BaseModel):
    # kenburns = ffmpeg animation of stills; comfyui = local image-to-video workflow;
    # agnes = Agnes AI async /v1/videos (text-to-video, image-to-video, first+last frame)
    provider: Literal["kenburns", "comfyui", "agnes"] = "kenburns"
    api_key: str = ""
    base_url: str = "https://apihub.agnes-ai.com/v1"
    model: str = "agnes-video-v2.0"
    resolution: Literal["480p", "720p", "1080p"] = "720p"
    mode: Literal["i2v", "t2v", "keyframes"] = "i2v"
    max_clip_seconds: int = Field(10, ge=1, le=18)
    concurrency: int = Field(1, ge=1, le=4)
    poll_timeout: int = Field(1800, ge=60, le=7200)
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_workflow: str = "video_default.json"
    fps: int = Field(30, ge=15, le=60)


class RenderConfig(BaseModel):
    font_path: str = ""
    subtitle_size: int = Field(56, ge=20, le=140)
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0)
    crf: int = Field(23, ge=15, le=35)
    ffmpeg_path: str = ""


class ReviewConfig(BaseModel):
    """AI review of the rendered video: keyframes + narration -> multimodal model.

    Empty api_key / base_url / model fall back to the LLM settings, so an OpenAI-compatible
    multimodal chat model (Agnes, GPT-4o, Qwen-VL, Gemini via proxy ...) is all that is needed.
    """

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    frames_per_scene: int = Field(2, ge=1, le=3)
    frame_width: int = Field(768, ge=256, le=1920)
    concurrency: int = Field(2, ge=1, le=4)


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    image: ImageConfig = ImageConfig()
    video: VideoConfig = VideoConfig()
    render: RenderConfig = RenderConfig()
    review: ReviewConfig = ReviewConfig()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class ConfigManager:
    """Thread-safe holder of the application config with load/save/update."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._config = AppConfig()
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> AppConfig:
        with self._lock:
            return self._config

    def load(self) -> AppConfig:
        with self._lock:
            raw: dict[str, Any] = {}
            if self._path.exists():
                raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
            self._config = AppConfig.model_validate(raw)
            if not self._path.exists():
                self.save()
            return self._config

    def save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                yaml.safe_dump(self._config.model_dump(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def update(self, patch: dict[str, Any]) -> AppConfig:
        """Deep-merge a partial config; masked secrets keep their stored value."""
        with self._lock:
            current = self._config.model_dump()
            cleaned = self._strip_masked(patch, current)
            merged = _deep_merge(current, cleaned)
            self._config = AppConfig.model_validate(merged)
            self.save()
            return self._config

    @staticmethod
    def _strip_masked(patch: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in patch.items():
            if isinstance(value, dict):
                out[key] = ConfigManager._strip_masked(value, current.get(key, {}) or {})
            elif key in SECRET_FIELDS and value == SECRET_MASK:
                continue
            else:
                out[key] = value
        return out

    def masked(self) -> dict[str, Any]:
        def mask(node: Any) -> Any:
            if isinstance(node, dict):
                return {
                    k: (SECRET_MASK if k in SECRET_FIELDS and v else mask(v))
                    for k, v in node.items()
                }
            return node

        with self._lock:
            return mask(self._config.model_dump())

    def warnings(self) -> list[str]:
        cfg = self.get()
        out: list[str] = []
        if cfg.llm.provider == "mock":
            out.append("LLM provider is 'mock': scripts are not AI-written. Configure an LLM in Settings.")
        elif not cfg.llm.api_key and "localhost" not in cfg.llm.base_url and "127.0.0.1" not in cfg.llm.base_url:
            out.append("LLM api_key is empty.")
        if cfg.image.provider == "placeholder":
            out.append("Image provider is 'placeholder': scenes use generated gradient cards instead of AI images.")
        if cfg.tts.provider == "silent":
            out.append("TTS provider is 'silent': videos will have no voice-over.")
        if cfg.video.provider == "agnes" and not cfg.video.api_key:
            out.append("Video provider is 'agnes' but video.api_key is empty.")
        return out


config_manager = ConfigManager(CONFIG_PATH)


def ensure_dirs() -> None:
    for d in (DATA_DIR, PROJECTS_DIR, BGM_DIR, WORKFLOWS_DIR):
        d.mkdir(parents=True, exist_ok=True)
