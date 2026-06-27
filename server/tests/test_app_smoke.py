"""
tests.test_app_smoke — app-level smoke tests via FastAPI TestClient.

These run with NO infrastructure:
  • GET /health returns the standard envelope,
  • the four Member-1 routes are registered on app.routes,
  • GET /api/v1/match/{random_uuid} returns a well-formed envelope on the error
    path (it cannot succeed without a DB; we assert the envelope shape and error
    contract, and skip only the "must be exactly 404" assertion when no DB).

Envelope contract (SoW §12.1):
    success: {"data": <...>, "error": null,  "timestamp": ISO8601}
    error:   {"data": null,  "error": {"code","message"}, "timestamp": ISO8601}
"""

from __future__ import annotations

import uuid
from datetime import datetime

from tests.conftest import db_available


# ─────────────────────────────────────────────────────────────────────────────
# Envelope helpers
# ─────────────────────────────────────────────────────────────────────────────
def _assert_envelope_keys(body: dict) -> None:
    assert isinstance(body, dict)
    assert set(body.keys()) == {"data", "error", "timestamp"}
    # timestamp is a parseable ISO-8601 string (trailing Z form).
    ts = body["timestamp"]
    assert isinstance(ts, str) and ts
    datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _assert_success_envelope(body: dict) -> None:
    _assert_envelope_keys(body)
    assert body["error"] is None
    assert body["data"] is not None


def _assert_error_envelope(body: dict) -> None:
    _assert_envelope_keys(body)
    assert body["data"] is None
    assert isinstance(body["error"], dict)
    assert "code" in body["error"] and body["error"]["code"]
    assert "message" in body["error"]


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────
def test_health_returns_success_envelope(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    _assert_success_envelope(body)
    assert body["data"] == {"status": "ok", "service": "nandi-api"}


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────
def test_m1_routes_are_registered() -> None:
    from api.main import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    expected = {
        "/api/v1/match/{found_id}",
        "/api/v1/match/confirm",
        "/api/v1/match/reject",
        "/api/v1/internal/validate",
    }
    missing = expected - paths
    assert not missing, f"M1 routes not registered: {missing}"


def test_m1_route_methods() -> None:
    """GET on listing, POST on confirm/reject/validate."""
    from api.main import app

    methods: dict[str, set[str]] = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            methods.setdefault(route.path, set()).update(route.methods or set())

    assert "GET" in methods["/api/v1/match/{found_id}"]
    assert "POST" in methods["/api/v1/match/confirm"]
    assert "POST" in methods["/api/v1/match/reject"]
    assert "POST" in methods["/api/v1/internal/validate"]


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/match/{found_id} — envelope shape on the no-such-found / no-DB path
# ─────────────────────────────────────────────────────────────────────────────
def test_get_matches_returns_well_formed_envelope() -> None:
    """
    With a random UUID this can never succeed:
      • with a DB  → matcher raises ValueError → 404 FOUND_NOT_FOUND envelope,
      • without a DB → the session/query fails → 500 INTERNAL_ERROR envelope.
    Either way the *envelope shape* must hold. We assert that unconditionally,
    and only assert the precise 404 contract when a DB is actually available.

    We use raise_server_exceptions=False so that the DB-down 500 is rendered as
    the standard error envelope (the registered Exception handler) rather than
    re-raised out of the TestClient — that 500 envelope IS the error code path we
    want to assert when no live DB is present.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    random_id = uuid.uuid4()
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get(f"/api/v1/match/{random_id}")

    body = resp.json()
    _assert_error_envelope(body)
    assert resp.status_code in (404, 500)

    available, _ = db_available()
    if available:
        # With a live, migrated DB the contract is a clean 404.
        assert resp.status_code == 404
        assert body["error"]["code"] == "FOUND_NOT_FOUND"
    else:
        # No DB: the query fails deep in the handler → 500 INTERNAL_ERROR envelope.
        assert resp.status_code == 500
        assert body["error"]["code"] == "INTERNAL_ERROR"


def test_get_matches_rejects_non_uuid(client) -> None:
    """A non-UUID path param is a validation error → 422 envelope, no DB needed."""
    resp = client.get("/api/v1/match/not-a-uuid")
    assert resp.status_code == 422
    body = resp.json()
    _assert_error_envelope(body)
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# /internal/validate — guarded by X-Internal-Key (no DB needed for the auth path)
# ─────────────────────────────────────────────────────────────────────────────
def test_internal_validate_requires_key(client) -> None:
    """Without X-Internal-Key the route is rejected before any DB access."""
    resp = client.post(
        "/api/v1/internal/validate",
        json={"missing_id": str(uuid.uuid4()), "found_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401
    body = resp.json()
    _assert_error_envelope(body)
    assert body["error"]["code"] == "UNAUTHORIZED_INTERNAL"
