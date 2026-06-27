"""
services.notify — one multi-channel sender: SMS · WhatsApp · Telegram · Email (M2).

Each channel is feature-flagged on its keys in core.config. A channel with no key
configured logs a masked no-op and returns False, so the match-notification and
location-blast paths always run regardless of which providers are wired up.

    await notify.send("whatsapp", "+9198...", "text")
    await notify.send("email", "a@b.com", "body", subject="...")

All senders return True only when the message was handed to a real provider.
"""

from __future__ import annotations

import asyncio
import re
import smtplib
from email.mime.text import MIMEText

import httpx

from core.config import settings
from core.logging_utils import get_logger, mask_phone

log = get_logger("nandi.notify")
_TIMEOUT = httpx.Timeout(20.0)


def _from_email() -> tuple[str, str]:
    """Parse EMAIL_FROM ('Name <addr>' or 'addr') into (display, address)."""
    m = re.match(r"\s*(.*?)\s*<\s*([^>]+)\s*>\s*$", settings.EMAIL_FROM)
    if m:
        return m.group(1) or "NANDI", m.group(2)
    return "NANDI", settings.EMAIL_FROM.strip()


async def _twilio_message(*, to: str, body: str, from_: str) -> bool:
    sid, token = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    if not (sid and token and from_):
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"To": to, "From": from_, "Body": body},
            )
            r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("twilio send to %s failed (%s)", mask_phone(to), exc)
        return False


async def send_sms(to: str, text: str) -> bool:
    """Send an SMS via Twilio (if a Twilio number is set) else MSG91."""
    if settings.TWILIO_SMS_FROM and settings.TWILIO_ACCOUNT_SID:
        if await _twilio_message(to=to, body=text, from_=settings.TWILIO_SMS_FROM):
            return True
    if settings.MSG91_AUTH_KEY:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://control.msg91.com/api/v5/flow/",
                    headers={"authkey": settings.MSG91_AUTH_KEY, "Content-Type": "application/json"},
                    json={"sender": settings.MSG91_SENDER_ID, "short_url": "0",
                          "mobiles": "".join(c for c in to if c.isdigit()), "message": text},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            log.warning("msg91 send to %s failed (%s)", mask_phone(to), exc)
            return False
    log.info("[stub] SMS suppressed (no SMS provider): to=%s", mask_phone(to))
    return False


async def send_whatsapp(to: str, text: str) -> bool:
    if not settings.whatsapp_enabled:
        log.info("[stub] WhatsApp suppressed (no Twilio): to=%s", mask_phone(to))
        return False
    addr = to if str(to).startswith("whatsapp:") else f"whatsapp:{to}"
    return await _twilio_message(to=addr, body=text, from_=settings.TWILIO_WHATSAPP_FROM)


async def send_telegram(chat_id: str, text: str) -> bool:
    if not settings.telegram_enabled:
        log.info("[stub] Telegram suppressed (no bot token): chat=%s", chat_id)
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("telegram send to chat %s failed (%s)", chat_id, exc)
        return False


async def send_email(to: str, text: str, subject: str = "NANDI") -> bool:
    display, addr = _from_email()
    # 1) Resend
    if settings.RESEND_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json={"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "text": text},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            log.warning("resend email to %s failed (%s)", to, exc)
    # 2) SendGrid
    if settings.SENDGRID_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
                    json={"personalizations": [{"to": [{"email": to}]}],
                          "from": {"email": addr, "name": display},
                          "subject": subject,
                          "content": [{"type": "text/plain", "value": text}]},
                )
                r.raise_for_status()
            return True
        except Exception as exc:
            log.warning("sendgrid email to %s failed (%s)", to, exc)
    # 3) SMTP
    if settings.SMTP_HOST and settings.SMTP_USER:
        try:
            await asyncio.to_thread(_smtp_send, to, subject, text, addr)
            return True
        except Exception as exc:
            log.warning("smtp email to %s failed (%s)", to, exc)
            return False
    log.info("[stub] email suppressed (no email provider): to=%s", to)
    return False


def _smtp_send(to: str, subject: str, text: str, from_addr: str) -> None:
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
        s.starttls()
        s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.sendmail(from_addr, [to], msg.as_string())


async def send(channel: str, to: str, text: str, subject: str = "NANDI") -> bool:
    """Dispatch to the right channel sender. `to` is phone / chat_id / email."""
    if channel == "sms":
        return await send_sms(to, text)
    if channel == "whatsapp":
        return await send_whatsapp(to, text)
    if channel == "telegram":
        return await send_telegram(to, text)
    if channel == "email":
        return await send_email(to, text, subject=subject)
    log.warning("unknown channel %s", channel)
    return False
