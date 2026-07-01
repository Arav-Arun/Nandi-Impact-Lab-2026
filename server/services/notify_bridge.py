"""
services.notify_bridge - match-notification orchestration.

On a confirmed match, `POST /match/confirm` generates an OTP (services.otp) and
tells the family where to collect their relative. The family's only stored
contact is the missing report's `filed_by_phone`:

  • `tg:<chat_id>`  → they filed via Telegram; we message them there.
  • a phone number  → no live outbound channel (SMS is not wired in this
                      deployment), so the operator reads the code out at the booth.

Returns which channel actually delivered so the route can tell the operator the
truth (no silent "sent" when nothing was sent).
"""

from __future__ import annotations

from core.logging_utils import get_logger, mask_phone
from services import notify
from services.otp import generate_and_store

log = get_logger(__name__)


async def generate_otp(case_id: str) -> str:
    """Generate + store a 4-digit OTP for `case_id` (Redis, TTL = OTP_TTL_SECONDS)."""
    return await generate_and_store(case_id)


async def notify_family_of_match(
    *, filed_by_phone: str | None, booth_name: str, zone_name: str, otp: str
) -> tuple[bool, str]:
    """
    Tell the family a match was found and where to go.

    Returns (delivered, channel) where channel is "telegram" (message sent) or
    "onscreen" (no outbound channel - operator conveys the code in person).
    """
    where = booth_name or "NANDI Booth"
    if booth_name and zone_name:
        where = f"{booth_name} ({zone_name})"
    elif zone_name:
        where = zone_name

    text = (
        f"NANDI: We may have found your family member. Please come to {where}. "
        f"Verification code: {otp}.\n"
        f"नंदी: तुमची व्यक्ती सापडली असावी. कृपया {where} येथे या. पडताळणी कोड: {otp}."
    )

    if filed_by_phone and filed_by_phone.startswith("tg:"):
        chat_id = filed_by_phone[3:]
        delivered = await notify.send_telegram(chat_id, text)
        log.info("match notify via telegram chat=%s delivered=%s", chat_id, delivered)
        return delivered, "telegram"

    log.info(
        "match notify: no outbound channel for %s - operator reads code on-screen",
        mask_phone(filed_by_phone or ""),
    )
    return False, "onscreen"
