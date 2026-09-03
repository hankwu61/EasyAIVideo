"""Provider protocols. Every provider family has one small async interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol


class ProviderError(RuntimeError):
    """Raised when a provider call fails in a way the user should see."""


@dataclass
class VoiceInfo:
    id: str
    name: str
    locale: str
    gender: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "locale": self.locale, "gender": self.gender}


@dataclass
class VideoRequest:
    prompt: str
    duration: float  # requested seconds (providers clamp to their own limits)
    width: int  # target canvas; providers derive their own exact size from the aspect
    height: int
    fps: int
    output_path: Path
    start_image: Optional[Path] = None  # image-to-video first frame
    end_image: Optional[Path] = None  # first+last frame mode
    reference_images: list[Path] = field(default_factory=list)
    seed: Optional[int] = None


class LLMProvider(Protocol):
    name: str

    async def complete(self, prompt: str, *, system: Optional[str] = None) -> str: ...

    async def complete_json(self, prompt: str, *, system: Optional[str] = None) -> dict[str, Any]: ...

    async def test(self) -> str: ...


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> Path: ...

    async def list_voices(self) -> list[VoiceInfo]: ...

    async def test(self) -> str: ...


class ImageProvider(Protocol):
    name: str

    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        output_path: Path,
        seed: Optional[int] = None,
        reference_images: Optional[list[Path]] = None,
    ) -> Path: ...

    async def test(self) -> str: ...


class VideoProvider(Protocol):
    name: str

    async def generate(self, request: VideoRequest) -> Path: ...

    async def test(self) -> str: ...
