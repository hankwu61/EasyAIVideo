"""Project file layout helpers.

data/projects/<project_id>/
    scenes/<scene_id>/audio_<token>.mp3 | image_<token>.png | clip_<token>.mp4 | overlay.png | segment_<token>.mp4
    output/final_<token>.mp4
Relative paths stored in models always start with the project id.
"""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import Optional

from ..config import BGM_DIR, PROJECTS_DIR


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def abs_path(rel: str) -> Path:
    return PROJECTS_DIR / rel


def scene_rel(project_id: str, scene_id: str, stem: str, ext: str) -> str:
    return f"{project_id}/scenes/{scene_id}/{stem}_{secrets.token_hex(3)}.{ext}"


def output_rel(project_id: str, stem: str, ext: str) -> str:
    return f"{project_id}/output/{stem}_{secrets.token_hex(3)}.{ext}"


def remove(rel: Optional[str]) -> None:
    if not rel:
        return
    try:
        abs_path(rel).unlink(missing_ok=True)
    except OSError:
        pass


def delete_project_files(project_id: str) -> None:
    shutil.rmtree(project_dir(project_id), ignore_errors=True)


def safe_child(base: Path, relative: str) -> Path:
    """Resolve `relative` under `base`, rejecting path traversal."""
    target = (base / relative).resolve()
    if base.resolve() not in target.parents and target != base.resolve():
        raise ValueError("invalid path")
    return target


def bgm_path(name: Optional[str]) -> Optional[Path]:
    if not name:
        return None
    path = safe_child(BGM_DIR, name)
    return path if path.exists() else None
