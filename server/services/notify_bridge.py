"""
services.notify_bridge — Member 1 ↔ Member 2 hand-off for match notifications.

WHY THIS EXISTS
---------------
`POST /match/confirm` (M1) must, on confirmation, generate an OTP and send the
family an SMS. OTP + SMS are Member 2's domain (services/otp.py, services/sms.py).
This bridge calls M2's functions WHEN THEY EXIST and degrades to a safe local
fallback when they don't — so the confirm flow is testable today and "just works"
the moment M2 merges, with no changes to the route.

CONTRACT FOR MEMBER 2 (implement these exact signatures):

    # services/otp.py
    async def generate_and_store(case_id: str) -> str:
        '''4-digit OTP, stored in Redis at key f"otp:{case_id}",
           TTL = settings.OTP_TTL_SECONDS. Returns the OTP.'''

    # services/sms.py
    async def send_match_notification(
        phone: str, booth_name: str, zone_name: str, otp: str
    ) -> bool:
        '''Send the Marathi match SMS via MSG91 (Gupshup fallback).
           Returns True on accepted-for-delivery.'''

Both may be sync or async — this bridge awaits coroutines and calls plain
functions transparently.
"""

from __future__ import annotations

import inspect
import secrets
from typing import Any

from core.config import settings
from core.logging_utils import get_logger, mask_phone
from core.redis_client import redis_client

log = get_logger(__name__)


async def _maybe_await(value: Any) -> Any:
    """Await `value` if it is a coroutine, else return it as-is."""
    if inspect.isawaitable(value):
        return await value
    return value


async def generate_otp(case_id: str) -> str:
    """
    Get an OTP for a case — via M2's services.otp if present, else a dev fallback.

    The fallback stores a 4-digit OTP in Redis at `otp:{case_id}` with the agreed
    TTL, so M2's verify-otp endpoint reads the same key once they merge.
    """
    try:
        from services import otp as m2_otp  # type: ignore

        if hasattr(m2_otp, "generate_and_store"):
            return str(await _maybe_await(m2_otp.generate_and_store(case_id)))
    except Exception as exc:  # module missing or raised — fall through to fallback
        log.debug("M2 otp service unavailable (%s); using dev fallback.", exc)

    code = f"{secrets.randbelow(10000):04d}"
    try:
        await redis_client.set(f"otp:{case_id}", code, ex=settings.OTP_TTL_SECONDS)
    except Exception as exc:  # Redis down — OTP still returned for the operator
        log.warning("could not persist OTP for case %s (%s).", case_id, exc)
    return code


async def send_match_sms(*, phone: str, booth_name: str, zone_name: str, otp: str) -> bool:
    """
    Send the match SMS via M2's services.sms if present; otherwise log a no-op.

    Returns True if the message was handed to a real sender, False if it was only
    logged (dev / pre-M2-merge). Either way the match is already recorded — the
    SMS is best-effort and never blocks confirmation.
    """
    # Distinguish "M2 hasn't merged yet" (normal — info) from "M2 is present but
    # its sender raised" (a real problem — warning).
    try:
        from services import sms as m2_sms  # type: ignore
    except ImportError:
        m2_sms = None  # type: ignore

    if m2_sms is not None and hasattr(m2_sms, "send_match_notification"):
        try:
            result = await _maybe_await(
                m2_sms.send_match_notification(phone, booth_name, zone_name, otp)
            )
            return bool(result)
        except Exception as exc:
            log.warning("M2 sms send failed (%s); SMS not sent.", exc)
            return False

    log.info(
        "[dev] match SMS suppressed (M2 sms service not present yet): to=%s booth=%s zone=%s",
        mask_phone(phone),
        booth_name,
        zone_name,
    )
    return False
