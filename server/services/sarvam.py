"""
services.sarvam - Sarvam AI: native Indian-language speech-to-text + translation (M2).

Used by the intake layer to turn a voice note (Telegram / WhatsApp / web recorder)
into text the extractor and matcher can use. When SARVAM_API_KEY is absent every
call returns a deterministic mock so intake and the demo keep working with no key.
"""

from __future__ import annotations

import httpx

from core.config import settings
from core.logging_utils import get_logger

log = get_logger("nandi.sarvam")

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
    return {"api-subscription-key": settings.SARVAM_API_KEY or ""}


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
    """Translate text to `target` (English by default for the match layer)."""
    if not settings.sarvam_enabled or not text:
        return text
    payload = {"input": text, "source_language_code": source,
               "target_language_code": target, "model": "mayura:v1"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{BASE}/translate", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json().get("translated_text", text)
