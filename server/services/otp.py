"""
services.otp — OTP generation + storage (Member 2).

This is the file `services/notify_bridge.py` (M1) auto-detects. On a confirmed
match, M1 calls `notify_bridge.generate_otp(case_id)`, which finds this module
and calls `generate_and_store`. The OTP is stored in Redis at `otp:{case_id}`
(case_id = str(missing.id)) with TTL = OTP_TTL_SECONDS, so a verify-OTP endpoint
reads the same key.
"""

from __future__ import annotations

import secrets

from core.config import settings
from core.logging_utils import get_logger
from core.redis_client import redis_client

log = get_logger("nandi.otp")


async def generate_and_store(case_id: str) -> str:
    """Generate a 4-digit OTP, store it at `otp:{case_id}`, and return it."""
    code = f"{secrets.randbelow(10000):04d}"
    try:
        await redis_client.set(f"otp:{case_id}", code, ex=settings.OTP_TTL_SECONDS)
    except Exception as exc:  # Redis down — still return the code for the operator
        log.warning("could not persist OTP for case %s (%s)", case_id, exc)
    return code


async def verify(case_id: str, code: str) -> bool:
    """Check a submitted OTP against the stored one (used by the booth reunite step)."""
    try:
        stored = await redis_client.get(f"otp:{case_id}")
    except Exception as exc:
        log.warning("could not read OTP for case %s (%s)", case_id, exc)
        return False
    return bool(stored) and str(stored) == str(code).strip()
