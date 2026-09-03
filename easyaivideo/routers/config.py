from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body

from .. import __version__
from ..config import config_manager
from ..models import TestResult
from ..providers.registry import test_provider
from ..services import ffmpeg

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/health")
async def health() -> dict[str, Any]:
    warnings = config_manager.warnings()
    has_ffmpeg = ffmpeg.available()
    if not has_ffmpeg:
        warnings.insert(0, "ffmpeg not found on PATH; rendering will fail.")
    return {"status": "ok", "version": __version__, "ffmpeg": has_ffmpeg, "config_valid": has_ffmpeg, "warnings": warnings}


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return config_manager.masked()


@router.put("/config")
async def put_config(patch: dict[str, Any] = Body(...)) -> dict[str, Any]:
    config_manager.update(patch)
    return config_manager.masked()


@router.post("/config/test/{kind}", response_model=TestResult)
async def test_config(kind: str) -> TestResult:
    started = time.perf_counter()
    try:
        message = await test_provider(config_manager.get(), kind)
        ok = True
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        message, ok = str(exc), False
    return TestResult(ok=ok, message=message, elapsed_ms=int((time.perf_counter() - started) * 1000))
