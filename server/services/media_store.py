"""
services.media_store — local photo storage for missing/found person images.

The SoW targets S3 + presigned URLs (M4), but no AWS credentials are wired in the
hackathon box, so photos are persisted to a local directory and served back
through the API (api.routes.media). This keeps the *contract* identical to the S3
plan — intake stores a `photo_url` string on the report, the matcher passes it to
the operator, and the embedding pipeline reads the bytes to compute a face vector
— while working with zero cloud setup. Swapping in S3 later only changes this file.

Public surface:
    save_photo(data, content_type) -> (photo_url, filename)
    read_photo(filename)           -> bytes | None
    path_for(filename)             -> Path | None   (None if the name is unsafe)
    PHOTO_URL_PREFIX               -> "/api/v1/media/file"
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from core.logging_utils import get_logger

log = get_logger("nandi.media_store")

# media/photos/ under the server package root (sibling of api/, services/).
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media" / "photos"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Photos are served back under this API path (proxied by the frontend dev server).
PHOTO_URL_PREFIX = "/api/v1/media/file"

# content-type → extension (kept tiny + explicit; unknown types fall back to .bin).
_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
}

# Only ever serve simple uuid-style filenames — never anything with path parts.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]+$")


def _ext_for(content_type: str | None) -> str:
    return _EXT_BY_TYPE.get((content_type or "").lower().split(";")[0].strip(), ".bin")


def save_photo(data: bytes, content_type: str | None) -> tuple[str, str]:
    """
    Persist image bytes and return (photo_url, filename).

    `photo_url` is the API path the frontend renders directly; `filename` is the
    stable token stored alongside it so the embedding pipeline can re-read bytes.
    """
    filename = f"{uuid.uuid4().hex}{_ext_for(content_type)}"
    (MEDIA_ROOT / filename).write_bytes(data)
    log.info("stored photo %s (%d bytes)", filename, len(data))
    return f"{PHOTO_URL_PREFIX}/{filename}", filename


def filename_from_url(photo_url: str | None) -> str | None:
    """Extract the stored filename from a photo_url we minted (None otherwise)."""
    if not photo_url:
        return None
    name = photo_url.rstrip("/").rsplit("/", 1)[-1]
    return name if _SAFE_NAME.match(name) else None


def path_for(filename: str) -> Path | None:
    """Resolve a safe filename to its on-disk path (None if the name is unsafe)."""
    if not filename or not _SAFE_NAME.match(filename):
        return None
    return MEDIA_ROOT / filename


def read_photo(filename: str) -> bytes | None:
    """Read stored image bytes by filename (None if missing/unsafe)."""
    p = path_for(filename)
    if p is None or not p.exists():
        return None
    return p.read_bytes()


def read_photo_by_url(photo_url: str | None) -> bytes | None:
    """Convenience: read the bytes behind a stored photo_url (None if absent)."""
    name = filename_from_url(photo_url)
    return read_photo(name) if name else None
