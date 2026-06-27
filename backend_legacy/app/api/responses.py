"""Helpers for the NANDI response envelope: {data, error, timestamp}."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ok(data: Any) -> dict:
    return {"data": data, "error": None, "timestamp": _now()}


def err(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"data": None, "error": {"code": code, "message": message}, "timestamp": _now()},
    )
