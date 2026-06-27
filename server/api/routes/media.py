"""
api.routes.media — voice-note transcription for the intake recorder (M2).

  POST /api/v1/media/transcribe   multipart `file` → {transcript, language_code}

Uses services.sarvam (Sarvam STT, auto language detection). With no SARVAM key it
returns a deterministic mock transcript so the recorder flow works in the demo.
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from core.responses import ok
from services import sarvam

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await file.read()
    result = await sarvam.stt(
        audio,
        filename=file.filename or "audio.wav",
        content_type=file.content_type or "audio/wav",
    )
    return ok(result)
