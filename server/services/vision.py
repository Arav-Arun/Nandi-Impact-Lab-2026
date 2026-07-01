"""
services.vision - auto-describe an uploaded photo for search.

When a booth uploads a photo, an LLM turns it into a short operator-facing
description ("elderly man, blue kurta, glasses") that is folded into the report's
text embedding - so a photo becomes searchable alongside the spoken description.
Provider order: OpenAI → Anthropic. Returns None (logged no-op) with no key.
"""

from __future__ import annotations

import base64

from core.config import settings
from core.logging_utils import get_logger

log = get_logger("nandi.vision")

_PROMPT = (
    "Describe the person in this photo for a missing-persons search. Mention "
    "gender, approximate age, clothing colour/type, and any distinctive features "
    "(glasses, facial hair, cap, bag). Be concise and factual - under two "
    "sentences, in English. Do not guess identity or invent details."
)


async def describe_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str | None:
    """Short English description of the person, or None when vision is unavailable."""
    if not image_bytes:
        return None
    if settings.openai_enabled:
        desc = await _describe_openai(image_bytes, mime_type)
        if desc is not None:
            return desc
    if settings.claude_enabled:
        return await _describe_anthropic(image_bytes, mime_type)
    log.info("No LLM key set; skipping photo auto-description.")
    return None


async def _describe_openai(image_bytes: bytes, mime_type: str) -> str | None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    try:
        resp = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
        )
        return (resp.choices[0].message.content or "").strip() or None
    except Exception as exc:
        log.warning("OpenAI vision failed (%s)", exc)
        return None


async def _describe_anthropic(image_bytes: bytes, mime_type: str) -> str | None:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=150,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                {"type": "text", "text": _PROMPT},
            ]}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
        return text or None
    except Exception as exc:
        log.warning("Anthropic vision failed (%s)", exc)
        return None
