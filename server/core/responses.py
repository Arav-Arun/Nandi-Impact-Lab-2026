"""
core.responses - the one response envelope every NANDI route returns (SoW §12.1).

    Success:  { "data": {...}, "error": null,  "timestamp": "ISO8601" }
    Error:    { "data": null,  "error": {"code": "ERR_CODE", "message": "..."},
                "timestamp": "ISO8601" }

Use `ok(data)` for success bodies. Raise `ApiError(code, message, status)` for
handled failures - `register_exception_handlers(app)` turns it (and any
unhandled exception) into the envelope shape. This keeps all four members'
endpoints wire-compatible so the frontend (M3/M4) parses one shape everywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _now_iso() -> str:
    """UTC timestamp, ISO-8601 with trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ok(data: Any = None) -> dict[str, Any]:
    """Build a success envelope body."""
    return {"data": data, "error": None, "timestamp": _now_iso()}


def err(code: str, message: str) -> dict[str, Any]:
    """Build an error envelope body."""
    return {
        "data": None,
        "error": {"code": code, "message": message},
        "timestamp": _now_iso(),
    }


class ApiError(Exception):
    """
    Raise for any expected, client-facing failure.

        raise ApiError("MATCH_NOT_FOUND", "No found_report with that id", 404)

    `register_exception_handlers` renders it as the standard error envelope.
    """

    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire ApiError, validation errors, and uncaught exceptions to the envelope."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=err(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Surface the first validation problem in a stable, parseable shape.
        detail = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        message = f"{'.'.join(str(p) for p in detail.get('loc', []))}: {detail.get('msg', '')}".strip(": ")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=err("VALIDATION_ERROR", message or "Invalid request"),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Last line of defence - never leak a stack trace in the body.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err("INTERNAL_ERROR", "An unexpected error occurred"),
        )
