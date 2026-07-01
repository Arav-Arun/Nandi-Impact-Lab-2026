"""
api.routes.webhooks - Telegram intake channel (M2).

Auto-mounted under /api/v1. Inbound messages (text or voice) are transcribed
if needed (services.sarvam), structured (services.extraction), and funneled
through services.intake_pipeline.file_missing - the same path as the web form, so
graph sync / dedup / audit / live feed all happen identically.

  POST /api/v1/telegram/webhook   Telegram Bot API updates  (+ /set-webhook helper)
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response

from core.config import settings
from core.database import AsyncSessionLocal
from core.logging_utils import get_logger
from core.responses import ok
from services import blast, extraction, intake_pipeline, sarvam

log = get_logger("nandi.webhooks")
router = APIRouter(tags=["webhooks"])

_GREETING = (
    "🪷 NANDI: describe the missing person - name, age, and where they were last seen. "
    "You can also send a voice note in your language."
)


async def _file_from_message(*, text: str | None, audio_url: str | None,
                             filed_by_phone: str, channel: str,
                             subscriber_address: str | None = None,
                             audio_auth: tuple[str, str] | None = None) -> str:
    """Transcribe (if audio) → extract → file a missing report; also opt the sender
    into zone blasts on their channel. Returns the report id."""
    detected_language = None
    body = text or ""
    if audio_url:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            r = await client.get(audio_url, auth=audio_auth)
            r.raise_for_status()
            stt = await sarvam.stt(r.content, filename="voice.ogg",
                                   content_type=r.headers.get("content-type", "audio/ogg"))
        body = (body + " " + stt["transcript"]).strip()
        detected_language = stt.get("language_code")

    ex = await extraction.extract(body, detected_language=detected_language)
    async with AsyncSessionLocal() as session:
        report = await intake_pipeline.file_missing(
            session,
            filed_by_phone=ex.reporter_mobile or filed_by_phone,
            physical_description=ex.physical_description or body,
            subject_name=ex.subject_name,
            subject_age=ex.subject_age,
            subject_gender=ex.subject_gender,
            last_seen_landmark=ex.last_seen_landmark,
            language_spoken=ex.language_spoken,
            origin_city=ex.origin_city,
            channel=channel,
        )
        # opt the sender into blasts for the report's zone, on the channel they used
        if subscriber_address:
            await blast.upsert_subscriber(
                session, channel=channel, address=subscriber_address,
                zone_id=report.last_seen_zone_id, language=ex.language_spoken,
            )
        await session.commit()
        return str(report.id)


# ── Telegram ────────────────────────────────────────────────────────────────
_TG_API = "https://api.telegram.org/bot{token}/{method}"


async def _tg_call(method: str, payload: dict) -> dict | None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(_TG_API.format(token=token, method=method), json=payload)
        return r.json()


async def _tg_voice_url(file_id: str) -> str | None:
    data = await _tg_call("getFile", {"file_id": file_id})
    if data and data.get("ok"):
        return f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{data['result']['file_path']}"
    return None


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = msg.get("text") or msg.get("caption")
    audio_url = await _tg_voice_url(msg["voice"]["file_id"]) if msg.get("voice") else None

    if not text and not audio_url:
        await _tg_call("sendMessage", {"chat_id": chat_id, "text": _GREETING})
        return ok({"skipped": True})

    report_id = await _file_from_message(
        text=text, audio_url=audio_url,
        filed_by_phone=f"tg:{chat_id}", channel="telegram",
        subscriber_address=str(chat_id),
    )
    await _tg_call("sendMessage", {
        "chat_id": chat_id,
        "text": f"🪷 Registered. Case {report_id[:8]}. NANDI's team will follow up.",
    })
    return ok({"id": report_id, "channel": "telegram"})


@router.post("/telegram/set-webhook")
async def telegram_set_webhook(url: str):
    """Point Telegram at <url>/api/v1/telegram/webhook (needs TELEGRAM_BOT_TOKEN)."""
    res = await _tg_call("setWebhook", {"url": url.rstrip("/") + "/api/v1/telegram/webhook"})
    if res is None:
        return ok({"set": False, "reason": "TELEGRAM_BOT_TOKEN not set"})
    return ok(res)

