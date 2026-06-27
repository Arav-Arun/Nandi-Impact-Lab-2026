"""Telegram intake adapter — a thin webhook over the shared pipeline.

Deliberately small: parse a Telegram update, funnel its text (or voice note)
through pipeline.ingest() — which mock-extracts when no Claude key is set — and
ack the family with their case id. The real conversational flow + Postgres
pipeline replace pipeline.ingest()'s internals later; this adapter stays as-is.

Wire-up once deployed (needs TELEGRAM_BOT_TOKEN):
  POST https://<host>/api/v1/telegram/set-webhook?url=https://<host>
  (registers <host>/api/v1/telegram/webhook with Telegram)
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request

from app.api.responses import ok
from app.config import settings
from app.models.schemas import IntakeMessage
from app.services import pipeline

log = logging.getLogger("nandi.telegram")
router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])

_API = "https://api.telegram.org/bot{token}/{method}"
_GREETING = "🪷 NANDI: describe the missing person — name, age, and where they were last seen."


async def _call(method: str, payload: dict) -> dict | None:
    """Call the Telegram Bot API. No-op (returns None) when no token is set."""
    token = settings.telegram_bot_token
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(_API.format(token=token, method=method), json=payload)
        return r.json()


async def _voice_url(file_id: str) -> str | None:
    data = await _call("getFile", {"file_id": file_id})
    if data and data.get("ok"):
        return f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{data['result']['file_path']}"
    return None


@router.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = msg.get("text") or msg.get("caption")

    audio_url = None
    if msg.get("voice"):
        audio_url = await _voice_url(msg["voice"]["file_id"])

    if not text and not audio_url:
        await _call("sendMessage", {"chat_id": chat_id, "text": _GREETING})
        return ok({"skipped": True})

    report = await pipeline.ingest(IntakeMessage(
        channel="telegram",
        text=text,
        audio_url=audio_url,
        sender_ref=str(chat_id) if chat_id is not None else None,
    ))
    await _call("sendMessage", {
        "chat_id": chat_id,
        "text": f"🪷 Registered. Case {report.case_id}. NANDI's team will follow up.",
    })
    return ok({"case_id": report.case_id, "channel": "telegram"})


@router.post("/set-webhook")
async def set_webhook(url: str):
    """Convenience: point Telegram at <url>/api/v1/telegram/webhook."""
    res = await _call("setWebhook", {"url": url.rstrip("/") + "/api/v1/telegram/webhook"})
    if res is None:
        return ok({"set": False, "reason": "TELEGRAM_BOT_TOKEN not set"})
    return ok(res)
