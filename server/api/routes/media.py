"""
api.routes.media — voice-note transcription + person-photo upload/serving (M2).

  POST /api/v1/media/transcribe     multipart `file` → {transcript, language_code}
  POST /api/v1/media/upload         multipart `file` (image) → {photo_url, filename}
  GET  /api/v1/media/file/{name}    serve a stored person photo

Transcription uses services.sarvam (auto language detection; mock without a key).
Photos are stored locally via services.media_store and referenced from a report's
`photo_url`. The uploaded image is also embedded (face vector) at intake time so it
joins the matching pipeline — see services.intake_pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from core.responses import ApiError, ok
from services import media_store, sarvam

router = APIRouter(prefix="/media", tags=["media"])

# Guard rails for uploads (photos are optional everywhere — SoW §12.8 #5).
_MAX_BYTES = 8 * 1024 * 1024  # 8 MB
_ALLOWED_PREFIX = "image/"

_MEDIA_TYPE_BY_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif", ".heic": "image/heic",
}


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await file.read()
    result = await sarvam.stt(
        audio,
        filename=file.filename or "audio.wav",
        content_type=file.content_type or "audio/wav",
    )
    return ok(result)


@router.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    """
    Store an uploaded person photo and return its `photo_url`.

    The caller then passes `photo_url` to the intake routes; the intake pipeline
    re-reads the bytes to compute and store the face embedding (SoW §6 re-rank).
    """
    if file.content_type and not file.content_type.startswith(_ALLOWED_PREFIX):
        raise ApiError("BAD_IMAGE", "uploaded file must be an image")
    data = await file.read()
    if not data:
        raise ApiError("EMPTY_IMAGE", "uploaded image is empty")
    if len(data) > _MAX_BYTES:
        raise ApiError("IMAGE_TOO_LARGE", "image exceeds 8 MB limit")
    photo_url, filename = media_store.save_photo(data, file.content_type)
    return ok({"photo_url": photo_url, "filename": filename})


@router.get("/file/{name}")
async def serve_photo(name: str):
    """Serve a stored person photo by filename."""
    path = media_store.path_for(name)
    if path is None or not path.exists():
        raise ApiError("PHOTO_NOT_FOUND", "photo not found", 404)
    media_type = _MEDIA_TYPE_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)
