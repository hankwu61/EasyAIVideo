from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from ..config import BGM_DIR, PROJECTS_DIR
from ..services.storage import safe_child

router = APIRouter(prefix="/api/files", tags=["files"])
_UNSAFE = re.compile(r'[\\/:*?"<>|\r\n]+')


def attachment_headers(filename: str) -> dict[str, str]:
    """Content-Disposition with an ASCII fallback plus RFC 5987 UTF-8 name (CJK titles)."""
    clean = _UNSAFE.sub("_", filename).strip() or "download"
    stem, dot, ext = clean.rpartition(".")
    if not dot:
        stem, ext = clean, ""
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem.encode("ascii", "ignore").decode()).strip("_ .")
    if not re.search(r"[A-Za-z0-9]", ascii_stem):
        ascii_stem = "download"
    ascii_name = ascii_stem + (f".{ext}" if ext else "")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(clean)}"}


@router.get("/{project_id}/{path:path}")
async def get_file(
    project_id: str,
    path: str,
    download: Optional[str] = Query(None, description="Set to a filename (or '1') to download as an attachment"),
) -> FileResponse:
    base = BGM_DIR if project_id == "_bgm" else PROJECTS_DIR / project_id
    try:
        target = safe_child(base, path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid path") from exc
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    headers = {"Cache-Control": "private, max-age=3600"}
    if download:
        name = target.name if download == "1" else download
        if not name.lower().endswith(target.suffix.lower()):
            name += target.suffix
        headers.update(attachment_headers(name))
    return FileResponse(target, headers=headers)
