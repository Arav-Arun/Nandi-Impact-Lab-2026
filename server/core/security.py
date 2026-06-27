"""
core.security — lightweight auth dependencies shared across routes (SoW §12.1).

  • require_internal_key — guards `/internal/*` routes (server-to-server only).
    Checks `X-Internal-Key` against settings.INTERNAL_KEY.
  • get_booth_id        — extracts the mandatory `X-Booth-ID` on booth routes.

JWT issuing/verification for the dashboard lives with M4 (`/auth/login`). M1's
endpoints only need the internal key + booth id, so that's all this module owns.
"""

from __future__ import annotations

import uuid

from fastapi import Header, status

from core.config import settings
from core.responses import ApiError


async def require_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    """
    Dependency for internal-only routes. Rejects callers without the shared key.

    Use on `/internal/*` so the matching internals (e.g. /internal/validate) are
    not reachable from the public booth network.
    """
    if not x_internal_key or x_internal_key != settings.INTERNAL_KEY:
        raise ApiError(
            "UNAUTHORIZED_INTERNAL",
            "Missing or invalid X-Internal-Key",
            status.HTTP_401_UNAUTHORIZED,
        )


async def get_booth_id(x_booth_id: str | None = Header(default=None)) -> uuid.UUID:
    """
    Dependency that returns the booth UUID from the `X-Booth-ID` header.

    SoW §12.1 requires this header on all booth-facing routes so every action is
    attributable to a booth in the audit trail. Raises if absent/malformed.
    """
    if not x_booth_id:
        raise ApiError(
            "BOOTH_ID_REQUIRED",
            "X-Booth-ID header is required on booth routes",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        return uuid.UUID(str(x_booth_id))
    except (ValueError, AttributeError) as exc:
        raise ApiError(
            "BOOTH_ID_INVALID",
            "X-Booth-ID must be a valid UUID",
            status.HTTP_400_BAD_REQUEST,
        ) from exc
