"""
core.redis_client - shared async Redis connection.

Redis is used by several members:
  • M2  - OTP store (key `otp:{case_id}`) and blast idempotency keys
  • M4  - rate limiting
  • M1  - short-lived caches (optional)

This module just exposes one shared client and a FastAPI dependency. The actual
OTP / rate-limit logic lives in each owner's module - keep it that way so the
connection setup stays in exactly one place.
"""

from __future__ import annotations

from redis.asyncio import Redis

from core.config import settings

# decode_responses=True → str in / str out (no manual .decode() everywhere).
# from_url lazily connects on first command, so importing this module is cheap
# and does not fail when Redis is down (matters for graceful degradation).
redis_client: Redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    health_check_interval=30,
)


async def get_redis() -> Redis:
    """FastAPI dependency returning the shared Redis client."""
    return redis_client
