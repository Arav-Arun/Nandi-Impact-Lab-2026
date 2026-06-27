"""
services.sms — match-notification SMS sender (Member 2).

`services/notify_bridge.py` (M1) auto-detects this module and calls
`send_match_notification(phone, booth_name, zone_name, otp)` on a confirmed
match — the ONLY path that ever notifies a family (SoW §12.8 #1). Sends the
Marathi reunite SMS via MSG91; when no MSG91 key is set it logs a masked no-op
and returns False so confirmation still succeeds.
"""

from __future__ import annotations

import httpx

from core.config import settings
from core.logging_utils import get_logger, mask_phone

log = get_logger("nandi.sms")

# Marathi: "Good news — your missing family member has been found at {booth}
# ({zone}). Reference (OTP): {otp}. Please go there and tell the OTP to collect them."
_TEMPLATE = (
    "NANDI: तुमचे हरवलेले कुटुंबीय {booth} ({zone}) येथे सुरक्षित आहेत. "
    "ओळख क्रमांक (OTP): {otp}. कृपया तेथे जाऊन OTP सांगा."
)


async def send_match_notification(phone: str, booth_name: str, zone_name: str, otp: str) -> bool:
    """Send the Marathi match SMS. Returns True only if handed to a real sender."""
    body = _TEMPLATE.format(booth=booth_name or "booth", zone=zone_name or "", otp=otp)

    if not settings.MSG91_AUTH_KEY:
        log.info("[stub] match SMS suppressed (no MSG91_AUTH_KEY): to=%s booth=%s zone=%s otp=%s",
                 mask_phone(phone), booth_name, zone_name, otp)
        return False

    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://control.msg91.com/api/v5/flow/",
                headers={"authkey": settings.MSG91_AUTH_KEY, "Content-Type": "application/json"},
                json={
                    "sender": settings.MSG91_SENDER_ID,
                    "short_url": "0",
                    "mobiles": digits,
                    "message": body,
                },
            )
            r.raise_for_status()
    except Exception as exc:
        log.warning("MSG91 send failed for %s (%s)", mask_phone(phone), exc)
        return False

    log.info("match SMS dispatched to %s (booth=%s)", mask_phone(phone), booth_name)
    return True
