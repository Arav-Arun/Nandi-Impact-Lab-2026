"""WhatsApp (Twilio) intake adapter — thin inbound webhook + TwiML reply.

Twilio posts each inbound WhatsApp message here as form-encoded data; we funnel
Body (and any voice note) through pipeline.ingest() and reply with TwiML, so the
ack needs no outbound credentials. Voice-note download uses the Twilio creds when
present. Small + dummy on purpose; the real pipeline lands later.

Wire-up (Twilio WhatsApp sandbox → "When a message comes in", HTTP POST):
  https://<host>/api/v1/whatsapp/webhook
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.models.schemas import IntakeMessage
from app.services import pipeline

log = logging.getLogger("nandi.whatsapp")
router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])

_GREETING = "🪷 NANDI: please describe the missing person — name, age, and where they were last seen."


def _twiml(text: str) -> Response:
    body = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{text}</Message></Response>"
    return Response(content=body, media_type="application/xml")


@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (str(form.get("Body") or "")).strip()
    sender = form.get("From")  # e.g. "whatsapp:+9198XXXXXXXX"

    audio_url = None
    if int(form.get("NumMedia") or 0) > 0 and str(form.get("MediaContentType0", "")).startswith("audio"):
        audio_url = form.get("MediaUrl0")

    if not body and not audio_url:
        return _twiml(_GREETING)

    auth = None
    if settings.twilio_account_sid and settings.twilio_auth_token:
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)

    report = await pipeline.ingest(
        IntakeMessage(
            channel="whatsapp",
            text=body or None,
            audio_url=audio_url,
            reporter_mobile=sender.replace("whatsapp:", "") if sender else None,
            sender_ref=sender,
        ),
        audio_auth=auth,
    )
    return _twiml(f"🪷 Registered. Case {report.case_id}. NANDI's team will follow up shortly.")
