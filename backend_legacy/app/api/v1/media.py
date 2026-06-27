"""Media endpoints — voice in / voice out via Sarvam."""
from __future__ import annotations

import base64

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.api.responses import err, ok
from app.services import pipeline, sarvam

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Web mic → Sarvam STT. Returns the native transcript + detected language."""
    audio = await file.read()
    if not audio:
        return err("EMPTY_AUDIO", "No audio received", 400)
    result = await pipeline.transcribe(
        audio, filename=file.filename or "audio.webm",
        content_type=file.content_type or "audio/webm",
    )
    lang = result.get("language_code")
    return ok({
        "transcript": result.get("transcript", ""),
        "language_code": lang,
        "language_name": sarvam.LANG_NAME.get(lang or "", None),
        "language_probability": result.get("language_probability", 0.0),
        "mock": result.get("mock", False),
    })


class TTSIn(BaseModel):
    text: str
    language_code: str = "mr-IN"


@router.post("/tts")
async def text_to_speech(body: TTSIn):
    audio = await sarvam.tts(body.text, language_code=body.language_code)
    if not audio:
        return err("TTS_UNAVAILABLE", "TTS not available (no Sarvam key)", 503)
    return ok({"audio_b64": base64.b64encode(audio).decode(), "mime": "audio/mp3"})
