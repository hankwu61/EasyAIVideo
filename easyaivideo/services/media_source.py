"""Retain provider-hosted image URLs for APIs that require public media."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


def save_source(path: Path, url: str) -> None:
    path.with_suffix(path.suffix + ".source.json").write_text(json.dumps({
        "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }), encoding="utf-8")


def public_source(path: Path) -> str | None:
    try:
        data = json.loads(path.with_suffix(path.suffix + ".source.json").read_text(encoding="utf-8"))
        url = data["url"]
        parsed = urlsplit(url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            return None
        if data["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
            return None
        return url
    except (OSError, ValueError, KeyError, TypeError):
        return None
