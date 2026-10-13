"""Regression tests for the Emergent/Google sign-in bypass (Phase 0 audit S-02).

Before the fix, the API trusted identity data supplied by the browser:
- GET /api/auth/google/callback?token=<base64 JSON> signed in as any e-mail in that JSON;
- POST /api/auth/google/emergent-callback trusted ``emergent_user.email`` from the body.
"""
import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import decode_token
from routes import auth_routes, google_auth_routes
from services.emergent_auth_service import EmergentAuthError, emergent_session_verifier

ADMIN = {"id": "admin-1", "email": "admin@airyatra.com", "roles": ["admin"], "is_active": True, "full_name": "Admin"}


@pytest.fixture
def client(mock_db, monkeypatch):
    monkeypatch.setattr(auth_routes, "get_database", lambda: mock_db)
    monkeypatch.setattr(google_auth_routes, "get_database", lambda: mock_db)
    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(google_auth_routes.router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def emergent(monkeypatch):
    """Controls what Emergent says a session id belongs to."""
    sessions = {}

    async def verify(session_id):
        if session_id not in sessions:
            raise EmergentAuthError("unknown session")
        return dict(sessions[session_id])

    monkeypatch.setattr(emergent_session_verifier, "verify", verify)
    return sessions


async def _seed_admin(mock_db):
    await mock_db.users.insert_one(dict(ADMIN))


async def test_forged_base64_token_on_callback_does_not_sign_in(client, mock_db, emergent):
    await _seed_admin(mock_db)
    forged = base64.b64encode(json.dumps({"email": "admin@airyatra.com"}).encode()).decode()

    response = client.get(f"/api/auth/google/callback?token={forged}", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/auth/google/error" in location
    assert "/auth/google/success" not in location
    assert await mock_db.user_sessions.count_documents({}) == 0


def test_emergent_callback_ignores_identity_in_request_body(client, mock_db, emergent):
    response = client.post(
        "/api/auth/google/emergent-callback",
        json={"emergent_user": {"email": "admin@airyatra.com"}, "session_token": "anything"},
    )

    assert response.status_code == 401
    assert "access_token" not in response.text


def test_emergent_callback_signs_in_the_user_emergent_vouches_for(client, mock_db, emergent):
    emergent["sess-ok"] = {"id": "g-9", "email": "traveller@example.com", "name": "Traveller", "picture": "", "session_token": "st-9"}

    response = client.post(
        "/api/auth/google/emergent-callback",
        json={
            "session_id": "sess-ok",
            # A lying body must not change who is signed in.
            "emergent_user": {"email": "admin@airyatra.com"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "traveller@example.com"
    assert body["user"]["roles"] == ["customer"]
    assert body["is_new_user"] is True
    claims = decode_token(body["access_token"])
    assert claims["email"] == "traveller@example.com"


async def test_emergent_callback_keeps_existing_user_and_records_audit(client, mock_db, emergent):
    await mock_db.users.insert_one({**ADMIN, "email": "ops@example.com", "id": "ops-1", "roles": ["operator"]})
    emergent["sess-ops"] = {"id": "g-2", "email": "ops@example.com", "name": "", "picture": "", "session_token": "st-2"}

    response = client.post("/api/auth/google/emergent-callback", json={"session_id": "sess-ops"})

    assert response.status_code == 200, response.text
    assert response.json()["user"]["id"] == "ops-1"
    assert response.json()["is_new_user"] is False
    session = await mock_db.user_sessions.find_one({"user_id": "ops-1"})
    assert session["emergent_session_token"] == "st-2"
    assert await mock_db.audit_logs.count_documents({"action": "google_oauth_login"}) == 1


def test_emergent_callback_returns_404_when_disabled(client, monkeypatch):
    monkeypatch.setattr(emergent_session_verifier, "_enabled", False)
    response = client.post("/api/auth/google/emergent-callback", json={"session_id": "x"})
    assert response.status_code == 404
