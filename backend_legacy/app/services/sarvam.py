"""Sarvam AI integration — native Indian-language speech & text.

Endpoints (header auth: `api-subscription-key`):
  POST /speech-to-text   multipart: file, model=saaras:v3, language_code=unknown
  POST /translate        json: input, source_language_code, target_language_code
  POST /text-to-speech   json: text, target_language_code, model, speaker -> audios[b64]

When SARVAM_API_KEY is absent every call returns a deterministic mock so the rest
of the pipeline (and the demo) keeps working without a key.
"""
from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings

log = logging.getLogger("nandi.sarvam")
BASE = "https://api.sarvam.ai"
_TIMEOUT = httpx.Timeout(45.0)

# Sarvam language codes ↔ display names used across NANDI.
LANG_NAME = {
    "hi-IN": "Hindi", "mr-IN": "Marathi", "bn-IN": "Bengali", "te-IN": "Telugu",
    "ta-IN": "Tamil", "kn-IN": "Kannada", "gu-IN": "Gujarati", "ml-IN": "Malayalam",
    "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English",
}

_MOCK_TRANSCRIPT = (
    "माझे वडील हरवले आहेत. ते ७२ वर्षांचे आहेत, भगवा कुर्ता घातला आहे. "
    "रामकुंड घाटाजवळ शेवटचे दिसले. माझा नंबर ९८७६५४३२१०."
)


def _headers() -> dict:
    return {"api-subscription-key": settings.sarvam_api_key or ""}


async def stt(audio: bytes, filename: str = "audio.wav", content_type: str = "audio/wav") -> dict:
    """Transcribe speech in any of 22 Indian languages, auto-detecting the language."""
    if not settings.sarvam_enabled:
        return {"transcript": _MOCK_TRANSCRIPT, "language_code": "mr-IN",
                "language_probability": 0.0, "mock": True}
    data = {"model": "saaras:v3", "language_code": "unknown"}
    files = {"file": (filename, audio, content_type)}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{BASE}/speech-to-text", headers=_headers(), data=data, files=files)
        r.raise_for_status()
        body = r.json()
    return {
        "transcript": body.get("transcript", ""),
        "language_code": body.get("language_code") or "unknown",
        "language_probability": body.get("language_probability", 0.0),
    }


async def translate(text: str, target: str = "en-IN", source: str = "auto") -> str:
    """Translate text to `target`. Used to normalize to English for the match layer."""
    if not settings.sarvam_enabled or not text:
        return text
    payload = {"input": text, "source_language_code": source,
               "target_language_code": target, "model": "mayura:v1"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{BASE}/translate", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json().get("translated_text", text)


async def tts(text: str, language_code: str = "mr-IN", speaker: str | None = None) -> bytes | None:
    """Synthesize a spoken reply in the user's language (for the bots). Returns mp3 bytes."""
    if not settings.sarvam_enabled or not text:
        return None
    payload = {
        "text": text[:1400],
        "target_language_code": language_code if language_code in LANG_NAME else "hi-IN",
        "model": "bulbul:v2",
        "output_audio_codec": "mp3",
    }
    if speaker:
        payload["speaker"] = speaker
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{BASE}/text-to-speech", headers=_headers(), json=payload)
        r.raise_for_status()
        audios = r.json().get("audios", [])
    return base64.b64decode(audios[0]) if audios else None
